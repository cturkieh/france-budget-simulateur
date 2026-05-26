"""
Test sensibilité : Le PA tombe-t-il toujours à 100.0 en 2035 ?
Ou est-ce une coïncidence numérique ?
"""

from budget_simulator.simulator import BudgetSimulatorV45

def test_pa_avec_seed_differents():
    """Tester avec différentes seeds aléatoires"""
    print("\n=== TEST SENSIBILITÉ PA (SEEDS ALÉATOIRES) ===\n")

    import numpy as np

    print("Seed | PA 2035 | Variation vs 100")
    print("-" * 45)

    for seed in [42, 123, 456, 789, 999]:
        np.random.seed(seed)
        sim = BudgetSimulatorV45(mesures={})
        df, _, _ = sim.simulate()
        pa_2035 = df.iloc[10]['Pouvoir d\'Achat']
        delta = pa_2035 - 100.0

        print(f"{seed:4d} | {pa_2035:6.2f} | {delta:+6.2f}")

    print("\nConclusion:")
    print("Si PA varie avec la seed => Oscillations aléatoires normales")
    print("Si PA = 100.0 toujours => Calibration exacte (coïncidence)\n")

def test_pa_calcul_theorique():
    """Calculer le PA théorique attendu"""
    print("\n=== CALCUL THÉORIQUE PA MOYEN ===\n")

    sim = BudgetSimulatorV45(mesures={})
    df, _, _ = sim.simulate()

    # Calculer moyennes sur 2026-2035
    growth_avg = df.iloc[1:11]['Croissance %'].mean()
    inflation_avg = df.iloc[1:11]['Inflation %'].mean()

    from budget_simulator.constants import INDEXATION_BASELINE_RATIO
    gap_macro = growth_avg - inflation_avg
    indexation = INDEXATION_BASELINE_RATIO * inflation_avg
    gap_net = gap_macro + indexation

    # PA théorique après 10 ans
    pa_theorique = 100 * (1 + gap_net/100)**10
    pa_observe = df.iloc[10]['Pouvoir d\'Achat']

    print(f"Croissance moyenne 2026-2035:  {growth_avg:.2f}%")
    print(f"Inflation moyenne 2026-2035:   {inflation_avg:.2f}%")
    print(f"Gap macro (Cr - Inf):          {gap_macro:+.2f}%")
    print(f"Indexation ({INDEXATION_BASELINE_RATIO*100:.0f}% × Inf):        {indexation:+.2f}%")
    print(f"Gap net annuel:                {gap_net:+.2f}%")
    print()
    print(f"PA théorique 2035: {pa_theorique:.2f}")
    print(f"PA observé 2035:   {pa_observe:.2f}")
    print(f"Écart:             {pa_observe - pa_theorique:+.2f}")

    if abs(gap_net) < 0.05:
        print("\n=> Gap net quasi NUL => PA stable autour de 100 (quasi-coïncidence)")
    else:
        print(f"\n=> Gap net {gap_net:+.2f}%/an => PA devrait être {pa_theorique:.1f}")

def test_pa_avec_indexation_55_vs_65():
    """Tester PA avec indexation 55% vs 65% (au lieu de 60%)"""
    print("\n=== SENSIBILITÉ INDEXATION (55% vs 60% vs 65%) ===\n")

    # Modifier temporairement le code pour tester 55% et 65%
    print("Indexation | PA 2035 | Variation")
    print("-" * 40)

    # Baseline 60% (actuel)
    sim_60 = BudgetSimulatorV45(mesures={})
    df_60, _, _ = sim_60.simulate()
    pa_60 = df_60.iloc[10]['Pouvoir d\'Achat']

    print(f"   60%     | {pa_60:6.2f} | baseline")

    # Note : Pour tester 55% et 65%, il faudrait modifier simulator.py
    # Ici on calcule théoriquement
    inflation_avg = df_60.iloc[1:11]['Inflation %'].mean()
    growth_avg = df_60.iloc[1:11]['Croissance %'].mean()
    gap_macro = growth_avg - inflation_avg

    # Avec 55%
    gap_net_55 = gap_macro + 0.55 * inflation_avg
    pa_55_theorique = 100 * (1 + gap_net_55/100)**10
    delta_55 = pa_55_theorique - pa_60
    print(f"   55%     | {pa_55_theorique:6.2f} | {delta_55:+6.2f} (théorique)")

    # Avec 65%
    gap_net_65 = gap_macro + 0.65 * inflation_avg
    pa_65_theorique = 100 * (1 + gap_net_65/100)**10
    delta_65 = pa_65_theorique - pa_60
    print(f"   65%     | {pa_65_theorique:6.2f} | {delta_65:+6.2f} (théorique)")

    print("\nConclusion:")
    print(f"- Indexation 55% => PA ~{pa_55_theorique:.0f} (plus pessimiste)")
    print(f"- Indexation 60% => PA ~{pa_60:.0f} (équilibre)")
    print(f"- Indexation 65% => PA ~{pa_65_theorique:.0f} (plus optimiste)")
    print("\n=> 60% arrive pile à ~100 car calibration proche de l'équilibre\n")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("ANALYSE SENSIBILITÉ PA = 100.0 EN 2035")
    print("="*60)

    test_pa_avec_seed_differents()
    test_pa_calcul_theorique()
    test_pa_avec_indexation_55_vs_65()

    print("="*60)
    print("CONCLUSION GÉNÉRALE")
    print("="*60)
    print("\nPA = 100.0 en 2035 resulte de:")
    print("1. Gap net moyen ~= -0.02%/an (quasi-nul)")
    print("2. Oscillations aleatoires se compensant")
    print("3. Indexation 60% calibree proche de l'equilibre")
    print("\n=> C'est une QUASI-COINCIDENCE, pas une garantie mathematique")
    print("=> Avec indexation 55% => PA ~98")
    print("=> Avec indexation 65% => PA ~102")
    print("="*60 + "\n")
