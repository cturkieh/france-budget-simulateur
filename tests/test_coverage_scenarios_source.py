"""Dé-tautologisation de coverage_scenarios (One Source of Truth, T4).

Avant : les mini-scénarios standalone étaient dérivés de
`policy_measures.json` et le test les comparait à un snapshot — sans
garantie que les clés exercées soient le VRAI contrat (clé morte = test
qui se valide lui-même). Après : chaque clé pilote est cross-validée
contre le registre (vérité = handlers). Une clé hors contrat → échec
BRUYANT et ACTIONNABLE (jamais un faux sentiment de couverture).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
sys.path.insert(0, str(SNAPSHOTS_DIR))
from coverage_scenarios import _assert_param_in_contract  # noqa: E402

# Sentinelles depuis le PRODUCTEUR (source unique — pas de re-littéral).
sys.path.insert(0, str(ROOT))
from scripts.generate_measure_registry import _DYNAMIC, _UNMODELED  # noqa: E402


def test_param_in_contract_accepts_real_key():
    reg = {"mesures": {"sante": {"params": {"effort_hopital": {}}}}}
    _assert_param_in_contract("sante", "effort_hopital", reg)  # ne lève pas


def test_param_in_contract_accepts_real_key_coexisting_with_sentinels():
    """Une clé réelle reste valide même si la mesure porte aussi des

    sentinelles (régression si l'opérande du `- _CONTRACT_SENTINELS`
    était inversé)."""
    reg = {
        "mesures": {
            "x": {"params": {"vrai": {}, _DYNAMIC: {}, _UNMODELED: {}}}
        }
    }
    _assert_param_in_contract("x", "vrai", reg)  # ne lève pas


def test_param_in_contract_rejects_non_contract_key_loud():
    """Garde rouge-vert : clé pilote absente du registre (= clé morte

    ré-introduite dans le JSON) → échec bruyant."""
    reg = {"mesures": {"sante": {"params": {"effort_hopital": {}}}}}
    with pytest.raises(RuntimeError, match="HORS contrat"):
        _assert_param_in_contract("sante", "arrets_reforme", reg)


def test_param_in_contract_rejects_sentinel_as_pilot_key():
    """`<DYNAMIC>`/`<UNMODELED>` ne sont pas des clés de contrat."""
    reg = {"mesures": {"x": {"params": {_DYNAMIC: {}, _UNMODELED: {}}}}}
    with pytest.raises(RuntimeError, match="HORS contrat"):
        _assert_param_in_contract("x", _DYNAMIC, reg)


def test_param_in_contract_distinguishes_missing_measure():
    """Mesure handler-backed absente du registre → message DÉDIÉ

    (« registre périmé »), pas le message trompeur « clé morte »."""
    reg = {"mesures": {"autre": {"params": {"k": {}}}}}
    with pytest.raises(RuntimeError, match="absent du registre"):
        _assert_param_in_contract("sante", "effort_hopital", reg)
