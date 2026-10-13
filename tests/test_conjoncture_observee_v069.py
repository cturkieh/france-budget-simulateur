"""Conjoncture OBSERVÉE (v0.6.9) : le mécanisme, sans aucune valeur.

Deux tables par année calendaire, vides en v0.6.9 (``constants.py``) :
- ``CHOCS_DEMANDE_OBSERVES`` — points de croissance ajoutés à l'année, APRÈS
  ``calculate_growth`` et AVANT tous ses lecteurs (PIB, Okun, recettes, écart de
  production, hystérèse du potentiel). Choc de DEMANDE : il n'entre ni dans les
  impulsions budgétaires ni dans le potentiel comme choc d'offre ; la Phillips
  le voit l'année suivante, par l'écart de production, comme tout choc de demande.
- ``COIN_PRIX_CONSOMMATION`` — écart prix de la consommation − prix du PIB,
  cumulé en niveau : il ne touche QUE le prix de l'indice de pouvoir d'achat.

Les tables de test sont INJECTÉES (monkeypatch du module ``constants``), jamais
écrites dans ``constants.py``. Toute comparaison « avec / sans » injecte les DEUX
tables explicitement, et les tests sur les tables LIVRÉES sont écrits sous une
forme vraie tables vides ou remplies : le fichier reste valide quand v0.6.10 les
remplira (seul ``test_v069_tables_livrees_vides__a_retirer_en_v0610`` est daté).
Plan : ``docs/plans/v069-recalage-macro-2026.md`` du dépôt parent, § 4.1
(mécanisme) et § 7.1 (preuves).

Sans le ``scenarios.json`` du dépôt parent (CI du dépôt public seul), les tests
paramétrés tournent sur deux cas (statu quo, programme mixte) au lieu de douze.
"""
import ast
import functools
import importlib.util
import inspect
import logging
import re
import sys
import types
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.orchestrator as orch
from budget_simulator.engine import rdb as rdb_module
from budget_simulator.engine.growth import GrowthMixin
from budget_simulator.engine.unemployment import UnemploymentMixin
from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS  # noqa: E402  (10 scénarios publiés si présents)

PA = "Pouvoir d'Achat"
TABLES = C.ConjonctureObservee._fields   # source unique des noms de tables
CHOC = -0.0076                     # ordre de grandeur du plan (§ 4.2), valeur de TEST
COINS = ((2026, 0.005), (2028, 0.003))  # deux années : le cumul en niveau est testé
# Toujours disponibles, même sans le scenarios.json du dépôt parent (fork moteur
# seul) : un programme mixte (TVA → coin fiscal non nul, retraites, IR, SMIC).
PROGRAMME_MIXTE = {'tva_rate': {'taux': 0.22}, 'retraites': {'indexation': 0.8},
                   'impot_revenu': {'taux_superieur': 0.50}, 'smic': {'montant_brut': 1900}}
CAS = {'statu_quo': {}, 'programme_mixte': PROGRAMME_MIXTE, **SCENARIOS}
NOMS = sorted(CAS)
ABSENT = object()


class _Espion(BudgetSimulatorV45):
    """Enregistre, année par année, ce que PRODUIT ``calculate_growth`` et ce que
    LIT chacun de ses consommateurs — sans rien modifier."""

    def _reset_state(self):
        super()._reset_state()
        self.espion = {}
        self._espion_an = 0

    def _t(self):
        return self.espion.setdefault(self._espion_an, {})

    def calculate_growth(self, year, economic_state):
        self._espion_an = year
        g = super().calculate_growth(year, economic_state)
        self._t().update(g_brut=g, gap_lu_croissance=economic_state['output_gap'])
        return g

    def calculate_inflation(self, year, economic_state):
        pi = super().calculate_inflation(year, economic_state)
        self._t().update(gap_lu_phillips=economic_state['output_gap'],
                         ecart_chomage_lu_phillips=economic_state['unemployment_gap'],
                         inflation=pi)
        return pi

    def calculate_unemployment(self, growth, unemployment_prev, year, impacts=None):
        u = super().calculate_unemployment(growth, unemployment_prev, year, impacts)
        self._t().update(g_okun=growth, u=u)
        return u

    def calculate_revenues(self, gdp, growth, inflation, year):
        self._t().update(g_recettes=growth)
        return super().calculate_revenues(gdp, growth, inflation, year)

    def prochain_output_gap(self, gap, croissance, croissance_potentielle):
        nouveau = super().prochain_output_gap(gap, croissance, croissance_potentielle)
        self._t().update(gap_avant=gap, g_gap=croissance,
                         g_pot=croissance_potentielle, gap_apres=nouveau)
        return nouveau

    def update_potential_growth(self, growth, year):
        self._t().update(g_hysterese=growth)
        return super().update_potential_growth(growth, year)


