"""Tests de l'extracteur AST du contrat de paramètres (One Source of Truth).

Vérité = lectures de ``params`` dans le corps des méthodes handlers.
Parsing statique (aucune exécution, déterministe).
"""
import functools
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Niveau "sliders" du registre = parse de `frontend-react/src/components/
# ExploreCreateSection.jsx`. Pour un fork moteur seul (frontend absent),
# build_registry() lèverait RuntimeError. On skip toute la suite gracieusement.
_FRONT_JSX = REPO_ROOT / "frontend-react" / "src" / "components" / "ExploreCreateSection.jsx"
pytestmark = pytest.mark.skipif(
    not _FRONT_JSX.exists(),
    reason="frontend-react/ hors périmètre fork moteur seul",
)

# Insertion pour importer le package `scripts/` (pas de __init__.py, non
# couvert par conftest.py qui ne met que la racine pour `budget_simulator`).
sys.path.insert(0, str(REPO_ROOT))
from scripts.generate_measure_registry import (  # noqa: E402
    _KIND_FORMULE,
    _KIND_UNWIRED,
    _classify_dead_keys,
    _handler_source,
    _no_handler_entry,
    assert_contract_complete,
    build_registry,
    extract_params_from_source,
    render_markdown,
)


@pytest.fixture(scope="session")
def registry():
    """Registre construit une seule fois pour toute la session (build_registry
    instancie le moteur + parse tous les handlers : coûteux à répéter)."""
    return build_registry()


def test_extracts_literal_params_get():
    src = (
        "def _apply_x(self, measure, params, year):\n"
        "    a = params.get('asu_activation', 0)\n"
        "    b = params.get('asu_plafonnement', 0.65)\n"
    )
    keys = extract_params_from_source(src, func_name="_apply_x")
    assert keys == {
        "asu_activation": {"default": 0},
        "asu_plafonnement": {"default": 0.65},
    }


def test_get_without_default_is_optional_none():
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n    v = params.get('k')\n"
    )
    assert keys == {"k": {"default": None}}


def test_subscript_is_required_param():
    """``params['k']`` lève KeyError si absent → paramètre REQUIS, distinct

    d'un ``.get`` optionnel. Doit être capté (faux négatif sinon)."""
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n    v = params['seuil']\n"
    )
    assert keys == {"seuil": {"required": True}}


def test_membership_in_params_is_captured():
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n"
        "    if 'taux_remplacement' in params:\n"
        "        pass\n"
    )
    assert keys == {"taux_remplacement": {"presence_checked": True}}


def test_legacy_lambda_param_get_is_captured():
    """`_resolve_intensite_or_legacy(params, simplified, lambda p: p.get(...))`

    : `p` est un alias de `params`. Ses clés legacy NE doivent PAS être
    silencieusement omises du contrat (faux négatif = doc qui ment).
    """
    src = (
        "def _apply_tx(self, m, params, y):\n"
        "    a, b = _resolve_intensite_or_legacy(\n"
        "        params,\n"
        "        lambda i: (0.25 * i, 1.0),\n"
        "        lambda p: (p.get('taux', 0.25), p.get('seuil_hausse', 1.2)),\n"
        "    )\n"
    )
    keys = extract_params_from_source(src)
    assert keys == {
        "taux": {"default": 0.25},
        "seuil_hausse": {"default": 1.2},
    }


def test_lambda_arg_scoped_no_false_key_outside_lambda():
    """Une variable locale homonyme d'un arg de lambda, HORS lambda, ne doit

    PAS créer de fausse clé de contrat (faux positif relevé en Passe 2 :
    set global non re-scopé)."""
    src = (
        "def _apply_z(self, m, params, year):\n"
        "    r = _resolve_intensite_or_legacy(\n"
        "        params, lambda i: i, lambda p: p.get('taux', 0.2))\n"
        "    p = self.scenario.profile   # 'p' local SANS rapport\n"
        "    base = p.get('coef_bidon')  # ne doit PAS devenir une clé\n"
    )
    keys = extract_params_from_source(src)
    assert keys == {"taux": {"default": 0.2}}, keys


