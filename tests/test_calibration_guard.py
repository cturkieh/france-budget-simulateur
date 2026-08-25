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

import pytest

from budget_simulator.simulator import BudgetSimulatorV45


@pytest.fixture(scope='module')
def baseline_df():
    """Statu quo 10 ans simulé UNE fois pour tout le module (dédup : 10 tests
    relançaient chacun la même baseline — passe efficacité revue 2026-06-10)."""
    df, _, _ = BudgetSimulatorV45().simulate()
    return df


# === BASELINE (aucune réforme) ===

def test_baseline_dette_range(baseline_df):
    """La dette baseline doit rester dans 155-170 % en 2035 (v0.6.1).

    RECALIBRAGE v0.6.1 lot 8 — Phillips ancrée (mesuré 162,1 %) : le
    déflateur réalisé passe de ~0,9 à ~1,5 %/an, donc le PIB nominal 2035
    est ~3 % plus haut. Effet de DÉNOMINATEUR pur sur le ratio, −10,1 pt
    (172,2 → 162,1) ; en euros la dette bouge à peine. La fenêtre garde la
    même demi-largeur (±8 pt) qu'en v0.6.0 : elle verrouille la mécanique de
    Domar, pas un consensus qui n'existe pas à cet horizon. À ne PAS lire
    comme une amélioration des finances publiques : c'est la correction d'un
    ratio que la v0.6.0 surestimait faute de croissance nominale.

    RECALIBRAGE v0.6.0 (audit externe 08/2026, mesuré 169,6 %) : taux marginal
    ré-ancré sur le marché (3,47 % @ 117,6 % AFT, courbe monotone) → charge
    124 Md€ en 2030 (corridor mission IGF 07/2026) et effet boule de neige
    réel (r > g dès 2029). L'ancien 150,4 % reposait sur un taux marginal 1,9 %
    (ancre ZIRP morte, écart 148 pb au marché).

    RECALIBRAGE refonte « assemblage temporel » 2026-06-10 (mesuré 150,4 %) :
    la baseline honnête garde un déficit ~5-5,5 % SANS consolidation (l'ancien
    moteur fabriquait ~24 Md€/an d'assainissement fantôme) et une inflation
    effective ~1,1-1,4 % (point fixe 1,5 % À CETTE DATE, gap négatif) au lieu du
    2,33 % artificiel qui gonflait le PIB nominal. Mécanique de Domar : à
    déficit ~5,3 % et nominal ~+2 %/an, Δratio ≈ +3 pt/an → ~150 % en 2035.
    Point d'ancrage externe : Y5 (2030) = 130,7 %, cohérent HCFP (« >125 % en
    2030 sans ajustement ») ; 2035 est au-delà des horizons publiés, la
    fourchette verrouille la mécanique, pas un consensus inexistant."""
    df = baseline_df
    dette = df.iloc[-1]['Dette/PIB %']
    assert 155 < dette < 170, f"Baseline dette {dette:.1f}% hors fourchette 155-170%"


def test_baseline_deficit_range(baseline_df):
    """Le déficit baseline 2035 doit rester dans -13,5/-9 % (v0.6.0, boule de neige réelle)"""
    df = baseline_df
    deficit = df.iloc[-1]['Déficit/PIB %']
    # v0.6.0 : à taux honnêtes, la boule de neige porte le déficit statu quo
    # 2035 vers ~-11,7 % (charge ~7 % du PIB à 170 % de dette) — le message
    # « politique inchangée insoutenable » de la mission IGF, prolongé à 2035.
    assert -13.5 < deficit < -9.0, f"Baseline déficit {deficit:.1f}% hors fourchette -13,5/-9%"


def test_baseline_croissance_range(baseline_df):
    """La croissance moyenne doit être entre 0.5% et 1.5% (potentiel France)"""
    df = baseline_df
    croissance = df['Croissance %'].mean()
    assert 0.5 < croissance < 1.5, f"Baseline croissance {croissance:.2f}% hors fourchette 0.5-1.5%"


def test_baseline_chomage_range(baseline_df):
    """Le chômage doit rester entre 6% et 10%"""
    df = baseline_df
    chomage_final = df.iloc[-1]['Chômage %']
    assert 6.0 < chomage_final < 10.0, f"Chômage {chomage_final:.1f}% hors fourchette 6-10%"


# === COMPORTEMENTS DIRECTIONNELS ===

def test_tva_hausse_ameliore_deficit(baseline_df):
    """Augmenter la TVA doit améliorer le déficit"""
    df_base = baseline_df

    sim_tva = BudgetSimulatorV45(mesures={'tva_rate': {'taux': 0.21}})
    df_tva, _, _ = sim_tva.simulate()

    deficit_base = df_base.iloc[-1]['Déficit/PIB %']
    deficit_tva = df_tva.iloc[-1]['Déficit/PIB %']
    assert deficit_tva > deficit_base, (
        f"TVA 21% devrait améliorer le déficit: base={deficit_base:.1f}%, tva={deficit_tva:.1f}%"
    )


