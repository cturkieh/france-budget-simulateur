# -*- coding: utf-8 -*-
"""
Test pour verifier que les sliders sante ont un effet sur la simulation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_simulator.simulator import BudgetSimulatorV45


def test_sante_sliders_have_effect():
    """Les sliders sante a 100% doivent reduire les depenses significativement."""
    # Sans reforme sante
    sim1 = BudgetSimulatorV45()
    proj1, _, _ = sim1.simulate()

    row_2030_sans = proj1[proj1['Année'] == 2030].iloc[0]
    pib_2030_sans = row_2030_sans['PIB']
    depenses_pib_2030_sans = row_2030_sans['Dépenses/PIB %']
    depenses_2030_sans = pib_2030_sans * depenses_pib_2030_sans / 100

    # Avec reforme sante maximale
    mesures_max = {
        'sante': {
            'effort_hopital': 100,
            'effort_ambu': 100,
            'effort_prev_org': 100
        }
    }
    sim2 = BudgetSimulatorV45(mesures=mesures_max)
    proj2, _, _ = sim2.simulate()

    row_2030_avec = proj2[proj2['Année'] == 2030].iloc[0]
    pib_2030_avec = row_2030_avec['PIB']
    depenses_pib_2030_avec = row_2030_avec['Dépenses/PIB %']
    depenses_2030_avec = pib_2030_avec * depenses_pib_2030_avec / 100

    delta_depenses = depenses_2030_avec - depenses_2030_sans

    # Sliders should produce at least -5 Md€ of savings
    assert delta_depenses < -5, (
        f"Les sliders sante n'ont presque aucun effet: "
        f"delta depenses = {delta_depenses:.1f} Md€ (attendu < -5)"
    )


def test_sante_dette_impact():
    """La reforme sante doit ameliorer la dette 2035."""
    sim1 = BudgetSimulatorV45()
    proj1, _, _ = sim1.simulate()
    dette_2035_sans = proj1[proj1['Année'] == 2035].iloc[0]['Dette/PIB %']

    mesures_max = {
        'sante': {
            'effort_hopital': 100,
            'effort_ambu': 100,
            'effort_prev_org': 100
        }
    }
    sim2 = BudgetSimulatorV45(mesures=mesures_max)
    proj2, _, _ = sim2.simulate()
    dette_2035_avec = proj2[proj2['Année'] == 2035].iloc[0]['Dette/PIB %']

    delta_dette = dette_2035_avec - dette_2035_sans

    # Sante reform should reduce debt
    assert delta_dette < 0, (
        f"La reforme sante devrait reduire la dette, "
        f"mais delta dette = {delta_dette:+.1f} points PIB"
    )


if __name__ == '__main__':
    test_sante_sliders_have_effect()
    test_sante_dette_impact()
    print("All tests passed.")
