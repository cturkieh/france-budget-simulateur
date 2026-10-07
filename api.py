# api.py — point d'entrée FastAPI du moteur france-budget-simulateur
# (AGPL-3.0). Expose /simulate, /scenarios, /health et /. CORS configurable
# via la variable d'environnement CORS_ORIGINS (CSV) — par défaut, développement
# local uniquement.
#
# Le contrat de simulation (/simulate, /scenarios) vit dans `router` : c'est la
# SOURCE unique, limitation de débit de /simulate comprise (v0.6.7). Un
# déploiement qui ajoute sa propre infrastructure (monitoring, CORS de
# production) inclut ce routeur dans son app au lieu de recopier les endpoints —
# une copie diverge (constaté en v0.6.6 : un levier inconnu rendait 200 sur une
# copie, 422 ici).
#
# Limitation de débit de POST /simulate : seaux à jetons EN MÉMOIRE, PAR
# PROCESSUS (plusieurs workers = autant de seaux). Au-delà : 429 + `Retry-After`.
#   - par adresse cliente : BUDGETLAB_RATE_LIMIT_PER_MIN (défaut 120 ; 0 =
#     désactivé, comme dans les tests) ; mémoire bornée (_RATE_LIMIT_CLES_MAX) ;
#   - toutes adresses confondues : BUDGETLAB_RATE_LIMIT_GLOBAL_PER_MIN (défaut
#     3 000 ; 0 = désactivé), un DÉLESTAGE DE DERNIER RESSORT dimensionné sur la
#     capacité de l'instance. Le plafond global protège l'instance, pas les
#     utilisateurs : quiconque l'épuise coupe le service à tous, et la protection
#     par utilisateur exige une limite par adresse dont la clé est vérifiée
#     (BUDGETLAB_TRUST_PROXY, ci-dessous). Jamais de bannissement : un refus ne
#     consomme aucun jeton, le seau se recharge en une fenêtre (60 s) qu'on le
#     martèle ou non, et un refus global rend son jeton à la limite par adresse.
# Adresse cliente : le pair TCP, sauf si BUDGETLAB_TRUST_PROXY = N ≥ 1 déclare N
# proxys de confiance devant l'app ; la clé est alors le N-ième élément de
# `X-Forwarded-For` EN PARTANT DE LA FIN (1 = le dernier, celui qu'ajoute le
# proxy le plus proche). Chaque proxy AJOUTE l'adresse de son pair à la fin de
# la liste : les éléments de tête sont écrits par le client, qui peut les forger
# à volonté (une clé lue en tête rendrait la limite inopérante). Derrière Render,
# seuls les éléments de fin ajoutés par son infrastructure sont fiables : le bon
# N se vérifie au déploiement (une adresse forgée ne doit jamais apparaître dans
# le WARNING de refus). Sans proxy de confiance, ne posez pas la variable. Une
# adresse IPv6 compte pour son /64. Le « pair TCP » est `request.client`, qu'uvicorn
# réécrit LUI-MÊME depuis X-Forwarded-For quand le pair figure dans ses adresses de
# confiance (FORWARDED_ALLOW_IPS, 127.0.0.1 par défaut : c'est le cas en local,
# pas derrière Render) ; un client local peut donc y choisir sa clé, ce qui est sans
# enjeu hors production.
import ipaddress
import json
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from budget_simulator import BudgetSimulatorV45, EntreeInvalide, load_default_values

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    force=True,
)
logger = logging.getLogger(__name__)

# Horizon maximal servi : celui sur lequel le moteur est calibré (2025-2035).
# Au-delà, la trajectoire sort du domaine de validité (v0.6.7 : sur 50 ans, une
# consolidation maximale rendait une dette négative avec `valid: true`).
PERIODS_MAX = 10

