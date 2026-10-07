"""Garde-fou de domaine des paramètres d'intensité — Lot C Item 1.

Porte unique (consommée par ``engine/orchestrator.py::apply_measures``,
juste avant le dispatch handler) qui valide ``params['intensite']``
contre le domaine légitime du levier (registre ``INTENSITE_DOMAINS``,
``budget_simulator/constants.py``).

Pourquoi : le slider frontend borne déjà l'utilisateur, mais les
entrées HORS-UI (scénarios politiques, API, config) ne passent par
AUCUN clamp backend pour ``optimisation_dette`` / ``isf_climatique`` /
``taxe_superprofits`` / ``exonerations_salaires`` (et un clamp
*silencieux* pour ``fiscalite_patrimoine``). Une valeur aberrante était
donc soit propagée sans alerte, soit écrasée sans trace. Cf.
``docs/MINI_DESIGN_ITEM1_BORNE_INTENSITE.md``.

Dualité STRICT/tolérant — même contrat que le reste du moteur :
- tolérant (prod, service citoyen) : ``logger.warning`` + clamp à la
  borne la plus proche ; NE CASSE JAMAIS le service. Modèle éprouvé
  ``handlers/additionnels.py`` (plafond superprofits/exonérations).
- ``BUDGETLAB_STRICT`` (CI/calibration) : ``raise ValueError``. Capté
  par l'``except`` existant de ``apply_measures`` → annoté
  ``measure_id`` → collecté → remonté dans l'``ExceptionGroup`` de fin
  de boucle. SYNERGIE Lot C Item 3 : aucune mécanique d'escalade
  nouvelle.

Contrainte dure MIXIN_BAD_PARAMS (mini-design §3.3, cf.
``tests/test_handler_failure_flag.py``) : la comparaison numérique se
fait SANS garde ``try/except`` et SANS normaliser une ``str``. Une
``str`` lève ``TypeError`` au premier comparateur — comportement VOULU
(remonte, ``_handler_failed=True``, ``ExceptionGroup`` strict),
strictement identique au contrat pré-Item 1. Le test
``test_str_intensite_*`` est load-bearing.
"""
import logging
import math
from typing import Dict

from ..constants import INTENSITE_DOMAINS, PARAM_DOMAINS

logger = logging.getLogger(__name__)

# Nombre de paramètres détaillés dans UN WARNING agrégé (au-delà : « +N
# autres »). Un bloc de milliers de clés fautives ne produit plus qu'une ligne
# par levier et par catégorie (volume Sentry Logs, backlog 2026-10-05 (2)).
_DETAILS_MAX = 5


class EntreeInvalide(Exception):
    """Faute de l'APPELANT sur la valeur d'un paramètre déclaré (hors domaine,
    non finie, non numérique) — v0.6.7. Base commune qui permet à l'API de
    répondre 422 en mode strict (faute client), et à l'orchestrateur de tracer
    un WARNING au lieu d'un ERROR (bug moteur) quand le levier échoue."""


class ValeurInvalide(EntreeInvalide, ValueError):
    """Valeur numérique hors domaine ou non finie (mode BUDGETLAB_STRICT)."""


class ValeurNonNumerique(EntreeInvalide, TypeError):
    """Valeur non numérique (``"bad"``, liste…) sur un paramètre numérique
    déclaré. Sous-classe de ``TypeError`` : le contrat MIXIN_BAD_PARAMS (une
    ``str`` remonte en TypeError, levier en échec, ExceptionGroup en strict)
    est préservé, la faute est seulement QUALIFIÉE."""


def _est_fini(value) -> bool:
    """``math.isfinite`` qui ne lève pas sur un entier JSON trop grand pour un
    float (``10**400`` → OverflowError) : un tel entier est traité comme non
    fini, au lieu de faire échouer le levier (ou, hors porte, la requête)."""
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _apercu(value) -> str:
    """``repr`` borné — un entier de 400 chiffres ne s'imprime pas en entier
    dans un log ni dans un rapport."""
    texte = repr(value)
    return texte if len(texte) <= 40 else texte[:37] + '...'


def _noter(corrections: dict | None, measure_id: str, key, texte: str) -> None:
    """Consigne une correction d'entrée pour le rapport de simulation
    (``report['warnings']``, ``report['valid']``) — dédupliquée par
    (levier, paramètre) : la porte tourne chaque année simulée."""
    if corrections is not None:
        corrections.setdefault((measure_id, key), texte)


