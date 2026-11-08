"""v0.7.0, lot A — « mesures de l'année » et année de début par scénario.

Contrat (dossier du dépôt parent ``docs/plans/passe-cadre-2027-2032.md`` § 2.1,
décisions du 07/11/2026) :

- ``annee_debut`` absent ou égal à 2026 = MODE HISTORIQUE : le programme
  s'applique dès 2026, exactement comme en v0.6.11 (propriété f) ;
- ``annee_debut`` ∈ [2027 ; 2032] = MODE CADRE : avant cette année, le moteur
  applique le DROIT EN VIGUEUR (fichier de données
  ``budget_simulator/data/droit_en_vigueur.json``), le programme ensuite ;
- un point UNIQUE : ``self.mesures`` est remplacé en tête d'année par les
  mesures de l'année, que lisent ``apply_measures`` ET les lecteurs latéraux
  (offre et chômage seniors, effet d'offre, ASU, point d'indice, réforme FP) ;
- un levier absent du programme (ou ``null``) hérite du droit en vigueur ;
- validation : hors [2026 ; 2032] ou non entier → 422 en strict, correction
  tracée (``report.valid = false``) en tolérant.

Propriétés : (a) tout programme est bit-identique au droit en vigueur avant
``annee_debut`` (8 colonnes, détails, impacts par levier) ; (f) champs absents :
sortie de v0.6.11 (golden masters inchangés + égalité absent = 2026) ;
(g) statu quo du cadre = statu quo historique, au bit.
"""
import copy
import importlib.util
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.engine.cadre as cadre
import budget_simulator.engine.growth as growth_mod
import budget_simulator.engine.unemployment as unemployment_mod
import budget_simulator.handlers.additionnels as additionnels_mod
import budget_simulator.handlers.depenses as depenses_mod
import budget_simulator.handlers.efficience as efficience_mod
from budget_simulator import EntreeInvalide
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import (CAS, DROIT_REAJUSTE, NOMS, NOMS_PROGRAMMES, PROGRAMME_MIXTE, SCENARIOS, atterrissage,
                           egalite_bit_a_bit, simuler)

API_FILE = Path(__file__).resolve().parent.parent / 'api.py'
FRONT_SCENARIOS = (Path(__file__).absolute().parent.parent / 'frontend-react' / 'src' / 'data'
                   / 'scenarios.json')
DEBUT = 2028


def _droit():
    return cadre.charger_droit_en_vigueur().mesures


# ---------------------------------------------------------------------------
# Le droit en vigueur : un fichier de données, validé, égal au budget voté
# ---------------------------------------------------------------------------

def test_droit_en_vigueur_charge_et_valide():
    droit = cadre.charger_droit_en_vigueur()
    assert droit.identifiant and droit.libelle and droit.source and droit.date
    assert droit.mesures, "droit en vigueur vide"
    # Validé : la porte d'entrée n'y corrige rien (objet identique, aucune correction).
    corrections, avis = {}, {}
    from budget_simulator.engine._param_domain import assainir_mesures
    assert assainir_mesures(droit.mesures, strict=False, warned=set(),
                            corrections=corrections, avis=avis) is droit.mesures
    assert corrections == {} and avis == {}


@pytest.mark.skipif(not FRONT_SCENARIOS.exists(), reason='frontend-react/ hors périmètre fork moteur seul')
def test_garde_le_budget_vote_de_l_app_egal_au_droit_en_vigueur():
    """Garde de synchronisation : le scénario « Budget 2026 voté, réajusté sur l'exécution 2026 » de
    l'app EST le droit en vigueur du moteur RÉAJUSTÉ sur l'atterrissage observé
    (voté ⊕ ``reajustements_droit_en_vigueur`` de toutes les années observées),
    c'est-à-dire le point de départ commun du mode cadre (décision du mainteneur du
    08/11/2026 : le scénario reste égal au statu quo, avec ou sans pont). Le jour
    où un budget 2027 est voté, on remplace le fichier de données ET le scénario,
    ensemble ; un nouveau réajustement de l'atterrissage se reporte au scénario."""
    app = json.loads(FRONT_SCENARIOS.read_text(encoding='utf-8'))['plf_2026']['apiMeasures']
    att = cadre.charger_atterrissage()
    attendu = cadre.droit_reajuste(_droit(), att, max(att.annees))
    assert app == attendu
    # Le réajustement est réel : le scénario n'est plus le voté brut.
    assert app != _droit()


