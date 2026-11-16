"""Prestations en espèces émises hors des leviers de transfert : traitement des transferts (lot 5e des
corrections d'équations).

Règle (même mécanique que le lot 5b) : le montant qu'un levier émet au canal ménages ``prestations`` et qui
n'est pas déjà traité comme un transfert (levier hors ``TRANSFER_MEASURES``, hors coefficient propre) forme
un flux distinct, au coefficient et au profil des transferts, dans les deux sens ; le reste du levier garde
sa famille. Cas connu : le rabot uniforme, dont les coupes de pensions, d'allocations chômage et de minima
sociaux (prestations en espèces, SEC 2010 D.62) étaient prises en dépense courante, comme le reste du rabot.

Exceptions déclarées, verrouillées par la liste ET par le comportement :
- le SMIC, levier de transfert depuis toujours (son coefficient propre a été retiré au lot SMIC) : toute sa
  dépense est déjà au traitement des transferts, son canal ``prestations`` n'est pas reclassé ;
- la santé (``PRESTATIONS_NON_RECLASSEES``) : son canal ``prestations`` porte les franchises et
  participations, un reste à charge sur des remboursements de soins, c'est-à-dire une prestation EN NATURE,
  pas en espèces ; laissée en l'état, en attente d'un arbitrage.

Contrat verrouillé ici, dans le moteur complet :

1. inventaire : les émetteurs du canal sont DÉRIVÉS du registre des paramètres (chaque paramètre porté seul
   à chaque borne de son domaine) ; hors des leviers de transfert et des coefficients propres, ce sont
   exactement le rabot (reclassé) et la santé (exclue) — un émetteur nouveau rougit ici, à classer ;
2. source unique : chaque année, le flux de prestations vaut exactement −(canal) et le reste de la dépense
   garde sa famille ; aucun flux de prestations pour un levier de transfert, à coefficient propre ou exclu ;
3. même effet qu'un transfert du même montant, sur toute la trajectoire macroéconomique, à 1e-9 près, en
   montée en charge sur trois ans, dans les deux sens et cinq états, pour le rabot et un émetteur
   synthétique ; non-vacuité ;
4. exceptions par le comportement : retirer le canal ``prestations`` du SMIC (levier de transfert) ou de la
   santé ne change aucune colonne macroéconomique.

Ne change pas : la coupe de masse salariale du rabot (assimilée à des effectifs, limite déclarée) et son
assiette, les leviers de transfert, le pouvoir d'achat (qui lisait déjà ce canal), le Gini.
"""
from functools import lru_cache

import pytest

from budget_simulator.constants import INTENSITE_DOMAINS, PARAM_DOMAINS
from budget_simulator.engine import growth as growth_mod
from budget_simulator.engine.cadre import LEVIERS_REFUSES_EN_MODE_HISTORIQUE
from budget_simulator.handlers._types import canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

S = BudgetSimulatorV45
NETS = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
COMPO_TRANSFERT = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 1.0}
JUMEAU_TRANSFERT = 'prestations_menages'
RECLASSES = frozenset({'rabot_uniforme'})
EXCLUS = frozenset({'sante'})


def _prestations(impact):
    canaux = impact.get('menages') if isinstance(impact, dict) else None
    return float((canaux or {}).get('prestations', 0) or 0)


def test_le_registre_des_exclusions_est_celui_declare():
    assert S.PRESTATIONS_NON_RECLASSEES == EXCLUS


class _Capture(BudgetSimulatorV45):
    def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
        sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
        self.__dict__.setdefault('_impacts_vus', []).append(imp)
        return sp, rv, imp


@lru_cache(maxsize=1)
def emetteurs():
    """Leviers qui émettent un montant non nul au canal ``prestations`` quand l'un de leurs paramètres est
    porté seul à une borne de son domaine."""
    domaines = {levier: dict(params) for levier, params in PARAM_DOMAINS.items()}
    for levier, bornes in INTENSITE_DOMAINS.items():
        domaines.setdefault(levier, {})['intensite'] = bornes
    vus = set()
    for levier, params in sorted(domaines.items()):
        debut = 2028 if levier in LEVIERS_REFUSES_EN_MODE_HISTORIQUE else None
        for param, bornes in params.items():
            for valeur in bornes:
                sim = _Capture(periods=6, mesures={levier: {param: valeur}}, annee_debut=debut)
                sim.simulate()
                if any(_prestations(imp.get(levier)) for imp in sim._impacts_vus):
                    vus.add(levier)
    return frozenset(vus)


