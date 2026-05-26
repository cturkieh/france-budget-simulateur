"""Contrat anti-double-comptage ASU ↔ prestations_indexation.

L'ASU (Allocation Sociale Unique) fusionne et absorbe RSA / Prime
activité / APL / allocations familiales — exactement la base 90 Md€ du
levier ``prestations_indexation`` (cf. docstrings ``_apply_asu`` et
``_apply_prestations_indexation``). Si l'ASU est dans le scénario, une
désindexation séparée de ces mêmes 90 Md€ est un DOUBLE-COMPTAGE :
``_apply_prestations_indexation`` doit donc se neutraliser quand l'ASU
est active.

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
        f"via mesures['asu'] (double-comptage des 90 Md€ sinon) ; ds={ds}"
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


def test_malformed_asu_fails_loudly_not_silently():
    """DÉCISION verrouillée : un `asu` mal formé (non-dict, ex. raccourci
    humain `{'asu': 1}` au lieu de `{'asu_activation': 1}`) DOIT échouer
    bruyamment, PAS neutraliser/ignorer en silence.

    Cohérent avec la convention projet (MIXIN_BAD_PARAMS → _handler_failed
    / ExceptionGroup STRICT) : un param malformé remonte, il n'est jamais
    silencieusement absorbé. Ne PAS « durcir » `asu_is_active` en
    `isinstance(asu, dict)` : cela (a) casserait la byte-identité de
    `asu_phasing` (l'ancien code crashait aussi sur non-dict), (b)
    transformerait un échec bruyant en neutralisation silencieuse —
    l'inverse de la convention. Le trou « clé `asu` mal orthographiée →
    pas de neutralisation » relève du contrat de params (Item 2)."""
    with pytest.raises(AttributeError):
        asu_is_active({'asu': 1})
    with pytest.raises(AttributeError):
        _prestations_ds({
            'asu': 1,
            'prestations_indexation': {'taux_indexation': 0.005},
        })
