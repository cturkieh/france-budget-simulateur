"""
Economic constants for BudgetLab France simulator.
All values documented with sources.
"""

from pathlib import Path

# Chemin absolu vers policy_measures.json (à la racine du projet, parent du package)
POLICY_MEASURES_PATH = Path(__file__).resolve().parent.parent / 'policy_measures.json'

# === BASELINE ECONOMIC PARAMETERS (réalisé INSEE 2025, comptes provisoires) ===
# Ancrage sur l'atterrissage RÉALISÉ INSEE 2025 (IR n°78 du 27/03/2026, reconfirmé Comptes de
# la Nation 29/05/2026 ; statut provisoire, révisable 03/2027), et non plus la prévision PLF.
# Déficit et dette étaient déjà conformes ; on corrige les NIVEAUX (ratios honnêtes 57,2/52,1)
# et surtout la charge d'intérêts. Identité année 0 (orchestrator.py:348) : dépenses = depenses_base − intérêts.
PIB_BASE_2025_MD_EUR = 2991  # PIB nominal réalisé 2025 (INSEE)
DETTE_RATIO_2025 = 1.156  # 115.6% du PIB (dette Maastricht ~3460 Md€, inchangé, conforme au réalisé)
RECETTES_BASE_MD_EUR = 1562  # Recettes totales APU réalisées 2025 (INSEE) — ex-1545 (prévision PLF)
DEPENSES_BASE_MD_EUR = 1714  # Dépenses APU réalisées 2025 (INSEE) — ex-1698 (prévision PLF)
CHARGES_INTERET_MD_EUR = 64.7  # Charge d'intérêts APU réalisée 2025 (INSEE, +11,2%) — ex-56 (sous-évalué)

# === UNEMPLOYMENT (INSEE/DARES 2025) ===
CHOMAGE_BASE = 0.076  # 7.6% unemployment rate
CHOMAGE_NAIRU = 0.075  # Natural rate of unemployment

# === INEQUALITY (INSEE 2024) ===
GINI_BASE = 0.29  # Gini coefficient France

# --- Assemblage Gini (v0.4.0 — réalisme empirique) ---
# Les handlers émettent des sensibilités Gini par mesure (METHODOLOGIE.md, § par
# levier). Leur somme brute appliquée en one-time sur-réagit d'un facteur ~4 vs
# les microsimulations (IPP/OFCE 2022 : un programme redistributif de 5-10 % du
# PIB ≈ −0,02 à −0,03 de Gini sur un quinquennat) et produit des niveaux
# impossibles (somme brute LFI 2030 = 0,166 < record mondial, Slovaquie ~0,209,
# Eurostat 2024). Trois étages d'assemblage, appliqués au POINT UNIQUE
# d'agrégation (engine/orchestrator.py, « Calcul Gini centralisé ») :
GINI_IMPACT_SCALE = 0.22  # Rescale de l'agrégat → cible cumulée (calé : LFI 2030 ≈ 0,267, ordres de grandeur IPP/OFCE)
GINI_CONVERGENCE_RATE = 0.35  # Inertie sociale : ~35 %/an vers la cible (série INSEE 25 ans : |ΔGini| ≤ ~0,01/an)
GINI_SOFT_FLOOR = 0.25  # Plancher asymptotique = borne basse du clip (source unique) : l'amortissement tend vers 0 à l'approche → le clip ne mord jamais (filet anti-flottant). <0,25 = Slovaquie/Tchéquie/Slovénie/Belgique seulement (Eurostat 2024)
GINI_HARD_CEILING = 0.40  # Borne haute du clip (source unique, partagée orchestrator + EconomicConstraints)
# Garde de domaine : l'amortissement divise par (GINI_BASE − GINI_SOFT_FLOOR) —
# un recalibrage qui inverse ces bornes casserait la simulation. `raise` et non
# `assert` : python -O strip les asserts, la garde doit survivre en prod.
if not GINI_SOFT_FLOOR < GINI_BASE < GINI_HARD_CEILING:
    raise ValueError("GINI_SOFT_FLOOR < GINI_BASE < GINI_HARD_CEILING requis (dénominateur de l'amortissement)")
if not (0 < GINI_IMPACT_SCALE <= 1 and 0 < GINI_CONVERGENCE_RATE < 1):
    raise ValueError("Constantes d'assemblage Gini hors domaine (SCALE ∈ ]0;1], RATE ∈ ]0;1[)")

# === INFLATION & GROWTH ===
# INFLATION_BASE : graine d'inertie. Valeur initiale de `inflation_precedente`
# (terme AR(1) `inflation_inertia * inflation_precedente` de la courbe de
# Phillips) en année 0.
# Mécanisme (source unique) : INFLATION_BASE → base_params['inflation_base']
# (seedé dans simulator.py) → seed de `inflation_precedente` pour l'année 0.
# Ce même base_params['inflation_base'] est consommé à la fois par simulator.py
# et par orchestrator.py (chemin année 0) : aucun littéral 0.010 dupliqué.
# Ce N'EST PAS l'intercept de Phillips (cf. INFLATION_STRUCTURELLE ci-dessous)
# ni la cible BCE (ancrage de convergence ~2,0 %, dans le rappel BCE inflation.py).
INFLATION_BASE = 0.010  # graine inertie inflation année 0 (init inflation_precedente)
# INFLATION_STRUCTURELLE : inflation TENDANCIELLE de moyen terme France =
# POINT FIXE de la courbe de Phillips augmentée (engine/inflation.py).
# Refonte 2026-06 : la formule applique désormais (1−ρ)·π* + ρ·π_{t-1}, donc
# cette constante EST le point de convergence du régime (1,5 %). L'ancienne
# forme (π* + ρ·π_{t-1}) en faisait un intercept brut → attracteur caché
# c/(1−ρ) = 3,0 %, bridé par le rappel BCE en équilibre permanent à 2,33 % :
# la doc promettait 1,5 % mais l'arithmétique livrait 2,33 (piège intercept
# AR(1) ≠ point fixe, diagnostic 2026-06-10).
# Calibration : 1,5 % = médian sourcé entre la sous-jacente INSEE 2025 (+1,2 %)
# et le cœur Banque de France projeté / cible BCE (1,6-2,0 %). Décision PO
# 2026-05-18, Option C ; intention confirmée par décision PO 2026-06-10
# (BCE = garde-fou de surchauffe >2 %, pas thermostat de convergence).
INFLATION_STRUCTURELLE = 0.015  # 1,5 % — point fixe Phillips, inflation tendancielle moyen terme FR
CROISSANCE_POTENTIELLE = 0.011  # 1,1 % — moyenne du sentier de la mission
                                # Jaravel/Ragot/Tavernier/Valla (07/2026) :
                                # 1,2 / 1,2 / 1,0 / 1,0 % (2027-2030). v0.5.1 : 1,0.
