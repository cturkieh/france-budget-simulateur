"""Release v0.7.2 « paramètres » — bornes, écrêtage visible.

1. Borne basse du curseur ``fonction_publique.effectifs`` portée à −500 000
   (décision du mainteneur du 08/11/2026, banc effectifs −480 k / −500 k). Le
   garde-fou : la borne, en valeur absolue, reste STRICTEMENT sous la capacité
   du vivier de départs d'un mandat 2028-2032 en mode cadre. Sinon le handler
   rabote la cible sans prévenir de 2028 à 2032, puis le stock rattrape d'un
   coup en 2033 quand le vivier recommence à croître.
2. Écrêtage visible : ``report.leviers_ecretes`` (cf. section suivante).

Aucun test ne lit ``scenarios.json`` : la suite publique tourne sans.
"""
import importlib.util
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator._logging as journal
from budget_simulator import BudgetSimulatorV45
from budget_simulator.constants import (
    DEPARTS_ANNUELS_FP,
    FP_TAUX_NON_REMPLACEMENT_MAX,
    PARAM_DOMAINS,
)
from budget_simulator.engine._param_domain import (
    validate_intensite_domain,
    validate_param_domains,
)
from budget_simulator.handlers.efficience import FP_EFFECTIFS_ANNEE_CIBLE

def _simulateur(mesures, annee_debut=None) -> BudgetSimulatorV45:
    """Point d'entrée de la simulation, le même que l'API (``api.py``,
    ``/simulate``) : ``BudgetSimulatorV45(periods, mesures, annee_debut)``.
    Pyright juge la classe abstraite à tort : le ``Protocol`` _SimulatorState
    (``handlers/_types.py``) déclare ``masse_categorie_nominale`` et
    ``indice_prix_depenses``, implémentés par ``engine/expenditures.py`` plus
    loin dans l'ordre d'héritage. Faux positif préexistant, commun à tous les
    tests qui simulent ; ignoré ici, en un seul endroit."""
    return BudgetSimulatorV45(periods=10, mesures=mesures,  # pyright: ignore[reportAbstractUsage]
                              annee_debut=annee_debut)


# Premier budget du mandat en mode cadre : celui des programmes et du
# simulateur (engine/cadre.py, en-tête), élection de 2027.
_PREMIERE_ANNEE_MANDAT = 2028
_MARQUEUR_PLAFOND = "plafonnée par le vivier"


def _capacite_vivier_mandat() -> float:
    """Postes que le vivier peut retirer sur 2028-2032, sans réforme de l'État :
    taux maximal de non-remplacement × départs annuels × cohortes du mandat."""
    cohortes = FP_EFFECTIFS_ANNEE_CIBLE - _PREMIERE_ANNEE_MANDAT + 1
    return FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP * cohortes


def test_borne_effectifs_sous_le_vivier_du_mandat():
    """Propriété : |borne basse| < capacité du vivier 2028-2032, calculée depuis
    les constantes. La rampe étant linéaire (1/5 par an), la condition sur le
    stock final vaut pour chaque année du mandat."""
    borne_basse = PARAM_DOMAINS['fonction_publique']['effectifs'][0]
    assert borne_basse < 0
    assert abs(borne_basse) < _capacite_vivier_mandat()


def test_borne_effectifs_couvre_la_decision_du_08_11_2026():
    """La borne couvre −500 000 (décision du mainteneur), au-delà du −400 000
    de v0.6.11 ; la borne haute est inchangée."""
    assert PARAM_DOMAINS['fonction_publique']['effectifs'] == (-500_000.0, 60_000.0)


def _journal_plafond(effectifs: float, monkeypatch) -> list[str]:
    monkeypatch.setattr(journal, 'DEBUG_MODE', True)
    sim = _simulateur({'fonction_publique': {'effectifs': effectifs}},
                      annee_debut=_PREMIERE_ANNEE_MANDAT)
    sim.simulate()
    return [ligne for ligne in sim.debug_logs if _MARQUEUR_PLAFOND in ligne]


def test_a_la_borne_le_vivier_ne_rabote_rien(monkeypatch):
    """Comportement : à la borne basse, en mode cadre 2028, le handler réalise
    la cible chaque année (aucune ligne « plafonnée par le vivier »)."""
    borne_basse = PARAM_DOMAINS['fonction_publique']['effectifs'][0]
    assert _journal_plafond(borne_basse, monkeypatch) == []


def test_au_dela_du_vivier_le_rabot_est_detecte(monkeypatch):
    """Témoin : le test précédent n'est pas vide. Domaine élargi en mémoire,
    une cible de 110 % de la capacité est rabotée, et le journal le dit."""
    capacite = _capacite_vivier_mandat()
    domaines = {**PARAM_DOMAINS['fonction_publique'],
                'effectifs': (-2 * capacite, 60_000.0)}
    monkeypatch.setitem(PARAM_DOMAINS, 'fonction_publique', domaines)
    assert _journal_plafond(-1.1 * capacite, monkeypatch)


def test_la_borne_n_est_pas_ecretee():
    """−480 000 et −500 000 passent la porte sans correction (rapport valide)."""
    for valeur in (-480_000, -500_000):
        sim = _simulateur({'fonction_publique': {'effectifs': valeur}},
                          annee_debut=_PREMIERE_ANNEE_MANDAT)
        _, _, rapport = sim.simulate()
        assert rapport['valid'] is True, rapport['warnings']


