"""Tests unitaires des helpers de phasing (Lot B.1).

Verrouille l'équivalence byte-identique des patterns factorisés depuis
`additionnels.py` et le contrat des helpers partagés (utilisés aussi par
les appelants Lot B.2).
"""
import pytest

from budget_simulator.handlers._phasing import (
    _one_time_level,
    _resolve_intensite_or_legacy,
    _year_phasing,
)


@pytest.mark.parametrize("years_elapsed,expected", [
    (-2, 0.0), (-1, 0.0), (0, 42.0), (1, 0.0), (5, 0.0),
])
def test_one_time_level(years_elapsed, expected):
    assert _one_time_level(years_elapsed, 42.0) == expected


def test_one_time_level_evaluates_value_eagerly():
    """Le contrat byte-identique suppose ``value`` déjà évalué (pur)."""
    assert _one_time_level(3, -0.005) == 0.0
    assert _one_time_level(0, -0.005) == -0.005


@pytest.mark.parametrize("years_elapsed,expected", [
    (-1, 0.0),          # pas encore en vigueur
    (0, 1.0), (1, 1.0), (9, 1.0),  # schedule (1.0,) = plein effet immédiat
])
def test_year_phasing_immediate(years_elapsed, expected):
    """`(1.0,)` ≡ ancien `0.0 if years_elapsed < 0 else 1.0`."""
    assert _year_phasing(years_elapsed, (1.0,)) == expected


@pytest.mark.parametrize("years_elapsed,expected", [
    (-1, 0.0), (0, 0.5), (1, 1.0), (2, 1.0), (7, 1.0),
])
def test_year_phasing_ramp_clamped_to_last(years_elapsed, expected):
    """Schedule multi-paliers borné à la dernière valeur (format PHASING_*)."""
    assert _year_phasing(years_elapsed, (0.5, 1.0)) == expected


def test_year_phasing_empty_schedule_raises():
    """Schedule vide = erreur de programmation explicite (pas IndexError)."""
    with pytest.raises(ValueError, match="schedule vide"):
        _year_phasing(0, ())


def test_resolve_intensite_simplified_branch():
    """`intensite` présent (même 0.0) → branche simplifiée (parité pré-refactor)."""
    out = _resolve_intensite_or_legacy(
        {'intensite': 0.0}, lambda i: ('simpl', i), lambda p: ('legacy',)
    )
    assert out == ('simpl', 0.0)


def test_resolve_intensite_legacy_branch():
    """`intensite` absent → branche legacy avec lecture des params."""
    out = _resolve_intensite_or_legacy(
        {'taux': 0.25}, lambda i: ('simpl',), lambda p: ('legacy', p.get('taux'))
    )
    assert out == ('legacy', 0.25)
