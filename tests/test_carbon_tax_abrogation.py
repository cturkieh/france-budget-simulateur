"""Couverture de la plage [0, 44.6) pour taxe_carbone (suite à `min: 0` dans policy_measures.json).

Avant le fix, `min: 50` rendait toute valeur < 44.6 inatteignable depuis le slider.
Avec `min: 0`, les scénarios "abrogation/moratoire taxe carbone" deviennent simulables.
Ces tests garantissent que les formules de _apply_transition_ecologique restent cohérentes
sur cette nouvelle plage (signe inversé attendu vs hausse au-dessus de 44.6).

RECALIBRAGE 2026-06 — robustesse de la mesure : ces tests mesuraient l'effet sur le
Déficit/PIB de la DERNIÈRE année (2035). Or l'effet net de la taxe sur le déficit y est
minuscule (~0.05 pt) et NON-MONOTONE dans le temps : en 2027 la recette directe domine
(signe correct), mais à long terme l'érosion du PIB (via la croissance) finit par l'emporter
et inverse le signe — lu sur un déficit arrondi à 0.01 pt, c'était fragile par construction.
Le HANDLER est directionnellement correct (cf. recettes ci-dessous) ; seule la SONDE était
mauvaise. On mesure désormais l'effet DIRECT sur les RECETTES en euros à 2027 (signal franc,
monotone, sans érosion-PIB cumulée), ce qui teste réellement le signe de la formule.
"""
import sys
sys.path.insert(0, '.')
from budget_simulator.simulator import BudgetSimulatorV45


BASELINE_TAXE = 44.6  # statu quo France 2018-2025 (taxe gelée)
YEAR_2027 = 2  # index trajectoire : 0=2025, 2=2027


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


def _recettes_2027(taxe_carbone):
    """Recettes publiques en Md€ à 2027 (Recettes/PIB % × PIB nominal). Sonde directe de
    l'effet-recette de la taxe, robuste (avant que l'érosion-PIB de long terme ne brouille
    le signal) et invariante aux conventions d'affichage du déficit."""
    df = _simulate(taxe_carbone)
    return df['Recettes/PIB %'][YEAR_2027] / 100 * df['PIB'][YEAR_2027]


def test_baseline_44_6_neutre():
    """À 44.6, le delta vs simulation sans mesure doit être négligeable (status quo)."""
    df_baseline = BudgetSimulatorV45().simulate()[0]
    df_status_quo = _simulate(BASELINE_TAXE)
    deficit_diff = abs(df_baseline.iloc[-1]['Déficit/PIB %'] - df_status_quo.iloc[-1]['Déficit/PIB %'])
    assert deficit_diff < 0.05, (
        f"Taxe à baseline (44.6) doit être ~neutre, écart déficit = {deficit_diff:.3f} pts"
    )


def test_abrogation_reduit_recettes():
    """taxe_carbone = 0 doit produire des recettes plus basses qu'au statu quo (effet direct 2027)."""
    rec_sq = _recettes_2027(BASELINE_TAXE)
    rec_abr = _recettes_2027(0)
    assert rec_abr < rec_sq, (
        f"Abrogation (ct=0) doit baisser les recettes 2027: sq={rec_sq:.2f} Md€, abr={rec_abr:.2f} Md€"
    )


def test_signe_inverse_baisse_vs_hausse():
    """Baisse sous baseline et hausse au-dessus → effets de SIGNES OPPOSÉS sur les recettes 2027."""
    rec_baseline = _recettes_2027(BASELINE_TAXE)
    delta_hausse = _recettes_2027(100) - rec_baseline  # taxe ↑ → recettes ↑ → delta > 0
    delta_baisse = _recettes_2027(0) - rec_baseline     # taxe ↓ → recettes ↓ → delta < 0
    assert delta_hausse > 0 > delta_baisse, (
        f"Signes opposés attendus sur recettes 2027: hausse={delta_hausse:+.3f}, baisse={delta_baisse:+.3f}"
    )


def test_continuite_passage_baseline():
    """Aucune discontinuité numérique au franchissement de 44.6 (formules linéaires en (ct - 44.6)).

    Mesure sur recettes 2027 : un écart de -4.6 (ct=40) et +5.4 (ct=50) doit produire des deltas
    du même ordre de grandeur (formule linéaire), pas un saut d'un facteur 10+."""
    rec_baseline = _recettes_2027(BASELINE_TAXE)
    delta_sous = _recettes_2027(40) - rec_baseline
    delta_au_dessus = _recettes_2027(50) - rec_baseline

    if abs(delta_au_dessus) > 0.001:
        ratio = abs(delta_sous) / abs(delta_au_dessus)
        assert 0.3 < ratio < 3.0, (
            f"Discontinuité suspecte au passage de 44.6: ratio={ratio:.2f}"
        )
