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
CROISSANCE_POTENTIELLE = 0.010  # 1.0% potential growth
CROISSANCE_2025 = 0.009  # 0.9% INSEE définitif 2025

# === FISCAL PARAMETERS ===
TAUX_INTERET_BASE = 0.019  # 1.9% interest rate (OAT 10 ans 2025)

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

# === PROFILS DE PHASING (montée en charge progressive) ===
# Format : tableau indexé par year_idx (0=Y1=2026, 1=Y2=2027, ...), borné à la dernière valeur.
# Retraites — COR 2024 : montée en charge cohortes 5 ans (linéaire 0.2 → 1.0).
PHASING_RETRAITES_5ANS = (0.20, 0.40, 0.60, 0.80, 1.00, 1.00)
# Niches fiscales TGE — Cour des comptes 2024 : débouclage 30-50% Y1, 70% Y2, 100% Y3+.
PHASING_NICHES_FISCALES_TGE = (0.40, 0.70, 1.00, 1.00, 1.00, 1.00)

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
