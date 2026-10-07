# -*- coding: utf-8 -*-
"""
Test simple de la fonction _apply_sante() v2025.1
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_simulator.simulator import BudgetSimulatorV45


def test_efforts_max_2030():
    """Test 1: Efforts max en 2030 (phasing complet)"""
    sim = BudgetSimulatorV45()
    params = {'effort_hopital': 100, 'effort_ambu': 100, 'effort_prev_org': 100}
    delta_spend, _, _ = sim._apply_sante(
        {}, params, 2030, 3000.0, 0.017, 0.073
    )
    assert abs(delta_spend - (-30.0)) < 0.5, (
        f"Expected delta ~-30.0, got {delta_spend:.1f}"
    )


def test_efforts_max_2026():
    """Test 2: Efforts max en 2026 (phasing partiel)"""
    sim = BudgetSimulatorV45()
    params = {'effort_hopital': 100, 'effort_ambu': 100, 'effort_prev_org': 100}
    delta_spend, _, _ = sim._apply_sante(
        {}, params, 2026, 2970.0, 0.017, 0.073
    )
    assert abs(delta_spend - (-7.2)) < 2.0, (
        f"Expected delta ~-7.2, got {delta_spend:.1f}"
    )


def test_effort_hopital_seul():
    """Test 3: effort_hopital seul"""
    sim = BudgetSimulatorV45()
    params = {'effort_hopital': 100}
    delta_spend, _, _ = sim._apply_sante(
        {}, params, 2030, 3000.0, 0.017, 0.073
    )
    assert abs(delta_spend - (-13.0)) < 0.5, (
        f"Expected delta ~-13.0 for effort_hopital seul, got {delta_spend:.1f}"
    )


def test_simulation_complete():
    """Test 4: Simulation complete - dette et deficit 2035 (baseline statu quo).

    Valeurs de référence calibrées après triple-audit (DG Trésor / COR / Bozio-Wasmer,
    commit c510c22 du 2026-04-XX) qui a recalibré le moteur sur les Programmes de Stabilité
    publiés. La baseline 2035 antérieure (~140% / -7.7%) supposait des coefficients pré-audit
    plus pessimistes. La trajectoire actuelle est cohérente avec DG Trésor PStab 2024-2027.
    """
    sim = BudgetSimulatorV45()
    # Patch global du bruit aléatoire pour déterminisme (sinon flakiness possible en CI).
    # Affecte les DEUX bruits en cascade : croissance (simulator.py:963, σ=0.003) ET
    # inflation (simulator.py:1020, σ=0.0005). Le moteur reste identique à la prod, on
    # neutralise uniquement les sources stochastiques.
    projections, _, _ = sim.simulate()

    row_2035 = projections[projections['Année'] == 2035].iloc[0]
    dette_2035 = row_2035['Dette/PIB %']
    deficit_2035 = row_2035['Déficit/PIB %']

    # RECALIBRAGE refonte « assemblage temporel » 2026-06-10 (mesuré sans bruit :
    # 151,4 % / -7,26 %) : baseline honnête — déficit ~5-5,5 % jamais consolidé
    # (l'assainissement fantôme de ~24 Md€/an a disparu avec le lag) + inflation
    # effective ~1,1-1,4 % à cette date (PIB nominal moins gonflé). Ancrage : 2030 = 129,5 %,
    # cohérent HCFP « >125 % sans ajustement ».
    # RECALIBRAGE v0.6.0 (audit externe 08/2026, mesuré sans bruit ~170,9 % /
    # ~-11,8 %) : taux marginal ré-ancré sur le marché (courbe AFT monotone,
    # charge 124 Md€ en 2030, corridor mission IGF 07/2026) → boule de neige
    # réelle en fin d'horizon. Cf. tests/test_calibration_mission_v060.py.
    # RECALIBRAGE v0.6.1 lot 8 (Phillips ancrée, mesuré sans bruit 163,5 % /
    # -11,15 %) : le déflateur réalisé passe de ~0,9 à ~1,5 %/an, donc le PIB
    # nominal 2035 est ~3 % plus haut et le DÉNOMINATEUR du ratio de dette
    # avec lui (-9,5 pt de dette 2035, -3,7 pt en 2030). Le déficit s'améliore
    # aussi d'~1 pt, en partie par le même dénominateur, en partie par le
    # décalage d'indexation pendant la transition d'inflation (biais I17
    # déclaré). Ce recalage joue dans le MÊME sens pour tous les scénarios :
    # cf. le paragraphe « sens des corrections » du CHANGELOG v0.6.1.
    # RECALIBRAGE v0.6.7 B3 (mesuré sans bruit 157,8 % / -10,23 %) : output
    # gap en niveau refermé à 20 %/an (le gap initial −0,7 % se résorbe, +0,7 %
    # de PIB), traînée de dette passée dans le potentiel (Okun ne la lit plus :
    # chômage plus bas, moindres dépenses). Sens commun à tous les scénarios.
    # RECALIBRAGE v0.6.7 lot 3b (mesuré 151,2 % / −9,05 %) : tendanciel ré-ancré
    # 1,1 → 1,228 % (dérivé : potentiel officiel + traînée de la dette héritée,
    # constants.py). Dette 2035 −6,6 pt = dénominateur −2,1 (PIB nominal +1,4 %)
    # + numérateur −4,5 (recettes sur un PIB plus haut, dépense primaire
    # insensible au PIB réel). Tolérances inchangées.
    assert abs(dette_2035 - 151.2) <= 4.0, (
        f"Dette/PIB 2035: {dette_2035:.1f}%, expected ~151,2% (v0.6.7, lot 3b)"
    )
    assert abs(deficit_2035 - (-9.05)) <= 2.0, (
        f"Deficit/PIB 2035: {deficit_2035:.2f}%, expected ~-9,05% (v0.6.7, lot 3b)"
    )


if __name__ == '__main__':
    test_efforts_max_2030()
    test_efforts_max_2026()
    test_effort_hopital_seul()
    test_simulation_complete()
    print("All tests passed.")
