"""Contrat anti-double-comptage ASU ↔ prestations_indexation.

L'ASU (Allocation Sociale Unique) unifie RSA / prime d'activité / APL.
Si l'ASU est dans le scénario, une désindexation séparée de ces mêmes
prestations est un DOUBLE-COMPTAGE : ``_apply_prestations_indexation``
doit donc se neutraliser quand l'ASU est active.

CORRECTION v0.6.1 (lot 5) — le COMPORTEMENT testé ici est inchangé, la
JUSTIFICATION l'est : jusqu'à la v0.6.0, ce fichier et les docstrings du
handler écrivaient que l'ASU absorbe « exactement » la base 90 Md€ du
levier d'indexation. C'est faux. Le périmètre officiel de la réforme est
de 39 Md€ (RSA + prime d'activité + APL ; les prestations familiales sont
HORS réforme). La neutralisation reste TOTALE, comme choix
CONSERVATEUR assumé : elle ne peut qu'ÔTER des économies à un scénario
qui cumule les deux leviers, jamais lui en offrir. Re-baser le levier
d'indexation, dont l'assiette n'a pas été auditée par le lot ASU, est un
chantier distinct.

La neutralisation doit dériver de la MÊME source unique que le reste de
l'anti-double-comptage ASU (``mesures['asu']`` via le prédicat de
``handlers._phasing``), PAS d'un paramètre ``prestations_indexation.
asu_active`` jamais propagé depuis la mesure ``asu`` (collision de
nommage : la garde historique était inerte dans les scénarios utilisant
la convention « source unique », ex. ``lr_2027``).

Ces tests verrouillent : (a) ASU active via ``mesures`` → neutralisé
même SANS ``asu_active`` dans les params ; (b) ASU absente → levier
plein (inchangé) ; (c) prédicat ``!= 0`` aligné sur ``asu_phasing``.
"""
import pytest

from budget_simulator.handlers._phasing import asu_is_active
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075
_YEAR = 2029  # year_idx = 4 > 0 → érosion active si non neutralisé


def _prestations_ds(mesures, year=_YEAR):
    """delta_spending de prestations_indexation pour `mesures` à `year`."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    ds, _, _ = sim._apply_prestations_indexation(
        {}, mesures['prestations_indexation'], year, _GDP, _INFLATION, _UNEMP)
    return ds


def test_neutralized_when_asu_active_via_mesures_without_asu_active_param():
    """Cœur du fix : forme exacte de lr_2027 (asu activé via la mesure
    `asu`, prestations_indexation SANS clé `asu_active`). La garde doit
    tirer depuis `mesures['asu']` → neutralisé → delta_spending == 0.

    Avant le fix la garde lisait `params.get('asu_active', 0)` (= 0 ici)
    → désindexation appliquée EN PLUS de l'ASU = double-comptage."""
    ds = _prestations_ds({
        'asu': {'asu_activation': 1},
        'prestations_indexation': {'taux_indexation': 0.005},
    })
    assert ds == 0, (
        f"prestations_indexation doit être neutralisé quand l'ASU est active "
        f"via mesures['asu'] (double-comptage des prestations unifiées "
        f"sinon) ; ds={ds}"
    )


def test_not_neutralized_when_asu_absent():
    """Réciproque (non-régression) : ASU absente → levier plein, une
    sous-indexation produit bien une économie réelle (ds < 0)."""
    ds = _prestations_ds({
        'prestations_indexation': {'taux_indexation': 0.005},
    })
    assert ds < 0, (
        f"Sans ASU, une désindexation (taux 0.005) doit produire une "
        f"économie réelle non nulle ; ds={ds}"
    )


def test_neutralized_when_asu_inactive_is_false():
    """ASU présente mais désactivée (`asu_activation: 0`) → NON neutralisé
    (prédicat aligné sur asu_phasing : actif ssi asu_activation != 0)."""
    ds = _prestations_ds({
        'asu': {'asu_activation': 0},
        'prestations_indexation': {'taux_indexation': 0.005},
    })
    assert ds < 0, f"ASU désactivée ne doit pas neutraliser ; ds={ds}"


def test_predicate_matches_asu_phasing_non_zero():
    """Toggle dévié à 0.5 (harnais standalone) = ACTIF, comme
    `asu_phasing` / `_apply_asu` (prédicat `!= 0`, pas `== 1`)."""
    ds = _prestations_ds({
        'asu': {'asu_activation': 0.5},
        'prestations_indexation': {'taux_indexation': 0.005},
    })
    assert ds == 0, (
        f"asu_activation=0.5 doit être traité ACTIF (prédicat != 0) → "
        f"prestations_indexation neutralisé ; ds={ds}"
    )


def test_malformed_asu_fails_loudly_not_silently(monkeypatch):
    """DÉCISION (révisée v0.6.7) : un `asu` mal formé (non-dict, ex. raccourci
    humain `{'asu': 1}` au lieu de `{'asu_activation': 1}`) DOIT échouer
    bruyamment, PAS être neutralisé en silence — et il doit échouer SUR LE
    LEVIER `asu`, pas sur ses lecteurs latéraux.

    Révision : la version d'origine exigeait que `asu_is_active` lève
    (AttributeError), faute d'autre signal à l'époque. Depuis la porte du
    05/10/2026 (Sentry FRANCE-BUDGET-Z), un bloc mal formé est qualifié par
    `apply_measures` sur le levier lui-même (`logger.error` +
    `HANDLER_FAILED_KEY` ; `ExceptionGroup` en STRICT), et les lecteurs
    latéraux le traitent comme absent (`valeur_brute`). Lever DANS
    `asu_is_active` faisait échouer à sa place prestations_indexation et
    fraude_sociale : désindexation perdue, échec attribué au mauvais levier,
    et une ASU en échec (donc non appliquée) neutralisait quand même les
    prestations. Le contrat « bruyant » est conservé, déplacé à la porte ;
    la byte-identité d'`asu_phasing` sur toute entrée valide est vérifiée par
    le golden master. Le trou « clé `asu` mal orthographiée » relève toujours
    du contrat de params (Item 2)."""
    from budget_simulator.constants import HANDLER_FAILED_KEY
    mesures = {'asu': 1, 'prestations_indexation': {'taux_indexation': 0.005}}
    assert asu_is_active({'asu': 1}) is False
    # Tolérant : échec tracé sur `asu`, prestations calculées (ASU non appliquée).
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    an = rapport['measure_impacts_by_year'][4]
    assert an['asu'][HANDLER_FAILED_KEY] is True
    assert HANDLER_FAILED_KEY not in an['prestations_indexation']
    assert _prestations_ds(mesures) < 0
    # STRICT : la simulation lève, et le seul levier mis en cause est `asu`.
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    with pytest.raises(ExceptionGroup) as exc:
        BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    notes = [n for e in exc.value.exceptions for n in getattr(e, '__notes__', [])]
    assert notes and all(n.startswith('measure_id=asu,') for n in notes), notes