CROISSANCE_2025 = 0.009  # 0.9% INSEE définitif 2025

# === FISCAL PARAMETERS ===
# v0.6.0 (audit externe 08/2026, constat 1) : TAUX_INTERET_BASE ne sert PLUS de
# taux marginal — il n'amorce que le taux moyen du STOCK hérité (~1,9 %, charge
# 2025 ≈ 64,7 Md€ / 3 457 Md€). Le taux marginal des émissions nouvelles est
# reconstruit ci-dessous : ancre zone euro + spread France piloté par la
# simulation (dette, effort). Recalé en calibration sur le corridor de la
# mission Jaravel/Ragot/Tavernier/Valla (IGF, 07/2026) : taux apparent
# 2,2 % → 3,1 % (2026-2030), charge 78 → 124 Md€.
TAUX_INTERET_BASE = 0.0200  # amorce 2026 du taux moyen du stock hérité, périmètre
                            # TOUTES APU — recalée v0.6.0 sur le taux apparent 2026
                            # de la mission Jaravel/Ragot/Tavernier/Valla (2,2 %,
                            # Tableau 6) : blend 84,1 % × 2,00 + 15,9 % × 3,47 %
                            # (repricing linéaire demi-vie 4 ans, cf. engine/debt.py)
                            # ≈ 2,23 %. Distinct du taux moyen 2025 périmètre ÉTAT
                            # (~1,87 % = 64,7 Md€ / 3 457 Md€, Cour des comptes) :
                            # le périmètre APU intègre des dettes plus chères
                            # (Cades, hôpitaux, locales).

# --- Taux marginal v0.6.0 : ancre + spread -------------------------------
# Architecture : toute la littérature estime l'effet de la dette sur le SPREAD,
# jamais sur le taux total. Le moteur ne prévoit pas la politique monétaire :
# l'ancre zone euro est une constante exogène datée (choix de design assumé).
ANCRE_TAUX_ZONE_EURO = 0.0265  # Bund 10 ans 3,24 % − 59 pb de coin de maturité (calage 08/2026)
# Point d'ancrage OBSERVÉ : taux moyen pondéré des émissions MLT France 3,47 %
# au ratio de dette 117,6 % (AFT, août 2026) → spread 82 pb sur l'ancre.
SPREAD_ANCRAGE_DETTE = 1.176
SPREAD_ANCRAGE = 0.0082
# Pentes du spread, en fraction de taux par point de dette/PIB (1 pt = 0.01) :
# 2 pb/pt < 90 % · 3 pb/pt 90-120 % (solide : Laubach 2009, Pamies et al. 2021,
# Baldacci-Kumar 2010, Gruber-Kamin 2010) · 5,5 pb/pt 120-150 % (forme
# non linéaire sourcée, point interpolé) · 8 pb/pt > 150 % (EXTRAPOLATION hors
# échantillon, calée sur épisodes — Portugal 2011 spread 459 pb — jamais une
# estimation ; cf. METHODOLOGIE § design).
SPREAD_PENTE_SOUS_90 = 0.0002
SPREAD_PENTE_90_120 = 0.0003
SPREAD_PENTE_120_150 = 0.00055
SPREAD_PENTE_SUP_150 = 0.0008
# Plafond absolu de stress (borne, pas une prévision) : l'ancien 5 % serait
# franchi dès ~147 % de dette avec ces pentes et écraserait la branche de
# stress. Ancrage épisode : Portugal 2011.
TAUX_PLAFOND_ABSOLU = 0.080

# --- Prime de taux sur l'effort budgétaire ------------------------------
# NB sémantique (revue adverse 24/08) : `effort_budgetaire` est un NIVEAU
# d'effort vs baseline, pas un flux annuel — le cumul partiel avec le
# déplacement le long de la courbe de dette est BORNÉ par les caps ci-dessous
# (choix assumé, documenté METHODOLOGIE § Taux).
# 20 pb par point de PIB d'effort — FMI WEO oct. 2010 ch. 3 ; Furceri,
# Goncalves & Li 2025 (20-30 pb) ; Laubach 2009 (25 pb) ; vécu France
# 2024-2026 : 15-21 pb/pt (OMFIF). Symétrique JUSQU'AUX PLAFONDS (caps
# asymétriques sourcés : bonus −45 pb mission, malus +60 pb), amplifiée par
# la dette au-delà de 90 % (ACL,
# BCE WP 411 : non-linéarité de la dette, la forme est sourcée, la
# paramétrisation est un choix). Falaise +100 pb v0.5.1 SUPPRIMÉE (toute la
# crise politique française 2024-2026 = +21 pb de spread).
PRIME_TAUX_PAR_PT_EFFORT = 0.0020
PRIME_TAUX_SEUIL_DETTE = 0.90
PRIME_TAUX_PENTE_DETTE = 1.00
PRIME_TAUX_CAP_MALUS = 0.0060   # ~2× le pic France 2024-2026 (32 pb, OMFIF)
PRIME_TAUX_CAP_BONUS = 0.0045   # mission 07/2026, encadré 4 : −0,4 pt max,
                                # sans repasser sous le point bas 2021 (~30-35 pb)

# Semi-élasticité du solde public au PIB — constante de CONTRÔLE, pas de calcul.
# Le moteur la produit par CONSTRUCTION (ELASTICITE_PO_PIB = 1,0 + dépenses
# chômage indexées sur le taux de chômage) ; le test-propriété
# tests/test_asymetries_v060.py vérifie qu'elle ressort dans [0,50 ; 0,60].
# Sources : FIPECO/Ecalle (0,55) ; OCDE ECO/WKP(2020)44 (0,5 moyenne, 0,66 max) ;
# CE Mourre, Poissonnier & Lausegger DP 098 (2019). Les « stabilisateurs » en
# escalier ajoutés au TAUX DE CROISSANCE (v0.5.1) étaient une erreur de nature
# et un triple comptage — supprimés en v0.6.0 (audit 08/2026, constat 3).
SEMI_ELASTICITE_SOLDE_PIB_FRANCE = 0.55

# Coût complet chargé d'un agent public (masse salariale FP 330 Md€ / 5,5 M
# d'agents — DGAFP 2024, INSEE 2024). SOURCE UNIQUE v0.6.0 : les deux handlers
# fonction publique (réforme ET effectifs) valorisent un poste au même coût ;
# v0.5.1 utilisait 40 k€ dans l'un et 60 k€ dans l'autre sans périmètre
# documenté (audit 08/2026, constat 4).
COUT_MOYEN_AGENT_FP_EUR = 60000
# Départs naturels annuels dans la fonction publique (retraites) — le vivier
# UNIQUE dans lequel puisent le non-remplacement de la réforme de l'État et le
# curseur effectifs (anti-double-comptage v0.6.0 : l'objectif d'effectifs est
# servi d'abord par les non-remplacements que la réforme réalise déjà).
DEPARTS_ANNUELS_FP = 157000