def _avertir_agrege(warned: set | None, measure_id: str, jeton: str,
                    details: list, consequence: str) -> None:
    """UN ``logger.warning`` par (levier, catégorie) et par simulation, qui
    liste les paramètres concernés (au plus ``_DETAILS_MAX``). Avant v0.6.7 :
    une ligne par clé, soit des milliers pour un bloc de milliers de clés."""
    if not details:
        return
    resume = ', '.join(details[:_DETAILS_MAX])
    if len(details) > _DETAILS_MAX:
        resume += f" (+{len(details) - _DETAILS_MAX} autres)"
    _avertir_une_fois(warned, (measure_id, jeton), "%s %s — %s",
                      jeton, resume, consequence)


def _avertir_une_fois(warned: set | None, cle: tuple, msg: str, *args) -> None:
    """``logger.warning`` dédupliqué sur la simulation via ``warned`` (set
    détenu par l'appelant ; ``None`` = pas de dédup). La porte tourne chaque
    année simulée : sans dédup, une seule anomalie = ~10 lignes identiques."""
    if warned is not None and cle in warned:
        return
    logger.warning(msg, *args)
    if warned is not None:
        warned.add(cle)


def _tracer_null(libelle: str, consequence: str, cle_dedup: tuple,
                 warned: set | None) -> None:
    """WARNING ``PARAM_NULL`` — token stable, filtrable dans Sentry Logs.
    Clé suffixée ``'null'`` : espace distinct des clés ``(mesure, param)`` du
    clamp et de la finitude, qui partagent le même set ``warned``."""
    _avertir_une_fois(
        warned, cle_dedup,
        "PARAM_NULL %s=None — %s (null = pas de valeur ; l'appelant devrait "
        "omettre la clé)",
        libelle, consequence,
    )


def tracer_si_levier_null(measure_id: str, params, *,
                          warned: set | None = None) -> bool:
    """Vrai ssi le bloc du levier est ``None`` (``{"levier": null}``), auquel
    cas un WARNING ``PARAM_NULL`` dédupliqué est tracé. L'appelant
    (``apply_measures``) SAUTE alors le levier : null = « pas de valeur » =
    levier ABSENT, et non ``{}`` — ``{}`` n'est pas neutre (ex.
    ``{"taxe_superprofits": {}}`` applique la taxe à 25 % tous secteurs, choix
    de conception antérieur). Les lecteurs latéraux de ``self.mesures``
    partagent la même règle via ``leviers_presents`` et ``valeur_brute``.

    Seul ``None`` est concerné. Un bloc MAL FORMÉ (liste, nombre, str) rend
    ``False`` et échoue BRUYAMMENT au premier accès de la porte
    (``logger.error`` + ``HANDLER_FAILED_KEY``, ``ExceptionGroup`` en strict)
    — décision verrouillée par
    ``tests/test_asu_prestations_indexation_contract.py::test_malformed_asu_fails_loudly_not_silently``
    : un raccourci humain ``{'asu': 1}`` est une faute à remonter, pas une
    absence.
    """
    if params is not None:
        return False
    _tracer_null(measure_id, "levier ignoré, comme s'il était absent",
                 (measure_id, None, 'null'), warned)
    return True


def leviers_presents(mesures: Dict) -> Dict:
    """``mesures`` sans les leviers à ``None`` — la vue « levier absent » que
    doivent partager les lecteurs de ``self.mesures`` BRUT (hash des mesures,
    journalisation). Objet IDENTIQUE quand aucun bloc n'est null (golden
    byte-identique) ; sinon copie, l'entrée n'est jamais mutée."""
    if all(v is not None for v in mesures.values()):
        return mesures
    return {k: v for k, v in mesures.items() if v is not None}


def valeur_brute(mesures: Dict, measure_id: str, param: str, defaut):
    """``mesures[measure_id][param]`` pour un lecteur LATÉRAL de
    ``self.mesures`` brut (hors porte unique), avec la sémantique « null =
    pas de valeur » de la porte : bloc absent, ``null`` ou mal formé →
    ``defaut`` ; clé absente ou ``None`` → ``defaut``. Un bloc mal formé est
    neutre ici, son anomalie ressortant par la porte d'``apply_measures``
    (``logger.error`` + ``HANDLER_FAILED_KEY``). NaN, ±inf et types non
    numériques sont rendus tels quels : au lecteur de les neutraliser."""
    bloc = mesures.get(measure_id)
    if not isinstance(bloc, dict):
        return defaut
    valeur = bloc.get(param)
    return defaut if valeur is None else valeur


