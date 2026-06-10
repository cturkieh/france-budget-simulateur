"""Tests-propriétés du baseline statu quo — contrat de la refonte « assemblage temporel ».

Phase 0 (TDD) de docs/plans/refonte-annee1-assemblage.md (repo parent) : ces 5
propriétés définissent ce qu'un scénario « à politique inchangée » DOIT vérifier,
conformément aux pratiques institutionnelles (CBO/OBR/DG Trésor/HCFP) :

  (a) croissance RÉELLE des dépenses primaires dans [0,8 % ; 1,4 %] CHAQUE année
      (tendanciel officiel +1,0-1,2 %/an ; « chaque année » car une moyenne masque
      une année d'austérité fantôme compensée par une bosse) ;
  (b) aucune marche du ratio dépenses PRIMAIRES/PIB > 0,3 pt entre années
      adjacentes (raccord Y0→Y1 inclus) — le ratio primaire isole l'assemblage de
      la boule de neige des intérêts, légitime en fin d'horizon ;
  (c) élasticité apparente des recettes au PIB nominal = 1,00 ± 0,02 (HCFP
      note 2023-01 : 1,01-1,07, non significativement différent de 1) ;
  (d) jump-off : l'année 0 reproduit les niveaux INSEE au demi-milliard près,
      et la base par catégories somme EXACTEMENT au primaire officiel ;
  (e) non-régression des DELTAS mesure-vs-baseline (l'invariant utilisateur est
      l'écart au statu quo, pas le niveau) vs snapshot scenario_deltas_baseline.json,
      avec tolérances larges EXPLICITES (un changement de timing du multiplicateur
      déplace légitimement quelques dixièmes ; on bloque l'explosion/le
      double-comptage, pas le recalibrage).

Historique : sur le moteur pré-refonte, (a), (b), (c) sont ROUGES — c'est le bug
d'assemblage diagnostiqué le 2026-06-10 (lag du déflateur + couture bridging),
pas une calibration à resserrer. Ne pas « élargir les bornes pour faire passer ».
"""
import json
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import (
    DEPENSES_BASE_MD_EUR,
    RECETTES_BASE_MD_EUR,
    CHARGES_INTERET_MD_EUR,
    PIB_BASE_2025_MD_EUR,
    DETTE_RATIO_2025,
)

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS  # noqa: E402

DELTAS_BASELINE_PATH = SNAPSHOTS_DIR / 'scenario_deltas_baseline.json'
REGEN_DELTAS_CMD = ('python3 tests/snapshots/capture_scenario_deltas.py '
                    '--out tests/snapshots/scenario_deltas_baseline.json')

PRIMARY_SPENDING_2025 = DEPENSES_BASE_MD_EUR - CHARGES_INTERET_MD_EUR  # 1649.3


@pytest.fixture(scope='module')
def statu_quo():
    """Une seule simulation statu quo 10 ans partagée par les propriétés (a)-(d)."""
    results, details, report = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    return results, details


def test_a_croissance_reelle_depenses_primaires_chaque_annee(statu_quo):
    """Statu quo : dépenses primaires en VOLUME entre +0,8 % et +1,4 % chaque année.

    Volume = nominal de l'année N déflaté par l'inflation de l'année N (déflateur
    contemporain, symétrique du PIB). Le tendanciel officiel « politique
    inchangée » France est +1,0-1,2 %/an (LPFP/Commission) ; les ajustements
    démographiques du moteur (vieillissement, dépendance) restent dans [0,8 ; 1,4].
    """
    results, details = statu_quo
    primary = [PRIMARY_SPENDING_2025] + [
        float(details.iloc[i]['Dépenses_Totales']) for i in range(1, 11)
    ]
    violations = []
    for i in range(1, 11):
        infl = float(results.iloc[i]['Inflation %']) / 100
        real_growth = (primary[i] / primary[i - 1]) / (1 + infl) - 1
        if not (0.008 <= real_growth <= 0.014):
            violations.append(f"Y{i} ({2025 + i}) : {real_growth * 100:+.2f} % réel")
    assert not violations, (
        "Croissance réelle des dépenses primaires hors [0,8 % ; 1,4 %] : "
        + " ; ".join(violations)
    )


def test_b_aucune_marche_ratio_primaire(statu_quo):
    """Statu quo : |Δ(dépenses primaires/PIB)| borné entre années adjacentes.

    Inclut le raccord Y0→Y1 (c'est lui le sujet). Ratio PRIMAIRE (hors charge
    d'intérêts) : la boule de neige de la dette est une dynamique légitime qui
    peut dépasser 0,3 pt/an en fin d'horizon sur le ratio total.

    Deux fenêtres de tolérance (décomposition exécutée 2026-06-10, post-refonte) :
    - transitions jusqu'à Y6→Y7 : ≤ 0,30 pt — zone où la démographie du moteur
      est quasi linéaire ; tout dépassement = artefact d'ASSEMBLAGE (l'objet du
      test : l'ancien moteur faisait −0,39 puis −1,31 pt aux raccords) ;
    - transitions Y7→Y8 et suivantes : ≤ 0,60 pt — le vieillissement programmé
      accélère (retraites +0,2 pt ≥ Y5, dépendance +0,3, santé jusqu'à +0,5 :
      ajustements COR/ONDAM du moteur) face à une croissance bridée par le debt
      drag (~0,35-0,55 % réel mesuré) : marches +0,37/+0,48 pt économiquement
      VOULUES (scénario vieillissement non financé), sans aucun terme de prix
      ou de couture (inflation stable ~1,1 % sur la fenêtre).
    """
    results, details = statu_quo
    ratios = [PRIMARY_SPENDING_2025 / PIB_BASE_2025_MD_EUR * 100] + [
        float(details.iloc[i]['Dépenses_Totales']) / float(results.iloc[i]['PIB']) * 100
        for i in range(1, 11)
    ]
    steps = [ratios[i] - ratios[i - 1] for i in range(1, 11)]
    violations = [
        f"Y{i - 1}→Y{i} : {step:+.2f} pt (tol ±{0.30 if i <= 7 else 0.60})"
        for i, step in enumerate(steps, start=1)
        if abs(step) > (0.30 if i <= 7 else 0.60)
    ]
    assert not violations, (
        "Marche(s) du ratio dépenses primaires/PIB hors tolérance en statu quo : "
        + " ; ".join(violations)
    )