# Constantes RETIRÉES par la refonte « assemblage temporel » (2026-06,
# cf. docs/plans/refonte-annee1-assemblage.md du repo parent) :
# - AMORCAGE_DEPENSES_Y1 (ex-0.009) : taux exogène de la « bridging year » 2026.
#   Supprimée AVEC le régime spécial année 1 : la récurrence unique chaînée
#   (engine/expenditures.py) applique le tendanciel par catégorie dès Y1 —
#   aucune institution (CBO/OBR/DG Trésor) n'a d'année 1 à mécanique spéciale.
#   NE PAS réintroduire : tout taux Y1 exogène posé sur une formule non chaînée
#   est jeté au passage à Y2 (cause racine n°2 du diagnostic 2026-06-10).
# - EROSION_RECETTES (ex-0.002, « CPO 2023 ») : érosion forfaitaire globale qui
#   rendait l'élasticité PO/PIB de facto 0,933. Remplacée par
#   ELASTICITE_PO_PIB = 1.0 ci-dessous ; une érosion réelle se modélise PAR
#   TAXE (mesure explicite), jamais en taux global.

# === CIBLE D'INFLATION BCE ===
# Seuil ET point d'ancrage du rappel monétaire restrictif (engine/inflation.py) :
# au-dessus de la cible, la BCE freine (blend 50/50 vers la cible). Source :
# cible symétrique 2 % BCE (revue stratégique 2021). Refonte 2026-06 : sert de
# GARDE-FOU de surchauffe (l'ancien seuil 2,3 % en faisait un thermostat).
BCE_CIBLE_INFLATION = 0.020

# === ÉLASTICITÉ DES PRÉLÈVEMENTS OBLIGATOIRES AU PIB NOMINAL ===
# HCFP note 2023-01 (séries 2002-2022) : élasticité observée 1,01-1,07, non
# significativement différente de 1 ; convention CBO/OBR/DG Trésor = 1,0 à
# politique inchangée. Consommée par engine/revenues.py (refonte 2026-06).
ELASTICITE_PO_PIB = 1.0


# Constantes retirées 2026-05-17 (audit pré-open-source) : RETIREMENT,
# HEALTH REFORM POTENTIAL, PHASING COEFFICIENTS, FISCAL MULTIPLIERS —
# 0 consommateur (valeurs ré-hardcodées dans les handlers concernés avec
# leurs propres sources). Drift documentaire supprimé. Si un besoin de
# source unique émerge, recâbler côté handler (chantier dédié, golden
# master à régénérer), ne pas réintroduire une constante orpheline.

# === COEFFICIENTS NICHES SOCIALES TGE ===
# IMPORTANT — Pourquoi ces coefficients sont à 0 :
# Test runtime de calibration (mai 2026) : la cible Bozio-Wasmer 2024 (138k emplois pour
# suppression 60 Md€ ≈ +0.48 pt chômage) est ATTEINTE uniquement par le multiplicateur
# fiscal du moteur (cascade : +recettes → -croissance → +chômage via Okun β=0.35).
# Suppression 60 Md€ → -140 630 emplois Y10 mesuré (vs 138k cible) sans coefficient direct.
# Avec coefficient direct 0.008/Md€, l'effet était amplifié ×9 à 95× (double-comptage).
# Conclusion : aucun signal direct nécessaire. Constantes conservées à 0 pour traçabilité
# de la décision et possibilité de réactiver si la modélisation du multiplicateur évolue.
COEFF_CHOMAGE_NICHES_SOCIALES_TGE = 0.0
COEFF_PA_NICHES_SOCIALES_TGE = 0.0

# === COEFFICIENTS COMPÉTITIVITÉ TGE (DG Trésor 2019, OCDE 2024) ===
# Impact one-time sur indice compétitivité par Md€ supprimé.
COEFF_COMPETITIVITE_NICHES_FISCALES_TGE = 0.015
COEFF_COMPETITIVITE_NICHES_SOCIALES_TGE = 0.020  # Symétrique inverse cotisations patronales
COEFF_COMPETITIVITE_SUBVENTIONS_TGE = 0.008

# === ELASTICITE REVENU IMPOSABLE — Saez-Diamond 2011 ===
# ETI sur tranche supérieure IR (Lehmann-Sicsic IPP 2020 : 0.20-0.30, médian 0.25).
ETI_TRANCHE_SUPERIEURE = 0.25

# === ANNÉE DE DÉPART DES POLITIQUES SIMULÉES ===
# Première année d'application des mesures (Y1). Hardcodée auparavant en
# `year_start = 2026` dans chaque handler — centralisée ici pour qu'un
# changement d'horizon (ex. campagne active 2027) ne soit pas un grep-replace.
POLICY_START_YEAR = 2026

# === FLAGS INTERNES (sentinelles dans dict d'impact) ===
# Marque les mesures dont le handler a raise — détecté par golden master / tests stricts
# pour éviter qu'une régression silencieuse ne passe quand la mesure était à default.
HANDLER_FAILED_KEY = '_handler_failed'

# === DOMAINES LÉGITIMES DES PARAMÈTRES D'INTENSITÉ (Lot C Item 1) ===
# Garde-fou scénario/API : le slider frontend borne déjà l'utilisateur ;
# ce registre protège les entrées HORS-UI (scénarios, API, config) qui
# n'ont AUCUN clamp backend. Domaines vérifiés sur le code handler
# (1 explorateur + 3 agents adverses, 2026-05-17 — cf.
# docs/MINI_DESIGN_ITEM1_BORNE_INTENSITE.md §2).
#   fiscalite_patrimoine : delta = 53 Md€ × intensite ; docstring
#     "-0.3 = baisse 30%, 0 = statu quo, +0.3 = hausse 30%"
#     (handlers/fiscalite_menages.py::_apply_fiscalite_patrimoine,
#      clamp historique de défense en profondeur conservé dans la fonction).
#   optimisation_dette / isf_climatique / taxe_superprofits /
#     exonerations_salaires : intensité fractionnaire [0,1]
#     (0 = inactif, 1 = plein effet ; aucun clamp backend).
# fraude_fiscale / fraude_sociale EXCLUS : `effort` bimodal
# (∈[0,1] = intensité, >1 = montant Md€ legacy) non bornable sans
# clarifier la sémantique → chantier Item 2 (contrat de params).
INTENSITE_DOMAINS = {
    'optimisation_dette': (0.0, 1.0),
    'isf_climatique': (0.0, 1.0),
    'taxe_superprofits': (0.0, 1.0),
    'exonerations_salaires': (0.0, 1.0),
    'fiscalite_patrimoine': (-0.3, 0.3),
}

