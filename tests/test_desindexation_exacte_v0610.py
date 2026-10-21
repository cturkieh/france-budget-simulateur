"""Désindexation : ratio EXACT de revalorisation (v0.6.10, contre-audit externe V2-03).

Constat (contre-audit du 07/10/2026 sur v0.6.7, reproduit à l'identique sur v0.6.9) :
``_ecart_revalorisations`` composait ``Π (1 − δ × π)`` et appliquait l'écart à la
masse nominale de l'année, qui est la masse APRÈS revalorisation complète
(``masse_categorie_nominale`` porte l'indice de prix cumulé des dépenses). Le
rapport exact entre une masse revalorisée de ``(1 − δ) × π`` et la même masse
revalorisée de ``π`` est ``(1 + (1 − δ)π) / (1 + π) = 1 − δπ / (1 + π)`` : la
formule v0.6.7 omettait le dénominateur ``1 + π``, une approximation au premier
ordre qui surestimait toute économie (et tout surcoût) de désindexation.

Exemple du contre-audit : une masse de 100 revalorisée de 2 % devient 102 ; un gel
total économise exactement 2, la formule v0.6.7 en rendait 2,04. Après dix
revalorisations à 2 % : écart exact 17,965170 %, formule v0.6.7 18,292719 %.
Dette 2035 des gels totaux, seul le facteur remplacé : pensions 148,02 → 148,06 %,
prestations 150,20 → 150,21 %.
"""
import pytest

from budget_simulator.constants import POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45

_PI = 0.02
_N_MAX = 10   # plafond de revalorisations des prestations ; ici seul compte qu'il ne morde pas


def _ecart_hors_simulation(delta: float, n_revalorisations: int, pi: float = _PI) -> float:
    """Écart du helper du moteur après ``n_revalorisations`` à inflation constante ``pi``.

    Hors simulation, ``_inflation_par_annee`` est vide : chaque revalorisation après
    la première porte l'inflation de l'appel, et la première ``taux_2026`` — ici la
    même ``pi``, pour une inflation rigoureusement constante.
    """
    sim = BudgetSimulatorV45(mesures={})
    return sim._ecart_revalorisations(delta, POLICY_START_YEAR + n_revalorisations - 1,
                                      pi, _N_MAX, pi)


# ---------------------------------------------------------------------------
# RED — chiffres exacts du contre-audit (V2-03)
# ---------------------------------------------------------------------------

def test_v2_03_gel_total_masse_100_revalorisee_a_102_economise_exactement_2():
    """RED v0.6.9 : 102 × 2 % = 2,04. Une masse de 100 revalorisée de 2 % vaut 102 ;
    gelée, elle reste à 100 : l'économie est exactement 2."""
    masse_revalorisee = 100.0 * (1 + _PI)
    economie = masse_revalorisee * _ecart_hors_simulation(1.0, 1)
    assert economie == pytest.approx(2.0, abs=1e-12)


def test_v2_03_dix_revalorisations_a_2_pourcent_ecart_exact():
    """RED v0.6.9 : 18,292719 % (1 − 0,98¹⁰). Exact : 1 − 1,02⁻¹⁰ = 17,965170 %."""
    assert _ecart_hors_simulation(1.0, 10) * 100 == pytest.approx(17.965170, abs=5e-7)


@pytest.mark.parametrize('mesures, dette_2035', [
    pytest.param({'retraites': {'indexation': 0.0}}, 148.06, id='gel_pensions'),
    pytest.param({'prestations_indexation': {'taux_indexation': 0.0}}, 150.21,
                 id='gel_prestations'),
])
def test_v2_03_dette_2035_des_gels_totaux(mesures, dette_2035):
    """RED v0.6.9 : 148,02 (pensions) et 150,20 (prestations). Contre-calcul du
    contre-audit, seul le facteur remplacé par le ratio exact, toutes les autres
    règles conservées (part indexée comprise) : 148,06 et 150,21, au centième.
    Chiffres de la trajectoire v0.6.9 : un lot d'équation ultérieur qui déplace la
    dette du statu quo re-déclare ces deux valeurs en acte."""
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    dette = df.loc[df['Année'] == 2035, 'Dette/PIB %'].iloc[0]
    assert dette == pytest.approx(dette_2035, abs=0.005)


