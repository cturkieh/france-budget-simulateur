# budget_simulator/__init__.py

# Version du moteur : source UNIQUE, publiée par GET /health (`moteur_version`). La première entrée
# du CHANGELOG porte le même numéro (tests/test_version_publiee.py).
__version__ = "0.8.1"

from .simulator import EconomicConstraints, EconomicValidator, FiscalMultipliers, BudgetSimulatorV45
from .config import load_default_values, load_policy_config
from .engine._param_domain import EntreeInvalide

__all__ = [
    'EconomicConstraints', 
    'EconomicValidator', 
    'FiscalMultipliers', 
    'BudgetSimulatorV45',
    'load_default_values',
    'load_policy_config',
    'EntreeInvalide',
]