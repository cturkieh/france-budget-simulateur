"""Limite de débit de POST /simulate (v0.6.7, lot 4 — prévue, absente jusqu'à la
réfutation des handlers).

Contrat : seau à jetons en mémoire par adresse cliente, BUDGETLAB_RATE_LIMIT_PER_MIN
requêtes par minute (défaut 120, 0 = désactivé), porté par le ROUTEUR (un
déploiement qui l'inclut, comme la production, en hérite). Au-delà : 429 avec
`Retry-After` (secondes entières), et les en-têtes CORS, sans quoi le navigateur
lirait le refus comme une panne réseau. Adresse cliente = PREMIER élément de
`X-Forwarded-For` (Render y place l'adresse réelle), validé comme adresse IP,
sinon l'adresse du pair TCP ; une adresse IPv6 compte pour son /64. Aucun en-tête
`X-RateLimit-*` : il n'y aurait rien de juste à y mettre par processus.
"""
import importlib.util
import pathlib

import pytest
from fastapi.testclient import TestClient

API_FILE = pathlib.Path(__file__).resolve().parent.parent / 'api.py'


def _api(monkeypatch, limite):
    if limite is None:
        monkeypatch.delenv('BUDGETLAB_RATE_LIMIT_PER_MIN', raising=False)
    else:
        monkeypatch.setenv('BUDGETLAB_RATE_LIMIT_PER_MIN', str(limite))
    spec = importlib.util.spec_from_file_location('api_rate_limit_v067', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _post(client, xff=None, origin=None):
    headers = {}
    if xff is not None:
        headers['X-Forwarded-For'] = xff
    if origin is not None:
        headers['Origin'] = origin
    return client.post('/simulate', json={'mesures': {}, 'periods': 1}, headers=headers)


def test_au_dela_de_la_limite_429_avec_retry_after(monkeypatch):
    client = TestClient(_api(monkeypatch, 3).app)
    assert [_post(client, '203.0.113.7').status_code for _ in range(3)] == [200, 200, 200]
    refus = _post(client, '203.0.113.7')
    assert refus.status_code == 429
    assert int(refus.headers['Retry-After']) >= 1
    assert 'Trop de simulations' in refus.json()['detail']
    assert not any(h.lower().startswith('x-ratelimit') for h in refus.headers)
    assert _post(client, '198.51.100.1').status_code == 200   # une autre adresse n'est pas touchée


def test_le_refus_porte_les_en_tetes_cors(monkeypatch):
    """Sans CORS, le front lirait le 429 comme une panne réseau — et la retenterait."""
    client = TestClient(_api(monkeypatch, 1).app)
    origine = 'http://localhost:5173'
    assert _post(client, '203.0.113.8', origin=origine).status_code == 200
    refus = _post(client, '203.0.113.8', origin=origine)
    assert refus.status_code == 429
    assert refus.headers['access-control-allow-origin'] == origine


def test_seul_le_premier_ip_de_x_forwarded_for_compte(monkeypatch):
    """« client, proxy… » : faire varier les éléments suivants n'ouvre pas de seau neuf."""
    client = TestClient(_api(monkeypatch, 2).app)
    assert _post(client, '203.0.113.9, 10.0.0.1').status_code == 200
    assert _post(client, ' 203.0.113.9 ,10.0.0.2, 10.0.0.3').status_code == 200
    assert _post(client, '203.0.113.9, 10.0.0.4').status_code == 429


def test_x_forwarded_for_invalide_retombe_sur_le_pair(monkeypatch):
    """Un premier élément qui n'est pas une adresse IP n'est pas une clé : chaque
    valeur fantaisiste ouvrirait sinon un seau neuf."""
    client = TestClient(_api(monkeypatch, 2).app)
    codes = [_post(client, xff).status_code for xff in ('pas-une-ip', 'x' * 500, '', None)]
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]


def test_ipv6_compte_par_reseau_64(monkeypatch):
    client = TestClient(_api(monkeypatch, 1).app)
    assert _post(client, '2001:db8:1:2::1').status_code == 200
    assert _post(client, '2001:db8:1:2:ffff::9').status_code == 429
    assert _post(client, '2001:db8:1:3::1').status_code == 200


def test_desactivable(monkeypatch):
    client = TestClient(_api(monkeypatch, 0).app)
    assert {_post(client, '203.0.113.10').status_code for _ in range(10)} == {200}


def test_defaut_120_par_minute(monkeypatch):
    api = _api(monkeypatch, None)
    assert api.RATE_LIMIT_PAR_MIN_DEFAUT == 120
    assert api._limiteur is not None and api._limiteur.capacite == 120


def test_valeur_invalide_echoue_au_demarrage(monkeypatch):
    """Une limite mal configurée ne se replie pas en silence sur une valeur."""
    for valeur in ('abc', '-5', 'nan', 'inf'):
        with pytest.raises(ValueError):
            _api(monkeypatch, valeur)


def test_scenarios_non_limite(monkeypatch):
    client = TestClient(_api(monkeypatch, 1).app)
    _post(client, '203.0.113.11')
    assert _post(client, '203.0.113.11').status_code == 429
    assert client.get('/scenarios', headers={'X-Forwarded-For': '203.0.113.11'}).status_code == 200


def test_seau_se_remplit_au_debit_annonce(monkeypatch):
    api = _api(monkeypatch, 0)
    horloge = [0.0]
    seau = api._LimiteurDebit(60, horloge=lambda: horloge[0])
    assert all(seau.prendre('a') == (0.0, False) for _ in range(60))
    attente, nouveau = seau.prendre('a')
    assert attente == pytest.approx(1.0) and nouveau   # 60/min = un jeton par seconde
    horloge[0] += 0.5
    attente, nouveau = seau.prendre('a')
    assert attente == pytest.approx(0.5) and not nouveau   # même épisode : signalé une fois
    horloge[0] += 0.5
    assert seau.prendre('a') == (0.0, False)
    horloge[0] += 3600
    assert all(seau.prendre('a') == (0.0, False) for _ in range(60))   # plafonné à la capacité
    assert seau.prendre('a')[0] > 0


def test_nombre_de_cles_borne(monkeypatch):
    """La mémoire ne croît pas avec le nombre d'adresses : au-delà de `cles_max`,
    le seau le moins récemment vu est oublié (équivaut à un seau plein)."""
    api = _api(monkeypatch, 0)
    seau = api._LimiteurDebit(5, cles_max=3)
    for cle in 'abcde':
        seau.prendre(cle)
    assert list(seau._seaux) == ['c', 'd', 'e']
