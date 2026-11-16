"""ISF : la recette de l'ISF suit le PIB nominal depuis son année source, comme l'IFI qu'il remplace
(règle commune « un taux suit son assiette », METHODOLOGIE § Impôts à taux : règles communes).

Avant : l'IFI déduit suivait le PIB nominal depuis 2025, mais la recette brute de l'ISF restait fixe
en euros (350 000 foyers × 4,512 M€ × 0,75 %, phasage compris). La règle commune ne s'appliquait qu'à
un côté de la différence ISF − IFI, qui perdait de son poids dans le PIB d'année en année. L'impôt
plancher, autre impôt à taux sur le patrimoine, suit déjà le PIB.

Désormais : recette nette de l'année source × PIB_t / PIB(ANNEE_SOURCE_ISF). L'année source est celle
de l'IFI remplacé (2025). C'est une convention de symétrie, déclarée : les chiffrages publiés qui calent
la recette ne fixent pas d'année de base. Le plafond (convention sans source) s'applique en euros de
l'année source et ne mord jamais. Gini et compétitivité ponctuels : euros HORS indice, comme les autres
impôts à taux du moteur (revenus du capital, impôt plancher, bloc du patrimoine).
"""
import pytest

import budget_simulator.constants as C
from budget_simulator.constants import (
    ANNEE_SOURCE_PATRIMOINE,
    PATRIMOINE_IFI_MD,
    PIB_BASE_2025_MD_EUR,
)
from budget_simulator.simulator import BudgetSimulatorV45

# Recette nette de l'ISF complet en euros de l'année source : 350 000 foyers × 4,512 M€ d'assiette
# nette × 0,75 % de taux effectif moyen × (1 − 15 % d'évasion).
RECETTE_NETTE_SOURCE_MD = 350_000 * (4.8 - 4.8 * 0.20 * 0.30) * 0.0075 * 0.85 / 1000


def _isf(i, gdp, annee=2030):
    sim = BudgetSimulatorV45(mesures={'isf_climatique': {'intensite': i}})
    _, rec, impacts = sim._apply_isf_climatique({}, {'intensite': i}, annee, gdp, 0.015, 0.075)
    return rec, impacts


def test_annee_source_de_l_isf_celle_de_l_ifi_remplace():
    assert getattr(C, 'ANNEE_SOURCE_ISF', None) == ANNEE_SOURCE_PATRIMOINE == 2025


@pytest.mark.parametrize('i', [0.3, 0.6, 1.0])
@pytest.mark.parametrize('facteur', [1.1, 1.25, 1.4])
def test_ecart_isf_ifi_proportionnel_au_pib(i, facteur):
    """Les deux côtés de la différence suivent le même PIB : PIB × f donne une recette × f."""
    rec_base, _ = _isf(i, PIB_BASE_2025_MD_EUR)
    rec, _ = _isf(i, PIB_BASE_2025_MD_EUR * facteur)
    assert rec == pytest.approx(rec_base * facteur, rel=1e-12)


@pytest.mark.parametrize('i', [0.3, 1.0])
def test_recette_de_l_annee_source_inchangee(i):
    """Au PIB de l'année source (indice 1), la recette est celle d'avant : i × (recette nette − IFI)."""
    rec, _ = _isf(i, PIB_BASE_2025_MD_EUR)
    assert rec == pytest.approx(i * (RECETTE_NETTE_SOURCE_MD - PATRIMOINE_IFI_MD), rel=1e-12)


@pytest.mark.parametrize('facteur', [1.1, 1.4])
def test_gini_et_competitivite_hors_indice(facteur):
    """Effets ponctuels en euros de l'année source : ils ne dépendent pas du PIB de l'année."""
    _, imp_base = _isf(1.0, PIB_BASE_2025_MD_EUR)
    _, imp = _isf(1.0, PIB_BASE_2025_MD_EUR * facteur)
    assert imp['gini'] == pytest.approx(imp_base['gini'], rel=1e-12)
    assert imp['competitivite'] == pytest.approx(imp_base['competitivite'], rel=1e-12)
    assert imp['menages']['prelevements_directs'] == pytest.approx(
        imp_base['menages']['prelevements_directs'] * facteur, rel=1e-12)


def test_isf_et_ifi_meme_annee_a_pib_egal():
    """À phasage plein, la recette ne dépend du temps que par le PIB."""
    r1, _ = _isf(1.0, 3300.0, 2030)
    r2, _ = _isf(1.0, 3300.0, 2034)
    assert r1 == pytest.approx(r2, abs=1e-12)