# ---------------------------------------------------------------------------
# 2. Écrêtage visible : report.leviers_ecretes
# ---------------------------------------------------------------------------
_API_FILE = Path(__file__).resolve().parent.parent / "api.py"


def test_porte_des_parametres_consigne_l_ecretage():
    """Unitaire : une valeur sous la borne basse est ramenée à la borne et
    consignée {levier, demande, applique, borne}."""
    ecretages = {}
    out = validate_param_domains('fonction_publique', {'effectifs': -600_000},
                                 strict=False, corrections={}, ecretages=ecretages)
    assert out['effectifs'] == -500_000.0
    assert list(ecretages.values()) == [{
        'levier': 'fonction_publique.effectifs', 'demande': -600_000,
        'applique': -500_000.0, 'borne': [-500_000.0, 60_000.0]}]


def test_porte_des_parametres_ne_consigne_rien_dans_le_domaine():
    """Unitaire : dans le domaine (bornes incluses), objet identique et rien
    de consigné."""
    ecretages = {}
    params = {'effectifs': -500_000}
    assert validate_param_domains('fonction_publique', params, strict=False,
                                  corrections={}, ecretages=ecretages) is params
    assert ecretages == {}


def test_porte_d_intensite_consigne_l_ecretage_et_rend_nan_en_texte():
    """Unitaire : l'intensité est écrêtée de même ; un NaN (ramené à la borne
    basse) est rendu en texte, la réponse JSON refusant NaN."""
    ecretages = {}
    validate_intensite_domain('isf_climatique', {'intensite': 3.0}, strict=False,
                              corrections={}, ecretages=ecretages)
    validate_intensite_domain('optimisation_dette', {'intensite': math.nan},
                              strict=False, corrections={}, ecretages=ecretages)
    lignes = list(ecretages.values())
    assert lignes[0] == {'levier': 'isf_climatique.intensite', 'demande': 3.0,
                         'applique': 1.0, 'borne': [0.0, 1.0]}
    assert lignes[1]['demande'] == 'nan' and lignes[1]['applique'] == 0.0
    json.dumps(lignes, allow_nan=False)


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_simulation_expose_l_ecretage_une_fois(annee_debut, monkeypatch):
    """Simulateur tolérant, mode historique et mode cadre : un écrêtage par
    paramètre (pas un par année simulée), rapport invalide, correction en
    phrase toujours présente."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    sim = _simulateur({'fonction_publique': {'effectifs': -900_000, 'point_indice': 50.0}},
                      annee_debut=annee_debut)
    _, _, rapport = sim.simulate()
    assert [e['levier'] for e in rapport['leviers_ecretes']] == [
        'fonction_publique.effectifs', 'fonction_publique.point_indice']
    assert rapport['leviers_ecretes'][1]['applique'] == 10.0
    assert rapport['valid'] is False
    assert sum('hors du domaine' in w for w in rapport['warnings']) == 2


def test_simulation_sans_ecretage_liste_vide():
    """Rien d'écrêté : liste vide, rapport valide (statu quo)."""
    _, _, rapport = _simulateur({}).simulate()
    assert rapport['leviers_ecretes'] == []
    assert rapport['valid'] is True


def test_un_second_simulate_repart_de_zero(monkeypatch):
    """Portée = une simulation : le champ est ré-armé par simulate()."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    sim = _simulateur({'fonction_publique': {'effectifs': -900_000}})
    _, _, premier = sim.simulate()
    _, _, second = sim.simulate()
    assert premier['leviers_ecretes'] == second['leviers_ecretes']
    assert len(second['leviers_ecretes']) == 1


@pytest.fixture(scope="module")
def _client():
    spec = importlib.util.spec_from_file_location("api_parametres_v072", _API_FILE)
    assert spec is not None and spec.loader is not None, _API_FILE
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


def test_api_tolerant_expose_leviers_ecretes(_client, monkeypatch):
    """API, mode tolérant : 200, champ structuré dans `report`."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = _client.post('/simulate', json={'periods': 10, 'annee_debut': 2028,
                                        'mesures': {'fonction_publique': {'effectifs': -600000}}})
    assert r.status_code == 200
    rapport = r.json()['report']
    assert rapport['leviers_ecretes'] == [{
        'levier': 'fonction_publique.effectifs', 'demande': -600000,
        'applique': -500000.0, 'borne': [-500000.0, 60000.0]}]
    assert rapport['valid'] is False


def test_api_sans_ecretage_liste_vide(_client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = _client.post('/simulate', json={'periods': 10, 'mesures': {
        'fonction_publique': {'effectifs': -500000}}})
    assert r.status_code == 200
    assert r.json()['report']['leviers_ecretes'] == []


def test_api_strict_refuse_sans_ecreter(_client, monkeypatch):
    """API, mode strict : hors domaine = 422, inchangé (rien n'est écrêté)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client.post('/simulate', json={'periods': 10, 'mesures': {
        'fonction_publique': {'effectifs': -600000}}})
    assert r.status_code == 422
