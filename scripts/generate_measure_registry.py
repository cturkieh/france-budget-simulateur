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

Trois artefacts, une seule extraction :

- ``docs/MEASURE_REGISTRY.md`` + ``tests/snapshots/measure_registry.json`` —
  le registre public (paramètres lus + sliders UI, ce dernier niveau exigeant
  les sources du frontend) ;
- ``budget_simulator/engine/_noms_parametres.py`` (v0.6.10, contre-audit
  externe V2-04) — les NOMS de paramètres admis par levier, consommés à
  l'exécution par la porte des noms (``engine/_param_domain.py``). Il ne lit
  pas le frontend : ``--noms`` le génère et le vérifie depuis le dépôt public
  seul.

Usage::

    python scripts/generate_measure_registry.py         # (re)génère les 3 artefacts
    python scripts/generate_measure_registry.py --check # CI : exit 1 si drift
    python scripts/generate_measure_registry.py --noms [--check]  # noms seuls
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
DEFAULT_NOMS = ROOT / "budget_simulator" / "engine" / "_noms_parametres.py"

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


def _contrat_handler(mid: str, src: str, domains: dict) -> dict:
    """Paramètres lus par le handler ``mid`` (extraction AST de ``src``),
    plus ``intensite`` si le levier est piloté par une intensité
    (``INTENSITE_DOMAINS`` : le ``params.get('intensite')`` réel vit dans
    ``_phasing._resolve_intensite_or_legacy``, hors AST par-méthode).

    SOURCE UNIQUE du contrat d'un handler : le registre public
    (``build_registry``) et le module des noms admis (``build_noms_admis``)
    l'appellent tous les deux — ils ne peuvent pas diverger."""
    params = extract_params_from_source(src)
    if mid in domains:
        lo, hi = domains[mid]
        params["intensite"] = {"default": None, "domain": [lo, hi]}
    return params


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
        # Vrai contrat UI des leviers d'INTENSITE_DOMAINS : slider unique
        # `intensite` + domaine canonique (cf. _contrat_handler).
        params = _contrat_handler(mid, src, domains)
        intensite_driven = mid in domains
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


def _noms_formule(mid: str, formule) -> dict:
    """Paramètres lus par une formule ASTEVAL (``policy_measures.json``).

    L'orchestrateur évalue la formule avec ``p`` = le bloc du levier : la
    formule est donc lue comme le corps d'une ``lambda p: …``, que
    l'extracteur suit déjà (alias de ``params`` dans la portée d'une lambda).
    Même extracteur que pour les handlers, aucune règle propre aux formules."""
    if not isinstance(formule, str) or not formule.strip():
        raise RuntimeError(
            f"levier formule {mid!r} : formule absente ou vide dans "
            "policy_measures.json — noms admis indérivables")
    try:
        return extract_params_from_source(f"lambda p: ({formule})")
    except SyntaxError as e:
        raise RuntimeError(
            f"levier formule {mid!r} : formule illisible ({e.msg}) — noms "
            "admis indérivables") from e


def build_noms_admis() -> dict[str, list[str]]:
    """``{levier: [noms de paramètres admis, triés]}`` — le contrat des NOMS
    consommé à l'exécution (porte des noms, contre-audit externe V2-04).

    Même dispatch que ``orchestrator.apply_measures`` : un handler Python
    prime sur la formule ASTEVAL ; à défaut, la formule de
    ``policy_measures.json``. Échec DUR (jamais un levier sans contrat qui
    laisserait tout passer, ni un contrat partiel qui rejetterait un nom
    réellement lu) si :
    - un accès à ``params`` n'est pas modélisable en clé littérale
      (``<DYNAMIC>``/``<UNMODELED>``) : la liste des noms lus serait fausse ;
    - un levier de ``policy_measures.json`` n'a ni handler ni formule.

    Ne lit PAS le frontend : générable et vérifiable depuis le dépôt public
    seul (``--noms``)."""
    domains = _intensite_domains()
    noms: dict[str, list[str]] = {}
    for mid, src in _iter_handler_funcs():
        noms[mid] = _cles_reelles(mid, _contrat_handler(mid, src, domains))
    for m in _load_policy_cfg()["mesures"]:
        mid = m["id"]
        if mid in noms:
            continue
        if m.get("type") != "formule":
            raise RuntimeError(
                f"levier {mid!r} : ni handler Python ni formule ASTEVAL — "
                "noms admis indérivables (l'orchestrateur l'ignorerait)")
        noms[mid] = _cles_reelles(mid, _noms_formule(mid, m.get("formule")))
    return dict(sorted(noms.items()))


