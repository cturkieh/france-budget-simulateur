"""Revue 2026-08-04 — domaines des paramètres NOMMÉS (PARAM_DOMAINS).

La symétrisation des handlers retraites/prestations remplace les if/elif
directionnels par de l'arithmétique uniforme : un NaN qui était neutralisé
PAR ACCIDENT (comparaisons toutes False → terme sauté) se propagerait
désormais jusqu'au DataFrame — déficit/dette NaN 2026-2035, aucun signal
(pas de HANDLER_FAILED, pas de CLIP, mesure absente de measure_impacts),
HTTP 500 opaque à la sérialisation. Prouvé en revue (silent-failure-hunter).
S'y ajoute la bande silencieuse hors-UI (indexation=-10 → -21 pts de dette,
HTTP 200, zéro trace).

Même philosophie et même contrat dual qu'INTENSITE_DOMAINS (Lot C Item 1) :
tolérant = warning PARAM_DOMAIN_CLAMP + clamp ; BUDGETLAB_STRICT =
ValueError → ExceptionGroup. Une `str` lève TOUJOURS TypeError (contrat
MIXIN_BAD_PARAMS préservé).
"""
import os
from unittest.mock import patch

import pytest

from budget_simulator.constants import PARAM_DOMAINS
from budget_simulator.engine._param_domain import validate_param_domains
from budget_simulator.simulator import BudgetSimulatorV45


# --------------------------------------------------------------------------
# Fonction pure
# --------------------------------------------------------------------------

def test_noop_for_measure_without_named_domains():
    """Mesure hors registre : params rendus tels quels (objet identique)."""
    params = {'taux': 999.0}
    out = validate_param_domains('tva_rate', params, strict=True)
    assert out is params


def test_noop_when_param_absent_or_none():
    """Paramètre absent ou None → no-op (les défauts du handler font foi)."""
    params = {'age_depart': 62.75}  # indexation/duree absents
    out = validate_param_domains('retraites', params, strict=True)
    assert out is params
    params_none = {'indexation': None}
    out_none = validate_param_domains('retraites', params_none, strict=True)
    assert out_none is params_none


def test_in_domain_values_return_same_object():
    """Valeurs légitimes (bornes incluses) → objet identique (golden
    master byte-identique sur toute entrée valide)."""
    params = {'age_depart': 60.0, 'indexation': 1.2, 'duree_cotisation': 45.0}
    out = validate_param_domains('retraites', params, strict=True)
    assert out is params


def test_nan_indexation_traite_hors_domaine():
    """NaN n'est ni < low ni > high : sans garde explicite il empoisonne
    toute la trajectoire en silence. Strict = ValueError, tolérant =
    clamp borne basse + copie défensive."""
    nan = float('nan')
    params = {'indexation': nan}
    with pytest.raises(ValueError, match='hors domaine'):
        validate_param_domains('retraites', params, strict=True)
    out = validate_param_domains('retraites', params, strict=False)
    assert out is not params
    assert out['indexation'] == 0.0


def test_hors_domaine_clampe_a_la_borne_la_plus_proche():
    """-10 → borne basse ; 100 → borne haute (tolérant)."""
    out_low = validate_param_domains('retraites', {'indexation': -10.0}, strict=False)
    assert out_low['indexation'] == 0.0
    out_high = validate_param_domains('retraites', {'indexation': 100.0}, strict=False)
    assert out_high['indexation'] == 1.2


def test_str_param_leve_toujours_typeerror():
    """LOAD-BEARING (contrat MIXIN_BAD_PARAMS) : une str lève TypeError au
    comparateur, dans les deux modes — jamais ValueError ni early-return."""
    for strict in (True, False):
        with pytest.raises(TypeError):
            validate_param_domains('retraites', {'indexation': 'abc'}, strict=strict)


def test_prestations_taux_indexation_couvert():
    """Le levier frère symétrisé le même jour est au registre lui aussi.
    Forme du registre : {measure_id: {param: (low, high)}} — lookup O(1)
    par mesure, aligné sur INTENSITE_DOMAINS (finition revue finale)."""
    assert 'taux_indexation' in PARAM_DOMAINS['prestations_indexation']
    out = validate_param_domains(
        'prestations_indexation', {'taux_indexation': float('nan')}, strict=False)
    assert out['taux_indexation'] == 0.0


def test_warning_deduplique_par_simulation(caplog):
    """Finition revue finale : le clamp d'une même (mesure, param) hors
    domaine se journalise UNE fois par simulation, pas une fois par année
    simulée (mesuré avant : ~10 lignes WARNING pour une seule erreur —
    bruit pur pour Sentry Logs, l'info est identique chaque année)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': -10.0}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        sim.simulate()
    clamps = [r for r in caplog.records if 'PARAM_DOMAIN_CLAMP' in r.message]
    assert len(clamps) == 1, f"{len(clamps)} warnings pour une seule erreur"
    # Et une 2e simulation sur la même instance ré-alerte (état par run).
    caplog.clear()
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        sim.simulate()
    clamps2 = [r for r in caplog.records if 'PARAM_DOMAIN_CLAMP' in r.message]
    assert len(clamps2) == 1, "le reset par simulation doit ré-armer l'alerte"


# --------------------------------------------------------------------------
# Intégration (branchement orchestrateur)
# --------------------------------------------------------------------------

def test_nan_indexation_ne_pollue_plus_la_trajectoire(caplog):
    """Bout-en-bout tolérant : NaN → trajectoire ENTIÈREMENT finie + trace
    PARAM_DOMAIN_CLAMP (avant ce garde : déficit/dette NaN sans un signal)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        df, _, _ = sim.simulate()
    assert df['Déficit/PIB %'].notna().all(), "trajectoire NaN = échec silencieux"
    assert df['Dette/PIB %'].notna().all()
    assert any('PARAM_DOMAIN_CLAMP' in rec.message for rec in caplog.records), \
        "le clamp doit laisser une trace filtrable (Sentry Logs)"


def test_strict_nan_escalade_en_exceptiongroup_valueerror():
    """Bout-en-bout strict : NaN → ExceptionGroup contenant un ValueError
    (synergie Lot C Item 3, aucune mécanique nouvelle)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    inner = excinfo.value.exceptions
    assert len(inner) == 1 and isinstance(inner[0], ValueError)
