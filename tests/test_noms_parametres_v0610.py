"""v0.6.10 — noms de paramètres validés (contre-audit externe, réserve V2-04).

Constat reproduit sur v0.6.7 → v0.6.9 : ``{"tva_rate": {"tauxx": 0.25}}``
(faute de frappe sur ``taux``) → HTTP 200, ``report.valid: true``, trajectoire
identique à la référence, aucun avertissement — la hausse de TVA demandée
n'est pas appliquée et rien ne le dit. Même 200 en mode strict.

Contrat attendu : un nom que le levier ne lit pas est rejeté en strict (422,
message qui nomme le levier, le nom fautif et les noms admis) ; en tolérant,
il est signalé (``report.warnings``) et invalide le résultat
(``report.valid: false``), le levier restant appliqué avec ses paramètres
connus.

Chargé par chemin (comme test_api_contrat_v067) : depuis le dépôt parent,
``import api`` désignerait l'API de production, qui INCLUT ce routeur.
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_FILE = Path(__file__).resolve().parent.parent / "api.py"


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location("api_noms_v0610", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(api):
    return TestClient(api.app, raise_server_exceptions=False)


def _post(client, mesures, periods=10):
    return client.post('/simulate', json={'mesures': mesures, 'periods': periods})


def test_v2_04_faute_de_frappe_tauxx_contre_audit(client, monkeypatch):
    """Requête exacte du contre-audit (§ 4, V2-04)."""
    mesures = {'tva_rate': {'tauxx': 0.25}}

    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = _post(client, mesures)
    assert r.status_code == 200, r.text
    rapport = r.json()['report']
    signalements = [w for w in rapport['warnings'] if 'tauxx' in w]
    assert rapport['valid'] is False, (
        f"tolérant : valid={rapport['valid']}, avertissements nommant "
        f"'tauxx' : {signalements}")
    assert signalements, rapport['warnings']

    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _post(client, mesures)
    assert r.status_code == 422, f"strict : HTTP {r.status_code} (422 attendu)"
    detail = r.json()['detail']
    for attendu in ('tva_rate', 'tauxx', 'taux'):
        assert attendu in detail, detail