# Limitation de débit de /simulate (cf. en-tête). 120/min par adresse : le
# simulateur du site relance un calcul au plus une fois par seconde de réglage
# (anti-rebond d'1 s), soit ~60/min pour un visiteur actif ; le double laisse
# passer deux visiteurs derrière la même adresse (établissement, rédaction, NAT
# d'opérateur) et borne un client automatisé à 2 calculs par seconde. 3 000/min
# au total : 50 calculs par seconde, l'ordre de la capacité d'un cœur (~7 ms le
# calcul en local, plus sur l'instance de production) — au-delà, refuser vaut
# mieux que laisser saturer le service ; en deçà, le plafond ne doit jamais
# mordre sur un usage réel. Il faut 25 adresses saturées en continu pour
# l'atteindre (3 000 / 120).
RATE_LIMIT_PAR_MIN_DEFAUT = 120
RATE_LIMIT_GLOBAL_PAR_MIN_DEFAUT = 3000
_RATE_LIMIT_CLES_MAX = 10_000
_CLE_GLOBALE = "*"


def _lire_limite_par_min(nom: str, defaut: float) -> float:
    """Variable d'environnement `nom` (requêtes par minute), ou `defaut` si
    absente ou vide. Une valeur invalide fait échouer le démarrage : une limite
    mal écrite ne se replie pas en silence sur une autre."""
    brut = os.getenv(nom, "").strip()
    if not brut:
        return float(defaut)
    valeur = float(brut)
    if not math.isfinite(valeur) or valeur < 0:
        raise ValueError(f"{nom}={brut!r} : nombre fini ≥ 0 attendu (0 = désactivé)")
    return valeur


def _lire_proxys_de_confiance() -> int:
    """BUDGETLAB_TRUST_PROXY : nombre de proxys de confiance devant l'app (0 si
    absente). Un booléen (« true ») ou tout autre texte fait échouer le
    démarrage : le nombre de proxys décide de l'élément lu, il ne se devine pas."""
    brut = os.getenv("BUDGETLAB_TRUST_PROXY", "").strip()
    if not brut:
        return 0
    if not brut.isdigit():
        raise ValueError(f"BUDGETLAB_TRUST_PROXY={brut!r} : nombre de proxys de confiance "
                         "attendu (0, 1, 2…) — 1 = dernier élément de X-Forwarded-For")
    return int(brut)


class _LimiteurDebit:
    """Seau à jetons par clé : `capacite` jetons au plus, rechargés au débit de
    `capacite` par minute ; une requête consomme un jeton. Au-delà de `cles_max`
    clés, la moins récemment vue est oubliée — l'équivalent d'un seau plein, donc
    sans effet pour une clé restée inactive une minute."""

    def __init__(self, par_minute: float, cles_max: int = _RATE_LIMIT_CLES_MAX,
                 horloge=time.monotonic):
        self.capacite = float(par_minute)
        self._debit = self.capacite / 60.0  # jetons par seconde
        self._cles_max = cles_max
        self._horloge = horloge
        self._seaux: OrderedDict[str, tuple[float, float, bool]] = OrderedDict()
        self._verrou = threading.Lock()

    def prendre(self, cle: str) -> tuple[float, bool]:
        """(0.0, False) si la requête passe ; sinon (secondes avant le prochain
        jeton, True au premier refus d'un épisode — pour le tracer une fois)."""
        maintenant = self._horloge()
        with self._verrou:
            jetons, dernier, en_refus = self._seaux.pop(cle, (self.capacite, maintenant, False))
            jetons = min(self.capacite, jetons + (maintenant - dernier) * self._debit)
            if jetons >= 1.0:
                resultat, en_refus = (0.0, False), False
                jetons -= 1.0
            else:
                resultat, en_refus = ((1.0 - jetons) / self._debit, not en_refus), True
            self._seaux[cle] = (jetons, maintenant, en_refus)
            while len(self._seaux) > self._cles_max:
                self._seaux.popitem(last=False)
        return resultat

    def rendre(self, cle: str) -> None:
        """Rend le jeton d'une requête acceptée ici puis refusée plus loin
        (plafond global) : ce refus ne coûte rien à la clé."""
        with self._verrou:
            if cle in self._seaux:
                jetons, dernier, en_refus = self._seaux[cle]
                self._seaux[cle] = (min(self.capacite, jetons + 1.0), dernier, en_refus)