# ---------------------------------------------------------------------------
# Propriétés durables — le défaut ne peut pas revenir.
#
# Référence INDÉPENDANTE du moteur : deux masses construites explicitement, l'une
# revalorisée de π⁺ à chaque revalorisation (pleine indexation), l'autre de
# (1 − δ)π⁺. L'écart du moteur doit valoir (pleine − politique) / pleine, quelle
# que soit l'écriture algébrique retenue dans le code.
# ---------------------------------------------------------------------------

# Trajectoire d'inflation N−1 par année civile (déflation comprise), et taux 2026.
_TAUX_2026 = 0.009
_INFL = {2026: 0.02, 2027: 0.035, 2028: -0.01, 2029: 0.0, 2030: 0.015,
         2031: -0.004, 2032: 0.05, 2033: 0.012, 2034: 0.018}


def _sim_historise(inflation_par_annee):
    """Le moteur hors simulation, avec une mémoire d'inflation imposée."""
    sim = BudgetSimulatorV45(mesures={})
    sim._inflation_par_annee = dict(inflation_par_annee)
    return sim


def _deux_masses(delta, annee, n_max, taux_2026=_TAUX_2026, infl=_INFL):
    """(masse pleinement revalorisée, masse de la politique), base 1 avant 2026."""
    pleine = politique = 1.0
    for s in range(POLICY_START_YEAR, min(annee, POLICY_START_YEAR + n_max - 1) + 1):
        pi = max(taux_2026 if s == POLICY_START_YEAR else infl[s - 1], 0.0)
        pleine *= 1 + pi
        politique *= 1 + (1 - delta) * pi
    return pleine, politique


@pytest.mark.parametrize('delta', [1.0, 0.8, 0.5, 0.1, -0.2])
@pytest.mark.parametrize('n_max', [7, 10])
def test_propriete_ecart_egal_rapport_des_deux_masses(delta, n_max):
    """L'écart du moteur est EXACTEMENT (pleine − politique) / pleine, pour toute
    indexation (sous- et sur-), toute trajectoire d'inflation (déflation comprise)
    et tout plafond de revalorisations."""
    sim = _sim_historise(_INFL)
    for annee in range(POLICY_START_YEAR, 2036):
        pleine, politique = _deux_masses(delta, annee, n_max)
        ecart = sim._ecart_revalorisations(delta, annee, 0.0, n_max, _TAUX_2026)
        assert ecart == pytest.approx((pleine - politique) / pleine, rel=1e-12, abs=1e-15), annee


@pytest.mark.parametrize('pi', [0.0, 0.004, 0.011, 0.02, 0.05, 0.12])
def test_propriete_i_gel_total_retire_exactement_la_revalorisation(pi):
    """(i) Une masse M₀ revalorisée de π vaut M = M₀ (1 + π) ; gelée, elle reste à M₀ :
    économie = M × π / (1 + π) = M₀ × π, exactement, quelle que soit π ≥ 0."""
    m_avant = 336.0
    masse = m_avant * (1 + pi)
    assert masse * _ecart_hors_simulation(1.0, 1, pi) == pytest.approx(m_avant * pi, rel=1e-12, abs=1e-12)


def test_propriete_i_handlers_gel_2026_part_indexee_comprise():
    """(i) Au niveau des handlers : gel total 2026 = part indexée × masse × π / (1 + π),
    au taux de la revalorisation 2026 propre à chaque levier (pensions : le taux légal
    effectif ; prestations : l'inflation 2025 réalisée)."""
    from budget_simulator.constants import (
        INFLATION_BASE, REVALORISATION_PENSIONS_2026 as r26, RETRAITES_PART_MASSE_INDEXEE)
    sim = BudgetSimulatorV45(mesures={})
    d_pen, _, _ = sim._apply_retraites({}, {'indexation': 0.0}, POLICY_START_YEAR, 3000.0, 0.02, 0.075)
    masse_pen = RETRAITES_PART_MASSE_INDEXEE * sim.masse_categorie_nominale('retraites')
    assert d_pen == pytest.approx(-masse_pen * r26 / (1 + r26), rel=1e-12)
    mesures = {'prestations_indexation': {'taux_indexation': 0.0}}
    sim = BudgetSimulatorV45(mesures=mesures)
    d_pre, _, _ = sim._apply_prestations_indexation(
        {}, mesures['prestations_indexation'], POLICY_START_YEAR, 3000.0, 0.02, 0.075)
    masse_pre = sim.masse_categorie_nominale('minima_sociaux')
    assert d_pre == pytest.approx(-masse_pre * INFLATION_BASE / (1 + INFLATION_BASE), rel=1e-12)


