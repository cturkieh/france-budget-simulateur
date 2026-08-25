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
import importlib
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

# `.absolute()` et PAS `.resolve()` — MÊME PIÈGE que dans
# `tests/test_scenario_params_sync.py`, et il a coûté aussi cher ici : le repo
# parent (budgetlab-france) monte `tests/` comme SYMLINK vers ce submodule.
# `resolve()` suit le lien et retombe TOUJOURS sur la racine du submodule, où
# `frontend-react/` n'existe pas — ce qui rendait le skipif de
# `test_measure_registry_sync.py` permanent : la garde ne tournait nulle part,
# et le générateur a pu pourrir sans que rien ne rougisse (constaté au lot 7).
# `absolute()` préserve le chemin d'invocation : lancé depuis le parent, le
# script voit le frontend ; lancé depuis un fork moteur seul, il ne le voit pas
# et le dit.
ROOT = Path(__file__).absolute().parents[1]

# Chemins canoniques des artefacts générés (source unique — utilisés par la
# génération ET par --check ET dans le message d'erreur : pas de dérive).
DEFAULT_MD = ROOT / "docs" / "MEASURE_REGISTRY.md"
DEFAULT_JSON = ROOT / "tests" / "snapshots" / "measure_registry.json"

# Sources UI canoniques des sliders (niveau 3 du registre : sliders -> mesures
# -> handlers). Le mapping slider->mesure->param est DÉRIVÉ de l'existant,
# jamais inventé :
#   - `ALL_VARIABLES` (simulatorConfig.js) = whitelist des sliders réellement
#     exposés à l'utilisateur ;
#   - `LEVER_META` (leverMeta.js)          = bornes min/max/step ;
#   - `convertToAPIFormat` (apiFormat.js)  = builder RÉEL du payload envoyé au
#     moteur, donc le seul lien slider->mesure->param qui fasse foi.
#
# LES TROIS VIVAIENT DANS `ExploreCreateSection.jsx` jusqu'au découpage du
# composant : `variablesConfig` y est devenu `LEVER_META`, `allVariables` y est
# devenu `ALL_VARIABLES`, et `convertToAPIFormat` a migré dans `utils/`.
# L'extracteur, lui, a continué de chercher les anciens blocs dans l'ancien
# fichier : il levait RuntimeError à chaque exécution — sans que personne le
# voie, la garde CI étant neutralisée par le piège de symlink ci-dessus.
# C'est le mode de défaillance que ce lot ferme des DEUX côtés (extraction
# réparée ET garde remise en service, cf. `make check-docs-sync`).
#: Chemins RELATIFS des trois sources, sous la racine du frontend.
_FRONT_RELATIFS = (
    ("sim_config", Path("src") / "data" / "simulatorConfig.js"),
    ("lever_meta", Path("src") / "data" / "leverMeta.js"),
    ("api_format", Path("src") / "utils" / "apiFormat.js"),
)


def _racines_frontend_candidates() -> tuple[Path, ...]:
    """Où chercher `frontend-react/`, dans l'ordre.

    DEUX candidates, parce que ce script vit dans un submodule PUBLIC intégré
    par un repo privé — et que `resolve()` sur un symlink fait basculer d'une
    racine à l'autre sans prévenir (le piège documenté sur ROOT). Plutôt que
    d'exiger de chaque appelant qu'il évite le piège, on rend la résolution
    robuste aux deux :

    1. ``<ROOT>/frontend-react``            — invocation depuis le repo parent ;
    2. ``<ROOT>/../../frontend-react``      — ROOT tombé sur la racine du
       submodule (``<parent>/vendor/france-budget-simulateur``), cas d'un
       import du module par un test qui a `resolve()` un chemin symlinké.

    Aucune des deux n'existe sur un fork moteur seul : le niveau « sliders »
    est alors déclaré indisponible, bruyamment (jamais silencieusement vide).
    """
    candidates = [ROOT / "frontend-react"]
    if len(ROOT.parents) >= 2:
        candidates.append(ROOT.parents[1] / "frontend-react")
    return tuple(candidates)


