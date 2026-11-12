"""Release E — relecture adverse finale du 12/11/2026. Tests écrits AVANT le code
(TDD) ; une section par constat.

I-1. Gini d'un gel d'UNE année des pensions ou des prestations. L'effet émis
     l'année du gel était gardé en entier au retour de la revalorisation
     normale, autant qu'un gel permanent, et ce retour ne se reconnaissait qu'à
     l'égalité au littéral 1,0 : avec un droit en vigueur à 0,9999, le même gel
     rendait presque tout. Désormais, le Gini suit l'écart de niveau accumulé :
     au retour à la référence du calendrier (le droit en vigueur de l'année,
     quelle que soit sa valeur) après k revalorisations au coefficient gelé, le
     levier garde min(k, N)/N de l'effet émis, N étant son plateau (7
     revalorisations pour les pensions, 10 pour les prestations). À coefficient
     constant, la convention est inchangée au bit.
m-b. Infobulle de la prévention : le curseur borne la DÉPENSE de prévention ;
     un effort supplémentaire se saisit en dépense de soins, sans retour
     modélisé.
m-c. Calendrier trop long : même comportement tolérant pour un profil « rampe »
     et pour l'alias ``rampe`` (ramené à la borne, correction tracée) ; en
     strict, un message exact (refus, sans « ramené »).
H-1. Hors périmètre de la passe, signalé par le relecteur : un entier géant sur
     la réforme de la fonction publique faisait répondre 500 en strict (lecteur
     latéral) au lieu de 422.

Règle d'écriture : chaque valeur attendue est dérivée des constantes nommées de
``constants.py`` ou de la règle écrite du levier, jamais recopiée d'une sortie
du moteur.
"""
import copy
import json
import math
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre
import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
# Documents du MOTEUR (CHANGELOG, METHODOLOGIE) : `resolve()` suit le lien
# tests/ du dépôt parent jusqu'au sous-module ; sous `RACINE`, le dépôt parent
# a son propre CHANGELOG.md, celui du site.
RACINE_MOTEUR = Path(__file__).resolve().parent.parent
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
DEBUT = C.ANNEE_PREMIER_BUDGET_MANDAT
FIN = C.ANNEE_FIN_MANDAT
R = C.RETRAITES_GINI_RESIDU_FLUX

# ===========================================================================
# I-1. Gini d'un gel d'une année : proportionnel à l'écart de niveau accumulé
# ===========================================================================

LEVIERS = {
    'retraites': ('indexation', {'duree_cotisation': C.RETRAITES_REF_DUREE_ANS}),
    'prestations_indexation': ('taux_indexation', {}),
}
CLES = {'retraites': 'retraites.indexation',
        'prestations_indexation': 'prestations_indexation.taux_indexation'}


def _plateau(levier):
    """N : revalorisations comptées au plus dans l'écart de niveau du levier."""
    if levier == 'retraites':
        return C.RETRAITES_EROSION_PLATEAU_ANS
    return getattr(C, 'PRESTATIONS_REVALORISATIONS_MAX', 10)


def _g(levier, c):
    """Effet de NIVEAU émis à l'ouverture d'un écart au coefficient ``c``
    (convention inchangée) : pensions, RETRAITES_GINI_PAR_POINT_DESINDEXATION ×
    (1 − c) ; prestations, règle du handler « 100 % → 90 % = +0,008 » :
    0,008 × (1 − c) / 0,10."""
    if levier == 'retraites':
        return C.RETRAITES_GINI_PAR_POINT_DESINDEXATION * (1.0 - c)
    return 0.008 * (1.0 - c) / 0.10


def _flux(levier):
    """Part ré-émise chaque année après l'ouverture : flux des nouvelles
    cohortes de retraités pour les pensions, rien pour les prestations."""
    return R if levier == 'retraites' else 0.0


def _sim_neuf():
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    return sim