@pytest.mark.parametrize('defaut, motif', [
    ({'mesures': {'levier_inconnu': {'x': 1}}}, 'levier'),
    ({'mesures': {'tva_rate': {'tauxx': 0.2}}}, 'tauxx'),
    ({'mesures': {'tva_rate': {'taux': 20}}}, 'tva_rate'),
    ({'mesures': {'csg': {'taux': float('nan')}}}, 'csg'),
    ({'mesures': {'tva_rate': None}}, 'tva_rate'),
    ({'identifiant': ''}, 'identifiant'),
    ({'date': '07/11/2026'}, 'date'),
    ({'mesures': []}, 'mesures'),
])
def test_droit_en_vigueur_invalide_est_un_defaut_serveur(tmp_path, monkeypatch, defaut, motif):
    """Une donnée serveur invalide n'est JAMAIS une faute de l'appelant :
    RuntimeError (500 + ERROR côté API), jamais 422 ni correction silencieuse."""
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    contenu.update(copy.deepcopy(defaut))
    chemin = tmp_path / 'droit.json'
    chemin.write_text(json.dumps(contenu), encoding='utf-8')
    monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
    cadre.vider_caches()
    try:
        with pytest.raises(RuntimeError, match=motif):
            cadre.charger_droit_en_vigueur()
    finally:
        cadre.vider_caches()


# ---------------------------------------------------------------------------
# Mesures de l'année : fonction pure
# ---------------------------------------------------------------------------

def test_mesures_de_l_annee_avant_et_apres_le_debut():
    droit = _droit()
    prog = copy.deepcopy(droit)
    prog['defense'] = {'budget': 70}
    prog['rabot_uniforme'] = {'taux_reduction': 0.02}
    del prog['collectivites']             # absent : hérite du droit
    prog['csg'] = None                     # null : hérite du droit
    with atterrissage({}):                 # mécanique du lot A, sans réajustement (lot E)
        c = cadre.CadreTemporel.preparer(prog, DEBUT, droit=cadre.charger_droit_en_vigueur())
    assert c.etat.mesures_droit == droit and c.etat.mesures_droit is not droit  # copie par simulation
    for an in (2026, 2027):
        assert c.mesures_de_l_annee(an) is c.etat.mesures_droit
    m = c.mesures_de_l_annee(DEBUT)
    assert m['defense'] == {'budget': 70}
    assert m['rabot_uniforme'] == {'taux_reduction': 0.02}
    assert m['collectivites'] == droit['collectivites']
    assert m['csg'] == droit['csg']
    assert all(c.mesures_de_l_annee(an) is m for an in range(DEBUT, 2036))
    assert c.leviers_modifies == frozenset({'defense', 'rabot_uniforme'})


@pytest.mark.parametrize('annee_debut', [None, 2026])
def test_mode_historique_rend_le_programme_tel_quel(annee_debut):
    prog = {'defense': {'budget': 70}}
    c = cadre.CadreTemporel.preparer(prog, annee_debut)
    assert c.mode == 'historique' and c.annee_debut == 2026
    assert all(c.mesures_de_l_annee(an) is prog for an in range(2026, 2036))


# ---------------------------------------------------------------------------
# (f) rétrocompatibilité : champ absent = 2026 = v0.6.11
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nom', NOMS)
def test_f_annee_debut_absente_egale_2026_au_bit(nom):
    """Absent et 2026 : même chemin, même sortie au bit. Que cette sortie soit
    celle de v0.6.11 est prouvé par les golden masters, inchangés
    (``test_golden_master_full.py``, ``test_handler_coverage.py``)."""
    egalite_bit_a_bit(simuler(CAS[nom]), simuler(CAS[nom], annee_debut=2026), libelle=nom)


