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


# --------------------------------------------------------------------------
# Propriétés durables (porte des noms)
# --------------------------------------------------------------------------

import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from unittest.mock import patch  # noqa: E402

from budget_simulator import BudgetSimulatorV45, load_default_values  # noqa: E402
from budget_simulator.constants import INTENSITE_DOMAINS, PARAM_DOMAINS  # noqa: E402
from budget_simulator.engine._noms_parametres import NOMS_PARAMETRES_ADMIS  # noqa: E402
from budget_simulator.engine._param_domain import (  # noqa: E402
    EntreeInvalide, ParametreInconnu, _DETAILS_MAX)

RACINE = Path(__file__).resolve().parent.parent
REGISTRE = RACINE / "tests" / "snapshots" / "measure_registry.json"
CORRIGEE = 'Entrée ou sortie corrigée'
LEVIERS = sorted(NOMS_PARAMETRES_ADMIS)


def _simuler(mesures, periods=3, strict=False):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
        return BudgetSimulatorV45(periods=periods, mesures=mesures).simulate()


def _scenarios_publies():
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    chemin = Path(env) if env else RACINE.parent.parent / 'frontend-react' / 'src' / 'data' / 'scenarios.json'
    if not chemin.exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return {sid: d.get('apiMeasures') or {}
            for sid, d in json.loads(chemin.read_text(encoding='utf-8')).items()}


def _noms_non_admis(mesures):
    return {mid: sorted(set(bloc) - NOMS_PARAMETRES_ADMIS[mid])
            for mid, bloc in mesures.items()
            if isinstance(bloc, dict) and set(bloc) - NOMS_PARAMETRES_ADMIS[mid]}


def _faute(mid):
    """Faute de frappe plausible sur le premier nom admis du levier."""
    nom = min(NOMS_PARAMETRES_ADMIS[mid])
    return nom + nom[-1]


# --- Entrées légitimes : aucun nom non admis (sinon c'est un VRAI défaut) ----

def test_scenarios_publies_sans_nom_inconnu():
    scenarios = _scenarios_publies()
    assert len(scenarios) == 10, sorted(scenarios)
    fautes = {sid: _noms_non_admis(m) for sid, m in scenarios.items() if _noms_non_admis(m)}
    assert not fautes, fautes


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_scenarios_publies_valides_dans_les_deux_modes(strict):
    for sid, mesures in _scenarios_publies().items():
        _, _, rapport = _simuler(mesures, periods=2, strict=strict)
        assert not [w for w in rapport['warnings'] if 'inconnu' in w], sid