def test_inventaire_des_emetteurs():
    """Hors des leviers de transfert et des coefficients propres, les émetteurs du canal sont exactement le
    rabot (reclassé) et la santé (exclue). Aucun émetteur à coefficient propre depuis que le SMIC en est
    sorti (lot SMIC) ; il émet le canal comme levier de transfert."""
    hors_transferts = emetteurs() - S.TRANSFER_MEASURES - NETS
    assert hors_transferts == RECLASSES | EXCLUS, sorted(hors_transferts)
    assert emetteurs() & NETS == frozenset(), sorted(emetteurs() & NETS)
    assert 'smic' in emetteurs() & S.TRANSFER_MEASURES


PROGRAMME = {'rabot_uniforme': {'taux_reduction': 0.08}, 'sante': {'franchise_participation_taux': 200},
             'smic': {'montant_brut': 2000}, 'retraites': {'indexation': 0.5},
             'chomage_alloc': {'montant': 30.0}}


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_source_unique_le_montant_reclasse_est_celui_du_canal_menages(monkeypatch, annee_debut):
    """Chaque année : le flux de prestations du rabot vaut exactement −(canal ``prestations``), le flux de
    dépense le reste ; aucun flux de prestations pour un levier de transfert, à coefficient propre ou exclu.
    Comme au lot 5b, c'est un détecteur de changement de la formule de ``flux_par_levier``."""
    appels = []
    origine = growth_mod.flux_par_levier

    def espion(impacts, nettes, **ensembles):
        f = origine(impacts, nettes, **ensembles)
        appels.append((impacts, f))
        return f
    monkeypatch.setattr(growth_mod, 'flux_par_levier', espion)
    BudgetSimulatorV45(periods=8, mesures=PROGRAMME, annee_debut=annee_debut).simulate()
    vus = 0
    for impacts, f in appels:
        for m, imp in impacts.items():
            p = _prestations(imp)
            if m in RECLASSES and p:
                vus += 1
                dep = float(imp.get('depenses', 0) or 0)
                inv = float(imp.get('depenses_investissement', 0) or 0)   # part investie de sa coupe de dotation (lot 5c)
                assert f[(m, 'prestations')] == -p, m
                assert f[(m, 'depenses')] == -(dep - inv - p), m
                assert abs(p) < abs(dep), (m, p, dep)   # une part de la dépense du levier
            else:
                assert (m, 'prestations') not in f, m
    assert vus


# --- Même effet qu'un transfert du même montant ------------------------------------------------

ETATS = {
    'banc_historique': dict(annee_debut=None, debut=2026),
    'cadre_2028': dict(annee_debut=2028, debut=2028),
    'dette_haute': dict(annee_debut=None, debut=2026, dette=1.60),
    'ecart_negatif': dict(annee_debut=None, debut=2026, ecart=-0.03),
    'ecart_positif': dict(annee_debut=None, debut=2026, ecart=+0.015),
}
PERIODES = 10
COLONNES = {0: ('Dette/PIB %', 'Déficit/PIB %', 'Croissance %', 'Chômage %', 'Inflation %', 'PIB', 'Dette',
                'Recettes/PIB %', 'Dépenses/PIB %'),
            1: ('PIB_Réel_Base2025', 'Output_Gap %', 'Taux_Intérêt %', 'Recettes_Totales', 'Intérêts_Dette',
                'Croissance_Potentielle_Totale %', 'Multiplicateur', 'Dépenses_Totales')}


def _injecte(etat, levier, x0, prestation):
    """Choc durable de x0 × PIB sur la dépense de ``levier``, en montée en charge sur trois ans ; s'il est une
    prestation, le même montant est émis au canal ménages ``prestations``."""
    e = ETATS[etat]

    class _Banc(BudgetSimulatorV45):
        def _reset_state(self):
            super()._reset_state()
            if 'ecart' in e:
                self.output_gap_courant = e['ecart']

        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if year >= e['debut']:
                x = x0 * gdp * min(1.0, (year - e['debut'] + 1) / 3)
                imp = dict(imp)
                bloc = dict(imp.get(levier) or {})
                bloc['depenses'] = float(bloc.get('depenses', 0) or 0) + x
                bloc['recettes'] = float(bloc.get('recettes', 0) or 0)
                if prestation:
                    canaux = dict(bloc.get('menages') or canaux_menages())
                    canaux['prestations'] = canaux.get('prestations', 0.0) + x
                    bloc['menages'] = canaux
                imp[levier] = bloc
                sp += x
            return sp, rv, imp

    sim = _Banc(periods=PERIODES, mesures={}, annee_debut=e['annee_debut'])
    if 'dette' in e:
        sim.base_params['dette_ratio'] = e['dette']
    return sim.simulate()


@pytest.fixture(scope='module')
def jumeaux():
    cache = {}

    def run(etat, signe):
        if (etat, signe) not in cache:
            cache[(etat, signe)] = _injecte(etat, JUMEAU_TRANSFERT, 0.01 * signe, prestation=False)
        return cache[(etat, signe)]
    return run