def _refuser_non_finis(measure_id: str, params: Dict, *,
                       strict: bool, warned: set | None,
                       corrections: dict | None = None) -> Dict:
    """Porte de FINITUDE — universelle, indépendante de tout domaine déclaré.

    Pourquoi elle est séparée de la boucle de domaines (clôture de la revue
    adverse, 2026-08-26) : ``PARAM_DOMAINS`` ne couvre que deux leviers, et
    ``validate_param_domains`` rendait donc ``params`` tel quel — sans même
    regarder les valeurs — pour tous les autres. Un NaN traversait ``csg.taux``
    ou ``collectivites.dotation``, rendait déficit ET dette ``nan`` sur tout
    l'horizon publié, et ne levait rien MÊME sous ``BUDGETLAB_STRICT=1``. Or
    ce sont exactement les deux paramètres que le lot 9 venait de rendre
    porteurs : durcir levier par levier (comme au lot 7 pour
    ``asu.asu_plafonnement``) laisse toujours le prochain levier ouvert. La
    finitude est une propriété de TOUT paramètre numérique, pas d'une liste.

    Contrat dual, aligné sur le reste du moteur :
    - ``strict`` → ``ValueError`` (captée par l'``except`` d'``apply_measures``
      → ``ExceptionGroup`` de fin de boucle) ;
    - tolérant → la clé est RETIRÉE et le retrait tracé. Retirer, et non
      clamper : aucune borne n'étant déclarée pour ce paramètre, toute valeur
      de repli serait inventée, alors que l'absence de clé a une sémantique
      déjà définie et NEUTRE (le handler applique son défaut).

    Elle s'applique AUSSI aux paramètres qui ont un domaine, et c'est
    délibéré : jusqu'ici la boucle de domaines clampait un NaN à la BORNE
    BASSE, ce qui n'est pas un repli neutre mais une POSITION — sur
    ``retraites.indexation`` la borne basse, c'est le gel total des pensions.
    Or un NaN ne dit pas « trop bas », il dit « pas de valeur » : le seul
    repli qui n'invente rien est le défaut du handler. Une seule règle pour
    une seule condition, sinon deux lectures du même objet coexistent.

    ``None`` (JSON ``null``) — même porte, même repli, contrat différent
    (Sentry FRANCE-BUDGET-Z, 2026-10) : ``None`` dit lui aussi « pas de
    valeur », et c'est même sa seule signification. Le laisser passer
    trahissait la sémantique annoncée : ``params.get('montant', 97)`` rend
    ``None`` (la clé EXISTE), pas le défaut, et ``97 - None`` lève — mesure
    comptée à 0 + une ERROR par année simulée. La clé est donc RETIRÉE, comme
    pour NaN, et tracée par un WARNING ``PARAM_NULL`` dédupliqué. Mais dans
    les DEUX modes, sans escalade stricte : un NaN est un poison de calcul (un
    amont a divisé par zéro), alors qu'un ``None`` est une absence déclarée,
    déjà LÉGITIME en strict pour ``intensite`` (« slider non posé »,
    ``validate_intensite_domain``). Inventaire préalable (2026-10) : pour la
    plupart des lecteurs, ``None`` faisait lever (``params.get(k, défaut)``
    rend ``None``, l'arithmétique échoue) ou se confondait déjà avec
    l'absence (tests ``is None`` de ``_resolve_intensite_or_legacy`` et
    ``_seniors``). DEUX lecteurs lui donnaient en silence un sens distinct, et
    ce retrait CHANGE donc leur résultat observable (alignement voulu sur la
    clé absente) :

    - ``taxe_superprofits.tous_secteurs: null`` était lu comme FAUX (assiette
      énergie seule) ; il vaut désormais le défaut ``True`` (tous secteurs) ;
    - ``asu.asu_activation: null`` ACTIVAIT l'ASU (``None == 0`` faux dans
      ``_apply_asu``, ``None != 0`` vrai dans ``asu_is_active``) ; il vaut
      désormais le défaut 0 (ASU inactive).

    Règle uniforme, booléens compris : ``null`` sur un paramètre = défaut du
    levier. Propriété verrouillée pour chaque (mesure, paramètre) du
    registre : ``tests/test_param_null_porte.py``.

    Une valeur non numérique est ignorée ici : le contrat MIXIN_BAD_PARAMS
    veut qu'une ``str`` lève ``TypeError`` au comparateur de domaine, jamais
    qu'elle soit avalée par une garde de finitude. ``None`` n'est pas une
    valeur mal typée : c'est l'absence de valeur.
    """
    # Clés à retirer, accumulées puis retirées en UNE reconstruction : un
    # retrait clé par clé recopiait le dict à chaque fois (quadratique sur un
    # bloc de milliers de null, payload JSON standard sous la limite de taille).
    # v0.6.7 : journalisation AGRÉGÉE par levier (une ligne par catégorie, et
    # non une par clé) ; un entier trop grand pour un float (10**400) est non
    # fini, comme inf.
    retirees = set()
    nulls, non_finis = [], []
    for key, value in params.items():
        if value is None:
            nulls.append(f"{measure_id}.{key}=None")
        elif (isinstance(value, bool) or not isinstance(value, (int, float))
              or _est_fini(value)):
            continue
        elif strict:
            raise ValeurInvalide(
                f"{measure_id}.{key}={_apercu(value)} non fini (NaN/inf) — "
                f"empoisonnerait toute la trajectoire (mode BUDGETLAB_STRICT)"
            )
        else:
            non_finis.append(f"{measure_id}.{key}={_apercu(value)}")
            _noter(corrections, measure_id, key,
                   f"{measure_id}.{key}={_apercu(value)} : valeur non finie, "
                   f"retirée — le levier applique son défaut pour ce paramètre")
        retirees.add(key)
    _avertir_agrege(warned, measure_id, 'PARAM_NULL', nulls,
                    "retiré, le handler applique son défaut (null = pas de "
                    "valeur ; l'appelant devrait omettre la clé)")
    _avertir_agrege(warned, measure_id, 'PARAM_NON_FINI', non_finis,
                    "clé retirée, le handler retombe sur son défaut (mode "
                    "tolérant : service préservé, entrée appelante à corriger)")
    if not retirees:
        return params  # chemin nominal : objet identique, aucune copie
    return {k: v for k, v in params.items() if k not in retirees}


