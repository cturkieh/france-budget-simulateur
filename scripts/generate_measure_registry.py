"""Génère LE registre du contrat de paramètres depuis les handlers (AST).

Vérité = lectures du dict utilisateur ``params`` dans le **corps des
méthodes** câblées par ``BudgetSimulatorV45().measure_handlers`` (+ la table
canonique ``constants.INTENSITE_DOMAINS`` pour les leviers à slider unique
d'intensité). Parsing STATIQUE (``ast`` ; aucune exécution, aucun ``eval`` ;
déterministe — convention test projet).

Patterns de lecture modélisés (sur ``params`` ou sur le paramètre d'une
lambda legacy passée à ``_resolve_intensite_or_legacy``) :
``X.get("clé"[, défaut])``, ``X["clé"]`` (requis), ``"clé" in X``.
Tout accès ``params`` NON modélisable en clé littérale
(``.items()``/``.keys()``/``.values()``, ``**params``, indice non
littéral) est signalé BRUYAMMENT (clé ``<UNMODELED>`` + flag), jamais
ignoré : un registre « source de vérité » ne ment pas par omission.

Usage::

    python scripts/generate_measure_registry.py        # (re)génère les 2 artefacts
    python scripts/generate_measure_registry.py --check # CI : exit 1 si drift
"""
from __future__ import annotations