_xff_ignore_signale = False


def _adresse_cliente(request: Request, proxys: int) -> str:
    """Clé du seau. Sans proxy de confiance (`proxys` = 0) : le pair TCP,
    `X-Forwarded-For` n'est jamais lu (le client l'écrit). Avec N proxys : le
    N-ième élément EN PARTANT DE LA FIN, celui qu'a ajouté le plus lointain des
    proxys de confiance — jamais un élément de tête, que le client contrôle ;
    liste trop courte ou élément invalide → le pair TCP. IPv6 regroupée par /64
    (l'unité qu'un abonné reçoit)."""
    global _xff_ignore_signale
    candidats = []
    valeurs = request.headers.getlist("x-forwarded-for")
    if proxys > 0:
        elements = [e.strip() for e in ",".join(valeurs).split(",")]
        if len(elements) >= proxys:
            candidats.append(elements[-proxys])
    elif valeurs and not _xff_ignore_signale:
        _xff_ignore_signale = True
        logger.warning("X-Forwarded-For reçu sans BUDGETLAB_TRUST_PROXY : la limite de débit "
                       "porte sur le pair TCP — derrière un proxy, c'est LE PROXY, donc une "
                       "seule clé pour tous les visiteurs (cf. en-tête d'api.py)")
    if request.client is not None:
        candidats.append(request.client.host)
    for brut in candidats:
        try:
            ip = ipaddress.ip_address(brut)
        except ValueError:
            continue
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if ip.version == 6:
            return str(ipaddress.ip_network(f"{ip}/64", strict=False))
        return str(ip)
    return request.client.host if request.client is not None else "inconnu"


def _cle_masquee(cle: str) -> str:
    """La clé tronquée pour les journaux (IPv4 /24, IPv6 /48) : pas d'adresse
    complète dans les logs."""
    try:
        reseau = ipaddress.ip_network(cle, strict=False)
    except ValueError:
        return cle
    return str(reseau.supernet(new_prefix=24 if reseau.version == 4 else 48))


_limite_par_min = _lire_limite_par_min("BUDGETLAB_RATE_LIMIT_PER_MIN", RATE_LIMIT_PAR_MIN_DEFAUT)
_limite_globale_par_min = _lire_limite_par_min("BUDGETLAB_RATE_LIMIT_GLOBAL_PER_MIN",
                                               RATE_LIMIT_GLOBAL_PAR_MIN_DEFAUT)
_proxys_de_confiance = _lire_proxys_de_confiance()
_limiteur = _LimiteurDebit(_limite_par_min) if _limite_par_min > 0 else None
_limiteur_global = (_LimiteurDebit(_limite_globale_par_min, cles_max=1)
                    if _limite_globale_par_min > 0 else None)
logger.info("Limite de débit /simulate : %s par adresse (%s), %s au total",
            f"{_limite_par_min:g}/min" if _limiteur else "désactivée",
            f"X-Forwarded-For[-{_proxys_de_confiance}]" if _proxys_de_confiance else "pair TCP",
            f"{_limite_globale_par_min:g}/min" if _limiteur_global else "désactivée")


def _refus(attente: float, detail: str) -> HTTPException:
    secondes = max(1, math.ceil(attente))
    return HTTPException(status_code=429, detail=detail.format(secondes=secondes),
                         headers={"Retry-After": str(secondes)})