@pytest.mark.parametrize('ampleur', [0.05, 0.2])
@pytest.mark.parametrize('pi', [0.009, 0.02, 0.06])
def test_propriete_ii_surindexation_miroir_exact(ampleur, pi):
    """(ii) δ < 0 : pour une revalorisation, le surcoût est le miroir EXACT de
    l'économie de même ampleur, et la masse sur-indexée vaut exactement
    M₀ (1 + (1 + |δ|)π) — composée, elle reste le rapport exact des deux masses
    (test_propriete_ecart_egal_rapport_des_deux_masses)."""
    eco = _ecart_hors_simulation(ampleur, 1, pi)
    sur = _ecart_hors_simulation(-ampleur, 1, pi)
    assert sur == pytest.approx(-eco, rel=1e-12)
    m_avant = 100.0
    masse = m_avant * (1 + pi)
    assert masse * (1 - sur) == pytest.approx(m_avant * (1 + (1 + ampleur) * pi), rel=1e-12)
    # Au niveau du handler des pensions, 2026 : 120 % = −(80 %), exactement.
    sim = BudgetSimulatorV45(mesures={})
    d_sur, _, _ = sim._apply_retraites({}, {'indexation': 1 + ampleur}, POLICY_START_YEAR, 3000.0, pi, 0.075)
    d_eco, _, _ = sim._apply_retraites({}, {'indexation': 1 - ampleur}, POLICY_START_YEAR, 3000.0, pi, 0.075)
    assert d_sur == pytest.approx(-d_eco, rel=1e-12)


def test_propriete_iii_pleine_indexation_ecart_nul():
    """(iii) δ = 0 : écart EXACTEMENT nul (pas seulement petit), toute année, toute
    trajectoire d'inflation — le statu quo reste bit-identique."""
    sim = _sim_historise(_INFL)
    for annee in range(POLICY_START_YEAR, 2036):
        for n_max in (7, 10):
            assert sim._ecart_revalorisations(0.0, annee, 0.03, n_max, _TAUX_2026) == 0.0
    d, _, _ = BudgetSimulatorV45(mesures={})._apply_retraites(
        {}, {'indexation': 1.0}, 2030, 3000.0, 0.02, 0.075)
    assert d == 0.0


@pytest.mark.parametrize('delta', [1.0, 0.3, -0.2])
def test_propriete_iv_deflation_ni_ecart_nouveau_ni_remboursement(delta):
    """(iv) Une revalorisation portant une inflation négative est nulle (la loi ne
    revalorise jamais à la baisse) : elle n'ouvre aucun écart nouveau et ne rend
    rien des écarts passés."""
    infl = {2026: 0.02, 2027: -0.03, 2028: -0.001, 2029: 0.0}
    sim = _sim_historise(infl)
    avant = sim._ecart_revalorisations(delta, 2027, 0.0, 10, _TAUX_2026)
    for annee in (2028, 2029, 2030):
        assert sim._ecart_revalorisations(delta, annee, 0.0, 10, _TAUX_2026) == pytest.approx(
            avant, rel=1e-15, abs=1e-18), annee
    assert avant != 0.0   # les écarts 2026-2027 sont bien constitués


def test_propriete_v_continuite_en_delta_et_en_inflation():
    """(v) Continuité : un ε sur δ ou sur π ne déplace l'écart que d'O(ε) — pas de
    marche au passage de δ = 0 (sous- / sur-indexation) ni de π = 0 (déflation)."""
    eps = 1e-7
    deltas = [-0.2, -0.1, -eps, 0.0, eps, 0.1, 0.5, 0.9, 1.0]
    pis = [-0.02, -eps, 0.0, eps, 0.005, 0.02, 0.1]
    for n in (1, 5, 10):
        for d in deltas:
            for p in pis:
                base = _ecart_hors_simulation(d, n, p)
                assert abs(_ecart_hors_simulation(d + eps, n, p) - base) <= 10 * eps, (n, d, p)
                assert abs(_ecart_hors_simulation(d, n, p + eps) - base) <= 10 * eps, (n, d, p)
