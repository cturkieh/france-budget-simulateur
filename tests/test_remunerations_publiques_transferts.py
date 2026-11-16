"""Hausses et baisses de rémunération des agents publics à effectifs constants : famille des transferts
(lot 5b des corrections d'équations).

Arbitrage du mainteneur (16/11/2026) : une hausse (ou une baisse) de rémunération des agents publics à
effectifs constants est un revenu versé aux agents. Pour la croissance, elle prend le traitement des
transferts, coefficient ``MULT_TRANSFERTS`` et profil ``DECAY_PROFILE_TRANSFERS``, dans les deux sens.
Avant : le point d'indice (``fonction_publique``) était de la dépense courante, la revalorisation des
enseignants en place (``education.salaires``) de l'investissement productif, avec leurs profils.

Sources, et ce qu'elles ne disent pas (METHODOLOGIE, encadré du lot 5b) : en comptabilité nationale,
une hausse de rémunération à effectifs et structure constants est un effet prix, pas volume (SEC 2010
§ 10.44 et § 11.35-11.37 ; manuel Eurostat des prix et volumes, 2016, § 3.11.2) ; le modèle Mésange
(Insee, document de travail G2017/04, p. 106) fait jouer les « salaires publics en prix » comme les
prestations en espèces. Le niveau est encadré par deux modèles publiés : e-mod.fr (OFCE, policy brief
n° 17, 2017, p. 15 : multiplicateur « proche de 0,9 au bout de trois ans » pour les prestations sociales
et les salaires publics) et QUEST (Roeger & in 't Veld 2010 : effet sur le PIB privé de 0,3, 0,55 à 0,74
fois celui d'un transfert, choc d'un an). Limite déclarée : Mésange décrit un effet différé, le profil
des transferts du moteur ne l'est pas (profil repris par analogie, sans source).

Contrat verrouillé ici, dans le moteur complet :

1. source unique : le montant porté par la famille des transferts est exactement celui que le levier
   émet au canal ménages ``remunerations_publiques`` (coût de l'année), ni plus ni moins, et le reste
   de sa dépense garde sa famille et son profil ; réciproquement, aucun flux de rémunération sans ce
   canal. Les émetteurs sont DÉRIVÉS du registre des paramètres (chaque paramètre porté seul à chaque
   borne de son domaine), pas d'une liste ;
2. une hausse ou une baisse de rémunération a, sur toute la trajectoire macroéconomique (PIB, dette,
   déficit, chômage, inflation, taux), le même effet qu'un transfert du même montant (coût employeur
   brut), à 1e-9 près, pour chaque émetteur dérivé et un émetteur synthétique, dans les deux sens et dans
   cinq états (banc historique, mode cadre 2028, dette haute, écarts de production négatif et positif),
   avec une montée en charge sur trois ans : la règle vaut pour chaque impulsion, pas pour la seule
   première ;
3. par les vrais curseurs (point d'indice ±2 %, revalorisation des enseignants ±5 %), hausse et baisse
   déplacent le PIB réel en miroir à 1 % près, de 1 à 6 ans, dans les deux modes ;
4. plus d'exception : le SMIC, dont la part « agents publics » de la hausse restait dans un solde à
   coefficient propre en attente d'un arbitrage, suit la règle depuis le lot SMIC (arbitrage du mainteneur
   du 16/11/2026 ; tests/test_smic_flux_tresor.py) ; aucun levier à coefficient propre n'émet ce canal
   (le test rougit si l'un d'eux se met à l'émettre) ;
5. sous le plafond de 10 % du PIB en mode « reduction », le canal et la dépense du levier sont réduits
   du même facteur : la source unique tient, et la part de la rémunération dans la dépense ne change pas.

Ne change pas : effectifs (embauches, suppressions, postes d'enseignants), reste de chaque levier,
effet d'offre, compétitivité, Gini, pouvoir d'achat. Aucune donnée du dépôt parent n'est lue.
"""
from functools import lru_cache

import pytest

from budget_simulator.constants import INTENSITE_DOMAINS, PARAM_DOMAINS
from budget_simulator.engine import growth as growth_mod
from budget_simulator.engine.cadre import LEVIERS_REFUSES_EN_MODE_HISTORIQUE, charger_droit_en_vigueur
from budget_simulator.handlers._types import canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers
from tests.test_bornes_entrees_sorties_v067 import CONSOLIDATION_MAXIMALE

