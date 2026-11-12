"""Golden master du CADRE 2027-2032 (v0.7.0) : les 10 scénarios publiés avec
``annee_debut = 2028``, cellule par cellule (mêmes colonnes et même tolérance que
``test_golden_master_full.py``, qui fige le mode historique, sortie de v0.6.11).

Régénération (changement intentionnel, à motiver dans le CHANGELOG) :
    BUDGETLAB_REGEN=1 make snapshot-baseline
ou directement :
    python tests/snapshots/run_scenarios_full.py --annee-debut 2028 \
        --out tests/snapshots/golden_master_cadre_2028.json
"""
import json
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
GOLDEN_PATH = SNAPSHOTS_DIR / 'golden_master_cadre_2028.json'
TOLERANCE = 1e-3
ANNEE_DEBUT = 2028
REGEN_CMD = ('python tests/snapshots/run_scenarios_full.py --annee-debut 2028 '
             '--out tests/snapshots/golden_master_cadre_2028.json')

sys.path.insert(0, str(SNAPSHOTS_DIR))
from _compare import assert_no_silent_handler_failure, compare_against_snapshot  # noqa: E402
from run_scenarios_full import PROFILS, SCENARIOS, TRACKED_COLUMNS  # noqa: E402

pytestmark = pytest.mark.skipif(
    not SCENARIOS,
    reason="scenarios.json hors périmètre fork moteur seul (frontend-react absent)",
)


@pytest.fixture(scope='module')
def resultats():
    # Calendriers de chaque scénario (release E, contrat § 2.3), comme le runner
    # qui écrit l'instantané et comme le site : fiche = simulateur = précalcul =
    # golden master. Release P : des scénarios publiés en portent.
    return {name: BudgetSimulatorV45(periods=10, mesures=m, annee_debut=ANNEE_DEBUT,
                                     profils=PROFILS.get(name) or None).simulate()
            for name, m in SCENARIOS.items()}


def test_golden_master_cadre(resultats):
    if not GOLDEN_PATH.exists():
        pytest.fail(f"Snapshot manquant : {GOLDEN_PATH}. Régénérer : {REGEN_CMD}")
    compare_against_snapshot(
        {name: r[0] for name, r in resultats.items()},
        json.loads(GOLDEN_PATH.read_text(encoding='utf-8')),
        label='golden master cadre 2028',
        missing_msg="Scénario '{name}' absent du snapshot cadre",
        tolerance=TOLERANCE, min_scenarios=8, regen_hint=REGEN_CMD,
        tracked_columns=TRACKED_COLUMNS,
    )


def test_golden_master_cadre_sans_echec_silencieux(resultats):
    assert_no_silent_handler_failure(
        {name: r[2] for name, r in resultats.items()},
        label="ont échoué silencieusement dans le golden master cadre",
        empty_report_msg="{name}: report['measure_impacts_by_year'] vide",
        no_inspection_msg="Aucune mesure inspectée (structure measure_impacts_by_year changée)",
    )
