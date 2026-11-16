"""Calendrier de l'impulsion budgétaire (lot 6 des corrections d'équations).

Jusqu'au lot 6, une mesure n'agissait sur le PIB qu'à partir de l'année qui SUIT son premier
budget : la croissance de l'année était calculée avant les mesures de l'année et lisait
l'impulsion du budget précédent (« lag standard », pour casser la circularité mesures → macro →
flux → mesures, sans source). Effet nul la première année pour toutes les familles, dans les deux
modes, alors que les variantes publiées donnent toutes un effet l'année du choc (METHODOLOGIE,
« Calendrier de l'impulsion » : FMI, WEO d'octobre 2014, ch. 3, tableau 3.4 ; Mésange 2017,
p. 102 et 105 ; OFCE 2011, tableau 5 ; OFCE, policy brief n° 17, 2017, tableau 5).

Désormais le budget de l'année est évalué hors de son effet propre (le bloc « demande » tourne
une fois sans son impulsion, sur une copie de l'état), puis son impulsion agit dès son année,
âge 0 de son profil. Contrat verrouillé ici :

1. effet PLEIN l'année du premier budget, pour chaque famille (dépense courante en hausse et en
   baisse, transferts, investissement, impôts en hausse et en baisse, et les deux coefficients
   propres, SMIC et fraude fiscale) et dans les deux modes : l'impulsion est stockée à l'année du
   budget et la croissance de cette année s'écarte de la référence d'exactement
   −k × impulsion × profil(0) ;
2. impulsion EX ANTE : un montant fixe en euros est rapporté au PIB de l'année hors de son effet
   propre (celui de la référence la première année), pas au PIB final ;
3. l'évaluation hors effet propre ne laisse AUCUNE trace dans l'état d'instance, et les attributs
   qu'elle partage au lieu de les copier (``_ETAT_PARTAGE_HORS_EFFET_PROPRE``) ne sont pas
   modifiés (seul le jeu de déduplication des avertissements peut grandir) ;
4. ``simulate()`` passe toujours les niveaux du budget de l'année : le chemin par défaut de
   ``_stocker_impulsions`` (budget de ``_last_impacts``, bancs unitaires) n'est jamais emprunté.

Les niveaux à quatre ans par famille (banc de tests/test_multiplicateurs_centraux_v067.py) et le
miroir hausse/baisse (tests/test_symetrie_*.py) restent gardés là où ils l'étaient.
"""
import math
import types

import numpy as np
import pytest

from budget_simulator.engine import orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

S = BudgetSimulatorV45

# famille → (levier portant un flux synthétique, flux, signe) ; leviers rangés dans leur famille
# par les listes du moteur (INVESTMENT_CORE_MEASURES, TRANSFER_MEASURES,
# MESURES_MULTIPLICATEUR_NET), comme au banc des multiplicateurs ; la dépense courante sur un
# levier absent de toute liste et du droit en vigueur (banc de symétrie de la dépense courante).
FAMILLES = {
    'courante_hausse': ('depense_courante_synthetique', 'depenses', +1),
    'courante_baisse': ('depense_courante_synthetique', 'depenses', -1),
    'transferts_hausse': ('retraites', 'depenses', +1),
    'transferts_baisse': ('retraites', 'depenses', -1),
    'investissement_hausse': ('education', 'depenses', +1),
    'investissement_baisse': ('education', 'depenses', -1),
    'impots_hausse': ('tva_rate', 'recettes', +1),
    'impots_baisse': ('tva_rate', 'recettes', -1),
    'smic': ('smic', 'depenses', +1),
    'fraude_fiscale': ('fraude_fiscale', 'recettes', +1),
}
# mode → (annee_debut, premier budget de l'impulsion)
MODES = {'historique': (None, 2026), 'cadre_2028': (2028, 2028)}


def _banc(levier, flux, part, debut, montant_fixe=None):
    """Simulateur qui ajoute à l'impact de ``levier`` un flux permanent de ``part`` × PIB (ou d'un
    montant fixe en Md€) à partir du budget ``debut`` ; la trace des niveaux reçus par
    _stocker_impulsions est gardée."""

    class _Banc(S):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier and year >= debut:
                x = montant_fixe if montant_fixe is not None else part * gdp
                imp = dict(imp)
                bloc = dict(imp.get(levier) or {})
                bloc[flux] = float(bloc.get(flux, 0) or 0) + x
                bloc.setdefault('depenses', 0.0)
                bloc.setdefault('recettes', 0.0)
                imp[levier] = bloc
                if flux == 'depenses':
                    sp += x
                else:
                    rv += x
            return sp, rv, imp

    return _Banc