def _cles_reelles(mid: str, params: dict) -> list[str]:
    """Clés littérales triées, ou échec dur si l'extraction est incertaine."""
    incertains = sorted(k for k in (_DYNAMIC, _UNMODELED) if k in params)
    if incertains:
        raise RuntimeError(
            f"levier {mid!r} : accès à params non modélisable "
            f"({', '.join(incertains)} : "
            f"{[r for k in incertains for r in params[k]['raw']]}) — la porte "
            "des noms ne peut pas valider ce levier ; rendre la lecture "
            "littérale, ou étendre l'extracteur")
    return sorted(params)


# ---------------------------------------------------------------------------
# Modes EXCLUSIFS (v0.6.10, réfutation de V2-04) : un nom ADMIS peut être
# ignoré quand un autre nom est fourni. La porte des noms laissait passer ces
# clés (elles sont lues… dans l'autre mode), avec HTTP 200 et
# ``report.valid: true``, même en strict. Deux formes dans le code, dérivées
# ici depuis l'AST (jamais une liste tenue à la main) :
#   1. ``_resolve_intensite_or_legacy(params, simplifie, lambda p: …)`` : les
#      clés lues par la lambda HÉRITÉE sont ignorées dès que la clé lue par le
#      résolveur (``intensite``) est fournie ;
#   2. ``if 'k' in params: … else: …`` (instruction ou expression) : les clés
#      lues seulement dans la branche « absent » sont ignorées dès que ``k``
#      est fourni (``not in`` : branches inversées).
# Une clé n'est déclarée ignorée que si elle n'est lue NULLE PART ailleurs
# dans le handler (sinon elle est appliquée dans les deux modes). Tout AUTRE
# test de présence sur ``params`` (``params.get(k) is None``, ``'k' in params``
# dans une condition composée…) est un échec DUR : un mode exclusif non
# modélisé redonnerait le silence que cette porte ferme.

_RESOLVEUR_EXCLUSIF = "_resolve_intensite_or_legacy"


def _cles_litterales(src: str) -> set[str]:
    """Clés littérales lues dans ``src`` (``params`` ou alias de lambda)."""
    return {k for k in extract_params_from_source(src)
            if k not in (_DYNAMIC, _UNMODELED)}


def _cle_dominante_du_resolveur() -> str:
    """La clé dont la présence fait ignorer le mode hérité, lue dans la source
    de ``_phasing._resolve_intensite_or_legacy`` (une seule, sinon échec dur)."""
    from budget_simulator.handlers import _phasing

    cles = _cles_litterales(inspect.getsource(getattr(_phasing, _RESOLVEUR_EXCLUSIF)))
    if len(cles) != 1:
        raise RuntimeError(
            f"{_RESOLVEUR_EXCLUSIF} lit {sorted(cles)} : une seule clé "
            "dominante attendue — étendre la dérivation des modes exclusifs")
    return cles.pop()


def _est_params(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "params"


def _test_de_presence(test: ast.AST) -> tuple[str, bool] | None:
    """``('k', True)`` pour ``'k' in params``, ``('k', False)`` pour
    ``'k' not in params`` ; ``None`` pour tout autre test."""
    if (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.In, ast.NotIn))
            and _est_params(test.comparators[0])
            and isinstance(_const(test.left), str)):
        return _const(test.left), isinstance(test.ops[0], ast.In)
    return None


