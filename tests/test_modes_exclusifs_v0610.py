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


# --------------------------------------------------------------------------
# Propriétés durables (porte des modes exclusifs)
# --------------------------------------------------------------------------

import json  # noqa: E402
import os  # noqa: E402
from unittest.mock import patch  # noqa: E402

from budget_simulator import BudgetSimulatorV45, load_default_values  # noqa: E402
from budget_simulator.engine._noms_parametres import (  # noqa: E402
    MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS)
from budget_simulator.engine._param_domain import (  # noqa: E402
    EntreeInvalide, ParametreIgnore)

RACINE = Path(__file__).resolve().parent.parent
CORRIGEE = 'Entrée ou sortie corrigée'

#: (levier, clé dominante, clé ignorée) — TOUS les couples du module généré.
COUPLES = sorted((mid, dom, cle) for mid, groupes in MODES_EXCLUSIFS.items()
                 for dom, cles in groupes.items() for cle in cles)

#: Valeur légitime (dans le domaine, non nulle) par clé, pour composer les
#: blocs : la valeur ne change rien au contrat, seule la présence compte.
VALEUR = {'intensite': 0.5, 'taux_remplacement': 0.6, 'montant': 30,
          'taux': 0.05, 'seuil_hausse': 1.1, 'tous_secteurs': False,
          'taux_exoneration': 0.2}


def _simuler(mesures, periods=3, strict=False):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
        return BudgetSimulatorV45(periods=periods, mesures=mesures).simulate()


def _conflits(mesures):
    """Couples (levier, dominante, clés masquées) présents dans `mesures`."""
    return [(mid, dom, sorted(set(bloc) & cles))
            for mid, bloc in mesures.items() if isinstance(bloc, dict)
            for dom, cles in MODES_EXCLUSIFS.get(mid, {}).items()
            if bloc.get(dom) is not None and set(bloc) & cles]


def test_module_genere_couvre_les_trois_leviers_connus():
    """Garde de sens : les trois modes exclusifs de la réfutation sont dérivés
    (si l'un disparaît, c'est le code qui a changé — le relire)."""
    assert {(mid, dom) for mid, dom, _ in COUPLES} == {
        ('taxe_superprofits', 'intensite'), ('exonerations_salaires', 'intensite'),
        ('chomage_alloc', 'taux_remplacement')}
    for mid, dom, cle in COUPLES:
        assert {dom, cle} <= NOMS_PARAMETRES_ADMIS[mid], (mid, dom, cle)
        assert cle in VALEUR and dom in VALEUR


@pytest.mark.parametrize('mid,dom,cle', COUPLES, ids=['.'.join(c) for c in COUPLES])
def test_cle_masquee_strict_rejetee(mid, dom, cle):
    with pytest.raises(ExceptionGroup) as excinfo:
        _simuler({mid: {dom: VALEUR[dom], cle: VALEUR[cle]}}, periods=1, strict=True)
    erreurs = excinfo.value.exceptions
    assert all(isinstance(e, ParametreIgnore) and isinstance(e, EntreeInvalide)
               for e in erreurs)
    assert all(t in str(erreurs[0]) for t in (mid, dom, cle))


@pytest.mark.parametrize('mid,dom,cle', COUPLES, ids=['.'.join(c) for c in COUPLES])
def test_cle_masquee_tolerante_signalee_trajectoire_du_mode_retenu(mid, dom, cle):
    """Tolérant : signalé une fois, résultat invalidé, trajectoire = celle du
    bloc SANS la clé masquée (le mode retenu est celui de la dominante)."""
    df, _, rapport = _simuler({mid: {dom: VALEUR[dom], cle: VALEUR[cle]}})
    df_ref, _, rapport_ref = _simuler({mid: {dom: VALEUR[dom]}})
    assert rapport['valid'] is False and rapport_ref['valid'] is True
    signalements = [w for w in rapport['warnings']
                    if w.startswith(CORRIGEE) and cle in w and dom in w]
    assert len(signalements) == 1, rapport['warnings']
    assert df.equals(df_ref)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mid,dom,cle', COUPLES, ids=['.'.join(c) for c in COUPLES])
def test_mode_herite_seul_ou_dominante_null_inchanges(mid, dom, cle, strict):
    """Sans la dominante (absente ou `null`), la clé est LUE : aucun signal,
    et `null` garde sa sémantique « pas de valeur » (même trajectoire)."""
    df, _, rapport = _simuler({mid: {cle: VALEUR[cle]}}, periods=2, strict=strict)
    df_null, _, rapport_null = _simuler({mid: {dom: None, cle: VALEUR[cle]}},
                                        periods=2, strict=strict)
    assert rapport['valid'] is True
    assert not [w for w in rapport_null['warnings'] if 'modes exclusifs' in w]
    assert df.equals(df_null)


def test_toutes_les_cles_masquees_dans_un_seul_message():
    mid = 'taxe_superprofits'
    bloc = {'intensite': 0.5, 'taux': 0.05, 'seuil_hausse': 1.1, 'tous_secteurs': False}
    _, _, rapport = _simuler({mid: bloc})
    entrees = [w for w in rapport['warnings'] if 'modes exclusifs' in w]
    assert len(entrees) == 1
    assert 'seuil_hausse, taux, tous_secteurs' in entrees[0]


def test_entrees_legitimes_sans_conflit():
    """Scénarios publiés, défauts statu quo : aucune clé masquée (sinon c'est
    un VRAI défaut de l'entrée, à corriger à la source, pas à tolérer)."""
    assert not _conflits(load_default_values())
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    chemin = Path(env) if env else RACINE.parent.parent / 'frontend-react' / 'src' / 'data' / 'scenarios.json'
    if not chemin.exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    scenarios = json.loads(chemin.read_text(encoding='utf-8'))
    assert scenarios
    fautes = {sid: _conflits(d.get('apiMeasures') or {})
              for sid, d in scenarios.items() if _conflits(d.get('apiMeasures') or {})}
    assert not fautes, fautes


def test_exemples_get_scenarios_sans_conflit(client):
    for nom, mesures in client.get('/scenarios').json().items():
        assert not _conflits(mesures), nom
