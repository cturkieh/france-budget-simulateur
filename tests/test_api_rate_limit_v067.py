"""Limite de débit de POST /simulate (v0.6.7, lot 4 — prévue, absente jusqu'à la
réfutation des handlers ; clé d'adresse durcie après la revue de sécurité).

Contrat : seaux à jetons en mémoire, portés par le ROUTEUR (un déploiement qui
l'inclut, comme la production, en hérite) — BUDGETLAB_RATE_LIMIT_PER_MIN par
adresse (défaut 120) et BUDGETLAB_RATE_LIMIT_GLOBAL_PER_MIN toutes adresses
confondues (défaut 1 200), 0 = désactivé. Au-delà : 429 avec `Retry-After`
(secondes entières) et les en-têtes CORS, sans quoi le navigateur lirait le refus
comme une panne réseau. Adresse = le pair TCP ; `X-Forwarded-For` n'est lu que si
BUDGETLAB_TRUST_PROXY = N déclare N proxys de confiance, et alors au N-ième
élément EN PARTANT DE LA FIN — jamais en tête, que le client écrit (une clé de
tête rendait la limite inopérante : changer d'« adresse » à chaque requête).
Une adresse IPv6 compte pour son /64. Aucun en-tête `X-RateLimit-*`.
"""
import importlib.util
import logging
import pathlib

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

API_FILE = pathlib.Path(__file__).resolve().parent.parent / 'api.py'


