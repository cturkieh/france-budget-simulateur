"""Impôts sur le patrimoine : l'assiette suit le PIB nominal depuis son année source (règle commune
« un taux suit son assiette », METHODOLOGIE § Impôts à taux : règles communes).

Avant le lot 3, deux exceptions à la règle :

- ``fiscalite_patrimoine`` (IFI + successions et donations + taxe foncière) : une intensité est un
  pourcentage des recettes de ces impôts, donc un taux ; le moteur l'appliquait pourtant à un bloc
  figé en euros de l'année source, quelle que soit l'année — sa part dans le PIB baissait d'environ
  10 % sur le mandat ;
- l'IFI que remplace ``isf_climatique`` croissait de 2 % par an depuis 2026 (« inflation
  patrimoniale »), une convention propre à ce levier, sans source ouverte.

Désormais : bloc × intensité × PIB_t / PIB_2025 et IFI remplacé × PIB_t / PIB_2025 (indice
d'assiette des impôts à taux, ``_indice_pib_source``) ; aucune valeur de base ne change ici (release
de paramètres distincte). Gini et compétitivité ponctuels : euros HORS indice, comme les autres
impôts à taux du moteur (revenus du capital, impôt plancher).
"""
import pytest

from budget_simulator.constants import (
    GINI_HAUT_PATRIMOINE_PAR_MD,
    PATRIMOINE_IFI_MD,
    PIB_BASE_2025_MD_EUR,
)
from budget_simulator.simulator import BudgetSimulatorV45


def _patrimoine(p, gdp, annee=2030):
    sim = BudgetSimulatorV45(mesures={'fiscalite_patrimoine': {'intensite': p}})
    sim._pib_nominal_par_annee[annee] = gdp
    _, rec, impacts = sim._apply_fiscalite_patrimoine({}, {'intensite': p}, annee, gdp, 0.015, 0.075)
    return rec, impacts


def _isf(i, gdp, annee=2030):
    sim = BudgetSimulatorV45(mesures={'isf_climatique': {'intensite': i}})
    _, rec, impacts = sim._apply_isf_climatique({}, {'intensite': i}, annee, gdp, 0.015, 0.075)
    return rec, impacts


@pytest.mark.parametrize('p', [-0.3, -0.05, 0.1, 0.3])
@pytest.mark.parametrize('facteur', [1.1, 1.25, 1.4])
def test_bloc_patrimoine_proportionnel_au_pib(p, facteur):
    rec_base, imp_base = _patrimoine(p, PIB_BASE_2025_MD_EUR)
    rec, imp = _patrimoine(p, PIB_BASE_2025_MD_EUR * facteur)
    assert rec == pytest.approx(rec_base * facteur, rel=1e-12)
    assert imp['menages']['prelevements_directs'] == pytest.approx(
        imp_base['menages']['prelevements_directs'] * facteur, rel=1e-12)
    # Gini et compétitivité ponctuels : hors indice (euros de l'année source).
    assert imp['gini'] == pytest.approx(imp_base['gini'], rel=1e-12)
    assert imp['competitivite'] == pytest.approx(imp_base['competitivite'], rel=1e-12)
    # Méthode unique du lot 4 (K × montant) : seul l'IFI porte un coefficient, en euros de l'année source.
    assert imp['gini'] == pytest.approx(p * GINI_HAUT_PATRIMOINE_PAR_MD * PATRIMOINE_IFI_MD, rel=1e-12)


@pytest.mark.parametrize('annee', [2026, 2028, 2030, 2035])
def test_bloc_patrimoine_ne_depend_pas_de_l_annee_a_pib_egal(annee):
    rec_2030, _ = _patrimoine(0.2, 3300.0, 2030)
    rec, _ = _patrimoine(0.2, 3300.0, annee)
    assert rec == rec_2030


def test_ifi_remplace_par_l_isf_suit_le_pib_et_pas_le_calendrier():
    """À phasage plein, la recette de l'ISF ne dépend du temps que par le PIB : l'IFI remplacé
    vaut IFI × PIB_t / PIB_2025, comme la recette de l'ISF qui le remplace (même PIB, années
    différentes : même recette ; PIB × 1,2 : écart ISF − IFI × 1,2 ;
    tests/test_isf_recette_suit_pib.py)."""
    r1, _ = _isf(1.0, 3300.0, 2030)
    r2, _ = _isf(1.0, 3300.0, 2034)
    assert r1 == pytest.approx(r2, abs=1e-12)
    r3, _ = _isf(1.0, 3300.0 * 1.2, 2030)
    assert r3 == pytest.approx(r1 * 1.2, rel=1e-12)


def test_chiffre_publie_de_l_isf_en_2030_lie_a_la_mesure():
    """METHODOLOGIE (§ ISF climatique) publie la recette de l'ISF complet en 2030 en mode cadre :
    le chiffre écrit est celui que rend le moteur (arrondi à 0,01 Md€)."""
    from pathlib import Path
    sim = BudgetSimulatorV45(periods=10, annee_debut=2028, mesures={'isf_climatique': {'intensite': 1.0}})
    _, _, rapport = sim.simulate()
    recette = {y['Année']: y for y in rapport['measure_impacts_by_year']}[2030]['isf_climatique']['recettes']
    ecrit = f"+{recette:.2f}".replace('.', ',') + ' Md EUR en 2030 en\nmode cadre'
    doc = (Path(__file__).absolute().parent.parent / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    assert ecrit in doc, ecrit
