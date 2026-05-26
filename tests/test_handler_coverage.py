"""Coverage handlers + golden master standalone (Phase 0.8 du plan refactor).

Trois tests complémentaires aux golden master combinés (Phase 0.6) :

1. **Coverage 33/33** : 100% des handlers du moteur (`measure_handlers`) sont
   activés par ≥1 scénario combiné FULL_SCENARIOS OU ≥1 mini-scénario standalone
   avec une valeur ≠ default. Détecte les handlers orphelins (oubli de scénario,
   handler obsolète à supprimer, etc.).

2. **Standalone master** : 33 mini-scénarios (1 handler activé, autres à default)
   comparés cellule par cellule au snapshot `standalone_master_v1.json` (33 × 7
   colonnes × 11 années = 2 541 cellules). Évite les bugs masqués par compensation
   entre mesures dans les scénarios combinés.

3. **Pas de silent failure standalone** : aucun handler ne crash silencieusement
   sur sa propre activation isolée. A déjà détecté un bug latent dans
   `_apply_fonction_publique` (format string `{:+d}` sur float depuis JSON).

Régénération du snapshot après changement intentionnel de calibration :
    python tests/snapshots/coverage_scenarios.py --out tests/snapshots/standalone_master_v1.json

Voir docs/REFACTOR_SPLIT_PLAN.md § Phase 0.8.
"""
import json
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45


SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
STANDALONE_MASTER_PATH = SNAPSHOTS_DIR / 'standalone_master_v1.json'
TOLERANCE = 1e-3

sys.path.insert(0, str(SNAPSHOTS_DIR))
from _compare import assert_no_silent_handler_failure, compare_against_snapshot


@pytest.fixture(scope='module')
def standalone_scenarios():
    from coverage_scenarios import build_standalone_scenarios
    return build_standalone_scenarios()


@pytest.fixture(scope='module')
def full_scenarios():
    from run_scenarios_full import SCENARIOS
    return SCENARIOS


@pytest.fixture(scope='module')
def standalone_master():
    if not STANDALONE_MASTER_PATH.exists():
        pytest.fail(
            f"Snapshot standalone manquant : {STANDALONE_MASTER_PATH}. "
            f"Régénérer en jouant tests/snapshots/coverage_scenarios.py."
        )
    return json.loads(STANDALONE_MASTER_PATH.read_text())


@pytest.fixture(scope='module')
def standalone_results(standalone_scenarios):
    """Pré-calcule (df, report) pour chaque mini-scénario : partagé par les 2 tests qui
    en ont besoin (master comparison + no_silent_handler_failure) → 33 simulations
    au lieu de 66."""
    results = {}
    for name, mesures in standalone_scenarios.items():
        df, _, report = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        results[name] = (df, report)
    return results


def _measure_deviates_from_default(measure_id: str, params: dict, defaults: dict) -> bool:
    """True si au moins un paramètre de la mesure dévie de sa valeur default."""
    default_params = defaults.get(measure_id, {})
    for key in set(params) | set(default_params):
        if params.get(key, default_params.get(key)) != default_params.get(key):
            return True
    return False


def test_all_handlers_covered_by_scenarios(full_scenarios, standalone_scenarios):
    """100% des handlers sont activés (valeur ≠ default) par ≥1 scénario FULL OU standalone."""
    sim = BudgetSimulatorV45()
    all_handlers = set(sim.measure_handlers.keys())
    defaults = sim._get_default_values()

    covered = set()
    for scenarios in (full_scenarios, standalone_scenarios):
        for mesures in scenarios.values():
            for measure_id, params in mesures.items():
                if measure_id in all_handlers and _measure_deviates_from_default(measure_id, params, defaults):
                    covered.add(measure_id)

    uncovered = all_handlers - covered
    assert not uncovered, (
        f"\n{len(uncovered)}/{len(all_handlers)} handler(s) jamais activés avec valeur ≠ default "
        f"par les scénarios :\n  {sorted(uncovered)}\n"
        f"Ajouter un mini-scénario dans tests/snapshots/coverage_scenarios.py "
        f"(via les bornes min/max de policy_measures.json)."
    )


def test_standalone_master_all_scenarios_match(standalone_master, standalone_results):
    """Les 33 mini-scénarios actuels matchent le snapshot standalone_master_v1.json (ε=1e-3)."""
    compare_against_snapshot(
        {name: df for name, (df, _) in standalone_results.items()},
        standalone_master,
        label='standalone master',
        missing_msg=("Mini-scénario '{name}' construit dynamiquement mais absent "
                     "du snapshot (régénérer après ajout d'un handler ou modif "
                     "de policy_measures.json)"),
        tolerance=TOLERANCE,
        min_scenarios=33,  # 33 mini-scénarios standalone (anti-faux-vert)
        report_missing_column=True,
    )


def test_standalone_no_silent_handler_failure(standalone_results):
    """Aucun mini-scénario standalone ne fait crasher silencieusement un handler.

    Couverture ANTI-COMPENSATION : un bug masqué dans un scénario combiné se révèle
    en isolation. A déjà détecté `_apply_fonction_publique` qui crashait sur
    `{variation_effectifs:+d}` quand le frontend envoyait un float (25000.0).
    """
    assert_no_silent_handler_failure(
        {name: report for name, (_, report) in standalone_results.items()},
        label="ont échoué en isolation standalone",
        empty_report_msg="{name}: report['measure_impacts_by_year'] vide",
        no_inspection_msg="Aucune mesure inspectée → structure measure_impacts_by_year a changé",
    )