S = BudgetSimulatorV45
NETS = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
# Émetteurs à coefficient propre laissés en l'état : aucun. Le SMIC, seul cas jusqu'au lot SMIC (part
# « agents publics » de sa hausse), est désormais multiplié flux par flux.
EN_ATTENTE = frozenset()
COMPO_TRANSFERT = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 1.0}
JUMEAU_TRANSFERT = 'prestations_menages'   # levier de transfert, profil des transferts, neutre au droit


def _remuneration(impact):
    canaux = impact.get('menages') if isinstance(impact, dict) else None
    return float((canaux or {}).get('remunerations_publiques', 0) or 0)


def _domaines():
    """Registre des paramètres du moteur : domaines publiés et domaines d'intensité."""
    d = {levier: dict(params) for levier, params in PARAM_DOMAINS.items()}
    for levier, bornes in INTENSITE_DOMAINS.items():
        d.setdefault(levier, {})['intensite'] = bornes
    return d


class _Capture(BudgetSimulatorV45):
    """Garde les impacts que le moteur utilise réellement, année par année (après plafonds)."""

    def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
        sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
        self.__dict__.setdefault('_impacts_vus', []).append(imp)
        return sp, rv, imp


@lru_cache(maxsize=1)
def emetteurs():
    """Leviers qui émettent un montant non nul au canal ``remunerations_publiques`` quand l'un de leurs
    paramètres est porté seul à une borne de son domaine (mode historique ; mode cadre 2028 pour un
    levier que le mode historique refuse)."""
    vus = set()
    for levier, params in sorted(_domaines().items()):
        debut = 2028 if levier in LEVIERS_REFUSES_EN_MODE_HISTORIQUE else None
        for param, bornes in params.items():
            for valeur in bornes:
                sim = _Capture(periods=6, mesures={levier: {param: valeur}}, annee_debut=debut)
                sim.simulate()
                if any(_remuneration(imp.get(levier)) for imp in sim._impacts_vus):
                    vus.add(levier)
    return frozenset(vus)


EMETTEURS = tuple(sorted(emetteurs() - NETS)) + ('emetteur_synthetique',)


# --- 1. Inventaire et source unique ------------------------------------------------------------

def test_inventaire_des_emetteurs():
    """Le balayage retrouve les trois émetteurs connus (point d'indice, revalorisation des
    enseignants, part « agents publics » du SMIC) ; il peut en trouver d'autres, alors traités d'office.
    L'exception des leviers à coefficient propre est exactement celle déclarée."""
    assert {'fonction_publique', 'education', 'smic'} <= emetteurs(), sorted(emetteurs())
    assert emetteurs() & NETS == EN_ATTENTE, sorted(emetteurs() & NETS)


# Programmes par les vrais curseurs : tous les émetteurs dans les deux sens, avec le reste de leur
# levier (effectifs, budget, postes) et des leviers d'autres familles.
PROGRAMMES = {
    'hausses': {'fonction_publique': {'effectifs': -50000, 'point_indice': 4},
                'education': {'budget': 70, 'enseignants': 8000, 'salaires': 6},
                'smic': {'montant_brut': 2000}, 'collectivites': {'investissement': 5, 'dotation': 125},
                'retraites': {'indexation': 1.1}, 'tva_rate': {'taux': 0.21}},
    'baisses': {'fonction_publique': {'effectifs': 30000, 'point_indice': -2},
                'education': {'budget': 62, 'enseignants': -5000, 'salaires': -5},
                'defense': {'budget': 55}},
}