def _parcours(levier, chemin, *, debut=DEBUT, origine=DEBUT, reference=None):
    """Handler seul, un monde : coefficient ``chemin[i]`` l'année ``debut + i``,
    horloge du levier à ``origine``. ``reference`` : référence du calendrier
    imposée (sinon celle du moteur hors cadre, la pleine indexation). Rend
    [(dépense, gini)] par année."""
    param, fixes = LEVIERS[levier]
    sim = _sim_neuf()
    sim._origines_courantes = {levier: origine}
    sim._inflation_par_annee = {a: 0.012 + 0.0005 * (a - 2025) for a in range(2025, 2050)}
    if reference is not None:
        sim._reference_du_calendrier = lambda _levier, _param, _annee: reference
    sorties = []
    for i, c in enumerate(chemin):
        dep, _, impacts = sim.measure_handlers[levier](
            sim.measure_registry[levier], {**fixes, param: c}, debut + i, 3300.0, 0.015, 0.078)
        sorties.append((dep, impacts.get('gini', 0.0)))
    return sorties


def _cumul(sorties):
    return sum(g for _, g in sorties)


def test_i1_plateaux_nommes_et_retour_sans_egalite_au_litteral():
    """N vient des constantes nommées (7 et 10, vérifiés dans le code), et le
    retour ne se reconnaît plus à l'égalité au littéral 1,0."""
    assert C.RETRAITES_EROSION_PLATEAU_ANS == 7
    assert getattr(C, 'PRESTATIONS_REVALORISATIONS_MAX', None) == 10
    source = (RACINE / 'budget_simulator' / 'handlers' / 'depenses.py').read_text(encoding='utf-8')
    assert 'PRESTATIONS_REVALORISATIONS_MAX' in source
    assert '== INDEXATION_PLEINE' not in source
    assert 'indexation == indexation_ref' not in source


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_gel_d_une_annee_garde_un_n_ieme_de_l_effet(levier):
    """Gel d'une année puis pleine indexation (droit livré) : l'effet est émis
    en entier l'année du gel (convention), le retour en rend (N − 1)/N, et
    rien ensuite. Cumul : g / N (pensions 0,005 / 7, prestations 0,08 / 10)."""
    n = _plateau(levier)
    emis = [g for _, g in _parcours(levier, [0.0] + [1.0] * 6)]
    assert emis[0] == _g(levier, 0.0) > 0
    assert emis[1] == pytest.approx(-(1 - 1 / n) * _g(levier, 0.0), rel=1e-12), emis
    assert emis[2:] == [0.0] * 5, emis
    assert sum(emis) == pytest.approx(_g(levier, 0.0) / n, rel=1e-12)


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('coef, reference', [(0.0, 1.0), (0.5, 1.0), (1.2, 1.0), (0.0, 0.9),
                                             (0.95, 0.9), (0.0, 0.9999)])
