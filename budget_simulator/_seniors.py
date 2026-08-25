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

ANCRAGE — UNE SEULE HORLOGE POUR LES QUATRE CANAUX (v0.6.1, clôture de la revue
du lot 3 puis de la revue adverse du 25/08) — les tables sont indexées sur le
DÉBUT DE L'ÉCART du programme simulé, pas sur le début du run. Elles décrivent
la réaction de l'économie à un choc d'âge : leur horloge part quand le choc
part. Cela vaut aussi pour la montée en charge par cohortes
``PHASING_RETRAITES_5ANS`` que lit le canal BUDGÉTAIRE (handler retraites) :
c'est le même facteur que les deux profils macro incluent multiplicativement,
donc la même horloge — ``retraites_annee_debut_ecart_age_handler``. La clôture
du lot 3 n'avait ré-ancré que les profils macro, ce qui faisait entrer les mêmes
générations à 100 % pour les moindres pensions et à 60 % pour l'offre de travail
la même année (≈4,3 Md€ imputés en avance de phase sur 2028-2031 pour un écart
s'ouvrant en 2028). Depuis l'item I3 la référence légale monte de 62,75 ans
(2026-2027) à 64,0 ans (2032), donc un programme qui pose l'âge à 62,75 a un
écart RIGOUREUSEMENT NUL en 2026-2027 et ne diverge du droit en vigueur qu'à
partir de 2028. Indexer sur ``year - POLICY_START_YEAR`` lui appliquait alors
la bosse de chômage en pleine phase de RÉSORPTION et un niveau de PIB déjà
presque formé, soit un artefact mesuré à +4,7 pt de dette 2035 sur le scénario
« Budget 2026 (voté) ».

CONVENTION ASSUMÉE de cet ancrage : l'écart est un NIVEAU, et son ouverture est
datée une fois pour toutes. Un écart qui s'ouvre progressivement (−0,25 an en
2028, puis −0,50…) n'est donc pas traité comme une SUITE de chocs annuels dont
il faudrait convoluer les profils : le simulateur date le choc à sa première
année non nulle et applique une seule montée en charge. Une convolution
demanderait de décomposer un profil publié en réponses impulsionnelles, ce que
le COR ne publie pas.

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
import math
from typing import Callable, Dict

from .constants import (
    CHOMAGE_SENIORS_PIC,
    OFFRE_SENIORS_PIB_NIVEAU_LT,
    PARAM_DOMAINS,
    PHASING_CHOMAGE_SENIORS,
    PHASING_OFFRE_SENIORS,
    POLICY_START_YEAR,
    RETRAITES_REF_AGE_ANS,
    RETRAITES_REF_AGE_CIBLE_ANS,
    RETRAITES_REF_AGE_DERNIERE_ANNEE_GEL,
    RETRAITES_REF_AGE_PAS_ANNUEL_ANS,
    retraites_ref_age_ans,
)
from .handlers._phasing import _year_phasing

__all__ = [
    'retraites_annee_debut_ecart_age',
    'retraites_annee_debut_ecart_age_handler',
    'retraites_ecart_age_ans',
    'retraites_ecart_age_ans_moteur',
    'offre_seniors_niveau_pib',
    'chomage_seniors_ecart',
]