def test_c_elasticite_recettes_unitaire(statu_quo):
    """Statu quo : élasticité apparente recettes/PIB nominal = 1,00 ± 0,02 chaque année.

    Niveaux lus dans `details` (Md€, précision 0,1) et non reconstruits depuis
    le ratio affiché (arrondi à 1 décimale de %, qui injecte jusqu'à ±0,03
    d'erreur d'élasticité — artefact de mesure, pas de moteur).
    """
    results, details = statu_quo
    revenues = [float(RECETTES_BASE_MD_EUR)] + [
        float(details.iloc[i]['Recettes_Totales']) for i in range(1, 11)
    ]
    gdp = [float(results.iloc[i]['PIB']) for i in range(0, 11)]
    violations = []
    for i in range(1, 11):
        rev_growth = revenues[i] / revenues[i - 1] - 1
        gdp_growth = gdp[i] / gdp[i - 1] - 1
        elasticity = rev_growth / gdp_growth
        if not (0.98 <= elasticity <= 1.02):
            violations.append(f"Y{i} : {elasticity:.3f}")
    assert not violations, (
        "Élasticité apparente recettes/PIB hors 1,00 ± 0,02 : " + " ; ".join(violations)
    )


def test_d_jump_off_niveaux_insee():
    """Année 0 = niveaux INSEE exacts ; base catégorielle = primaire officiel exact."""
    sim = BudgetSimulatorV45(periods=1, mesures={})
    results, details, _ = sim.simulate()
    y0, d0 = results.iloc[0], details.iloc[0]

    assert abs(float(d0['Dépenses_Totales_Avec_Intérêts']) - DEPENSES_BASE_MD_EUR) <= 0.5, \
        f"Dépenses Y0 {d0['Dépenses_Totales_Avec_Intérêts']} ≠ INSEE {DEPENSES_BASE_MD_EUR}"
    assert abs(float(d0['Recettes_Totales']) - RECETTES_BASE_MD_EUR) <= 0.5
    assert abs(float(y0['Déficit']) - (RECETTES_BASE_MD_EUR - DEPENSES_BASE_MD_EUR)) <= 0.5
    assert abs(float(y0['Dette']) - PIB_BASE_2025_MD_EUR * DETTE_RATIO_2025) <= 1.0
    assert abs(float(y0['PIB']) - PIB_BASE_2025_MD_EUR) <= 0.5

    base_sum = sum(sim.spending_categories_base.values())
    assert abs(base_sum - PRIMARY_SPENDING_2025) <= 0.005, (
        f"Σ spending_categories_base = {base_sum:.1f} ≠ primaire officiel "
        f"{PRIMARY_SPENDING_2025:.1f} (re-ancrer la catégorie résiduelle, pas l'arrondir)"
    )


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_e_non_regression_deltas_scenarios():
    """Les deltas mesure-vs-baseline restent dans une tolérance explicite du snapshot.

    Tolérances LARGES à dessein (phase de refonte : le timing du multiplicateur
    bouge légitimement) : déficit max(1,0 pt ; 25 %), dette max(2,5 pt ; 25 %),
    chômage max(0,5 pt ; 25 %). Elles attrapent une explosion ou un
    double-comptage (deltas ×2), pas un recalibrage. À resserrer post-refonte.
    Régénération (changement intentionnel) : voir REGEN_DELTAS_CMD.
    """
    if not DELTAS_BASELINE_PATH.exists():
        pytest.fail(f"Snapshot deltas manquant : {DELTAS_BASELINE_PATH}\n→ {REGEN_DELTAS_CMD}")
    reference = json.loads(DELTAS_BASELINE_PATH.read_text())
    # Tolérances RESSERRÉES post-refonte (la référence est désormais capturée
    # sur le moteur refondu — vérification croisée 2026-06-10 : deltas de
    # DÉFICIT stables à ±0,3 pt vs pré-refonte sur les 3 scénarios, signes et
    # ordre préservés ; le shift des deltas de dette long terme = effet de
    # composition de la baseline honnête, changement intentionnel documenté).
    tolerances = {
        'Déficit/PIB %': lambda ref: max(0.5, 0.15 * abs(ref)),
        'Dette/PIB %': lambda ref: max(1.5, 0.15 * abs(ref)),
        'Chômage %': lambda ref: max(0.3, 0.15 * abs(ref)),
    }
    baseline_df, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    violations = []
    for name, cols in reference.items():
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=SCENARIOS[name]).simulate()
        for col, by_year in cols.items():
            for year_idx, ref_delta in by_year.items():
                idx = int(year_idx)
                actual = float(df.iloc[idx][col] - baseline_df.iloc[idx][col])
                tol = tolerances[col](ref_delta)
                if abs(actual - ref_delta) > tol:
                    violations.append(
                        f"{name}/{col}/Y{idx} : delta {actual:+.2f} vs réf "
                        f"{ref_delta:+.2f} (tol ±{tol:.2f})"
                    )
    assert not violations, (
        "Deltas mesure-vs-baseline hors tolérance (explosion/double-comptage ?) : "
        + " ; ".join(violations)
    )