def test_f_mode_historique_n_utilise_pas_le_droit_en_vigueur(monkeypatch):
    """Le mode historique ne lit même pas le fichier : un droit en vigueur cassé
    ne peut pas dégrader une requête sans ``annee_debut``."""
    def interdit():
        raise AssertionError("droit en vigueur lu en mode historique")
    monkeypatch.setattr(cadre, 'charger_droit_en_vigueur', interdit)
    simuler(PROGRAMME_MIXTE)
    simuler(PROGRAMME_MIXTE, annee_debut=2026)


# ---------------------------------------------------------------------------
# (a) avant annee_debut, tout programme EST le droit en vigueur
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def statu_quo_cadre():
    return {debut: simuler(_droit(), annee_debut=debut) for debut in (2027, DEBUT, 2032)}


@pytest.mark.parametrize('debut', [2027, DEBUT, 2032])
@pytest.mark.parametrize('nom', NOMS_PROGRAMMES)
def test_a_programme_bit_identique_au_droit_avant_le_debut(nom, debut, statu_quo_cadre):
    egalite_bit_a_bit(simuler(CAS[nom], annee_debut=debut), statu_quo_cadre[debut],
                      annees=range(2025, debut), libelle=f'{nom}/{debut}')


@pytest.mark.parametrize('nom', NOMS_PROGRAMMES)
def test_a_le_programme_s_applique_a_partir_du_debut(nom, statu_quo_cadre):
    """Contre-épreuve : l'égalité avant le début n'est pas l'absence de programme."""
    df_p = simuler(CAS[nom], annee_debut=DEBUT)[0].set_index('Année')
    df_s = statu_quo_cadre[DEBUT][0].set_index('Année')
    assert any(df_p.at[an, 'Dette/PIB %'] != df_s.at[an, 'Dette/PIB %']
               for an in range(DEBUT, 2036)), nom


# ---------------------------------------------------------------------------
# (g) statu quo du cadre = statu quo historique
# ---------------------------------------------------------------------------

def test_g_statu_quo_cadre_egal_statu_quo_historique_au_bit():
    """Le budget voté, rejoué en mode cadre (droit = programme), est au bit le
    budget voté historique, tables d'atterrissage vides (lot E : avec
    l'atterrissage, 2026 est injecté — test_cadre_v070_atterrissage.py)."""
    historique = simuler(_droit())
    with atterrissage({}):
        for debut in (2027, DEBUT, 2032):
            egalite_bit_a_bit(historique, simuler(_droit(), annee_debut=debut), libelle=str(debut))


def test_g_programme_vide_en_cadre_est_le_droit_en_vigueur():
    """``{}`` en mode cadre = « rien ne change » = le droit en vigueur RÉAJUSTÉ
    (≠ défauts du moteur, sens historique de ``{}``). v0.7.2, présent = imposé :
    le droit réajusté posé explicitement, et ``plf_2026`` (« Budget 2026 voté,
    réajusté sur l'exécution 2026 ») quand scenarios.json est là, sont le statu
    quo au bit ; le voté
    BRUT posé explicitement n'est plus le statu quo (57 / 100 / 7,3 imposés)."""
    vide = simuler({}, annee_debut=DEBUT)
    egalite_bit_a_bit(vide, simuler(copy.deepcopy(DROIT_REAJUSTE), annee_debut=DEBUT))
    if SCENARIOS:
        egalite_bit_a_bit(vide, simuler(SCENARIOS['plf_2026'], annee_debut=DEBUT))
    assert _droit() != DROIT_REAJUSTE
    _, _, rapport_vote, _ = simuler(_droit(), annee_debut=DEBUT)
    assert set(rapport_vote['cadre']['leviers_modifies']) == {
        levier for levier in DROIT_REAJUSTE if DROIT_REAJUSTE[levier] != _droit().get(levier)}


# ---------------------------------------------------------------------------
# Un point unique : les lecteurs latéraux lisent les mesures de l'année
# ---------------------------------------------------------------------------

