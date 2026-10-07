"""Désindexation des pensions proportionnelle à l'inflation, prestations alignées
(v0.6.7, lot 3C — audit Codex 10/2026 bloc B constat 2, arbitrage de Cyril n° 2).

v0.6.6 : pensions = 1,5 Md€ × (1 − indexation) × min(années, 7), SANS inflation —
un gel total rapportait 3,00 Md€ en 2027 que l'inflation vaille 0 %, 1,5 % ou 4 %,
soit une inflation implicite de 0,39 % sur la masse des pensions. Prestations
(lot 2) : base 90 Md€ figée en euros 2025, et rien en 2026.

Contrat : économie(t) = masse indexée(t) × [1 − Π_s (1 − δ × max(π_s, 0))],
δ = 1 − indexation, une revalorisation par an dès POLICY_START_YEAR, chacune à
l'inflation de l'ANNÉE PRÉCÉDENTE (2026 : l'inflation 2025 réalisée, INFLATION_BASE
— réfutation des handlers, v0.6.7 ; c'était l'inflation de l'année courante) ;
masse indexée = masse NOMINALE de la catégorie du moteur l'année t (× part indexée
pour les pensions, calée sur l'OFCE).
"""
import pytest

from budget_simulator.constants import (
    POLICY_START_YEAR,
    RETRAITES_EROSION_PLATEAU_ANS,
    RETRAITES_PART_MASSE_INDEXEE,
)
from budget_simulator.simulator import BudgetSimulatorV45


def _pension(indexation, year, inflation):
    sim = BudgetSimulatorV45(mesures={})
    d, _, _ = sim._apply_retraites({}, {'indexation': indexation}, year, 3000.0, inflation, 0.075)
    return d, sim


def test_pensions_economie_proportionnelle_a_l_inflation():
    """RED v0.6.6 : −1,50 Md€ en 2026 à π = 0 %, 1,5 % ou 3 %. Désormais :
    2026 = masse indexée × la revalorisation légale effective du 1er janvier 2026
    (un fait, REVALORISATION_PENSIONS_2026), quelle que soit l'inflation du moteur ;
    la revalorisation 2027 porte l'inflation 2026 — nulle sans inflation,
    proportionnelle sinon (hors simulation : l'inflation de l'appel)."""
    from budget_simulator.constants import REVALORISATION_PENSIONS_2026 as r26
    gels_2026 = {pi: _pension(0.0, POLICY_START_YEAR, pi)[0] for pi in (0.0, 0.015, 0.03)}
    _, sim = _pension(0.0, POLICY_START_YEAR, 0.0)
    masse = RETRAITES_PART_MASSE_INDEXEE * sim.masse_categorie_nominale('retraites')
    assert all(g == pytest.approx(-masse * r26, rel=1e-12) for g in gels_2026.values())
    for pi in (0.0, 0.015, 0.03):
        d, _ = _pension(0.0, POLICY_START_YEAR + 1, pi)
        assert d == pytest.approx(-masse * (1 - (1 - r26) * (1 - pi)), rel=1e-12), pi


def test_pensions_ancrage_ofce_annee_blanche_2026():
    """OFCE (P. Madec, billet du 30/06/2025, « Impôts et prestations : quels effets
    attendre d'une année blanche ? ») : gel des pensions de retraite au 1er janvier
    2026, revalorisation évitée 1,1 %, économie 3,7 Md€. Le moteur, sur SA masse
    nominale 2026 du statu quo, le reproduit à 0,05 Md€ près."""
    sim = BudgetSimulatorV45(periods=1, mesures={})
    sim.simulate()   # l'état final est celui de 2026
    masse_2026 = RETRAITES_PART_MASSE_INDEXEE * sim.masse_categorie_nominale('retraites')
    assert masse_2026 * 0.011 == pytest.approx(3.7, abs=0.05)


class _Script(BudgetSimulatorV45):
    """Le moteur, inflation imposée (année civile → π), masses relevées à chaque appel."""
    script: dict = {}

    def calculate_inflation(self, year, economic_state):
        return self.script[self.annee_base + year]

    def _apply_retraites(self, measure, params, year, gdp, inflation, unemployment):
        self.masses.setdefault('retraites', {})[year] = (
            RETRAITES_PART_MASSE_INDEXEE * self.masse_categorie_nominale('retraites'))
        return super()._apply_retraites(measure, params, year, gdp, inflation, unemployment)

    def _apply_prestations_indexation(self, measure, params, year, gdp, inflation, unemployment):
        self.masses.setdefault('prestations', {})[year] = self.masse_categorie_nominale('minima_sociaux')
        return super()._apply_prestations_indexation(measure, params, year, gdp, inflation, unemployment)