# === DOMAINES LÉGITIMES DES PARAMÈTRES NOMMÉS (revue 2026-08-04) ===
# Même philosophie qu'INTENSITE_DOMAINS, clé (measure_id, param) : couvre les
# handlers SYMÉTRISÉS (retraites, prestations), où l'arithmétique uniforme a
# remplacé les if/elif directionnels qui neutralisaient un NaN par accident
# (comparaisons False → terme sauté). Sans ce registre, un NaN hors-UI
# empoisonne toute la trajectoire sans un signal, et une valeur aberrante
# (indexation=-10) déplace la dette de 21 pts en silence. Domaines = union
# des bornes UI (leverMeta.js) et des scénarios publiés. Extension complète
# aux autres params nommés = chantier « contrat de params » (Item 2), différé.
PARAM_DOMAINS = {
    'retraites': {
        'age_depart': (60.0, 67.0),
        'indexation': (0.0, 1.2),
        'duree_cotisation': (40.0, 45.0),
    },
    'prestations_indexation': {
        'taux_indexation': (0.0, 1.2),
    },
}

# === CALIBRATION RETRAITES (COR 2024, METHODOLOGIE.md § Retraites) ===
# Coefficients budgétaires du handler retraites (handlers/depenses.py), nommés
# pour la garde CODE→DOC de tests/test_methodologie_consistency.py — la dérive
# ×2 constatée le 2026-08-04 (code 16/4 vs doc et tooltips 8/2) est le mode de
# défaillance que ce verrou bloque désormais.
# --- Référence d'âge = CALENDRIER LÉGAL, pas une valeur figée (v0.6.1, I3) ---
# La LFSS 2026 suspend l'âge d'ouverture des droits (AOD) à 62 ans et 9 mois à
# compter du 1er septembre 2026 et JUSQU'AU 1er JANVIER 2028 SEULEMENT ; la
# montée en charge de la réforme 2023 (+3 mois par génération) reprend ensuite
# jusqu'à 64 ans. Sources : service-public.gouv.fr, « Suspension de la réforme
# des retraites : qui est concerné » ; OFCE, billet du 29/01/2026,
# https://www.ofce.sciences-po.fr/blog2024/fr/2026/20260129_MD/
#
# Pourquoi une FONCTION et pas une constante : la baseline du moteur est calée
# sur le tendanciel de la mission IGF de juillet 2026, dont les hypothèses
# retraites intègrent explicitement « suspension de la réforme des retraites
# jusqu'en 2028 » — la reprise vers 64 ans est DANS la baseline. Avec une
# référence figée à 62,75, un programme qui dit « je maintiens 64 ans » était
# crédité d'une économie que la loi produit déjà (double comptage pur), et un
# programme à 60 ans était chiffré sur 2,75 années alors que l'écart au droit
# en vigueur à horizon 2032 est de 4,0 années.
RETRAITES_REF_AGE_ANS = 62.75            # AOD gelé 2026-2027 : 62 ans 9 mois (LFSS 2026)
RETRAITES_REF_AGE_CIBLE_ANS = 64.0       # cible de la réforme 2023, atteinte en 2032
RETRAITES_REF_AGE_DERNIERE_ANNEE_GEL = 2027  # suspension jusqu'au 01/01/2028
RETRAITES_REF_AGE_PAS_ANNUEL_ANS = 0.25  # +3 mois par génération (réforme 2023)
RETRAITES_REF_DUREE_ANS = 42.5           # référence 2025 : 170 trimestres


def retraites_ref_age_ans(year: int) -> float:
    """Âge légal d'ouverture des droits applicable l'année civile ``year``.

    62,75 ans jusqu'en 2027 (gel LFSS 2026), puis +0,25 an par an jusqu'à
    64,0 ans en 2032, plafonné ensuite. Bornée des deux côtés : aucun
    millésime hors de l'horizon publié ne peut faire dériver la référence.
    """
    if year <= RETRAITES_REF_AGE_DERNIERE_ANNEE_GEL:
        return RETRAITES_REF_AGE_ANS
    montee = RETRAITES_REF_AGE_PAS_ANNUEL_ANS * (year - RETRAITES_REF_AGE_DERNIERE_ANNEE_GEL)
    return min(RETRAITES_REF_AGE_CIBLE_ANS, RETRAITES_REF_AGE_ANS + montee)


# --- Barème d'âge v0.6.1 : PLAT et SYMÉTRIQUE, 6,0 Md€ par année d'âge ---
# Remplace le barème à 2 segments de la v0.6.0 (14,2 avant 64 ans / 6,0 au-delà).
# Le 14,2 venait d'une COLLISION NUMÉRIQUE entre deux « 17,7 Md€ » sans rapport
# (cf. METHODOLOGIE.md § Retraites, table de passage) : celui du Sénat mêlait
# l'âge ET l'accélération Touraine, sur le seul système de retraites, en euros
# courants 2030 et en montée en charge partielle. Rapporté à une année d'âge,
# il surestimait le rendement d'un facteur ≈ 2,4.
#
# Les deux sources primaires qui chiffrent réellement UNE année d'âge sur les
# moindres dépenses convergent au dixième :
#  - DG Trésor, « Effets d'une mesure d'âge sur le solde des APU », document
#    n° 12 de la séance plénière du COR du 27/01/2022, diapositive 5 : −0,4 pt
#    de PIB pour un report de 2 ans, soit 0,20 pt/an × 2 991 Md€ = 5,98 Md€.
#    https://www.cor-retraites.fr/sites/default/files/2022-01/Doc12_Mesure%20d%27%C3%A2ge_DG%20Tr%C3%A9sor_V2.pdf
#  - Cour des comptes, « Situation financière et perspectives du système de
#    retraites », février 2025, tableau n° 6, p. 72 (variante symétrique
#    générations 1964-1968, exercice 2035, Md€ constants 2024) : +6,0 Md€ de
#    moindres dépenses par année d'âge (4,3 base + 1,7 complémentaires).
#    https://www.ccomptes.fr/sites/default/files/2025-03/20250220-Situation-financiere-et-perspectives-du-systeme-de%20retraites.pdf
# Base de conversion validée par le COR lui-même (Dossier en bref du
# 26/03/2026 : « 0,2 point de PIB ex ante (6 milliards d'euros) »).
#
# PLAT sur tout le domaine [60 ; 67] et SYMÉTRIQUE dans les deux sens
# (arbitrage du propriétaire, 25/08/2026). Deux choix à assumer, déclarés dans
# METHODOLOGIE.md § Retraites :
#  1. AU-DELÀ DE 65 ANS, aucune source consultée ne chiffre 65→66 ni 66→67
#     alors que le domaine UI monte à 67 : prolonger le palier est une
#     convention, pas une estimation. Le rendement décroissant est réel mais
#     DOUX (0,285 → 0,25 → 0,20-0,25 pt sur le solde système), jamais en falaise.
#  2. SYMÉTRIE STRICTE : le facteur d'asymétrie publié (0,70 à la baisse) est
#     mesuré sur le seul palier 64→63 et découle d'une hypothèse explicite sur
#     les carrières longues ; rien ne le valide de 62 vers 60. L'appliquer
#     allégerait mécaniquement le coût affiché des programmes d'abaissement de
#     l'âge, donc prendrait parti. Bande de sensibilité publiée : une baisse
#     d'une année d'âge coûte de 4,2 à 6,0 Md€/an.
#
# PÉRIMÈTRE : moindres dépenses de pension UNIQUEMENT. Le canal cotisations
# (Cour T6 : +2,4 Md€/an ; DG Trésor : +1,5) n'a PAS de slot dans ce handler —
# il naît du canal PIB/emploi (lot « emploi seniors » du chantier v0.6.1), ce
# qui rend le double comptage structurellement impossible.
RETRAITES_COEFF_AGE_MD_EUR = 6.0

