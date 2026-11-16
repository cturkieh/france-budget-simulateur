"""Cotisations salariales : mode « montant en Md€ » (``montant_md``), constant en euros courants.

Constat (recherche sur les paramètres officiels du lot 3, section 2) : les programmes publiés qui baissent
les cotisations salariales écrivent des MILLIARDS (« 5 milliards », « 15,0 Md€ 2032 », « 120
milliards »), jamais des points ; leur encodage en points (montant ÷ coût du point) n'était fidèle que
parce que le coût du point était figé en euros 2025. Règle commune du moteur (METHODOLOGIE, § Impôts à
taux : règles communes) : un taux suit son assiette, un montant en Md€ reste constant en euros courants.

Le levier reçoit donc deux modes exclusifs, sur le modèle de ``fiscalite_capital.rendement_md`` :
``baisse_points`` (le curseur, en points de la masse salariale brute) et ``montant_md`` (Md€ par an
rendus aux salariés). Avec ``montant_md``, ``baisse_points`` n'est pas lu (refus en strict, correction
signalée sinon). Gini : même coefficient par Md€ rendu (``GINI_COTIS_SAL_PAR_MD``). Calendriers : un
montant en Md€ admet la rampe et les valeurs annuelles, comme les autres montants.
"""
import os
from unittest.mock import patch

import pytest

import budget_simulator.constants as C
from budget_simulator.engine._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS
from budget_simulator.engine.cadre import PROFILS_ELIGIBLES
from budget_simulator.constants import PARAM_DOMAINS
from budget_simulator.simulator import BudgetSimulatorV45


def _handler(params, gdp=3300.0, annee=2030):
    sim = BudgetSimulatorV45(mesures={'cotisations_salariales': params})
    sim._pib_nominal_par_annee[annee] = gdp
    _, rec, impacts = sim._apply_cotisations_salariales({}, params, annee, gdp, 0.015, 0.075)
    return rec, impacts


@pytest.mark.parametrize('montant', [0.5, 5.0, 15.0, 120.0])
@pytest.mark.parametrize('gdp,annee', [(3000.0, 2028), (3300.0, 2030), (3700.0, 2034)])
def test_montant_constant_en_euros_courants(montant, gdp, annee):
    rec, imp = _handler({'montant_md': montant}, gdp, annee)
    assert rec == -montant
    assert imp['menages']['prelevements_directs'] == -montant
    assert imp['gini'] == pytest.approx(C.GINI_COTIS_SAL_PAR_MD * montant, rel=1e-12)


def test_montant_nul_neutre():
    rec, imp = _handler({'montant_md': 0.0})
    assert rec == 0.0 and imp == {}


def test_contrat_du_mode():
    assert 'montant_md' in NOMS_PARAMETRES_ADMIS['cotisations_salariales']
    assert MODES_EXCLUSIFS['cotisations_salariales'] == {'montant_md': frozenset({'baisse_points'})}
    assert PARAM_DOMAINS['cotisations_salariales']['montant_md'] == (0.0, C.COTIS_SAL_MASSE_2025_MD)
    assert 'cotisations_salariales.montant_md' in PROFILS_ELIGIBLES


def test_les_deux_modes_ensemble_refuses_en_strict_signales_sinon():
    mesures = {'cotisations_salariales': {'montant_md': 5.0, 'baisse_points': 2.0}}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        with pytest.raises(ExceptionGroup):
            BudgetSimulatorV45(periods=6, mesures=mesures, annee_debut=2028).simulate()
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        df, _, rapport = BudgetSimulatorV45(periods=6, mesures=mesures, annee_debut=2028).simulate()
        df_m, _, _ = BudgetSimulatorV45(periods=6, mesures={'cotisations_salariales': {'montant_md': 5.0}},
                                        annee_debut=2028).simulate()
    assert rapport['valid'] is False
    assert df['Dette/PIB %'].tolist() == df_m['Dette/PIB %'].tolist()


def test_rampe_d_un_montant_lineaire_de_zero_a_la_cible():
    """Rampe 2028 → 2032 : un cinquième de la cible par an, cible exacte en 2032 (référence 0 : au neutre,
    aucun euro rendu)."""
    sim = BudgetSimulatorV45(periods=10, annee_debut=2028,
                             mesures={'cotisations_salariales': {'montant_md': 120.0}},
                             profils={'cotisations_salariales.montant_md': {'forme': 'rampe'}})
    _, _, rapport = sim.simulate()
    assert rapport['valid'] is True
    imp = {y['Année']: y for y in rapport['measure_impacts_by_year']}
    recettes = [imp[a]['cotisations_salariales']['recettes'] for a in range(2028, 2033)]
    assert recettes == pytest.approx([-24.0, -48.0, -72.0, -96.0, -120.0], abs=1e-9)
    assert imp[2035]['cotisations_salariales']['recettes'] == pytest.approx(-120.0, abs=1e-12)
