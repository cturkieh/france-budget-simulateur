"""Indice de pouvoir d'achat — fin du double retranchement de l'inflation (v0.6.7,
lot 3E — audit Codex 10/2026, bloc C constat 4, arbitrage de Cyril n° 4, temps 1).

v0.6.6 : ``pa_macro = growth − inflation`` puis ``+ 0,54 × inflation``. Or
``growth`` est la croissance RÉELLE (``gdp_real *= 1 + growth``, le nominal
portant le déflateur) : l'inflation était retranchée une seconde fois, en partie
compensée par une « protection d'indexation » de 54 % — net g − 0,46 π.

Formule exacte servie depuis (aucune autre composante) :
    PA_t = PA_{t−1} × (1 + borne(g_t + micro_t))
    micro_t = Σ_mesures impacts['pouvoir_achat'] × (1 en 2026, 0,5 ensuite)
    borne = ±PA_VARIATION_ANNUELLE_MAX, PA_2025 = 100
Indice SYNTHÉTIQUE : croissance réelle du PIB agrégé (pas par tête, pas le RDB)
plus les effets forfaitaires des mesures — non comparable au RDB réel par UC de
l'INSEE. La refonte en RDB réel est la v0.6.8.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45


def _pleine_precision(mesures, monkeypatch):
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    df, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return df.set_index('Année'), rapport


def test_statu_quo_l_indice_suit_la_croissance_reelle(monkeypatch):
    """RED v0.6.6 : l'indice valait Π (1 + g − 0,46 π) — l'inflation, déjà hors de
    la croissance réelle, en était retirée une seconde fois."""
    df, _ = _pleine_precision({}, monkeypatch)
    assert df.loc[2025, "Pouvoir d'Achat"] == 100.0
    for an in range(2026, 2036):
        attendu = df.loc[an - 1, "Pouvoir d'Achat"] * (1 + df.loc[an, 'Croissance %'] / 100)
        assert df.loc[an, "Pouvoir d'Achat"] == pytest.approx(attendu, rel=1e-13), an


def test_l_inflation_n_entre_plus_dans_l_indice_macro(monkeypatch):
    """À croissance réelle identique, deux inflations différentes donnent le même
    indice : le déflateur ne frappe le pouvoir d'achat qu'à travers la croissance
    réelle (et les effets micro des mesures d'indexation)."""
    class _Inflation(BudgetSimulatorV45):
        pi = 0.0

        def calculate_inflation(self, year, economic_state):
            return self.pi

    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    series = []
    for pi in (0.005, 0.03):
        cls = type('_I', (_Inflation,), {'pi': pi})
        df, _, _ = cls(periods=10, mesures={}).simulate()
        g = list(df['Croissance %'])
        pa = list(df["Pouvoir d'Achat"])
        series.append([p / pa_prec / (1 + gr / 100) for p, pa_prec, gr in zip(pa[1:], pa[:-1], g[1:])])
    for a, b in zip(*series):
        assert a == pytest.approx(1.0, abs=1e-13) and b == pytest.approx(1.0, abs=1e-13)


def test_formule_exacte_avec_mesures(monkeypatch):
    """La formule publiée dans METHODOLOGIE, rejouée sur un programme : croissance
    réelle + effets micro (pleins en 2026, moitié ensuite)."""
    mesures = {'tva_rate': {'taux': 0.22}, 'retraites': {'indexation': 0.8}}
    df, rapport = _pleine_precision(mesures, monkeypatch)
    impacts = rapport['measure_impacts_by_year']
    for i, an in enumerate(range(2026, 2036), start=1):
        micro = sum(v['pouvoir_achat'] for k, v in impacts[i].items()
                    if k != 'Année' and isinstance(v, dict) and 'pouvoir_achat' in v)
        micro *= 1.0 if i == 1 else 0.5
        attendu = df.loc[an - 1, "Pouvoir d'Achat"] * (1 + df.loc[an, 'Croissance %'] / 100 + micro)
        assert df.loc[an, "Pouvoir d'Achat"] == pytest.approx(attendu, rel=1e-13), an
