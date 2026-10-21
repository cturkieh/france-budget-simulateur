"""v0.6.10 — paramètres admis mais IGNORÉS (réfutation de V2-04, constat major).

La porte des noms (V2-04) rejette un nom que le levier ne lit jamais. Mais
trois leviers ont des MODES EXCLUSIFS : un nom admis y est ignoré dès qu'un
autre est fourni, et passait en silence, même en strict (exécuté sur la
branche V2-04, 5 périodes, ``BUDGETLAB_STRICT=1``) :

- ``taxe_superprofits {intensite: 0.5, taux: 0.05}`` → valid True, aucun
  avertissement, trajectoire identique à ``{intensite: 0.5}`` ;
- ``exonerations_salaires {intensite: 0.5, taux_exoneration: 0.1}`` → idem ;
- ``chomage_alloc {taux_remplacement: 0.57, montant: 30}`` → idem.

Cause : ``_resolve_intensite_or_legacy`` ignore les clés du mode hérité dès
que ``intensite`` est présent, et ``chomage_alloc`` ignore ``montant`` si
``taux_remplacement`` est fourni. Même symptôme que V2-04 : un paramètre
demandé n'est pas appliqué, HTTP 200, ``report.valid: true``.

Contrat attendu (le même que pour un nom inconnu) : strict → 422 qui nomme le
levier, la clé ignorée et la clé qui la masque ; tolérant → 200, la clé
ignorée est signalée dans ``report.warnings`` et ``report.valid`` vaut
``false`` (la trajectoire reste celle du mode retenu).
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_FILE = Path(__file__).resolve().parent.parent / "api.py"

#: (levier, bloc, clé ignorée, clé qui la masque) — cas exacts de la réfutation.
CAS_REFUTATION = [
    ('taxe_superprofits', {'intensite': 0.5, 'taux': 0.05}, 'taux', 'intensite'),
    ('exonerations_salaires', {'intensite': 0.5, 'taux_exoneration': 0.1},
     'taux_exoneration', 'intensite'),
    ('chomage_alloc', {'taux_remplacement': 0.57, 'montant': 30},
     'montant', 'taux_remplacement'),
]


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location("api_exclusifs_v0610", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(api):
    return TestClient(api.app, raise_server_exceptions=False)


def _post(client, mesures, periods=5):
    return client.post('/simulate', json={'mesures': mesures, 'periods': periods})


@pytest.mark.parametrize('mid,bloc,ignoree,masque', CAS_REFUTATION,
                         ids=[c[0] for c in CAS_REFUTATION])
def test_cle_ignoree_en_mode_exclusif_refutation(client, monkeypatch,
                                                 mid, bloc, ignoree, masque):
    """Cas exacts de la réfutation 1 de V2-04 (major)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _post(client, {mid: bloc})
    assert r.status_code == 422, (
        f"strict : HTTP {r.status_code}, valid={r.json().get('report', {}).get('valid')} "
        f"(422 attendu : {mid}.{ignoree} ignoré car {masque} est fourni)")
    detail = r.json()['detail']
    for attendu in (mid, ignoree, masque):
        assert attendu in detail, detail

    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = _post(client, {mid: bloc})
    assert r.status_code == 200, r.text
    rapport = r.json()['report']
    signalements = [w for w in rapport['warnings'] if ignoree in w and masque in w]
    assert rapport['valid'] is False, (
        f"tolérant : valid={rapport['valid']}, avertissements : {rapport['warnings']}")
    assert signalements, rapport['warnings']