@pytest.fixture(scope='module')
def pleine_precision():
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    yield
    mp.undo()


def _simuler(cls, annee_debut, periods=6):
    sim = cls(periods=periods, mesures={}, annee_debut=annee_debut)
    df, annexes, _ = sim.simulate()
    return sim, df, annexes


@pytest.fixture(scope='module')
def references(pleine_precision):
    return {mode: _simuler(S, annee_debut) for mode, (annee_debut, _) in MODES.items()}


# --- 1. Effet plein l'année du premier budget --------------------------------------------------

def _effet_de_l_annee(sim, i):
    """Effet sur la croissance de l'année d'indice i des impulsions stockées À cette année (âge 0)."""
    return sum(-k * delta * profil[0] for cle, (delta, k, profil) in sim._fiscal_impulses.items()
               if cle[0] == i)


def _effort_stocke(sim, i, levier):
    return sum(delta for cle, (delta, _, _) in sim._fiscal_impulses.items()
               if cle[0] == i and cle[1] == levier)


@pytest.mark.parametrize('mode', list(MODES))
@pytest.mark.parametrize('famille', list(FAMILLES))
def test_effet_plein_l_annee_du_premier_budget(references, famille, mode):
    """L'année du premier budget, l'impulsion du levier est stockée À cette année (effort ex ante
    de ±1 point de PIB exactement, en plus de ce qu'y porte déjà le droit en vigueur en mode cadre)
    et la croissance de l'année s'écarte de la référence d'exactement la différence des effets
    d'âge 0, −k × impulsion × profil(0) : effet plein, ni nul, ni partiel. Rouge avant le lot 6 :
    aucune impulsion à l'année du budget, écart de croissance nul."""
    levier, flux, signe = FAMILLES[famille]
    annee_debut, debut = MODES[mode]
    sim, df, _ = _simuler(_banc(levier, flux, 0.01 * signe, debut), annee_debut)
    sim0, df0, _ = references[mode]
    i = debut - sim.annee_base
    effort = 0.01 * signe * (-1 if flux == 'depenses' else 1)
    assert _effort_stocke(sim, i, levier) - _effort_stocke(sim0, i, levier) == pytest.approx(
        effort, abs=1e-15), (famille, mode, sorted(c for c in sim._fiscal_impulses if c[0] == i))
    attendu = _effet_de_l_annee(sim, i) - _effet_de_l_annee(sim0, i)
    assert abs(attendu) > 5e-4, (famille, mode, attendu)
    ecart = (df['Croissance %'][i] - df0['Croissance %'][i]) / 100
    assert ecart == pytest.approx(attendu, rel=1e-9, abs=1e-14), (
        f'{famille}, {mode} : croissance {debut} {ecart:+.6%} contre −k × impulsion × profil(0) '
        f'= {attendu:+.6%}')


@pytest.mark.parametrize('mode', list(MODES))
def test_annee_d_avant_le_premier_budget_inchangee(references, mode):
    """L'impulsion n'agit pas AVANT son budget : l'année qui précède est identique au bit."""
    levier, flux, signe = FAMILLES['courante_hausse']
    annee_debut, debut = MODES[mode]
    sim, df, _ = _simuler(_banc(levier, flux, 0.01 * signe, debut), annee_debut)
    _, df0, _ = references[mode]
    i = debut - sim.annee_base
    assert df.iloc[:i].equals(df0.iloc[:i])
    assert df['Croissance %'][i] != df0['Croissance %'][i]


# --- 2. Impulsion ex ante -----------------------------------------------------------------------

def test_montant_fixe_rapporte_au_pib_hors_effet_propre(references):
    """Un flux fixe de 30 Md€ dès le budget 2026, mode historique, aucune autre mesure : l'année
    2026 de la simulation SANS son impulsion est la référence elle-même, donc l'effort vaut
    30 / PIB nominal 2026 de la référence. Le rapporter au PIB final (impulsion « ex post », celle
    d'un point fixe) donnerait une autre valeur : le test les distingue."""
    _, df0, annexes0 = references['historique']
    sim, df, annexes = _simuler(_banc('collectivites', 'depenses', None, 2026, montant_fixe=30.0), None)
    (delta, _, _), = [v for cle, v in sim._fiscal_impulses.items() if cle[0] == 1 and cle[1] == 'collectivites']
    pib_reference, pib_final = df0['PIB'][1], df['PIB'][1]
    assert abs(30.0 / pib_reference - 30.0 / pib_final) > 1e-7     # le test discrimine
    assert -delta == pytest.approx(30.0 / pib_reference, rel=1e-12)


# --- 3. Aucune trace de l'évaluation hors effet propre -----------------------------------------

