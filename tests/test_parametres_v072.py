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
        'applique': -500_000.0, 'borne': [-500_000.0, 60_000.0], 'motif': 'domaine'}]


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
                         'applique': 1.0, 'borne': [0.0, 1.0], 'motif': 'domaine'}
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
        'applique': -500000.0, 'borne': [-500000.0, 60000.0], 'motif': 'domaine'}]
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


# ---------------------------------------------------------------------------
# 3. Rabot du vivier visible (revue passe 1, E1) : motif « vivier »
# ---------------------------------------------------------------------------
_REFORME_50 = {'fusion_agences': 50, 'digitalisation': 50}
_FIN_HORIZON = 2035


def _cible_et_capacite_sans_reforme(cible: float, debut: int) -> list[tuple[int, float, float]]:
    """Oracle arithmétique indépendant du handler, curseur seul : (année, cible
    de l'année, capacité du vivier), rampe linéaire début-2032, une cohorte de
    départs par an depuis le début."""
    duree = FP_EFFECTIFS_ANNEE_CIBLE - debut + 1
    lignes = []
    for an in range(debut, _FIN_HORIZON + 1):
        ecoule = min(an - debut + 1, duree)
        lignes.append((an, cible * ecoule / duree,
                       FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP * (an - debut + 1)))
    return lignes


def _entree_vivier(rapport: dict) -> list[dict]:
    return [e for e in rapport['leviers_ecretes'] if e.get('motif') == 'vivier']


@pytest.mark.parametrize('annee_debut', [2028, 2029, 2030, 2031, 2032])
def test_rabot_du_vivier_signale_si_et_seulement_si_la_cible_est_rabotee(annee_debut, monkeypatch):
    """Garde comportemental, curseur à la borne basse : l'entrée « vivier » est
    présente si et seulement si le réalisé est inférieur à la cible une année
    (oracle arithmétique), avec le réalisé de la dernière année rabotée ;
    rapport valide (limite du modèle, pas entrée invalide) et un avis."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    cible = PARAM_DOMAINS['fonction_publique']['effectifs'][0]
    _, _, rapport = _simulateur({'fonction_publique': {'effectifs': cible}},
                                annee_debut=annee_debut).simulate()
    rabotees = [(an, -cap) for an, c, cap in _cible_et_capacite_sans_reforme(cible, annee_debut)
                if -c > cap]
    entrees = _entree_vivier(rapport)
    avis = [w for w in rapport['warnings'] if 'rabotée par le vivier' in w]
    assert rapport['valid'] is True, rapport['warnings']
    if not rabotees:
        assert entrees == [] and avis == []
        return
    derniere, realise = rabotees[-1]
    assert entrees == [{'levier': 'fonction_publique.effectifs', 'demande': cible,
                        'applique': pytest.approx(realise), 'borne': [pytest.approx(realise), None],
                        'motif': 'vivier', 'annee': derniere}]
    assert len(avis) == 1 and avis[0].startswith('Avis — ') and str(derniere) in avis[0]
    json.dumps(rapport['leviers_ecretes'], allow_nan=False)


def test_rabot_du_vivier_attendu_de_2029_a_2032():
    """Témoin de l'oracle : à −500 000, le mandat 2028 n'est pas raboté, tous
    les débuts suivants le sont (cinq cohortes = 525 950 postes au plus)."""
    cible = PARAM_DOMAINS['fonction_publique']['effectifs'][0]
    rabote = {d: any(-c > cap for _, c, cap in _cible_et_capacite_sans_reforme(cible, d))
              for d in range(2028, 2033)}
    assert rabote == {2028: False, 2029: True, 2030: True, 2031: True, 2032: True}


@pytest.mark.parametrize('annee_debut', [None, 2028])
@pytest.mark.parametrize('effectifs', [-100_000, -500_000])
def test_rabot_du_vivier_avec_la_reforme(annee_debut, effectifs, monkeypatch):
    """Curseur + réforme de l'État 50/50 (même vivier) : oracle = le journal du
    handler (« plafonnée par le vivier »), monde du programme. Entrée présente
    si et seulement si le handler a raboté, réalisé de la dernière année."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    monkeypatch.setattr(journal, 'DEBUG_MODE', True)
    sim = _simulateur({'fonction_publique': {'effectifs': effectifs},
                       'fonction_publique_reforme': _REFORME_50}, annee_debut=annee_debut)
    _, _, rapport = sim.simulate()
    lignes = [l for l in sim.debug_logs if _MARQUEUR_PLAFOND in l]
    entrees = _entree_vivier(rapport)
    assert rapport['valid'] is True, rapport['warnings']
    if not lignes:
        assert entrees == []
        return
    assert len(entrees) == 1
    entree = entrees[0]
    assert entree['demande'] == effectifs and entree['applique'] > effectifs
    assert entree['borne'] == [entree['applique'], None]
    assert f"réalisé {entree['applique']:,.0f}" in lignes[-1]
    assert f"Y{entree['annee']}:" in lignes[-1]


