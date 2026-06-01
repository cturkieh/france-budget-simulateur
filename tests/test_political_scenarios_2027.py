"""Smoke test : les 8 scénarios politiques 2027 simulent sans erreur ASTEVAL.

Garde-fou anti-régression après le renommage nfp_2027 → lfi_2027 et l'activation
du scénario PS 2027 (mai 2026). Vérifie que les apiMeasures de chaque scénario,
tels qu'ils sont déclarés dans frontend-react/src/pages/ScenariosPage.jsx, sont
mappés sur des handlers Python existants (ou des formules ASTEVAL valides) et
produisent une trajectoire 10 ans cohérente.

Ne valide PAS la calibration économique des scénarios — seulement leur exécutabilité.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from budget_simulator.simulator import BudgetSimulatorV45  # noqa: E402
from tests.snapshots.run_scenarios_full import SCENARIOS as FULL_SCENARIOS  # noqa: E402

# Garde-fou PA 2029 et smoke test FULL_SCENARIOS dépendent de `scenarios.json`
# (cf run_scenarios_full). Si la source est absente (fork moteur seul), parametrize
# collecterait 0 case et le garde-fou disparaîtrait silencieusement → on skip
# explicitement plutôt que d'avoir un faux vert.
_FULL_SCENARIOS_AVAILABLE = pytest.mark.skipif(
    not FULL_SCENARIOS,
    reason="scenarios.json hors périmètre fork moteur seul (frontend-react absent)",
)


SCENARIOS = {
    "lf_2026": {
        "is_exceptionnel_tge": {"montant": 7.3},
    },
    "rn_2027_bardella": {
        "retraites": {"age_depart": 61.5, "indexation": 1.0, "duree_cotisation": 41.0},
        "tva_energie": {"taux": 0.055},
        "cotisations_salariales": {"baisse_points": 2},
        "impots_production": {"montant": 87},
        "taxe_superprofits": {"intensite": 0.50},
    },
    "lfi_2027_melenchon": {
        "retraites": {"age_depart": 60.0, "indexation": 1.0, "duree_cotisation": 40.0},
        "smic": {"montant_brut": 2050},
        "isf_climatique": {"intensite": 1.0},
        "impot_societes": {"taux": 0.30, "niches": 0},
        "impot_revenu": {"taux_superieur": 0.60, "decote": 1.0},
        "taxe_superprofits": {"intensite": 1.0},
        "tva_energie": {"taux": 0.055},
        "transition_ecologique": {"investissement": 50, "renovation": 30, "taxe_carbone": 120},
        "csg": {"taux": 0.105, "progressive": 1},
        "niches_fiscales_tge": {"montant": 20},
        "niches_sociales_tge": {"montant": 50},
    },
    "ps_2027": {
        "retraites": {"age_depart": 62.0, "indexation": 1.0, "duree_cotisation": 43.0},
        "smic": {"montant_brut": 2150},
        "isf_climatique": {"intensite": 0.60},
        "fiscalite_patrimoine": {"intensite": 0.25},
        "impot_societes": {"taux": 0.27},
    },
    "lr_2027": {
        "asu": {"asu_activation": 1, "asu_plafonnement": 0.70},
        "fonction_publique": {"effectifs": -100000},
        "fonction_publique_reforme": {"fusion_agences": 60},
        "prestations_indexation": {"taux_indexation": 0.005},
    },
    "renaissance_2027": {
        "retraites": {"age_depart": 64, "indexation": 0.80, "duree_cotisation": 43},
        "asu": {"asu_activation": 1},
        "transition_ecologique": {"investissement": 20, "taxe_carbone": 110},
    },
    "im_rabot_2029": {
        "depenses_etat": {"economies_pct": 0.08},
    },
    "im_competitivite_2029": {
        "impots_production": {"montant": 80},
    },
}


@pytest.mark.parametrize("name,measures", SCENARIOS.items())
def test_scenario_simule_sans_erreur(name, measures):
    """Chaque scénario doit produire une trajectoire 10 ans complète sans crash."""
    sim = BudgetSimulatorV45(periods=10, mesures=measures)
    df_main, df_secondary, summary = sim.simulate()

    assert len(df_main) == 11, f"{name}: attendu 11 années (2025-2035), obtenu {len(df_main)}"
    assert df_main["Dette/PIB %"].notna().all(), f"{name}: NaN dans Dette/PIB"
    assert df_main["Déficit/PIB %"].notna().all(), f"{name}: NaN dans Déficit/PIB"
    assert df_main["Chômage %"].notna().all(), f"{name}: NaN dans Chômage"

    # Bornes de cohérence (plage très large : c'est un smoke test, pas un calibration test)
    final = df_main.iloc[-1]
    assert 80 < final["Dette/PIB %"] < 250, f"{name}: dette aberrante {final['Dette/PIB %']:.1f}%"
    assert -20 < final["Déficit/PIB %"] < 5, f"{name}: déficit aberrant {final['Déficit/PIB %']:.2f}%"
    assert 2 < final["Chômage %"] < 20, f"{name}: chômage aberrant {final['Chômage %']:.2f}%"


_SCENARIOS_JSX = (
    Path(__file__).resolve().parents[1] / "frontend-react" / "src" / "pages" / "ScenariosPage.jsx"
)


@pytest.mark.skipif(
    not _SCENARIOS_JSX.exists(),
    reason="frontend-react/ hors périmètre open source (repo privé) — "
    "garde-fou frontend non applicable à un fork du moteur seul",
)
def test_aucune_collision_id_lfi_2026():
    """Garde-fou anti-régression : l'acronyme LFI désigne uniquement le parti, jamais la Loi Finances."""
    content = _SCENARIOS_JSX.read_text()
    assert "'LFI 2026" not in content, "Collision sémantique : 'LFI 2026' désigne la Loi Finances mais LFI = parti"
    assert "lfi_2027" in content, "Le scénario lfi_2027 (LFI Mélenchon) doit être présent"
    # La string 'nfp_2027' reste autorisée dans le mapping SCENARIO_RENAMES (migration localStorage)
    assert "nfp_2027: {" not in content, "Le scénario nfp_2027 a été renommé en lfi_2027 — pas de définition résiduelle"