def test_exemples_de_get_scenarios_et_statu_quo(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    exemples = client.get('/scenarios').json()
    assert {'status_quo', 'austerite', 'scandinave', 'relance_verte'} <= set(exemples)
    for nom, mesures in exemples.items():
        assert not _noms_non_admis(mesures), nom
        r = _post(client, mesures, periods=2)
        assert r.status_code == 200, (nom, r.text)
        assert r.json()['report']['valid'] is True, nom


def test_defauts_et_lecteurs_lateraux_dans_le_contrat():
    """Tout nom que le moteur lit ou publie hors handler doit être admis :
    défauts statu quo, domaines de valeurs, intensités, effets d'offre."""
    assert not _noms_non_admis(load_default_values())
    for mid, domaines in PARAM_DOMAINS.items():
        assert set(domaines) <= NOMS_PARAMETRES_ADMIS[mid], mid
    for mid in INTENSITE_DOMAINS:
        assert 'intensite' in NOMS_PARAMETRES_ADMIS[mid], mid
    for cfg in BudgetSimulatorV45.SUPPLY_EFFECTS.values():
        assert cfg['param'] in NOMS_PARAMETRES_ADMIS[cfg['measure_id']], cfg


def test_sliders_publies_dans_le_contrat():
    """Le frontend n'envoie que des noms admis (niveau « sliders » du registre
    commité, dérivé de `convertToAPIFormat`)."""
    registre = json.loads(REGISTRE.read_text(encoding='utf-8'))
    for mid, m in registre['mesures'].items():
        for s in m['sliders']:
            assert s['param'] in NOMS_PARAMETRES_ADMIS[mid], (mid, s)
    for s in registre['sliders_sans_handler']:
        if 'measure' in s:
            assert s['param'] in NOMS_PARAMETRES_ADMIS[s['measure']], s


def test_tout_levier_connu_a_un_contrat_de_noms():
    sim = BudgetSimulatorV45(periods=1, mesures={})
    assert set(sim.measure_registry) <= set(NOMS_PARAMETRES_ADMIS)
    assert all(NOMS_PARAMETRES_ADMIS[mid] for mid in sim.measure_registry)


# --- Faute de frappe sur chaque levier -------------------------------------

@pytest.mark.parametrize('mid', LEVIERS)
def test_faute_de_frappe_strict_rejetee(mid):
    with pytest.raises(ExceptionGroup) as excinfo:
        _simuler({mid: {_faute(mid): 1.0}}, periods=1, strict=True)
    erreurs = excinfo.value.exceptions
    assert all(isinstance(e, ParametreInconnu) and isinstance(e, EntreeInvalide)
               for e in erreurs)
    message = str(erreurs[0])
    assert mid in message and _faute(mid) in message
    assert all(nom in message for nom in NOMS_PARAMETRES_ADMIS[mid])


@pytest.mark.parametrize('mid', LEVIERS)
def test_faute_de_frappe_tolerante_signalee_et_ignoree(mid):
    """Tolérant : signalé, résultat invalidé, et le levier est appliqué avec
    ses autres paramètres — ici aucun : trajectoire de `{levier: {}}`."""
    df, _, rapport = _simuler({mid: {_faute(mid): 1.0}})
    df_ref, _, rapport_ref = _simuler({mid: {}})
    assert rapport['valid'] is False
    assert rapport_ref['valid'] is True
    signalements = [w for w in rapport['warnings'] if w.startswith(CORRIGEE) and _faute(mid) in w]
    assert len(signalements) == 1, rapport['warnings']
    assert df.equals(df_ref)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_melange_connu_inconnu(client, monkeypatch, strict):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1' if strict else '')
    r = _post(client, {'tva_rate': {'taux': 0.22, 'tauxx': 0.25}})
    if strict:
        assert r.status_code == 422, r.text
        assert 'tauxx' in r.json()['detail'] and "'taux'" not in r.json()['detail']
        return
    corps = r.json()
    attendu = _post(client, {'tva_rate': {'taux': 0.22}}).json()
    assert corps['report']['valid'] is False
    assert attendu['report']['valid'] is True
    assert corps['results'] == attendu['results']  # `taux` appliqué, `tauxx` ignoré


def test_nom_inconnu_a_null_signale_aussi():
    """La faute est dans le NOM : `null` sur un nom inconnu reste signalé."""
    _, _, rapport = _simuler({'csg': {'tauxx': None}})
    assert rapport['valid'] is False
    assert any('tauxx' in w for w in rapport['warnings'] if w.startswith(CORRIGEE))
    with pytest.raises(ExceptionGroup):
        _simuler({'csg': {'tauxx': None}}, periods=1, strict=True)


def test_null_et_bloc_vide_inchanges():
    _, _, rapport = _simuler({'csg': {'taux': None}})
    assert rapport['valid'] is True and not [w for w in rapport['warnings'] if 'inconnu' in w]
    _, _, rapport = _simuler({'taxe_superprofits': {}})
    assert rapport['valid'] is True
    assert any(w.startswith('Avis — taxe_superprofits={}') for w in rapport['warnings'])
    _, _, rapport = _simuler({'taxe_superprofits': None})
    assert rapport['valid'] is True


def test_journalisation_agregee_et_dedupliquee(caplog):
    """Un bloc de milliers de noms inconnus : UNE ligne WARNING par levier et
    par simulation (pas une par nom ni par année), une entrée au rapport."""
    bloc = {f'cle_{i}': 1.0 for i in range(2000)}
    with caplog.at_level(logging.WARNING):
        _, _, rapport = _simuler({'csg': bloc}, periods=10)
    lignes = [r for r in caplog.records if 'PARAM_NOM_INCONNU' in r.getMessage()]
    assert len(lignes) == 1
    assert f'(+{2000 - _DETAILS_MAX} autres)' in lignes[0].getMessage()
    entrees = [w for w in rapport['warnings'] if w.startswith(CORRIGEE) and 'inconnu' in w]
    assert len(entrees) == 1 and f'(+{2000 - _DETAILS_MAX} autres)' in entrees[0]


def test_levier_absent_du_module_genere_echoue_bruyamment(monkeypatch, caplog):
    """Artefact périmé = bug moteur : ERROR + drapeau, jamais « tout passe »."""
    monkeypatch.delitem(NOMS_PARAMETRES_ADMIS, 'tva_rate')
    with caplog.at_level(logging.ERROR):
        _, _, rapport = _simuler({'tva_rate': {'taux': 0.22}})
    assert any(y.get('tva_rate', {}).get('_handler_failed')
               for y in rapport['measure_impacts_by_year'])
    assert any('NOMS_PARAMETRES_ADMIS' in r.getMessage() for r in caplog.records
               if r.levelno >= logging.ERROR)