CONSOMMATEURS = ('g_okun', 'g_recettes', 'g_gap', 'g_hysterese')


@functools.lru_cache(maxsize=None)
def _simuler(nom, chocs=None, coins=None):
    """Simulation PLEINE PRÉCISION (``round`` neutralisé) avec espions.

    ``chocs`` / ``coins`` : tuple de paires (année, valeur) INJECTÉ à la place de
    la table livrée ; ``None`` = table livrée telle quelle. Rend aussi le facteur
    de prix effectivement reçu par ``rdb_annee`` pour chaque année.
    LECTURE SEULE : le résultat est partagé entre tests."""
    facteurs_recus = {}
    vrai = orch.rdb_annee
    signature = inspect.signature(vrai)

    def espion_rdb(*args, **kwargs):
        lie = signature.bind(*args, **kwargs)
        lie.apply_defaults()
        facteurs_recus[lie.arguments['annees']] = lie.arguments.get(
            'facteur_prix_conjoncture', ABSENT)
        return vrai(*args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        mp.setattr(orch, 'rdb_annee', espion_rdb)
        if chocs is not None:
            mp.setattr(C, 'CHOCS_DEMANDE_OBSERVES', dict(chocs), raising=False)
        if coins is not None:
            mp.setattr(C, 'COIN_PRIX_CONSOMMATION', dict(coins), raising=False)
        sim = _Espion(periods=10, mesures=CAS[nom])
        df, det, rapport = sim.simulate()
    return sim, df.set_index('Année'), det.set_index('Année'), rapport, facteurs_recus


def _sans(nom):
    return _simuler(nom, chocs=(), coins=())


def _avec_choc(nom, annee):
    return _simuler(nom, chocs=((annee, CHOC),), coins=())


def _avec_coins(nom):
    return _simuler(nom, chocs=(), coins=COINS)


def _idx(annee):
    return annee - 2025


def _lignes(df, annees):
    return {a: df.loc[a].to_dict() for a in annees}


# ---------------------------------------------------------------------------
# 1. Les tables : source unique, vides en v0.6.9, garde d'import
# ---------------------------------------------------------------------------

def test_v069_tables_livrees_vides__a_retirer_en_v0610():
    """DATÉ — à RETIRER par la release qui remplit les tables (v0.6.10, GO
    séparé) : v0.6.9 livre la case, pas les valeurs. C'est le seul test du fichier
    qui exige des tables vides ; tous les autres valent tables vides ou remplies."""
    for nom in TABLES:
        assert getattr(C, nom) == {}, nom


def test_horizon_des_tables_egal_a_l_horizon_simule_et_servi():
    """Première année = première année SIMULÉE (2025 est un réalisé, pas un choc) ;
    dernière = horizon maximal servi par l'API (lu dans api.py, sans l'importer)."""
    periods_max = next(
        n.value.value for n in ast.parse(
            (Path(__file__).resolve().parent.parent / 'api.py').read_text(encoding='utf-8')).body
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == 'PERIODS_MAX' for t in n.targets))
    annee_base = BudgetSimulatorV45(periods=1).annee_base
    assert C.CONJONCTURE_PREMIERE_ANNEE == annee_base + 1
    assert C.CONJONCTURE_DERNIERE_ANNEE == annee_base + periods_max


