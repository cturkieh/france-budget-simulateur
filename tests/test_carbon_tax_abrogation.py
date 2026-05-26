"""Couverture de la plage [0, 44.6) pour taxe_carbone (suite à `min: 0` dans policy_measures.json).

Avant le fix, `min: 50` rendait toute valeur < 44.6 inatteignable depuis le slider.
Avec `min: 0`, les scénarios "abrogation/moratoire taxe carbone" deviennent simulables.
Ces tests garantissent que les formules de _apply_transition_ecologique restent cohérentes
sur cette nouvelle plage (signe inversé attendu vs hausse au-dessus de 44.6).
"""
import sys
sys.path.insert(0, '.')
from budget_simulator.simulator import BudgetSimulatorV45


BASELINE_TAXE = 44.6  # statu quo France 2018-2025 (taxe gelée)


def _simulate(taxe_carbone):
    mesures = {
        'transition_ecologique': {
            'investissement': 0,
            'taxe_carbone': taxe_carbone,
            'renovation': 0,
        }
    }
    sim = BudgetSimulatorV45(mesures=mesures)
    df, _, _ = sim.simulate()
    return df


def test_baseline_44_6_neutre():
    """À 44.6, le delta vs simulation sans mesure doit être négligeable (status quo)."""
    df_baseline = BudgetSimulatorV45().simulate()[0]
    df_status_quo = _simulate(BASELINE_TAXE)
    deficit_diff = abs(df_baseline.iloc[-1]['Déficit/PIB %'] - df_status_quo.iloc[-1]['Déficit/PIB %'])
    assert deficit_diff < 0.05, (
        f"Taxe à baseline (44.6) doit être ~neutre, écart déficit = {deficit_diff:.3f} pts"
    )


def test_abrogation_reduit_recettes():
    """taxe_carbone = 0 doit produire des recettes plus basses qu'au statu quo."""
    df_status_quo = _simulate(BASELINE_TAXE)
    df_abrogation = _simulate(0)
    deficit_sq = df_status_quo.iloc[-1]['Déficit/PIB %']
    deficit_abr = df_abrogation.iloc[-1]['Déficit/PIB %']
    # Abrogation → moins de recettes → déficit plus dégradé (plus négatif ou plus de déficit)
    assert deficit_abr < deficit_sq, (
        f"Abrogation (ct=0) doit dégrader le déficit vs baseline: sq={deficit_sq:.2f}, abr={deficit_abr:.2f}"
    )


def test_signe_inverse_baisse_vs_hausse():
    """Une baisse sous baseline et une hausse au-dessus doivent produire des effets de signes opposés."""
    df_hausse = _simulate(100)  # +55.4 vs baseline
    df_baisse = _simulate(0)    # -44.6 vs baseline
    df_baseline = _simulate(BASELINE_TAXE)

    deficit_baseline = df_baseline.iloc[-1]['Déficit/PIB %']
    delta_hausse = df_hausse.iloc[-1]['Déficit/PIB %'] - deficit_baseline
    delta_baisse = df_baisse.iloc[-1]['Déficit/PIB %'] - deficit_baseline

    # Hausse de la taxe → recettes ↑ → déficit moins négatif (delta > 0)
    # Baisse de la taxe → recettes ↓ → déficit plus négatif (delta < 0)
    assert delta_hausse * delta_baisse < 0, (
        f"Signes opposés attendus: delta_hausse={delta_hausse:.3f}, delta_baisse={delta_baisse:.3f}"
    )


def test_continuite_passage_baseline():
    """Aucune discontinuité numérique au franchissement de 44.6 (formules linéaires en (ct - 44.6))."""
    df_juste_sous = _simulate(40)
    df_juste_au_dessus = _simulate(50)
    df_baseline = _simulate(BASELINE_TAXE)

    deficit_baseline = df_baseline.iloc[-1]['Déficit/PIB %']
    delta_sous = df_juste_sous.iloc[-1]['Déficit/PIB %'] - deficit_baseline
    delta_au_dessus = df_juste_au_dessus.iloc[-1]['Déficit/PIB %'] - deficit_baseline

    # Symétrie approximative : un écart de 4.6 sous baseline et 5.4 au-dessus doit produire
    # des deltas du même ordre de grandeur (pas un saut d'un facteur 10+)
    if abs(delta_au_dessus) > 0.001:
        ratio = abs(delta_sous) / abs(delta_au_dessus)
        assert 0.3 < ratio < 3.0, (
            f"Discontinuité suspecte au passage de 44.6: ratio={ratio:.2f}"
        )
