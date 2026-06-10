"""
Tests de calibration — garde-fous pour les contributions externes.

Ces tests vérifient que le moteur économique produit des résultats
cohérents avec la réalité macroéconomique française. Tout PR qui
casse ces tests sera automatiquement refusé.

Sources : INSEE, Banque de France, Cour des comptes, IMF, OFCE.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_simulator.simulator import BudgetSimulatorV45


# === BASELINE (aucune réforme) ===

def test_baseline_dette_range():
    """La dette baseline doit rester dans 140-160% en 2035 (statu quo honnête post-refonte).

    RECALIBRAGE refonte « assemblage temporel » 2026-06-10 (mesuré 150,4 %) :
    la baseline honnête garde un déficit ~5-5,5 % SANS consolidation (l'ancien
    moteur fabriquait ~24 Md€/an d'assainissement fantôme) et une inflation
    effective ~1,1-1,4 % (point fixe 1,5 %, gap négatif persistant) au lieu du
    2,33 % artificiel qui gonflait le PIB nominal. Mécanique de Domar : à
    déficit ~5,3 % et nominal ~+2 %/an, Δratio ≈ +3 pt/an → ~150 % en 2035.
    Point d'ancrage externe : Y5 (2030) = 129,5 %, cohérent HCFP (« >125 % en
    2030 sans ajustement ») ; 2035 est au-delà des horizons publiés, la
    fourchette verrouille la mécanique, pas un consensus inexistant."""
    sim = BudgetSimulatorV45()
    df, _, _ = sim.simulate()
    dette = df.iloc[-1]['Dette/PIB %']
    assert 140 < dette < 160, f"Baseline dette {dette:.1f}% hors fourchette 140-160%"


def test_baseline_deficit_range():
    """Le déficit baseline doit être entre -4% et -8% en 2035"""
    sim = BudgetSimulatorV45()
    df, _, _ = sim.simulate()
    deficit = df.iloc[-1]['Déficit/PIB %']
    assert -8.0 < deficit < -4.0, f"Baseline déficit {deficit:.1f}% hors fourchette -8/-4%"


def test_baseline_croissance_range():
    """La croissance moyenne doit être entre 0.5% et 1.5% (potentiel France)"""
    sim = BudgetSimulatorV45()
    df, _, _ = sim.simulate()
    croissance = df['Croissance %'].mean()
    assert 0.5 < croissance < 1.5, f"Baseline croissance {croissance:.2f}% hors fourchette 0.5-1.5%"


def test_baseline_chomage_range():
    """Le chômage doit rester entre 6% et 10%"""
    sim = BudgetSimulatorV45()
    df, _, _ = sim.simulate()
    chomage_final = df.iloc[-1]['Chômage %']
    assert 6.0 < chomage_final < 10.0, f"Chômage {chomage_final:.1f}% hors fourchette 6-10%"


# === COMPORTEMENTS DIRECTIONNELS ===

def test_tva_hausse_ameliore_deficit():
    """Augmenter la TVA doit améliorer le déficit"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    sim_tva = BudgetSimulatorV45(mesures={'tva_rate': {'taux': 0.21}})
    df_tva, _, _ = sim_tva.simulate()

    deficit_base = df_base.iloc[-1]['Déficit/PIB %']
    deficit_tva = df_tva.iloc[-1]['Déficit/PIB %']
    assert deficit_tva > deficit_base, (
        f"TVA 21% devrait améliorer le déficit: base={deficit_base:.1f}%, tva={deficit_tva:.1f}%"
    )


def test_smic_hausse_augmente_dette():
    """Augmenter le SMIC doit augmenter la dette (coût net > retour croissance)"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    sim_smic = BudgetSimulatorV45(mesures={'smic': {'montant_brut': 2200}})
    df_smic, _, _ = sim_smic.simulate()

    dette_base = df_base.iloc[-1]['Dette/PIB %']
    dette_smic = df_smic.iloc[-1]['Dette/PIB %']
    assert dette_smic > dette_base, (
        f"SMIC 2200 devrait augmenter la dette: base={dette_base:.1f}%, smic={dette_smic:.1f}%"
    )


def test_defense_augmente_dette():
    """Augmenter les dépenses de défense doit augmenter la dette"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    sim_def = BudgetSimulatorV45(mesures={'defense': {'budget': 65}})
    df_def, _, _ = sim_def.simulate()

    dette_base = df_base.iloc[-1]['Dette/PIB %']
    dette_def = df_def.iloc[-1]['Dette/PIB %']
    assert dette_def > dette_base, (
        f"Défense 65 Md€ devrait augmenter la dette: base={dette_base:.1f}%, def={dette_def:.1f}%"
    )


