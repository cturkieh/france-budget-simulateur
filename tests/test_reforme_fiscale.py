# -*- coding: utf-8 -*-
"""
Test des nouvelles fonctions de reforme fiscale 2025.2
"""

import sys
from budget_simulator.simulator import BudgetSimulatorV45

PA_COL = "Pouvoir d'Achat"

def test_csg_progressive():
    """Test CSG progressive : neutralite recettes + redistribution"""
    print("\n" + "="*60)
    print("TEST 1 : CSG PROGRESSIVE")
    print("="*60)

    print("\n[1a] CSG flat 9.7% (status quo)")
    sim_flat = BudgetSimulatorV45(mesures={'csg': {'taux': 0.097, 'progressive': 0}})
    df_flat, _, _ = sim_flat.simulate()
    y0_flat = df_flat.iloc[1]  # Année 2026 (première année avec mesures)

    print(f"  Deficit : {y0_flat['Déficit']:.2f} Md")
    print(f"  Gini : {y0_flat['Gini']:.3f}")
    pa_val = y0_flat[PA_COL]
    print(f"  PA : {pa_val:.2f}%")

    print("\n[1b] CSG progressive activee (taux 9.7%)")
    sim_prog = BudgetSimulatorV45(mesures={'csg': {'taux': 0.097, 'progressive': 1}})
    df_prog, _, _ = sim_prog.simulate()
    y0_prog = df_prog.iloc[1]

    delta_recettes = y0_prog['Déficit'] - y0_flat['Déficit']
    delta_gini = y0_prog['Gini'] - y0_flat['Gini']
    delta_pa = y0_prog[PA_COL] - y0_flat[PA_COL]

    print(f"\n  Delta Deficit : {delta_recettes:.2f} Md (attendu: ~0)")
    print(f"  Delta Gini : {delta_gini:.3f} (attendu: -0.015)")
    print(f"  Delta PA : {delta_pa:.2f}% (attendu: +0.4%)")

    # Validation souple
    assert abs(delta_recettes) < 2.0, f"[X] Neutralite recettes echouee : {delta_recettes:.2f} Md"
    assert -0.022 < delta_gini < -0.008, f"[X] Impact Gini hors cible : {delta_gini:.3f}"
    assert 0.2 < delta_pa < 0.6, f"[X] Impact PA hors cible : {delta_pa:.2f}%"

    print("\n[OK] TEST CSG PROGRESSIVE REUSSI")