def test_lecteurs_lateraux_lisent_les_mesures_de_l_annee(monkeypatch):
    """Les 8 lecteurs latéraux du dossier (§ 1) reçoivent le droit en vigueur
    avant le début et le programme ensuite — jamais le programme dès 2026."""
    vus = {}

    def espion(nom, vraie, position_mesures=0, cle_annee=None):
        def f(*args, **kwargs):
            mesures = args[position_mesures]
            vus.setdefault(nom, []).append(mesures)
            return vraie(*args, **kwargs)
        return f

    monkeypatch.setattr(growth_mod, 'offre_seniors_niveau_pib',
                        espion('offre_seniors', growth_mod.offre_seniors_niveau_pib))
    monkeypatch.setattr(unemployment_mod, 'chomage_seniors_ecart',
                        espion('chomage_seniors', unemployment_mod.chomage_seniors_ecart))
    monkeypatch.setattr(growth_mod, 'valeur_brute',
                        espion('effet_offre', growth_mod.valeur_brute))
    monkeypatch.setattr(efficience_mod, 'asu_phasing',
                        espion('asu_fraude', efficience_mod.asu_phasing))
    monkeypatch.setattr(depenses_mod, 'asu_phasing',
                        espion('asu', depenses_mod.asu_phasing))
    monkeypatch.setattr(depenses_mod, 'asu_is_active',
                        espion('asu_prestations', depenses_mod.asu_is_active))
    monkeypatch.setattr(additionnels_mod, '_point_indice_fp_brut',
                        espion('point_indice', additionnels_mod._point_indice_fp_brut))
    vrai_reforme = BudgetSimulatorV45._reforme_fp_reduction_cumulee

    class Sim(BudgetSimulatorV45):
        def _reforme_fp_reduction_cumulee(self, year):
            vus.setdefault('reforme_fp', []).append(self.mesures)
            return vrai_reforme(self, year)

    annees = {}

    class SimAnnee(Sim):
        def update_labour_supply(self, year):
            annees[year] = self.mesures
            return super().update_labour_supply(year)

    sim = SimAnnee(periods=10, mesures=copy.deepcopy(PROGRAMME_MIXTE), annee_debut=DEBUT)
    with atterrissage({}):                 # droit voté tel quel (réajustements : lot E)
        sim.simulate()
    droit = _droit()
    assert set(vus) == {'offre_seniors', 'chomage_seniors', 'effet_offre', 'asu_fraude',
                        'asu', 'asu_prestations', 'point_indice', 'reforme_fp'}, set(vus)
    for an, mesures in annees.items():
        if an < DEBUT:
            assert mesures == droit, an
        else:
            assert mesures['asu'] == PROGRAMME_MIXTE['asu'], an
    autorises = {id(m) for m in annees.values()}
    for nom, liste in vus.items():
        assert all(id(m) in autorises for m in liste), nom


# ---------------------------------------------------------------------------
# Validation de annee_debut (moteur et API)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('valeur', [2025, 2033, 1900, True, 2028.0, '2028', [2028]])
def test_annee_debut_invalide_strict_entree_invalide(valeur):
    with pytest.raises(EntreeInvalide, match='annee_debut'):
        simuler({}, strict=True, annee_debut=valeur)