def test_nude_params_to_non_whitelisted_call_is_flagged_unmodeled():
    """`params` passé nu à une fonction non whitelistée → signal BRUYANT

    (lecture potentielle hors de notre vue, jamais omission silencieuse)."""
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n    return helper_externe(params)\n"
    )
    assert "<UNMODELED>" in keys


def test_nude_params_to_whitelisted_resolver_is_not_flagged():
    """`_resolve_intensite_or_legacy(params, ...)` est whitelisté (sa lambda

    legacy est suivie inline) : pas de faux <UNMODELED>."""
    src = (
        "def f(self, m, params, y):\n"
        "    a, b = _resolve_intensite_or_legacy(\n"
        "        params, lambda i: (i, 0), lambda p: (p.get('t', 0), 0))\n"
    )
    keys = extract_params_from_source(src)
    assert "<UNMODELED>" not in keys
    assert keys == {"t": {"default": 0}}


def test_dynamic_keys_accumulated_in_list():
    src = (
        "def _apply_y(self, measure, params, year):\n"
        "    k1 = 'a' + str(year)\n"
        "    u = params.get(k1, 0)\n"
        "    k2 = 'b' + str(year)\n"
        "    v = params.get(k2, 0)\n"
    )
    keys = extract_params_from_source(src, func_name="_apply_y")
    assert keys == {"<DYNAMIC>": {"raw": ["k1", "k2"]}}


def test_generic_iteration_is_flagged_unmodeled_not_silent():
    """`params.items()` n'énumère pas de clé statiquement : doit produire un

    signal BRUYANT `<UNMODELED>` (jamais une omission silencieuse)."""
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n"
        "    for kk, vv in params.items():\n"
        "        pass\n"
    )
    assert "<UNMODELED>" in keys
    assert keys["<UNMODELED>"]["raw"] == ["params.items()"]


def test_self_base_params_subscript_is_not_confused_with_params():
    """`self.base_params['pib_base']` (receveur Attribute) ≠ `params[...]` :

    aucune fausse clé de contrat."""
    keys = extract_params_from_source(
        "def f(self, m, params, y):\n"
        "    x = self.base_params['pib_base']\n"
    )
    assert keys == {}


def test_registry_covers_all_measure_handlers(registry):
    from budget_simulator import BudgetSimulatorV45

    handler_ids = set(BudgetSimulatorV45().measure_handlers.keys())
    assert handler_ids.issubset(set(registry["mesures"].keys())), (
        f"manquants: {handler_ids - set(registry['mesures'].keys())}"
    )
    asu = registry["mesures"]["asu"]
    assert "asu_activation" in asu["params"]
    assert "asu_plafonnement" in asu["params"]
    assert asu["params"]["asu_activation"]["default"] == 0


def test_legacy_keys_present_for_resolve_intensite_levers(registry):
    """taxe_superprofits / exonerations_salaires lisent des clés legacy via

    lambda dans `_resolve_intensite_or_legacy` : elles DOIVENT figurer au
    contrat (le bug du faux négatif silencieux relevé en revue Passe 1).
    """
    tsp = registry["mesures"]["taxe_superprofits"]["params"]
    assert {"taux", "seuil_hausse", "tous_secteurs"}.issubset(tsp)
    exo = registry["mesures"]["exonerations_salaires"]["params"]
    assert {"taux_exoneration", "seuil_hausse"}.issubset(exo)


def test_intensite_driven_levers_expose_intensite_contract(registry):
    """Leviers pilotés par intensité (INTENSITE_DOMAINS, Lot C Item 1) :

    contrat UI `intensite` + domaine canonique présent."""
    from budget_simulator.constants import INTENSITE_DOMAINS

    for mid, (lo, hi) in INTENSITE_DOMAINS.items():
        m = registry["mesures"][mid]
        assert "intensite" in m["params"], f"{mid} : contrat intensite manquant"
        assert m["params"]["intensite"]["domain"] == [lo, hi]
        assert "INTENSITE_DRIVEN" in m["flags"]