def _empreinte(x, vus=None):
    """Empreinte structurelle canonique (flottants au bit, ensembles triés, objets par leurs
    attributs) : deux états égaux ont la même empreinte, quel que soit l'ordre d'insertion."""
    vus = set() if vus is None else vus
    if isinstance(x, (bool, int, str, bytes, type(None))):
        return x
    if isinstance(x, (float, np.floating)):
        return ('f', float(x).hex())
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.ndarray):
        return ('a', x.tobytes(), x.shape)
    if id(x) in vus:
        return ('cycle', type(x).__name__)
    vus = vus | {id(x)}
    if isinstance(x, dict):
        return ('d', sorted(((repr(k), _empreinte(v, vus)) for k, v in x.items()), key=lambda p: p[0]))
    if isinstance(x, (list, tuple)):
        return (type(x).__name__, [_empreinte(v, vus) for v in x])
    if isinstance(x, (set, frozenset)):
        return ('s', sorted(repr(_empreinte(v, vus)) for v in x))
    if isinstance(x, (types.FunctionType, types.MethodType, types.BuiltinFunctionType)):
        return ('fn', getattr(x, '__qualname__', repr(x)))
    if hasattr(x, '__dict__'):
        return ('o', type(x).__name__, _empreinte(vars(x), vus))
    return ('r', repr(x))


# Non comparés : handlers liés à l'instance (table de méthodes, figée) et interpréteur ASTEVAL
# (sa table de symboles est réécrite avant chaque formule, orchestrator._apply_formula).
NON_COMPARES = {'measure_handlers', 'aeval'}


def _etat(sim):
    return {k: _empreinte(v) for k, v in vars(sim).items() if k not in NON_COMPARES}


class _Espion(S):
    """Compare l'état d'instance avant et après chaque évaluation hors effet propre."""
    traces = []

    def _niveaux_hors_effet_propre(self, *args):
        avant = _etat(self)
        avertis = set(self._domain_clamp_warned)
        partages = {k: id(getattr(self, k)) for k in orch._ETAT_PARTAGE_HORS_EFFET_PROPRE}
        niveaux = super()._niveaux_hors_effet_propre(*args)
        apres = _etat(self)
        differents = sorted(k for k in set(avant) | set(apres)
                            if k != '_domain_clamp_warned' and avant.get(k) != apres.get(k))
        _Espion.traces.append((differents,
                               avertis <= self._domain_clamp_warned,
                               all(id(getattr(self, k)) == v for k, v in partages.items())))
        return niveaux


