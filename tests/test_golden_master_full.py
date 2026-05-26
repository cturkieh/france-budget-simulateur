"""Golden master strict cellule par cellule (Phase 0.6 du plan refactor).

Filet de sécurité avant le split modulaire (Phase 1) : toute modification du moteur
qui change le moindre chiffre d'un des 8 scénarios politiques (PLF 2026, RN 2027,
LFI 2027, Renaissance 2027, LR 2027, PS 2027, IM Rabot 2029, IM Compétitivité 2029)
fera virer ce test au rouge avec un message indiquant scénario/colonne/année/écart.

Le snapshot de référence `tests/snapshots/golden_master_v1.json` doit être régénéré
explicitement après chaque changement intentionnel de calibration :
    python tests/snapshots/run_scenarios_full.py --out tests/snapshots/golden_master_v1.json

Le déterminisme est garanti par `np.random.seed(42)` dans simulator.py (lignes 363/627).
Tolérance ε=1e-3 cohérente avec l'arrondi 3 décimales du snapshot.

La boucle de comparaison et la détection de silent failure sont factorisées dans
`tests/snapshots/_compare.py` (dédup Lot E, partagée avec test_handler_coverage.py).

Voir docs/REFACTOR_SPLIT_PLAN.md § Phase 0.6.
"""
import json
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
GOLDEN_MASTER_PATH = SNAPSHOTS_DIR / 'golden_master_v1.json'
TOLERANCE = 1e-3  # 3 décimales (cohérent avec round 3 dans run_scenarios_full.py)
REGEN_CMD = 'python tests/snapshots/run_scenarios_full.py --out tests/snapshots/golden_master_v1.json'

sys.path.insert(0, str(SNAPSHOTS_DIR))
from _compare import assert_no_silent_handler_failure, compare_against_snapshot
from run_scenarios_full import SCENARIOS as _SCENARIOS_AT_IMPORT

# Le golden master compare bit-à-bit les 8 scénarios politiques. Source unique
# = `frontend-react/src/data/scenarios.json` (lue par run_scenarios_full). Pour
# un fork moteur seul, SCENARIOS = {} → on skip plutôt que d'asserter sur du vide.
pytestmark = pytest.mark.skipif(
    not _SCENARIOS_AT_IMPORT,
    reason="scenarios.json hors périmètre fork moteur seul (frontend-react absent)",
)


@pytest.fixture(scope='module')
def golden_master():
    if not GOLDEN_MASTER_PATH.exists():
        pytest.fail(f"Snapshot golden master manquant : {GOLDEN_MASTER_PATH}.\nRégénérer : {REGEN_CMD}")
    return json.loads(GOLDEN_MASTER_PATH.read_text())


@pytest.fixture(scope='module')
def scenarios_data():
    from run_scenarios_full import SCENARIOS, TRACKED_COLUMNS
    return SCENARIOS, TRACKED_COLUMNS


@pytest.fixture(scope='module')
def scenario_results(scenarios_data):
    """(df, report) par scénario, simulé UNE fois, partagé par les 2 tests
    (8 simulations au lieu de 16)."""
    scenarios, _ = scenarios_data
    out = {}
    for name, mesures in scenarios.items():
        df, _, report = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        out[name] = (df, report)
    return out


def test_golden_master_all_scenarios_match(golden_master, scenarios_data, scenario_results):
    """Compare cellule par cellule chaque scénario actuel au snapshot de référence.

    Pour chaque (scénario × colonne × année) : `abs(actual - expected) < TOLERANCE`.
    Vérifie aussi le shape (colonnes tracked, années) pour détecter les régressions
    structurelles : nouvelle colonne ignorée, colonne disparue, drift d'index.
    """
    _, tracked_columns = scenarios_data
    compare_against_snapshot(
        {name: df for name, (df, _) in scenario_results.items()},
        golden_master,
        label='golden master',
        missing_msg="Scénario '{name}' présent dans run_scenarios_full mais absent du snapshot",
        tolerance=TOLERANCE,
        min_scenarios=8,  # 8 scénarios politiques (anti-faux-vert fixture cassée)
        regen_hint=REGEN_CMD,
        tracked_columns=tracked_columns,
    )


def test_golden_master_no_silent_handler_failure(scenario_results):
    """Aucun des 8 scénarios ne doit avoir un handler qui crash silencieusement.

    Combine le golden master (Phase 0.6) avec le flag _handler_failed (Phase 0.7) :
    si une refacto fait crasher un handler dans un scénario où la mesure était à
    valeur sourcée, le golden master pourrait matcher (cellule cappée à default ou
    proche), mais le flag révèlera la régression.
    """
    assert_no_silent_handler_failure(
        {name: report for name, (_, report) in scenario_results.items()},
        label="ont échoué silencieusement dans les scénarios golden master",
        empty_report_msg="{name}: report['measure_impacts_by_year'] vide → régression structurelle",
        no_inspection_msg="Aucune mesure inspectée sur 8 scénarios → la structure measure_impacts_by_year a changé",
    )