def test_i1_part_gardee_min_k_n_sur_n_quelle_que_soit_la_reference(levier, coef, reference):
    """k années au coefficient ``coef`` puis retour à la référence (quelle que
    soit sa valeur) : écart au chemin de référence = min(k, N)/N × l'effet émis
    au-delà de la référence, (g(coef) − g(ref)) × (1 + (k − 1) × flux)."""
    n = _plateau(levier)
    for k in range(1, n + 3):
        gel = _cumul(_parcours(levier, [coef] * k + [reference] * 3, reference=reference))
        ref = _cumul(_parcours(levier, [reference] * (k + 3), reference=reference))
        exces = (_g(levier, coef) - _g(levier, reference)) * (1 + (k - 1) * _flux(levier))
        assert gel - ref == pytest.approx(min(k, n) / n * exces, rel=1e-9, abs=1e-15), (k, gel, ref)


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_monotone_dans_le_nombre_d_annees_gelees_et_sous_le_gel_permanent(levier):
    """(c) Gel de k années puis retour : cumul croissant avec k (strictement
    jusqu'au plateau), sous le gel permanent du même horizon (au plus égal
    au-delà du plateau)."""
    n = _plateau(levier)
    horizon = n + 5
    cumuls = [_cumul(_parcours(levier, [0.0] * k + [1.0] * (horizon - k))) for k in range(1, n + 3)]
    permanent = _cumul(_parcours(levier, [0.0] * horizon))
    assert all(b > a for a, b in zip(cumuls[:n], cumuls[1:n])), cumuls
    assert all(b >= a for a, b in zip(cumuls, cumuls[1:])), cumuls
    # Sous le gel permanent tant que le palier est plus court que le plateau ;
    # au-delà, au plus égal (prestations : aucun flux, l'écart est au plateau).
    assert all(c < permanent for c in cumuls[:n - 1]), (cumuls, permanent)
    assert all(c <= permanent for c in cumuls), (cumuls, permanent)
    assert cumuls[0] < permanent / 2


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('coef', [0.0, 0.9, 1.0, 1.2])
def test_i1_coefficient_constant_convention_inchangee_au_bit(levier, coef):
    """(d) Coefficient constant : effet émis à l'ouverture, puis le flux
    (pensions) ou rien (prestations), au bit."""
    emis = [g for _, g in _parcours(levier, [coef] * 9)]
    g = _g(levier, coef)
    assert emis == [g] + [g * _flux(levier)] * 8, emis


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_aucun_residu_quand_le_gel_n_a_porte_sur_aucune_revalorisation(levier):
    """(e) Gel posé l'année qui suit la dernière revalorisation comptée
    (fenêtre [origine ; origine + N − 1] épuisée) puis retiré : il n'a gelé
    aucune revalorisation, aucun écart de niveau (dépense nulle) ; l'effet émis
    à son ouverture (convention) est rendu en entier au retour, aucun résidu."""
    n = _plateau(levier)
    sorties = _parcours(levier, [1.0] * n + [0.0] + [1.0] * 3, debut=2026, origine=2026)
    assert sorties[n][0] == 0.0, sorties[n]
    assert sorties[n][1] == _g(levier, 0.0) > 0      # NON_VACUITE : effet émis à l'ouverture
    assert _cumul(sorties) == pytest.approx(0.0, abs=1e-15), sorties


# --- En simulation complète (mode cadre) ------------------------------------

def _pleine_precision(monkeypatch):
    """Sorties publiées sans arrondi (le Gini est publié au millième)."""
    monkeypatch.setattr(orch, 'round', lambda x, nd=None: float(x), raising=False)


class _Sonde(BudgetSimulatorV45):
    """Moteur instrumenté : sortie COMBINÉE de chaque levier, chaque année (les
    trois mondes de la composition en mode cadre), lue au moment de l'appel —
    y compris pour un levier égal au droit en vigueur, que le rapport ne
    publie pas. Aucun calcul modifié."""

    def _evaluer_handler(self, measure, parameters, year, gdp, inflation, unemployment):
        sortie = super()._evaluer_handler(measure, parameters, year, gdp, inflation, unemployment)
        self.__dict__.setdefault('sonde', {})[(year, measure['id'])] = sortie
        return sortie


def _simuler(mesures, profils=None, annee_debut=DEBUT):
    sim = _Sonde(periods=10, mesures=copy.deepcopy(mesures), annee_debut=annee_debut, profils=profils)
    df, _, rapport = sim.simulate()
    return df.set_index('Année'), rapport, sim


def _emis(sim, levier, jusqu_a=2035):
    """Gini émis par le levier (sortie combinée), cumulé jusqu'à ``jusqu_a``."""
    return sum(sortie[2].get('gini', 0.0) for (annee, nom), sortie in sim.sonde.items()
               if nom == levier and annee <= jusqu_a)


def _depense(sim, levier, annee):
    sortie = sim.sonde.get((annee, levier))
    return 0.0 if sortie is None else sortie[0]