import argparse
import ast
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Chemins canoniques des artefacts générés (source unique — utilisés par la
# génération ET par --check ET dans le message d'erreur : pas de dérive).
DEFAULT_MD = ROOT / "docs" / "MEASURE_REGISTRY.md"
DEFAULT_JSON = ROOT / "tests" / "snapshots" / "measure_registry.json"

# Source UI canonique des sliders (niveau 3 du registre : sliders -> mesures
# -> handlers). Le mapping slider->mesure->param est DÉRIVÉ de l'existant,
# jamais inventé : `convertToAPIFormat` est le builder réel du payload envoyé
# au moteur, `variablesConfig` porte les bornes min/max/step, `allVariables`
# est la whitelist des sliders réellement exposés à l'utilisateur.
_FRONT_JSX = ROOT / "frontend-react" / "src" / "components" / "ExploreCreateSection.jsx"

# Exécuté en script (`python scripts/...`) la racine projet n'est pas sur
# sys.path : on l'ajoute pour importer budget_simulator (idempotent).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_DYNAMIC = "<DYNAMIC>"
_UNMODELED = "<UNMODELED>"
# `kind` d'un slider hors `measure_handlers` : formule ASTEVAL (effet réel
# sur le solde) vs réellement non rattaché. Contrat partagé script↔test.
_KIND_FORMULE = "formule"
_KIND_UNWIRED = "unwired"
# Flags qui justifient explicitement qu'une mesure n'expose aucune clé
# littérale (sinon = registre silencieusement incomplet → échec dur).
_JUSTIFY_NO_PARAM = {"INTENSITE_DRIVEN", "DYNAMIC_KEY", "UNMODELED_PARAM_ACCESS"}

_NON_LITERAL = object()


def _const(node: ast.AST):
    """Valeur d'un littéral constant (str/num/bool/None), sinon sentinelle.

    Lecture directe de ``ast.Constant`` — jamais d'``eval`` (déterminisme +
    aucune exécution de code arbitraire, cf. docstring module)."""
    if isinstance(node, ast.Constant):
        return node.value
    return _NON_LITERAL


# Helpers dont le 1er argument positionnel reçoit le dict `params` nu et le
# relaie à une lambda inline suivie par l'extracteur (alias legacy). Tout
# AUTRE appel recevant `params` nu = accès non modélisé → signalé bruyant.
_PARAMS_FORWARDING_WHITELIST = {"_resolve_intensite_or_legacy"}


def _lambda_arg_names(node: ast.Lambda) -> set[str]:
    """Tous les noms de paramètres d'UNE lambda (positionnels, pos-only,
    kw-only, *args, **kwargs) — exhaustif pour ne pas rater un alias legacy.

    Les handlers délèguent la lecture legacy via
    ``_resolve_intensite_or_legacy(params, simplified, lambda p: p.get(...))``
    : ``p`` est un alias de ``params`` qu'il faut suivre, mais UNIQUEMENT
    dans la portée de la lambda (sinon faux positif : une variable locale
    homonyme hors lambda créerait une fausse clé de contrat)."""
    a = node.args
    names = {arg.arg for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def extract_params_from_source(src: str, func_name: str | None = None) -> dict:
    """Extrait le contrat de paramètres lu dans ``src``.

    Retour : ``{clé: {...}}`` où la valeur porte ``default`` (lecture
    ``.get``) et/ou ``required: True`` (indice ``X["clé"]``, KeyError si
    absent). Clés non littérales -> ``{_DYNAMIC: {"raw": [...]}}``. Accès
    ``params`` non modélisable -> ``{_UNMODELED: {"raw": [...]}}`` (jamais
    silencieux). ``func_name`` restreint à une fonction (API de test).

    ``src`` est dédenté (``textwrap.dedent``) pour accepter le source d'une
    méthode extrait par ``inspect.getsource`` (indenté sous sa classe).
    """
    tree = ast.parse(textwrap.dedent(src))
    out: dict = {}

    def _slot(key: str) -> dict:
        return out.setdefault(key, {})

    def _add_dynamic(bucket: str, expr: ast.AST) -> None:
        out.setdefault(bucket, {"raw": []})["raw"].append(ast.unparse(expr))

    class V(ast.NodeVisitor):
        def __init__(self):
            self.scope_ok = func_name is None
            # Pile des noms assimilés au dict utilisateur : `params` partout +
            # les args d'une lambda UNIQUEMENT dans sa portée (push/pop). Pas
            # de set global → pas de faux positif sur une variable locale
            # homonyme hors lambda. Receveur Name nu uniquement → jamais de
            # confusion avec `self.base_params[...]` (receveur Attribute).
            self._param_scopes: list[set[str]] = [{"params"}]

        def _is_param_name(self, node: ast.AST) -> bool:
            return isinstance(node, ast.Name) and any(
                node.id in s for s in self._param_scopes
            )

        def visit_FunctionDef(self, node):
            prev = self.scope_ok
            if func_name is not None:
                self.scope_ok = node.name == func_name
            self.generic_visit(node)
            self.scope_ok = prev

        visit_AsyncFunctionDef = visit_FunctionDef  # même filtre de scope

        def visit_Lambda(self, node):
            self._param_scopes.append(_lambda_arg_names(node))
            self.generic_visit(node)
            self._param_scopes.pop()

        def visit_Call(self, node):
            f = node.func
            if self.scope_ok:
                if isinstance(f, ast.Attribute) and self._is_param_name(
                    f.value
                ):
                    if f.attr == "get" and node.args:
                        key = _const(node.args[0])
                        if key is _NON_LITERAL:
                            _add_dynamic(_DYNAMIC, node.args[0])
                        else:
                            dft = (
                                _const(node.args[1])
                                if len(node.args) > 1
                                else _NON_LITERAL
                            )
                            _slot(key)["default"] = (
                                None if dft is _NON_LITERAL else dft
                            )
                    elif f.attr in ("items", "keys", "values"):
                        # Itération générique : clés non énumérables.
                        _add_dynamic(_UNMODELED, node)
                else:
                    # `params` nu passé à un appel non whitelisté = lecture
                    # potentielle hors de notre vue → signalé BRUYANT, jamais
                    # une omission silencieuse.
                    fname = (
                        f.id if isinstance(f, ast.Name)
                        else f.attr if isinstance(f, ast.Attribute)
                        else None
                    )
                    if fname not in _PARAMS_FORWARDING_WHITELIST:
                        for arg in (*node.args, *(k.value for k in node.keywords)):
                            if self._is_param_name(arg):
                                _add_dynamic(_UNMODELED, node)
                                break
            self.generic_visit(node)

        def visit_Subscript(self, node):
            if self.scope_ok and self._is_param_name(node.value):
                key = _const(node.slice)
                if key is _NON_LITERAL:
                    _add_dynamic(_UNMODELED, node)
                else:
                    # X["clé"] lève KeyError si absent → paramètre requis.
                    _slot(key)["required"] = True
            self.generic_visit(node)

        def visit_Compare(self, node):
            # "clé" in params / not in params : présence testée (optionnel).
            if (
                self.scope_ok
                and len(node.ops) == 1
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and self._is_param_name(node.comparators[0])
            ):
                key = _const(node.left)
                if key is _NON_LITERAL:
                    _add_dynamic(_UNMODELED, node)
                else:
                    _slot(key).setdefault("presence_checked", True)
            self.generic_visit(node)

    V().visit(tree)
    return out


def _handler_source(mid: str, fn) -> str:
    """Source d'un handler, ou **lève** si introuvable.

    Un registre « source de vérité » ne doit JAMAIS produire silencieusement
    ``params={}`` pour un handler dont le code est inaccessible (``partial``,
    lambda, builtin C, fichier déplacé) : ce serait exactement le « doc qui
    ment » que cet outil combat. Échec bruyant obligatoire."""
    try:
        return inspect.getsource(fn)
    except (OSError, TypeError) as e:
        raise RuntimeError(
            f"source du handler '{mid}' introuvable ({type(e).__name__}) : "
            "le registre est la source de vérité, il ne peut pas être "
            "silencieusement incomplet — corriger le handler ou l'extracteur"
        ) from e


def _iter_handler_funcs():
    """``(measure_id, source_de_la_méthode_handler)`` pour chaque mesure câblée.

    Mapping mesure->méthode lu via ``BudgetSimulatorV45().measure_handlers``
    (``simulator.py``). Source extrait par ``inspect.getsource`` (lecture
    seule — aucune exécution du calcul moteur)."""
    from budget_simulator import BudgetSimulatorV45

    sim = BudgetSimulatorV45()
    for mid, fn in sim.measure_handlers.items():
        yield mid, _handler_source(mid, fn)


def _intensite_domains() -> dict:
    """``constants.INTENSITE_DOMAINS`` — source machine canonique (Lot C
    Item 1) des leviers pilotés par un slider d'intensité unique et de leur
    domaine ``[min, max]``. C'est le VRAI contrat UI de ces leviers (le
    ``params.get('intensite')`` réel vit dans
    ``_phasing._resolve_intensite_or_legacy``, hors corps du handler)."""
    from budget_simulator.constants import INTENSITE_DOMAINS

    return INTENSITE_DOMAINS


def _load_policy_cfg() -> dict:
    """``policy_measures.json`` parsé, ou erreur ACTIONNABLE (pas une
    stacktrace brute). Source partagée par ``_load_json_meta`` et
    ``rewrite_json_parametres`` (DRY + gestion d'erreur cohérente)."""
    path = ROOT / "policy_measures.json"
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"policy_measures.json illisible ({type(e).__name__}: {e})"
        ) from e


def _load_json_meta() -> dict:
    """Métadonnées (nom/catégorie/type) indexées par ``id``.

    Ces métadonnées ne sont pas le contrat (le code l'est) mais leur
    indisponibilité doit être explicite, pas silencieuse."""
    cfg = _load_policy_cfg()
    # Validation de structure HORS lecture I/O : un KeyError/TypeError ici
    # est un vrai défaut de structure, pas un fichier illisible — diagnostic
    # exact, jamais menteur sur la cause (cf. CLAUDE.md error-handling).
    try:
        return {m["id"]: m for m in cfg["mesures"]}
    except (KeyError, TypeError) as e:
        raise RuntimeError(
            f"policy_measures.json structure invalide "
            f"({type(e).__name__}: {e}) — clé 'mesures'/'id' attendue"
        ) from e


def _flags(mid: str, params: dict, *, intensite_driven: bool) -> list[str]:
    """Drapeaux non comportementaux (documentation/audit) du registre.

    ``intensite_driven`` est calculé par l'appelant (qui a déjà la table
    des domaines en main) — pas de ré-interrogation de la constante."""
    f = []
    if _DYNAMIC in params:
        f.append("DYNAMIC_KEY")
    if _UNMODELED in params:
        f.append("UNMODELED_PARAM_ACCESS")
    if intensite_driven:
        f.append("INTENSITE_DRIVEN")
    if mid in ("fraude_fiscale", "fraude_sociale"):
        # cf. spec D4 : effort = intensité 0-1 (UI) OU Md€ bruts (>1, legacy
        # scénarios/API). Documenté tel quel, AUCUN changement de calcul.
        f.append("KNOWN_SEMANTIC_EFFORT_BIMODAL")
    if mid == "asu":
        # Vérifié-vivant : lu par depenses._apply_asu (cf. config.py défauts
        # 'asu'). Pas de n° de ligne figé (pourrirait au 1er edit).
        f.append("VERIFIED_ALIVE_config_asu_defaults")
    return f


def _num(s: str):
    """Littéral numérique JS -> int si entier exact, sinon float (rendu Markdown
    propre : ``0`` et non ``0.0``). Déterministe, aucune exécution JS."""
    f = float(s)
    return int(f) if f.is_integer() else f


def _read_front_jsx() -> str:
    """Source du composant front, ou erreur ACTIONNABLE (jamais une
    stacktrace brute) — même philosophie anti-silence que ``_handler_source``.
    """
    try:
        return _FRONT_JSX.read_text("utf-8")
    except OSError as e:
        raise RuntimeError(
            f"source front introuvable ({type(e).__name__}: {e}) : "
            f"{_FRONT_JSX.relative_to(ROOT)} — le niveau 'sliders' du registre "
            "ne peut pas être silencieusement vide"
        ) from e


def extract_slider_contract(src: str) -> tuple[dict, list[dict]]:
    """Niveau 3 du registre : sliders UI -> (mesure, param) + bornes.

    DÉRIVE le mapping de l'existant (aucune invention) :

    - ``allVariables`` : whitelist des sliders réellement exposés à l'UI.
    - ``variablesConfig`` : ``{slider_id: {min, max, step, ...}}`` (bornes).
    - ``convertToAPIFormat`` : builder AUTORITATIF du payload moteur, de
      forme ``payload[<mesure>][<param>] = measures.<slider_id>`` — c'est
      LE lien slider->mesure->param réellement consommé par les handlers.

    Retour ``(by_measure, orphans)`` où ``by_measure[mid]`` est la liste
    triée des sliders ``{id, min, max, step, param}`` alimentant la mesure
    ``mid``, et ``orphans`` la liste des sliders dont la mesure-cible n'a
    PAS de handler câblé (signalé, jamais omis silencieusement).

    Parsing par regex ciblée sur des structures régulières (id/min/max/step
    sur une ligne, ``param: measures.slider_id``) : déterministe, aucune
    exécution JS (convention test projet, cf. docstring module).
    """
    m = re.search(r"const allVariables = \[(.*?)\n  \]", src, re.S)
    if not m:
        raise RuntimeError(
            "bloc `allVariables` introuvable dans le front : structure "
            "inattendue — refuser de deviner (registre source de vérité)"
        )
    whitelist = re.findall(r"'([A-Za-z0-9_]+)'", m.group(1))

    # Capture bornée : on s'arrête au délimiteur de fin de l'objet
    # `variablesConfig` — la ligne `\n  }\n` (accolade indentée 2 espaces qui
    # clôt l'objet ; les entrées sont indentées 4 espaces). Empêche le débord
    # sur le reste du fichier (visibleVars, categories, JSX…).
    cfg = re.search(r"const variablesConfig = \{(.*?)\n  \}\n", src, re.S)
    if not cfg:
        raise RuntimeError("bloc `variablesConfig` introuvable dans le front")
    bounds: dict[str, dict] = {}
    for e in re.finditer(
        r"(?:^|\n)\s{4}([A-Za-z0-9_]+):\s*\{(.*?)\n\s{4}\}", cfg.group(1), re.S
    ):
        bm = re.search(
            r"min:\s*(-?[\d.]+),\s*max:\s*(-?[\d.]+),\s*step:\s*(-?[\d.]+)",
            e.group(2),
        )
        if bm:
            bounds[e.group(1)] = {
                "min": _num(bm.group(1)),
                "max": _num(bm.group(2)),
                "step": _num(bm.group(3)),
            }

    api = re.search(
        r"function convertToAPIFormat\(measures\)\s*\{(.*?)\n    return payload",
        src,
        re.S,
    )
    if not api:
        raise RuntimeError(
            "fonction `convertToAPIFormat` introuvable : mapping "
            "slider->mesure indérivable — refuser de deviner"
        )
    slider_map: dict[str, tuple[str, str]] = {}
    for blk in re.finditer(
        r"(?:^|\n)      ([A-Za-z0-9_]+):\s*\{(.*?)\n      \}", api.group(1), re.S
    ):
        mid = blk.group(1)
        for pm in re.finditer(
            r"([A-Za-z0-9_]+):\s*measures\.([A-Za-z0-9_]+)", blk.group(2)
        ):
            slider_map[pm.group(2)] = (mid, pm.group(1))

    by_measure: dict[str, list[dict]] = {}
    orphans: list[dict] = []
    for sid in whitelist:
        if sid not in slider_map:
            # Slider exposé mais absent du payload : lien indérivable -> on
            # le signale (jamais une omission silencieuse).
            orphans.append(
                {"id": sid, "kind": _KIND_UNWIRED,
                 "reason": "absent de convertToAPIFormat"}
            )
            continue
        mid, param = slider_map[sid]
        b = bounds.get(sid)
        if b is None:
            # Whitelisté + mappé mais bornes non parsées : dérive silencieuse
            # potentielle si on n'émet aucun signal à la génération.
            print(
                f"[generate_measure_registry] WARNING: bornes introuvables "
                f"pour slider '{sid}' (whitelisté mais variablesConfig non parsé)",
                file=sys.stderr,
            )
            orphans.append(
                {"id": sid, "measure": mid, "param": param,
                 "kind": _KIND_UNWIRED,
                 "reason": "bornes absentes de variablesConfig"}
            )
            continue
        by_measure.setdefault(mid, []).append(
            {"id": sid, "min": b["min"], "max": b["max"],
             "step": b["step"], "param": param}
        )
    for lst in by_measure.values():
        lst.sort(key=lambda s: s["id"])
    return by_measure, orphans


def _no_handler_entry(mid: str, s: dict, json_meta: dict) -> dict:
    """Entrée `sliders_sans_handler` pour un slider dont la mesure-cible n'a
    PAS de handler Python. Classement EXPLICITE par le `type` de
    policy_measures.json (le registre est doc publique : jamais de classement
    par défaut muet — cf. <UNMODELED>) :

    - type "formule" (ASTEVAL)        → EFFET RÉEL sur le solde : kind=formule
    - type "fonction" sans handler    → réellement non rattaché : kind=unwired
    - méta absente / type inattendu   → INDÉTERMINÉ : RuntimeError actionnable
      (même philosophie que assert_contract_complete : pas d'`else` fourre-tout
      qui présenterait un levier à effet réel comme orphelin de câblage).

    Module-level (pas une closure) pour être testable en isolation : les
    branches d'échec dur sont défensives (inatteignables sur les données
    actuelles) — sans test direct, une régression de message/clé passerait
    verte. `json_meta` injecté (pas de capture implicite)."""
    base = {"id": s["id"], "measure": mid, "param": s["param"]}
    meta = json_meta.get(mid)
    if meta is None:
        raise RuntimeError(
            f"slider {s['id']} → mesure {mid!r} : ni handler Python ni "
            "entrée policy_measures.json — classement formule/non-rattaché "
            "impossible (jamais d'omission silencieuse)"
        )
    mtype = meta.get("type")
    if mtype == "formule":
        return {**base, "kind": _KIND_FORMULE,
                "reason": "mesure formule ASTEVAL — effet réel sur le solde "
                          "(policy_measures.json), hors measure_handlers "
                          "Python"}
    if mtype == "fonction":
        return {**base, "kind": _KIND_UNWIRED,
                "reason": "mesure-cible sans handler câblé"}
    raise RuntimeError(
        f"slider {s['id']} → mesure {mid!r} : type policy_measures.json "
        f"inattendu {mtype!r} — classement formule/non-rattaché indéterminé "
        "(étendre le classement explicitement)"
    )


def build_registry() -> dict:
    """Registre canonique : ``mesures -> {params, type, categorie, nom, flags}``.

    La vérité est le code des handlers. ``policy_measures.json`` ne fournit
    QUE les métadonnées (nom/catégorie/type) — jamais le contrat.
    """
    json_meta = _load_json_meta()
    domains = _intensite_domains()
    sliders_by_measure, slider_orphans = extract_slider_contract(
        _read_front_jsx()
    )
    mesures: dict = {}
    for mid, src in _iter_handler_funcs():
        params = extract_params_from_source(src)
        intensite_driven = mid in domains
        if intensite_driven:
            # Vrai contrat UI : slider unique `intensite` + domaine canonique
            # (INTENSITE_DOMAINS). Le params.get('intensite') réel est dans
            # _phasing._resolve_intensite_or_legacy, hors AST par-méthode.
            lo, hi = domains[mid]
            params["intensite"] = {"default": None, "domain": [lo, hi]}
        meta = json_meta.get(mid, {})
        mesures[mid] = {
            "params": params,
            "type": meta.get("type", "fonction"),
            "categorie": meta.get("categorie"),
            "nom": meta.get("nom"),
            "flags": _flags(mid, params, intensite_driven=intensite_driven),
            # Niveau 3 : sliders UI pilotant cette mesure (id + bornes +
            # param ciblé). Liste vide = mesure non pilotée par un slider UI
            # (pilotée par scénario/API uniquement) — explicite, pas absent.
            "sliders": sliders_by_measure.get(mid, []),
        }
    orphan_no_handler = sorted(
        (
            _no_handler_entry(mid, s, json_meta)
            for mid, lst in sliders_by_measure.items()
            if mid not in mesures
            for s in lst
        ),
        key=lambda o: o["id"],
    )
    return {
        "_generated": "scripts/generate_measure_registry.py — NE PAS ÉDITER",
        # Tri load-bearing : render_markdown itère dans l'ordre d'insertion
        # (le sort_keys=True du json.dumps ne déterminise QUE le JSON, pas le
        # Markdown). Ne pas retirer ce sorted() en croyant sort_keys suffit.
        "mesures": dict(sorted(mesures.items())),
        # Sliders sans rattachement possible à une mesure handler :
        # (a) absents de convertToAPIFormat / sans bornes (slider_orphans),
        # (b) mappés vers une mesure SANS handler câblé. Signalé, jamais omis.
        "sliders_sans_handler": sorted(
            slider_orphans + orphan_no_handler, key=lambda o: o["id"]
        ),
    }


def assert_contract_complete(reg: dict) -> None:
    """Invariant de NON-VACUITÉ : aucune mesure silencieusement vide.

    Toute mesure câblée doit exposer ≥1 clé réelle OU porter un flag qui
    justifie explicitement l'absence (intensité / clé dynamique / accès non
    modélisé). Sinon → **échec dur** (même philosophie que
    ``_handler_source``).

    Portée HONNÊTE de la garantie : cet invariant assure qu'aucune mesure
    n'est *totalement* muette. Il NE prouve PAS la complétude exhaustive du
    contrat (une mesure ayant ≥1 clé extraite mais une clé légitime non
    captée par un pattern non encore modélisé passerait). La complétude
    exhaustive repose sur : (1) la couverture des patterns par l'extracteur,
    (2) le signal bruyant ``<UNMODELED>`` sur tout accès non modélisable,
    (3) la garde de drift ``--check``. Les trois ensemble, pas cet
    invariant seul."""
    offenders = []
    for mid, m in reg["mesures"].items():
        real_keys = [
            k for k in m["params"] if k not in (_DYNAMIC, _UNMODELED)
        ]
        justified = _JUSTIFY_NO_PARAM.intersection(m["flags"])
        if not real_keys and not justified:
            offenders.append(mid)
    if offenders:
        raise RuntimeError(
            "registre incomplet (mesures sans contrat ni flag justificatif) : "
            + ", ".join(sorted(offenders))
            + " — extracteur à étendre ou flag explicite à ajouter"
        )


# Flags qui signalent une extraction INCERTAINE pour la mesure : on ne peut
# alors PAS déclarer une clé JSON « morte » avec certitude → on s'abstient
# (anti-boucle d'auto-renforcement extracteur↔rewrite).
_UNCERTAIN_EXTRACTION_FLAGS = {"UNMODELED_PARAM_ACCESS", "DYNAMIC_KEY"}


def _classify_dead_keys(measure: dict, reg_entry: dict) -> tuple[list, str | None]:
    """Clés ``parametres`` mortes d'une mesure, OU motif d'abstention.

    Retour ``(dead_keys, skip_reason)``. ``skip_reason`` non nul ⇒ ne rien
    supprimer : l'extracteur admet ne pas tout voir sur cette mesure
    (flag incertain), déclarer une clé « morte » serait un faux positif qui
    AGGRAVERAIT le mensonge en le faisant valider par l'outil anti-mensonge.
    """
    if measure.get("type") != "fonction" or "parametres" not in measure:
        return [], None
    flags = set(reg_entry.get("flags", []))
    uncertain = flags & _UNCERTAIN_EXTRACTION_FLAGS
    if uncertain:
        return [], f"extraction incertaine ({', '.join(sorted(uncertain))})"
    real = {
        k for k in reg_entry.get("params", {})
        if k not in (_DYNAMIC, _UNMODELED)
    }
    return [k for k in measure["parametres"] if k not in real], None


def rewrite_json_parametres() -> dict:
    """Retire de ``policy_measures.json`` les clés ``parametres`` MORTES.

    Pour chaque levier ``type:"fonction"``, supprime les clés du bloc
    ``parametres`` que le handler ne lit pas (absentes du registre = vérité).
    Choix de périmètre VOLONTAIRE (vs plan initial qui ajoutait les clés
    manquantes) : le JSON n'est PAS le contrat (le registre l'est, cf.
    bandeau ``_AVERTISSEMENT_CONTRAT``) — il doit seulement NE PAS MENTIR.
    On ne fabrique aucune métadonnée (min/max) et on préserve byte-identique
    tout le reste : churn ``standalone`` borné aux mesures dont une clé morte
    pilotait le mini-scénario. ``type:"formule"`` (ASTEVAL) INCHANGÉS.

    Sécurité : ``assert_contract_complete`` AVANT toute écriture (parité
    ``main``) ; mesures à extraction incertaine PRÉSERVÉES intactes et
    tracées (anti auto-renforcement extracteur↔rewrite).

    Retour ``{"removed": {id: [clés]}, "skipped": {id: motif}}`` (audit)."""
    reg = build_registry()
    assert_contract_complete(reg)  # échec dur AVANT mutation fichier
    cfg = _load_policy_cfg()
    removed: dict = {}
    skipped: dict = {}
    for m in cfg["mesures"]:
        reg_entry = reg["mesures"].get(m["id"], {})
        dead, skip_reason = _classify_dead_keys(m, reg_entry)
        if skip_reason:
            skipped[m["id"]] = skip_reason
            continue
        if dead:
            for k in dead:
                del m["parametres"][k]
            removed[m["id"]] = sorted(dead)
    # Pas de newline final ajouté : le fichier d'origine n'en a pas. Diff
    # minimal auditable = UNIQUEMENT les clés mortes retirées (json.dumps
    # indent=2 reproduit le corps byte-identique : ordre d'insertion
    # préservé par json.loads/dict).
    path = ROOT / "policy_measures.json"
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")
    return {"removed": removed, "skipped": skipped}


def render_markdown(reg: dict) -> str:
    """Rend le registre en Markdown humain (artefact canonique généré)."""
    lines = [
        "# MEASURE_REGISTRY — Contrat de paramètres (GÉNÉRÉ)",
        "",
        "> **NE PAS ÉDITER À LA MAIN.** Généré par "
        "`scripts/generate_measure_registry.py` depuis les lectures du dict "
        "`params` dans le corps des méthodes `measure_handlers`. Toute "
        "édition manuelle sera écrasée et fait échouer la CI "
        "(`tests/test_measure_registry_sync.py`).",
        "",
        "Vérité = corps des méthodes `measure_handlers` + "
        "`constants.INTENSITE_DOMAINS`. Le bloc `parametres` de "
        "`policy_measures.json` n'est PAS le contrat.",
        "",
    ]
    for mid, m in reg["mesures"].items():
        lines.append(f"## `{mid}` — {m.get('nom') or ''}")
        lines.append(
            f"- type : `{m['type']}` · catégorie : `{m.get('categorie')}`"
        )
        if m["flags"]:
            lines.append("- flags : " + ", ".join(f"`{x}`" for x in m["flags"]))
        lines.append("- paramètres lus par le handler :")
        real = {
            k: v for k, v in m["params"].items()
            if k not in (_DYNAMIC, _UNMODELED)
        }
        if not real:
            lines.append("  - _(aucune clé littérale — voir flags)_")
        for k, v in sorted(real.items()):
            attrs = []
            if "domain" in v:
                attrs.append(f"domaine : `{v['domain']}`")
            if v.get("required"):
                attrs.append("**requis** (KeyError si absent)")
            if "default" in v:
                attrs.append(f"défaut : `{v['default']}`")
            suffix = f" ({', '.join(attrs)})" if attrs else ""
            lines.append(f"  - `{k}`{suffix}")
        for bucket, label in (
            (_DYNAMIC, "⚠️ clé(s) dynamique(s)"),
            (_UNMODELED, "⚠️ accès `params` non modélisé"),
        ):
            if bucket in m["params"]:
                raws = ", ".join(f"`{r}`" for r in m["params"][bucket]["raw"])
                lines.append(f"  - {label} : {raws}")
        # Niveau 3 : sliders UI pilotant cette mesure (id, bornes, param
        # ciblé). Absorbe l'info de FONCTIONS_53_SLIDERS /
        # SLIDERS_CONFIGURATION_INTERNE. Liste vide rendue explicitement.
        if m["sliders"]:
            lines.append(
                "- sliders UI (front → moteur, dérivé de "
                "`convertToAPIFormat`/`variablesConfig`) :"
            )
            for s in m["sliders"]:
                lines.append(
                    f"  - `{s['id']}` → param `{s['param']}` "
                    f"[{s['min']}–{s['max']}, pas {s['step']}]"
                )
        else:
            lines.append(
                "- sliders UI : _(aucun — mesure pilotée par "
                "scénario/API uniquement)_"
            )
        lines.append("")
    # Sliders hors handlers Python : (a) mesures formule ASTEVAL = EFFET RÉEL
    # sur le solde, (b) sliders réellement non rattachés. Distingués
    # explicitement (doc publique : ne jamais suggérer « levier sans effet »).
    orphans = reg.get("sliders_sans_handler", [])
    if orphans:
        # Anti-omission (raison d'être de ce fichier) : un `kind` manquant ou
        # non classé disparaîtrait des deux sections d'une DOC PUBLIQUE.
        # Garde AVANT toute partition (sinon `o["kind"]` lèverait un KeyError
        # brut non actionnable) — même philosophie que assert_contract_complete.
        # `key=str` : `None` (kind absent) non comparable aux str sinon.
        unknown = sorted(
            {o.get("kind") for o in orphans} - {_KIND_FORMULE, _KIND_UNWIRED},
            key=str,
        )
        if unknown:
            raise RuntimeError(
                f"sliders_sans_handler : kind manquant/inconnu {unknown} — "
                "classement explicite requis (jamais d'omission silencieuse)"
            )
        formule = [o for o in orphans if o["kind"] == _KIND_FORMULE]
        unwired = [o for o in orphans if o["kind"] == _KIND_UNWIRED]
        lines.append("## Sliders hors handlers Python")
        lines.append("")
        lines.append(
            "Ces sliders ne passent pas par un handler Python de "
            "`measure_handlers`. **Cela ne signifie pas qu'ils sont sans "
            "effet** — voir les deux catégories ci-dessous."
        )
        lines.append("")

        def _emit(o: dict) -> None:
            # reason omise pour le cas formule (identique à l'intro de
            # section → doublon Markdown) ; conservée dans le JSON
            # (consommable seul) et pour unwired (discriminante, actionnable).
            tgt = o.get("measure")
            param = o.get("param")
            where = f" → `{tgt}`.`{param}`" if tgt and param else ""
            suffix = "" if o["kind"] == _KIND_FORMULE else f" — {o['reason']}"
            lines.append(f"- `{o['id']}`{where}{suffix}")

        if formule:
            lines.append(
                "### Mesures formule (ASTEVAL) — effet réel sur le solde"
            )
            lines.append("")
            lines.append(
                "Pilotées par une formule déclarative dans "
                "`policy_measures.json` (évaluée via ASTEVAL, cf. "
                "`orchestrator.py`). Elles **modifient bien dépenses/recettes "
                "et le solde** ; simplement modélisées par formule plutôt "
                "que par un handler Python."
            )
            lines.append("")
            for o in formule:
                _emit(o)
            lines.append("")
        if unwired:
            lines.append("### Sliders non rattachés — à vérifier")
            lines.append("")
            lines.append(
                "Sliders exposés à l'UI mais absents de "
                "`convertToAPIFormat`/`variablesConfig`, ou sans mesure-cible "
                "câblée. Listés pour ne pas mentir par omission."
            )
            lines.append("")
            for o in unwired:
                _emit(o)
            lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    p.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 1 si les artefacts commités divergent du code",
    )
    a = p.parse_args()
    reg = build_registry()
    assert_contract_complete(reg)  # échec dur AVANT toute écriture/diff
    md = render_markdown(reg)
    js = json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=True)
    if a.check:
        drift = [
            str(path)
            for path, content in ((DEFAULT_MD, md), (DEFAULT_JSON, js))
            if not path.exists() or path.read_text("utf-8") != content
        ]
        if drift:
            print("DRIFT registre vs code : " + ", ".join(drift),
                  file=sys.stderr)
            print(
                f"Régénérer : python {Path(__file__).name} "
                f"--out-md {DEFAULT_MD.relative_to(ROOT)} "
                f"--out-json {DEFAULT_JSON.relative_to(ROOT)}",
                file=sys.stderr,
            )
            sys.exit(1)
        print("registre synchro ✓")
        return
    a.out_md.write_text(md, "utf-8")
    a.out_json.write_text(js, "utf-8")
    print(f"registre : {len(reg['mesures'])} mesures")


if __name__ == "__main__":
    main()