def validate_param_domains(measure_id: str, params: Dict, *, strict: bool,
                           warned: set | None = None,
                           corrections: dict | None = None) -> Dict:
    """Valide/borne les paramètres NOMMÉS de ``measure_id`` selon
    ``PARAM_DOMAINS`` (revue 2026-08-04) — même contrat dual que
    ``validate_intensite_domain`` : no-op (objet identique) pour toute
    entrée légitime ou clé absente, ``ValueError`` en strict sinon,
    ``logger.warning`` + copie clampée en tolérant. Une clé à ``None`` est
    RETIRÉE dans les deux modes (copie, WARNING ``PARAM_NULL``) : le handler
    applique son défaut, comme pour la clé absente — cf. ``_refuser_non_finis``.
    Une ``str`` lève TypeError au comparateur (contrat MIXIN_BAD_PARAMS, pas
    de garde).

    ``warned`` (optionnel) : set détenu par l'appelant, portée = une
    simulation. La fonction est appelée chaque année simulée pour la même
    entrée ; sans dédup, une seule erreur produit ~10 lignes WARNING
    identiques (bruit pur pour Sentry Logs). Le CLAMP lui-même reste
    appliqué chaque année — seule la journalisation est dédupliquée.

    Raison d'être : les handlers symétrisés (retraites, prestations)
    font désormais de l'arithmétique inconditionnelle — un NaN n'y est
    plus neutralisé par accident et empoisonnerait toute la trajectoire
    sans signal (cf tests/test_param_domains_guard.py).

    Deux étages depuis la clôture de la revue adverse (2026-08-26) :
    (1) la FINITUDE, universelle — tout paramètre numérique de toute
    mesure, domaine déclaré ou non (``_refuser_non_finis``) ; (2) les
    BORNES, pour les paramètres du registre. L'étage (1) manquait, et
    l'``if not domains: return params`` ci-dessous en était la cause
    exacte : il rendait la fonction aveugle aux valeurs dès que la mesure
    n'était pas au registre.
    """
    # Notes locales, versées au rapport seulement si la porte aboutit : un
    # levier qui échoue plus bas (valeur non numérique) est consigné par
    # l'orchestrateur comme « en échec », pas comme « clampé ».
    notes = {} if corrections is not None else None
    out = _refuser_non_finis(measure_id, params, strict=strict, warned=warned,
                             corrections=notes)
    domains = PARAM_DOMAINS.get(measure_id)
    clamps = []
    for key, (low, high) in (domains or {}).items():
        if out.get(key) is None:
            continue
        value = out[key]
        # Type qualifié AVANT la comparaison (v0.6.7) : une `str` levait déjà
        # TypeError au comparateur ; elle lève désormais ValeurNonNumerique,
        # sous-classe de TypeError (contrat MIXIN_BAD_PARAMS inchangé), pour
        # que l'appelant sache que la faute est l'ENTRÉE et non le moteur. Un
        # booléen reste comparé comme 0/1, comme avant.
        if not isinstance(value, (int, float)):
            raise ValeurNonNumerique(
                f"{measure_id}.{key}={_apercu(value)} : valeur non numérique "
                f"(domaine [{low}, {high}])"
            )
        # `value != value` n'est vrai que pour NaN — même piège que pour
        # intensite : NaN passe `< low` ET `> high` (les deux False). Ce
        # filet est désormais un SECOND filet : l'étage de finitude a déjà
        # retiré la clé. Il reste, non pour tourner, mais pour qu'une
        # réorganisation qui déplacerait l'étage 1 ne rouvre pas le trou en
        # silence — la seule forme de code mort qui se justifie ici.
        if value != value or value < low or value > high:
            if strict:
                raise ValeurInvalide(
                    f"{measure_id}.{key}={_apercu(value)} hors domaine "
                    f"[{low}, {high}] (mode BUDGETLAB_STRICT)"
                )
            clamped = high if value > high else low  # < low → borne basse
            clamps.append(f"{measure_id}.{key}={_apercu(value)} hors domaine "
                          f"[{low}, {high}] → clampé à {clamped}")
            _noter(notes, measure_id, key,
                   f"{measure_id}.{key}={_apercu(value)} hors du domaine "
                   f"[{low}, {high}] : ramené à {clamped}")
            out = {**out, key: clamped}
    _avertir_agrege(warned, measure_id, 'PARAM_DOMAIN_CLAMP', clamps,
                    "mode tolérant : service préservé, calibration à vérifier")
    if notes:
        for cle, texte in notes.items():
            corrections.setdefault(cle, texte)
    return out


