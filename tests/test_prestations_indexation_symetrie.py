"""Tests-propriétés : symétrie budgétaire de l'indexation des prestations.

Même contrat que les retraites (test_retraites_indexation_symetrie.py) :
la sur-indexation (> 100 %) des prestations (RSA/APL/allocations, base
90 Md€) doit COÛTER — le gate de signe historique (`delta_indexation > 0`)
rendait la sur-indexation budgétairement gratuite alors que Gini et
pouvoir d'achat y répondaient déjà (repéré en revue croisée 2026-08-04,
amplitude 16× celle des pensions sur le Gini).

Trajectoires ≤ 100 % inchangées — couvertes par les golden masters
(renaissance_2027 à 0.8, autres à 1.0).
"""

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075
_YEAR = 2029  # year_idx = 4 → érosion composée active


def _delta_depenses(taux: float, year: int = _YEAR) -> float:
    """Impact dépenses (Md€, négatif = économie) du handler prestations."""
    mesures = {'prestations_indexation': {'taux_indexation': taux}}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    ds, _, _ = sim._apply_prestations_indexation(
        {}, mesures['prestations_indexation'], year, _GDP, _INFLATION, _UNEMP)
    return ds


def test_surindexation_a_un_cout_budgetaire():
    """120 % de compensation = dépense supplémentaire, pas un repas gratuit."""
    assert _delta_depenses(1.2) > 0


def test_symetrie_sous_sur_indexation():
    """±20 % d'écart à la pleine indexation → impacts budgétaires miroirs
    (formule composée : miroir au 2ᵉ ordre près, tolérance relative)."""
    economie = _delta_depenses(0.8)
    surcout = _delta_depenses(1.2)
    assert economie < 0 < surcout
    assert surcout == pytest.approx(-economie, rel=0.02), (
        f"asymétrie : économie {economie:+.3f} vs surcoût {surcout:+.3f}"
    )


def test_pleine_indexation_neutre():
    """100 % = statu quo légal, zéro impact budgétaire."""
    assert _delta_depenses(1.0) == 0
