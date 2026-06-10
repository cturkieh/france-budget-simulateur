# -*- coding: utf-8 -*-
"""
Test simple de la fonction _apply_sante() v2025.1
"""
import sys
import os
from unittest.mock import patch

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
    with patch('numpy.random.normal', return_value=0):
        projections, _, _ = sim.simulate()

    row_2035 = projections[projections['Année'] == 2035].iloc[0]
    dette_2035 = row_2035['Dette/PIB %']
    deficit_2035 = row_2035['Déficit/PIB %']

    # RECALIBRAGE refonte « assemblage temporel » 2026-06-10 (mesuré sans bruit :
    # 151,4 % / -7,26 %) : baseline honnête — déficit ~5-5,5 % jamais consolidé
    # (l'assainissement fantôme de ~24 Md€/an a disparu avec le lag) + inflation
    # effective ~1,1-1,4 % (PIB nominal moins gonflé). Ancrage : 2030 = 129,5 %,
    # cohérent HCFP « >125 % sans ajustement ».
    assert abs(dette_2035 - 151.4) <= 3.0, (
        f"Dette/PIB 2035: {dette_2035:.1f}%, expected ~151.4% (baseline honnête post-refonte)"
    )
    assert abs(deficit_2035 - (-7.26)) <= 1.5, (
        f"Deficit/PIB 2035: {deficit_2035:.2f}%, expected ~-7.26% (baseline honnête post-refonte)"
    )


if __name__ == '__main__':
    test_efforts_max_2030()
    test_efforts_max_2026()
    test_effort_hopital_seul()
    test_simulation_complete()
    print("All tests passed.")