def validate_intensite_domain(measure_id: str, params: Dict, *, strict: bool,
                              warned: set | None = None,
                              corrections: dict | None = None) -> Dict:
    """Valide/borne ``params['intensite']`` selon le domaine du levier.

    No-op (objet ``params`` rendu tel quel, sans copie) si le levier
    n'est pas au registre OU si ``intensite`` est absent/``None`` — ce
    dernier cas préserve la branche legacy de
    ``_resolve_intensite_or_legacy`` (taxe_superprofits/
    exonerations_salaires en mode legacy : pas de clé ``intensite``, ou
    ``intensite=None``). No-op aussi pour toute valeur DANS le domaine
    (bornes incluses) → golden master byte-identique sur les entrées
    légitimes. NaN traité hors domaine (sinon propagation silencieuse).

    Hors domaine : ``ValueError`` en ``strict``, sinon ``logger.warning``
    + copie défensive clampée (l'entrée appelante n'est jamais mutée).
    """
    domain = INTENSITE_DOMAINS.get(measure_id)
    # `params.get('intensite') is None` (et NON `'intensite' not in params`) :
    # aligne le no-op sur la sémantique aval de _resolve_intensite_or_legacy
    # (`params.get('intensite', None) is not None`). {'intensite': None} est
    # une entrée legacy LÉGITIME (slider non posé) — pas une erreur à borner.
    if domain is None or params.get('intensite') is None:
        return params
    low, high = domain
    value = params['intensite']
    # Une str lève TypeError ici (contrat MIXIN_BAD_PARAMS — surtout NE PAS
    # l'avaler) ; v0.6.7 la qualifie en ValeurNonNumerique (sous-classe de
    # TypeError) au lieu de laisser le comparateur lever un TypeError anonyme.
    if not isinstance(value, (int, float)):
        raise ValeurNonNumerique(
            f"{measure_id}.intensite={_apercu(value)} : valeur non numérique "
            f"(domaine [{low}, {high}])"
        )
    # `value != value` n'est vrai que pour NaN : sans ce test un NaN passe
    # `< low` ET `> high` (les deux False) et empoisonne silencieusement
    # TOUTE la trajectoire — exactement la classe d'échec silencieux que
    # ce garde-fou existe pour fermer (pire qu'un clamp tracé). Un entier
    # trop grand pour un float (10**400) se compare sans lever : clampé.
    if value != value or value < low or value > high:
        if strict:
            raise ValeurInvalide(
                f"{measure_id}.intensite={_apercu(value)} hors domaine "
                f"[{low}, {high}] (mode BUDGETLAB_STRICT)"
            )
        clamped = high if value > high else low  # NaN / < low → borne basse
        # Token stable INTENSITE_DOMAIN_CLAMP : rend le clamp filtrable/
        # alertable dans Sentry Logs (enable_logs=True expédie les warning),
        # à l'instar de HANDLER_FAILED_KEY pour les crashs.
        _avertir_une_fois(
            warned, (measure_id, 'INTENSITE_DOMAIN_CLAMP'),
            "INTENSITE_DOMAIN_CLAMP %s.intensite=%s hors domaine [%s, %s] "
            "→ clampé à %s (mode tolérant : service préservé, calibration "
            "à vérifier)",
            measure_id, _apercu(value), low, high, clamped,
        )
        _noter(corrections, measure_id, 'intensite',
               f"{measure_id}.intensite={_apercu(value)} hors du domaine "
               f"[{low}, {high}] : ramené à {clamped}")
        return {**params, 'intensite': clamped}
    return params