def _source_de(noeud) -> str:
    """Source d'un nœud expression, ou d'une liste d'instructions."""
    if isinstance(noeud, list):
        return ast.unparse(ast.Module(body=noeud, type_ignores=[]))
    return ast.unparse(noeud)


def modes_exclusifs_du_handler(mid: str, src: str,
                               dominante_resolveur: str) -> dict[str, list[str]]:
    """``{clé dominante: [clés ignorées si elle est fournie]}`` du handler.

    Pour chaque branche « mode écarté » reconnue, les clés qu'elle lit moins
    celles lues ailleurs dans le handler (la branche remplacée par ``None``
    sur une COPIE de l'arbre, puis ré-extraite par le même extracteur)."""
    arbre = ast.parse(textwrap.dedent(src))
    groupes: dict[str, set[str]] = {}
    tests_modelises: set[int] = set()
    for i, n in enumerate(ast.walk(arbre)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == _RESOLVEUR_EXCLUSIF):
            if len(n.args) != 3 or not isinstance(n.args[2], ast.Lambda):
                raise RuntimeError(
                    f"levier {mid!r} : {_RESOLVEUR_EXCLUSIF} sans lambda héritée "
                    "inline en 3e argument — modes exclusifs indérivables")
            dominante, attribut = dominante_resolveur, ("args", 2)
        elif isinstance(n, (ast.If, ast.IfExp)) and _test_de_presence(n.test):
            tests_modelises.add(id(n.test))
            dominante, present = _test_de_presence(n.test)
            attribut = ("orelse", None) if present else ("body", None)
        else:
            continue
        nom, indice = attribut
        branche = getattr(n, nom) if indice is None else getattr(n, nom)[indice]
        copie = ast.parse(textwrap.dedent(src))
        cible = list(ast.walk(copie))[i]
        vide = [ast.Pass()] if isinstance(branche, list) else ast.Constant(None)
        if indice is None:
            setattr(cible, nom, vide)
        else:
            getattr(cible, nom)[indice] = vide
        ignorees = (_cles_litterales(_source_de(branche))
                    - _cles_litterales(ast.unparse(copie)) - {dominante})
        if ignorees:
            groupes.setdefault(dominante, set()).update(ignorees)
    for n in ast.walk(arbre):
        presence = isinstance(n, ast.Compare) and (
            (_test_de_presence(n) and id(n) not in tests_modelises)
            or (len(n.ops) == 1 and isinstance(n.ops[0], (ast.Is, ast.IsNot))
                and isinstance(n.left, ast.Call)
                and isinstance(n.left.func, ast.Attribute)
                and _est_params(n.left.func.value)))
        if presence:
            raise RuntimeError(
                f"levier {mid!r} : test de présence non modélisé "
                f"({ast.unparse(n)}) — un mode exclusif ignoré en silence ; "
                "réécrire en `if 'k' in params:` ou étendre la dérivation")
    return {d: sorted(c) for d, c in sorted(groupes.items())}


def build_modes_exclusifs() -> dict[str, dict[str, list[str]]]:
    """``{levier: {clé dominante: [clés ignorées]}}`` pour les handlers qui
    en ont. Les formules ASTEVAL n'y entrent pas : ce sont des expressions
    arithmétiques sans test de présence (verrouillé par
    ``tests/test_noms_parametres_sync.py``)."""
    dominante = _cle_dominante_du_resolveur()
    modes = {}
    for mid, src in _iter_handler_funcs():
        groupes = modes_exclusifs_du_handler(mid, src, dominante)
        if groupes:
            modes[mid] = groupes
    return dict(sorted(modes.items()))