@pytest.mark.parametrize('annee_debut', [None, 2028])
@pytest.mark.parametrize('nom', list(PROGRAMMES))
def test_source_unique_le_montant_reclasse_est_celui_du_canal_menages(monkeypatch, nom, annee_debut):
    """Chaque année, pour chaque levier : le flux de rémunération vaut exactement −(canal
    ``remunerations_publiques``) et le flux de dépense le reste (dépense − investissement −
    rémunération) ; sans ce canal, aucun flux de rémunération ; un levier à coefficient propre garde
    tout dans son solde.

    Portée : c'est un DÉTECTEUR DE CHANGEMENT de la formule de ``flux_par_levier`` (il en recopie la
    règle), pas une propriété. Il ne vérifie pas que le canal fait partie de la dépense du levier : un
    canal pris hors de la dépense, ou doublé, est vu par le miroir des curseurs (section 3) et par
    ``test_pouvoir_achat_v068`` et ``test_fp_rampe_v067``, pas ici."""
    appels = []
    origine = growth_mod.flux_par_levier

    def espion(impacts, nettes, **ensembles):
        f = origine(impacts, nettes, **ensembles)
        appels.append((impacts, f))
        return f
    monkeypatch.setattr(growth_mod, 'flux_par_levier', espion)
    BudgetSimulatorV45(periods=8, mesures=PROGRAMMES[nom], annee_debut=annee_debut).simulate()
    vus = set()
    for impacts, f in appels:
        cles = {m for (m, flux) in f if flux == 'remunerations'}
        for m, imp in impacts.items():
            if not isinstance(imp, dict):
                continue
            r = _remuneration(imp)
            if m in NETS or not r:
                assert m not in cles, m
                continue
            vus.add(m)
            dep = float(imp.get('depenses', 0) or 0)
            inv = float(imp.get('depenses_investissement', 0) or 0)
            assert f[(m, 'remunerations')] == -r, (m, f[(m, 'remunerations')], r)
            assert f[(m, 'depenses')] == -(dep - inv - r), m
        assert cles <= {m for m, imp in impacts.items() if _remuneration(imp) and m not in NETS}
    assert {'fonction_publique', 'education'} <= vus, vus


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_remuneration_au_traitement_des_transferts_le_reste_dans_sa_famille(annee_debut):
    """Impulsions stockées : un flux de rémunération porte le coefficient et le profil des transferts ;
    le reste de la dépense de l'éducation garde ceux de l'investissement, celui de la fonction publique
    ceux de la dépense courante (profil des impôts)."""
    etats = {}

    class _Etats(BudgetSimulatorV45):
        def _stocker_impulsions(self, year, eco_state, niveaux=None):   # signature du lot 6 (niveaux du budget)
            etats[year] = dict(eco_state)
            return super()._stocker_impulsions(year, eco_state, niveaux)
    sim = _Etats(periods=8, mesures=PROGRAMMES['hausses'], annee_debut=annee_debut)
    sim.simulate()
    familles = {'remunerations': (COMPO_TRANSFERT, S.DECAY_PROFILE_TRANSFERS)}
    reste = {'education': ({'depenses': 1.0, 'recettes': 0.0, 'investissement': 1.0, 'transferts': 0.0},
                           S.DECAY_PROFILE_INVEST),
             'fonction_publique': ({'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 0.0},
                                   S.DECAY_PROFILE_TAXES)}
    vus = set()
    for (annee, m, flux, sens), (_delta, k, profil) in sim._fiscal_impulses.items():
        if flux == 'remunerations':
            compo, attendu = familles['remunerations']
        elif flux == 'depenses' and m in reste:
            compo, attendu = reste[m]
        else:
            continue
        vus.add((m, flux))
        assert profil == attendu, (annee, m, flux, sens)
        assert k == abs(FiscalMultipliers().get_multiplier(sens, compo, etats[annee], annee, m)), (annee, m, flux)
    assert {('education', 'remunerations'), ('fonction_publique', 'remunerations'),
            ('education', 'depenses'), ('fonction_publique', 'depenses')} <= vus, vus


# --- 2. Même effet qu'un transfert du même montant, sur toute la trajectoire ---------------------

ETATS = {
    'banc_historique': dict(annee_debut=None, debut=2026),
    'cadre_2028': dict(annee_debut=2028, debut=2028),
    'dette_haute': dict(annee_debut=None, debut=2026, dette=1.60),
    'ecart_negatif': dict(annee_debut=None, debut=2026, ecart=-0.03),
    'ecart_positif': dict(annee_debut=None, debut=2026, ecart=+0.015),
}
PERIODES = 10
COLONNES = {0: ('Dette/PIB %', 'Déficit/PIB %', 'Croissance %', 'Chômage %', 'Inflation %', 'PIB', 'Dette'),
            1: ('PIB_Réel_Base2025', 'Output_Gap %', 'Taux_Intérêt %', 'Recettes_Totales', 'Intérêts_Dette')}


def _injecte(etat, levier, x0, remuneration):
    """Choc durable de x0 × PIB sur la dépense de ``levier`` dès le premier budget de l'état, en montée
    en charge sur trois ans (un tiers, deux tiers, puis le tout) : plusieurs impulsions successives, pas
    une seule ; s'il est une rémunération, le même montant est émis au canal ménages
    ``remunerations_publiques``."""
    e = ETATS[etat]

    class _Banc(BudgetSimulatorV45):
        def _reset_state(self):
            super()._reset_state()
            if 'ecart' in e:
                self.output_gap_courant = e['ecart']

        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if year >= e['debut']:
                x = x0 * gdp * min(1.0, (year - e['debut'] + 1) / 3)   # montée en charge sur 3 ans
                imp = dict(imp)
                bloc = dict(imp.get(levier) or {})
                bloc['depenses'] = float(bloc.get('depenses', 0) or 0) + x
                bloc['recettes'] = float(bloc.get('recettes', 0) or 0)
                if remuneration:
                    canaux = dict(bloc.get('menages') or canaux_menages())
                    canaux['remunerations_publiques'] = canaux.get('remunerations_publiques', 0.0) + x
                    bloc['menages'] = canaux
                imp[levier] = bloc
                sp += x
            return sp, rv, imp

    sim = _Banc(periods=PERIODES, mesures={}, annee_debut=e['annee_debut'])
    if 'dette' in e:
        sim.base_params['dette_ratio'] = e['dette']
    # Le lot 5d ajoute au PIB PUBLIÉ le coût d'une rémunération (effet prix), pas d'un transfert :
    # l'équivalence porte sur l'effet de demande, l'effet prix est retiré des deux côtés (il est
    # verrouillé par test_effet_prix_remunerations.py).
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, '_cout_remunerations_annee', lambda self, impacts: 0.0)
        return sim.simulate()


