"""
Tests v0.6.0 — fin des « repas gratuits » santé (audit 08/2026, constats 5-6).

METHODOLOGIE.md promet « NEUTRALITE TOTALE : Gini 0, PA 0, Compétitivité 0 »
pour les mesures d'EFFICIENCE santé ; le code v0.5.1 leur donnait pourtant un
triple bonus non sourcé (Gini négatif + pouvoir d'achat positif + compétitivité
positive) — couper jusqu'à 30 Md€ n'avait aucun coût dans aucune dimension.
Décision v0.6.0 (règle validée : contrepartie SOURCÉE ou neutralité réelle) :
les impacts macro de l'efficience deviennent réellement neutres, conformes à
la doc. Les FRANCHISES conservent leurs impacts, eux sourcés (Gini régressif
+0,003 pour 100→200 %, OFCE 2024 ; pouvoir d'achat −0,001, INSEE 2024).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45


def _impacts_sante(params, year=2027):
    s = BudgetSimulatorV45(periods=10, mesures={'sante': params})
    _, _, impacts = s._apply_sante({}, params, year, 3100, 0.015, 0.075)
    return impacts


def test_efficience_sante_reellement_neutre():
    """Efficience pure (hôpital + ambulatoire + organisation) : Gini 0, PA 0,
    compétitivité 0 — le code fait enfin ce que la doc promet."""
    imp = _impacts_sante({'effort_hopital': 1.0, 'effort_ambu': 1.0, 'effort_prev_org': 1.0})
    assert imp['gini'] == 0.0
    assert imp['pouvoir_achat'] == 0.0
    assert imp['competitivite'] == 0.0
    # Et l'économie budgétaire, elle, existe bien.
    assert imp['depenses'] < 0


def test_franchises_gardent_leurs_impacts_sources():
    """Franchises doublées : impacts conservés car sourcés (OFCE/INSEE 2024) —
    régressif sur le Gini, négatif sur le pouvoir d'achat."""
    imp = _impacts_sante({'franchise_participation_taux': 200})
    assert imp['gini'] == pytest.approx(0.003, abs=1e-9)
    assert imp['pouvoir_achat'] == pytest.approx(-0.001, abs=1e-9)
