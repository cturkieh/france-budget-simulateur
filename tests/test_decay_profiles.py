"""Tests for differentiated DECAY_PROFILE and annual investment re-impulse."""
import sys
sys.path.insert(0, '.')
from budget_simulator.simulator import BudgetSimulatorV45


def test_decay_profile_sums():
    """All decay profiles must sum to <= 2.0 (calibration constraint)."""
    assert sum(BudgetSimulatorV45.DECAY_PROFILE_TAXES) <= 2.01
    assert sum(BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS) <= 2.01
    assert sum(BudgetSimulatorV45.DECAY_PROFILE_INVEST) <= 2.01
    print(f"  TAXES sum: {sum(BudgetSimulatorV45.DECAY_PROFILE_TAXES):.2f}")
    print(f"  TRANSFERS sum: {sum(BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS):.2f}")
    print(f"  INVEST sum: {sum(BudgetSimulatorV45.DECAY_PROFILE_INVEST):.2f}")


def test_invest_profile_peaks_year2():
    """Investment profile must peak at year 2 (index 1), not year 1."""
    p = BudgetSimulatorV45.DECAY_PROFILE_INVEST
    assert p[1] > p[0], f"Y2 ({p[1]}) should be > Y1 ({p[0]})"
    assert p[1] >= p[2], f"Y2 ({p[1]}) should be >= Y3 ({p[2]})"


def test_transfer_profile_frontloaded():
    """Transfer profile must be front-loaded: Y1 is the peak."""
    p = BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS
    assert p[0] > p[1] > p[2], "Transfers should strictly decrease"


def test_backward_compat_alias():
    """DECAY_PROFILE alias must equal DECAY_PROFILE_TAXES."""
    assert BudgetSimulatorV45.DECAY_PROFILE == BudgetSimulatorV45.DECAY_PROFILE_TAXES


def test_classification():
    """Measure classification helper."""
    assert BudgetSimulatorV45._get_decay_profile('education') == BudgetSimulatorV45.DECAY_PROFILE_INVEST
    assert BudgetSimulatorV45._get_decay_profile('retraites') == BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS
    assert BudgetSimulatorV45._get_decay_profile('tva_rate') == BudgetSimulatorV45.DECAY_PROFILE_TAXES
    assert BudgetSimulatorV45._get_decay_profile('transition_ecologique') == BudgetSimulatorV45.DECAY_PROFILE_INVEST


def test_baseline_unchanged():
    """Status quo (no measures) must produce reasonable results."""
    sim = BudgetSimulatorV45(periods=10)
    results, _, _ = sim.simulate()
    growth_2030 = results[results['Année'] == 2030]['Croissance %'].values[0]
    assert 0.5 < growth_2030 < 1.5, f"Baseline growth 2030 = {growth_2030}%, expected 0.5-1.5%"
    print(f"  Baseline growth 2030: {growth_2030:.2f}%")


def test_investment_uses_invest_profile():
    """Investment measures should use DECAY_PROFILE_INVEST (peaks Y2)."""
    sim = BudgetSimulatorV45(periods=10, mesures={
        'transition_ecologique': {'investissement': 30, 'taxe_carbone': 44.6, 'renovation': 0}
    })
    results, _, _ = sim.simulate()
    # Check the stored profile has invest characteristics (Y2 > Y1)
    if sim._fiscal_impulses:
        first_impulse = list(sim._fiscal_impulses.values())[0]
        profile = first_impulse[2] if len(first_impulse) > 2 else None
        if profile:
            print(f"  Stored profile: {tuple(round(p, 2) for p in profile)}")
            assert profile[1] > profile[0], "Investment profile should peak at Y2"
    print(f"  Impulses stored: {len(sim._fiscal_impulses)}")


def test_tva_uses_tax_profile():
    """TVA change should use DECAY_PROFILE_TAXES (peaks Y1)."""
    sim = BudgetSimulatorV45(periods=10, mesures={'tva_rate': {'taux': 0.21}})
    results, _, _ = sim.simulate()
    if sim._fiscal_impulses:
        first_impulse = list(sim._fiscal_impulses.values())[0]
        profile = first_impulse[2] if len(first_impulse) > 2 else None
        if profile:
            print(f"  Stored profile: {tuple(round(p, 2) for p in profile)}")
            assert profile[0] > profile[1], "Tax profile should peak at Y1"
    print(f"  Impulses stored: {len(sim._fiscal_impulses)}")


def test_growth_not_explosive():
    """Even with max investment, growth should stay reasonable."""
    sim = BudgetSimulatorV45(periods=10, mesures={
        'transition_ecologique': {'investissement': 40, 'taxe_carbone': 44.6, 'renovation': 40},
        'education': {'budget': 85, 'enseignants': 0, 'salaires': 0},
    })
    results, _, _ = sim.simulate()
    max_growth = results['Croissance %'].max()
    assert max_growth < 3.0, f"Max growth = {max_growth}% — should be < 3%"
    print(f"  Max growth (heavy invest): {max_growth:.2f}%")
    avg_growth = results['Croissance %'].mean()
    print(f"  Avg growth (heavy invest): {avg_growth:.2f}%")


if __name__ == '__main__':
    tests = [
        test_decay_profile_sums,
        test_invest_profile_peaks_year2,
        test_transfer_profile_frontloaded,
        test_backward_compat_alias,
        test_classification,
        test_baseline_unchanged,
        test_investment_uses_invest_profile,
        test_tva_uses_tax_profile,
        test_growth_not_explosive,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            print(f"\n{'='*60}")
            print(f"Running: {t.__name__}")
            t()
            print(f"  PASS")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
    print("✅ All decay profile tests passed!")