def _gel(leviers, coef=0.0, annee=None):
    mesures, profils = {}, {}
    for levier in leviers:
        param, _ = LEVIERS[levier]
        mesures[levier] = {param: coef}
        if annee is not None:
            profils[CLES[levier]] = {'forme': 'annee', 'annee': annee}
    return mesures, (profils or None)


@pytest.fixture(scope='module')
def _bancs():
    out = {'sq': _simuler({})}
    for nom, leviers in (('deux', list(LEVIERS)), *((l, [l]) for l in LEVIERS)):
        out[(nom, 'annee')] = _simuler(*_gel(leviers, annee=DEBUT))
        out[(nom, 'permanent')] = _simuler(*_gel(leviers))
        out[(nom, 'sous09')] = _simuler(*_gel(leviers, coef=0.9))
    return out


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_simulation_gel_2028_emet_g_sur_n(levier, _bancs):
    """Gel 2028 d'un levier, mode cadre : émis net sur l'horizon = g(0) / N."""
    s0 = _bancs['sq'][2]
    _, r, s = _bancs[(levier, 'annee')]
    assert r['valid'] is True, r['warnings']
    emis = _emis(s, levier) - _emis(s0, levier)
    assert emis == pytest.approx(_g(levier, 0.0) / _plateau(levier), rel=1e-9), emis


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_simulation_gel_d_une_annee_sous_le_gel_permanent(levier, _bancs):
    """(c) En simulation : émis jusqu'en 2032 du gel d'une année < la moitié
    de celui du gel permanent, pour chaque levier (avant : égaux pour les
    prestations, 0,005 contre 0,007 pour les pensions)."""
    s0 = _bancs['sq'][2]
    annee = _emis(_bancs[(levier, 'annee')][2], levier, FIN) - _emis(s0, levier, FIN)
    permanent = _emis(_bancs[(levier, 'permanent')][2], levier, FIN) - _emis(s0, levier, FIN)
    assert 0 < annee < permanent / 2, (annee, permanent)


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('ecriture', ['permanent', 'sous09'])
def test_i1_simulation_coefficient_constant_emissions_de_la_convention(levier, ecriture, _bancs):
    """(d) En simulation, coefficient constant (gel permanent, sous-indexation
    permanente à 0,9) : émissions PUBLIÉES = convention, au bit — rien avant le
    début (droit en vigueur), g l'année du début, puis le flux ; en mode
    historique, dès 2026."""
    coef = 0.0 if ecriture == 'permanent' else 0.9
    g = _g(levier, coef)
    for debut, (_, r, _s) in ((DEBUT, _bancs[(levier, ecriture)]),
                              (C.POLICY_START_YEAR, _simuler(*_gel([levier], coef=coef), annee_debut=None))):
        emis = {b['Année']: b[levier]['gini'] for b in r['measure_impacts_by_year']
                if isinstance(b.get(levier), dict)}
        assert emis == {debut: g, **{a: g * _flux(levier) for a in range(debut + 1, 2036)}}, debut


def _memes_euros(sim, s0, leviers, annee=FIN):
    """Programme en MONTANT (prestations_menages) qui retire en ``annee`` les
    mêmes euros que l'écriture en coefficient."""
    montant = {}
    if 'retraites' in leviers:
        montant['pensions'] = _depense(sim, 'retraites', annee) - _depense(s0, 'retraites', annee)
    if 'prestations_indexation' in leviers:
        montant['solidarite'] = (_depense(sim, 'prestations_indexation', annee)
                                 - _depense(s0, 'prestations_indexation', annee))
    return {'prestations_menages': montant}


def _emis_total(sim, s0, jusqu_a=FIN):
    leviers = ('retraites', 'prestations_indexation', 'prestations_menages')
    return sum(_emis(sim, l, jusqu_a) - _emis(s0, l, jusqu_a) for l in leviers)


