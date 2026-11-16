"""ISF climatique en courbe continue (v0.6.7, lot 3D — audit Codex 10/2026 bloc B
constat 5, arbitrage du mainteneur n° 3).

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

from budget_simulator.constants import PATRIMOINE_IFI_MD, PIB_BASE_2025_MD_EUR, POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45

GDP = 3000.0  # PIB passé au handler par ces tests


def _isf(intensite, year):
    sim = BudgetSimulatorV45(mesures={})
    _, rec, impacts = sim._apply_isf_climatique({}, {'intensite': intensite}, year, GDP, 0.015, 0.075)
    return rec, impacts


def _isf_complet(year):
    """Point haut en forme fermée (paramètres du handler à l'intensité 1), recette de l'année :
    euros de l'année source × PIB / PIB 2025 (lot 3 : la recette suit le PIB comme l'IFI
    qu'elle remplace ; avant, fixe en euros)."""
    phasing = 0.5 if year == POLICY_START_YEAR else 1.0
    brutes = 350_000 * (4.8 * (1 - 0.20 * 0.30)) * (0.01 * 0.75) * phasing / 1000
    return brutes * (1 - 0.15) * GDP / PIB_BASE_2025_MD_EUR


def _ifi(year):
    """IFI remplacé : recette de l'année source × PIB / PIB 2025 (lot 3 ; avant : 2 Md€ × 1,02^n
    depuis 2026). Ne dépend plus de l'année à PIB donné."""
    return PATRIMOINE_IFI_MD * GDP / PIB_BASE_2025_MD_EUR


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
        # ISF complet ≈ 10,07 Md€ moins l'IFI remplacé, les deux au PIB du test (× 3 000 / 2 991).
        assert rec == pytest.approx((10.0716 - PATRIMOINE_IFI_MD) * GDP / PIB_BASE_2025_MD_EUR, abs=5e-3)


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
