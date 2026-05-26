"""
Economic constants for BudgetLab France simulator.
All values documented with sources.
"""

from pathlib import Path

# Chemin absolu vers policy_measures.json (à la racine du projet, parent du package)
POLICY_MEASURES_PATH = Path(__file__).resolve().parent.parent / 'policy_measures.json'

# === BASELINE ECONOMIC PARAMETERS (INSEE 2025) ===
PIB_BASE_2025_MD_EUR = 2994  # GDP in billion euros
DETTE_RATIO_2025 = 1.156  # 115.6% of GDP
RECETTES_BASE_MD_EUR = 1545  # Government revenue
DEPENSES_BASE_MD_EUR = 1698  # Government spending
CHARGES_INTERET_MD_EUR = 56  # Interest payments on debt

# === UNEMPLOYMENT (INSEE/DARES 2025) ===
CHOMAGE_BASE = 0.076  # 7.6% unemployment rate
CHOMAGE_NAIRU = 0.075  # Natural rate of unemployment

# === INEQUALITY (INSEE 2024) ===
GINI_BASE = 0.29  # Gini coefficient France

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
# INFLATION_STRUCTURELLE : terme intercept (constante additive) de la courbe de
# Phillips augmentée — engine/inflation.py. C'est l'inflation tendancielle de
# moyen terme France vers laquelle pousse le régime quand l'output gap est
# nul/négatif, avant écrêtage par le rappel BCE. Source unique nommée
# (remplace l'ancien littéral magique 0.012).
# Calibration : 1,5 % = médian sourcé entre la sous-jacente INSEE 2025 (+1,2 %)
# et le cœur Banque de France projeté / cible BCE (1,6-2,0 %). Décision PO
# 2026-05-18, Option C (recoupement INSEE / Banque de France / BCE).
INFLATION_STRUCTURELLE = 0.015  # 1,5 % — intercept Phillips, inflation tendancielle moyen terme FR
CROISSANCE_POTENTIELLE = 0.010  # 1.0% potential growth
CROISSANCE_2025 = 0.009  # 0.9% INSEE définitif 2025

# === FISCAL PARAMETERS ===
TAUX_INTERET_BASE = 0.019  # 1.9% interest rate (OAT 10 ans 2025)
# AMORCAGE_DEPENSES_Y1 : facteur d'amorçage Y1 uniquement (~0.03% / Md€). Ce N'EST PAS
# une vraie inertie AR(1) au sens littérature (Pina-Venes 2018 : ρ ≈ 0.7-0.9). La vraie
# persistance des dépenses passe par le compounding de _spending_factors par catégorie
# (santé +1.8%/an, retraites +1.2%/an, etc.) dans calculate_expenditures.
AMORCAGE_DEPENSES_Y1 = 0.0003
EROSION_RECETTES = 0.002  # Revenue erosion rate (CPO 2023)


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
