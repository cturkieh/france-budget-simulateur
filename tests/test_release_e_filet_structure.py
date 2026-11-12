"""Release E — filet de croissance publié en bloc structuré. Tests écrits AVANT
le code (TDD).

Le filet [−3,5 % ; +2,5 %] de la croissance réelle annuelle n'était lisible que
dans une phrase de ``report.warnings`` (« Avis — filet de croissance … atteint :
2030 (2,87 % calculés, 2,50 % retenus) … »). Un écran devait donc analyser une
phrase. Désormais, le bloc ``cadre.filet_croissance`` publie la même
information, à côté de l'avis inchangé, comme ``cadre.plafond_total`` le fait
pour le plafond de l'impact total :

    {"borne_min_pct": -3.5, "borne_max_pct": 2.5,
     "annees": [2029, …],
     "ecretages": [{"annee": 2029, "croissance_calculee_pct": 3.4381,
                    "croissance_retenue_pct": 2.5}, …]}

Toujours émis (listes vides si le filet ne mord pas), dans les deux modes. Les
sorties numériques ne changent pas (bloc de rapport seul).

Règle d'écriture : chaque valeur attendue est dérivée des constantes nommées de
``constants.py`` ou de l'avis texte du même calcul, jamais recopiée d'une sortie
du moteur.
"""
import importlib.util
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
API_FILE = RACINE / 'api.py'
DEBUT_CADRE = C.ANNEE_PREMIER_BUDGET_MANDAT

# Programme de relance dont la croissance calculée dépasse la borne haute
# (même programme que le test de l'avis, m6, test_release_e_arbitrages.py).
PROGRAMME_RELANCE = {'transition_ecologique': {'investissement': 50, 'renovation': 40},
                     'recherche_publique': {'budget': 20}, 'collectivites': {'investissement': 20},
                     'depenses_publiques': {'credits_etat': 20}}

CLES = {'borne_min_pct', 'borne_max_pct', 'annees', 'ecretages'}
CLES_ECRETAGE = {'annee', 'croissance_calculee_pct', 'croissance_retenue_pct'}
MODES = pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])


def _simuler(mesures, annee_debut):
    return BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()


def _avis_filet(rapport):
    return [w for w in rapport['warnings'] if w.startswith('Avis') and 'filet de croissance' in w]


def _pct_avis(texte):
    return float(texte.replace('−', '-').replace(',', '.'))


def _bornes_pct():
    return round(C.CROISSANCE_FILET_MIN * 100, 6), round(C.CROISSANCE_FILET_MAX * 100, 6)


@MODES
def test_bloc_toujours_emis_vide_sans_ecretage(annee_debut):
    _, _, rapport = _simuler({}, annee_debut)
    bloc = rapport['cadre']['filet_croissance']
    assert set(bloc) == CLES
    assert (bloc['borne_min_pct'], bloc['borne_max_pct']) == _bornes_pct()
    assert bloc['annees'] == [] and bloc['ecretages'] == []
    assert _avis_filet(rapport) == []


@MODES
def test_bloc_et_avis_disent_la_meme_chose(annee_debut):
    """Même calcul, deux écritures : chaque écrêtage du bloc est l'année et les
    deux valeurs de l'avis texte (à l'arrondi de l'avis), dans le même ordre."""
    _, _, rapport = _simuler(PROGRAMME_RELANCE, annee_debut)
    bloc = rapport['cadre']['filet_croissance']
    assert bloc['ecretages'], ('NON_VACUITE', rapport['warnings'])
    avis = _avis_filet(rapport)
    assert len(avis) == 1, rapport['warnings']
    du_texte = [(int(a), _pct_avis(c), _pct_avis(r)) for a, c, r in
                re.findall(r'(\d{4}) \(([−\d,]+) % calculés, ([−\d,]+) % retenus\)', avis[0])]
    assert [e['annee'] for e in bloc['ecretages']] == [a for a, _, _ in du_texte], avis[0]
    for e, (_, calculee, retenue) in zip(bloc['ecretages'], du_texte):
        # L'avis arrondit à 2 décimales, le bloc à 4 : écart au plus d'un demi-centième.
        assert abs(e['croissance_calculee_pct'] - calculee) <= 0.005 + 1e-9, (e, avis[0])
        assert abs(e['croissance_retenue_pct'] - retenue) <= 0.005 + 1e-9, (e, avis[0])
    for e in bloc['ecretages']:
        assert set(e) == CLES_ECRETAGE
        assert isinstance(e['annee'], int)