@pytest.mark.parametrize('table, motif', [
    ({2025: -0.01}, 'horizon'),              # année de base : un réalisé, pas un choc
    ({2036: -0.01}, 'horizon'),
    ({2026.0: -0.01}, 'entière'),
    ({'2026': -0.01}, 'entière'),
    ({True: -0.01}, 'entière'),
    ({2026: float('nan')}, 'fini'),
    ({2026: float('inf')}, 'fini'),
    ({2026: -float('inf')}, 'fini'),
    ({2026: '-0.0076'}, 'nombre'),
    ({2026: None}, 'nombre'),
    ({2026: True}, 'nombre'),
    ({2026: -0.76}, 'unité'),                # « −0,76 point » écrit en fraction : ×100
    ({2026: 0.031}, 'domaine'),              # au-delà de ±0,03 : les filets mordent
    ({2026: -0.031}, 'domaine'),
    ([(2026, -0.01)], 'dict'),
])
@pytest.mark.parametrize('nom', TABLES)
def test_garde_refuse_une_table_invalide(nom, table, motif):
    with pytest.raises(ValueError, match=motif) as erreur:
        C.valider_table_conjoncture(nom, table)
    assert nom in str(erreur.value)


def test_garde_accepte_une_table_valide():
    assert C.valider_table_conjoncture('CHOCS_DEMANDE_OBSERVES', {}) is None
    assert C.valider_table_conjoncture(
        'CHOCS_DEMANDE_OBSERVES', {2026: -0.0076, 2035: 0.0, 2030: 0.03, 2031: -0.03}) is None
    assert C.CONJONCTURE_AMPLITUDE_MAX == 0.03


@pytest.mark.parametrize('nom', TABLES)
def test_garde_s_applique_a_l_import(nom):
    """La table DÉCLARÉE dans constants.py est validée à l'import : on rejoue le
    module avec une table fautive à la place de la sienne."""
    source = Path(C.__file__).read_text(encoding='utf-8')
    fautive, n = re.subn(rf'^({nom}: dict\[int, float\] = )\{{[^}}]*\}}',
                         r'\g<1>{2025: -0.01}', source, flags=re.M)
    assert n == 1, f"déclaration typée de {nom} introuvable (ou dupliquée) dans constants.py"
    module = types.ModuleType('constants_essai')
    module.__file__ = C.__file__
    with pytest.raises(ValueError, match=nom):
        exec(compile(fautive, C.__file__, 'exec'), module.__dict__)


@pytest.mark.parametrize('nom', TABLES)
def test_garde_s_applique_a_chaque_simulation(monkeypatch, nom):
    """Un dict reste mutable après la garde d'import : la simulation revalide la
    table qu'elle applique (zéro échec silencieux, NaN compris). Une table devenue
    invalide après l'import est un défaut du SERVEUR : RuntimeError, jamais
    ValueError (que l'API traduit en 422 « paramètres invalides » + WARNING)."""
    monkeypatch.setattr(C, nom, {2026: float('nan')}, raising=False)
    with pytest.raises(RuntimeError, match=nom) as erreur:
        BudgetSimulatorV45(periods=10, mesures={}).simulate()
    assert not isinstance(erreur.value, ValueError)
    assert isinstance(erreur.value.__cause__, ValueError)