RETRAITES_COEFF_DUREE_MD_EUR = 4.0       # Md€/an par année de cotisation (2 Md€/semestre, plein régime)
RETRAITES_EROSION_INDEXATION_MD_EUR = 1.5  # Md€/an par année écoulée pour un gel total (proportionnel à l'écart)
RETRAITES_EROSION_PLATEAU_ANS = 7        # renouvellement des cohortes : l'écart au statu quo cesse de croître

# === PROFILS DE PHASING (montée en charge progressive) ===
# Format : tableau indexé par year_idx (0=Y1=2026, 1=Y2=2027, ...), borné à la dernière valeur.
# Retraites — COR 2024 : montée en charge cohortes 5 ans (linéaire 0.2 → 1.0).
PHASING_RETRAITES_5ANS = (0.20, 0.40, 0.60, 0.80, 1.00, 1.00)
# Niches fiscales TGE — Cour des comptes 2024 : débouclage 30-50% Y1, 70% Y2, 100% Y3+.
PHASING_NICHES_FISCALES_TGE = (0.40, 0.70, 1.00, 1.00, 1.00, 1.00)

# === CANAL EMPLOI SENIORS (v0.6.1 — I7 à I10) ===
# Une mesure d'âge n'agit pas seulement sur les pensions versées : elle
# augmente l'offre de travail, donc le PIB potentiel, donc les recettes.
# Les trois briques ci-dessous forment une IDENTITÉ COMPTABLE et ne se
# livrent pas séparément (COR, séance plénière du 26 mars 2026, Document
# n° 3 « Effets macroéconomiques d'une mesure d'âge », encadré 2) :
#   A. moindres dépenses de pension       → handler retraites
#      (RETRAITES_COEFF_AGE_MD_EUR ci-dessus)
#   D. surcroît d'offre de travail → PIB  → OFFRE_SENIORS_* ci-dessous
#   E. bosse de chômage transitoire       → CHOMAGE_SENIORS_* ci-dessous
#   F. fuite sociale résiduelle           → FUITE_SOCIALE_RESIDUELLE
# Les cotisations retraite (ligne B de la Cour) et les autres recettes
# publiques (ligne C) n'ont AUCUN slot : elles naissent entièrement du
# canal PIB, ce qui rend le double comptage structurellement impossible
# (arbitrage du propriétaire, 25/08/2026). Voir RETRAITES_PART_COTISATIONS_PO.
#
# Source commune du volet macro : COR, séance plénière du 26 mars 2026,
# « Impact macroéconomique des leviers d'équilibre financier d'un système de
# retraite », Documents n° 2 (SG-COR, tableau 4), n° 3 (DG Trésor), n° 4
# (I-MIP/CepreHANK), n° 5 (OFCE/EmeRaude) et Dossier en bref.
# https://www.cor-retraites.fr/reunions-du-cor/impact-macroeconomique-leviers-dequilibre-financier-dun-systeme-retraite

# --- D. Offre de travail → NIVEAU de PIB (I7) ---------------------------
# +0,80 pt de NIVEAU de PIB par année d'AOD à long terme : milieu du
# consensus des trois équipes du COR, publié tel quel par le Conseil
# (Dossier en bref du 26/03/2026 : « 0,7 à 0,9 point de PIB », « 210 000 à
# 240 000 emplois »). Modèles individuels à long terme (Doc n° 2, T4) :
# I-MIP 0,93 / OFCE 0,78 / DG Trésor 0,7 à 20 ans.
#
# ATTENTION — c'est un effet de NIVEAU, pas de TAUX. Le moteur ne consomme
# que l'INCRÉMENT annuel de ce niveau (engine/growth.py,
# update_labour_supply) : l'incrément maximal vaut +0,12 pt de croissance,
# une seule année. La v0.6.0 ajoutait « +0,8 pt » au taux de croissance
# CHAQUE année, ce qui composait à ~+8 % de PIB en dix ans — quatorze fois
# l'effet publié. C'était l'une des deux raisons du retrait de ce canal.
OFFRE_SENIORS_PIB_NIVEAU_LT = 0.0080

# Profil d'ABSORPTION macroéconomique — moyenne des trois modèles du COR
# (Doc n° 2, T4 : 0,107 / 0,297 / 0,433 / 0,600 / 0,723 / 0,855 % de PIB aux
# horizons 1 / 2 / 5 / 10 / 20 ans / LT), normalisée sur sa valeur de long
# terme (0,855) : 0,125 / 0,347 / 0,507 / 0,702 / 0,846 / 1,000.
# CHOIX À ASSUMER : les horizons 3, 4 et 6 à 9 ans ne sont pas publiés —
# interpolation log-linéaire entre les points publiés (0,393 et 0,446 pour
# Y3-Y4 ; 0,541 / 0,578 / 0,617 / 0,658 pour Y6-Y9).
# Non consommée par le moteur : elle existe pour que le profil ci-dessous
# reste AUDITABLE (un test-propriété vérifie qu'il en est bien le produit par
# la montée en charge cohortes) et pour servir de variante de sensibilité.
ABSORPTION_OFFRE_SENIORS = (0.125, 0.347, 0.393, 0.446, 0.507,
                            0.541, 0.578, 0.617, 0.658, 0.702)