def test_smic_hausse_augmente_dette(baseline_df):
    """Augmenter le SMIC doit augmenter la dette (coût net > retour croissance)"""
    df_base = baseline_df

    sim_smic = BudgetSimulatorV45(mesures={'smic': {'montant_brut': 2200}})
    df_smic, _, _ = sim_smic.simulate()

    dette_base = df_base.iloc[-1]['Dette/PIB %']
    dette_smic = df_smic.iloc[-1]['Dette/PIB %']
    assert dette_smic > dette_base, (
        f"SMIC 2200 devrait augmenter la dette: base={dette_base:.1f}%, smic={dette_smic:.1f}%"
    )


def test_defense_augmente_dette(baseline_df):
    """Augmenter les dépenses de défense doit augmenter la dette"""
    df_base = baseline_df

    sim_def = BudgetSimulatorV45(mesures={'defense': {'budget': 65}})
    df_def, _, _ = sim_def.simulate()

    dette_base = df_base.iloc[-1]['Dette/PIB %']
    dette_def = df_def.iloc[-1]['Dette/PIB %']
    assert dette_def > dette_base, (
        f"Défense 65 Md€ devrait augmenter la dette: base={dette_base:.1f}%, def={dette_def:.1f}%"
    )


def test_investissement_massif_pas_dautofinancement_magique(baseline_df):
    """v0.6.0 — la garde « pas d'autofinancement magique » se teste en EUROS.

    Avec les multiplicateurs symétrisés (audit 08/2026), un paquet
    d'investissement massif AUGMENTE la dette en niveau (€) — pas de repas
    gratuit — mais peut RÉDUIRE le ratio dette/PIB (dénominateur : FMI WEO
    oct. 2014 ch. 3 — l'investissement public en creux conjoncturel financé
    par dette peut améliorer le ratio ; effet borné). La dépense NON
    productive (défense +70 Md€, multiplicateur transfert), elle, dégrade
    AUSSI le ratio."""
    df_base = baseline_df

    mesures = {
        'education': {'budget': 80, 'enseignants': 0, 'salaires': 0},
        'transition_ecologique': {'investissement': 40, 'taxe_carbone': 44.6, 'renovation': 40},
        'defense': {'budget': 70},
        'recherche_publique': {'budget': 15}
    }
    df_inv, _, _ = BudgetSimulatorV45(mesures=mesures).simulate()

    # (a) En euros : la dette augmente substantiellement (mesuré ~+380 Md€ hors
    # taxe carbone du paquet, ~+150 Md€ net ici avec les 44,6 Md€ de recettes).
    delta_eur = df_inv.iloc[-1]['Dette'] - df_base.iloc[-1]['Dette']
    assert delta_eur > 50, f"Invest massif : dette € devrait monter nettement, mesuré {delta_eur:+.0f} Md€"
    # (b) En ratio : l'amélioration éventuelle reste bornée (mesuré −1,2 pt
    # post-fixes v0.6.0 ; le paquet invest pur max mesuré −9,5 pt).
    delta_ratio = df_inv.iloc[-1]['Dette/PIB %'] - df_base.iloc[-1]['Dette/PIB %']
    assert delta_ratio > -12, f"Amélioration de ratio invraisemblable : {delta_ratio:+.1f} pt"

    # (c) Dépense non productive seule : ratio ET euros se dégradent.
    df_def, _, _ = BudgetSimulatorV45(mesures={'defense': {'budget': 70}}).simulate()
    assert df_def.iloc[-1]['Dette/PIB %'] > df_base.iloc[-1]['Dette/PIB %'] + 1.5
    assert df_def.iloc[-1]['Dette'] > df_base.iloc[-1]['Dette'] + 100


def test_austerite_reduit_croissance(baseline_df):
    """L'austérité massive doit réduire la croissance moyenne sous le baseline"""
    df_base = baseline_df

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

def test_pas_de_contamination_tva(baseline_df):
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


