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
    # artefact de l'inflation forcée à 2,33 % (g − 0,46·π ≈ 0).
    # v0.6.7 (lot 3E, audit Codex bloc C constat 4) : la soustraction de
    # l'inflation à une croissance déjà RÉELLE est retirée — au statu quo
    # l'indice vaut EXACTEMENT 100 × Π (1 + g_t) (tests/test_pouvoir_achat_v067.py),
    # mesuré 108,7 en 2035 (g moyen 0,84 %/an). Ce n'est pas le RDB réel par
    # UC de l'INSEE (+0,3-0,8 %/an), mais un indice synthétique — d'où la
    # fenêtre dérivée du corridor de croissance du statu quo (0,5-1,5 %/an,
    # test_calibration_guard) : [105 ; 116].
    assert 105.0 < pa_2035 < 116.0, f"PA 2035 ({pa_2035:.1f}) hors fenêtre statu quo [105;116]"


def test_autres_indicateurs_inchanges(statu_quo):
    """Test 2: Autres indicateurs doivent être cohérents"""
    inflation_2035 = statu_quo.iloc[10]['Inflation %']
    croissance_2035 = statu_quo.iloc[10]['Croissance %']
    dette_2035 = statu_quo.iloc[10]['Dette/PIB %']
    deficit_2035 = statu_quo.iloc[10]['Déficit/PIB %']

    print(f"\nInflation {inflation_2035:.2f}% / Croissance {croissance_2035:.2f}% / "
          f"Dette/PIB {dette_2035:.1f}% / Déficit/PIB {deficit_2035:.1f}%")

    # Vérifications de cohérence (plages élargies pour robustesse)
    # Inflation : plage [0,8 ; 2,2], INCHANGÉE depuis la refonte 2026-06-10 —
    # elle avait alors remplacé un plancher à 1,5 % qui encodait l'attracteur
    # artificiel 2,33 %. Le point fixe Phillips vaut 1,6 % depuis la v0.6.1
    # (déflateur du PIB) et l'output gap reste négatif en statu quo →
    # effective ~1,2-1,5 %, toujours au milieu de la plage.
    assert 0.8 <= inflation_2035 <= 2.2, f"Inflation hors plage : {inflation_2035:.2f}%"
    assert 0.3 <= croissance_2035 <= 1.5, f"Croissance hors plage : {croissance_2035:.2f}%"
    # Dette plus basse avec Fix 6 (ratio dépenses/PIB sur PIB courant, pas fixe)
    # Dépenses maîtrisées → possible excédent budgétaire
    assert 60 <= dette_2035 <= 180, f"Dette/PIB hors plage : {dette_2035:.1f}%"
    assert -13.5 <= deficit_2035 <= 6.0, f"Déficit/PIB hors plage : {deficit_2035:.1f}%"


def test_mesures_deltas_preserves():
    """Test 3: Les mesures doivent avoir les mêmes deltas PA"""
    # v0.6.7 : écart lu en PLEINE PRÉCISION. Lu sur la colonne publiée (arrondie
    # au dixième), la différence de deux arrondis porte ±0,1 pt : 0,436 rendait
    # « 0,4 » sur 08810ad, 0,440 rend « 0,5 » sans le bruit tiré — la borne
    # mordait sur l'arrondi, pas sur le modèle.
    from unittest.mock import patch
    from budget_simulator.engine import orchestrator as orchestrator_module

    with patch.object(orchestrator_module, 'round', lambda x, n=None: float(x), create=True):
        df_sq, _, _ = BudgetSimulatorV45(mesures={}).simulate()
        # CSG progressive (simulation dédiée — pas un statu quo)
        df_csg, _, _ = BudgetSimulatorV45(
            mesures={'csg': {'taux': 0.097, 'progressive': 1}}).simulate()
    pa_sq_2035 = df_sq.iloc[10]['Pouvoir d\'Achat']
    pa_csg_2035 = df_csg.iloc[10]['Pouvoir d\'Achat']

    delta_csg = pa_csg_2035 - pa_sq_2035
    print(f"\nPA SQ 2035: {pa_sq_2035:.2f} / PA CSG prog 2035: {pa_csg_2035:.2f} "
          f"(delta {delta_csg:+.3f} pts)")

    # Delta CSG progressive : effet ONE-TIME en 2026 (+0,4 pt d'indice) qui,
    # depuis v0.6.7 (lot 3E, indice = Π (1 + g)), persiste en NIVEAU au lieu de
    # « s'estomper avec l'indexation baseline » (supprimée) : 0,44 pt en 2035.
    assert delta_csg > 0, f"Delta CSG ({delta_csg:.3f}) devrait être positif"
    assert delta_csg < 0.5, f"Delta CSG ({delta_csg:.3f}) trop élevé"


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