def assainir_mesures(mesures: Dict, *, strict: bool, warned: set | None,
                     corrections: dict | None,
                     avis: dict | None = None) -> Dict:
    """Porte d'ENTRÉE, appliquée UNE fois par simulation à tout le dict de
    mesures (v0.6.7), en amont de la porte annuelle d'``apply_measures``.

    Pourquoi une seconde porte : la porte annuelle ne protège que les
    handlers. Les lecteurs LATÉRAUX de ``self.mesures`` (effets d'offre de
    ``growth.py``, chômage seniors, phasing ASU, point d'indice…) lisaient la
    valeur BRUTE : ``education.budget = 10**6`` était clampé pour le handler
    mais ajoutait toujours ~2 pts de croissance potentielle par l'offre. Ici,
    tolérant, chaque bloc passe les deux portes (intensité puis paramètres
    nommés) et ``self.mesures`` devient la version corrigée — que TOUS les
    lecteurs partagent.

    Contrat :
    - entrée valide → objet IDENTIQUE (golden master byte-identique) ;
    - bloc ``null`` ou mal formé → laissé tel quel (la porte annuelle le
      qualifie : levier absent, ou échec bruyant) ;
    - valeur non numérique → bloc laissé tel quel : la porte annuelle lève
      ``ValeurNonNumerique`` et le levier échoue BRUYAMMENT (contrat
      MIXIN_BAD_PARAMS) — jamais un retrait silencieux ;
    - ``strict`` → aucune correction (la porte annuelle lève à la première
      année, ``ExceptionGroup`` inchangé) ; seul le bloc vide est signalé.
    - bloc vide ``{}`` → signalé (WARNING ``PARAM_BLOC_VIDE``, entrée dans
      ``avis``) : il applique le levier à TOUS ses défauts, ce qui est un statu
      quo pour la plupart des leviers mais pas pour ``taxe_superprofits``
      (choix de conception antérieur). Ce n'est pas une CORRECTION (l'entrée
      est lue telle quelle) : ``corrections`` reste vide, ``avis`` le dit.
    """
    propre = None
    for measure_id, bloc in mesures.items():
        if not isinstance(bloc, dict):
            continue
        if not bloc:
            _avertir_une_fois(
                warned, (measure_id, 'PARAM_BLOC_VIDE'),
                "PARAM_BLOC_VIDE %s={} — levier appliqué avec tous ses "
                "défauts (l'appelant devrait omettre le levier ou poser ses "
                "paramètres)", measure_id,
            )
            if avis is not None:
                avis.setdefault(
                    (measure_id, 'PARAM_BLOC_VIDE'),
                    f"{measure_id}={{}} : bloc vide, levier appliqué avec "
                    f"tous ses défauts")
            continue
        if strict:
            continue
        try:
            nouveau = validate_intensite_domain(
                measure_id, bloc, strict=False, warned=warned,
                corrections=corrections)
            nouveau = validate_param_domains(
                measure_id, nouveau, strict=False, warned=warned,
                corrections=corrections)
        except TypeError:
            continue
        if nouveau is not bloc:
            if propre is None:
                propre = dict(mesures)
            propre[measure_id] = nouveau
    return mesures if propre is None else propre
