"""Capture les DELTAS mesure-vs-baseline de 3 scénarios représentatifs.

Référence du test-propriété (e) de la refonte assemblage temporel
(docs/plans/refonte-annee1-assemblage.md, parent) : l'invariant utilisateur du
simulateur est l'ÉCART entre un scénario politique et le statu quo, pas le
niveau absolu. Ce snapshot fige les deltas du moteur de référence ; après tout
changement de moteur, `test_baseline_properties.py::test_e_*` vérifie que les
deltas restent dans une tolérance explicite (anti-explosion / anti-double-
comptage), PAS qu'ils sont identiques (un changement de timing du
multiplicateur déplace légitimement quelques dixièmes).

Régénération (changement intentionnel de calibration uniquement) :
    python3 tests/snapshots/capture_scenario_deltas.py --out tests/snapshots/scenario_deltas_baseline.json

Même source unique scenarios.json que run_scenarios_full.py (skip gracieux en
fork moteur seul).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from budget_simulator.simulator import BudgetSimulatorV45
from run_scenarios_full import SCENARIOS

# 3 scénarios représentatifs : le budget voté (test en or), un programme
# dépensier et un programme d'économies — couvrent les deux signes d'impulsion.
DELTA_SCENARIOS = ('plf_2026', 'lfi_2027', 'rn_2027')
DELTA_COLUMNS = ('Déficit/PIB %', 'Dette/PIB %', 'Chômage %')
DELTA_YEAR_IDX = (1, 5, 10)  # 2026, 2030, 2035


def capture() -> dict:
    baseline_df, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    out = {}
    for name in DELTA_SCENARIOS:
        if name not in SCENARIOS:
            raise KeyError(f"Scénario {name!r} absent de scenarios.json")
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=SCENARIOS[name]).simulate()
        out[name] = {
            col: {str(idx): round(float(df.iloc[idx][col] - baseline_df.iloc[idx][col]), 3)
                  for idx in DELTA_YEAR_IDX}
            for col in DELTA_COLUMNS
        }
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='tests/snapshots/scenario_deltas_baseline.json')
    args = parser.parse_args()
    if not SCENARIOS:
        sys.exit("scenarios.json introuvable (fork moteur seul) — capture impossible.")
    payload = capture()
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    print(f"Deltas capturés → {args.out}")
    for name, cols in payload.items():
        print(f"  {name}: déficit Y10 {cols['Déficit/PIB %']['10']:+.2f} pt, "
              f"dette Y10 {cols['Dette/PIB %']['10']:+.2f} pt")
