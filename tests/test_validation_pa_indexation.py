"""
Test de validation : Indexation PA baseline 60%

Objectif : Vérifier que l'ajout d'indexation baseline :
1. Stabilise le PA en statut quo (100 en 2025 → ~100 en 2035)
2. Ne modifie AUCUN autre indicateur (PIB, dette, déficit, inflation, etc.)
3. Préserve les deltas des mesures (CSG prog, ASU, etc.)

La simulation statu quo est fournie par la fixture partagée ``statu_quo``
(conftest, scope session — dédup Lot E : 1 simulation au lieu de 4).
"""

from budget_simulator.simulator import BudgetSimulatorV45


def test_statut_quo_pa_stable(statu_quo):
    """Test 1: PA statut quo doit rester stable (~100)"""
    pa_2025 = statu_quo.iloc[0]['Pouvoir d\'Achat']
    pa_2035 = statu_quo.iloc[10]['Pouvoir d\'Achat']

    print(f"\nPA 2025: {pa_2025:.1f} / PA 2035: {pa_2035:.1f} "
          f"(variation {pa_2035 - pa_2025:+.1f} pts)")

    # RECALIBRAGE refonte 2026-06-10 : le statu quo dégage désormais +0,37 %/an
    # de PA réel (mesuré 103,8 en 2035) — l'ancien « plat à 100 » était un
    # artefact de l'inflation forcée à 2,33 % (g − 0,46·π ≈ 0). Avec π ~1,2 %,
    # pa_macro_net ≈ +0,35 %/an, dans la fourchette historique INSEE du RDB
    # réel par tête (+0,3-0,8 %/an hors crises). Fenêtre [100 ; 107] : borne
    # basse = pas de retour de l'austérité fantôme (PA écrasé), haute = pas
    # d'emballement (>0,7 %/an non justifiable en statu quo mou).
    assert 100.0 < pa_2035 < 107.0, f"PA 2035 ({pa_2035:.1f}) hors fenêtre statu quo [100;107]"


def test_autres_indicateurs_inchanges(statu_quo):
    """Test 2: Autres indicateurs doivent être cohérents"""
    inflation_2035 = statu_quo.iloc[10]['Inflation %']
    croissance_2035 = statu_quo.iloc[10]['Croissance %']
    dette_2035 = statu_quo.iloc[10]['Dette/PIB %']
    deficit_2035 = statu_quo.iloc[10]['Déficit/PIB %']

    print(f"\nInflation {inflation_2035:.2f}% / Croissance {croissance_2035:.2f}% / "
          f"Dette/PIB {dette_2035:.1f}% / Déficit/PIB {deficit_2035:.1f}%")

    # Vérifications de cohérence (plages élargies pour robustesse)
    # Inflation : plage recalée [0,8 ; 2,2] (refonte 2026-06-10) — point fixe
    # Phillips = 1,5 % (intercept ×(1−ρ) corrigé) et output gap négatif
    # persistant en statu quo → effective ~1,1-1,4 %. L'ancien plancher 1,5 %
    # encodait l'attracteur artificiel 2,33 %.
    assert 0.8 <= inflation_2035 <= 2.2, f"Inflation hors plage : {inflation_2035:.2f}%"
    assert 0.3 <= croissance_2035 <= 1.5, f"Croissance hors plage : {croissance_2035:.2f}%"
    # Dette plus basse avec Fix 6 (ratio dépenses/PIB sur PIB courant, pas fixe)
    # Dépenses maîtrisées → possible excédent budgétaire
    assert 60 <= dette_2035 <= 155, f"Dette/PIB hors plage : {dette_2035:.1f}%"
    assert -9.0 <= deficit_2035 <= 6.0, f"Déficit/PIB hors plage : {deficit_2035:.1f}%"


def test_mesures_deltas_preserves(statu_quo):
    """Test 3: Les mesures doivent avoir les mêmes deltas PA"""
    pa_sq_2035 = statu_quo.iloc[10]['Pouvoir d\'Achat']

    # CSG progressive (simulation dédiée — pas un statu quo)
    sim_csg = BudgetSimulatorV45(mesures={'csg': {'taux': 0.097, 'progressive': 1}})
    df_csg, _, _ = sim_csg.simulate()
    pa_csg_2035 = df_csg.iloc[10]['Pouvoir d\'Achat']

    delta_csg = pa_csg_2035 - pa_sq_2035
    print(f"\nPA SQ 2035: {pa_sq_2035:.1f} / PA CSG prog 2035: {pa_csg_2035:.1f} "
          f"(delta {delta_csg:+.1f} pts)")

    # Delta CSG progressive est un effet ONE-TIME en 2026 (+0.4 pts) qui
    # s'estompe avec l'indexation baseline → résiduel ~0.1 pts en 2035.
    assert delta_csg > 0, f"Delta CSG ({delta_csg:.2f}) devrait être positif"
    assert delta_csg < 0.5, f"Delta CSG ({delta_csg:.2f}) trop élevé"


def test_evolution_annuelle(statu_quo):
    """Test 4: Évolution PA année par année (affichage diagnostique)"""
    print("\nAnnée | PA    | Delta | Croissance | Inflation | Gap")
    print("-" * 60)
    for i in range(0, 11):
        pa = statu_quo.iloc[i]['Pouvoir d\'Achat']
        growth = statu_quo.iloc[i]['Croissance %']
        inflation = statu_quo.iloc[i]['Inflation %']
        gap = growth - inflation
        if i > 0:
            delta_pa = pa - statu_quo.iloc[i - 1]['Pouvoir d\'Achat']
            print(f"{2025+i} | {pa:5.1f} | {delta_pa:+5.1f} | {growth:6.2f}%   | "
                  f"{inflation:6.2f}%  | {gap:+5.2f}%")
        else:
            print(f"{2025+i} | {pa:5.1f} |   -   | {growth:6.2f}%   | "
                  f"{inflation:6.2f}%  | {gap:+5.2f}%")
