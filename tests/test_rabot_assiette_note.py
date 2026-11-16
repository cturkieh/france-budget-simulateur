"""Rabot uniforme : assiette en euros de l'année.

Source rouverte : Institut Montaigne, « Budget base zéro : décider sous la contrainte », novembre 2025
(PDF de 146 pages, retéléchargé), annexe 4, p. 141 : les dépenses sont projetées « selon ce tendanciel en
volume ajusté par le déflateur du PIB » — en euros COURANTS de 2029 ; p. 87 : « ce rabot uniforme devrait
s'élever à 8 % sur l'ensemble des services publics et prestations sociales ».

Avant : l'assiette était en VOLUME (base 2025 × facteurs de volume, qui « ne portent que le volume ») :
un rabot de 8 % ne valait qu'environ 7,4 % des dépenses de l'année en 2032. Désormais : masses nominales
de l'année (``masse_categorie_nominale``) ; l'AAH, part en espèces de « dépendance », à la même assiette.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45


def _coupes(mesures, annee_debut=2028):
    """{année: coupe totale (Md€)} lue dans les détails du handler, et le contexte de l'appel."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut)
    coupes, contexte = {}, {}
    original = sim._apply_rabot_uniforme

    def espion(measure, params, year, gdp, inflation, unemployment):
        out = original(measure, params, year, gdp, inflation, unemployment)
        if out[2]:
            coupes[year] = out[2]['rabot_details']['total_coupe']
            masses = {c: sim.masse_categorie_nominale(c) for c in sim.spending_categories_base}
            contexte[year] = {'gdp': gdp, 'masses': masses, 'phasing': out[2]['rabot_details']['phasing'],
                              'facteur_autres': sim._spending_factors['autres'],
                              'indice_prix': sim.indice_prix_depenses()}
        return out

    sim.measure_handlers['rabot_uniforme'] = espion
    sim._apply_rabot_uniforme = espion
    sim.simulate()
    return coupes, contexte


@pytest.mark.parametrize('annee', [2029, 2030, 2032, 2035])
def test_sans_exclusion_de_la_defense_toute_l_assiette_nominale(annee):
    """Coupe = taux × phasage × Σ masses NOMINALES de l'année (défense non exclue)."""
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_defense': 0}})
    c = ctx[annee]
    assert coupes[annee] == pytest.approx(0.08 * c['phasing'] * sum(c['masses'].values()), rel=1e-12)


def test_la_coupe_suit_les_prix_pas_seulement_le_volume():
    """En 2032, l'indice de prix des dépenses dépasse 1 : la coupe en euros de l'année est plus grande que la
    coupe sur les volumes (base 2025 × facteurs), à taux égal."""
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_defense': 0}})
    c = ctx[2032]
    assert c['indice_prix'] > 1.05
    volume = sum(c['masses'].values()) / c['indice_prix']
    assert coupes[2032] == pytest.approx(0.08 * c['phasing'] * volume * c['indice_prix'], rel=1e-12)
    assert coupes[2032] > 0.08 * c['phasing'] * volume * 1.05
