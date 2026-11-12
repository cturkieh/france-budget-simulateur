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

Porte des NOMS (v0.6.10, contre-audit externe V2-04) : à côté de la porte
des valeurs, ``valider_noms_parametres`` refuse (strict) ou signale avec
invalidation (tolérant) tout nom que le levier ne lit pas, contre le module
GÉNÉRÉ ``_noms_parametres.py`` (même extracteur que le registre public).
Même contrat dual pour un nom ADMIS mais ignoré parce qu'un autre est fourni
(modes exclusifs, ``valider_modes_exclusifs``, réfutation de V2-04).

Porte des LEVIERS INCONNUS et EXCLUSIONS MUTUELLES (release E, chantier W1,
contrat § 5.1 et § 4.1) : dans ``assainir_mesures``, avant tout le reste, un
levier que le moteur ne connaît pas (``LevierInconnu``) et un levier qui
compterait une seconde fois le même euro qu'un autre (``LeviersIncompatibles``,
table ``constants.EXCLUSIONS_MUTUELLES``) : strict, 422 ; tolérant, retirés du
programme avec correction tracée, lisible dans ``report.corrections``.
"""
import logging
import math
import numbers
from typing import Dict

from ..constants import EXCLUSIONS_MUTUELLES, INTENSITE_DOMAINS, NEUTRES_RELEASE_E, PARAM_DOMAINS
from ._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS

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


class ParametreInconnu(EntreeInvalide, ValueError):
    """Nom de paramètre que le levier ne lit pas (faute de frappe, nom d'un
    autre levier) — v0.6.10, contre-audit externe V2-04 (mode
    BUDGETLAB_STRICT). Avant : ignoré en silence, le levier appliquant son
    défaut avec ``report.valid: true``."""


class ParametreIgnore(EntreeInvalide, ValueError):
    """Nom admis mais IGNORÉ parce qu'un autre nom du levier est fourni
    (modes exclusifs : ``intensite`` masque le mode hérité,
    ``taux_remplacement`` masque ``montant``) — v0.6.10, réfutation de V2-04
    (mode BUDGETLAB_STRICT). Avant : ignoré en silence, ``report.valid: true``."""


class LevierInconnu(EntreeInvalide, ValueError):
    """Levier de premier niveau que le moteur ne connaît pas (release E, W1,
    contrat § 5.1 ; mode BUDGETLAB_STRICT). Avant : sauté en silence par
    ``apply_measures`` quand le moteur servait de bibliothèque (l'API, elle,
    le refusait déjà en 422)."""


class LeviersIncompatibles(EntreeInvalide, ValueError):
    """Deux leviers qui feraient varier le même euro (exclusions mutuelles,
    ``constants.EXCLUSIONS_MUTUELLES`` ; release E, W1, contrat § 4.1 ; mode
    BUDGETLAB_STRICT)."""


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


def entree_levier_ecrete(levier: str, demande, applique, borne: list,
                         motif: str) -> dict:
    """Une entrée de ``report.leviers_ecretes`` (v0.7.2), forme commune aux deux
    motifs : ``domaine`` (``_noter_ecretage`` ci-dessous) et ``vivier`` (rabot
    du curseur effectifs, orchestrateur, qui y ajoute ``annee``)."""
    return {'levier': levier, 'demande': demande, 'applique': applique,
            'borne': borne, 'motif': motif}


def _noter_ecretage(ecretages: dict | None, measure_id: str, key: str,
                    demande, applique, low, high) -> None:
    """Consigne un ÉCRÊTAGE de domaine sous forme structurée (v0.7.2), pour le
    champ ``report.leviers_ecretes`` de la réponse : la même correction que
    ``_noter``, lisible par une machine au lieu d'une phrase, ``motif``
    ``domaine``. Dédupliqué par (levier, paramètre), comme ``_noter``. Une
    demande non finie (NaN sur ``intensite``, seul cas qui atteint le clamp)
    est rendue en texte : la réponse JSON refuse NaN et ±inf."""
    if ecretages is None:
        return
    if isinstance(demande, float) and not math.isfinite(demande):
        demande = repr(demande)
    ecretages.setdefault((measure_id, key), entree_levier_ecrete(
        f"{measure_id}.{key}", demande, applique, [low, high], 'domaine'))


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


def _apercu_nom(cle) -> str:
    """Nom de paramètre lisible et borné (une clé JSON est une ``str`` ; un
    appelant Python peut passer autre chose, rendu par ``repr``)."""
    texte = cle if isinstance(cle, str) else repr(cle)
    return texte if len(texte) <= 40 else texte[:37] + '...'


def valider_noms_parametres(measure_id: str, params, *, strict: bool,
                            warned: set | None = None,
                            corrections: dict | None = None) -> None:
    """Porte des NOMS (v0.6.10, contre-audit externe V2-04), à côté de la
    porte des valeurs : tout nom de ``params`` doit être lu par le levier.

    Pourquoi : la porte des valeurs ne regarde que les noms qu'elle connaît.
    ``{"tva_rate": {"tauxx": 0.25}}`` (faute de frappe sur ``taux``) passait
    donc sans trace : le handler lit ``taux``, absent, et applique son défaut
    — HTTP 200, ``report.valid: true``, la hausse demandée jamais appliquée.

    Contrat des noms admis : ``NOMS_PARAMETRES_ADMIS`` (module GÉNÉRÉ depuis
    les lectures réelles des handlers et des formules ASTEVAL, y compris les
    paramètres internes exposés comme ``intensite`` ou ``degressivite`` ;
    jamais ``policy_measures.json``, qui n'est pas le contrat).

    Contrat dual, aligné sur la porte des valeurs :
    - ``strict`` → ``ParametreInconnu`` (``EntreeInvalide`` → 422 par le
      chemin existant), message qui nomme le levier, les noms fautifs et les
      noms admis ;
    - tolérant → WARNING agrégé ``PARAM_NOM_INCONNU`` (au plus
      ``_DETAILS_MAX`` noms détaillés), entrée dans ``corrections`` (donc
      ``report.valid = false`` et un message dans ``report.warnings``). Le
      levier reste appliqué avec ses paramètres connus : le nom inconnu n'est
      lu par personne, la trajectoire est celle de la requête sans lui. (Un
      nom ADMIS mais masqué par un autre relève de
      ``valider_modes_exclusifs``, même contrat.)

    Un nom inconnu est signalé quelle que soit sa valeur, ``null`` compris :
    la faute est dans le nom. Bloc ``{}`` (avis ``PARAM_BLOC_VIDE``) et bloc
    non dict (``null`` = levier absent, mal formé = échec bruyant de la porte
    des valeurs) : inchangés, rien à valider ici.

    Un levier connu ABSENT du module généré est un bug moteur (artefact
    périmé) : ``RuntimeError``, jamais un levier qui laisserait tout passer.
    """
    if not isinstance(params, dict) or not params:
        return
    admis = NOMS_PARAMETRES_ADMIS.get(measure_id)
    if admis is None:
        raise RuntimeError(
            f"levier {measure_id!r} absent de NOMS_PARAMETRES_ADMIS : module "
            f"généré périmé (python scripts/generate_measure_registry.py --noms)")
    inconnus = sorted((_apercu_nom(k) for k in params if k not in admis))
    if not inconnus:
        return
    resume = ', '.join(inconnus[:_DETAILS_MAX])
    if len(inconnus) > _DETAILS_MAX:
        resume += f" (+{len(inconnus) - _DETAILS_MAX} autres)"
    noms_admis = ', '.join(sorted(admis)) or '(aucun)'
    if strict:
        raise ParametreInconnu(
            f"{measure_id} : paramètre(s) inconnu(s) {resume} — noms admis : "
            f"{noms_admis} (mode BUDGETLAB_STRICT)")
    _avertir_agrege(warned, measure_id, 'PARAM_NOM_INCONNU',
                    [f"{measure_id}.{nom}" for nom in inconnus],
                    f"nom(s) inconnu(s), ignoré(s) — levier appliqué avec ses "
                    f"autres paramètres (noms admis : {noms_admis}) ; résultat "
                    f"invalidé")
    _noter(corrections, measure_id, 'PARAM_NOM_INCONNU',
           f"{measure_id} : paramètre(s) inconnu(s) {resume}, ignoré(s) — le "
           f"levier est appliqué avec ses autres paramètres (noms admis : "
           f"{noms_admis})")


def valider_modes_exclusifs(measure_id: str, params, *, strict: bool,
                            warned: set | None = None,
                            corrections: dict | None = None) -> None:
    """Porte des MODES EXCLUSIFS (v0.6.10, réfutation de V2-04) : un nom
    admis que le levier IGNORE parce qu'un autre est fourni.

    Pourquoi : la porte des noms admet ``taux`` pour ``taxe_superprofits``
    (lu par le mode hérité), mais ``_resolve_intensite_or_legacy`` ne lit plus
    le mode hérité dès qu'``intensite`` est fourni ; de même ``chomage_alloc``
    ignore ``montant`` si ``taux_remplacement`` est fourni. ``{"intensite":
    0.5, "taux": 0.05}`` passait donc en 200, ``report.valid: true``, le
    ``taux`` demandé jamais appliqué — le symptôme de V2-04.

    Contrat (``MODES_EXCLUSIFS``, module GÉNÉRÉ depuis l'AST des handlers) :
    à appeler sur le bloc tel que le handler le recevra, APRÈS la porte des
    valeurs (un ``null`` ou un non-fini retiré ne masque rien : le mode qu'il
    aurait choisi n'est pas retenu). Strict → ``ParametreIgnore`` (422) ;
    tolérant → WARNING ``PARAM_IGNORE`` + correction (``report.valid =
    false``), la trajectoire restant celle du mode retenu (la clé dominante).
    """
    if not isinstance(params, dict):
        return
    for dominante, ignorees in MODES_EXCLUSIFS.get(measure_id, {}).items():
        presentes = sorted(k for k in params if k in ignorees)
        if dominante not in params or not presentes:
            continue
        texte = (f"{measure_id} : {', '.join(presentes)} ignoré(s) car "
                 f"« {dominante} » est fourni (modes exclusifs : fournir l'un "
                 f"ou l'autre)")
        if strict:
            raise ParametreIgnore(f"{texte} (mode BUDGETLAB_STRICT)")
        _avertir_une_fois(warned, (measure_id, 'PARAM_IGNORE', dominante),
                          "PARAM_IGNORE %s — résultat invalidé", texte)
        _noter(corrections, measure_id, ('PARAM_IGNORE', dominante), texte)


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
    # v0.6.10 (réfutation de V2-04) : la VALEUR d'un nom que le levier ne lit
    # pas n'est jugée par personne — la porte des NOMS l'a déjà signalé (une
    # correction). Juger ici sa finitude ajoutait une seconde correction
    # contradictoire (« le levier applique son défaut pour ce paramètre » —
    # un paramètre qui n'existe pas). Un `null` reste retiré et journalisé
    # (PARAM_NULL, ligne de log agrégée, aucune correction) comme avant.
    admis = NOMS_PARAMETRES_ADMIS.get(measure_id)
    for key, value in params.items():
        if value is not None and admis is not None and key not in admis:
            continue
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
                           corrections: dict | None = None,
                           ecretages: dict | None = None) -> Dict:
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

    ``ecretages`` (optionnel, v0.7.2) : reçoit chaque valeur ramenée à une
    borne sous forme structurée (``_noter_ecretage``), versée avec les
    corrections et à la même condition.
    """
    # Notes locales, versées au rapport seulement si la porte aboutit : un
    # levier qui échoue plus bas (valeur non numérique) est consigné par
    # l'orchestrateur comme « en échec », pas comme « clampé ».
    notes = {} if corrections is not None else None
    notes_ecretage = {} if ecretages is not None else None
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
            _noter_ecretage(notes_ecretage, measure_id, key, value, clamped,
                            low, high)
            out = {**out, key: clamped}
    _avertir_agrege(warned, measure_id, 'PARAM_DOMAIN_CLAMP', clamps,
                    "mode tolérant : service préservé, calibration à vérifier")
    if notes:
        for cle, texte in notes.items():
            corrections.setdefault(cle, texte)
    if notes_ecretage:
        for cle, ligne in notes_ecretage.items():
            ecretages.setdefault(cle, ligne)
    return out


def validate_intensite_domain(measure_id: str, params: Dict, *, strict: bool,
                              warned: set | None = None,
                              corrections: dict | None = None,
                              ecretages: dict | None = None) -> Dict:
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
        _noter_ecretage(ecretages, measure_id, 'intensite', value, clamped,
                        low, high)
        return {**params, 'intensite': clamped}
    return params


def _resume_noms(noms: list) -> str:
    """Au plus ``_DETAILS_MAX`` noms, puis « (+N autres) »."""
    texte = ', '.join(noms[:_DETAILS_MAX])
    return texte + (f" (+{len(noms) - _DETAILS_MAX} autres)" if len(noms) > _DETAILS_MAX else '')


def _noter_regle(regles: dict | None, regle: str, ignores: list, message: str) -> None:
    """Entrée de ``report.corrections`` (release E, W1) : une par règle
    déclenchée, ``{"regle", "leviers_ignores", "message"}`` ; noms nus, au plus
    ``_DETAILS_MAX``, chacun borné à 40 caractères ; ``message`` est aussi la
    correction publiée dans ``report.warnings``."""
    if regles is not None:
        regles.setdefault(regle, {'regle': regle,
                                  'leviers_ignores': [_apercu_nom(n) for n in ignores[:_DETAILS_MAX]],
                                  'message': message})


def retirer_leviers_inconnus(mesures: Dict, *, strict: bool, warned: set | None,
                             corrections: dict | None,
                             regles: dict | None = None, connus=None) -> Dict:
    """Porte des LEVIERS INCONNUS (release E, W1, contrat § 5.1) : un levier de
    premier niveau absent du REGISTRE du moteur (``connus`` : le
    ``measure_registry`` de la simulation, le même que lit l'API ; à défaut,
    les leviers du contrat des noms ``NOMS_PARAMETRES_ADMIS``) n'est lu par
    aucun handler ni aucune formule. Un levier du registre absent du module
    généré des noms (artefact périmé) n'est PAS inconnu : c'est un défaut du
    moteur, que la porte des noms fait échouer bruyamment.

    Pourquoi : ``apply_measures`` le sautait en silence (``continue``) ; l'API le
    refusait déjà en 422, mais le moteur appelé comme bibliothèque (précalcul,
    scripts, lecteurs qui rejouent des paramètres publiés) rendait le statu quo
    avec ``report.valid: true`` (constat « avant » du cadrage : un
    ``impot_plancher`` mal nommé passait sans trace).

    Strict : ``LevierInconnu``. Tolérant : UN WARNING par simulation, une
    correction (``report.valid = false``, une ligne bornée dans
    ``report.warnings``), une entrée ``LEVIER_INCONNU`` dans
    ``report.corrections`` ; les leviers sont retirés. Un bloc ``null`` d'un
    levier inconnu suit la même règle (la faute est dans le nom). Message
    borné : au plus ``_DETAILS_MAX`` noms, chacun tronqué à 40 caractères, et
    le nombre total. Objet identique si tout est connu."""
    connus = NOMS_PARAMETRES_ADMIS if connus is None else connus
    inconnus = [k for k in mesures if k not in connus]
    if not inconnus:
        return mesures
    noms = sorted(_apercu_nom(k) for k in inconnus)
    if strict:
        raise LevierInconnu(f"{len(noms)} levier(s) inconnu(s) du moteur : {_resume_noms(noms)} "
                            f"(leviers connus : policy_measures.json ; mode BUDGETLAB_STRICT)")
    message = (f"{len(noms)} levier(s) inconnu(s) du moteur, ignoré(s) : {_resume_noms(noms)} "
               f"(leviers connus : policy_measures.json)")
    _avertir_une_fois(warned, ('*', 'LEVIER_INCONNU'), "LEVIER_INCONNU %s — résultat invalidé",
                      message)
    _noter(corrections, '*', 'LEVIER_INCONNU', message)
    _noter_regle(regles, 'LEVIER_INCONNU', noms, message)
    retires = set(inconnus)
    return {k: v for k, v in mesures.items() if k not in retires}


_OPERATEURS_EXCLUSION = {
    '!=': lambda valeur, seuil: valeur != seuil,
    '>': lambda valeur, seuil: valeur > seuil,
    '==': lambda valeur, seuil: valeur == seuil,
}


def condition_d_exclusion_vraie(mesures: Dict, regle: str, spec: Dict, condition: tuple) -> bool:
    """Une condition ``(levier, parametre, operateur, seuil)`` d'une règle de
    ``constants.EXCLUSIONS_MUTUELLES``, sur la valeur DEMANDÉE ; paramètre
    absent ou ``null`` (levier absent compris) = défaut du levier
    (``NEUTRES_RELEASE_E``, ``config.load_default_values``, puis
    ``spec['defauts']``). Une valeur non numérique ou non finie ne satisfait
    aucune condition : la porte des valeurs la qualifie (échec bruyant ou
    retrait tracé). Un paramètre sans défaut connu, ou un opérateur inconnu,
    est un défaut de la TABLE : ``RuntimeError``."""
    levier, parametre, operateur, seuil = condition
    if operateur not in _OPERATEURS_EXCLUSION:
        raise RuntimeError(f"EXCLUSIONS_MUTUELLES[{regle!r}] : opérateur {operateur!r} inconnu")
    bloc = mesures.get(levier)
    valeur = bloc.get(parametre) if isinstance(bloc, dict) else None
    if valeur is None:
        from ..config import load_default_values
        for source in (NEUTRES_RELEASE_E.get(levier, {}), load_default_values().get(levier) or {}):
            if parametre in source:
                valeur = source[parametre]
                break
        else:
            if (levier, parametre) not in spec.get('defauts', {}):
                raise RuntimeError(
                    f"EXCLUSIONS_MUTUELLES[{regle!r}] : aucun défaut connu pour "
                    f"{levier}.{parametre} (ajouter ce défaut à 'defauts')")
            valeur = spec['defauts'][(levier, parametre)]
    if not isinstance(valeur, numbers.Real) or not _est_fini(valeur):
        return False
    return bool(_OPERATEURS_EXCLUSION[operateur](valeur, seuil))


def appliquer_exclusions(mesures: Dict, *, strict: bool, warned: set | None,
                         corrections: dict | None, regles: dict | None = None) -> Dict:
    """Exclusions MUTUELLES (release E, W1, contrat § 4.1) : pour chaque règle
    de ``constants.EXCLUSIONS_MUTUELLES`` (relue à chaque appel) dont toutes
    les conditions sont vraies, le levier ``ignore`` n'est pas appliqué — sans
    quoi le même euro serait compté par deux leviers.

    Strict : ``LeviersIncompatibles`` (422), message qui nomme les deux
    leviers. Tolérant : WARNING une fois, correction tracée (``report.valid =
    false``), entrée lisible dans ``report.corrections`` (règle, levier
    ignoré, message), levier retiré du programme : jamais évalué, absent des
    impacts et, en mode cadre, de ``leviers_modifies``. Objet identique si
    aucune règle ne se déclenche."""
    for regle, spec in EXCLUSIONS_MUTUELLES.items():
        if not all(condition_d_exclusion_vraie(mesures, regle, spec, c) for c in spec['conditions']):
            continue
        ignore, avec = spec['ignore'], spec['avec']
        if strict:
            raise LeviersIncompatibles(f"{regle} : {ignore} et {avec} ne se combinent pas — "
                                       f"{spec['motif']} (mode BUDGETLAB_STRICT)")
        message = (f"{regle} : {ignore} ignoré, il ne se combine pas avec {avec} — "
                   f"{spec['motif']}")
        _avertir_une_fois(warned, ('*', 'EXCLUSION', regle), "EXCLUSION %s — résultat invalidé",
                          message)
        _noter(corrections, '*', ('EXCLUSION', regle), message)
        _noter_regle(regles, regle, [ignore], message)
        mesures = {k: v for k, v in mesures.items() if k != ignore}
    return mesures


def assainir_mesures(mesures: Dict, *, strict: bool, warned: set | None,
                     corrections: dict | None,
                     avis: dict | None = None,
                     ecretages: dict | None = None,
                     regles: dict | None = None, connus=None) -> Dict:
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
    - nom de paramètre inconnu (v0.6.10) → signalé ici sur l'entrée brute
      (``valider_noms_parametres``, tolérant) : la clé n'est lue par personne,
      le bloc n'est pas modifié pour elle.
    - bloc vide ``{}`` → signalé (WARNING ``PARAM_BLOC_VIDE``, entrée dans
      ``avis``) : il applique le levier à TOUS ses défauts, ce qui est un statu
      quo pour la plupart des leviers mais pas pour ``taxe_superprofits``
      (choix de conception antérieur). Ce n'est pas une CORRECTION (l'entrée
      est lue telle quelle) : ``corrections`` reste vide, ``avis`` le dit.
    - levier inconnu (release E) → ``retirer_leviers_inconnus``, AVANT tout le
      reste (strict : ``LevierInconnu``) ;
    - exclusions mutuelles (release E) → ``appliquer_exclusions``, APRÈS les
      portes des valeurs (sur les blocs tels qu'ils seront appliqués ; en
      strict, sur l'entrée brute : ``LeviersIncompatibles``).
    ``regles`` (optionnel) : reçoit les entrées de ``report.corrections`` ;
    ``connus`` (optionnel) : les leviers du registre du moteur.
    """
    mesures = retirer_leviers_inconnus(mesures, strict=strict, warned=warned,
                                       corrections=corrections, regles=regles, connus=connus)
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
        # Porte des NOMS sur l'entrée BRUTE (v0.6.10, V2-04), avant que la
        # porte des valeurs ne retire un `null` ou un non-fini : un nom inconnu
        # est signalé quelle que soit sa valeur, comme en strict (où la porte
        # annuelle voit l'entrée brute). Levier hors contrat des noms (inconnu
        # du registre, ou module généré périmé) : laissé à la porte annuelle,
        # qui l'ignore ou le fait échouer bruyamment dans son `try` par levier.
        if measure_id in NOMS_PARAMETRES_ADMIS:
            valider_noms_parametres(measure_id, bloc, strict=False,
                                    warned=warned, corrections=corrections)
        try:
            nouveau = validate_intensite_domain(
                measure_id, bloc, strict=False, warned=warned,
                corrections=corrections, ecretages=ecretages)
            nouveau = validate_param_domains(
                measure_id, nouveau, strict=False, warned=warned,
                corrections=corrections, ecretages=ecretages)
        except TypeError:
            continue
        if nouveau is not bloc:
            if propre is None:
                propre = dict(mesures)
            propre[measure_id] = nouveau
    return appliquer_exclusions(mesures if propre is None else propre, strict=strict,
                                warned=warned, corrections=corrections, regles=regles)