def _limiter_debit(request: Request) -> None:
    """Dépendance de POST /simulate : 429 au-delà de la limite par adresse, puis du
    plafond global (cf. en-tête). Le refus passe par le gestionnaire d'exceptions
    de FastAPI, donc par le CORS de l'app : le navigateur le lit comme un refus,
    pas comme une panne réseau."""
    cle = None
    if _limiteur is not None:
        cle = _adresse_cliente(request, _proxys_de_confiance)
        attente, nouveau_refus = _limiteur.prendre(cle)
        if attente:
            if nouveau_refus:
                logger.warning("Limite de débit /simulate atteinte (%s, %g/min) : 429",
                               _cle_masquee(cle), _limiteur.capacite)
            raise _refus(attente, "Trop de simulations en peu de temps depuis cette "
                                  "connexion : réessayez dans {secondes} s.")
    if _limiteur_global is not None:
        attente, nouveau_refus = _limiteur_global.prendre(_CLE_GLOBALE)
        if attente:
            if cle is not None:
                _limiteur.rendre(cle)
            if nouveau_refus:
                # Systémique (pic d'audience ou attaque distribuée) : ERROR, donc
                # remonté par l'observabilité de la production, une fois par épisode.
                logger.error("Plafond global de /simulate atteint (%g/min, toutes adresses) : "
                             "429 pour tous les visiteurs", _limiteur_global.capacite)
            raise _refus(attente, "Le simulateur reçoit trop de demandes en ce moment : "
                                  "réessayez dans {secondes} s.")


class SimulationRequest(BaseModel):
    """Requête de simulation avec validation stricte."""
    mesures: dict[str, Any] | None = Field(default_factory=dict)
    periods: int = Field(default=10, ge=1, le=PERIODS_MAX)

    @field_validator('mesures')
    @classmethod
    def validate_mesures(cls, v):
        if v and len(str(v)) > 50000:
            raise ValueError('Le dictionnaire de mesures est trop volumineux')
        return v


router = APIRouter()


def _erreurs_d_entree(groupe: BaseExceptionGroup) -> list[str] | None:
    """Messages des erreurs d'entrée d'un ExceptionGroup strict, ou None si le
    groupe contient AUSSI autre chose (un bug moteur ne se déguise pas en
    faute client)."""
    entrees, reste = groupe.split(EntreeInvalide)
    if entrees is None or reste is not None:
        return None
    messages = []
    pile = [entrees]
    while pile:
        for exc in pile.pop().exceptions:
            if isinstance(exc, BaseExceptionGroup):
                pile.append(exc)
            else:
                messages.append(str(exc))
    return messages