def test_retraites_64ans_ne_capture_que_lacceleration_du_calendrier(baseline_df):
    """RECADRAGE v0.6.1 — « 64 ans » n'est plus une reforme, c'est le DROIT
    EN VIGUEUR a partir de 2032.

    La reference d'age du moteur suit desormais le calendrier legal
    post-LFSS 2026 (62,75 ans geles jusqu'en 2027, puis +3 mois par an jusqu'a
    64,0 ans en 2032), et cette montee en charge est deja dans la baseline
    (tendanciel mission IGF 07/2026). Un programme « je maintiens 64 ans » ne
    peut donc plus etre credite de l'economie que la loi produit toute seule :
    il ne capture que l'ACCELERATION du calendrier sur 2026-2031.

    Decomposition du canal budgetaire direct (6,0 Md€ par annee d'ecart,
    phasing 5 ans, net de 9,6 % de fuite sociale residuelle) : 1,4 + 2,7 +
    3,3 + 3,3 + 2,7 + 1,4 = 14,7 Md€ cumules, puis ZERO a partir de 2032.

    RECALIBRATION v0.6.1 lot 3 : le canal emploi seniors s'ajoute a ce canal
    direct (surcroit d'offre de travail -> PIB -> recettes, net de la bosse de
    chomage). Mesure : -39,5 Md€ de dette Y10, contre -17,7 avant le lot.
    Fenetre [-90 ; -22], BILATERALE et adossee a deux contre-epreuves
    mesurees :
    - au-dessus de -22 : le canal emploi a disparu (sans lui : -17,7) ;
    - au-dela de -90 : le canal est relu comme un effet de TAUX et non de
      NIVEAU (la regression v0.6.0 donne -173 Md€, mesuree).
    """
    df_base = baseline_df

    sim_64 = BudgetSimulatorV45(
        periods=10,
        mesures={'retraites': {'age_depart': 64, 'indexation': 1.0, 'duree_cotisation': 42.5}},
    )
    df_64, _, _ = sim_64.simulate()

    economie_md = df_64.iloc[-1]['Dette'] - df_base.iloc[-1]['Dette']
    assert -90 < economie_md < -22, (
        f"Acceleration vers 64 ans hors fenetre v0.6.1 : {economie_md:+.0f} Md€"
    )

    delta_dette_y10 = df_64.iloc[-1]['Dette/PIB %'] - df_base.iloc[-1]['Dette/PIB %']
    assert -2.5 < delta_dette_y10 < -0.3, (
        f"Acceleration vers 64 ans : delta dette Y10 hors fenetre v0.6.1 : "
        f"delta={delta_dette_y10:+.2f} pts (base={df_base.iloc[-1]['Dette/PIB %']:.1f}%, "
        f"64ans={df_64.iloc[-1]['Dette/PIB %']:.1f}%)"
    )


def test_retraites_65ans_reduit_dette_significativement(baseline_df):
    """Verite physique du bareme d'age, mesuree LA OU un programme depasse
    reellement le droit en vigueur.

    65 ans, c'est +2,25 annees d'ecart en 2026 puis +1,0 annee a partir de
    2032 (le calendrier legal ayant rattrape 64 ans). A 6,0 Md€ par annee
    d'age (DG Tresor, COR 27/01/2022, doc n 12, diapo 5 ; Cour des comptes
    02/2025, T6 p. 72), cela fait ~46 Md€ d'economies directes cumulees sur
    l'horizon, ~42 nettes de la fuite sociale residuelle.

    RECALIBRATION v0.6.1 lot 3 : le canal emploi seniors ajoute le surcroit
    de recettes ne du PIB (~+0,51 % de PIB reel en 2035), net de la bosse de
    chomage transitoire. Mesure : -170 Md€ de dette Y10, contre -74 avant le
    lot. C'est l'ordre de grandeur de la Cour (T6 p. 72 : 17,7 Md€ par an au
    plein regime, toutes APU) cumule sur dix ans.

    Anti-faux-vert bilateral, adosse a deux contre-epreuves mesurees :
    - au-dessus de -110 : le canal emploi a disparu (sans lui : -74) ;
    - au-dela de -300 : le canal est relu comme un effet de TAUX et non de
      NIVEAU (la regression v0.6.0 donne -537 Md€, mesuree).
    """
    df_base = baseline_df

    df_65, _, _ = BudgetSimulatorV45(
        periods=10,
        mesures={'retraites': {'age_depart': 65, 'indexation': 1.0, 'duree_cotisation': 42.5}},
    ).simulate()

    economie_md = df_65.iloc[-1]['Dette'] - df_base.iloc[-1]['Dette']
    assert -300 < economie_md < -110, (
        f"Economie retraite 65 ans hors fenetre v0.6.1 : {economie_md:+.0f} Md€"
    )

    delta_dette_y10 = df_65.iloc[-1]['Dette/PIB %'] - df_base.iloc[-1]['Dette/PIB %']
    assert -9.0 < delta_dette_y10 < -2.5, (
        f"Retraite 65 ans devrait reduire la dette Y10 : delta={delta_dette_y10:+.2f} pts "
        f"(base={df_base.iloc[-1]['Dette/PIB %']:.1f}%, 65ans={df_65.iloc[-1]['Dette/PIB %']:.1f}%)"
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


def test_investissement_booste_croissance(baseline_df):
    """L'investissement productif doit booster la croissance vs baseline"""
    df_base = baseline_df

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
