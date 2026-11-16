"""Curseur « Fiscalité du patrimoine » : les donations entrent dans la base (arbitrage du mainteneur).

Le curseur fait varier un pourcentage des recettes de l'IFI, des droits de mutation à titre gratuit et de la taxe
foncière. Jusqu'ici la part « droits de mutation » ne comptait que les successions (16,070 Md€ en 2025) ; elle
compte désormais les successions ET les donations (21,052 Md€, Insee, comptes nationaux annuels, tableau 3.217,
D91), comme le levier ``droits_succession``, qui porte sur les deux. C'est un choix de périmètre, pas une valeur
sourcée. Gini : les droits de mutation sont hors du revenu disponible que mesure l'Insee (coefficient nul, méthode
du lot 4) ; l'effet sur les inégalités ne change pas.
"""
import pytest

import budget_simulator.constants as C
from budget_simulator.simulator import BudgetSimulatorV45


def _patrimoine(p, gdp=None, annee=2030):
    gdp = C.PIB_BASE_2025_MD_EUR if gdp is None else gdp
    sim = BudgetSimulatorV45(mesures={'fiscalite_patrimoine': {'intensite': p}})
    sim._pib_nominal_par_annee[annee] = gdp
    _, rec, impacts = sim._apply_fiscalite_patrimoine({}, {'intensite': p}, annee, gdp, 0.015, 0.075)
    return rec, impacts


def test_la_base_compte_successions_et_donations():
    assert C.DMTG_2025_MD == 21.052
    assert C.PATRIMOINE_SUCCESSIONS_MD == C.DMTG_2025_MD


@pytest.mark.parametrize('p', [-0.3, 0.1, 0.3])
def test_recette_au_pib_2025(p):
    """Au PIB de 2025 : p × (IFI + successions et donations + taxe foncière) = p × 67,945 Md€."""
    rec, _ = _patrimoine(p)
    assert rec == pytest.approx(p * (2.714 + 21.052 + 44.179), rel=1e-12)


@pytest.mark.parametrize('p', [-0.3, 0.3])
def test_les_donations_ajoutent_leur_part_sans_effet_sur_le_gini(p):
    """Par rapport aux successions seules, le curseur ajoute p × 4,982 Md€ de donations ; le Gini ne change pas
    (droits de mutation hors du revenu disponible)."""
    rec, imp = _patrimoine(p)
    rec_successions = p * (2.714 + C.DMTG_SUCCESSIONS_2025_MD + 44.179)
    assert rec - rec_successions == pytest.approx(p * 4.982, rel=1e-9)
    assert C.GINI_SUCCESSIONS_PAR_MD == 0.0
    assert imp['gini'] == pytest.approx(p * C.GINI_HAUT_PATRIMOINE_PAR_MD * C.PATRIMOINE_IFI_MD, rel=1e-12)
