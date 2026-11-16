# -*- coding: utf-8 -*-
"""
Test des nouvelles fonctions de reforme fiscale 2025.2

Chaque test lit le COÛT d'une réforme sur l'écart de déficit de l'année
d'entrée (2026) : effet direct. Jusqu'au lot 6, l'impulsion budgétaire n'y
agissait pas encore (laguée d'un an) ; depuis, elle agit l'année même, et les
tests tournent dans le laboratoire des effets directs
(``tests/effets_directs.py`` : multiplicateurs nuls), qui rend à l'année
d'entrée 2026 l'état du moteur d'avant le lot (au bit, colonne « Multiplicateur »
à part ; mode historique, celui de ces tests).
"""

import sys
from effets_directs import SansRetroactionKeynesienne

import pytest

import budget_simulator.engine.orchestrator as orch
import budget_simulator.constants as C
from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import (COUT_PAR_POINT_COTIS_SAL,
                                        GINI_CSG_PROGRESSIVE, GINI_HAUT_PATRIMOINE_PAR_MD,
                                        GINI_IMPACT_SCALE, GINI_IR_CIBLE_PAR_MD)

PA_COL = "Pouvoir d'Achat"

# Assemblage Gini (lot 4, arbitrage du mainteneur) : ni convergence ni
# amortissement — l'indice publié vaut la base plus l'effet brut × SCALE dès
# l'année où la mesure s'applique, et le garde ensuite (effet émis une fois).
# Jusqu'au lot 4 : × RATE (0,35) l'année d'entrée, 1 − 0,65^k après k années.
ATTENUATION_Y1 = GINI_IMPACT_SCALE
ATTENUATION_HORIZON = GINI_IMPACT_SCALE

def test_csg_progressive(monkeypatch):
    """Test CSG progressive : neutralite recettes + redistribution"""
    # Lot 4 : forfait GINI_CSG_PROGRESSIVE (règle sans source vérifiée gardée à
    # son poids publié d'avant), sous la résolution de sortie : pleine précision.
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    print("\n" + "="*60)
    print("TEST 1 : CSG PROGRESSIVE")
    print("="*60)

    print("\n[1a] CSG flat 9.7% (status quo)")
    sim_flat = SansRetroactionKeynesienne(mesures={'csg': {'taux': 0.097, 'progressive': 0}})
    df_flat, _, _ = sim_flat.simulate()
    y0_flat = df_flat.iloc[1]  # Année 2026 (première année avec mesures)

    print(f"  Deficit : {y0_flat['Déficit']:.2f} Md")
    print(f"  Gini : {y0_flat['Gini']:.3f}")
    pa_val = y0_flat[PA_COL]
    print(f"  PA : {pa_val:.2f}%")

    print("\n[1b] CSG progressive activee (taux 9.7%)")
    sim_prog = SansRetroactionKeynesienne(mesures={'csg': {'taux': 0.097, 'progressive': 1}})
    df_prog, _, _ = sim_prog.simulate()
    y0_prog = df_prog.iloc[1]

    delta_recettes = y0_prog['Déficit'] - y0_flat['Déficit']
    delta_gini = y0_prog['Gini'] - y0_flat['Gini']
    delta_pa = y0_prog[PA_COL] - y0_flat[PA_COL]

    print(f"\n  Delta Deficit : {delta_recettes:.2f} Md (attendu: ~0)")
    print(f"  Delta Gini : {delta_gini:.4f} (attendu: 0, GINI_CSG_PROGRESSIVE faute de source)")
    print(f"  Delta PA : {delta_pa:.2f}% (attendu: 0)")

    # Validation souple
    assert abs(delta_recettes) < 2.0, f"[X] Neutralite recettes echouee : {delta_recettes:.2f} Md"
    # Lot 4 : GINI_CSG_PROGRESSIVE = 0 faute de source (règle du mainteneur :
    # sans source, zéro et limite déclarée) ; jusqu'ici −0,015 brut, « OFCE
    # 2023, modèle Allemagne », sans passage retrouvé.
    assert GINI_CSG_PROGRESSIVE == 0.0
    assert delta_gini == pytest.approx(GINI_CSG_PROGRESSIVE * ATTENUATION_Y1, abs=1e-12), \
        f"[X] Impact Gini hors cible : {delta_gini:.4f}"
    # v0.6.8 (indice RDB-moteur) : à recette nulle, la progressivité déplace du
    # revenu ENTRE ménages sans changer leur RDB total — effet porté par le
    # Gini, nul sur l'indice agrégé (l'ancien +0,4 % était un coefficient).
    assert abs(delta_pa) < 1e-9, f"[X] Impact PA hors cible : {delta_pa:.2f}%"

    print("\n[OK] TEST CSG PROGRESSIVE REUSSI")