def test_registry_documents_slider_to_measure_mapping():
    """Le registre doit, pour chaque mesure pilotée par UI, lister ses sliders
    + bornes (niveau 3 : sliders -> mesures -> handlers).

    Structure réelle du snapshot : ``{"mesures": {mid: {...}}}`` (dict indexé
    par id, PAS une liste avec ``measure_id``). Le mapping slider->mesure->param
    est dérivé de ``convertToAPIFormat`` (autoritatif, non inventé) et les
    bornes de ``variablesConfig`` — tous deux dans ``ExploreCreateSection.jsx``.
    Les sliders ``effort_hopital``/``effort_ambu`` alimentent la mesure
    ``sante`` (cf. payload ``sante: { effort_hopital: measures.effort_hopital,
    effort_ambu: measures.effort_ambu, ... }``).
    """
    import json

    snap_path = REPO_ROOT / "tests" / "snapshots" / "measure_registry.json"
    snap = json.loads(snap_path.read_text("utf-8"))
    measures = snap["mesures"]
    sante = measures["sante"]
    assert "sliders" in sante, "la mesure 'sante' doit exposer ses sliders UI"
    slider_ids = {s["id"] for s in sante["sliders"]}
    assert {"effort_hopital", "effort_ambu"}.issubset(slider_ids), slider_ids
    for s in sante["sliders"]:
        assert {"min", "max", "step"}.issubset(s.keys()), s
        assert "param" in s, s  # param du handler que le slider alimente


def test_registry_slider_extraction_is_coherent_count():
    """~52-53 sliders extraits au total (cohérence anti-régression parsing).

    Si le nb diffère fortement, le parsing de allVariables/variablesConfig a
    silencieusement raté des sliders → registre menteur par omission.
    """
    import json

    snap_path = REPO_ROOT / "tests" / "snapshots" / "measure_registry.json"
    snap = json.loads(snap_path.read_text("utf-8"))
    all_slider_ids = {
        s["id"]
        for m in snap["mesures"].values()
        for s in m.get("sliders", [])
    }
    assert 45 <= len(all_slider_ids) <= 55, sorted(all_slider_ids)


def test_handler_source_raises_loud_when_unavailable():
    """Un registre source-de-vérité ne doit JAMAIS produire un faux

    `params={}` silencieux : `_handler_source` lève si le code est
    inaccessible (functools.partial -> inspect.getsource TypeError).
    """
    fake = functools.partial(lambda params: None)
    with pytest.raises(RuntimeError, match=r"source du handler '.*' introuvable"):
        _handler_source("levier_factice", fake)


def test_real_registry_satisfies_completeness_invariant(registry):
    """Le registre réel ne doit avoir AUCUNE mesure silencieusement vide."""
    assert_contract_complete(registry)  # ne lève pas


def test_classify_dead_keys_flags_truly_dead():
    m = {"type": "fonction", "parametres": {"vivant": {}, "mort": {}}}
    reg_entry = {"params": {"vivant": {"default": 0}}, "flags": []}
    dead, skip = _classify_dead_keys(m, reg_entry)
    assert dead == ["mort"] and skip is None


def test_classify_dead_keys_abstains_on_uncertain_extraction():
    """Anti auto-renforcement : si l'extracteur est INCERTAIN sur la mesure

    (flag UNMODELED/DYNAMIC), on ne déclare AUCUNE clé morte — sinon une
    clé réelle non vue serait supprimée du JSON = mensonge aggravé."""
    m = {"type": "fonction", "parametres": {"peut_etre_vivant": {}}}
    reg_entry = {"params": {}, "flags": ["UNMODELED_PARAM_ACCESS"]}
    dead, skip = _classify_dead_keys(m, reg_entry)
    assert dead == []
    assert skip is not None and "incertaine" in skip


def test_classify_dead_keys_ignores_formule():
    m = {"type": "formule", "parametres": {"x": {}}}
    dead, skip = _classify_dead_keys(m, {"params": {}, "flags": []})
    assert dead == [] and skip is None