# Première année où la référence légale atteint sa cible et cesse de bouger
# (2032 avec le calendrier en vigueur). DÉRIVÉE des constantes du calendrier,
# jamais saisie : elle borne la recherche de l'année d'ouverture de l'écart.
# Au-delà, ``retraites_ref_age_ans`` est plate, donc l'écart d'un programme à
# âge constant l'est aussi — un écart nul jusque-là est nul pour toujours.
_ANNEE_PLATEAU_REF_AGE = RETRAITES_REF_AGE_DERNIERE_ANNEE_GEL + math.ceil(
    (RETRAITES_REF_AGE_CIBLE_ANS - RETRAITES_REF_AGE_ANS)
    / RETRAITES_REF_AGE_PAS_ANNUEL_ANS
)


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

    RÈGLE D'ALIGNEMENT (v0.6.1, clôture de la revue du lot 3) : la frontière
    entre « dégrader à neutre » et « refléter la valeur » n'est pas le type
    lu ici, c'est le COMPORTEMENT DE LA PORTE UNIQUE.

    - Ce que ``validate_param_domains`` traite sans lever — un booléen, une
      valeur FINIE hors domaine — est CLAMPÉ à une borne du domaine en mode
      tolérant, et le handler chiffre alors ce clamp. Le canal macro doit
      refléter le même clamp. La v0.6.1 initiale dégradait ces cas à un écart
      nul : le canal dépense pricait un abaissement de 2,75 à 4 ans pendant
      que l'offre de travail et le chômage restaient neutres — un programme
      hybride que personne n'a demandé.
    - Ce que la porte RETIRE — NaN et ±inf, depuis le 2026-08-26 — rend le
      handler à son défaut, c'est-à-dire au calendrier légal : écart nul,
      des deux côtés.
    - Ce qui fait LEVER la porte (``str``) ou le handler (``None``, qui
      traverse la porte intact puis échoue à la soustraction) reste dégradé
      à neutre : y lever ici court-circuiterait le seul chemin tracé.
    """
    bloc = mesures.get('retraites')
    # Garde de type sur le BLOC lui-même : un payload non-dict (liste, str,
    # nombre) levait ici une AttributeError en tête de boucle d'année, hors du
    # `try` per-mesure — donc sans `logger.error` ni `HANDLER_FAILED_KEY`.
    # Neutre ici, l'anomalie ressort par la porte unique la même année.
    if not isinstance(bloc, dict):
        return 0.0
    age = bloc.get('age_depart')
    # `None` : la porte le laisse passer intact (`out.get(key) is None` →
    # `continue`) et c'est le handler qui lève à la soustraction. Neutre.
    # `str` et objets : la porte lève au comparateur. Neutre.
    # Les booléens restent DANS ce chemin (`isinstance(True, int)` est vrai en
    # Python) — c'est voulu : la porte les clampe, donc nous aussi.
    if age is None or not isinstance(age, (int, float)):
        return 0.0
    # NaN/±inf : depuis la clôture de la revue adverse (2026-08-26) la porte
    # unique ne les clampe plus à la borne basse — elle RETIRE la clé, donc le
    # handler retombe sur le calendrier légal. Le canal macro suit, c'est tout
    # l'objet de cette fonction. Le motif du changement vaut ici mot pour mot :
    # clamper un NaN à 60 ans, c'était faire chiffrer par le moteur, en
    # silence, le programme d'abaissement le plus lourd de tout le domaine.
    if age != age or age in (float('inf'), float('-inf')):
        return 0.0
    # `.get` et non indexation : quand le levier n'est pas au registre, la
    # porte unique ne borne rien non plus (`validate_param_domains` no-ope).
    # Les deux canaux restent alignés, y compris registre vidé — c'est ce que
    # font les tests de crise qui retirent volontairement le domaine.
    domaine = (PARAM_DOMAINS.get('retraites') or {}).get('age_depart')
    if domaine is None:
        # Registre vidé : plus rien ne borne, ni ici ni à la porte. Un NaN
        # empoisonnerait alors la trajectoire macro SANS qu'aucun garde ne
        # l'ait vu passer — on reste neutre plutôt que de propager.
        return age - retraites_ref_age_ans(year)
    borne_basse, borne_haute = domaine
    # Même arbre de décision que la porte pour les valeurs FINIES : elle
    # applique `clamped = high if value > high else low`. Les non-finies sont
    # déjà sorties plus haut, comme à la porte.
    if age < borne_basse:
        age = borne_basse
    elif age > borne_haute:
        age = borne_haute
    return age - retraites_ref_age_ans(year)


def _premiere_annee_ecart_non_nul(ecart_de_lannee: Callable[[int], float]) -> int:
    """Balayage commun aux deux lectures de l'horloge — cf. les deux fonctions
    publiques ci-dessous. Une seule implémentation, deux lecteurs : c'est la
    raison d'être de ce module (un recalibrage du calendrier légal doit
    atteindre les quatre canaux, jamais deux sur quatre)."""
    for annee in range(POLICY_START_YEAR, _ANNEE_PLATEAU_REF_AGE + 1):
        if ecart_de_lannee(annee) != 0.0:
            return annee
    return POLICY_START_YEAR


def retraites_annee_debut_ecart_age_handler(params: Dict) -> int:
    """Même horloge, lue depuis le bloc `params` que reçoit le HANDLER.

    Ajoutée par la clôture de la revue adverse (25/08) : la montée en charge
    par cohortes `PHASING_RETRAITES_5ANS` est UNE seule montée en charge, lue
    par le canal budgétaire directement et par les canaux macro à travers
    ``PHASING_OFFRE_SENIORS`` / ``PHASING_CHOMAGE_SENIORS``, qui l'incluent
    multiplicativement. Le handler l'indexait sur ``year - POLICY_START_YEAR``
    pendant que les profils macro partaient du début de l'écart : pour un
    programme s'écartant en 2028, les mêmes générations étaient réputées
    entrées à 100 % pour les moindres pensions et à 60 % pour l'offre de
    travail, la même année.

    La lecture handler et la lecture moteur coïncident toujours : `params` a
    traversé la porte unique (donc déjà borné), et c'est exactement le clamp
    que ``retraites_ecart_age_ans_moteur`` reproduit.
    """
    return _premiere_annee_ecart_non_nul(
        lambda annee: retraites_ecart_age_ans(params, annee))


def retraites_annee_debut_ecart_age(mesures: Dict) -> int:
    """Première année civile où l'écart au droit en vigueur devient non nul.

    C'est l'HORLOGE des profils macro (cf. l'ancrage documenté en tête de
    module) : ils décrivent la réaction de l'économie à un choc d'âge, leur
    index doit donc partir quand le choc part, et non quand la simulation
    part. Depuis la clôture de la revue adverse, le canal budgétaire lit la
    MÊME horloge, via ``retraites_annee_debut_ecart_age_handler``.

    Recherche bornée au plateau de la référence légale : au-delà,
    ``retraites_ref_age_ans`` est constante, donc l'écart d'un programme à âge
    constant l'est aussi. Un écart nul sur toute la fenêtre est nul pour
    toujours (le programme ne touche pas à l'âge) — le canal est alors
    identiquement nul et l'ancrage inobservable : on rend le défaut, ce qui
    laisse les scénarios sans curseur d'âge bit-identiques.

    Comparaison EXACTE à zéro, sans tolérance : le calendrier légal et le
    curseur ne portent que des quarts d'année, exactement représentables en
    binaire. Un résidu numérique éventuel avancerait l'ancrage d'une ou deux
    années sur un écart de l'ordre de 1e-16, c'est-à-dire sur un canal déjà
    nul à la précision d'affichage.
    """
    return _premiere_annee_ecart_non_nul(
        lambda annee: retraites_ecart_age_ans_moteur(mesures, annee))


def offre_seniors_niveau_pib(mesures: Dict, year: int) -> float:
    """Surcroît de NIVEAU de PIB (en fraction) imputable au canal d'offre.

    C'est un NIVEAU, pas un taux : le producteur (``GrowthMixin.
    update_labour_supply``) n'en consomme que l'INCRÉMENT annuel. Le niveau
    se mesure à l'écart d'âge de l'ANNÉE — un programme dont l'avance sur le
    droit en vigueur se réduit voit donc son surcroît de PIB se réduire
    aussi, ce qui est la bonne comptabilité.

    Le profil d'absorption, lui, est indexé sur le DÉBUT DE L'ÉCART du
    programme (cf. ``retraites_annee_debut_ecart_age``).
    """
    return (OFFRE_SENIORS_PIB_NIVEAU_LT
            * _year_phasing(year - retraites_annee_debut_ecart_age(mesures),
                            PHASING_OFFRE_SENIORS)
            * retraites_ecart_age_ans_moteur(mesures, year))


def chomage_seniors_ecart(mesures: Dict, year: int) -> float:
    """Écart de NIVEAU du taux de chômage (en fraction) imputable au canal.

    Écart de NIVEAU explicite piloté par la table, et non impulsion : le
    consommateur (``UnemploymentMixin.calculate_unemployment``) retire la
    part de l'année précédente avant la récurrence, sans quoi la convergence
    NAIRU (``u = 0,94·u + 0,06·nairu``) l'accumulerait vers ``1/0,06 ≈ 16,7``
    fois sa valeur.

    Le profil de résorption est indexé sur le DÉBUT DE L'ÉCART du programme
    (cf. ``retraites_annee_debut_ecart_age``) : c'est une table qui MONTE vers
    son pic avant de redescendre, la lire au millésime du run la faisait
    démarrer déjà résorbée pour tout programme s'écartant après 2026.
    """
    return (CHOMAGE_SENIORS_PIC
            * _year_phasing(year - retraites_annee_debut_ecart_age(mesures),
                            PHASING_CHOMAGE_SENIORS)
            * retraites_ecart_age_ans_moteur(mesures, year))