# Valeurs PA 2029 figées par revue humaine sur les apiMeasures complètes (8 scénarios × 35 leviers).
# Tolérance ±1.5 pt = absorbe les recalibrages mineurs tout en détectant la perte d'un gate
# one-time PA (tva_rate, impot_revenu, impots_production, elargissement_ir, fiscalite_patrimoine,
# transition_ecologique taxe_carbone) ou de l'asymétrie fonction_publique.
#
# Ne PAS dériver depuis un snapshot existant (ex: snapshot_pa_after_sprint7fixes.json) : ce serait
# une auto-référence (régénérer le snapshot puis comparer à lui-même = test qui passe toujours).
# Les valeurs ci-dessous sont figées par revue humaine lors du sprint de calibration final.
#
# Mise à jour : si recalibrage volontaire, régénérer via
#   python3 tests/snapshots/run_scenarios_full.py --out tests/snapshots/snapshot_pa_<date>.json
# et reporter les nouvelles valeurs ici (commit séparé pour traçabilité).
#
# Recalibrage 2026-05-18 (décision PO, commit inflation) : terme structurel
# de la courbe de Phillips porté de 1,2 % à 1,5 % (INFLATION_STRUCTURELLE).
# Effet ATTENDU et AUDITÉ : inflation simulée +0,1 à +0,2 pt sur l'horizon,
# qui érode le pouvoir d'achat RÉEL (revenus indexés à ~54 % seulement, cf.
# INDEXATION_BASELINE_RATIO) → PA 2029 baisse de ~0,4 à ~1,8 pt sur tous les
# scénarios, dans le bon sens (plus d'inflation ⇒ moins de PA réel). Le seul
# dépassement de tolérance était im_competitivite_2029 (105,2 → 103,4, Δ -1,8).
# Valeurs ci-dessous = nouvelles valeurs figées par revue, cohérentes avec le
# golden master régénéré. Les gates one-time PA restent inchangés (seul
# l'intercept Phillips a bougé, aucune logique de gating touchée).
# Recalibrage 2026-06-02 (décision PO) : ré-encodage fidèle du scénario plf_2026
# sur la LOI DE FINANCES 2026 VOTÉE (loi 2026-103, 19/02/2026) au lieu d'un PLF mal
# encodé. 5 leviers corrigés (chômage durée 24→18 = réforme avril 2025 tient ;
# retraites 64→suspendue ; transition verte +16→0 ; CVAE gel ; défense +6,7 Md€).
# Effet AUDITÉ : PA 2029 plf_2026 103,4 → 100,9 (Δ -2,5, hors tolérance ±1,5).
# Source : OFCE pbrief n°154 « Budget 2026 : un déficit de compromis ». Golden
# master régénéré dans le même commit. Aucune logique moteur modifiée.
EXPECTED_PA_2029_FULL = {
    "plf_2026": 100.9,
    "rn_2027": 105.8,
    "lfi_2027": 111.0,
    "renaissance_2027": 104.1,
    "lr_2027": 100.9,
    "ps_2027": 107.9,
    "im_rabot_2029": 99.4,
    "im_competitivite_2029": 103.4,
}


@_FULL_SCENARIOS_AVAILABLE
@pytest.mark.parametrize("name,measures", FULL_SCENARIOS.items())
def test_pa_2029_garde_fou_gating_one_time(name, measures):
    """Garde-fou anti-régression sur les 6 gates one-time PA + asymétrie fonction_publique.
    Une dérive ≥1.5 pt sur un scénario signale un changement de comportement à investiguer."""
    sim = BudgetSimulatorV45(periods=10, mesures=measures)
    df_main, _, _ = sim.simulate()
    pa_2029 = df_main.iloc[4]["Pouvoir d'Achat"]
    expected = EXPECTED_PA_2029_FULL[name]
    assert abs(pa_2029 - expected) < 1.5, (
        f"{name}: PA 2029 = {pa_2029:.1f} hors tolérance ±1.5 vs attendu {expected:.1f} "
        f"(régression possible sur gating one-time PA ou recalibrage fonction_publique)"
    )