def test_completeness_invariant_rejects_silent_empty_measure():
    """Garde rouge-vert : une mesure sans clé NI flag justificatif → échec dur."""
    bad = {"mesures": {"trou": {"params": {}, "flags": []}}}
    with pytest.raises(RuntimeError, match="registre incomplet"):
        assert_contract_complete(bad)
    # Avec un flag justificatif explicite, l'invariant passe.
    ok = {"mesures": {"trou": {"params": {}, "flags": ["UNMODELED_PARAM_ACCESS"]}}}
    assert_contract_complete(ok)


# Mesures de type "formule" (ASTEVAL, policy_measures.json) : effet RÉEL sur
# le solde mais hors du dict Python `measure_handlers`. Le registre est une
# DOC PUBLIQUE (open source) : ne doit pas laisser croire que defense /
# collectivites / immigration sont des leviers sans effet.
_FORMULE_SLIDERS = (
    "defense_budget",
    "collectivites_dotation",
    "collectivites_investissement",
    "immigration_ame",
    "immigration_integration",
)


# --- _no_handler_entry : 3/4 branches sont défensives (inatteignables sur
# les données actuelles : toutes les mesures sans handler sont type:formule).
# Testées en isolation, sinon une régression de message/clé passerait verte.

def test_no_handler_entry_classifies_formule_and_fonction():
    """Les 2 branches nominales : type:formule → kind=formule (+ASTEVAL dans
    la raison) ; type:fonction sans handler → kind=unwired."""
    s = {"id": "x_slider", "param": "p"}
    jm = {"m_form": {"type": "formule"}, "m_fonc": {"type": "fonction"}}
    f = _no_handler_entry("m_form", s, jm)
    assert f == {
        "id": "x_slider", "measure": "m_form", "param": "p",
        "kind": _KIND_FORMULE, "reason": f["reason"],
    }
    assert "asteval" in f["reason"].lower()
    u = _no_handler_entry("m_fonc", s, jm)
    assert u["kind"] == _KIND_UNWIRED
    assert "sans handler câblé" in u["reason"]


def test_no_handler_entry_raises_on_missing_meta():
    """Mesure-cible absente de policy_measures.json ET sans handler →
    indéterminé : échec dur actionnable (jamais classé en doc publique)."""
    with pytest.raises(RuntimeError, match="policy_measures.json"):
        _no_handler_entry("absente", {"id": "sl", "param": "p"}, {})


def test_no_handler_entry_raises_on_unexpected_type():
    """Type inattendu (ni formule ni fonction) → échec dur, pas de classement
    par défaut muet."""
    jm = {"m": {"type": "forfait"}}
    with pytest.raises(RuntimeError, match="type policy_measures.json inattendu"):
        _no_handler_entry("m", {"id": "sl", "param": "p"}, jm)


def test_render_markdown_separates_formule_and_unwired(registry):
    """Registre SYNTHÉTIQUE (formule + unwired) : les deux sections sont
    rendues, chaque slider dans la sienne, AUCUNE contamination croisée. La
    `reason` est omise pour formule (doublon intro) mais gardée pour unwired
    (discriminante). Exerce le chemin unwired, jamais produit en prod."""
    reg = {
        "mesures": {},
        "sliders_sans_handler": [
            {"id": "s_form", "measure": "mf", "param": "p",
             "kind": _KIND_FORMULE, "reason": "raison-formule-NEVER-SHOWN"},
            {"id": "s_unw", "measure": "mu", "param": "q",
             "kind": _KIND_UNWIRED, "reason": "mesure-cible sans handler câblé"},
        ],
    }
    secs = _md_sections(render_markdown(reg))
    aseval = next(b for t, b in secs.items()
                  if "formule" in t.lower() and "asteval" in t.lower())
    unwired = next(b for t, b in secs.items() if "non rattaché" in t.lower())
    assert "`s_form`" in aseval and "`s_form`" not in unwired
    assert "`s_unw`" in unwired and "`s_unw`" not in aseval
    assert "raison-formule-NEVER-SHOWN" not in aseval  # reason omise (doublon)
    assert "sans handler câblé" in unwired              # reason gardée