def test_rabot_du_vivier_cas_de_la_revue():
    """Valeurs de la revue passe 1 : effectifs + réforme 50/50, mandat 2028 :
    −311 645 en 2035 pour −500 000 demandés, cible non atteinte à l'horizon."""
    _, _, rapport = _simulateur({'fonction_publique': {'effectifs': -500_000},
                                 'fonction_publique_reforme': _REFORME_50},
                                annee_debut=2028).simulate()
    (entree,) = _entree_vivier(rapport)
    assert (entree['applique'], entree['annee']) == (pytest.approx(-311_645), 2035)
    assert any("non atteinte à l'horizon 2035" in w for w in rapport['warnings'])


def test_rabot_du_vivier_une_entree_par_simulation():
    """Dédoublonné (une entrée quel que soit le nombre d'années rabotées) et
    ré-armé par simulate()."""
    sim = _simulateur({'fonction_publique': {'effectifs': -500_000}}, annee_debut=2032)
    _, _, premier = sim.simulate()
    _, _, second = sim.simulate()
    assert len(_entree_vivier(premier)) == 1
    assert premier['leviers_ecretes'] == second['leviers_ecretes']


def test_rabot_du_vivier_api(_client, monkeypatch):
    """API : l'entrée « vivier » sort dans `report.leviers_ecretes`, 200,
    rapport valide, même en mode strict (rien n'est refusé)."""
    for strict in ('', '1'):
        monkeypatch.setenv('BUDGETLAB_STRICT', strict)
        r = _client.post('/simulate', json={'periods': 10, 'annee_debut': 2029, 'mesures': {
            'fonction_publique': {'effectifs': -500000}}})
        assert r.status_code == 200, r.text
        rapport = r.json()['report']
        assert rapport['valid'] is True
        assert rapport['leviers_ecretes'] == [{
            'levier': 'fonction_publique.effectifs', 'demande': -500000,
            'applique': -420760.0, 'borne': [-420760.0, None], 'motif': 'vivier',
            'annee': 2032}]


# ---------------------------------------------------------------------------
# 6. Requête /simulate : clé inconnue refusée (E2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('strict', ['', '1'])
@pytest.mark.parametrize('corps', [
    {'periods': 10, 'mesures': {}, 'annee_debu': 2030},
    {'periods': 10, 'mesures': {}, 'annee_debut': 2028, 'rampe_annees': 3},
])
def test_api_cle_inconnue_422(corps, strict, _client, monkeypatch):
    """Une clé inconnue au niveau de la requête est refusée (422) dans les deux
    modes, au lieu d'être ignorée (mode historique sans avertissement)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    r = _client.post('/simulate', json=corps)
    assert r.status_code == 422, r.text
    inconnue = next(k for k in corps if k not in ('periods', 'mesures', 'annee_debut'))
    assert inconnue in r.text


def test_api_cles_connues_acceptees(_client, monkeypatch):
    """Témoin : le corps du site (`mesures`, `periods`, `annee_debut`) et
    `rampe` passent."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = _client.post('/simulate', json={'periods': 10, 'mesures': {}, 'annee_debut': 2028,
                                        'rampe': {'annees': 2, 'leviers': []}})
    assert r.status_code == 200, r.text
