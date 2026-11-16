"""SMIC : référence et part nette officielles (lot SMIC, paramètres).

Arbitrage du mainteneur (16/11/2026) : la référence est le dernier SMIC brut mensuel paru au Journal officiel,
1 867,02 € (12,31 € de l'heure, arrêté du 22 mai 2026, en vigueur au 1er juin 2026) ; un montant net se convertit
en brut avec le rapport officiel net / brut du SMIC (1 477,93 / 1 867,02 ≈ 0,7916). Le défaut du moteur, le droit
en vigueur et le registre des paramètres portent la référence : ils sont neutres.
"""
import json
from pathlib import Path

import pytest

from budget_simulator.config import load_default_values
from budget_simulator.constants import (
    PART_NETTE_DU_BRUT_SMIC,
    SMIC_ANNEE_DE_REFERENCE,
    SMIC_BRUT_MENSUEL_REFERENCE_EUR,
    SMIC_NET_MENSUEL_REFERENCE_EUR,
)
from budget_simulator.engine.cadre import charger_droit_en_vigueur
from budget_simulator.handlers.additionnels import smic_brut_du_net
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).resolve().parents[1]


def test_reference_du_journal_officiel():
    assert SMIC_BRUT_MENSUEL_REFERENCE_EUR == 1867.02
    assert SMIC_ANNEE_DE_REFERENCE == 2026
    # 12,31 € × 35 heures × 52 semaines / 12 mois.
    assert SMIC_BRUT_MENSUEL_REFERENCE_EUR == pytest.approx(12.31 * 35 * 52 / 12, abs=0.005)


def test_part_nette_officielle_et_conversion():
    assert SMIC_NET_MENSUEL_REFERENCE_EUR == 1477.93
    assert PART_NETTE_DU_BRUT_SMIC == SMIC_NET_MENSUEL_REFERENCE_EUR / SMIC_BRUT_MENSUEL_REFERENCE_EUR
    assert round(PART_NETTE_DU_BRUT_SMIC, 4) == 0.7916
    assert smic_brut_du_net(SMIC_NET_MENSUEL_REFERENCE_EUR) == pytest.approx(SMIC_BRUT_MENSUEL_REFERENCE_EUR, rel=1e-15)
    assert round(smic_brut_du_net(1700.0), 2) == 2147.55


def test_defaut_droit_et_registre_portent_la_reference():
    assert load_default_values()['smic']['montant_brut'] == SMIC_BRUT_MENSUEL_REFERENCE_EUR
    droit = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json').read_text(encoding='utf-8'))
    assert droit['mesures']['smic']['montant_brut'] == SMIC_BRUT_MENSUEL_REFERENCE_EUR
    assert charger_droit_en_vigueur() is not None
    registre = json.loads((RACINE / 'policy_measures.json').read_text(encoding='utf-8'))
    (smic,) = [m for m in registre['mesures'] if m['id'] == 'smic']
    assert smic['parametres']['montant_brut']['valeur_defaut'] == SMIC_BRUT_MENSUEL_REFERENCE_EUR


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_le_droit_et_le_defaut_sont_neutres(annee_debut):
    """Sans le levier, avec le défaut, ou avec la valeur du droit : trajectoires identiques au bit."""
    base = BudgetSimulatorV45(periods=10, mesures={}, annee_debut=annee_debut).simulate()[0]
    avec = BudgetSimulatorV45(periods=10, mesures={'smic': {'montant_brut': SMIC_BRUT_MENSUEL_REFERENCE_EUR}},
                              annee_debut=annee_debut).simulate()[0]
    assert base.equals(avec)