def test_render_markdown_raises_on_unknown_kind():
    """Garde anti-omission : un `kind` hors {formule, unwired} dans une doc
    publique → RuntimeError (jamais une disparition silencieuse)."""
    reg = {"mesures": {}, "sliders_sans_handler": [
        {"id": "s", "measure": "m", "param": "p", "kind": "bidon",
         "reason": "x"}]}
    with pytest.raises(RuntimeError, match="kind manquant/inconnu"):
        render_markdown(reg)


def test_every_orphan_has_explicit_kind(registry):
    """Invariant anti-omission UNIQUEMENT : toute entrée porte un `kind` ∈
    {formule, unwired} (jamais absent/inconnu). Ne garantit PAS la JUSTESSE
    du classement — celle-ci est portée par
    `test_formule_sliders_labeled_as_aseval_not_unwired` (ne pas supprimer
    l'un en croyant l'autre suffisant). Accès direct `o["kind"]` aligné sur
    la prod (échec franc si absent), pas `.get` tolérant."""
    for o in registry["sliders_sans_handler"]:
        assert o["kind"] in (_KIND_FORMULE, _KIND_UNWIRED), (
            f"{o['id']}: kind={o.get('kind')!r} — un registre source de "
            "vérité ne laisse aucune entrée non classée"
        )


def test_formule_sliders_labeled_as_aseval_not_unwired(registry):
    """Un slider pilotant une mesure type:formule est étiqueté `kind=formule`
    avec une raison mentionnant explicitement ASTEVAL / effet réel — jamais
    confondu avec un vrai orphelin de câblage."""
    orphans = {o["id"]: o for o in registry["sliders_sans_handler"]}
    for sid in _FORMULE_SLIDERS:
        assert sid in orphans, f"{sid} doit rester listé (jamais omis)"
        assert orphans[sid]["kind"] == _KIND_FORMULE, (
            f"{sid}: kind attendu {_KIND_FORMULE!r}, "
            f"obtenu {orphans[sid]['kind']!r}"
        )
        reason = orphans[sid]["reason"].lower()
        assert "formule" in reason and "asteval" in reason, (
            f"{sid}: reason={orphans[sid]['reason']!r} doit indiquer "
            "explicitement la mesure formule ASTEVAL (effet réel)"
        )


def _md_sections(md: str) -> dict[str, str]:
    """Découpe le Markdown en {titre de section ###: corps} pour asserter le
    PLACEMENT d'un slider, pas une simple présence de chaîne (anti faux-vert
    sur reclassement partiel : un slider formule glissé en 'non rattaché'
    doit faire ROUGIR)."""
    out: dict[str, str] = {}
    current = None
    for line in md.splitlines():
        if line.startswith("### "):
            current = line[4:].strip()
            out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return out


def test_markdown_places_each_formule_slider_in_aseval_section(registry):
    """Le Markdown public ne titre plus `Sliders sans handler câblé` et place
    CHAQUE slider formule dans la section ASTEVAL — et dans AUCUNE section
    'non rattaché' (placement structurel, pas présence globale de mots)."""
    md = render_markdown(registry)
    assert "## Sliders sans handler câblé" not in md, (
        "titre trompeur conservé — un lecteur conclut à tort 'levier inerte'"
    )
    sections = _md_sections(md)
    aseval = next(
        (body for title, body in sections.items()
         if "formule" in title.lower() and "asteval" in title.lower()),
        None,
    )
    assert aseval is not None, "section 'Mesures formule (ASTEVAL)' absente"
    unwired_bodies = [
        body for title, body in sections.items()
        if "non rattaché" in title.lower()
    ]
    for sid in _FORMULE_SLIDERS:
        assert f"`{sid}`" in aseval, (
            f"{sid} absent de la section ASTEVAL (mal classé ?)"
        )
        for body in unwired_bodies:
            assert f"`{sid}`" not in body, (
                f"{sid} (formule, effet réel) listé à tort en 'non "
                "rattaché' — mensonge par omission dans la doc publique"
            )