def _sources_front() -> dict[str, Path]:
    """``{clé: chemin}`` sous la première racine candidate complète.

    Retourne les chemins sous la PREMIÈRE candidate si aucune n'est complète :
    le message d'erreur de ``_read_front_sources`` reste ainsi actionnable
    (il nomme un chemin réel, pas un dict vide)."""
    for racine in _racines_frontend_candidates():
        chemins = {cle: racine / rel for cle, rel in _FRONT_RELATIFS}
        if all(p.exists() for p in chemins.values()):
            return chemins
    racine = _racines_frontend_candidates()[0]
    return {cle: racine / rel for cle, rel in _FRONT_RELATIFS}


def front_disponible() -> bool:
    """Le niveau « sliders » est-il constructible ici ?

    SOURCE UNIQUE de la condition de skip des tests du registre : dupliquer
    les chemins côté tests, c'est exactement ainsi qu'on se retrouve avec une
    garde qui skippe pour une raison qui n'est plus vraie."""
    return all(p.exists() for p in _sources_front().values())

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

# Helpers de LECTURE : ils reçoivent `params` nu et lisent eux-mêmes des clés
# littérales, hors du corps du handler. Les whitelister ne suffit PAS — cela
# ferait taire le signal `<UNMODELED>` tout en perdant les clés qu'ils lisent,
# c'est-à-dire en remplaçant un registre bruyamment incomplet par un registre
# silencieusement faux. L'extracteur SUIT donc leur source avec les mêmes
# règles, et fusionne le résultat : le contrat reste DÉRIVÉ du code, jamais
# ré-énoncé à la main.
#
# Pourquoi ils existent : le canal d'âge des retraites a une source unique
# (`budget_simulator/_seniors`) que consomment les quatre canaux d'une mesure
# d'âge PLUS le garde Gini. `age_depart` n'est donc plus lu nulle part dans le
# corps du handler — sans ce suivi, la clé la plus visible du simulateur
# disparaîtrait du registre public.
_PARAMS_READING_HELPERS = {
    "retraites_ecart_age_ans": "budget_simulator._seniors",
    "retraites_annee_debut_ecart_age_handler": "budget_simulator._seniors",
}

#: Profondeur maximale de suivi (garde anti-cycle ET anti-explosion : au-delà,
#: un contrat devient illisible pour un auditeur, ce qui est le contraire du
#: but). `retraites_annee_debut_ecart_age_handler` → lambda →
#: `retraites_ecart_age_ans` fait deux niveaux.
_PROFONDEUR_MAX_HELPERS = 4


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


def _helper_source(nom: str) -> str:
    """Source d'un helper de lecture whitelisté, ou **lève**.

    Même contrat anti-silence que ``_handler_source`` : si la source d'un
    helper suivi devient inaccessible, le registre perdrait ses clés sans
    prévenir — exactement le « doc qui ment » que cet outil combat."""
    module_name = _PARAMS_READING_HELPERS[nom]
    try:
        module = importlib.import_module(module_name)
        return inspect.getsource(getattr(module, nom))
    except (ImportError, AttributeError, OSError, TypeError) as e:
        raise RuntimeError(
            f"source du helper de lecture '{nom}' ({module_name}) "
            f"introuvable ({type(e).__name__}: {e}) — le registre ne peut pas "
            "être silencieusement incomplet : corriger le helper, ou le "
            "retirer de _PARAMS_READING_HELPERS"
        ) from e


def _fusionner_contrats(out: dict, sous_contrat: dict) -> None:
    """Fusionne le contrat d'un helper suivi dans celui de son appelant.

    CONSERVATRICE : ce que l'appelant a déjà établi prime (il est plus proche
    du contrat réel), et les listes d'accès non modélisés se CONCATÈNENT —
    perdre un signal `<DYNAMIC>`/`<UNMODELED>` en fusionnant serait la
    dernière chose à faire dans un outil dont tout l'intérêt est de ne rien
    taire."""
    for cle, valeur in sous_contrat.items():
        if cle in (_DYNAMIC, _UNMODELED):
            out.setdefault(cle, {"raw": []})["raw"].extend(valeur["raw"])
            continue
        slot = out.setdefault(cle, {})
        for attribut, v in valeur.items():
            slot.setdefault(attribut, v)


