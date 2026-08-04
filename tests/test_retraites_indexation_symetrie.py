"""Tests-propriétés : symétrie budgétaire de l'indexation des retraites.

Contrat verrouillé (cf METHODOLOGIE.md § Retraites) :
- sur-indexation (> 100 %) = surcoût budgétaire, miroir exact de l'économie
  de sous-indexation ;
- érosion CUMULATIVE : RETRAITES_EROSION_INDEXATION_MD_EUR par année écoulée
  pour un gel total, proportionnelle à l'écart, plateau
  RETRAITES_EROSION_PLATEAU_ANS ;
- trajectoires ≤ 100 % par ailleurs inchangées — couvertes par les golden
  masters (renaissance_2027 à 0.9, im_competitivite_2029 à 0.8).
"""

import pytest

from budget_simulator.constants import (
    POLICY_START_YEAR,
    RETRAITES_EROSION_PLATEAU_ANS,
)
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075

# Dernière année de croissance de l'érosion (l'écart au statu quo plafonne ensuite).
_PLATEAU_YEAR = POLICY_START_YEAR + RETRAITES_EROSION_PLATEAU_ANS - 1


def _delta_depenses(indexation: float, year: int) -> float:
    """Impact dépenses (Md€, négatif = économie) du handler retraites —
    âge et durée laissés aux défauts du handler (statu quo)."""
    sim = BudgetSimulatorV45(mesures={})
    delta, _, _ = sim._apply_retraites(
        {}, {'indexation': indexation}, year, _GDP, _INFLATION, _UNEMP
    )
    return delta


def test_surindexation_a_un_cout_budgetaire():
    """120 % de compensation = dépense supplémentaire, pas un repas gratuit."""
    assert _delta_depenses(1.2, POLICY_START_YEAR + 4) > 0


def test_symetrie_sous_sur_indexation():
    """±20 % d'écart à la pleine indexation → impacts budgétaires miroirs."""
    for year in (POLICY_START_YEAR, POLICY_START_YEAR + 2,
                 POLICY_START_YEAR + 4, POLICY_START_YEAR + 9):
        economie = _delta_depenses(0.8, year)
        surcout = _delta_depenses(1.2, year)
        assert surcout == pytest.approx(-economie), (
            f"asymétrie en {year} : économie {economie:+.2f} vs surcoût {surcout:+.2f}"
        )


def test_pleine_indexation_neutre():
    """100 % = statu quo légal, zéro impact budgétaire."""
    assert _delta_depenses(1.0, POLICY_START_YEAR + 4) == 0


def test_symetrie_age_et_duree():
    """Le refactor uniformise aussi âge et durée : ±1 an autour de la
    référence 2025 → impacts budgétaires miroirs (même contrat que
    l'indexation, non couvert par les golden masters en direction baisse)."""
    sim = BudgetSimulatorV45(mesures={})
    year = POLICY_START_YEAR + 4

    def delta(params):
        d, _, _ = sim._apply_retraites({}, params, year, _GDP, _INFLATION, _UNEMP)
        return d

    assert delta({'age_depart': 63.75}) == pytest.approx(
        -delta({'age_depart': 61.75}))
    assert delta({'duree_cotisation': 43.5}) == pytest.approx(
        -delta({'duree_cotisation': 41.5}))


def test_gel_total_erosion_lineaire_puis_plateau():
    """Caractérisation (comportement pré-existant, verrou anti-régression) :
    valeurs épinglées en littéral à dessein — 1,5 Md€ × années écoulées."""
    assert _delta_depenses(0.0, POLICY_START_YEAR) == pytest.approx(-1.5)
    assert _delta_depenses(0.0, POLICY_START_YEAR + 4) == pytest.approx(-7.5)
    assert _delta_depenses(0.0, _PLATEAU_YEAR) == pytest.approx(-10.5)
    # Plateau : au-delà, l'écart au statu quo n'augmente plus.
    assert _delta_depenses(0.0, POLICY_START_YEAR + 9) == pytest.approx(
        _delta_depenses(0.0, _PLATEAU_YEAR)
    )


def test_surindexation_degrade_le_deficit_en_simulation_complete(statu_quo):
    """Intégration bout en bout : sur-indexer à 120 % doit creuser le déficit
    par rapport au statu quo (câblage handler → assemblage vérifié)."""
    sur_df, _, _ = BudgetSimulatorV45(
        mesures={'retraites': {'indexation': 1.2}}
    ).simulate()
    year = POLICY_START_YEAR + 4
    base = statu_quo.loc[statu_quo['Année'] == year, 'Déficit/PIB %'].iloc[0]
    sur = sur_df.loc[sur_df['Année'] == year, 'Déficit/PIB %'].iloc[0]
    assert sur < base, (
        f"déficit {year} inchangé malgré la sur-indexation : {sur} vs {base}"
    )