def render_noms_module(noms: dict[str, list[str]],
                       modes: dict[str, dict[str, list[str]]]) -> str:
    """Module Python des noms admis (artefact GÉNÉRÉ, importé à l'exécution :
    aucun fichier de données à empaqueter, aucune analyse de code au
    démarrage du service)."""
    lignes = [
        '"""Noms de paramètres admis par levier — GÉNÉRÉ, NE PAS ÉDITER.',
        "",
        "Généré par ``scripts/generate_measure_registry.py`` depuis le code : les",
        "lectures du dict ``params`` dans le corps des handlers (même extracteur",
        "que ``docs/MEASURE_REGISTRY.md``), ``intensite`` pour les leviers",
        "d'``INTENSITE_DOMAINS``, et les lectures ``p.get(...)`` des formules",
        "ASTEVAL de ``policy_measures.json`` pour les leviers sans handler.",
        "",
        "``MODES_EXCLUSIFS`` : noms admis mais IGNORÉS quand un autre est fourni",
        "(lambda héritée de ``_resolve_intensite_or_legacy``, branche « absent »",
        "d'un ``if 'k' in params``) — réfutation de V2-04.",
        "",
        "Consommé par la porte des noms (``engine/_param_domain.py``,",
        "``valider_noms_parametres``, v0.6.10 — contre-audit externe V2-04).",
        "Synchronisation verrouillée par ``tests/test_noms_parametres_sync.py``",
        "(``--noms --check``). Régénérer :",
        "``python scripts/generate_measure_registry.py --noms``.",
        '"""',
        "",
        "NOMS_PARAMETRES_ADMIS: dict[str, frozenset[str]] = {",
    ]
    for mid, cles in noms.items():
        contenu = ", ".join(repr(c) for c in cles)
        lignes.append(f"    {mid!r}: frozenset({{{contenu}}}),"
                      if cles else f"    {mid!r}: frozenset(),")
    lignes += ["}", "",
               "MODES_EXCLUSIFS: dict[str, dict[str, frozenset[str]]] = {"]
    for mid, groupes in modes.items():
        lignes.append(f"    {mid!r}: {{")
        for dominante, cles in groupes.items():
            contenu = ", ".join(repr(c) for c in cles)
            lignes.append(f"        {dominante!r}: frozenset({{{contenu}}}),")
        lignes.append("    },")
    lignes.append("}")
    return "\n".join(lignes) + "\n"


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
    p.add_argument("--out-noms", type=Path, default=DEFAULT_NOMS)
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 1 si les artefacts commités divergent du code",
    )
    p.add_argument(
        "--noms",
        action="store_true",
        help="seulement le module des noms admis (ne lit pas le frontend : "
             "tourne depuis le dépôt public seul)",
    )
    a = p.parse_args()
    # Le module des noms d'abord : il ne dépend pas du frontend, et son échec
    # dur (accès non modélisable, levier sans contrat) précède toute écriture.
    artefacts = [(a.out_noms, render_noms_module(build_noms_admis(),
                                                 build_modes_exclusifs()))]
    reg = None
    if not a.noms:
        reg = build_registry()
        assert_contract_complete(reg)  # échec dur AVANT toute écriture/diff
        artefacts += [
            (a.out_md, render_markdown(reg)),
            (a.out_json,
             json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=True)),
        ]
    if a.check:
        # Compare les artefacts DÉSIGNÉS (défaut : les fichiers commités). La
        # garde de drift des tests passe des COPIES corrompues : elle ne
        # réécrit plus le fichier commité en place, ce qui exposait toute
        # collecte pytest concurrente à un JSON tronqué (« Extra data »).
        drift = [
            str(path)
            for path, content in artefacts
            if not path.exists() or path.read_text("utf-8") != content
        ]
        if drift:
            print("DRIFT registre vs code : " + ", ".join(drift),
                  file=sys.stderr)
            print(
                f"Régénérer : python scripts/{Path(__file__).name}"
                + (" --noms" if a.noms else ""),
                file=sys.stderr,
            )
            sys.exit(1)
        print("noms admis synchro ✓" if a.noms else "registre synchro ✓")
        return
    for path, content in artefacts:
        path.write_text(content, "utf-8")
    if reg is not None:
        print(f"registre : {len(reg['mesures'])} mesures")
    print(f"noms admis : {a.out_noms}")


if __name__ == "__main__":
    main()
