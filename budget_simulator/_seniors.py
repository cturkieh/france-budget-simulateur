"""Canal emploi seniors — source unique de l'écart d'âge et des deux profils macro.

Module de package (comme ``_logging``), volontairement neutre vis-à-vis du
découpage ``handlers/`` ↔ ``engine/`` : ses fonctions sont consommées des
DEUX côtés, et c'est tout l'intérêt.

Pourquoi une source unique — le mode de défaillance qu'elle ferme :
une mesure d'âge agit sur QUATRE canaux (moindres dépenses de pension et
fuite sociale côté handler ; offre de travail → PIB et bosse de chômage côté
moteur). Les quatre partent du MÊME écart au droit en vigueur, lequel est
lui-même mobile (la référence légale monte de 62,75 ans en 2026-2027 à
64,0 ans en 2032, cf. ``constants.retraites_ref_age_ans``). Si chaque canal
recalculait son écart, un recalibrage du calendrier légal n'en atteindrait
qu'une partie — et le simulateur chiffrerait une réforme avec deux âges de
référence différents selon le canal.

Même patron que ``handlers/_phasing.asu_phasing`` : les fonctions dérivent
tout de l'ENTRÉE du run (``mesures``) et de l'année, jamais d'un état posé
par un sibling. Aucune dépendance à l'ordre d'exécution : le moteur consomme
le canal AVANT que le handler ait tourné, et les deux voient la même chose.

Sources, valeurs et choix assumés : ``constants.py``, section « CANAL EMPLOI
SENIORS ». Aucun littéral de calibration ici (verrouillé en CI par le
test-propriété P8).

AU-DELÀ DE L'HORIZON PUBLIÉ (10 ans) — convention déclarée : les deux tables
comptent dix millésimes et ``_year_phasing`` borne à la dernière valeur.
L'horizon du simulateur est de dix ans, mais l'API accepte ``periods`` jusqu'à
50 : pour ces appels, l'absorption reste à 0,702 au lieu de monter vers 0,846
à vingt ans, et la résorption du chômage reste à 0,357 au lieu de descendre
vers 0,161. Les deux gels vont dans le MÊME sens — ils sous-estiment le gain
de PIB d'un report d'âge ET surestiment sa bosse de chômage. Le chiffrage
au-delà de dix ans est donc conservateur CONTRE les programmes de report
d'âge, et il faut le dire plutôt que d'extrapoler des points que le COR ne
publie pas.
"""
from typing import Dict

from .constants import (
    CHOMAGE_SENIORS_PIC,
    OFFRE_SENIORS_PIB_NIVEAU_LT,
    PARAM_DOMAINS,
    PHASING_CHOMAGE_SENIORS,
    PHASING_OFFRE_SENIORS,
    POLICY_START_YEAR,
    retraites_ref_age_ans,
)
from .handlers._phasing import _year_phasing

__all__ = [
    'retraites_ecart_age_ans',
    'retraites_ecart_age_ans_moteur',
    'offre_seniors_niveau_pib',
    'chomage_seniors_ecart',
]


def retraites_ecart_age_ans(params: Dict, year: int) -> float:
    """Écart, en années, entre l'âge programmé et le droit en vigueur de ``year``.

    Lecture du HANDLER : ``params`` a déjà traversé la porte unique
    ``validate_param_domains`` (bornage + WARNING/raise tracés), et le
    contrat MIXIN_BAD_PARAMS veut qu'une valeur non numérique lève ici
    (``logger.error`` + ``HANDLER_FAILED_KEY`` en aval) — d'où l'absence de
    garde de type, VOULUE.

    Défaut = la référence de l'année : un curseur absent décrit « je ne
    touche à rien », donc un écart nul, quel que soit le millésime.
    """
    ref_age = retraites_ref_age_ans(year)
    return params.get('age_depart', ref_age) - ref_age


def retraites_ecart_age_ans_moteur(mesures: Dict, year: int) -> float:
    """Même écart, lu depuis ``mesures`` par les canaux MACRO du moteur.

    Deux différences avec la lecture du handler, toutes deux délibérées :

    1. **Défensive sur le type.** Ces canaux sont évalués en AMONT de la
       boucle des mesures : y lever court-circuiterait la porte unique
       ``apply_measures``, qui est le seul endroit où une anomalie de
       paramètre est tracée (``logger.error`` + ``HANDLER_FAILED_KEY``,
       ``ExceptionGroup`` en mode ``BUDGETLAB_STRICT``). On dégrade donc à
       un canal neutre — sans rien avaler : la même anomalie est signalée
       par la porte unique la même année.
    2. **Bornée par le registre ``PARAM_DOMAINS``** — le même que la porte
       unique. Sans ce bornage, une entrée hors domaine (scénario, API :
       aucun clamp navigateur) ferait diverger le canal macro du canal
       budgétaire, qui lui reçoit la valeur bornée. Ce bornage ALIGNE, il ne
       masque pas : le WARNING (ou le raise STRICT) reste émis par la porte.
    """
    age = (mesures.get('retraites') or {}).get('age_depart')
    # `age != age` n'est vrai que pour NaN ; `isinstance(True, int)` est vrai
    # en Python, d'où l'exclusion explicite des booléens.
    if isinstance(age, bool) or not isinstance(age, (int, float)) or age != age:
        return 0.0
    # `.get` et non indexation : quand le levier n'est pas au registre, la
    # porte unique ne borne rien non plus (`validate_param_domains` no-ope).
    # Les deux canaux restent alignés, y compris registre vidé — c'est ce que
    # font les tests de crise qui retirent volontairement le domaine.
    domaine = (PARAM_DOMAINS.get('retraites') or {}).get('age_depart')
    if domaine is not None:
        borne_basse, borne_haute = domaine
        age = min(max(age, borne_basse), borne_haute)
    return age - retraites_ref_age_ans(year)


def offre_seniors_niveau_pib(mesures: Dict, year: int) -> float:
    """Surcroît de NIVEAU de PIB (en fraction) imputable au canal d'offre.

    C'est un NIVEAU, pas un taux : le producteur (``GrowthMixin.
    update_labour_supply``) n'en consomme que l'INCRÉMENT annuel. Le niveau
    se mesure à l'écart d'âge de l'ANNÉE — un programme dont l'avance sur le
    droit en vigueur se réduit voit donc son surcroît de PIB se réduire
    aussi, ce qui est la bonne comptabilité.
    """
    return (OFFRE_SENIORS_PIB_NIVEAU_LT
            * _year_phasing(year - POLICY_START_YEAR, PHASING_OFFRE_SENIORS)
            * retraites_ecart_age_ans_moteur(mesures, year))


def chomage_seniors_ecart(mesures: Dict, year: int) -> float:
    """Écart de NIVEAU du taux de chômage (en fraction) imputable au canal.

    Écart de NIVEAU explicite piloté par la table, et non impulsion : le
    consommateur (``UnemploymentMixin.calculate_unemployment``) retire la
    part de l'année précédente avant la récurrence, sans quoi la convergence
    NAIRU (``u = 0,94·u + 0,06·nairu``) l'accumulerait vers ``1/0,06 ≈ 16,7``
    fois sa valeur.
    """
    return (CHOMAGE_SENIORS_PIC
            * _year_phasing(year - POLICY_START_YEAR, PHASING_CHOMAGE_SENIORS)
            * retraites_ecart_age_ans_moteur(mesures, year))