@MODES
def test_valeurs_retenues_a_la_borne_et_calculees_au_dela(annee_debut):
    df, _, rapport = _simuler(PROGRAMME_RELANCE, annee_debut)
    bloc = rapport['cadre']['filet_croissance']
    bas, haut = _bornes_pct()
    croissance = df.set_index('Année')['Croissance %']
    assert bloc['ecretages'], 'NON_VACUITE'
    for e in bloc['ecretages']:
        assert e['croissance_retenue_pct'] in (bas, haut), e
        if e['croissance_retenue_pct'] == haut:
            assert e['croissance_calculee_pct'] > haut, e
        else:
            assert e['croissance_calculee_pct'] < bas, e
        # La croissance publiée de l'année est la valeur retenue.
        assert croissance[e['annee']] == pytest.approx(e['croissance_retenue_pct'], abs=0.005), e


@MODES
def test_annees_uniques_croissantes_et_egales_aux_ecretages(annee_debut):
    _, _, rapport = _simuler(PROGRAMME_RELANCE, annee_debut)
    bloc = rapport['cadre']['filet_croissance']
    annees = [e['annee'] for e in bloc['ecretages']]
    assert bloc['annees'] == annees
    assert annees == sorted(set(annees)), annees


def test_borne_basse_et_arrondi_par_le_rapport():
    """Borne basse (aucun programme admis ne l'atteint aujourd'hui) : le
    rapport publie l'écrêtage tel que le journal du filet le consigne, en %
    arrondi à 4 décimales, valeur retenue à la borne."""
    bas, haut = _bornes_pct()
    journal = [(2029, -0.0412345678, C.CROISSANCE_FILET_MIN), (2031, 0.0301, C.CROISSANCE_FILET_MAX)]
    bloc = cadre.CadreTemporel.preparer({}, None).rapport(None, [], filet_croissance=journal)['filet_croissance']
    assert bloc == {'borne_min_pct': bas, 'borne_max_pct': haut, 'annees': [2029, 2031],
                    'ecretages': [{'annee': 2029, 'croissance_calculee_pct': -4.1235,
                                   'croissance_retenue_pct': bas},
                                  {'annee': 2031, 'croissance_calculee_pct': 3.01,
                                   'croissance_retenue_pct': haut}]}


def test_rapport_sans_journal_garde_sa_signature():
    """Appel existant ``rapport(journal, annees)`` : bloc vide, aucune erreur."""
    bloc = cadre.CadreTemporel.preparer({}, None).rapport(None, [2030])['filet_croissance']
    assert bloc['annees'] == [] and bloc['ecretages'] == []


@pytest.fixture(scope='module')
def client():
    spec = importlib.util.spec_from_file_location('api_filet_structure', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('strict', ['', '1'], ids=['tolerant', 'strict'])
def test_api_publie_le_bloc(client, monkeypatch, strict):
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    r = client.post('/simulate', json={'mesures': PROGRAMME_RELANCE, 'annee_debut': DEBUT_CADRE})
    assert r.status_code == 200, r.text
    corps = r.json()
    bloc = corps['cadre']['filet_croissance']
    assert set(bloc) == CLES and bloc['ecretages'], bloc
    assert bloc['annees'] == [e['annee'] for e in bloc['ecretages']]
    assert all(a >= DEBUT_CADRE for a in bloc['annees']), bloc
    vide = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT_CADRE})
    assert vide.status_code == 200, vide.text
    assert vide.json()['cadre']['filet_croissance']['ecretages'] == []