@pytest.fixture(scope='module')
def jumeaux():
    cache = {}

    def run(etat, signe):
        if (etat, signe) not in cache:
            cache[(etat, signe)] = _injecte(etat, JUMEAU_TRANSFERT, 0.01 * signe, remuneration=False)
        return cache[(etat, signe)]
    return run


@pytest.mark.parametrize('signe', [+1, -1])
@pytest.mark.parametrize('etat', list(ETATS))
@pytest.mark.parametrize('levier', EMETTEURS)
def test_meme_effet_qu_un_transfert_du_meme_montant(jumeaux, levier, etat, signe):
    """±1 point de PIB de rémunération publique (dépense et canal ménages), en montée en charge sur
    trois ans : toute la trajectoire macroéconomique est celle d'un transfert du même montant, à 1e-9
    près (en points pour les taux, en relatif pour les montants). Rouge avant le lot 5b : le point
    d'indice suivait la dépense courante, la revalorisation des enseignants l'investissement. La
    montée en charge fait rougir une règle limitée à la première impulsion de chaque levier."""
    assert levier not in NETS
    a, b = _injecte(etat, levier, 0.01 * signe, remuneration=True), jumeaux(etat, signe)
    for table, colonnes in COLONNES.items():
        for col in colonnes:
            for i, (x, y) in enumerate(zip(a[table][col].values, b[table][col].values)):
                assert x == pytest.approx(y, rel=1e-12, abs=1e-9), (levier, etat, signe, col, i, x, y)


def test_l_equivalence_n_est_pas_vide(jumeaux):
    """Non-vacuité : sans le canal ménages, la même dépense de l'éducation ou de la fonction publique
    ne suit pas la trajectoire d'un transfert."""
    for levier in ('education', 'fonction_publique'):
        a = _injecte('banc_historique', levier, 0.01, remuneration=False)
        b = jumeaux('banc_historique', +1)
        assert abs(a[0]['Dette/PIB %'].values[-1] - b[0]['Dette/PIB %'].values[-1]) > 0.01, levier


# --- 3. Miroir par les vrais curseurs ------------------------------------------------------------