@router.post("/simulate", dependencies=[Depends(_limiter_debit)])
async def simulate(request: SimulationRequest):
    """Lance une simulation budgétaire.

    Contrat (v0.6.7) :
    - **422** : levier inconnu du registre `policy_measures.json` (avec la
      liste des clés), `periods` hors de [1, 10], payload trop volumineux ; et,
      en mode strict (`BUDGETLAB_STRICT=1` côté serveur), toute valeur
      invalide sur un paramètre déclaré (non numérique, non finie, hors
      domaine), avec la liste des valeurs fautives.
    - **200 en mode tolérant** (configuration de production) : une valeur hors
      domaine est **ramenée à la borne**, une valeur non finie (NaN, ±inf,
      entier trop grand pour un nombre flottant) est **retirée** (le levier
      applique son défaut), une valeur non numérique fait **échouer le
      levier** (effet compté nul, `_handler_failed: true` dans
      `measure_impacts`). Rien n'est silencieux : chaque correction figure dans
      `report.warnings` (préfixe « Entrée ou sortie corrigée ») et passe
      `report.valid` à `false` ; le serveur trace un WARNING par levier.
    - `report.valid` = le résultat se lit tel quel : aucune entrée corrigée,
      aucun levier en échec, aucune borne de sortie atteinte (variation
      annuelle du pouvoir d'achat ou de la compétitivité, Gini, dette ≥ 0). Il
      ne juge PAS la soutenabilité (une dette finale > 160 % figure dans
      `report.critical`).
    - `report.warnings` porte aussi des avis qui n'invalident pas le résultat
      (préfixe « Avis ») : bloc vide `{}` (le levier est appliqué avec TOUS ses
      défauts, ce qui n'est pas neutre pour `taxe_superprofits`), impact d'une
      mesure plafonné à 5 % du PIB (plafond du modèle).
    - `null` = « pas de valeur », dans les deux modes (tolérant et strict) :
      - `null` sur un PARAMÈTRE (`{"csg": {"taux": null}}`) = défaut du
        levier pour ce paramètre, y compris pour un booléen
        (`{"taxe_superprofits": {"tous_secteurs": null}}` = tous secteurs,
        le défaut) — exactement comme si la clé était omise ;
      - `null` sur un LEVIER ENTIER connu (`{"taxe_superprofits": null}`) =
        levier ABSENT : non appliqué, absent des impacts, résultat identique à une
        requête sans cette clé. Un levier INCONNU reste rejeté en 422, même à
        `null`.
      Préférer omettre la clé ; le serveur trace un WARNING `PARAM_NULL`.
    - **429** : plus de `BUDGETLAB_RATE_LIMIT_PER_MIN` requêtes par minute
      (défaut 120) depuis la même adresse cliente, ou plus de
      `BUDGETLAB_RATE_LIMIT_GLOBAL_PER_MIN` (défaut 3 000, délestage de l'instance) toutes adresses
      confondues ; `Retry-After` donne le délai en secondes. Limites par
      processus, désactivées à 0 ; adresse = pair TCP, ou élément de fin de
      `X-Forwarded-For` si `BUDGETLAB_TRUST_PROXY` déclare des proxys de
      confiance (cf. en-tête du module).
    - **500** : bug du moteur (y compris un résultat non fini), journalisé.
      Le nom d'un paramètre n'est pas validé : une faute de frappe
      (`{"tva_rate": {"tauxx": 0.25}}`) applique le défaut du levier.
    """
    mesures = request.mesures or {}
    # Instantiation moteur (chargement policy_measures.json + registre).
    # En cas d'échec systémique (fichier corrompu, schema cassé) → 500.
    try:
        sim = BudgetSimulatorV45(periods=request.periods, mesures=mesures)
    except Exception as e:
        logger.error("Échec instantiation moteur : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur initialisation moteur: {e}" if DEBUG_MODE
            else "Erreur initialisation moteur. L'incident a été journalisé."
        )

    # Validation explicite des leviers : un POST avec une clé inconnue ne doit
    # pas retourner 200 status-quo silencieusement. Le moteur tolère (continue
    # silencieux dans orchestrator.apply_measures) par compat historique —
    # l'API publique impose l'invariant côté contrat externe.
    unknown_levers = sorted(set(mesures) - set(sim.measure_registry))
    if unknown_levers:
        logger.warning("Leviers inconnus rejetés : %s", unknown_levers)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Leviers inconnus : {unknown_levers}. "
                f"Voir GET /scenarios pour les leviers valides."
            ),
        )

    try:
        results, details, report = sim.simulate()
    except BaseExceptionGroup as groupe:
        # Mode strict : le moteur collecte les échecs d'une année dans un
        # ExceptionGroup. Que des erreurs d'entrée → faute client, 422.
        erreurs = _erreurs_d_entree(groupe)
        if erreurs is not None:
            logger.warning("Simulation rejetée (mode strict, entrée invalide) : %s", erreurs)
            raise HTTPException(status_code=422,
                                detail=f"Paramètres invalides : {erreurs}")
        logger.error("Bug moteur (mode strict) : %s", groupe, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du moteur : {groupe}" if DEBUG_MODE
            else "Erreur interne du moteur. L'incident a été journalisé."
        )
    except (EntreeInvalide, ValueError) as e:
        # Paramètres hors domaine (clamp/range moteur) — faute client légitime.
        logger.warning("Simulation rejetée (paramètres hors domaine) : %s", e)
        raise HTTPException(
            status_code=422,
            detail=f"Paramètres invalides: {e}"
        )
    except (KeyError, AttributeError, TypeError, ZeroDivisionError) as e:
        # Bug interne du moteur (clé manquante, type incohérent, /0).
        # 500 explicite, pas 400 — distinction « faute client » vs « bug serveur ».
        logger.error("Bug moteur (%s) : %s", type(e).__name__, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du moteur ({type(e).__name__}). L'incident a été journalisé."
            if DEBUG_MODE
            else "Erreur interne du moteur. L'incident a été journalisé."
        )
    except Exception as e:
        logger.error("Erreur inattendue : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur inattendue: {e}" if DEBUG_MODE else "Erreur interne inattendue."
        )

    if 'measure_impacts_by_year' not in report:
        # Drift de contrat moteur — échec systémique (le front affichera un
        # tableau d'impacts vide). logger.error → remontée Sentry côté infra.
        logger.error(
            "Drift contrat moteur : 'measure_impacts_by_year' absent du report "
            "(periods=%d, n_mesures=%d)",
            request.periods, len(mesures)
        )
    measure_impacts = report.pop('measure_impacts_by_year', [])

    payload = {
        "success": True,
        "results": results.to_dict(orient='records'),
        "details": details.to_dict(orient='records'),
        "report": report,
        "measure_impacts": measure_impacts,
        "logs": sim.debug_logs[:200] if DEBUG_MODE else []
    }
    # Sérialisation éprouvée ICI : FastAPI encode la réponse APRÈS le retour
    # de l'endpoint, hors de tout `try`. Un NaN/inf moteur y lèverait au-dessus
    # du middleware CORS → 500 SANS en-tête CORS, que le navigateur ne voit que
    # comme un échec réseau. Ici, il devient un 500 explicite, avec CORS.
    try:
        json.dumps(jsonable_encoder(payload), allow_nan=False)
    except ValueError as e:
        logger.error("Résultat moteur non sérialisable (NaN/inf) : %s", e)
        raise HTTPException(
            status_code=500,
            detail="Résultat du moteur non fini. L'incident a été journalisé."
        )
    return payload