# Table effectivement consommée = absorption × montée en charge par cohortes
# (PHASING_RETRAITES_5ANS). CHOIX À ASSUMER : les deux profils décrivent des
# phénomènes distincts — l'absorption du choc par l'économie d'un côté, le
# rythme d'entrée des générations concernées de l'autre ; le calibrage COR
# est explicitement SANS progressivité (Dossier en bref : « Il n'intègre
# aucun délai de progressivité »), quand le volet budgétaire du moteur
# applique déjà une montée en charge sur 5 ans. Le raisonnement est solide,
# le PRODUIT n'est mesuré par personne : sa sensibilité est testée
# (tests/test_emploi_seniors_v061.py, P3 tourne avec ET sans).
PHASING_OFFRE_SENIORS = (0.025, 0.139, 0.236, 0.357, 0.507,
                         0.541, 0.578, 0.617, 0.658, 0.702)

# --- E. Bosse de chômage transitoire (I8) --------------------------------
# +0,18 pt de taux de chômage par année d'AOD, AU PIC.
#
# DÉRIVATION MAISON, à ne JAMAIS présenter comme une estimation officielle :
# la valeur ex ante est irréductiblement NON TRANCHÉE entre les équipes du
# COR (Doc n° 2, T4, à 1 an : DG Trésor 0,00 / I-MIP −0,40 / OFCE +0,55).
# Trois routes indépendantes, convergentes à ±0,04 pt, donnent 0,13 / 0,19 /
# 0,21 (moyenne 0,18) ; elles partent de la part « chômage » du devenir des
# séniors décalés, stable à 26-27 % sur deux méthodologies et deux sources
# de données indépendantes :
#  - Dubois Y. & Koubi M., « Relèvement de l'âge de départ à la retraite :
#    quel impact sur l'activité des séniors de la réforme des retraites de
#    2010 ? », Insee, document de travail G2016/08 (2016) et Insee Analyses
#    n° 30 (05/01/2017) — 26 % (hommes) / 27 % (femmes) ;
#    https://www.insee.fr/fr/statistiques/fichier/2121629/G2016-08.pdf
#  - Rabaté S. & Rochut J., « Employment and substitution effects of raising
#    the statutory retirement age in France », Journal of Pension Economics
#    and Finance 19(3), 2020, p. 293-308 — 27 % ;
#    https://shs.hal.science/halshs-01622346/document
#  - base démographique : population active 31 802 milliers, chômage 7,3 %
#    (COR 26/03/2026, Doc n° 4, note 7).
# Position dans le débat : entre DG Trésor 0,0 et OFCE +0,55, très loin de
# Mésange +0,7 / e-mod.fr +0,5, que la Cour des comptes désavoue
# explicitement (février 2025, p. 67, note 121 : « les recherches
# micro-économétriques menées sur la réforme de 2010 ont montré que
# l'évolution du chômage observée ne correspondait pas à celle prédite par
# les modèles »).
CHOMAGE_SENIORS_PIC = 0.0018

# Profil de RÉSORPTION — seule série publiée présentant une résorption
# complète : OFCE/EmeRaude (COR 26/03/2026, Doc n° 2, T4 : 0,55 / 0,56 /
# 0,31 / 0,20 / 0,09 / 0,00 pt aux horizons 1 / 2 / 5 / 10 / 20 ans / LT),
# rebasée sur son maximum (0,56 à 2 ans). CHOIX À ASSUMER : Y3-Y4 et Y6-Y9
# sont des interpolations log-linéaires entre points publiés.
# Non consommée par le moteur, même rôle d'auditabilité que
# ABSORPTION_OFFRE_SENIORS ci-dessus.
# Mécanisme sourcé de la résorption (COR Doc n° 6, partie 3) : l'offre de
# travail accrue ralentit les salaires et le revenu global de l'économie
# augmente — les deux canaux relèvent la demande de travail.
RESORPTION_CHOMAGE_SENIORS = (0.98, 1.00, 0.82, 0.67, 0.554,
                              0.507, 0.465, 0.426, 0.390, 0.357)

# Table effectivement consommée = résorption × montée en charge par cohortes
# (même choix assumé que pour l'offre). Écart de chômage résultant, par
# année d'AOD : 0,035 / 0,072 / 0,089 / 0,097 / 0,100 / 0,091 / 0,084 /
# 0,077 / 0,070 / 0,064 pt — pic +0,10 pt en Y4-Y5.
PHASING_CHOMAGE_SENIORS = (0.196, 0.400, 0.492, 0.536, 0.554,
                           0.507, 0.465, 0.426, 0.390, 0.357)

# --- F. Fuite sociale résiduelle (I9) ------------------------------------
# +9,6 % de la moindre dépense brute de pension, et NON 20 %.
# Cour des comptes, février 2025, p. 67-68, citant DREES note BRET n° 21-43,
# janvier 2022 et DARES note SD-EMT–DSIDE, janvier 2022 (les deux notes
# primaires N'ONT PAS été consultées directement — à citer via la Cour,
# p. 67, note 125, jamais en première main) : « l'augmentation des
# prestations sociales et d'assurance chômage serait de l'ordre de 20 % des
# économies brutes attendues pour le système de retraites. 52 % de cette
# augmentation serait liée aux prestations d'assurance chômage, 36 % aux
# indemnités journalières et 12 % aux minima sociaux. »
# On ne retient donc que 48 % × 20 % = 9,6 % (IJ + minima) : la part
# assurance-chômage (52 %) est DÉJÀ produite endogènement par la catégorie
# de dépense `chomage` du moteur, indexée sur le taux de chômage — que la
# brique E ci-dessus fait précisément bouger. L'inscrire aussi dans le
# handler serait un double comptage.
# Vérification croisée : au pic, +0,10 pt appliqué à la catégorie `chomage`
# (base 40 Md€, facteur u/u_base avec u_base = 7,6 %) donne 0,53 Md€, contre
# 52 % × 20 % × 6,0 = 0,62 Md€ dans la clé DREES/DARES — écart 14 %.
# Corroboration indépendante : Rabaté & Rochut 2020, « crowding out effects
# […] around one fifth of the fiscal gains ».
FUITE_SOCIALE_RESIDUELLE = 0.096

