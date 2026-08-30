"""Harnais partagé du handler assurance-chômage (revue Reuse v0.6.4).

La signature d'appel de ``_apply_chomage_alloc`` (7 args positionnels) et la
forme de son tuple de retour (``[0]`` = delta_spending, ``[2]`` = impacts) ne
vivent qu'ICI — ``test_passe_bugs_v063`` et ``test_calage_chomage_v064``
testaient le même handler avec deux copies mot pour mot de ce harnais, et
tout changement de contrat cassait deux fichiers indépendamment.

Chaque appel construit un simulateur FRAIS : le handler mute
``self._chomage_params_prev`` (sémantique ``is_first_year``) — partager une
instance casserait les impacts one-time testés.
"""
from budget_simulator.simulator import BudgetSimulatorV45

GDP, INFLATION, UNEMP = 3000.0, 0.02, 0.075


def chomage(params):
    """Tuple complet du handler (le handler ne lit pas self.mesures)."""
    sim = BudgetSimulatorV45(periods=10)
    return sim._apply_chomage_alloc({}, params, 2027, GDP, INFLATION, UNEMP)


def chomage_ds(params):
    return chomage(params)[0]


def chomage_impacts(params):
    return chomage(params)[2]