def test_investissement_massif_augmente_dette():
    """150 Md€ d'investissement doit augmenter la dette (pas d'autofinancement magique)"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    mesures = {
        'education': {'budget': 80, 'enseignants': 0, 'salaires': 0},
        'transition_ecologique': {'investissement': 40, 'taxe_carbone': 44.6, 'renovation': 40},
        'defense': {'budget': 70},
        'recherche_publique': {'budget': 15}
    }
    sim_inv = BudgetSimulatorV45(mesures=mesures)
    df_inv, _, _ = sim_inv.simulate()

    dette_base = df_base.iloc[-1]['Dette/PIB %']
    dette_inv = df_inv.iloc[-1]['Dette/PIB %']
    # Seuil recalé >5 → >2,5 pt (refonte 2026-06-10, mesuré +3,4) : même delta
    # en Md€, mais ratio dilué par la baseline honnête plus haute (150 vs 122 %)
    # et impulsion macro laguée d'un an (effets retours décalés). Le sens du
    # test (pas d'autofinancement magique) est inchangé : delta strictement > 0
    # et substantiel.
    assert dette_inv > dette_base + 2.5, (
        f"Invest massif devrait augmenter la dette de >2,5 pts: base={dette_base:.1f}%, inv={dette_inv:.1f}%"
    )


def test_austerite_reduit_croissance():
    """L'austérité massive doit réduire la croissance moyenne sous le baseline"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    mesures = {
        'rabot_uniforme': {'taux_reduction': 0.08},
        'retraites': {'age_depart': 65, 'duree_cotisation': 43.5, 'indexation': 0.7},
        'sante': {'effort_hopital': 100, 'effort_ambu': 100, 'effort_prev_org': 100}
    }
    sim_aus = BudgetSimulatorV45(mesures=mesures)
    df_aus, _, _ = sim_aus.simulate()

    croissance_base = df_base['Croissance %'].mean()
    croissance_aus = df_aus['Croissance %'].mean()
    assert croissance_aus < croissance_base, (
        f"Austérité devrait réduire la croissance: base={croissance_base:.2f}%, aus={croissance_aus:.2f}%"
    )


# === ANTI-RÉGRESSIONS SPÉCIFIQUES ===

def test_pas_de_contamination_tva():
    """Ajouter TVA à un paquet de réformes ne doit pas augmenter la dette de >3 pts"""
    mesures_base = {
        'retraites': {'age_depart': 64, 'duree_cotisation': 43, 'indexation': 0.8},
        'sante': {'effort_hopital': 100, 'effort_ambu': 100, 'effort_prev_org': 100},
        'fraude_fiscale': {'effort': 1.0},
    }
    sim1 = BudgetSimulatorV45(mesures=mesures_base)
    df1, _, _ = sim1.simulate()

    mesures_tva = {**mesures_base, 'tva_rate': {'taux': 0.21}}
    sim2 = BudgetSimulatorV45(mesures=mesures_tva)
    df2, _, _ = sim2.simulate()

    delta = df2.iloc[-1]['Dette/PIB %'] - df1.iloc[-1]['Dette/PIB %']
    assert delta < 3.0, (
        f"TVA marginale ne devrait pas dégrader la dette de >3 pts: delta={delta:+.1f}"
    )


def test_retraites_64ans_reduit_dette_significativement():
    """Recul age legal 62.75 -> 64 ans : economie calibree COR 2024, verifiee en Md€ (verite
    physique) ET en points de dette (borne elargie pour la baseline tendancielle A+B).

    Calibre sur COR 2024 : montee en charge 5 ans, coefficient stationnaire -16 Md€/an,
    cumul ~ -160 Md€. RECALIBRAGE 2026-06 (baseline A+B, tendanciel ~+1,1%/an) : la trajectoire
    statu-quo de reference etant plus pentue, la MEME economie en Md€ pese mecaniquement MOINS en
    POINTS de dette (denominateur plus gros) -> la borne ratio passe de [-3.5,-2.0] (ancienne
    baseline) a [-2.3,-0.9]. La garde Md€ ci-dessous VERROUILLE la verite physique COR
    independamment du denominateur (anti-faux-vert : une borne ratio elargie ne doit jamais
    masquer une reforme sous-calibree). Le handler retraites (depenses.py) est INCHANGE.
    """
    sim_base = BudgetSimulatorV45(periods=10)
    df_base, _, _ = sim_base.simulate()

    sim_64 = BudgetSimulatorV45(
        periods=10,
        mesures={'retraites': {'age_depart': 64, 'indexation': 1.0, 'duree_cotisation': 42.5}},
    )
    df_64, _, _ = sim_64.simulate()

    # Garde PHYSIQUE (Md€, verite COR) : l'economie de dette Y10 reste calibree en euros, quel
    # que soit le denominateur.
    # RECALIBRAGE refonte « assemblage temporel » 2026-06-10 : mesure -163,1 Md€
    # -> fenetre [-185, -135]. Decomposition exacte : economies directes handler
    # 160 Md€ cumules (phasing COR 0,2->1,0 puis -20 Md€/an stationnaire,
    # handler INCHANGE) + interets evites composes (~14 Md€) - feedback macro
    # modere (multiplicateur consolidation + second tour recettes, ~11 Md€).
    # L'ancienne mesure -115,7 etait LE chiffre suspect : ~44 Md€ d'economies
    # s'evaporaient dans le lag d'assemblage (recettes laguees + deflateur
    # retarde) — la refonte rend les reformes structurelles a leur vrai
    # rendement physique. Anti-faux-vert bilateral : retomber vers -115 =
    # retour du lag ; depasser -185 = double-comptage.
    economie_md = df_64.iloc[-1]['Dette'] - df_base.iloc[-1]['Dette']
    assert -185 < economie_md < -135, (
        f"Economie retraite 64 ans hors calibration COR (verite physique Md€): {economie_md:+.0f} Md€"
    )

    # Garde RATIO (points de dette) : recalee avec la garde Md€ (mesure -3,84 pt :
    # -163 Md€ sur un PIB 2035 plus bas — inflation 1,1-1,4 % vs 2,33 % artificiel).
    delta_dette_y10 = df_64.iloc[-1]['Dette/PIB %'] - df_base.iloc[-1]['Dette/PIB %']
    assert -5.0 < delta_dette_y10 < -2.5, (
        f"Retraite 64 ans devrait reduire dette Y10 (borne refonte [-5.0,-2.5]): "
        f"delta={delta_dette_y10:+.2f} pts (base={df_base.iloc[-1]['Dette/PIB %']:.1f}%, "
        f"64ans={df_64.iloc[-1]['Dette/PIB %']:.1f}%)"
    )


