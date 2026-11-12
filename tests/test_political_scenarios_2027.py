"""Smoke test : les scénarios politiques 2027 simulent sans erreur ASTEVAL.

Garde-fou anti-régression après le renommage nfp_2027 → lfi_2027 et l'activation
du scénario PS 2027 (mai 2026). Deux niveaux de couverture :
- le dict SCENARIOS ci-dessous = sous-ensemble LEGACY figé à la main (assertions
  de forme détaillées : longueur 11 ans, NaN, bornes d'aberration) ;
- FULL_SCENARIOS (lu depuis scenarios.json via run_scenarios_full) = la couverture
  COMPLÈTE et à jour de tous les scénarios (garde-fou PA 2029 paramétré + golden
  master bit-exact pour la sanité des trajectoires).
Un scénario récent (ex. horizons_2027, 07/2026) peut donc être absent du dict
legacy tout en étant intégralement couvert par FULL_SCENARIOS + golden master.

Ne valide PAS la calibration économique des scénarios — seulement leur exécutabilité.
"""

import json
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
    # Release E (chantier W1) : « depenses_etat » n'a jamais été un levier du
    # moteur (absent de policy_measures.json) ; il était sauté en silence, et
    # ce cas simulait le statu quo. Le levier du rabot uniforme de 8 % est
    # `rabot_uniforme.taux_reduction` (scénario publié de ce cas).
    "im_rabot_2029": {
        "rabot_uniforme": {"taux_reduction": 0.08},
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


def _front_src():
    """``frontend-react/src`` du dépôt parent, localisé par la MÊME source que les
    scénarios (``scenarios.json`` : ``BUDGETLAB_SCENARIOS_JSON``, exposée par le
    conftest parent, ou résolution automatique de run_scenarios_full).

    v0.6.7 : la garde cherchait ``Path(__file__).resolve().parents[1] /
    "frontend-react"``. Lancée depuis le parent, ``resolve()`` suit le symlink
    ``tests/`` et pointe vers le submodule, où ``frontend-react/`` n'existe pas :
    elle sautait dans TOUTES les exécutions (piège symlink documenté)."""
    from tests.snapshots.run_scenarios_full import _SCENARIOS_JSON
    if _SCENARIOS_JSON is None:
        return None
    src = _SCENARIOS_JSON.resolve().parents[1]
    return src if (src / "pages" / "ScenariosPage.jsx").exists() else None


@pytest.mark.skipif(
    _front_src() is None,
    reason="frontend-react/ hors périmètre open source (repo privé) — "
    "garde-fou frontend non applicable à un fork du moteur seul",
)
def test_aucune_collision_id_lfi_2026():
    """Garde-fou anti-régression : l'acronyme LFI désigne uniquement le parti, jamais la Loi Finances.

    Recible v0.6.7 : les identifiants ne vivent plus dans ``ScenariosPage.jsx``
    mais dans ``scenarios.json`` (source unique, cf. run_scenarios_full) et leurs
    libellés dans ``scenariosMeta.js``."""
    src = _front_src()
    assert "lfi_2027" in FULL_SCENARIOS, "Le scénario lfi_2027 (LFI Mélenchon) doit être présent"
    assert "nfp_2027" not in FULL_SCENARIOS, (
        "Le scénario nfp_2027 a été renommé en lfi_2027 — pas de définition résiduelle")
    for fichier in ("data/scenarios.json", "data/scenariosMeta.js", "pages/ScenariosPage.jsx"):
        contenu = (src / fichier).read_text(encoding="utf-8")
        assert "LFI 2026" not in contenu, (
            f"{fichier} : collision sémantique, « LFI 2026 » désignerait la Loi de finances "
            "alors que LFI = le parti")


# Valeurs PA 2029 figées par revue humaine sur les apiMeasures complètes de chaque scénario publié.
# Tolérance ±1.5 pt = absorbe les recalibrages mineurs tout en détectant la perte d'un gate
# one-time PA (tva_rate, impot_revenu, impots_production, elargissement_ir, fiscalite_patrimoine,
# transition_ecologique taxe_carbone) ou de l'asymétrie fonction_publique.
#
# Ne PAS dériver depuis le golden master : ce serait une auto-référence (régénérer le snapshot
# puis comparer à lui-même = test qui passe toujours). Les valeurs vivent dans
# ``tests/snapshots/pa_2029_figes.json`` (données figées, jamais régénérées par un script) :
# après un recalibrage ou un ré-encodage volontaire, y reporter les valeurs auditées, dans un
# commit identifiable. L'historique des recalages (v0.6.1 à v0.6.11) est dans le git de ce
# fichier et au CHANGELOG ; release de paramètres P (v0.8.1) : les dix encodages suivent leurs
# sources, valeurs re-figées après audit (CHANGELOG, v0.8.1).
EXPECTED_PA_2029_FULL = json.loads(
    (Path(__file__).resolve().parent / 'snapshots' / 'pa_2029_figes.json').read_text(encoding='utf-8'))['valeurs']


@_FULL_SCENARIOS_AVAILABLE
def test_expected_pa_keyset_couvre_tous_les_scenarios():
    """Anti-dérive BIDIRECTIONNELLE des jeux de clés : un scénario ajouté sans
    valeur attendue échoue déjà (KeyError dans le test paramétré), mais un
    scénario RETIRÉ de scenarios.json ferait silencieusement disparaître son cas
    paramétré (l'entrée EXPECTED périmée ne serait plus jamais lue). On verrouille
    l'égalité exacte des deux ensembles."""
    assert set(EXPECTED_PA_2029_FULL) == set(FULL_SCENARIOS), (
        f"dérive EXPECTED_PA_2029_FULL ↔ scenarios.json : "
        f"manquants={set(FULL_SCENARIOS) - set(EXPECTED_PA_2029_FULL)} ; "
        f"périmés={set(EXPECTED_PA_2029_FULL) - set(FULL_SCENARIOS)}"
    )


@_FULL_SCENARIOS_AVAILABLE
@pytest.mark.parametrize("name,measures", FULL_SCENARIOS.items())
def test_pa_2029_garde_fou_gating_one_time(name, measures):
    """Garde-fou anti-régression de l'indice de pouvoir d'achat (v0.6.8 : RDB-moteur).
    Une dérive ≥1.5 pt sur un scénario signale un changement de comportement à investiguer."""
    # Mode historique : mesures telles que le mode les accepte (release P).
    from tests.snapshots.run_scenarios_full import pour_le_mode
    sim = BudgetSimulatorV45(periods=10, mesures=pour_le_mode(measures))
    df_main, _, _ = sim.simulate()
    pa_2029 = df_main.iloc[4]["Pouvoir d'Achat"]
    expected = EXPECTED_PA_2029_FULL[name]
    assert abs(pa_2029 - expected) < 1.5, (
        f"{name}: PA 2029 = {pa_2029:.1f} hors tolérance ±1.5 vs attendu {expected:.1f} "
        f"(régression possible sur l'indice RDB-moteur ou les canaux ménages des handlers)"
    )
