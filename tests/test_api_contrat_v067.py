"""v0.6.7 — contrat HTTP de /simulate et /scenarios (audit externe, oct. 2026).

Rouges sur v0.6.6 : TVA à 2 000 % → 200 `valid: true` avec un pouvoir d'achat
de −296 (et 200 même en strict) ; `defense.budget = "bad"` → 200 sans drapeau,
même en strict ; entier géant → 500 en tolérant ; erreur d'entrée en strict →
500 (la docstring promettait 422) ; `periods` jusqu'à 50 ; statu quo
`valid: false` ; exemple « scandinave » de /scenarios hors domaine (clampé en
tolérant, 500 en strict).

Chargé par chemin (comme test_api_safety) : depuis le dépôt parent, `import
api` désignerait l'API de production, qui INCLUT ce routeur.
"""
import importlib.util
import logging
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

API_FILE = Path(__file__).resolve().parent.parent / "api.py"
PA = "Pouvoir d'Achat"
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location("api_contrat_v067", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(api):
    return TestClient(api.app, raise_server_exceptions=False)


@pytest.fixture(params=['tolerant', 'strict'])
def mode(request, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1' if request.param == 'strict' else '')
    return request.param


def _post(client, mesures, periods=10):
    return client.post('/simulate', json={'mesures': mesures, 'periods': periods})


def _corrections(body):
    return [w for w in body['report']['warnings'] if w.startswith('Entrée ou sortie corrigée')]


@pytest.mark.parametrize('mesures,cle', [
    ({'tva_rate': {'taux': 20}}, 'tva_rate.taux'),
    ({'defense': {'budget': 'bad'}}, 'defense.budget'),   # formule ASTEVAL
    ({'csg': {'taux': 'bad'}}, 'csg.taux'),               # handler Python
    ({'csg': {'taux': 10 ** 400}}, 'csg.taux'),           # entier JSON géant
], ids=['tva_2000_pct', 'texte_asteval', 'texte_handler', 'entier_geant'])
def test_entree_invalide_jamais_silencieuse(client, mode, mesures, cle):
    r = _post(client, mesures)
    if mode == 'strict':
        assert r.status_code == 422, r.text
        assert cle in r.json()['detail']
        return
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['report']['valid'] is False
    assert _corrections(body), body['report']['warnings']
    assert all(row[PA] > 0 for row in body['results'])


def test_valeur_texte_drapeau_dans_les_impacts(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    body = _post(client, {'defense': {'budget': 'bad'}}).json()
    assert any(y.get('defense', {}).get('_handler_failed') for y in body['measure_impacts'])


def test_infini_json(client, mode):
    """`Infinity` (JSON non standard, accepté par le parseur) : retiré et
    signalé en tolérant, 422 en strict."""
    r = client.post('/simulate', content='{"mesures": {"csg": {"taux": Infinity}}, "periods": 10}',
                    headers={'content-type': 'application/json'})
    if mode == 'strict':
        assert r.status_code == 422, r.text
    else:
        assert r.status_code == 200 and r.json()['report']['valid'] is False


def test_statu_quo_valide(client, mode):
    body = _post(client, {}).json()
    assert body['report']['valid'] is True and not _corrections(body)


def test_bloc_vide_avis(client, mode):
    body = _post(client, {'taxe_superprofits': {}}).json()
    assert body['report']['valid'] is True
    assert any(w.startswith('Avis — taxe_superprofits={}') for w in body['report']['warnings'])


@pytest.mark.parametrize('mesures', [{'foo': {}}, {'tva_rat': {'taux': 0.2}}, {'foo': None}])
def test_levier_inconnu_422(client, mode, mesures):
    r = _post(client, mesures)
    assert r.status_code == 422 and 'Leviers inconnus' in r.json()['detail']


@pytest.mark.parametrize('periods,attendu', [(0, 422), (1, 200), (10, 200), (11, 422), (50, 422)])
def test_horizon_plafonne_a_10_ans(client, periods, attendu):
    assert _post(client, {}, periods=periods).status_code == attendu


def test_chaque_scenario_d_exemple_passe_en_strict_sans_correction(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    scenarios = client.get('/scenarios').json()
    assert {'status_quo', 'austerite', 'scandinave', 'relance_verte'} <= set(scenarios)
    for nom, mesures in scenarios.items():
        r = _post(client, mesures)
        assert r.status_code == 200, (nom, r.text)
        assert r.json()['report']['valid'] is True, (nom, r.json()['report']['warnings'])


def test_bug_moteur_en_strict_500_et_pas_422(client, api, monkeypatch):
    """Un ExceptionGroup qui contient un VRAI bug ne se déguise pas en faute
    client."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')

    def _boom(*args, **kwargs):
        raise RuntimeError("boom-test")

    original = api.BudgetSimulatorV45.__init__

    def _init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.measure_handlers['csg'] = _boom

    monkeypatch.setattr(api.BudgetSimulatorV45, '__init__', _init)
    r = _post(client, {'csg': {'taux': 0.1}})
    assert r.status_code == 500, r.text


class _SimulateurNonFini:
    debug_logs = []
    measure_registry = {}

    def __init__(self, periods, mesures):
        pass

    def simulate(self):
        return (pd.DataFrame([{"Année": 2030, "Dette/PIB %": float('nan')}]),
                pd.DataFrame([{"Année": 2030}]), {"measure_impacts_by_year": []})


def test_resultat_non_fini_500_avec_cors_et_error(client, api, monkeypatch, caplog):
    """Sérialisation éprouvée DANS l'endpoint : un NaN moteur sort en 500
    explicite AVEC l'en-tête CORS (sinon le navigateur ne voit qu'un échec
    réseau), et trace une ERROR."""
    monkeypatch.setattr(api, 'BudgetSimulatorV45', _SimulateurNonFini)
    with caplog.at_level(logging.ERROR):
        r = client.post('/simulate', json={'mesures': {}, 'periods': 10},
                        headers={'Origin': ORIGIN})
    assert r.status_code == 500
    assert r.headers.get('access-control-allow-origin') == ORIGIN
    assert any('non sérialisable' in rec.getMessage() for rec in caplog.records)