# --- Contrôle du double comptage des cotisations (I10) -------------------
# Constante de CONTRÔLE, pas de calcul : aucun code ne la consomme, seul un
# test-propriété s'en sert. Cour des comptes, février 2025, tableau n° 6,
# p. 72 (décalage d'un an de l'AOD, variante symétrique générations
# 1964-1968, exercice 2035, Md€ constants 2024) : dépenses de retraites
# +6,0 / cotisations retraites +2,4 / autres recettes publiques +9,3 /
# ensemble des APU +17,7. La part des prélèvements additionnels qui relève
# des cotisations retraite vaut donc 2,4 / (2,4 + 9,3) = 20,5 %.
# C'est la grandeur que la DG Trésor DÉDUIT avant d'appliquer son taux de
# 53 % au surcroît de PIB (COR 26/03/2026, Doc n° 3, encadré 2, note 6 :
# « les cotisations retraites sont déduites du surcroît de recettes
# publiques, étant déjà comptabilisées dans le solde du système de
# retraites »). Le moteur, lui, applique ELASTICITE_PO_PIB = 1,0 au PIB : il
# produit donc les DEUX lignes d'un coup — ce qui n'est correct QUE parce
# que le handler retraites n'a aucun slot cotisations.
# Contre-épreuve T5 p. 68 (réforme 2023 entière) : 5,5 / (5,5 + 10,9) =
# 33,5 % ; l'écart s'explique par l'objet (T5 mêle 2 ans d'AOD ET
# l'accélération de la durée d'assurance). Fourchette de contrôle 20-33 %.
RETRAITES_PART_COTISATIONS_PO = 0.205

# === CALIBRATION PRÉVENTION SANTÉ (v0.6.1, I19-I20) ===
# Curseur `sante.prevention_budget` (handlers/depenses.py, « MESURE 2 :
# PRÉVENTION ») : budget ABSOLU de prévention institutionnelle, dont le
# handler ne consomme que l'écart à la base.
#
# --- I19 : l'assiette et l'amplitude du curseur ---------------------------
# Deux sources indépendantes, MÊME nomenclature (System of Health Accounts) :
# - DREES, « Les dépenses de santé en 2023 — Résultats des comptes de la
#   santé », Panoramas édition 2024, FICHE 21, TABLEAU 1 (et série longue) :
#   prévention institutionnelle 7 516 M€ en 2023 ; édition 2025 (30/09/2025) :
#   +0,9 % en 2024, soit ≈ 7,6 Md€, sur une dépense courante de santé au sens
#   international (DCSi) de 333 Md€.
#   https://drees.solidarites-sante.gouv.fr/sites/default/files/2025-02/Les%20d%C3%A9penses%20de%20sant%C3%A9%20en%202023_MEL2ok.pdf
# - OCDE, « Health at a Glance 2025 — Country note : France », novembre 2025 :
#   « France spends 2.3 % of total health spending on prevention […] less than
#   the OECD average of 3.4 % ».
#   https://www.oecd.org/en/publications/2025/11/health-at-a-glance-2025-country-notes_2f94481e/france_fc92ff53.html
#   ⇒ 2,3 % × 333 = 7,66 Md€ : les deux chemins coïncident à 1 % près.
#
# DEUX PIÈGES DE LECTURE, tous deux documentés dans METHODOLOGIE.md :
# (a) la bosse 2020-2022 (9 272 → 16 515 → 12 175 M€) est du COVID (tests,
#     vaccins, masques) et ne doit JAMAIS servir de base — l'OCDE note le
#     retour « to historical levels of 3 % in 2023 » ;
# (b) le périmètre SHA EXCLUT la prévention en consultation ordinaire, les
#     dépistages hors dépistage organisé, une grande partie de la vaccination
#     et la prise en charge des facteurs de risque (toutes en CSBM). En
#     périmètre large la Cour des comptes chiffre l'effort français à
#     ≈ 15 Md€/an : le curseur pilote l'agrégat SHA, PAS les 15.
DEPENSE_COURANTE_SANTE_MD_EUR = 333.0  # DCSi 2024 (DREES, comptes de la santé éd. 2025)
PREVENTION_PART_FRANCE = 0.023         # OCDE, Health at a Glance 2025, country note France
PREVENTION_PART_OCDE = 0.034           # idem, moyenne OCDE
PREVENTION_BASE_MD_EUR = 7.5           # DREES fiche 21 T1 (7 516 M€ en 2023) ≈ 2,3 % × DCSi
# Borne haute du curseur = convergence vers la moyenne OCDE. DÉRIVÉE, pas
# saisie : l'amplitude (0 → +3,7 Md€/an) est ainsi sourcée, alors que
# l'amplitude de la v0.5.1 (0 → +3,0) l'était par accident.
PREVENTION_PLAFOND_MD_EUR = round(
    PREVENTION_BASE_MD_EUR
    + (PREVENTION_PART_OCDE - PREVENTION_PART_FRANCE) * DEPENSE_COURANTE_SANTE_MD_EUR,
    1,
)  # = 11,2 Md€
#
# --- I20 : le taux de compensation (le dernier « repas gratuit ») ---------
# La v0.5.1 écrivait `roi_cumul = min(annees_roi * 0.25, 2.0)`, et son
# commentaire assumait le résultat : à partir de 2034, la mesure ne coûtait
# plus rien. Sémantique réelle : à 1,00 l'euro dépensé est intégralement
# gagé ; à 2,00 la mesure RAPPORTE autant qu'elle coûte, chaque année, pour
# toujours (+10 Md€/an de prévention réduisaient la dette 2035 d'environ
# 42 Md€). Trois sources primaires l'interdisent :
# - Cohen J.T., Neumann P.J., Weinstein M.C., « Does Preventive Care Save
#   Money? Health Economics and the Presidential Candidates », New England
#   Journal of Medicine 358(7):661-663, 14/02/2008, DOI 10.1056/NEJMp0708558
#   — 19 % seulement des interventions préventives sont cost-saving (599
#   études, ~1 500 ratios dont 279 préventifs), contre 18 % des traitements
#   curatifs : l'espérance du retour est très inférieure à 1.
#   https://www.nejm.org/doi/full/10.1056/NEJMp0708558
# - van Baal P.H.M. et al., « Lifetime Medical Costs of Obesity : Prevention
#   No Cure for Increasing Health Expenditure », PLoS Medicine 5(2):e29,
#   05/02/2008 — « lifetime health expenditure was highest among
#   healthy-living people » : les années de vie gagnées coûtent, contre-effet
#   entièrement absent du moteur.
#   https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0050029
# - Vos T. et al., « ACE-Prevention Final Report », University of Queensland /
#   Deakin University, septembre 2010 — 21 mesures DOMINANTES sur 150 : 4,6
#   Md AU$ investis ⇒ 11 Md AU$ d'économies de santé, ratio 2,4. C'est la
#   BORNE HAUTE ABSOLUE (sélection optimale, vie entière), pas une moyenne.
#   https://public-health.uq.edu.au/files/571/ACE-Prevention_final_report.pdf
# - OCDE, « The Heavy Burden of Obesity — The Economics of Prevention », 2019,
#   CHAPITRE 6 (Goryakin et al.) — la meilleure intervention y vaut 13 Md USD
#   PPA cumulés 2020-2050 sur 36 pays, soit ≈ 0,012 Md€ par pays et par an.
#   Le « six-fold economic return » du résumé exécutif du MÊME rapport est un
#   retour PIB/emploi, pas budgétaire : hors périmètre d'un solde public.
#   https://www.oecd.org/en/publications/the-heavy-burden-of-obesity_67450d67-en/full-report/component-11.html
#
# ⚠️ CE QUI N'EXISTE PAS, et ne doit jamais être fabriqué (§ B.3-22 du dossier
# de sourcing v0.6.1) : l'effet budgétaire net d'un euro SUPPLÉMENTAIRE de
# prévention EN FRANCE n'est publié par aucune institution. L'IGAS 2024
# (Bras & Monasse) dit pourquoi : « en l'absence d'une évaluation structurée
# en France de l'efficacité et de l'efficience des actions de PPS ».
# PREVENTION_OFFSET_CENTRAL_CAP est donc — et restera — un CHOIX DE
# MODÉLISATION ASSUMÉ, borné par la littérature internationale ci-dessus,
# JAMAIS présenté comme sourcé. Ce que les sources établissent, c'est
# seulement qu'il est < 1 (d'où le plafond dur) et qu'il est différé.
#
# Ancrage français des ordres de grandeur — Cour des comptes, note sur
# l'Ondam du 14/04/2025 (https://www.ccomptes.fr/fr/documents/74821) :
# 1 an d'espérance de vie sans incapacité ≈ 1,5 Md€ économisés ; prévention
# des maladies chroniques 400 M€ ; prévention de la perte d'autonomie jusqu'à
# 1,2 Md€ ⇒ ≈ 1,6 Md€ à horizon 2029, et par un MEILLEUR CIBLAGE, pas par une
# dépense additionnelle. C'est la borne haute crédible pour la France.
#
# Le délai de 4 ans (contre 2) : Cash & Fourcade 2023 § 45 (« les bénéfices
# économiques de la prévention sont souvent postérieurs aux dépenses
# engagées ») et ACE-Prevention (14 % de la dépense décaissée en année 1).
# La forme de la rampe est une CONVENTION : aucune courbe de rendement
# décroissant n'est publiée (§ B.3-24), mais deux éléments convergents
# interdisent un rendement constant et non borné — Cohen 2008 (« des
# dépistages fréquents sont plus efficaces mais moins efficients ») et
# l'IGAS 2024 (aucune évaluation d'efficience disponible en France).
# NB de sourcing : le dossier v0.6.1 proposait un troisième appui, un constat
# de la Cour des comptes daté de 2021 sur le rendement de la prévention
# française. Il n'est PAS repris : la seule attribution « Cour des comptes
# 2021 » déjà rencontrée dans ce moteur s'est révélée introuvable (§ B.1-5,
# retirée au lot 1), et une garde de citation la bloque désormais. On ne
# re-source pas par approximation — les deux appuis restants suffisent.
PREVENTION_OFFSET_HARD_CEILING = 1.00   # plafond DUR : au-delà, la mesure se paierait elle-même
PREVENTION_OFFSET_CENTRAL_CAP = 0.50    # plafond central — CHOIX DE MODÉLISATION ASSUMÉ
PREVENTION_OFFSET_RAMP_PER_YEAR = 0.10  # montée en charge annuelle du taux (convention)
PREVENTION_OFFSET_LAG_YEARS = 4         # années pleines sans aucun retour