@pytest.mark.parametrize('nom', ['deux', 'retraites', 'prestations_indexation'])
def test_i1_memes_euros_facteur_borne_par_la_sous_indexation_permanente(nom, _bancs):
    """(a) Mêmes euros de 2032, écrits en gel d'une année ou en montant
    (prestations_menages) : le facteur entre les deux Gini (émis jusqu'en 2032)
    est borné par celui que la sous-indexation PERMANENTE du même levier a déjà
    contre le montant — écart des règles par Md€ des deux leviers, antérieur à
    la passe (aligné par construction pour les pensions, GINI_PENSIONS_PAR_MD ;
    environ 14 pour les prestations, au backlog) ; le calendrier ne l'aggrave
    jamais. Borne basse : le gel garde sa part réalisée (1/N par revalorisation
    contre cinq revalorisations de la sous-indexation permanente en 2032), au
    moins le quart du facteur permanent. Avant : 35 fois pour les deux leviers,
    contre 7 pour la sous-indexation permanente."""
    leviers = list(LEVIERS) if nom == 'deux' else [nom]
    s0 = _bancs['sq'][2]
    facteurs = {}
    for ecriture in ('annee', 'sous09'):
        s = _bancs[(nom, ecriture)][2]
        _, rm, sm = _simuler(_memes_euros(s, s0, leviers))
        assert rm['valid'] is True, rm['warnings']
        montant = _emis_total(sm, s0)
        assert montant > 0, ('NON_VACUITE', ecriture, montant)
        facteurs[ecriture] = _emis_total(s, s0) / montant
    assert facteurs['sous09'] / 4 <= facteurs['annee'] <= facteurs['sous09'], facteurs


def _droit_indexation(idx, tmp_path):
    droit = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                       .read_text(encoding='utf-8'))
    droit['mesures']['retraites']['indexation'] = idx
    droit['mesures']['prestations_indexation']['taux_indexation'] = idx
    chemin = tmp_path / f'droit_{idx}.json'
    chemin.write_text(json.dumps(droit, ensure_ascii=False), encoding='utf-8')
    return chemin


def test_i1_continuite_entre_droit_a_1_0_9999_et_0_9(monkeypatch, tmp_path):
    """(b) Droit en vigueur (fichier remplaçable sans code) à 1,0, 0,9999 et
    0,9 : le gel 2028 des deux coefficients émet, net du statu quo de ce droit,
    (g(0) − g(droit)) / N par levier — proportionnel à l'écart gelé, continu ;
    et le Gini publié en 2032 suit, à la précision du calcul (avant : 0,0165 à
    1,0 contre 0,0013 à 0,9999)."""
    _pleine_precision(monkeypatch)
    deltas = {}
    for idx in (1.0, 0.9999, 0.9):
        monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', _droit_indexation(idx, tmp_path))
        cadre.vider_caches()
        try:
            d0, _, s0 = _simuler({})
            d, r, s = _simuler(*_gel(list(LEVIERS), annee=DEBUT))
        finally:
            cadre.vider_caches()
        assert r['valid'] is True, r['warnings']
        for levier in LEVIERS:
            emis = _emis(s, levier) - _emis(s0, levier)
            attendu = (_g(levier, 0.0) - _g(levier, idx)) / _plateau(levier)
            assert emis == pytest.approx(attendu, rel=1e-9), (idx, levier, emis, attendu)
        deltas[idx] = d.at[FIN, 'Gini'] - d0.at[FIN, 'Gini']
    monkeypatch.undo()
    cadre.vider_caches()
    assert deltas[1.0] > 0
    assert deltas[0.9999] == pytest.approx(deltas[1.0], rel=1e-3), deltas
    assert deltas[0.9] == pytest.approx(0.9 * deltas[1.0], rel=0.05), deltas


