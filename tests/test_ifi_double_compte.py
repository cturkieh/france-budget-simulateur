"""IFI compté une seule fois quand l'ISF et le levier « patrimoine » sont combinés.

Défaut (audit des défauts anciens du moteur v0.8.1) : ``isf_climatique`` REMPLACE l'IFI — à
l'intensité i, la recette totale vaut (1 − i) × IFI + i × ISF complet (courbe continue v0.6.7) —
pendant que ``fiscalite_patrimoine`` faisait varier un bloc qui contenait encore l'IFI ENTIER :
intensité patrimoine p × IFI était ajouté à un impôt déjà supprimé, dans la recette, dans le canal
des ménages et dans le Gini. Aucune règle d'exclusion ne couvrait la paire (X1 et X2 seulement),
et le rapport sortait ``valid: true``.

Contrat : le bloc du levier patrimoine ne fait varier que l'IFI ENCORE EN VIGUEUR, (1 − i) × IFI,
où i est l'intensité de l'ISF du programme (même lecture croisée que l'impôt plancher, règle Z).
Propriétés : à i = 0, le levier est inchangé au bit ; à i = 1, il ne touche plus l'IFI ; entre
les deux, l'IFI varie au prorata de ce qui en reste ; les successions et la taxe foncière ne
changent pas ; recette, canal ménages, Gini et compétitivité suivent les mêmes euros.
"""
import pytest

from budget_simulator.constants import GINI_HAUT_PATRIMOINE_PAR_MD, PATRIMOINE_IFI_MD, PIB_BASE_2025_MD_EUR
from budget_simulator.simulator import BudgetSimulatorV45

ANNEE = 2030
# PIB de l'année source de l'assiette (indice 1) : les euros du bloc sont ceux de l'année source,
# ceux sur lesquels le Gini est émis (hors indice, tests/test_patrimoine_assiette_pib.py).
GDP = float(PIB_BASE_2025_MD_EUR)


def _patrimoine(p, i, gdp=GDP, annee=ANNEE):
    mesures = {'fiscalite_patrimoine': {'intensite': p}}
    if i is not None:
        mesures['isf_climatique'] = {'intensite': i}
    sim = BudgetSimulatorV45(mesures=mesures)
    _, rec, impacts = sim._apply_fiscalite_patrimoine({}, {'intensite': p}, annee, gdp, 0.015, 0.075)
    return rec, impacts


def _ifi_du_bloc(gdp=GDP, annee=ANNEE):
    """Part IFI du bloc, mesurée et non recopiée : écart entre le bloc sans ISF et le bloc
    sous ISF complet (qui ne doit plus contenir aucun IFI)."""
    rec_sans, _ = _patrimoine(1.0 / 10, None, gdp, annee)
    rec_isf, _ = _patrimoine(1.0 / 10, 1.0, gdp, annee)
    return (rec_sans - rec_isf) * 10


@pytest.mark.parametrize('p', [-0.3, -0.1, 0.05, 0.3])
def test_sans_isf_le_levier_est_inchange(p):
    rec_absent, imp_absent = _patrimoine(p, None)
    rec_zero, imp_zero = _patrimoine(p, 0.0)
    assert rec_zero == rec_absent
    assert imp_zero == imp_absent


@pytest.mark.parametrize('p', [-0.3, 0.1, 0.3])
@pytest.mark.parametrize('i', [0.25, 0.5, 1.0])
def test_l_ifi_ne_varie_qu_au_prorata_de_ce_qui_en_reste(p, i):
    """RED avant correction : la recette du bloc ne dépendait pas de l'ISF (excès p × i × IFI)."""
    rec_sans, imp_sans = _patrimoine(p, None)
    rec, imp = _patrimoine(p, i)
    ifi = _ifi_du_bloc()
    assert ifi > 0
    assert rec == pytest.approx(rec_sans - p * i * ifi, abs=1e-12)
    # Même euros dans le canal des ménages (l'IFI est un impôt courant des ménages).
    assert imp['menages']['prelevements_directs'] == pytest.approx(
        imp_sans['menages']['prelevements_directs'] - p * i * ifi, abs=1e-12)
    # Gini (méthode unique du lot 4, K × montant) : seul l'IFI porte un coefficient (successions et taxe
    # foncière à 0) ; il ne compte que l'IFI encore en vigueur.
    assert imp['gini'] == pytest.approx(imp_sans['gini'] - p * i * ifi * GINI_HAUT_PATRIMOINE_PAR_MD, abs=1e-15)


def test_isf_complet_le_bloc_ne_contient_plus_d_ifi():
    """À l'intensité 1 de l'ISF, le bloc vaut successions + taxe foncière seules : l'écart
    mesuré est exactement l'IFI de la base du bloc."""
    assert _ifi_du_bloc() == pytest.approx(PATRIMOINE_IFI_MD, abs=1e-12)


def test_bout_en_bout_valide_et_sans_exces():
    """Le cas exécuté par l'audit (ISF 1,0 + patrimoine 0,3, mode cadre) : résultat valide, et le
    bloc du patrimoine de la simulation ne contient plus l'IFI supprimé (journal du handler)."""
    sim = BudgetSimulatorV45(periods=10, annee_debut=2028,
                             mesures={'isf_climatique': {'intensite': 1.0},
                                      'fiscalite_patrimoine': {'intensite': 0.3}})
    _, _, rapport = sim.simulate()
    assert rapport['valid'] is True
    assert _ifi_du_bloc() > 0
    rec_seul, _ = _patrimoine(0.3, None)
    rec_combine, _ = _patrimoine(0.3, 1.0)
    assert rec_seul - rec_combine == pytest.approx(0.3 * _ifi_du_bloc(), abs=1e-12)
