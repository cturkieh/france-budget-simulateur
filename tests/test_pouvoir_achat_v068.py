"""v0.6.8 — défauts PROUVÉS de l'indice de pouvoir d'achat v0.6.7 (tests RED).

Diagnostic : docs/plans/v068-pouvoir-achat.md (dépôt parent). Chaque test
mesure la part MICRO effective de la variation annuelle de l'indice
(variation − croissance réelle), capturée à l'entrée de la borne
`_borner_variation`, et la confronte à une identité comptable : un levier
ne peut pas changer le revenu des ménages de plus que les euros qu'il
déplace, rapportés au RDB.

RDB_PLANCHER_MD_EUR : borne BASSE volontaire du RDB des ménages (INSEE,
comptes nationaux : ~1 700 Md€ en 2024) ; une borne basse rend le test
indulgent — un levier qui échoue ici échoue a fortiori au vrai RDB.
"""
import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

RDB_PLANCHER_MD_EUR = 1600.0


def _cls():
    return next(c for c in vars(orch).values()
                if isinstance(c, type) and hasattr(c, 'apply_measures'))


@pytest.fixture
def run(monkeypatch):
    """mesures → (années, micro effectif/an, émissions/an, Δbudget/an)."""
    cls = _cls()
    orig_am, orig_bv = cls.apply_measures, orch._borner_variation
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)

    def go(mesures, periods=10):
        rec = {'var': [], 'em': {}, 'bud': {}}

        def am(self, year, *a, **k):
            r = orig_am(self, year, *a, **k)
            imp = [d for d in r[2].values() if isinstance(d, dict)]
            rec['em'][year] = sum(d.get('pouvoir_achat', 0.0) for d in imp)
            rec['bud'][year] = sum(d.get('recettes', 0.0) - d.get('depenses', 0.0) for d in imp)
            return r

        def bv(v, cap):
            if cap == orch.PA_VARIATION_ANNUELLE_MAX:
                rec['var'].append(v)
            return orig_bv(v, cap)

        monkeypatch.setattr(cls, 'apply_measures', am)
        monkeypatch.setattr(orch, '_borner_variation', bv)
        df = BudgetSimulatorV45(periods=periods, mesures=mesures).simulate()[0]
        col = next(c for c in df.columns if 'roissance' in c)
        g = [float(x) / 100 for x in df[col]]
        ys = [int(y) for y in df['Année']]
        micro = {y: rec['var'][i - 1] - g[i] for i, y in enumerate(ys) if i > 0}
        return ys, micro, rec['em'], rec['bud']
    return go


def test_tva_taux_normal_repercussion_sourcee(run):
    """+1 pt de TVA : le PA doit baisser de τ × Δrecettes / RDB, τ ∈ [0,6 ; 1]
    (répercussion des hausses, Benzarti et al. 2020). v0.6.7 : −0,2 %/pt fixe."""
    ys, micro, _, bud = run({'tva_rate': {'taux': 0.21}})
    y0 = ys[1]
    tau = -micro[y0] / (bud[y0] / RDB_PLANCHER_MD_EUR)
    assert 0.6 <= tau <= 1.0, f"répercussion implicite τ = {tau:.2f}"


def _standalone(nom):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent / 'snapshots'))
    from coverage_scenarios import build_standalone_scenarios
    return build_standalone_scenarios()[nom]


@pytest.mark.parametrize('nom', ['impots_production', 'impot_revenu',
                                 'cotisations_salariales', 'csg', 'tva_energie',
                                 'point_indice'])
def test_aucun_levier_ne_transmet_plus_que_ses_euros(run, nom):
    """|ΔPA micro| ≤ |Δ euros du levier| / RDB (transmission ≤ 100 %)."""
    mesures = ({'fonction_publique': {'point_indice': 3.0}} if nom == 'point_indice'
               else _standalone(nom))
    ys, micro, em, bud = run(mesures)
    y0 = next(y for y in ys[1:] if abs(em.get(y, 0.0)) > 1e-9)
    borne = abs(bud[y0]) / RDB_PLANCHER_MD_EUR
    assert abs(micro[y0]) <= borne * 1.001, (
        f"PA micro {micro[y0]:+.4%} > borne comptable {borne:.4%} "
        f"(Δ = {bud[y0]:+.1f} Md€, transmission {abs(micro[y0]) / borne:.0%})")


def test_un_niveau_permanent_ne_compose_pas(run):
    """Rabot de 7,5 % : une fois le montant stabilisé, la part micro de la
    VARIATION annuelle doit être nulle (effet de niveau, pas de croissance)."""
    ys, micro, _, bud = run({'rabot_uniforme': {'taux_reduction': 0.075}}, periods=10)
    stables = [y for i, y in enumerate(ys[2:], 2)
               if abs(bud[y] - bud[ys[i - 1]]) < 0.02 * abs(bud[y])]
    assert stables, 'montant jamais stabilisé : test sans objet'
    cumul = sum(micro[y] for y in stables)
    assert abs(cumul) < 1e-4, f"{len(stables)} années stables, micro cumulé {cumul:+.2%}"


def test_pas_d_attenuation_calendaire(run):
    """Un effet de niveau émis en 2027+ doit compter en entier (v0.6.7 :
    × 0,5 selon l'ANNÉE CALENDAIRE, pas selon l'âge de la mesure)."""
    ys, micro, em, _ = run({'fonction_publique': {'effectifs': 100000.0}})
    tardives = [y for y in ys[2:] if abs(em.get(y, 0.0)) > 1e-9]
    assert tardives, 'aucune émission après 2026 : test sans objet'
    ratio = sum(micro[y] for y in tardives) / sum(em[y] for y in tardives)
    assert ratio == pytest.approx(1.0, abs=0.02), f"part retenue {ratio:.2f}"
