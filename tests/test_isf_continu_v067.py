"""ISF climatique en courbe continue (v0.6.7, lot 3D — audit Codex 10/2026 bloc B
constat 5, arbitrage de Cyril n° 3).

v0.6.6, Δ recettes 2030 selon l'intensité : 0 → 0,00 ; 10⁻⁶ → −2,17 Md€ (l'IFI est
supprimé dès que l'intensité dépasse 0, le nouvel impôt rapporte ~0) ; 0,571 →
+0,75 ; 0,572 → +2,02 ; 0,999 → +5,08 ; 1,0 → +7,90 (paliers de foyers et
d'assiette en escalier).

Contrat : recette totale = IFI (droit en vigueur) + intensité × (ISF complet −
IFI) ; écart au statu quo = intensité × (ISF complet − IFI), où « ISF complet »
est le point NFP (seuil 1,3 M€, taux 1 %, bonus vert 30 %) déjà servi à
l'intensité 1. Monotone, continu, nul en 0, identique en 1.
"""
import pytest

from budget_simulator.constants import POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45


def _isf(intensite, year):
    sim = BudgetSimulatorV45(mesures={})
    _, rec, impacts = sim._apply_isf_climatique({}, {'intensite': intensite}, year, 3000.0, 0.015, 0.075)
    return rec, impacts


def _isf_complet(year):
    """Point NFP en forme fermée (paramètres du handler à l'intensité 1)."""
    phasing = 0.5 if year == POLICY_START_YEAR else 1.0
    brutes = 350_000 * (4.8 * (1 - 0.20 * 0.30)) * (0.01 * 0.75) * phasing / 1000
    return brutes * (1 - 0.15)


def _ifi(year):
    return 2.0 * 1.02 ** max(0, year - POLICY_START_YEAR)


GRILLE = [i / 1000 for i in range(1001)] + [1e-6, 0.571, 0.572, 0.999]


@pytest.mark.parametrize('year', [POLICY_START_YEAR, 2030, 2035])
def test_recette_monotone_continue_nulle_en_zero(year):
    """RED v0.6.6 : −2,17 Md€ à 10⁻⁶, sauts de +1,26 à 0,571 et +2,82 entre 0,999
    et 1. Désormais strictement croissante, linéaire, sans saut."""
    grille = sorted(set(GRILLE))
    recettes = [_isf(i, year)[0] for i in grille]
    assert recettes[0] == 0.0
    assert abs(_isf(1e-6, year)[0]) < 1e-5
    pente = _isf_complet(year) - _ifi(year)
    for i, r in zip(grille, recettes):
        assert r == pytest.approx(i * pente, abs=1e-12), i
    assert all(b > a for a, b in zip(recettes, recettes[1:]))


@pytest.mark.parametrize('year', [POLICY_START_YEAR, 2027, 2030, 2035])
def test_intensite_1_inchangee(year):
    """Le point haut était déjà l'ISF complet NFP : à l'intensité 1, la recette
    est EXACTEMENT celle d'avant (2030 : +7,90 Md€)."""
    rec, _ = _isf(1.0, year)
    assert rec == pytest.approx(_isf_complet(year) - _ifi(year), rel=1e-12)
    if year == 2030:
        assert rec == pytest.approx(7.90, abs=5e-3)


def test_effets_macro_interpoles_comme_la_recette():
    """Gini, pouvoir d'achat, compétitivité : même interpolation (nuls en 0,
    identiques en 1), donc continus eux aussi."""
    _, plein = _isf(1.0, POLICY_START_YEAR)
    for i in (0.0, 0.3, 0.6):
        _, imp = _isf(i, POLICY_START_YEAR)
        for k in ('gini', 'competitivite'):
            assert imp.get(k, 0.0) == pytest.approx(i * plein[k], abs=1e-15), (i, k)
        # v0.6.8 : canal ménages = la recette elle-même, donc interpolé pareil.
        directs = imp.get('menages', {}).get('prelevements_directs', 0.0)
        assert directs == pytest.approx(i * plein['menages']['prelevements_directs'],
                                        abs=1e-12), i
