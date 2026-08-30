"""
Pytest configuration and shared fixtures for BudgetLab France tests.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Enable debug mode for tests BEFORE importing the simulator
# (DEBUG_MODE is read at module level)
os.environ['BUDGET_DEBUG'] = 'true'

from budget_simulator import BudgetSimulatorV45, FiscalMultipliers, load_default_values


@pytest.fixture
def simulator():
    """Create a simulator with overridden base params for unit tests.

    ⚠️ HARNAIS FIGÉ, PAS L'ANCRE COURANTE : ces valeurs sont une photographie
    délibérément gelée (recettes/dépenses en prévision PLF, croissance 0,009,
    inflation 0,01…) pour que les tests unitaires calés dessus survivent aux
    recalages de constants.py. Ne PAS les « mettre à jour » vers les valeurs
    INSEE du moment (v0.6.3 : CROISSANCE_2025 = 0,008, INFLATION_BASE = 0,011)
    — un test qui veut l'ancre courante importe constants.py directement.
    """
    sim = BudgetSimulatorV45(periods=1)
    sim.base_params = {
        'pib_base': 2994,
        'dette_ratio': 1.156,
        'recettes_base': 1545,
        'depenses_base': 1698,
        'chomage_base': 0.076,
        'chomage_nairu': 0.075,
        'croissance_potentielle': 0.01,
        'croissance_2025': 0.009,
        'taux_interet_base': 0.019,
        'inflation_base': 0.01,
        # erosion_recettes / amorcage_depenses_y1 : retirés → tombstones constants.py
    }
    sim.pib_nominal = 2994
    sim.recettes_precedentes = 1545
    sim.debug_logs = []
    return sim


@pytest.fixture
def multipliers():
    """Create FiscalMultipliers instance."""
    return FiscalMultipliers()


@pytest.fixture
def default_simulator():
    """Create a simulator with default parameters."""
    return BudgetSimulatorV45(periods=10)


@pytest.fixture
def short_simulator():
    """Create a simulator for quick tests (1 period)."""
    return BudgetSimulatorV45(periods=1)


@pytest.fixture
def default_values():
    """Load default parameter values."""
    return load_default_values()


@pytest.fixture(scope="session")
def statu_quo():
    """DataFrame d'une simulation statu quo (aucune mesure), partagé.

    Déterministe (``np.random.seed(42)`` dans ``_reset_state`` avant chaque
    ``simulate()``), donc factorisable en une seule exécution. Dédup des 4
    simulations identiques de ``test_validation_pa_indexation.py`` (Lot E).
    LECTURE SEULE : ne pas muter le DataFrame (scope session)."""
    df, _, _ = BudgetSimulatorV45(mesures={}).simulate()
    return df