def _pib_curseur(levier, param, valeur, annee_debut):
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        mesures = {levier: {param: valeur}} if valeur is not None else {}
        return BudgetSimulatorV45(periods=PERIODES, mesures=mesures,
                                  annee_debut=annee_debut).simulate()[1]['PIB_Réel_Base2025'].values
    finally:
        mp.undo()


@pytest.mark.parametrize('annee_debut', [None, 2028])
@pytest.mark.parametrize('levier, param, ecart', [('fonction_publique', 'point_indice', 2.0),
                                                  ('education', 'salaires', 5.0)])
def test_curseurs_reels_en_miroir_de_1_a_6_ans(levier, param, ecart, annee_debut):
    """Point d'indice ±2 % et revalorisation des enseignants ±5 % autour du droit applicable (défaut en
    mode historique, droit en vigueur en mode cadre) : hausse et baisse en miroir à 1 % près."""
    ref = (charger_droit_en_vigueur().mesures.get(levier) or {}).get(param, 0) if annee_debut else 0
    y0 = _pib_curseur(levier, param, None, annee_debut)
    yh = _pib_curseur(levier, param, ref + ecart, annee_debut)
    yb = _pib_curseur(levier, param, ref - ecart, annee_debut)
    debut = (annee_debut or 2026) - 2025
    for h in range(1, 7):
        i = debut + h
        hausse, baisse = yh[i] / y0[i] - 1, yb[i] / y0[i] - 1
        assert hausse > 0 > baisse, (h, hausse, baisse)
        assert abs(abs(baisse) / hausse - 1) < 0.01, (levier, annee_debut, h, hausse, baisse)


# --- 5. Plafond de 10 % du PIB en mode « reduction » --------------------------------------------

# La consolidation maximale des tests de bornes (environ 20 % du PIB d'impact par an), avec des HAUSSES de
# point d'indice et de salaires des enseignants : le plafond mord chaque année.
PROGRAMME_AU_DELA_DU_PLAFOND = {
    **CONSOLIDATION_MAXIMALE,
    'fonction_publique': {'effectifs': -100000, 'point_indice': 4.0},
    'education': {'budget': 60, 'enseignants': -20000, 'salaires': 6},
}


def _flux_vus(monkeypatch, mode):
    import budget_simulator.engine.orchestrator as orchestrateur
    appels = []
    origine = growth_mod.flux_par_levier

    def espion(impacts, nettes, **ensembles):
        f = origine(impacts, nettes, **ensembles)
        appels.append((impacts, f))
        return f
    with monkeypatch.context() as mp:
        mp.setattr(growth_mod, 'flux_par_levier', espion)
        mp.setattr(orchestrateur, 'PLAFOND_TOTAL_MODE', mode)
        BudgetSimulatorV45(periods=8, mesures=PROGRAMME_AU_DELA_DU_PLAFOND).simulate()
    return appels


def test_plafond_en_mode_reduction_la_source_unique_tient(monkeypatch):
    """Mode « reduction » du plafond de 10 % du PIB, sur un programme qui le dépasse : chaque année, le
    flux de rémunération vaut −(canal) dans les impacts réduits, et la part de la rémunération dans la
    dépense du levier est celle du mode sans réduction (canal et dépense réduits du même facteur)."""
    reduits = _flux_vus(monkeypatch, 'reduction')
    entiers = _flux_vus(monkeypatch, 'avertissement')
    assert len(reduits) == len(entiers)
    vus, reduites = 0, 0
    for (imp_r, f_r), (imp_e, _f_e) in zip(reduits, entiers):
        for m in ('fonction_publique', 'education'):
            r_r, r_e = _remuneration(imp_r.get(m)), _remuneration(imp_e.get(m))
            if not r_r:
                continue
            vus += 1
            reduites += abs(r_r) < abs(r_e)
            assert f_r[(m, 'remunerations')] == -r_r, m
            part_r = r_r / float(imp_r[m]['depenses'])
            part_e = r_e / float(imp_e[m]['depenses'])
            assert part_r == pytest.approx(part_e, rel=1e-12), (m, part_r, part_e)
    assert vus and reduites, ('non-vacuité : le plafond doit réduire le canal', vus, reduites)
