"""Croissance réelle : plus d'écrêtage, l'avis reste un signal (filet de croissance retiré).

Arbitrage du mainteneur (16/11/2026) : l'écrêtage de la croissance réelle annuelle dans [−3,5 % ; +2,5 %]
(``CROISSANCE_FILET_MIN``, ``CROISSANCE_FILET_MAX``), qu'aucune source ne fondait, est supprimé. Les deux
bornes restent celles du domaine de validité des multiplicateurs linéaires : une croissance qui en sort est
publiée telle qu'elle est calculée, et l'avis du rapport le signale (résultats à lire avec prudence). Le
contrat lu par le site ne change pas : même préfixe, même format par année (« x % calculés, y % retenus »,
désormais égaux), même bloc ``cadre.filet_croissance`` (croissance retenue = croissance calculée).

Garde : en mode cadre (le mode publié), aucun programme publié ni la référence sans programme ne sort de
l'ancien domaine, aucune année — le retrait ne change donc aucun chiffre publié.
"""
import json
import os
import re
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

DEBUT_CADRE = C.ANNEE_PREMIER_BUDGET_MANDAT
MODES = pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
# Programme synthétique de relance dont la croissance calculée dépasse la borne haute (le même que les tests du
# bloc structuré, test_release_e_filet_structure.py).
PROGRAMME_RELANCE = {'transition_ecologique': {'investissement': 50, 'renovation': 40},
                     'recherche_publique': {'budget': 20}, 'collectivites': {'investissement': 20},
                     'depenses_publiques': {'credits_etat': 20}}


class _Releve(BudgetSimulatorV45):
    """Le moteur complet ; garde la croissance que rend ``calculate_growth`` chaque année (dernière passe)."""

    def calculate_growth(self, year, economic_state):
        g = super().calculate_growth(year, economic_state)
        self.croissances[self.annee_base + year] = g
        return g


def _simuler(mesures, annee_debut, profils=None):
    sim = _Releve(periods=10, mesures=mesures, annee_debut=annee_debut, profils=profils)
    sim.croissances = {}
    df, _, rapport = sim.simulate()
    return sim, df.set_index('Année'), rapport


def _avis(rapport):
    return [w for w in rapport['warnings'] if w.startswith('Avis') and 'filet de croissance' in w]


@MODES
def test_la_croissance_hors_du_domaine_n_est_plus_ecretee(annee_debut):
    sim, df, rapport = _simuler(PROGRAMME_RELANCE, annee_debut)
    haut = C.CROISSANCE_FILET_MAX
    hors = {a: g for a, g in sim.croissances.items() if g > haut}
    assert hors, 'non-vacuité : le programme de relance sort du domaine'
    for a, g in hors.items():
        assert df.at[a, 'Croissance %'] == pytest.approx(100 * g, abs=0.005), a
        assert df.at[a, 'Croissance %'] > 100 * haut + 0.005, a
    bloc = rapport['cadre']['filet_croissance']
    assert [e['annee'] for e in bloc['ecretages']] == sorted(hors)
    for e in bloc['ecretages']:
        assert e['croissance_retenue_pct'] == pytest.approx(e['croissance_calculee_pct'], abs=1e-4), e
        assert e['croissance_calculee_pct'] == pytest.approx(100 * hors[e['annee']], abs=1e-4), e


@MODES
def test_l_avis_reste_un_signal_au_meme_format(annee_debut):
    _, _, rapport = _simuler(PROGRAMME_RELANCE, annee_debut)
    (avis,) = _avis(rapport)
    assert avis.startswith('Avis — filet de croissance [−3,50 % ; 2,50 %] atteint : '), avis
    assert 'croissance non écrêtée' in avis and 'à lire avec prudence' in avis, avis
    annees = re.findall(r'(\d{4}) \((−?\d+,\d+) % calculés, (−?\d+,\d+) % retenus\)', avis)
    assert annees and all(calculee == retenue for _, calculee, retenue in annees), avis


@MODES
def test_aucun_avis_dans_le_domaine(annee_debut):
    _, _, rapport = _simuler({}, annee_debut)
    assert _avis(rapport) == []
    assert rapport['cadre']['filet_croissance']['ecretages'] == []


def _scenarios_publies():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip('scénarios publiés absents (BUDGETLAB_SCENARIOS_JSON)')
    return json.loads(Path(chemin).read_text(encoding='utf-8'))


def test_garde_aucun_programme_publie_hors_de_l_ancien_domaine_en_mode_cadre(monkeypatch):
    """Le mode publié : chaque programme publié et la référence sans programme, chaque année, en pleine
    précision, restent dans [CROISSANCE_FILET_MIN ; CROISSANCE_FILET_MAX] ; aucun avis, bloc vide. Si un
    réencodage y fait entrer un programme, ce test rougit : le retrait de l'écrêtage change alors un chiffre
    publié, à arbitrer."""
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    cas = {nom: (s['apiMeasures'], s.get('profils') or None) for nom, s in _scenarios_publies().items()}
    cas['reference_sans_programme'] = ({}, None)
    assert len(cas) >= 2
    for nom, (mesures, profils) in cas.items():
        sim, df, rapport = _simuler(mesures, DEBUT_CADRE, profils)
        hors = {a: g for a, g in sim.croissances.items()
                if not C.CROISSANCE_FILET_MIN <= g <= C.CROISSANCE_FILET_MAX}
        assert not hors, (nom, hors)
        assert rapport['cadre']['filet_croissance']['ecretages'] == [], nom
        assert _avis(rapport) == [], nom