def test_i1_valeur_datee_du_droit_regle_d_increment_et_part_du_gel(monkeypatch, tmp_path):
    """Droit en vigueur avec une valeur datée des deux coefficients (1,0 jusqu'en
    2029, 0,9 ensuite) : le statu quo suit la règle d'incrément au changement de
    sa référence (émis en 2030 : g(0,9), jamais une part « gardée ») ; un gel
    2028 garde toujours g(0) / N net du statu quo (le retour de 2029 est à la
    référence de 2029, le passage à 0,9 en 2030 suit le droit)."""
    droit = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                       .read_text(encoding='utf-8'))
    droit['valeurs_datees'] = {levier: {param: [
        {'de': 2026, 'a': 2029, 'valeur': 1.0, 'source': 'banc'},
        {'de': 2030, 'valeur': 0.9, 'source': 'banc'}]} for levier, (param, _) in LEVIERS.items()}
    chemin = tmp_path / 'droit_date.json'
    chemin.write_text(json.dumps(droit, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
    cadre.vider_caches()
    try:
        _, _, s0 = _simuler({})
        _, r, s = _simuler(*_gel(list(LEVIERS), annee=DEBUT))
    finally:
        monkeypatch.undo()
        cadre.vider_caches()
    assert r['valid'] is True, r['warnings']
    for levier in LEVIERS:
        assert s0.sonde[(2030, levier)][2]['gini'] == pytest.approx(_g(levier, 0.9), rel=1e-12)
        emis = _emis(s, levier) - _emis(s0, levier)
        assert emis == pytest.approx(_g(levier, 0.0) / _plateau(levier), rel=1e-9), (levier, emis)


def test_i1_methodologie_et_changelog_disent_l_ordre_de_grandeur():
    texte = (RACINE_MOTEUR / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    assert 'min(k, N)/N' in texte
    assert 'majore vraisemblablement' not in texte
    changelog = (RACINE_MOTEUR / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert 'jamais rendu' not in changelog
    assert 'min(k, N)/N' in changelog


# ===========================================================================
# m-b. Infobulle de la prévention
# ===========================================================================

def test_mb_infobulle_prevention_le_curseur_borne_la_depense():
    """Le curseur borne la DÉPENSE de prévention (PARAM_DOMAINS : 7,5 à 11,2,
    422 en strict au-delà) ; un effort supplémentaire se saisit en dépense de
    soins (curseur nommé), sans retour modélisé."""
    tooltip = REGISTRE['sante']['parametres']['prevention_budget']['tooltip']
    assert 'pas de la dépense' not in tooltip, tooltip
    assert C.PARAM_DOMAINS['sante']['prevention_budget'] == (7.5, 11.2)
    assert 'borne la dépense de prévention à 11,2 Md€' in tooltip, tooltip
    soins = REGISTRE['depenses_publiques']['parametres']['ondam']['label'].rsplit(' (', 1)[0]
    assert f'« {soins} »' in tooltip, (soins, tooltip)
    assert 'sans retour modélisé' in tooltip, tooltip
    assert 'hypothèse haute' in tooltip and '8 731' in tooltip, tooltip


# ===========================================================================
# m-c. Calendrier trop long : profil et alias, même comportement
# ===========================================================================

CLE_M5 = 'defense.budget'
PROG_M5 = {'defense': {'budget': 70}}


@pytest.mark.parametrize('debut, annees, borne', [(2028, 6, 5), (2031, 6, 2), (2032, 3, 1),
                                                  (2030, 0, 1)])
def test_mc_profil_et_alias_ramenes_a_la_borne_traces(debut, annees, borne):
    """Tolérant : un profil « rampe » trop long est ramené à la borne et tracé,
    exactement comme l'alias ``rampe`` (avant : profil ignoré, programme en
    plein dès le début ; alias ramené) ; mêmes mesures chaque année."""
    corr_p, corr_a = {}, {}
    p = cadre.CadreTemporel.preparer(PROG_M5, debut, profils={CLE_M5: {'forme': 'rampe', 'annees': annees}},
                                     strict=False, warned=set(), corrections=corr_p)
    a = cadre.CadreTemporel.preparer(PROG_M5, debut, rampe={'annees': annees, 'leviers': [CLE_M5]},
                                     strict=False, warned=set(), corrections=corr_a)
    assert a.etat.rampe.annees == borne
    assert CLE_M5 in p.etat.profils and p.etat.profils[CLE_M5].annees == borne, p.etat.profils
    for an in range(debut, 2036):
        assert p.mesures_de_l_annee(an) == a.mesures_de_l_annee(an), an
    for corrections in (corr_p, corr_a):
        textes = ' '.join(str(v) for v in corrections.values())
        assert f'ramenée à {borne}' in textes, corrections


@pytest.mark.parametrize('demande', ['profils', 'rampe'])
def test_mc_strict_message_exact_sans_ramene(demande):
    """Strict : refus, avec le domaine et la raison ; jamais « ramenée à »."""
    kw = ({'profils': {CLE_M5: {'forme': 'rampe', 'annees': 6}}} if demande == 'profils'
          else {'rampe': {'annees': 6, 'leviers': [CLE_M5]}})
    with pytest.raises((cadre.ProfilInvalide, cadre.RampeInvalide)) as e:
        cadre.CadreTemporel.preparer(PROG_M5, 2028, strict=True, **kw)
    message = str(e.value)
    assert 'annees = 6 hors de [1 ; 5] (la rampe finit au plus tard en 2032)' in message, message
    assert 'ramen' not in message, message


def test_mc_simulation_profil_trop_long_rapport_invalide_calendrier_publie(monkeypatch):
    """Simulation tolérante : rapport invalide (correction), calendrier publié
    avec la durée ramenée, cible atteinte en 2032."""
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    df, _, rapport = BudgetSimulatorV45(periods=10, mesures=PROG_M5, annee_debut=2028,
                                        profils={CLE_M5: {'forme': 'rampe', 'annees': 6}}).simulate()
    assert rapport['valid'] is False
    prof = rapport['cadre']['profils'][CLE_M5]
    assert prof['annees'] == 5 and prof['valeurs'][str(FIN)] == 70, prof
    assert prof['valeurs'][str(DEBUT)] < 70, prof


# ===========================================================================
# H-1. Entier géant sur la réforme de la fonction publique : 422, jamais 500
# ===========================================================================

def _client(monkeypatch, strict):
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('api_relecture_finale', RACINE / 'api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('param', ['fusion_agences', 'digitalisation'])
@pytest.mark.parametrize('signe', [1, -1])
@pytest.mark.parametrize('debut', [DEBUT, 2031])
def test_h1_entier_geant_reforme_fp_422_en_strict_200_en_tolerant(monkeypatch, param, signe, debut):
    corps = {'periods': 10, 'annee_debut': debut,
             'mesures': {'fonction_publique_reforme': {param: signe * 10 ** 400}}}
    r = _client(monkeypatch, '1').post('/simulate', json=corps)
    assert r.status_code == 422, r.text[:300]
    r = _client(monkeypatch, '').post('/simulate', json=corps)
    assert r.status_code == 200, r.text[:300]
    assert r.json()['report']['valid'] is False


@pytest.mark.parametrize('valeur', [10 ** 400, -10 ** 400, math.inf, -math.inf, math.nan])
def test_h1_lecteur_lateral_valeur_non_finie_comme_cle_absente(valeur):
    """Le lecteur latéral du vivier (effectifs) lit la réforme BRUTE : une valeur
    non finie ou hors des flottants y vaut la clé absente — ce que la porte des
    valeurs fait de la même entrée (clé retirée en tolérant, refus en strict) —
    au lieu de lever (entier géant) ou d'emporter le taux à son maximum (inf)."""
    def stock(reforme):
        sim = _sim_neuf()
        sim.mesures = {'fonction_publique_reforme': reforme}
        return sim._reforme_fp_reduction_cumulee(2030)
    assert stock({'fusion_agences': valeur, 'digitalisation': 30}) == stock({'digitalisation': 30})
    assert stock({'fusion_agences': 30, 'digitalisation': 30}) > stock({'digitalisation': 30}) > 0