class _Journal(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lignes = []

    def emit(self, record):
        self.lignes.append((record.levelno, record.getMessage()))


def test_table_invalide_apres_import_api_500_et_error(monkeypatch):
    """Contrat HTTP (reproduction du réfuteur v0.6.9) : 500 et une ERROR
    journalisée (remontée Sentry), pas un 422 « paramètres invalides » + WARNING
    qui ferait passer un bug serveur pour une faute du visiteur. api.py est
    chargé par chemin (depuis le dépôt parent, ``import api`` désigne l'API de
    prod) ; il appelle logging.basicConfig(force=True), d'où l'écoute directe de
    son logger."""
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location(
        'api_conjoncture_v069', Path(__file__).resolve().parent.parent / 'api.py')
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    journal = _Journal()
    api.logger.addHandler(journal)
    client = TestClient(api.app, raise_server_exceptions=False)
    monkeypatch.setattr(C, 'CHOCS_DEMANDE_OBSERVES', {2026: float('nan')}, raising=False)
    r = client.post('/simulate', json={'mesures': {}, 'periods': 10})
    assert r.status_code == 500, r.text
    assert any(niveau >= logging.ERROR and 'CHOCS_DEMANDE_OBSERVES' in message
               for niveau, message in journal.lignes), journal.lignes
    monkeypatch.setattr(C, 'CHOCS_DEMANDE_OBSERVES', {}, raising=False)
    assert client.post('/simulate', json={'mesures': {}, 'periods': 10}).status_code == 200


# ---------------------------------------------------------------------------
# 2. Tables LIVRÉES : appliquées telles quelles (vraies vides ou remplies ; à
#    tables vides, le mécanisme est un no-op — preuve chiffrée : golden master)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nom', NOMS)
def test_tables_livrees_appliquees_telles_quelles(nom):
    """Chaque lecteur de la croissance reçoit, au bit près, g_brut + le choc
    livré de son année (g_brut seul si l'année est absente), et le prix de la
    consommation reçoit Π (1 + coin livré) jusqu'à l'année (1 exactement sans coin)."""
    sim, *_, facteurs_recus = _simuler(nom)
    chocs, coins = C.CHOCS_DEMANDE_OBSERVES, C.COIN_PRIX_CONSOMMATION
    for idx, t in sim.espion.items():
        an = 2025 + idx
        attendu = t['g_brut'] + chocs[an] if an in chocs else t['g_brut']
        for cle in CONSOMMATEURS:
            assert t[cle] == attendu, (nom, an, cle)
    assert set(facteurs_recus) == set(range(0, 11))
    facteur = 1.0
    for idx in range(0, 11):
        if 2025 + idx in coins:
            facteur *= 1 + coins[2025 + idx]
        assert facteurs_recus[idx] == facteur and type(facteurs_recus[idx]) is float, idx


def _filets(sim):
    """Écrêtages des filets du modèle, année par année : croissance
    [−3,5 % ; +2,5 %], inflation [−0,3 % ; 3 %], chômage [CHOMAGE_CLIP_*]."""
    touches = set()
    for idx, t in sim.espion.items():
        if t['g_brut'] in (-0.035, 0.025):
            touches.add(('croissance', idx))
        if t['inflation'] in (-0.003, 0.030):
            touches.add(('inflation', idx))
        if t['u'] in (C.CHOMAGE_CLIP_MIN, C.CHOMAGE_CLIP_MAX):
            touches.add(('chomage', idx))
    return touches


@pytest.mark.parametrize('nom', NOMS)
def test_aucun_filet_supplementaire_sous_les_tables_livrees(nom):
    """Le choc observé n'est jamais écrêté, mais les filets du modèle qui le
    reçoit mordent en silence (valid reste vrai) : une valeur livrée ne doit faire
    mordre AUCUN filet de plus qu'à tables vides, dans aucun scénario (constants.py
    § CONJONCTURE OBSERVÉE : à −0,01 en 2026, le rebond 2027 d'un programme est
    déjà écrêté). Trivial à tables vides ; garde réelle dès qu'elles sont remplies."""
    assert _filets(_simuler(nom)[0]) <= _filets(_sans(nom)[0])


# ---------------------------------------------------------------------------
# 3. Choc de demande : exactement le choc, à son année, chez tous ses lecteurs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('annee', [2026, 2029])
@pytest.mark.parametrize('nom', NOMS)
def test_choc_ajoute_exactement_a_la_croissance_de_son_annee(nom, annee):
    sans, df_s, det_s, *_ = _sans(nom)
    avec, df_a, det_a, *_ = _avec_choc(nom, annee)
    t = _idx(annee)
    # Avant le choc : tout est identique au bit (aucune anticipation).
    avant = range(2025, annee)
    assert _lignes(df_a, avant) == _lignes(df_s, avant)
    assert _lignes(det_a, avant) == _lignes(det_s, avant)
    # L'année du choc : même croissance PRODUITE (état d'entrée identique), puis
    # TOUS les lecteurs reçoivent exactement g + choc — ni zéro, ni deux fois.
    assert avec.espion[t]['g_brut'] == sans.espion[t]['g_brut']
    for cle in CONSOMMATEURS:
        assert avec.espion[t][cle] == avec.espion[t]['g_brut'] + CHOC, cle
    assert df_a.loc[annee, 'Croissance %'] - df_s.loc[annee, 'Croissance %'] == pytest.approx(
        100 * CHOC, abs=1e-12)
    # Les autres années : aucun ajout direct (seulement les effets d'état).
    for an, e in avec.espion.items():
        if an != t:
            for cle in CONSOMMATEURS:
                assert e[cle] == e['g_brut'], (an, cle)


@pytest.mark.parametrize('nom', NOMS)
def test_choc_entre_dans_le_niveau_du_pib(nom):
    """PIB nominal de l'année du choc : même déflateur (la Phillips de t ne le voit
    pas), volume multiplié par (1 + g + choc) / (1 + g). Verrouille que le choc est
    appliqué AVANT la mise à jour du PIB (proposé par le réfuteur v0.6.9 : la
    mutation « choc après le PIB nominal » passait tous les autres tests)."""
    sans, df_s, det_s, *_ = _sans(nom)
    avec, df_a, det_a, *_ = _avec_choc(nom, 2026)
    g = sans.espion[1]['g_brut']
    assert df_a.loc[2025, 'PIB'] == df_s.loc[2025, 'PIB']
    assert det_a.loc[2026, 'Déflateur'] == det_s.loc[2026, 'Déflateur']
    assert df_a.loc[2026, 'PIB'] / df_s.loc[2026, 'PIB'] == pytest.approx(
        (1 + g + CHOC) / (1 + g), rel=1e-14)


def test_choc_hors_du_filet_n_est_pas_ecrete():
    """Un choc qui sort la croissance de [−3,5 % ; +2,5 %] reste appliqué en
    entier (donnée constatée). Amplitude admise par la garde (≤ 0,03) : un choc
    positif de +2 points porte le statu quo 2026 au-dessus de +2,5 %."""
    choc = 0.02
    avec, df_a, *_ = _simuler('statu_quo', chocs=((2026, choc),), coins=())
    t = avec.espion[1]
    assert t['g_brut'] + choc > 0.025                 # garde : le filet mordrait
    for cle in CONSOMMATEURS:
        assert t[cle] == t['g_brut'] + choc, cle
    assert df_a.loc[2026, 'Croissance %'] == pytest.approx(100 * (t['g_brut'] + choc), abs=1e-12)


@pytest.mark.parametrize('nom', NOMS)
def test_choc_traverse_ecart_de_production_okun_et_phillips(nom):
    """Calcul à la main, année du choc (2026) et suivante, pour chaque scénario :
    - écart de production en NIVEAU : Δgap = (1 + gap_{t−1}) × choc / (1 + g*) ;
    - Okun puis convergence NAIRU : Δu = 0,94 × okun × choc ;
    - Phillips : rien la même année (elle lit l'écart de t−1), l'écart choqué
      l'année suivante ; le rappel de t+1 lit lui aussi l'écart choqué."""
    sans, *_ = _sans(nom)
    avec, *_ = _avec_choc(nom, 2026)
    s, a = sans.espion[1], avec.espion[1]
    assert (a['gap_avant'], a['g_pot']) == (s['gap_avant'], s['g_pot'])
    assert a['gap_apres'] - s['gap_apres'] == pytest.approx(
        (1 + s['gap_avant']) * CHOC / (1 + s['g_pot']), abs=1e-15)
    assert a['u'] - s['u'] == pytest.approx(0.94 * avec.economic_coeffs['okun'] * CHOC, abs=1e-15)
    assert a['inflation'] == s['inflation']
    assert a['gap_lu_phillips'] == s['gap_lu_phillips']
    suivante = avec.espion[2]
    assert suivante['gap_lu_phillips'] == a['gap_apres']
    assert suivante['gap_lu_croissance'] == a['gap_apres']
    assert suivante['ecart_chomage_lu_phillips'] == a['u'] - avec.base_params['chomage_nairu']
    assert suivante['inflation'] != sans.espion[2]['inflation']


def test_choc_statu_quo_rejoue_a_la_main_jusqu_a_l_annee_suivante():
    """Au statu quo (ni mesure, ni impulsion, ni régime actif) la propagation se
    rejoue entièrement : Phillips de t+1 = (1 − ρ) × κ × Δgap, croissance de t+1 =
    Δg* (traînée de dette) − λ × Δgap + w_u × Δu. Aucune impulsion n'est créée."""
    from budget_simulator.constants import OUTPUT_GAP_RAPPEL, PHILLIPS_PENTE_MT
    sans, _, det_s, *_ = _sans('statu_quo')
    avec, _, det_a, *_ = _avec_choc('statu_quo', 2026)
    d_gap = avec.espion[1]['gap_apres'] - sans.espion[1]['gap_apres']
    d_u = avec.espion[1]['u'] - sans.espion[1]['u']
    # Garde intégrée : sans choc appliqué, le rejeu vaudrait 0 = 0.
    assert d_gap < -0.007 and d_u > 0.002
    rho = avec.economic_coeffs['inflation_inertia']
    assert avec.espion[2]['inflation'] - sans.espion[2]['inflation'] == pytest.approx(
        (1 - rho) * PHILLIPS_PENTE_MT * d_gap, abs=1e-15)
    d_g_pot = avec.espion[2]['g_pot'] - sans.espion[2]['g_pot']
    assert avec.espion[2]['g_brut'] - sans.espion[2]['g_brut'] == pytest.approx(
        d_g_pot - OUTPUT_GAP_RAPPEL * d_gap
        + avec.economic_coeffs['chomage_gap_weight'] * d_u, abs=1e-15)
    assert avec._fiscal_impulses == {} == sans._fiscal_impulses
    assert (det_a['Effort_Budgétaire %'] == 0).all()


@pytest.mark.parametrize('nom', NOMS)
def test_le_choc_n_est_pas_une_impulsion_budgetaire(nom):
    """Les impulsions jusqu'à l'année du choc sont identiques au bit, et aucune
    clé d'impulsion n'apparaît pour un autre levier que les mesures du scénario
    (le choc n'est ni stocké ni multiplié). Après, elles ne bougent que par le
    PIB nominal, dénominateur de l'effort — un effet d'état, pas une impulsion."""
    sans, *_ = _sans(nom)
    avec, *_ = _avec_choc(nom, 2026)
    # Garde intégrée : le choc est bien appliqué (sinon l'égalité serait triviale).
    assert avec.espion[1]['g_gap'] == avec.espion[1]['g_brut'] + CHOC
    jusqu_au_choc = {k: v for k, v in avec._fiscal_impulses.items() if k[0] <= 1}
    assert jusqu_au_choc == {k: v for k, v in sans._fiscal_impulses.items() if k[0] <= 1}
    assert {k[1] for k in avec._fiscal_impulses} <= set(CAS[nom])


# ---------------------------------------------------------------------------
# 4. Coin de prix : seul le pouvoir d'achat bouge, exactement de 1 / Π(1 + coin)
# ---------------------------------------------------------------------------

def _facteur(annee):
    f = 1.0
    for an, coin in COINS:
        if an <= annee:
            f *= 1 + coin
    return f


@pytest.mark.parametrize('nom', NOMS)
def test_coin_ne_touche_que_le_pouvoir_d_achat(nom):
    sans, df_s, det_s, _, recus_s = _sans(nom)
    avec, df_a, det_a, _, recus_a = _avec_coins(nom)
    autres = [c for c in df_s.columns if c != PA]
    assert len(autres) >= 7
    assert df_a[autres].to_dict() == df_s[autres].to_dict()
    autres_det = [c for c in det_s.columns if c != 'Prix_Consommation']
    assert det_a[autres_det].to_dict() == det_s[autres_det].to_dict()
    for an in range(2025, 2036):
        f = _facteur(an)
        assert recus_a[_idx(an)] == pytest.approx(f, rel=1e-15) and recus_s[_idx(an)] == 1.0
        assert det_a.loc[an, 'Prix_Consommation'] / det_s.loc[an, 'Prix_Consommation'] == pytest.approx(
            f, rel=1e-14), an
        assert df_a.loc[an, PA] / df_s.loc[an, PA] == pytest.approx(1 / f, rel=1e-12), an
        trace_a, trace_s = avec._rdb_trace[an], sans._rdb_trace[an]
        assert (trace_a.rdb_base, trace_a.effet_mesures, trace_a.coin_indirect) == (
            trace_s.rdb_base, trace_s.effet_mesures, trace_s.coin_indirect)


def test_coin_cumule_ne_persiste_pas_entre_deux_simulations(monkeypatch):
    """Le facteur cumulé repart de 1 à chaque simulation (pas d'état reporté)."""
    import budget_simulator.engine.orchestrator as o
    monkeypatch.setattr(o, 'round', lambda x, n=None: float(x), raising=False)
    monkeypatch.setattr(C, 'CHOCS_DEMANDE_OBSERVES', {}, raising=False)
    monkeypatch.setattr(C, 'COIN_PRIX_CONSOMMATION', dict(COINS), raising=False)
    sim = BudgetSimulatorV45(periods=10, mesures={})
    premier = list(sim.simulate()[0][PA])
    assert premier != list(_sans('statu_quo')[1][PA])  # garde : le coin agit
    assert list(sim.simulate()[0][PA]) == premier
    monkeypatch.setattr(C, 'COIN_PRIX_CONSOMMATION', {}, raising=False)
    assert list(sim.simulate()[0][PA]) == list(_sans('statu_quo')[1][PA])


def test_tables_figees_pendant_une_simulation(monkeypatch):
    """Une table modifiée PENDANT une simulation ne s'applique pas à celle-ci
    (copie au départ) : une simulation lit une seule version des tables."""
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)

    class _MutePendant(BudgetSimulatorV45):
        def calculate_growth(self, year, economic_state):
            if year == 1:
                C.CHOCS_DEMANDE_OBSERVES[2027] = -0.02
                C.COIN_PRIX_CONSOMMATION[2027] = 0.02
            return super().calculate_growth(year, economic_state)

    def tables():
        monkeypatch.setattr(C, 'CHOCS_DEMANDE_OBSERVES', {2026: CHOC}, raising=False)
        monkeypatch.setattr(C, 'COIN_PRIX_CONSOMMATION', {2026: 0.005}, raising=False)

    tables()
    mutee = _MutePendant(periods=10, mesures={}).simulate()[0]
    assert C.CHOCS_DEMANDE_OBSERVES[2027] == -0.02     # garde : la mutation a eu lieu
    applique_ensuite = BudgetSimulatorV45(periods=10, mesures={}).simulate()[0]
    tables()
    reference = BudgetSimulatorV45(periods=10, mesures={}).simulate()[0]
    assert mutee.equals(reference)
    assert not applique_ensuite.equals(reference)     # la simulation suivante la voit