def _valider_domaine_prevention(cap_central, plafond_dur, rampe, delai):
    """Garde de domaine des constantes de prévention.

    Même philosophie que ``GINI_SOFT_FLOOR < GINI_BASE < GINI_HARD_CEILING`` :
    un recalibrage qui inverserait les bornes rendrait la prévention gratuite
    sans qu'aucun test de trajectoire ne le voie sur l'horizon publié.
    ``raise`` et non ``assert`` : ``python -O`` strip les asserts, la garde
    doit survivre en prod.
    """
    if not 0 < cap_central <= plafond_dur <= 1:
        raise ValueError(
            "Prevention : 0 < CENTRAL_CAP <= HARD_CEILING <= 1 requis "
            f"(reçu cap={cap_central}, plafond={plafond_dur}) — au-delà de 1 "
            "la mesure rapporterait plus qu'elle ne coûte, ce qu'aucune source "
            "n'autorise."
        )
    if rampe <= 0 or delai < 0:
        raise ValueError(
            f"Prevention : rampe > 0 et délai >= 0 requis (reçu rampe={rampe}, "
            f"délai={delai})"
        )


_valider_domaine_prevention(
    PREVENTION_OFFSET_CENTRAL_CAP,
    PREVENTION_OFFSET_HARD_CEILING,
    PREVENTION_OFFSET_RAMP_PER_YEAR,
    PREVENTION_OFFSET_LAG_YEARS,
)

# === CALIBRATION ÉCONOMIQUE ===
# Ratio des revenus français indexés sur l'inflation. Calcul empirique pondéré
# (INSEE 2024 - Revenus disponibles bruts) :
#   (SMIC 135Md€×100% + Retraites 330×90% + RSA/APL 150×80%
#    + Point FP 100×30% + Salaires privés 665×25%) / 1380 = 54.22%
# Cohérent avec OFCE Plane & Sampognaro 2024 (indexation effective ~50-55%).
INDEXATION_BASELINE_RATIO = 0.54

# === PART DES DÉPENSES PUBLIQUES INDEXÉES SUR L'INFLATION PASSÉE ===
# Contrat DISTINCT de INDEXATION_BASELINE_RATIO (qui chiffre la protection des
# REVENUS DES MÉNAGES pour le pouvoir d'achat, assiette 1 380 Md€ de revenus) :
# celui-ci chiffre la part de la DÉPENSE PUBLIQUE (assiette 1 649 Md€ de
# primaire) revalorisée sur l'inflation de l'année PRÉCÉDENTE — pensions
# (révalo légale sur l'IPC passé), prestations, bases forfaitaires (FIPECO :
# ~500 Md€ indexés de droit + indexation de fait). Même valeur 0,54 par
# coïncidence de calibration 2026-06 : un recalibrage de l'un NE DOIT PAS
# entraîner l'autre silencieusement (revue type-design 2026-06-10).
# Consommée par engine/expenditures.py (π_idx, refonte assemblage temporel).
INDEXATION_DEPENSES_INFLATION_PASSEE = 0.54