def extract_params_from_source(src: str, func_name: str | None = None,
                               _profondeur: int = 0) -> dict:
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
                            # Défaut NON littéral mais bien présent (une
                            # constante nommée, un appel) : on publie son
                            # EXPRESSION. Rendre `None` laisserait croire
                            # qu'il n'y a pas de défaut du tout, alors que
                            # les défauts du moteur migrent justement vers
                            # des constantes nommées — un registre public ne
                            # doit pas régresser en lisibilité à mesure que
                            # le code gagne en traçabilité.
                            if dft is _NON_LITERAL and len(node.args) > 1:
                                _slot(key)["default_expr"] = ast.unparse(
                                    node.args[1])
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
                    recoit_params = any(
                        self._is_param_name(arg)
                        for arg in (*node.args,
                                    *(k.value for k in node.keywords))
                    )
                    if not recoit_params:
                        pass
                    elif fname in _PARAMS_READING_HELPERS:
                        # Helper de LECTURE : on suit sa source plutôt que de
                        # se taire (cf. _PARAMS_READING_HELPERS).
                        if _profondeur >= _PROFONDEUR_MAX_HELPERS:
                            raise RuntimeError(
                                f"suivi des helpers de lecture au-delà de "
                                f"{_PROFONDEUR_MAX_HELPERS} niveaux sur "
                                f"'{fname}' : cycle probable, ou contrat "
                                "devenu illisible — à plat plutôt qu'à "
                                "profondeur"
                            )
                        _fusionner_contrats(out, extract_params_from_source(
                            _helper_source(fname),
                            _profondeur=_profondeur + 1))
                    elif fname not in _PARAMS_FORWARDING_WHITELIST:
                        _add_dynamic(_UNMODELED, node)
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


def _read_front_sources() -> dict[str, str]:
    """Les trois sources UI, ou erreur ACTIONNABLE (jamais une stacktrace
    brute) — même philosophie anti-silence que ``_handler_source``."""
    sources = {}
    for cle, chemin in _sources_front().items():
        try:
            sources[cle] = chemin.read_text("utf-8")
        except OSError as e:
            raise RuntimeError(
                f"source front introuvable ({type(e).__name__}: {e}) : "
                f"{chemin} — le niveau 'sliders' du registre ne peut pas être "
                f"silencieusement vide. Racines cherchées : "
                f"{[str(r) for r in _racines_frontend_candidates()]}"
            ) from e
    return sources


#: Commentaires de ligne JS. Retirés AVANT toute extraction de chaînes : les
#: listes de sliders sont ponctuées de `// === SECTION … ===`, et un jour l'un
#: d'eux portera une apostrophe qui casserait le comptage des quotes.
_COMMENTAIRE_JS = re.compile(r"//[^\n]*")


def _bloc_js(src: str, entete: str, fermeture: str, quoi: str) -> str:
    """Corps d'un bloc JS délimité par son en-tête et sa ligne de fermeture.

    Refuse de deviner : un bloc introuvable LÈVE. C'est précisément ce que
    faisait l'ancienne version — et ce qui, en soi, était juste : le défaut
    n'était pas l'échec, c'était que personne ne le voyait (garde CI
    neutralisée par le piège de symlink)."""
    m = re.search(re.escape(entete) + r"(.*?)\n" + re.escape(fermeture),
                  src, re.S)
    if not m:
        raise RuntimeError(
            f"bloc `{quoi}` introuvable dans le front (en-tête attendu : "
            f"{entete!r}) : structure inattendue — refuser de deviner "
            "(le registre est une source de vérité publique)"
        )
    return m.group(1)


def _entrees_indentees(bloc: str, indentation: int) -> dict[str, str]:
    """``{clé: corps}`` des entrées d'objet JS à une indentation donnée.

    Découpage par ACCOLADE FERMANTE À LA MÊME INDENTATION, seul délimiteur
    fiable ici : les corps contiennent des accolades (littéraux de gabarit
    ``${…}``, fonctions fléchées ``format``) qui interdisent un comptage naïf.
    """
    marge = " " * indentation
    motif = re.compile(
        rf"^{marge}([A-Za-z0-9_]+):\s*\{{(.*?)^{marge}\}}",
        re.S | re.M,
    )
    return {m.group(1): m.group(2) for m in motif.finditer(bloc)}