@pytest.mark.parametrize('valeur, effective', [(2025, 2026), (2040, 2032), (1900, 2026)])
def test_annee_debut_hors_domaine_tolerant_ramenee_a_la_borne(valeur, effective, caplog):
    with caplog.at_level(logging.WARNING):
        df, det, rapport, sim = simuler(PROGRAMME_MIXTE, annee_debut=valeur)
    assert rapport['cadre']['annee_debut'] == effective
    assert rapport['valid'] is False
    assert any('annee_debut' in w for w in rapport['warnings'])
    assert any('annee_debut' in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize('valeur', [True, 2028.5, '2028'])
def test_annee_debut_non_entiere_tolerant_mode_historique(valeur):
    rapport = simuler(PROGRAMME_MIXTE, annee_debut=valeur)[2]
    assert rapport['cadre']['mode'] == 'historique'
    assert rapport['valid'] is False


@pytest.fixture(scope='module')
def api():
    spec = importlib.util.spec_from_file_location('api_cadre_v070', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(api):
    return TestClient(api.app, raise_server_exceptions=False)


def test_api_annee_debut_transmise_et_bloc_cadre(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    corps = client.post('/simulate', json={'mesures': PROGRAMME_MIXTE, 'annee_debut': DEBUT}).json()
    c = corps['cadre']
    assert c['annee_debut'] == DEBUT and c['mode'] == 'cadre'
    assert c['annees_droit_en_vigueur'] == list(range(2026, DEBUT))
    assert c['droit_en_vigueur']['identifiant'] == cadre.charger_droit_en_vigueur().identifiant
    assert 'tva_rate' in c['leviers_modifies']
    assert 'cadre' not in corps['report']


def test_api_sans_annee_debut_bloc_cadre_historique(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    corps = client.post('/simulate', json={'mesures': {}}).json()
    assert corps['cadre']['mode'] == 'historique' and corps['cadre']['annee_debut'] == 2026
    assert corps['cadre']['droit_en_vigueur'] is None


@pytest.mark.parametrize('valeur', ['2028', True, 2028.5, [2028]])
def test_api_annee_debut_non_entiere_422(client, valeur):
    r = client.post('/simulate', json={'mesures': {}, 'annee_debut': valeur})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize('valeur', [2025, 2033])
def test_api_annee_debut_hors_domaine(client, monkeypatch, valeur):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = client.post('/simulate', json={'mesures': {}, 'annee_debut': valeur})
    assert r.status_code == 422 and 'annee_debut' in r.json()['detail'], r.text
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    corps = client.post('/simulate', json={'mesures': {}, 'annee_debut': valeur}).json()
    assert corps['report']['valid'] is False


# ---------------------------------------------------------------------------
# RÉFUTEUR du lot A : tentatives de faire fuir le programme avant son début
# ---------------------------------------------------------------------------

REFUTATIONS = {
    # leviers absents du droit en vigueur (rabot) et bloc null
    'levier_absent_du_droit': {'rabot_uniforme': {'taux_reduction': 0.08}, 'csg': None},
    # valeur corrigée par la porte d'entrée (tolérant) : la correction ne doit
    # pas toucher les années de droit en vigueur
    'valeur_hors_domaine': {**PROGRAMME_MIXTE, 'education': {'budget': 10 ** 6}},
    # levier en échec (valeur non numérique) : l'échec n'existe pas avant le début
    'levier_en_echec': {**PROGRAMME_MIXTE, 'defense': {'budget': 'bad'}},
    # seul un lecteur latéral change (âge de départ) : offre et chômage seniors
    'lateral_seul': {'retraites': {'age_depart': 66.0, 'indexation': 1.0,
                                   'duree_cotisation': 42.5}},
    # bloc vide (tous défauts) : un avis, pas une fuite
    'bloc_vide': {'taxe_superprofits': {}},
}


@pytest.mark.parametrize('debut', [2027, DEBUT, 2032])
@pytest.mark.parametrize('nom', sorted(REFUTATIONS))
def test_refuteur_a_aucune_fuite_avant_le_debut(nom, debut, statu_quo_cadre):
    sortie = simuler(REFUTATIONS[nom], annee_debut=debut)
    egalite_bit_a_bit(sortie, statu_quo_cadre[debut], annees=range(2025, debut), libelle=nom)
    impacts = {y['Année']: y for y in sortie[2]['measure_impacts_by_year']}
    assert not any(v.get('_handler_failed') for an in range(2026, debut)
                   for v in impacts[an].values() if isinstance(v, dict)), nom


def test_refuteur_a_horizon_plus_court_que_le_debut():
    """periods = 1 avec un début en 2028 : toute la simulation est le droit."""
    egalite_bit_a_bit(simuler(PROGRAMME_MIXTE, periods=1, annee_debut=DEBUT),
                      simuler(_droit(), periods=1, annee_debut=DEBUT))


def test_refuteur_a_echec_strict_seulement_a_partir_du_debut():
    """En strict, un levier en échec lève l'année où il s'applique — le début —,
    pas en 2026 (le droit en vigueur, lui, est valide)."""
    with pytest.raises(BaseExceptionGroup) as exc:
        simuler({'defense': {'budget': 'bad'}}, strict=True, annee_debut=DEBUT)
    assert f'year={DEBUT}' in ''.join(exc.value.exceptions[0].__notes__)