# ---------------------------------------------------------------------------
# 5. Fonctions pures intactes, un seul point d'application
# ---------------------------------------------------------------------------

def test_rdb_annee_coin_par_defaut_neutre_et_multiplicatif():
    impacts = {'m': {'menages': {'prestations': 3.0, 'prelevements_directs': 1.0,
                                 'remunerations_publiques': 0.0, 'salaires_prives': 0.5,
                                 'prelevements_indirects': 4.0}}}
    args = (impacts, 3100.0, 2991.0, 1.02, 1.03, 1)
    defaut = rdb_module.rdb_annee(*args)
    assert rdb_module.rdb_annee(*args, facteur_prix_conjoncture=1.0) == defaut
    choque = rdb_module.rdb_annee(*args, facteur_prix_conjoncture=1.005)
    assert choque.prix == pytest.approx(defaut.prix * 1.005, rel=1e-15)
    assert choque.indice == pytest.approx(defaut.indice / 1.005, rel=1e-14)
    assert (choque.rdb_base, choque.rdb_prive, choque.effet_mesures, choque.coin_indirect) == (
        defaut.rdb_base, defaut.rdb_prive, defaut.effet_mesures, defaut.coin_indirect)


def test_fonctions_pures_inchangees():
    """Le choc s'applique dans l'orchestrateur : calculate_growth et
    calculate_unemployment gardent leur signature (et leurs tests unitaires)."""
    assert list(inspect.signature(GrowthMixin.calculate_growth).parameters) == [
        'self', 'year', 'economic_state']
    assert list(inspect.signature(UnemploymentMixin.calculate_unemployment).parameters) == [
        'self', 'growth', 'unemployment_prev', 'year', 'impacts']
    assert inspect.signature(rdb_module.rdb_annee).parameters[
        'facteur_prix_conjoncture'].default == 1.0


def _references_de_code(chemin):
    """Références EXÉCUTABLES aux tables (nom, attribut, ou chaîne exacte passée à
    getattr) — les commentaires et la documentation qui les citent n'en sont pas."""
    for noeud in ast.walk(ast.parse(chemin.read_text(encoding='utf-8'))):
        if (isinstance(noeud, ast.Name) and noeud.id in TABLES
                or isinstance(noeud, ast.Attribute) and noeud.attr in TABLES
                or isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and noeud.value in TABLES):
            yield noeud


def test_un_seul_point_d_application():
    """Anti-double comptage par construction : hors de constants.py, seul
    l'orchestrateur lit les tables."""
    paquet = Path(C.__file__).parent
    lecteurs = sorted(str(p.relative_to(paquet)) for p in paquet.rglob('*.py')
                      if p.name != 'constants.py' and any(_references_de_code(p)))
    assert lecteurs == ['engine/orchestrator.py']
