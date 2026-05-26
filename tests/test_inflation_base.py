"""Verrou — terme structurel de la courbe de Phillips = source unique nommée.

Contexte : le terme constant (intercept) de la courbe de Phillips augmentée
de `engine/inflation.py` était un littéral magique `0.012` (1,2 %). Décision PO
du 2026-05-18 : passage à 1,5 % (médian sourcé entre la sous-jacente INSEE 2025
à 1,2 % et le cœur Banque de France / cible BCE 1,6-2,0 % —
Option C, recoupement INSEE / Banque de France / BCE).

Ces tests verrouillent DEUX invariants :

1. La valeur est 0.015 ET provient d'UNE constante nommée
   (`constants.INFLATION_STRUCTURELLE`), pas d'un littéral magique réécrit
   ailleurs. Un changement de calibration futur doit toucher LA constante,
   pas un nombre noyé dans la formule.
2. `INFLATION_STRUCTURELLE` (intercept Phillips, ajouté chaque année) reste
   DISTINCT de `INFLATION_BASE` (graine d'inertie `inflation_precedente`
   en année 0, lue par simulator/orchestrator). Les confondre ré-introduirait
   la confusion conceptuelle que ce chantier supprime.
"""
import inspect

from budget_simulator import constants
from budget_simulator.engine import inflation as inflation_mod


def test_inflation_structurelle_constant_value():
    """La constante nommée existe et vaut 0.015 (décision PO 2026-05-18)."""
    assert hasattr(constants, "INFLATION_STRUCTURELLE"), (
        "constants.INFLATION_STRUCTURELLE doit exister : source unique nommée "
        "du terme intercept de la courbe de Phillips (remplace le littéral 0.012)."
    )
    assert constants.INFLATION_STRUCTURELLE == 0.015, (
        f"INFLATION_STRUCTURELLE = {constants.INFLATION_STRUCTURELLE!r}, attendu "
        "0.015 (1,5 % — médian sourcé INSEE sous-jacente / cœur BdF / cible BCE, "
        "note 2026-05-18 Option C, décision PO). Tout changement de calibration "
        "passe par CETTE constante + régénération golden master."
    )


def test_phillips_intercept_uses_named_constant_not_magic_literal():
    """`calculate_inflation` utilise la constante nommée, pas `0.012` en dur.

    Garde par lecture du source : le littéral `0.012` (ancien intercept) ne
    doit plus apparaître dans le corps de `calculate_inflation`, et la
    formule doit référencer `INFLATION_STRUCTURELLE`.
    """
    src = inspect.getsource(inflation_mod.InflationMixin.calculate_inflation)
    assert "0.012" not in src, (
        "Le littéral magique 0.012 (ancien intercept Phillips) subsiste dans "
        "calculate_inflation. Il doit être remplacé par "
        "constants.INFLATION_STRUCTURELLE (source unique nommée)."
    )
    assert "INFLATION_STRUCTURELLE" in src, (
        "calculate_inflation doit référencer INFLATION_STRUCTURELLE "
        "(import nommé) comme terme intercept de la courbe de Phillips."
    )


def test_inflation_base_distinct_from_structurelle():
    """`INFLATION_BASE` reste une constante VIVANTE et DISTINCTE.

    `INFLATION_BASE` n'est PAS morte : elle seede `inflation_precedente`
    (graine du terme d'inertie AR(1) en année 0) dans simulator.py et
    orchestrator.py. Elle est conceptuellement distincte du terme intercept
    Phillips (`INFLATION_STRUCTURELLE`, ajouté chaque année). Ce test verrouille
    la non-confusion : si quelqu'un fusionne les deux, relire la note
    2026-05-18 (§1.2) et le grep d'usage AVANT.
    """
    assert hasattr(constants, "INFLATION_BASE"), (
        "INFLATION_BASE doit subsister : graine d'inertie inflation_precedente "
        "(année 0), lue par simulator.py / orchestrator.py — pas une "
        "constante morte (cf. grep d'usage)."
    )
    assert constants.INFLATION_BASE != constants.INFLATION_STRUCTURELLE, (
        "INFLATION_BASE (graine d'inertie année 0) et INFLATION_STRUCTURELLE "
        "(intercept Phillips ajouté chaque année) sont deux paramètres "
        "ÉCONOMIQUEMENT distincts : ils ne doivent pas être confondus/égalisés."
    )