@pytest.mark.parametrize('signe', [+1, -1])
@pytest.mark.parametrize('etat', list(ETATS))
@pytest.mark.parametrize('levier', sorted(RECLASSES) + ['emetteur_synthetique'])
def test_meme_effet_qu_un_transfert_du_meme_montant(jumeaux, levier, etat, signe):
    """±1 point de PIB de prestation en espèces émise par un levier hors transfert, en montée en charge sur
    trois ans : toute la trajectoire macroéconomique est celle d'un transfert du même montant, à 1e-9 près.
    Rouge avant le lot 5e : la coupe de prestations du rabot suivait la dépense courante."""
    a, b = _injecte(etat, levier, 0.01 * signe, prestation=True), jumeaux(etat, signe)
    for table, colonnes in COLONNES.items():
        for col in colonnes:
            for i, (x, y) in enumerate(zip(a[table][col].values, b[table][col].values)):
                assert x == pytest.approx(y, rel=1e-12, abs=1e-9), (levier, etat, signe, col, i, x, y)


def test_l_equivalence_n_est_pas_vide(jumeaux):
    """Non-vacuité : sans le canal ménages, la même dépense du rabot ne suit pas la trajectoire d'un
    transfert."""
    a = _injecte('banc_historique', 'rabot_uniforme', 0.01, prestation=False)
    b = jumeaux('banc_historique', +1)
    assert abs(a[0]['Dette/PIB %'].values[-1] - b[0]['Dette/PIB %'].values[-1]) > 0.01


# --- Exceptions, verrouillées par le comportement ------------------------------------------------

def _sans_canal_prestations(levier):
    class _Sans(BudgetSimulatorV45):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            bloc = imp.get(levier)
            if isinstance(bloc, dict) and isinstance(bloc.get('menages'), dict):
                self.__dict__.setdefault('_retire', []).append(bloc['menages'].get('prestations', 0))
                imp = dict(imp)
                bloc = dict(bloc)
                canaux = dict(bloc['menages'])
                canaux['prestations'] = 0.0
                bloc['menages'] = canaux
                imp[levier] = bloc
            return sp, rv, imp
    return _Sans


@pytest.mark.parametrize('annee_debut', [None, 2028])
@pytest.mark.parametrize('levier, mesures', [('smic', {'smic': {'montant_brut': 2000}}),
                                             ('sante', {'sante': {'franchise_participation_taux': 200}})])
def test_exceptions_le_canal_ne_change_aucune_colonne_macroeconomique(levier, mesures, annee_debut):
    """SMIC (levier de transfert) et santé (prestation en nature, exclue) : retirer leur canal ``prestations``
    ne change aucune colonne macroéconomique, au bit. Seul l'indice de pouvoir d'achat, qui lit ce canal,
    bouge. Un reclassement de l'un d'eux au traitement des transferts rougit ici."""
    a = BudgetSimulatorV45(periods=PERIODES, mesures=mesures, annee_debut=annee_debut).simulate()
    sim = _sans_canal_prestations(levier)(periods=PERIODES, mesures=mesures, annee_debut=annee_debut)
    b = sim.simulate()
    assert any(sim._retire), f'non-vacuité : {levier} émet au canal prestations'
    for table, colonnes in COLONNES.items():
        for col in colonnes:
            assert list(a[table][col]) == list(b[table][col]), (levier, annee_debut, col)


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_le_rabot_change_de_trajectoire(annee_debut):
    """Le rabot réel (8 %) : retirer son canal ``prestations`` CHANGE la trajectoire (la règle mord sur le
    vrai levier), à l'inverse des exceptions."""
    mesures = {'rabot_uniforme': {'taux_reduction': 0.08}}
    a = BudgetSimulatorV45(periods=PERIODES, mesures=mesures, annee_debut=annee_debut).simulate()
    b = _sans_canal_prestations('rabot_uniforme')(periods=PERIODES, mesures=mesures,
                                                  annee_debut=annee_debut).simulate()
    assert abs(a[0]['Dette/PIB %'].values[-1] - b[0]['Dette/PIB %'].values[-1]) > 0.05


def test_les_ensembles_de_flux_par_levier_sont_obligatoires():
    """Sans valeur par défaut : un appelant qui oublierait les leviers de transfert ou les exclusions
    désactiverait la règle en silence ; l'appel est refusé."""
    with pytest.raises(TypeError):
        growth_mod.flux_par_levier({}, NETS)
    with pytest.raises(TypeError):
        growth_mod.flux_par_levier({}, NETS, leviers_de_transfert=S.TRANSFER_MEASURES)