def _trajectoire(levier, params, script):
    cls = type('_S', (_Script,), {'script': script})
    sim = cls(periods=10, mesures={levier: params})
    sim.masses = {}
    _, _, rapport = sim.simulate()
    dep = {an['Année']: an.get(levier, {}).get('depenses', 0.0)
           for an in rapport['measure_impacts_by_year']}
    return dep, sim.masses


def _ecart(delta, script, annee, n_max, levier='retraites'):
    """Revalorisation de s à l'inflation de s − 1 ; celle de 2026 est un fait que
    le script n'impose pas : le taux légal effectif pour les pensions, l'inflation
    2025 réalisée (INFLATION_BASE) pour les prestations."""
    return _ecart_n_moins_1(delta, script, annee, n_max, _TAUX_2026[levier])


from budget_simulator.constants import INFLATION_BASE, REVALORISATION_PENSIONS_2026  # noqa: E402

_TAUX_2026 = {'retraites': REVALORISATION_PENSIONS_2026, 'prestations': INFLATION_BASE}

PIS = [0.011, 0.01, 0.03, 0.005, -0.01, 0.02, 0.0, 0.015, 0.04, 0.012, 0.018]
SCRIPT = dict(zip(range(2025, 2036), PIS))


def test_pensions_historique_et_plateau_de_cohortes():
    """Inflation quelconque (déflation comprise) : l'écart de niveau vaut le produit
    des revalorisations écoulées, chacune à l'inflation N−1 ; il cesse de croître après
    RETRAITES_EROSION_PLATEAU_ANS revalorisations (renouvellement des cohortes), sans
    jamais se rembourser."""
    dep, masses = _trajectoire('retraites', {'indexation': 0.8}, SCRIPT)
    for annee in range(2026, 2036):
        attendu = -masses['retraites'][annee] * _ecart(0.2, SCRIPT, annee, RETRAITES_EROSION_PLATEAU_ANS)
        assert dep[annee] == pytest.approx(attendu, rel=1e-12, abs=1e-12), annee
    ratio = [dep[a] / masses['retraites'][a] for a in range(2026, 2036)]
    assert all(ratio[i + 1] <= ratio[i] + 1e-15 for i in range(9))
    fin_plateau = POLICY_START_YEAR + RETRAITES_EROSION_PLATEAU_ANS - 1
    assert ratio[-1] == pytest.approx(ratio[fin_plateau - 2026], rel=1e-12)


def test_pensions_l_ecart_constitue_ne_disparait_pas():
    """π = 2 % jusqu'en 2027 puis 0 : l'écart constitué subsiste ensuite, en part
    de la masse — revalorisations 2026 (taux légal effectif), 2027 et 2028 (les
    2 % de 2026 et 2027), rien au-delà."""
    from budget_simulator.constants import REVALORISATION_PENSIONS_2026 as r26
    script = {a: (0.02 if a <= 2027 else 0.0) for a in range(2025, 2036)}
    dep, masses = _trajectoire('retraites', {'indexation': 0.0}, script)
    for annee in range(2028, 2036):
        assert dep[annee] / masses['retraites'][annee] == pytest.approx(
            -(1 - (1 - r26) * 0.98 ** 2), rel=1e-12)


def test_prestations_alignees_masse_nominale_et_premiere_revalorisation_2026():
    """RED lot 2 : base 90 Md€ en euros 2025 et 2026 = 0 (un gel voté pour 2026 ne
    rapportait rien en 2026). Désormais même convention que les pensions : masse
    NOMINALE de la catégorie `minima_sociaux` de l'année (90 Md€ en 2025), première
    revalorisation en 2026 (à l'inflation 2025 réalisée), dix au plus."""
    from budget_simulator.constants import INFLATION_BASE
    dep, masses = _trajectoire('prestations_indexation', {'taux_indexation': 0.8}, SCRIPT)
    assert dep[2026] == pytest.approx(-masses['prestations'][2026] * 0.2 * INFLATION_BASE, rel=1e-12)
    for annee in range(2026, 2036):
        attendu = -masses['prestations'][annee] * _ecart(0.2, SCRIPT, annee, 10, 'prestations')
        assert dep[annee] == pytest.approx(attendu, rel=1e-12, abs=1e-12), annee
    assert masses['prestations'][2030] > 90.0   # masse nominale, plus des euros 2025


