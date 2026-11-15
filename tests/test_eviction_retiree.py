"""Croissance : l'éviction (« crowding-out ») est retirée (lot 1 des corrections d'équations).

Jusqu'à v0.8.1, ``calculate_growth`` ôtait à la croissance de l'année intensité × effort quand l'effort
net de t−1 était une EXPANSION et que la dette dépassait 100 % du PIB ; l'intensité allait de 0,002
(relance 100 % investissement productif) à 0,008 (0 %). Coefficients déclarés sans source dans
``constants.py`` ; aucun effet pour une consolidation. Arbitrage du mainteneur du 21/10/2026
(« option C ») : on ne garde, pour la dette, que le facteur ×0,95 sur les multiplicateurs au-delà
de 110 % du PIB (``FiscalMultipliers.adjustments['high_debt']``). La littérature lue (Huidrom et al.
2020 ; Ilzetzki, Mendoza & Végh 2013, qui scindent l'échantillon à 60 % de dette ; Nickel & Tudyka
2014) trouve un multiplicateur plus faible quand la dette est haute ; ses modèles sont linéaires dans
le signe du choc (Auerbach & Gorodnichenko 2017 préviennent que les coupes ne sont pas forcément
symétriques des hausses). Aucune étude lue ne réserve l'effet aux relances ni ne différencie
investissement et transferts de 1 à 4.

Ce que fait le ×0,95 restant, mesuré : dans tout le domaine publié (dix scénarios, deux modes, banc
de calibrage), la dette lue dépasse 110 % ; le facteur s'applique à tous les appels et il est absorbé
par la calibration des coefficients d'impact. Après le retrait de l'éviction, aucune réduction des
multiplicateurs liée au niveau de dette n'est donc modélisée dans le domaine publié : la dette agit
par la traînée sur le potentiel et par la prime de taux. Le facteur reste une marche à 110 %, inerte
dans ce domaine (dette de modèle déclarée) ; les deux derniers tests rougissent le jour où ce constat
devient faux.

Le recalage qui accompagnait l'éviction (coefficient d'impact des baisses d'impôts 0,63 au lieu de
0,615, pour compenser l'éviction d'une relance 100 % baisse d'impôts) tombe avec elle : baisse et
hausse reprennent le même coefficient (garde ``tests/test_symetrie_impots_v067.py``).

Contrat verrouillé ici : à impulsions données, la croissance ne dépend pas de l'effort net, quel que
soit son signe et la dette ; couper ou augmenter les transferts d'un point de PIB, dette au-delà de
100 % du PIB, a des effets de même ampleur ; plus aucun symbole de l'éviction dans le moteur.
Aucune donnée du dépôt parent n'est lue.
"""
import ast
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).resolve().parent.parent
EFFORTS = (-0.10, -0.03, -0.005, -1e-6, 0.02, 0.05)


def _croissance(effort, dette, part):
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    sim._last_impacts = {}
    etat = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': dette,
            'effort_budgetaire': effort, 'part_investissement': part,
            'unemployment': 0.075, 'deficit_ratio': -0.05, 'interest_rate': 0.03}
    return sim.calculate_growth(1, etat)


@pytest.mark.parametrize('dette', [0.9, 1.0 + 1e-9, 1.2, 1.6])
@pytest.mark.parametrize('part', [0.0, 0.5, 1.0])
def test_croissance_invariante_a_l_effort_net(dette, part):
    """À impulsions nulles, l'effort net de l'année précédente (relance ou consolidation, de −10 % à
    +5 % du PIB) ne change pas la croissance, au bit, quelle que soit la dette. v0.8.1 : une relance
    de 3 % du PIB à dette > 100 % ôtait 0,006 à 0,024 point selon sa composition."""
    reference = _croissance(0.0, dette, part)
    ecarts = {e: _croissance(e, dette, part) - reference for e in EFFORTS}
    assert all(d == 0.0 for d in ecarts.values()), ecarts


def _niveau_a_4_ans(signe):
    """Écart du PIB réel (%) 4 ans après le début d'une impulsion PERMANENTE de ±1 % du PIB sur les
    pensions (statu quo, dette au-delà de 100 % du PIB sur tout l'horizon)."""
    def run(x0):
        class _Impulsion(BudgetSimulatorV45):
            def apply_measures(self, year, sp, rv, gdp, inf, u):
                sp, rv, imp = super().apply_measures(year, sp, rv, gdp, inf, u)
                if year - self.annee_base >= 1 and x0:
                    x = x0 * gdp
                    imp = dict(imp)
                    imp['retraites'] = {'depenses': x, 'recettes': 0.0}
                    sp += x
                return sp, rv, imp
        return _Impulsion(periods=10, mesures={}).simulate()
    (df0, d0, _), (_, d1, _) = run(0.0), run(0.01 * signe)
    assert (df0['Dette/PIB %'] > 100).all()   # le domaine de l'ancienne éviction
    y0, y1 = d0['PIB_Réel_Base2025'], d1['PIB_Réel_Base2025']
    return (y1[5] / y0[5] - 1) * 100


@pytest.fixture(scope='module')
def pleine_precision():
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    yield
    mp.undo()


def test_coupe_et_hausse_de_transferts_de_meme_ampleur_a_dette_elevee(pleine_precision):
    """Même instrument, même effet dans les deux sens, à 1 % près (Gechert 2015 classe par
    instrument). v0.8.1 : la coupe coûtait 4 % de plus que la hausse ne rapportait (l'éviction ne
    frappait que la hausse)."""
    hausse, coupe = _niveau_a_4_ans(+1), _niveau_a_4_ans(-1)
    assert hausse > 0 > coupe
    assert abs(coupe) / hausse == pytest.approx(1.0, abs=0.01), (hausse, coupe)


