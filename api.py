# api.py — point d'entrée FastAPI du moteur france-budget-simulateur
# (AGPL-3.0). Expose /simulate, /scenarios, /health et /. CORS configurable
# via la variable d'environnement CORS_ORIGINS (CSV) — par défaut, développement
# local uniquement.
#
# Le contrat de simulation (/simulate, /scenarios) vit dans `router` : c'est la
# SOURCE unique. Un déploiement qui ajoute sa propre infrastructure (monitoring,
# CORS de production, limitation de débit) inclut ce routeur dans son app au
# lieu de recopier les endpoints — une copie diverge (constaté en v0.6.6 : un
# levier inconnu rendait 200 sur une copie, 422 ici).
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
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


@router.post("/simulate")
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
