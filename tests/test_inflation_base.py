"""Verrou — terme structurel de la courbe de Phillips = source unique nommée.

Contexte : le terme constant de la courbe de Phillips de `engine/inflation.py`
était un littéral magique `0.012` (1,2 %), remplacé par une constante nommée
en mai 2026.

Calibration courante — 1,6 % (v0.6.1, item I15/R4). La valeur précédente
(1,5 %) était une médiane entre une sous-jacente INSEE et une cible BCE, donc
un mélange d'IPC et d'IPCH, alors que la variable `inflation` du moteur EST
le déflateur du PIB (arbitrage I17). Le 1,6 % est le bout d'une chaîne
d'ancrage entièrement sourcée — 2,0 % IPCH zone euro (BCE, SPF T3 2026) →
≈1,75 % IPC France (RAA 2026, note 6, qui écrit l'écart explicitement) →
≈1,6 % déflateur (INSEE, blog sept. 2022) — cohérente avec le corridor
officiel de déflateur 1,3/1,6/1,6/1,5/1,5 % (RAA 2026 T2, mission IGF 2030).
Détail des maillons dans `constants.py`.

Ces tests verrouillent TROIS invariants :

1. La valeur est 0.016 ET provient d'UNE constante nommée
   (`constants.INFLATION_STRUCTURELLE`), pas d'un littéral magique réécrit
   ailleurs. Un changement de calibration futur doit toucher LA constante,
   pas un nombre noyé dans la formule.
2. `INFLATION_STRUCTURELLE` reste DISTINCT de `INFLATION_BASE` (graine
   d'inertie `inflation_precedente` en année 0, lue par
   simulator/orchestrator). Les confondre ré-introduirait la confusion
   conceptuelle que ce chantier supprime.
3. La constante alimente bien la courbe — désormais À TRAVERS la fonction
   d'ancrage `point_fixe_phillips_ancree`, source unique de la forme depuis
   la v0.6.1. Le test SUIT le code au lieu de ré-énoncer une formule.
"""
import inspect

from budget_simulator import constants
from budget_simulator.engine import inflation as inflation_mod


def test_inflation_structurelle_constant_value():
    """La constante nommée existe et vaut 0.016 (v0.6.1, item I15/R4)."""
    assert hasattr(constants, "INFLATION_STRUCTURELLE"), (
        "constants.INFLATION_STRUCTURELLE doit exister : source unique nommée "
        "du point fixe de la courbe de Phillips (remplace le littéral 0.012)."
    )
    assert constants.INFLATION_STRUCTURELLE == 0.016, (
        f"INFLATION_STRUCTURELLE = {constants.INFLATION_STRUCTURELLE!r}, attendu "
        "0.016 (1,6 % — DÉFLATEUR du PIB tendanciel, chaîne d'ancrage BCE SPF "
        "T3 2026 → RAA 2026 note 6 → INSEE déflateurs, cf. constants.py). "
        "Tout changement de calibration passe par CETTE constante + "
        "régénération golden master."
    )


def test_phillips_utilise_la_constante_nommee_pas_un_litteral_magique():
    """La courbe référence la constante nommée, pas `0.012` en dur.

    Garde par lecture du source. Depuis la v0.6.1 la formule passe par la
    fonction d'ancrage `point_fixe_phillips_ancree` (source unique de la
    courbe) : le test suit ce chaînage — constante → ancrage →
    `calculate_inflation` — au lieu d'exiger que le nom apparaisse dans un
    corps de méthode qu'un refactor légitime peut déplacer.
    """
    src_ancrage = inspect.getsource(inflation_mod.point_fixe_phillips_ancree)
    assert "0.012" not in src_ancrage, (
        "Le littéral magique 0.012 (ancien intercept Phillips) subsiste. Il "
        "doit être remplacé par constants.INFLATION_STRUCTURELLE."
    )
    assert "INFLATION_STRUCTURELLE" in src_ancrage, (
        "point_fixe_phillips_ancree doit référencer INFLATION_STRUCTURELLE "
        "(import nommé) comme point fixe de la courbe de Phillips."
    )
    src_methode = inspect.getsource(inflation_mod.InflationMixin.calculate_inflation)
    assert "point_fixe_phillips_ancree" in src_methode, (
        "calculate_inflation doit passer par point_fixe_phillips_ancree : "
        "une formule ré-écrite en dur rouvrirait la porte au défaut de forme "
        "corrigé en v0.6.1 (terme de gap hors ancrage)."
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