def _identifiants(arbre):
    for n in ast.walk(arbre):
        if isinstance(n, ast.Name):
            yield n.id
        elif isinstance(n, ast.Attribute):
            yield n.attr
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            yield n.name
        elif isinstance(n, ast.arg):
            yield n.arg
        elif isinstance(n, ast.alias):
            yield n.asname or n.name
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.isidentifier():
            yield n.value   # clés de dictionnaire d'état ('part_investissement', …)


def test_aucun_symbole_de_l_eviction_dans_le_moteur():
    """Ni fonction, ni constante, ni clé d'état, ni attribut : l'éviction et sa plomberie (part
    d'investissement de l'expansion, effort net lu par la croissance) ne peuvent revenir qu'en
    réécrivant ce test."""
    interdits = ('eviction', 'crowding', 'part_investissement', 'budget_effort_prev')
    fichiers = [RACINE / 'api.py', *sorted((RACINE / 'budget_simulator').rglob('*.py'))]
    trouves = sorted({(str(f.relative_to(RACINE)), i) for f in fichiers
                      for i in _identifiants(ast.parse(f.read_text(encoding='utf-8')))
                      if any(m in i.lower() for m in interdits)})
    assert not trouves, trouves
    assert not [n for n in dir(constants) if n.startswith('EVICTION')]


def test_l_etat_de_croissance_ne_porte_plus_ni_effort_ni_composition():
    """Plomberie : l'effort net et la part d'investissement de l'expansion n'avaient plus que
    l'éviction pour lecteur dans ``calculate_growth`` ; ils ne lui sont plus transmis. L'effort de
    l'année reste calculé pour la prime de taux et la colonne publiée."""
    sim = BudgetSimulatorV45(periods=4, mesures={'education': {'budget': 80}})
    origine, cles = sim.calculate_growth, set()

    def espion(year, etat):
        cles.update(etat)
        return origine(year, etat)
    sim.calculate_growth = espion
    df, detail, _ = sim.simulate()
    assert cles and not cles & {'effort_budgetaire', 'part_investissement'}, sorted(cles)
    assert (detail['Effort_Budgétaire %'].iloc[1:] != 0).any()


# --- Le facteur ×0,95 « dette élevée » est inerte dans le domaine publié (constat déclaré) ---------

SEUIL_DETTE_ELEVEE = 1.10   # FiscalMultipliers.get_multiplier : ``debt_ratio > 1.10``


def _dettes_lues(simulation):
    """Dette lue par chaque appel de ``FiscalMultipliers.get_multiplier`` pendant ``simulation()``."""
    from unittest.mock import patch
    from budget_simulator.simulator import FiscalMultipliers
    lues, origine = [], FiscalMultipliers.get_multiplier

    def espion(self, effort_type, composition, economic_state, year, measure_id=None):
        lues.append(economic_state.get('debt_ratio', 0.0))
        return origine(self, effort_type, composition, economic_state, year, measure_id)
    with patch.object(FiscalMultipliers, 'get_multiplier', espion):
        simulation()
    return lues


def test_le_seuil_du_facteur_dette_elevee_est_celui_du_code():
    import inspect
    from budget_simulator.simulator import FiscalMultipliers
    assert "debt_ratio', 0) > 1.10" in inspect.getsource(FiscalMultipliers.get_multiplier)


def test_banc_de_calibrage_toujours_au_dessus_du_seuil_dette_elevee():
    """Les coefficients d'impact sont calés sur le banc de ``test_multiplicateurs_centraux_v067.py`` :
    s'il lit une dette au-dessus de 110 % à chaque appel, le ×0,95 est absorbé dans les coefficients.
    Rougit le jour où ce n'est plus vrai (le texte qui le dit inerte deviendrait faux)."""
    from test_multiplicateurs_centraux_v067 import FAMILLES, _simuler as banc
    for famille in FAMILLES:
        lues = _dettes_lues(lambda: banc(famille))
        assert lues and min(lues) > SEUIL_DETTE_ELEVEE, (famille, min(lues, default=None))


def test_domaine_publie_toujours_au_dessus_du_seuil_dette_elevee():
    """Dix scénarios publiés, mode historique et mode cadre 2028 : chaque appel lit une dette au-dessus
    de 110 % (mesuré : 115,5 % au moins, 119 % en mode cadre). Le jour où un scénario publié lit une
    dette sous ce seuil, le facteur cesse d'être inerte et les textes qui le disent
    (``engine/growth.py``, ``constants.py``, METHODOLOGIE, CHANGELOG) deviennent faux : ce test rougit.

    Garde privée par nature : elle porte sur les scénarios publiés, que le dépôt du moteur ne contient
    pas ; elle est sautée sans ``scenarios.json``, donc en CI publique. La garde du banc de calibrage
    (test précédent), condition de l'absorption du facteur par les coefficients, tourne, elle, en
    public."""
    import os
    import sys
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
    from run_scenarios_full import PROFILS, SCENARIOS, pour_le_mode
    trop_bas = {}
    for sid, mesures in SCENARIOS.items():
        for mode, simulation in (
                ('historique', lambda: BudgetSimulatorV45(periods=10, mesures=pour_le_mode(mesures)).simulate()),
                ('cadre_2028', lambda: BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=2028,
                                                          profils=PROFILS.get(sid) or None).simulate())):
            lues = _dettes_lues(simulation)
            if not lues or min(lues) <= SEUIL_DETTE_ELEVEE:
                trop_bas[(sid, mode)] = min(lues, default=None)
    assert not trop_bas, trop_bas