def _api(monkeypatch, limite, proxys=None, globale=0):
    for nom, valeur in (('BUDGETLAB_RATE_LIMIT_PER_MIN', limite),
                        ('BUDGETLAB_TRUST_PROXY', proxys),
                        ('BUDGETLAB_RATE_LIMIT_GLOBAL_PER_MIN', globale)):
        if valeur is None:
            monkeypatch.delenv(nom, raising=False)
        else:
            monkeypatch.setenv(nom, str(valeur))
    spec = importlib.util.spec_from_file_location('api_rate_limit_v067', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Journal(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lignes = []

    def emit(self, record):
        self.lignes.append((record.levelno, record.getMessage()))


def _journal(api):
    """api.py appelle logging.basicConfig(force=True) à l'import, qui retire le
    handler de caplog : on écoute le logger du module directement."""
    journal = _Journal()
    api.logger.addHandler(journal)
    return journal


def _post(client, xff=None, origin=None):
    headers = {}
    if xff is not None:
        headers['X-Forwarded-For'] = xff
    if origin is not None:
        headers['Origin'] = origin
    return client.post('/simulate', json={'mesures': {}, 'periods': 1}, headers=headers)


def _requete(xff, pair='10.0.0.1'):
    en_tetes = [(b'x-forwarded-for', xff.encode())] if xff is not None else []
    return Request({'type': 'http', 'headers': en_tetes, 'client': (pair, 1234)})


def test_au_dela_de_la_limite_429_avec_retry_after(monkeypatch):
    client = TestClient(_api(monkeypatch, 3, proxys=1).app)
    assert [_post(client, '203.0.113.7').status_code for _ in range(3)] == [200, 200, 200]
    refus = _post(client, '203.0.113.7')
    assert refus.status_code == 429
    assert int(refus.headers['Retry-After']) >= 1
    assert 'Trop de simulations' in refus.json()['detail']
    assert not any(h.lower().startswith('x-ratelimit') for h in refus.headers)
    assert _post(client, '198.51.100.1').status_code == 200   # une autre adresse n'est pas touchée


def test_sans_proxy_de_confiance_un_x_forwarded_for_force_ne_change_pas_la_cle(monkeypatch):
    """RED revue de sécurité : la clé était le PREMIER élément de X-Forwarded-For,
    écrit par le client — une valeur neuve à chaque requête, et la limite ne
    mordait jamais. Sans BUDGETLAB_TRUST_PROXY, l'en-tête n'est pas lu."""
    api = _api(monkeypatch, 2)
    client = TestClient(api.app)
    codes = [_post(client, xff).status_code
             for xff in ('203.0.113.1', '203.0.113.2', '198.51.100.3', '192.0.2.4, 192.0.2.5')]
    assert codes == [200, 200, 429, 429]
    assert api._adresse_cliente(_requete('203.0.113.1, 198.51.100.2'), 0) == '10.0.0.1'


def test_avec_proxys_de_confiance_la_cle_est_lue_en_partant_de_la_fin():
    """« a, b, c » : c avec un proxy de confiance (le dernier élément, ajouté par
    lui), b avec deux ; liste trop courte ou élément invalide → le pair TCP."""
    import api as module   # conftest : limites désactivées, aucune requête ici
    xff = '203.0.113.1, 198.51.100.2, 192.0.2.3'
    assert module._adresse_cliente(_requete(xff), 1) == '192.0.2.3'
    assert module._adresse_cliente(_requete(xff), 2) == '198.51.100.2'
    assert module._adresse_cliente(_requete(xff), 4) == '10.0.0.1'
    assert module._adresse_cliente(_requete('203.0.113.1, pas-une-ip'), 1) == '10.0.0.1'
    assert module._adresse_cliente(_requete(None), 1) == '10.0.0.1'


def test_avec_un_proxy_forger_la_tete_n_ouvre_pas_de_seau_neuf(monkeypatch):
    client = TestClient(_api(monkeypatch, 2, proxys=1).app)
    assert _post(client, '1.1.1.1, 203.0.113.9').status_code == 200
    assert _post(client, '2.2.2.2, 3.3.3.3, 203.0.113.9').status_code == 200
    assert _post(client, '4.4.4.4, 203.0.113.9').status_code == 429
    assert _post(client, '4.4.4.4, 198.51.100.9').status_code == 200


def test_x_forwarded_for_sans_confiance_signale_une_fois(monkeypatch):
    """Derrière un proxy sans BUDGETLAB_TRUST_PROXY, tous les visiteurs partagent
    la clé du proxy : la mauvaise configuration se voit dans les journaux, une fois."""
    api = _api(monkeypatch, 100)
    journal = _journal(api)
    client = TestClient(api.app)
    for _ in range(3):
        _post(client, '203.0.113.1')
    avis = [m for niveau, m in journal.lignes if 'sans BUDGETLAB_TRUST_PROXY' in m]
    assert len(avis) == 1


def test_plafond_global_toutes_adresses_confondues(monkeypatch):
    """Borne qu'aucune usurpation ni aucun réseau d'adresses ne contourne :
    trois adresses distinctes épuisent un plafond global de 3/min. Refus tracé
    en ERROR (systémique), une fois par épisode."""
    api = _api(monkeypatch, 100, proxys=1, globale=3)
    journal = _journal(api)
    client = TestClient(api.app)
    assert [_post(client, f'203.0.113.{i}').status_code for i in (1, 2, 3)] == [200, 200, 200]
    refus = [_post(client, f'198.51.100.{i}') for i in (1, 2)]
    assert [r.status_code for r in refus] == [429, 429]
    assert 'trop de demandes' in refus[0].json()['detail']
    assert int(refus[0].headers['Retry-After']) >= 1
    erreurs = [m for niveau, m in journal.lignes if niveau == logging.ERROR]
    assert len(erreurs) == 1 and 'Plafond global' in erreurs[0]


def test_le_refus_porte_les_en_tetes_cors(monkeypatch):
    """Sans CORS, le front lirait le 429 comme une panne réseau — et la retenterait."""
    client = TestClient(_api(monkeypatch, 1, proxys=1).app)
    origine = 'http://localhost:5173'
    assert _post(client, '203.0.113.8', origin=origine).status_code == 200
    refus = _post(client, '203.0.113.8', origin=origine)
    assert refus.status_code == 429
    assert refus.headers['access-control-allow-origin'] == origine


def test_x_forwarded_for_invalide_retombe_sur_le_pair(monkeypatch):
    """Un premier élément qui n'est pas une adresse IP n'est pas une clé : chaque
    valeur fantaisiste ouvrirait sinon un seau neuf."""
    client = TestClient(_api(monkeypatch, 2, proxys=1).app)
    codes = [_post(client, xff).status_code for xff in ('pas-une-ip', 'x' * 500, '', None)]
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]


def test_ipv6_compte_par_reseau_64(monkeypatch):
    client = TestClient(_api(monkeypatch, 1, proxys=1).app)
    assert _post(client, '2001:db8:1:2::1').status_code == 200
    assert _post(client, '2001:db8:1:2:ffff::9').status_code == 429
    assert _post(client, '2001:db8:1:3::1').status_code == 200


def test_desactivable(monkeypatch):
    client = TestClient(_api(monkeypatch, 0).app)
    assert {_post(client, '203.0.113.10').status_code for _ in range(10)} == {200}


def test_defauts(monkeypatch):
    """120/min par adresse, 1 200/min au total, pair TCP (aucun proxy de confiance)."""
    api = _api(monkeypatch, None, proxys=None, globale=None)
    assert api.RATE_LIMIT_PAR_MIN_DEFAUT == 120 and api._limiteur.capacite == 120
    assert api.RATE_LIMIT_GLOBAL_PAR_MIN_DEFAUT == 1200 and api._limiteur_global.capacite == 1200
    assert api._proxys_de_confiance == 0


def test_valeur_invalide_echoue_au_demarrage(monkeypatch):
    """Une limite mal configurée ne se replie pas en silence sur une valeur."""
    for valeur in ('abc', '-5', 'nan', 'inf'):
        with pytest.raises(ValueError):
            _api(monkeypatch, valeur)
        with pytest.raises(ValueError):
            _api(monkeypatch, 0, globale=valeur)
    for proxys in ('true', '-1', '1.5', 'abc'):
        with pytest.raises(ValueError):
            _api(monkeypatch, 0, proxys=proxys)


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