@pytest.mark.parametrize('annee', [POLICY_START_YEAR, POLICY_START_YEAR + 4, POLICY_START_YEAR + 9])
def test_pensions_symetrie_au_premier_ordre(annee):
    """±20 % autour de la pleine indexation : miroir EXACT la première année ; ensuite
    la composition des revalorisations écarte économie et surcoût de O((δπ)²) — un
    écart de NIVEAU composé n'est pas linéaire, ni d'un côté ni de l'autre."""
    eco, _ = _pension(0.8, annee, 0.02)
    sur, _ = _pension(1.2, annee, 0.02)
    if annee == POLICY_START_YEAR:
        assert sur == pytest.approx(-eco, rel=1e-12)
    else:
        n = min(annee - POLICY_START_YEAR + 1, RETRAITES_EROSION_PLATEAU_ANS)
        assert abs(sur + eco) <= abs(eco) * n * 0.2 * 0.02 * 1.01
        assert sur > 0 > eco


# ---------------------------------------------------------------------------
# Revalorisation à l'inflation N−1 (v0.6.7, réfutation des handlers, angle 3).
# La loi revalorise les pensions au 1er janvier, et les prestations au 1er avril,
# sur l'inflation PASSÉE ; c'est elle que l'OFCE chiffre (gel 2026 : 1,1 %,
# l'inflation 2025, 3,7 Md€) et sur elle qu'est calée la part indexée 0,86. Le
# moteur revalorisait à l'inflation de l'année COURANTE (π₂₀₂₆ = 1,33 %) : gel
# 2026 = 4,48 Md€, 21 % de trop sur l'ancrage même de la calibration.
# ---------------------------------------------------------------------------

def test_gel_des_pensions_2026_en_simulation_porte_la_revalorisation_legale():
    """RED : 4,48 Md€ (inflation 2026 du moteur), puis 3,70 (inflation 2025, 1,1 %,
    l'hypothèse de l'OFCE). La revalorisation du 1er janvier 2026 a eu lieu : 0,9 %
    (service-public.fr, circulaire Cnav 2025/29). Le gel 2026 vaut la masse indexée
    calée sur l'OFCE (336 Md€ = 3,7 / 1,1 %) × 0,9 % = 3,0 Md€ — la part indexée ne
    bouge pas, seul le taux évité change."""
    from budget_simulator.constants import REVALORISATION_PENSIONS_2026 as r26
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={'retraites': {'indexation': 0.0}}).simulate()
    gel_2026 = -rapport['measure_impacts_by_year'][1]['retraites']['depenses']
    assert r26 == 0.009
    assert gel_2026 == pytest.approx(3.7 * r26 / 0.011, rel=0.03)


def _ecart_n_moins_1(delta, script, annee, n_max, pi_2025):
    # pi_2025 : le taux de la revalorisation 2026 (un fait, jamais le script)
    """Revalorisation de l'année s à l'inflation de s − 1 ; celle de 2026 à
    l'inflation 2025 réalisée (constante INSEE du moteur, pas le script)."""
    f = 1.0
    for s in range(POLICY_START_YEAR, min(annee, POLICY_START_YEAR + n_max - 1) + 1):
        pi = pi_2025 if s == POLICY_START_YEAR else script[s - 1]
        f *= 1 - delta * max(pi, 0.0)
    return 1 - f


@pytest.mark.parametrize('levier, params, n_max, cle', [
    ('retraites', {'indexation': 0.8}, RETRAITES_EROSION_PLATEAU_ANS, 'retraites'),
    ('prestations_indexation', {'taux_indexation': 0.8}, 10, 'prestations'),
])
def test_revalorisation_a_l_inflation_de_l_annee_precedente(levier, params, n_max, cle):
    """Inflation scriptée quelconque (déflation comprise) : chaque revalorisation
    porte l'inflation de l'année PRÉCÉDENTE ; celle de 2026 est un fait,
    indépendant du script — le taux légal effectif pour les pensions, l'inflation
    2025 réalisée pour les prestations."""
    script = {**SCRIPT, 2025: 0.5}   # 2025 scripté absurde : jamais lu
    dep, masses = _trajectoire(levier, params, script)
    for annee in range(2026, 2036):
        attendu = -masses[cle][annee] * _ecart_n_moins_1(0.2, script, annee, n_max, _TAUX_2026[cle])
        assert dep[annee] == pytest.approx(attendu, rel=1e-12, abs=1e-12), annee
