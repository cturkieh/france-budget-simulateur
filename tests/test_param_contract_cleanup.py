"""Garde-fous remise en ordre du contrat de paramètres (2026-05-17, Niveau 0+1).

Ces tests verrouillent :
- l'en-tête anti-piège dans policy_measures.json (Niveau 0) ;
- l'absence de code mort asu_active/asu_plafonnement réintroduit (Niveau 1) ;
- la délégation simulator -> config des défauts, sans dict ré-inliné (Niveau 1).
"""
import inspect
import json
from pathlib import Path

from budget_simulator import BudgetSimulatorV45

ROOT = Path(__file__).resolve().parent.parent


def test_policy_json_has_contract_warning_header():
    cfg = json.loads((ROOT / "policy_measures.json").read_text(encoding="utf-8"))
    assert "_AVERTISSEMENT_CONTRAT" in cfg, "en-tête anti-piège manquant"
    assert "n'est PAS le contrat" in cfg["_AVERTISSEMENT_CONTRAT"], (
        "l'avertissement doit dire explicitement que parametres n'est pas le contrat"
    )
    # Vrai intent anti-piège : la description doit elle-même clarifier que
    # `parametres` n'est pas le contrat (PAS bannir un compte de sliders —
    # un compte dans un fichier metadata drifte par nature, granularité-
    # dépendant ; le compte canonique vit dans l'UI, auto-calculé).
    assert "N'EST PAS le contrat" in cfg.get("description", ""), (
        "la description doit clarifier que 'parametres' n'est pas le contrat"
    )


def test_prestations_indexation_default_has_no_dead_asu_keys(default_values):
    pi = default_values["prestations_indexation"]
    assert pi == {"taux_indexation": 1.0}, f"clés mortes résiduelles: {pi}"


def test_simulator_delegates_defaults_to_config(default_values):
    """Garde anti-ré-inline RÉEL (pas une égalité tautologique).

    Détecte structurellement qu'un mainteneur recopie un dict littéral de
    défauts dans _get_default_values (régression du drift #2/#3 historique) :
    la source de la méthode DOIT déléguer à load_default_values et ne PAS
    contenir de littéral de défauts. L'égalité de valeur est une sanity check
    complémentaire."""
    src = inspect.getsource(BudgetSimulatorV45._get_default_values)
    assert "load_default_values" in src, (
        "_get_default_values ne délègue plus à config.load_default_values (ré-inline ?)"
    )
    assert "'tva_rate'" not in src, (
        "dict de défauts ré-inliné dans _get_default_values (DRY cassé, drift #2/#3)"
    )
    sim = BudgetSimulatorV45(mesures={})
    assert sim._get_default_values() == default_values, (
        "valeurs de défauts simulator != config"
    )


def test_json_parametres_aligned_with_registry():
    """Aucun bloc `parametres` mort sur les leviers `type:"fonction"`.

    Le registre (source de vérité, généré depuis les handlers) liste les
    vraies clés. Tout bloc JSON déclarant une clé que le handler ne lit pas
    = piège contributeur (« doc qui ment »). T3 rétro-aligne le JSON dessus.
    """
    reg = json.loads(
        (ROOT / "tests/snapshots/measure_registry.json").read_text("utf-8")
    )
    cfg = json.loads((ROOT / "policy_measures.json").read_text("utf-8"))
    dead = {}
    for m in cfg["mesures"]:
        if m.get("type") != "fonction":
            continue
        real = set(reg["mesures"].get(m["id"], {}).get("params", {}))
        real.discard("<DYNAMIC>")
        real.discard("<UNMODELED>")
        extra = set(m.get("parametres", {})) - real
        if extra:
            dead[m["id"]] = sorted(extra)
    assert not dead, f"blocs parametres morts (handler ne les lit pas) : {dead}"