@router.get("/scenarios")
async def get_scenarios():
    """Retourne des scénarios d'exemple (toutes valeurs dans les domaines du
    moteur : chacun passe en mode strict sans correction)."""
    try:
        status_quo = load_default_values()
    except Exception as e:
        logger.error("Échec chargement valeurs par défaut : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Configuration des valeurs par défaut indisponible."
        )
    return {
        "status_quo": status_quo,
        "austerite": {
            "impot_societes": {"taux": 0.33},
            "tva_rate": {"taux": 0.23},
            "retraites": {"age_depart": 64.0}
        },
        "scandinave": {
            "retraites": {"age_depart": 64.0},
            "education": {"budget": 85.0},
            "transition_ecologique": {"investissement": 25.0},
            # Intensité ∈ [0 ; 1], cible = effort × 30 Md€ : 0,67 ≈ 20 Md€.
            # L'ancienne valeur 20 datait de la lecture en Md€, supprimée en
            # v0.6.3 (elle était clampée à 1,0, et rejetée en strict).
            "fraude_fiscale": {"effort": 0.67}
        },
        "relance_verte": {
            "transition_ecologique": {"investissement": 40.0},
            "education": {"budget": 85.0}
        }
    }


app = FastAPI(
    title="Simulateur Budget France API",
    description="API publique du moteur économique france-budget-simulateur (AGPL-3.0)",
    version="4.5"
)

# Origines CORS — surcharge via env var CORS_ORIGINS (séparées par virgules).
# Défaut : localhost dev seulement. Un déploiement ajoute son domaine publique.
_DEFAULT_CORS_ORIGINS = ",".join(
    f"http://localhost:{port}"
    for port in (3000, 3001, 3002, 3003, 3004, 3005, 5173, 8501)
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
@app.head("/")
async def root():
    """Route racine — info API (supporte GET et HEAD pour health checks plateforme)."""
    return {
        "name": "France Budget API",
        "version": "4.5",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "simulate": "/simulate (POST)",
            "scenarios": "/scenarios (GET)",
            "documentation": "/docs"
        },
        "debug_mode": DEBUG_MODE
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "version": "4.5",
        "service": "budget-simulator-api",
        "debug_mode": DEBUG_MODE
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=DEBUG_MODE
    )
