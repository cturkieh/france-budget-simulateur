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
import pytest

import budget_simulator._logging as journal
from budget_simulator import BudgetSimulatorV45
from budget_simulator.constants import (
    DEPARTS_ANNUELS_FP,
    FP_TAUX_NON_REMPLACEMENT_MAX,
    PARAM_DOMAINS,
)
from budget_simulator.handlers.efficience import FP_EFFECTIFS_ANNEE_CIBLE

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
    sim = BudgetSimulatorV45(periods=10, annee_debut=_PREMIERE_ANNEE_MANDAT,
                             mesures={'fonction_publique': {'effectifs': effectifs}})
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


def test_la_borne_n_est_pas_ecretee(monkeypatch):
    """−480 000 et −500 000 passent la porte sans correction (rapport valide)."""
    for valeur in (-480_000, -500_000):
        sim = BudgetSimulatorV45(periods=10, annee_debut=_PREMIERE_ANNEE_MANDAT,
                                 mesures={'fonction_publique': {'effectifs': valeur}})
        _, _, rapport = sim.simulate()
        assert rapport['valid'] is True, rapport['warnings']