def test_niches_sociales_tge_suppression_60mds_destroys_jobs():
    """Suppression 60 Md€ niches sociales TGE → -100k a -200k emplois Y10.

    Calibre sur Bozio-Wasmer CAE 2024 : 138k emplois pour 60 Md€ supprimes.
    Test DIRECTIONNEL critique : valide la cible empirique en bout de cascade
    (multiplicateur fiscal + Okun), pas seulement le signal direct du handler.

    Garde-fou contre le bug double-comptage corrige le 6 mai 2026 : un coefficient
    direct mal calibre amplifiait l'effet ×9 a ×95 sans etre detecte par les tests
    qui validaient impacts['chomage'] (tautologique) au lieu du chomage_final.
    """
    sim_base = BudgetSimulatorV45(periods=10)
    df_base, _, _ = sim_base.simulate()
    chomage_y10_base = df_base.iloc[-1]['Chômage %']

    # NFP-style : suppression de 60 Md€ niches sociales TGE (montant 70 → 10)
    sim = BudgetSimulatorV45(periods=10, mesures={'niches_sociales_tge': {'montant': 10}})
    df, _, _ = sim.simulate()
    chomage_y10 = df.iloc[-1]['Chômage %']
    delta_chomage = chomage_y10 - chomage_y10_base

    # Cible Bozio-Wasmer 2024 : ~0.48 pt chomage. Plage [0.30, 0.80] couvre l'incertitude.
    assert 0.30 <= delta_chomage <= 0.80, (
        f"Suppression 60 Md€ niches sociales TGE devrait donner +0.30 a +0.80 pt chomage "
        f"(cible Bozio-Wasmer 138k emplois ≈ +0.48 pt). Obtenu : +{delta_chomage:.2f} pt "
        f"(base={chomage_y10_base:.2f}%, scenario={chomage_y10:.2f}%). "
        f"Si effet ×5+ : risque double-comptage signal direct + multiplicateur fiscal."
    )

    # Verification cumul emplois (28.7M actifs) : doit etre dans 100k-200k
    emplois_perdus = delta_chomage * 287_000
    assert 85_000 <= emplois_perdus <= 230_000, (
        f"Emplois perdus hors fourchette [85k, 230k]: {emplois_perdus:.0f}"
    )


def test_investissement_booste_croissance():
    """L'investissement productif doit booster la croissance vs baseline"""
    sim_base = BudgetSimulatorV45()
    df_base, _, _ = sim_base.simulate()

    mesures = {
        'education': {'budget': 80, 'enseignants': 0, 'salaires': 0},
        'transition_ecologique': {'investissement': 20, 'taxe_carbone': 44.6, 'renovation': 10},
        'recherche_publique': {'budget': 15}
    }
    sim_inv = BudgetSimulatorV45(mesures=mesures)
    df_inv, _, _ = sim_inv.simulate()

    croissance_base = df_base['Croissance %'].mean()
    croissance_inv = df_inv['Croissance %'].mean()
    assert croissance_inv > croissance_base + 0.05, (
        f"Invest devrait booster croissance de >0.05%: base={croissance_base:.2f}%, inv={croissance_inv:.2f}%"
    )