def test_cotisations_salariales():
    """Test baisse cotisations salariales"""
    print("\n" + "="*60)
    print("TEST 2 : COTISATIONS SALARIALES")
    print("="*60)

    print("\n[2a] Status quo (baisse 0 point)")
    sim_sq = SansRetroactionKeynesienne(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[2b] Baisse -3 points cotisations salariales")
    sim_baisse = SansRetroactionKeynesienne(mesures={'cotisations_salariales': {'baisse_points': 3.0}})
    df_baisse, _, _ = sim_baisse.simulate()
    y0_baisse = df_baisse.iloc[1]

    delta_recettes = y0_baisse['Déficit'] - y0_sq['Déficit']
    delta_pa = y0_baisse[PA_COL] - y0_sq[PA_COL]

    # Release E (décision du mainteneur du 12/11/2026) : un point = 1 % de la
    # masse salariale brute 2025 (COUT_PAR_POINT_COTIS_SAL, ≈ 11,57 Md€) ;
    # jusqu'en v0.7.2, 6 Md€ (fenêtre −21 / −15 autour de 18 Md€).
    attendu = 3.0 * COUT_PAR_POINT_COTIS_SAL
    print(f"\n  Cout : {-delta_recettes:.2f} Md (attendu: {attendu:.1f} Md)")
    print(f"  Delta PA : {delta_pa:.2f}% (attendu: {attendu / 19:.2f}%)")

    assert -1.17 * attendu < delta_recettes < -0.83 * attendu, f"[X] Cout hors cible : {delta_recettes:.2f} Md"
    # v0.6.8 : les euros rendus sur un RDB 2026 d'environ 1 900 Md€ (18 Md€ ≈
    # +0,95 pt ; l'ancien +0,5 %/point transmettait 133 % de ses euros).
    assert 0.9 * attendu / 19 < delta_pa < 1.1 * attendu / 19, f"[X] Impact PA hors cible : {delta_pa:.2f}%"

    print("\n[OK] TEST COTISATIONS SALARIALES REUSSI")

def test_elargissement_ir(monkeypatch):
    """Test elargissement base IR"""
    # Lot 4 (méthode unique du Gini) : l'effet par Md€ est physique et petit
    # (+0,000255 par Md€, convention « classes moyennes ») — sous la résolution
    # de sortie (3 décimales) : Gini lu en PLEINE PRÉCISION.
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    print("\n" + "="*60)
    print("TEST 3 : ELARGISSEMENT IR")
    print("="*60)

    print("\n[3a] Status quo (45% contribuables)")
    sim_sq = SansRetroactionKeynesienne(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[3b] Elargissement 45% -> 63% contribuables")
    # v0.6.10 (porte des noms, V2-04) : `seuil_entree` retiré — le handler ne
    # l'a jamais lu (ignoré en silence avant, rejeté désormais) ; seule la
    # cible de contribuables pilote la mesure.
    sim_elargis = SansRetroactionKeynesienne(mesures={
        'elargissement_ir': {
            'taux_contribuables_cible': 0.63
        }
    })
    df_elargis, _, _ = sim_elargis.simulate()
    y0_elargis = df_elargis.iloc[1]

    delta_recettes = y0_elargis['Déficit'] - y0_sq['Déficit']
    # Gini mesuré à l'HORIZON (Y10 ; lot 4 : sans convergence, l'effet émis en
    # 2026 est entier chaque année) : brut × SCALE. Brut (lot 4) = recette du
    # levier × GINI_IR_CIBLE_PAR_MD,
    # zéro faute de source : le levier ne dit pas quel instrument il porte
    # (jusqu'ici +0,005 pour +20 points, sans source).
    delta_gini = df_elargis.iloc[10]['Gini'] - df_sq.iloc[10]['Gini']
    recette = 41_000_000 * (0.63 - 0.45) * 18000 * 0.03 / 1e9
    attendu = GINI_IR_CIBLE_PAR_MD * recette * ATTENUATION_HORIZON

    print(f"\n  Recettes : +{delta_recettes:.2f} Md (attendu: +8 a +12 Md)")
    print(f"  Delta Gini Y10 : {delta_gini:.6f} (attendu: {attendu:.6f})")

    assert 3 < delta_recettes < 14, f"[X] Recettes hors cible : {delta_recettes:.2f} Md"
    assert delta_gini == pytest.approx(attendu, rel=1e-9, abs=1e-15), \
        f"[X] Impact Gini hors cible : {delta_gini:.6f}"

    print("\n[OK] TEST ELARGISSEMENT IR REUSSI")

def test_fiscalite_patrimoine(monkeypatch):
    """Test fiscalite patrimoine globale"""
    # Lot 4 : seul l'IFI (2 Md€ de la base) a un effet Gini, petit : pleine précision.
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    print("\n" + "="*60)
    print("TEST 4 : FISCALITE PATRIMOINE")
    print("="*60)

    print("\n[4a] Status quo (intensite 0%)")
    sim_sq = SansRetroactionKeynesienne(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    print("\n[4b] Hausse fiscalite patrimoine +30%")
    sim_hausse = SansRetroactionKeynesienne(mesures={'fiscalite_patrimoine': {'intensite': 0.30}})
    df_hausse, _, _ = sim_hausse.simulate()
    y0_hausse = df_hausse.iloc[1]

    delta_recettes = y0_hausse['Déficit'] - y0_sq['Déficit']
    delta_gini = y0_hausse['Gini'] - y0_sq['Gini']

    # Lot 3 : bases aux comptes nationaux 2025 (67,9 Md€ avec les donations, arbitrage du mainteneur, au
    # lieu de 53), qui suivent le PIB : 30 % ≈ 20,4 Md€ en 2025, un peu plus en 2026 (« +16 Md » jusqu'au lot 3).
    recette_attendue = 0.30 * (C.PATRIMOINE_IFI_MD + C.PATRIMOINE_SUCCESSIONS_MD + C.PATRIMOINE_TAXE_FONCIERE_MD)
    print(f"\n  Recettes : +{delta_recettes:.2f} Md (attendu: +{recette_attendue:.1f} Md, base 2025)")
    # Lot 4 (méthode unique) : seul l'IFI compte, au coefficient de l'INSEE, en euros de l'année source ;
    # successions, donations et taxe foncière hors du revenu disponible (0). Jusqu'ici −0,016 brut (−0,001 par Md€ du
    # total de 53 Md€).
    attendu = GINI_HAUT_PATRIMOINE_PAR_MD * C.PATRIMOINE_IFI_MD * 0.30 * ATTENUATION_Y1
    print(f"  Delta Gini : {delta_gini:.6f} (attendu: {attendu:.6f} en sortie Y1)")

    print("\n[4c] Baisse fiscalite patrimoine -30%")
    sim_baisse = SansRetroactionKeynesienne(mesures={'fiscalite_patrimoine': {'intensite': -0.30}})
    df_baisse, _, _ = sim_baisse.simulate()
    y0_baisse = df_baisse.iloc[1]

    delta_recettes_baisse = y0_baisse['Déficit'] - y0_sq['Déficit']

    print(f"  Cout : {delta_recettes_baisse:.2f} Md (attendu: -{recette_attendue:.1f} Md, base 2025)")

    assert 0.8 * recette_attendue < delta_recettes < 1.2 * recette_attendue, f"[X] Recettes +30% hors cible : {delta_recettes:.2f} Md"
    assert delta_gini == pytest.approx(attendu, rel=1e-9), \
        f"[X] Impact Gini hors cible : {delta_gini:.6f}"
    assert -1.2 * recette_attendue < delta_recettes_baisse < -0.8 * recette_attendue, f"[X] Cout -30% hors cible : {delta_recettes_baisse:.2f} Md"

    print("\n[OK] TEST FISCALITE PATRIMOINE REUSSI")

def test_package_complet():
    """Test package complet"""
    print("\n" + "="*60)
    print("TEST 5 : PACKAGE COMPLET")
    print("="*60)
    print("CSG progressive + Cotisations -4pts + Patrimoine -30%")

    sim_sq = SansRetroactionKeynesienne(mesures={})
    df_sq, _, _ = sim_sq.simulate()
    y0_sq = df_sq.iloc[1]

    sim_package = SansRetroactionKeynesienne(mesures={
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

    # Fenêtre v0.7.2 (point à 6 Md€) décalée du surcoût des 4 points au coût
    # décidé le 12/11/2026 (1 % de la masse salariale brute 2025).
    surcout = 4.0 * (COUT_PAR_POINT_COTIS_SAL - 6.0)
    assert -50 - surcout < delta_recettes < -30 - surcout, f"[X] Cout package hors cible : {delta_recettes:.2f} Md"
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