def _programmes_publics():
    """Mini-scénarios standalone (un levier dévié par scénario, tous les handlers), chacun dans son
    mode et en mode cadre 2028."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'snapshots'))
    from coverage_scenarios import annee_debut_mini, build_standalone_scenarios
    for nom, mesures in sorted(build_standalone_scenarios().items()):
        yield nom, mesures, annee_debut_mini(nom)
        if annee_debut_mini(nom) is None:
            yield nom, mesures, 2028


def test_l_evaluation_hors_effet_propre_ne_laisse_aucune_trace():
    """Sur les 42 mini-scénarios (tous les handlers), dans leur mode et en mode cadre 2028, chaque
    année : l'état d'instance après l'évaluation est celui d'avant (empreinte structurelle de tous
    les attributs), les attributs partagés sont les mêmes objets, non modifiés, et le jeu de
    déduplication des avertissements ne fait que grandir."""
    _Espion.traces = []
    n = 0
    for _, mesures, annee_debut in _programmes_publics():
        _Espion(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
        n += 1
    assert n >= 60 and len(_Espion.traces) == 10 * n
    fautes = [t for t in _Espion.traces if t[0] or not t[1] or not t[2]]
    assert not fautes, fautes[:3]


def _sorties_avec_et_sans_evaluation(mesures, annee_debut, preparer=None):
    """Sorties d'un simulateur qui jette le résultat de l'évaluation hors effet propre (niveaux du
    budget précédent à la place) et d'un simulateur qui ne la lance pas : deux simulations qui ne
    diffèrent QUE par l'exécution de l'évaluation."""
    from budget_simulator.engine.growth import niveaux_du_budget

    def niveaux_precedents(sim):
        return niveaux_du_budget(sim._last_impacts, sim.pib_nominal,
                                 sim.multipliers.MESURES_MULTIPLICATEUR_NET)

    class _Sans(S):
        def _niveaux_hors_effet_propre(self, *args):
            return niveaux_precedents(self)

    class _AvecPuisJete(S):
        def _niveaux_hors_effet_propre(self, *args):
            super()._niveaux_hors_effet_propre(*args)
            return niveaux_precedents(self)

    sorties = []
    for cls in (_Sans, _AvecPuisJete):
        sim = cls(periods=10, mesures=mesures, annee_debut=annee_debut)
        if preparer:
            preparer(sim)
        sorties.append(sim.simulate())
    return sorties


FORMULE_RECETTES = {'type': 'formule', 'formule': "p.get('x', 0)", 'cible': 'recettes', 'parametres': {}}


@pytest.mark.parametrize('cas', ['programme', 'formule_recettes', 'levier_en_echec', 'plafonds',
                                 'hors_domaine'])
@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_l_evaluation_hors_effet_propre_ne_change_aucune_sortie(pleine_precision, monkeypatch, cas,
                                                               annee_debut):
    """Jeter le résultat de l'évaluation rend des sorties identiques au bit à celles qu'on obtient
    sans la lancer (tableaux et rapport : avertissements, avis, corrections, écrêtages) : elle ne
    touche à rien d'autre que ses niveaux. Cas qui posent chacun une entrée du rapport depuis le
    bloc « demande » : programme réel à plusieurs leviers (trois mondes en mode cadre), formule côté
    recettes (avis FORMULE_MENAGES, posé sous la déduplication du journal jusqu'au lot 6 : il était
    perdu), levier en échec (correction ECHEC), plafonds de 5 % et de 10 % du PIB, valeur hors du
    domaine (écrêtage). Mode tolérant (celui de l'API), même sous BUDGETLAB_STRICT."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    mesures = {'tva_rate': {'taux': 0.21}, 'defense': {'budget': 70.0},
               'chomage_alloc': {'duree': 15}, 'smic': {'montant_brut': 1900}}
    preparer = None
    if cas == 'formule_recettes':
        from budget_simulator.engine._noms_parametres import NOMS_PARAMETRES_ADMIS
        monkeypatch.setitem(NOMS_PARAMETRES_ADMIS, 'formule_test', frozenset({'x'}))
        mesures = {**mesures, 'formule_test': {'x': 3.0}}

        def preparer(sim):
            sim.measure_registry['formule_test'] = dict(FORMULE_RECETTES)
    elif cas == 'levier_en_echec':
        def panne(self, *args, **kwargs):
            raise RuntimeError('panne de test')
        monkeypatch.setattr(S, '_apply_smic', panne)
    elif cas == 'plafonds':
        mesures = {'tva_rate': {'taux': 0.30}, 'csg': {'taux': 0.15},
                   'impot_revenu': {'taux_superieur': 0.60}, 'defense': {'budget': 150.0}}
    elif cas == 'hors_domaine':
        mesures = {**mesures, 'defense': {'budget': 10_000.0}}
    a, b = _sorties_avec_et_sans_evaluation(mesures, annee_debut, preparer)
    assert a[0].equals(b[0]) and a[1].equals(b[1]) and repr(a[2]) == repr(b[2])
    if cas == 'programme':
        assert a[2]['valid'] is True, a[2]['warnings']
    else:
        assert a[2]['warnings'], cas   # non-vacuité : le cas pose bien une entrée au rapport


# --- 4. simulate() passe toujours les niveaux de l'année ---------------------------------------

@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_simulate_passe_toujours_les_niveaux_du_budget(annee_debut):
    appels = []

    class _Sonde(S):
        def _stocker_impulsions(self, year, eco_state, niveaux=None):
            appels.append(niveaux is not None)
            return super()._stocker_impulsions(year, eco_state, niveaux)

    _Sonde(periods=10, mesures={'tva_rate': {'taux': 0.21}}, annee_debut=annee_debut).simulate()
    assert len(appels) == 20 and all(appels)   # deux appels par année simulée


def test_le_bloc_demande_ne_lit_pas_la_croissance_pour_les_prix(monkeypatch):
    """Les prix de l'année ne lisent pas la croissance de l'année (Phillips sur l'écart de fin
    t−1, TVA de t−1) : l'évaluation hors effet propre et l'évaluation définitive voient la même
    inflation. Sinon l'évaluation hors effet propre ne serait pas « le budget de l'année à son
    état macro hors son propre effet »."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    vues = []

    class _Sonde(S):
        def calculate_inflation(self, year, economic_state):
            pi = super().calculate_inflation(year, economic_state)
            vues.append((year, pi))
            return pi

    _Sonde(periods=10, mesures={'tva_rate': {'taux': 0.22}, 'defense': {'budget': 80.0}}).simulate()
    par_annee = {}
    for year, pi in vues:
        par_annee.setdefault(year, []).append(pi)
    assert len(par_annee) == 10
    assert all(len(v) == 2 and v[0] == v[1] and math.isfinite(v[0]) for v in par_annee.values())
