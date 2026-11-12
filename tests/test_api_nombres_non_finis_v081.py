"""v0.8.1 (revue du moteur) — un nombre non fini dans le corps de ``POST /simulate`` (``NaN``, ``Infinity``,
``-Infinity`` ou un littéral hors du domaine des flottants, ``1e400``, que l'analyseur JSON lit comme
l'infini) est une faute du client : 422, jamais 500.

Avant le correctif, la réponse d'erreur de validation de FastAPI recopiait l'entrée fautive (``input``) ;
un flottant non fini n'est pas sérialisable en JSON standard, la réponse 422 échouait elle-même et le
client recevait un 500 (montants d'un calendrier ``valeurs``, ``profils.*.annee``, ``annee_debut``,
``periods``, ``rampe.annees``). Le correctif vit dans la classe de route du ``router`` (SOURCE unique du
contrat) : il suit le routeur dans toute application qui l'inclut, pas seulement dans ``api.app``.

Ce que la réponse ne change pas : même structure que la réponse 422 standard de FastAPI ; seuls les
nombres non finis y sont écrits en texte (``"NaN"``, ``"Infinity"``, ``"-Infinity"``). Le refus est
tracé (WARNING, emplacement et type de l'erreur, jamais la valeur reçue), comme les autres refus
d'entrée de ``/simulate``. Données de test : aucune n'est un programme publié.
"""
import importlib.util
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ``api.py`` du MOTEUR (chemin résolu : depuis un dépôt qui lie ``tests/`` au moteur, c'est
# toujours celui du moteur) et ``api.py`` du dépôt APPELANT (chemin non résolu : le même ici,
# l'application du déploiement qui inclut le routeur depuis un tel dépôt).
API_MOTEUR = Path(__file__).resolve().parent.parent / 'api.py'
API_APPELANT = Path(__file__).absolute().parent.parent / 'api.py'
CLE = 'recherche_publique.budget'


def _charger(chemin, nom):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _charger(API_MOTEUR, 'api_nombres_non_finis')


def _app_du_module():
    return MODULE.app


def _app_qui_inclut_le_routeur():
    """Comme un déploiement qui ajoute sa propre infrastructure : une AUTRE application, sans
    gestionnaire d'exception propre, qui inclut le routeur du moteur."""
    app = FastAPI()
    app.include_router(MODULE.router)
    return app


APPLICATIONS = {'api.app': _app_du_module, 'app qui inclut le routeur': _app_qui_inclut_le_routeur}
if API_APPELANT.resolve() != API_MOTEUR:
    # Chargée UNE fois, à l'import : une application de déploiement peut reconfigurer la
    # journalisation (``logging.basicConfig(force=True)`` retire les handlers de la racine, dont
    # celui de ``caplog`` s'il était déjà posé).
    _APP_APPELANT = _charger(API_APPELANT, 'api_appelant_non_finis').app
    APPLICATIONS['app du dépôt appelant'] = lambda: _APP_APPELANT


def _profil_valeurs(litteral):
    return ('{"periods":10,"annee_debut":2028,"mesures":{"recherche_publique":{"budget":20}},'
            '"profils":{"%s":{"forme":"valeurs","valeurs":{"2028":%s}}}}' % (CLE, litteral))


# (corps JSON brut, texte attendu à la place du nombre non fini dans ``input``)
CORPS = {
    'valeurs NaN': (_profil_valeurs('NaN'), 'NaN'),
    'valeurs Infinity': (_profil_valeurs('Infinity'), 'Infinity'),
    'valeurs -Infinity': (_profil_valeurs('-Infinity'), '-Infinity'),
    'valeurs 1e400': (_profil_valeurs('1e400'), 'Infinity'),
    'profils.annee NaN': ('{"periods":10,"annee_debut":2028,"mesures":{"recherche_publique":{"budget":20}},'
                          '"profils":{"%s":{"forme":"annee","annee":NaN}}}' % CLE, 'NaN'),
    'profils.annees Infinity': ('{"periods":10,"annee_debut":2028,"mesures":{"recherche_publique":{"budget":20}},'
                                '"profils":{"%s":{"forme":"rampe","annees":Infinity}}}' % CLE, 'Infinity'),
    'annee_debut NaN': ('{"periods":10,"annee_debut":NaN,"mesures":{}}', 'NaN'),
    'annee_debut 1e400': ('{"periods":10,"annee_debut":1e400,"mesures":{}}', 'Infinity'),
    'periods Infinity': ('{"periods":Infinity,"mesures":{}}', 'Infinity'),
    'periods -1e400': ('{"periods":-1e400,"mesures":{}}', '-Infinity'),
    'periods NaN': ('{"periods":NaN,"mesures":{}}', 'NaN'),
    'rampe.annees NaN': ('{"periods":10,"annee_debut":2028,"mesures":{"recherche_publique":{"budget":20}},'
                         '"rampe":{"annees":NaN,"leviers":["recherche_publique"]}}', 'NaN'),
}


def _textes(objet):
    """Toutes les chaînes d'un objet JSON décodé (récursif)."""
    if isinstance(objet, str):
        yield objet
    elif isinstance(objet, dict):
        for k, v in objet.items():
            yield from _textes(k)
            yield from _textes(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _textes(v)


def _flottants_non_finis(objet):
    if isinstance(objet, float):
        return objet != objet or objet in (float('inf'), float('-inf'))
    if isinstance(objet, dict):
        return any(_flottants_non_finis(v) for v in objet.values())
    if isinstance(objet, list):
        return any(_flottants_non_finis(v) for v in objet)
    return False


@pytest.mark.parametrize('strict', ['1', ''], ids=['strict', 'tolérant'])
@pytest.mark.parametrize('nom_app', sorted(APPLICATIONS))
@pytest.mark.parametrize('nom', sorted(CORPS))
def test_nombre_non_fini_rend_422_et_jamais_500(nom, nom_app, strict, monkeypatch, caplog):
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    corps, texte = CORPS[nom]
    client = TestClient(APPLICATIONS[nom_app](), raise_server_exceptions=False)
    with caplog.at_level(logging.WARNING):
        r = client.post('/simulate', content=corps, headers={'content-type': 'application/json'})
    assert r.status_code == 422, (nom, r.status_code, r.text[:300])
    # Réponse en JSON STANDARD (aucun NaN/Infinity littéral) : json.loads strict la relit.
    detail = json.loads(r.text, parse_constant=lambda c: pytest.fail(f'littéral {c} dans la réponse'))['detail']
    assert isinstance(detail, list) and detail
    assert not _flottants_non_finis(detail)
    # Le nombre non fini reçu est rendu en texte dans ``input`` (aucune autre information).
    assert any(e.get('input') == texte for e in detail), detail
    for e in detail:
        assert set(e) <= {'type', 'loc', 'msg', 'input', 'ctx', 'url'}, e
    # Refus tracé : WARNING qui nomme l'emplacement, jamais la valeur reçue.
    refus = [rec for rec in caplog.records if rec.levelno == logging.WARNING
             and 'Requête /simulate rejetée' in rec.getMessage()]
    assert refus, [rec.getMessage() for rec in caplog.records]
    assert not any(rec.levelno >= logging.ERROR for rec in caplog.records), \
        [rec.getMessage() for rec in caplog.records if rec.levelno >= logging.ERROR]


@pytest.mark.parametrize('corps', [
    {'periods': 0, 'annee_debut': '2028', 'mesures': {}},
    {'periods': 10, 'annee_debut': 2028, 'mesures': {}, 'profils': {CLE: {'forme': 'valeurs',
                                                                         'valeurs': {'2028': 'douze'}}}},
    {'periods': 10, 'inconnue': 1},
], ids=['periods et annee_debut', 'montant texte', 'clé inconnue'])
@pytest.mark.parametrize('nom_app', sorted(APPLICATIONS))
def test_erreur_de_schema_finie_inchangee(nom_app, corps, monkeypatch):
    """Une erreur de schéma sans nombre non fini garde, au bit, la réponse 422 standard de FastAPI
    (celle d'une application témoin, même modèle, gestionnaire par défaut)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    temoin = FastAPI()

    @temoin.post('/simulate')
    def _simulate(requete: MODULE.SimulationRequest):  # pragma: no cover (jamais atteint : 422)
        return {}

    r = TestClient(APPLICATIONS[nom_app](), raise_server_exceptions=False).post('/simulate', json=corps)
    attendu = TestClient(temoin).post('/simulate', json=corps)
    assert attendu.status_code == 422
    assert (r.status_code, r.content) == (attendu.status_code, attendu.content)


def test_textes_non_finis_jamais_recopies_ailleurs(monkeypatch):
    """Aucune information ajoutée : les seuls textes « NaN »/« Infinity » de la réponse sont les
    entrées reçues, à leur place (``input``)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    corps, _ = CORPS['valeurs NaN']
    r = TestClient(_app_du_module(), raise_server_exceptions=False).post(
        '/simulate', content=corps, headers={'content-type': 'application/json'})
    detail = r.json()['detail']
    hors_input = [t for e in detail for k, v in e.items() if k != 'input' for t in _textes(v)]
    assert 'NaN' not in hors_input