def extract_slider_contract(sources: dict) -> tuple[dict, list[dict]]:
    """Niveau 3 du registre : sliders UI -> (mesure, param) + bornes.

    DÉRIVE le mapping de l'existant (aucune invention), depuis les TROIS
    fichiers front qui portent aujourd'hui la configuration du simulateur :

    - ``ALL_VARIABLES`` (``src/data/simulatorConfig.js``) : whitelist des
      sliders réellement exposés à l'utilisateur ;
    - ``LEVER_META`` (``src/data/leverMeta.js``) : ``{slider_id: {min, max,
      step, …}}``, les bornes ;
    - ``convertToAPIFormat`` (``src/utils/apiFormat.js``) : builder
      AUTORITATIF du payload moteur, de forme ``payload[<mesure>][<param>] =
      measures.<slider_id>`` — c'est LE lien slider->mesure->param réellement
      consommé par les handlers.

    Les trois vivaient dans ``ExploreCreateSection.jsx`` avant le découpage du
    composant ; l'extracteur les y cherchait encore. Cf. le commentaire des
    constantes ``_FRONT_*`` pour le mode de défaillance complet.

    Retour ``(by_measure, orphans)`` où ``by_measure[mid]`` est la liste
    triée des sliders ``{id, min, max, step, param}`` alimentant la mesure
    ``mid``, et ``orphans`` la liste des sliders dont la mesure-cible n'a
    PAS de handler câblé (signalé, jamais omis silencieusement).

    Parsing par regex ciblée sur des structures régulières : déterministe,
    aucune exécution JS (convention test projet, cf. docstring module).
    """
    # --- 1. Whitelist des sliders exposés (simulatorConfig.js) -------------
    liste = _bloc_js(sources["sim_config"], "export const ALL_VARIABLES = [",
                     "]", "ALL_VARIABLES")
    whitelist = re.findall(r"'([A-Za-z0-9_]+)'",
                           _COMMENTAIRE_JS.sub("", liste))

    # --- 2. Bornes (leverMeta.js) -----------------------------------------
    # `min`/`max`/`step` sont cherchés SÉPARÉMENT, et non sur une ligne
    # unique : les entrées récentes (asu_activation, asu_plafonnement) les
    # écrivent une par ligne. L'ancienne regex « les trois sur une ligne »
    # les aurait silencieusement rangés en orphelins « bornes absentes ».
    bounds: dict[str, dict] = {}
    meta = _bloc_js(sources["lever_meta"], "export const LEVER_META = {",
                    "  }", "LEVER_META")
    for sid, corps in _entrees_indentees(meta, 4).items():
        valeurs = {}
        for borne in ("min", "max", "step"):
            m = re.search(rf"(?:^|[\s,{{]){borne}:\s*(-?[\d.]+)", corps)
            if m:
                valeurs[borne] = _num(m.group(1))
        if len(valeurs) == 3:
            bounds[sid] = valeurs

    # --- 3. Mapping slider -> (mesure, param) (apiFormat.js) --------------
    api = _bloc_js(sources["api_format"],
                   "export function convertToAPIFormat(measures) {",
                   "  return payload", "convertToAPIFormat")
    slider_map: dict[str, tuple[str, str]] = {}
    for mid, corps in _entrees_indentees(api, 4).items():
        for pm in re.finditer(
            r"([A-Za-z0-9_]+):\s*measures\.([A-Za-z0-9_]+)", corps
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
                f"pour slider '{sid}' (whitelisté mais LEVER_META non parsé)",
                file=sys.stderr,
            )
            orphans.append(
                {"id": sid, "measure": mid, "param": param,
                 "kind": _KIND_UNWIRED,
                 "reason": "bornes absentes de LEVER_META"}
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
        _read_front_sources()
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
            if "default_expr" in v:
                attrs.append(f"défaut : `{v['default_expr']}` (non littéral)")
            elif "default" in v:
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
                "`convertToAPIFormat` (apiFormat.js) / `LEVER_META` "
                "(leverMeta.js)) :"
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
                "`convertToAPIFormat`, ou sans mesure-cible "
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
