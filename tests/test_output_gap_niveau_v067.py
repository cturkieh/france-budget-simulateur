"""Output gap en NIVEAU, rappel vers le potentiel, traînée de dette en OFFRE
(v0.6.7, B3 — audit Codex 10/2026, bloc A constat 3 ; arbitrage de Cyril).

Jusqu'en v0.6.6 : ``gap = 0,8·gap + 0,2·(g − g*)`` — une moyenne mobile de
l'écart de CROISSANCE, qui efface chaque année 20 % d'un écart de niveau réel.
METHODOLOGIE justifiait ce choix par « au statu quo, croissance = potentielle »,
prémisse fausse : au statu quo la croissance restait sous le potentiel (traînée de
dette + bruit tiré, ce dernier retiré en v0.6.7), de −0,13 pt en 2026 à −0,59 pt
en 2035.

Définition retenue : gap_t = (PIB réel − PIB potentiel) / PIB potentiel, soit
    (1 + gap_t) = (1 + gap_{t−1}) × (1 + g_t) / (1 + g*_t)
avec g* = croissance potentielle TOTALE (lecteur unique, bonus d'offre et
traînée de dette inclus), et dans l'équation de croissance un rappel
−OUTPUT_GAP_RAPPEL × gap_{t−1} (persistance 0,8, forme FPAS/QPM du FMI).

Identité pure seule (variante écartée, rejouée au centième de l'audit) : statu
quo gap 2034 −2,68, dette 2035 164,17, récession permanente dès 2033 et sortie
du corridor mission (PIB nominal 2030 −0,661 % pour ±0,6 %) — parce que la
traînée de dette (−2,0 pts cumulés) et le bruit (−0,56) s'accumulaient dans un
écart que rien ne refermait.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import OUTPUT_GAP_INITIAL


@pytest.fixture(scope='module')
def statu_quo(request):
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        df, detail, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    finally:
        mp.undo()
    return df.set_index('Année'), detail.set_index('Année')


def test_le_gap_est_l_ecart_de_niveau_au_potentiel(statu_quo):
    df, detail = statu_quo
    gap = OUTPUT_GAP_INITIAL
    for an in range(2026, 2036):
        g = df.loc[an, 'Croissance %'] / 100
        g_pot = detail.loc[an, 'Croissance_Potentielle_Totale %'] / 100
        gap = (1 + gap) * (1 + g) / (1 + g_pot) - 1
        assert detail.loc[an, 'Output_Gap %'] / 100 == pytest.approx(gap, abs=1e-12), an


def test_statu_quo_ecart_de_croissance_egal_au_rappel(statu_quo):
    """Au statu quo, g − g* vaut EXACTEMENT le rappel (−0,2 × gap_{t−1}) : plus de
    traînée de dette dans l'écart (v0.6.6 : −0,13 à −0,32 pt/an), elle est dans
    g* ; plus de bruit tiré non plus (retiré en v0.6.7, recalage du corridor)."""
    df, detail = statu_quo
    from budget_simulator.constants import OUTPUT_GAP_RAPPEL
    for an in range(2026, 2036):
        ecart = (df.loc[an, 'Croissance %'] - detail.loc[an, 'Croissance_Potentielle_Totale %']) / 100
        attendu = -OUTPUT_GAP_RAPPEL * detail.loc[an - 1, 'Output_Gap %'] / 100
        assert ecart == pytest.approx(attendu, abs=1e-12), an


def test_la_trainee_de_dette_n_ouvre_ni_gap_ni_chomage(statu_quo):
    """Effet d'OFFRE : changer le coefficient de traînée déplace le PIB et le
    potentiel ensemble, ni l'output gap ni le chômage (Okun lit g − g*)."""
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        sim = BudgetSimulatorV45(periods=10, mesures={})
        sim.economic_coeffs['debt_drag'] = -0.010
        df2, d2, _ = sim.simulate()
    finally:
        mp.undo()
    df, detail = statu_quo
    assert list(d2['PIB_Réel_Base2025'])[-1] < detail['PIB_Réel_Base2025'].iloc[-1] * 0.99
    # Au second ordre près : l'identité de niveau divise par (1 + g*), qui porte
    # la traînée — 0,0004 pt de gap au plus (contre −2,0 pts cumulés en v0.6.6).
    for a, b in zip(d2['Output_Gap %'], detail['Output_Gap %']):
        assert a == pytest.approx(b, abs=2e-3)
    for a, b in zip(df2['Chômage %'], df['Chômage %']):
        assert a == pytest.approx(b, abs=2e-3)


def test_le_rappel_ramene_le_pib_vers_le_potentiel():
    """Un gap de −2 % ajoute exactement +0,4 pt à la croissance de l'année."""
    from budget_simulator.constants import OUTPUT_GAP_RAPPEL
    etat = dict(unemployment_gap=0.0, effort_budgetaire=0.0, part_depenses=0.5,
                debt_ratio=0.8, unemployment=0.075, deficit_ratio=-0.03, interest_rate=0.03)
    def g(gap):
        sim = BudgetSimulatorV45(periods=1)
        return sim.calculate_growth(1, dict(etat, output_gap=gap))
    assert g(-0.02) - g(0.0) == pytest.approx(OUTPUT_GAP_RAPPEL * 0.02, abs=1e-15)
    assert OUTPUT_GAP_RAPPEL == 0.2


def test_un_choc_de_demande_ne_se_dissout_pas_dans_la_definition():
    """Propriété de définition : à croissance égale au potentiel, le gap reste
    là où il est (il ne se referme que si la croissance dépasse le potentiel).
    La v0.6.6 le ramenait vers 0 de 20 % par an par simple récurrence."""
    sim = BudgetSimulatorV45(periods=1)
    assert sim.prochain_output_gap(-0.02, 0.011, 0.011) == pytest.approx(-0.02, abs=1e-15)
    assert sim.prochain_output_gap(-0.02, 0.031, 0.011) == pytest.approx(
        0.98 * 1.031 / 1.011 - 1, abs=1e-15)
