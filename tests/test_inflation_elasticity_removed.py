"""Verrou de régression — branche d'élasticité recettes supprimée (Phase 2, option B).

Contexte : un ajustement `revenues_after *= 1 + (inflation -
inflation_precedente) * 0.5` se trouvait dans `OrchestratorMixin.simulate()`,
juste après l'appel `calculate_inflation`. Il était MORT par construction
(`calculate_inflation` réécrit `self.inflation_precedente` avec la valeur
courante → écart toujours nul) et faisait DOUBLE EMPLOI avec l'élasticité au
PIB nominal de `calculate_revenues`. Décision 2026-05-16 : suppression
(option B), validée par 2 agents adverses. Détail :
docs/REFACTOR_SPLIT_PLAN.md.

Ces tests verrouillent les deux invariants sur lesquels la décision repose,
pour qu'une régression future (réintroduction de l'ajustement, ou retrait de
l'écriture in-méthode de `calculate_inflation` conservée volontairement)
échoue bruyamment plutôt que de revenir au double-comptage silencieux.
"""
import inspect
from unittest.mock import patch

from budget_simulator.engine import orchestrator as orchestrator_mod


def test_calculate_inflation_invariant_inflation_precedente_equals_return(simulator):
    """`calculate_inflation` pose `self.inflation_precedente == valeur retournée`.

    C'est CETTE invariante (dernière instruction de `calculate_inflation`,
    `self.inflation_precedente = inflation`, conservée volontairement) qui
    rendait le garde d'élasticité supprimé inactif par construction. Si elle
    saute (ex. retrait de cette écriture sans analyse), ce test échoue →
    signal explicite avant tout re-réveil accidentel d'un canal
    inflation→recettes en double.

    Utilise la fixture `simulator` du conftest (1 période, base_params
    calibrés — fixture canonique des tests unitaires `calculate_inflation`).
    """
    economic_state = {
        'output_gap': -0.015,
        'unemployment_gap': 0.001,
        'effort_budgetaire': -0.007,
        'tva_impact': 0.0071,
    }
    simulator.inflation_precedente = 0.01
    with patch('numpy.random.normal', return_value=0):
        inflation = simulator.calculate_inflation(year=1, economic_state=economic_state)

    assert simulator.inflation_precedente == inflation, (
        "calculate_inflation doit laisser self.inflation_precedente == valeur "
        "retournée (sa dernière instruction). Si cette invariante change, "
        "relire docs/REFACTOR_SPLIT_PLAN.md (item branche élasticité) AVANT de "
        "modifier — risque de double-comptage inflation→recettes."
    )


def test_no_revenue_elasticity_adjustment_reintroduced():
    """Le source de `simulate()` ne réintroduit pas l'ajustement supprimé.

    La branche `revenues_after *= 1 + (inflation - inflation_precedente)
    * 0.5` a été supprimée pour cause de double-comptage avec l'élasticité
    au PIB nominal de `calculate_revenues`. La réintroduire (même réactivée
    « proprement ») doit être une décision méthodologique explicite (nouvelle
    baseline golden master + METHODOLOGIE.md), pas un ajout silencieux.

    Limitation ASSUMÉE : garde par token littéral `elasticity_adjust` dans
    le seul `orchestrator.py`. Une réintroduction sous un autre identifiant,
    en expression inline, ou dans `revenues.py`/`inflation.py`, n'est PAS
    détectée. Le vrai filet de sécurité méthodologique reste la baseline
    golden master byte-identique + la revue ; ce test n'est qu'un rappel
    in-situ bon marché contre le copier-coller du motif d'origine.
    """
    src = inspect.getsource(orchestrator_mod)
    assert "elasticity_adjust" not in src, (
        "Un 'elasticity_adjust' a été réintroduit dans orchestrator.py. "
        "L'ajustement d'élasticité recettes sur la VARIATION d'inflation "
        "fait double emploi avec l'élasticité au PIB nominal de "
        "calculate_revenues (engine/revenues.py). Toute réintroduction doit "
        "être une décision méthodologique délibérée — voir "
        "docs/REFACTOR_SPLIT_PLAN.md (item Phase 2 résolu, option B)."
    )