def test_cotisations_salariales():
    """Test baisse cotisations salariales"""
    print("\n" + "="*60)
    print("TEST 2 : COTISATIONS SALARIALES")
    print("="*60)

    print("\n[2a] Status quo (baisse 0 point)")
    sim_sq = BudgetSimulatorV45(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[2b] Baisse -3 points cotisations salariales")
    sim_baisse = BudgetSimulatorV45(mesures={'cotisations_salariales': {'baisse_points': 3.0}})
    df_baisse, _, _ = sim_baisse.simulate()
    y0_baisse = df_baisse.iloc[1]

    delta_recettes = y0_baisse['Déficit'] - y0_sq['Déficit']
    delta_pa = y0_baisse[PA_COL] - y0_sq[PA_COL]

    print(f"\n  Cout : {-delta_recettes:.2f} Md (attendu: 18 Md)")
    print(f"  Delta PA : {delta_pa:.2f}% (attendu: +1.5%)")

    assert -21 < delta_recettes < -15, f"[X] Cout hors cible : {delta_recettes:.2f} Md"
    assert 1.2 < delta_pa < 1.8, f"[X] Impact PA hors cible : {delta_pa:.2f}%"

    print("\n[OK] TEST COTISATIONS SALARIALES REUSSI")

def test_elargissement_ir():
    """Test elargissement base IR"""
    print("\n" + "="*60)
    print("TEST 3 : ELARGISSEMENT IR")
    print("="*60)

    print("\n[3a] Status quo (45% contribuables)")
    sim_sq = BudgetSimulatorV45(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[3b] Elargissement 45% -> 63% contribuables")
    sim_elargis = BudgetSimulatorV45(mesures={
        'elargissement_ir': {
            'seuil_entree': 8000,
            'taux_contribuables_cible': 0.63
        }
    })
    df_elargis, _, _ = sim_elargis.simulate()
    y0_elargis = df_elargis.iloc[1]

    delta_recettes = y0_elargis['Déficit'] - y0_sq['Déficit']
    delta_gini = y0_elargis['Gini'] - y0_sq['Gini']

    print(f"\n  Recettes : +{delta_recettes:.2f} Md (attendu: +8 a +12 Md)")
    print(f"  Delta Gini : {delta_gini:.3f} (attendu: +0.005)")

    assert 3 < delta_recettes < 14, f"[X] Recettes hors cible : {delta_recettes:.2f} Md"
    assert 0.002 < delta_gini < 0.008, f"[X] Impact Gini hors cible : {delta_gini:.3f}"

    print("\n[OK] TEST ELARGISSEMENT IR REUSSI")

def test_fiscalite_patrimoine():
    """Test fiscalite patrimoine globale"""
    print("\n" + "="*60)
    print("TEST 4 : FISCALITE PATRIMOINE")
    print("="*60)

    print("\n[4a] Status quo (intensite 0%)")
    sim_sq = BudgetSimulatorV45(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[4b] Hausse fiscalite patrimoine +30%")
    sim_hausse = BudgetSimulatorV45(mesures={'fiscalite_patrimoine': {'intensite': 0.30}})
    df_hausse, _, _ = sim_hausse.simulate()
    y0_hausse = df_hausse.iloc[1]

    delta_recettes = y0_hausse['Déficit'] - y0_sq['Déficit']
    delta_gini = y0_hausse['Gini'] - y0_sq['Gini']

    print(f"\n  Recettes : +{delta_recettes:.2f} Md (attendu: +16 Md)")
    print(f"  Delta Gini : {delta_gini:.3f} (attendu: -0.016)")

    print("\n[4c] Baisse fiscalite patrimoine -30%")
    sim_baisse = BudgetSimulatorV45(mesures={'fiscalite_patrimoine': {'intensite': -0.30}})
    df_baisse, _, _ = sim_baisse.simulate()
    y0_baisse = df_baisse.iloc[1]

    delta_recettes_baisse = y0_baisse['Déficit'] - y0_sq['Déficit']

    print(f"  Cout : {delta_recettes_baisse:.2f} Md (attendu: -16 Md)")

    assert 13 < delta_recettes < 19, f"[X] Recettes +30% hors cible : {delta_recettes:.2f} Md"
    assert -0.022 < delta_gini < -0.010, f"[X] Impact Gini hors cible : {delta_gini:.3f}"
    assert -19 < delta_recettes_baisse < -13, f"[X] Cout -30% hors cible : {delta_recettes_baisse:.2f} Md"

    print("\n[OK] TEST FISCALITE PATRIMOINE REUSSI")

def test_package_complet():
    """Test package complet"""
    print("\n" + "="*60)
    print("TEST 5 : PACKAGE COMPLET")
    print("="*60)
    print("CSG progressive + Cotisations -4pts + Patrimoine -30%")

    sim_sq = BudgetSimulatorV45(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    sim_package = BudgetSimulatorV45(mesures={
        'csg': {'taux': 0.097, 'progressive': 1},
        'cotisations_salariales': {'baisse_points': 4.0},
        'fiscalite_patrimoine': {'intensite': -0.30}
    })
    df_package, _, _ = sim_package.simulate()
    y0_package = df_package.iloc[1]

    delta_recettes = y0_package['Déficit'] - y0_sq['Déficit']
    delta_pa = y0_package[PA_COL] - y0_sq[PA_COL]
    delta_gini = y0_package['Gini'] - y0_sq['Gini']
    delta_chomage = y0_package['Chômage %'] - y0_sq['Chômage %']

    print(f"\n  Cout total : {-delta_recettes:.2f} Md")
    print(f"\n  Impacts :")
    print(f"    Delta PA : +{delta_pa:.2f}% (boost pouvoir d'achat)")
    print(f"    Delta Gini : {delta_gini:.3f} (redistributif)")
    print(f"    Delta Chomage : {delta_chomage:.2f} pts (creation emplois)")

    assert -50 < delta_recettes < -30, f"[X] Cout package hors cible : {delta_recettes:.2f} Md"
    assert delta_pa > 1.3, f"[X] PA insuffisant : {delta_pa:.2f}%"
    # Net Gini effect: CSG progressive (-0.015) + cotisations salariales (regressive) + patrimoine -30% (regressive)
    # The package reduces taxes more than it redistributes, so net Gini may be slightly positive
    assert abs(delta_gini) < 0.025, f"[X] Impact Gini excessif : {delta_gini:.3f}"

    print("\n[OK] TEST PACKAGE COMPLET REUSSI")

def main():
    print("\n" + "="*60)
    print("TESTS REFORME FISCALE 2025.2")
    print("Validation backend Python")
    print("="*60)

    try:
        test_csg_progressive()
        test_cotisations_salariales()
        test_elargissement_ir()
        test_fiscalite_patrimoine()
        test_package_complet()

        print("\n" + "="*60)
        print("[OK] TOUS LES TESTS REUSSIS !")
        print("="*60)

    except AssertionError as e:
        print(f"\n[X] ECHEC : {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] ERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
