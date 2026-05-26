"""Invariants d'architecture des mixins de handlers (Lot D, Phase 2).

Deux invariants rendus MÉCANIQUES (jusqu'ici garantis seulement par des
docstrings, ou différés à un mypy non encore branché) :

1. ADR I3 — aucun appel inter-mixin : un handler d'un mixin ne doit
   JAMAIS appeler un handler d'un autre mixin (``self._apply_<x>()``
   depuis le corps d'un ``_apply_*``). Si un croisement est nécessaire,
   la logique partagée est extraite comme méthode de
   ``BudgetSimulatorV45`` (hôte), pas appelée de mixin à mixin — sinon
   le MRO devient un graphe à raisonner. Vérifié par analyse AST de
   tous les ``handlers/*.py``.

   PORTÉE / LIMITE (à ne pas sur-vendre) : la détection est
   **syntaxique et partielle** — elle ne matche que l'appel LITTÉRAL
   ``self._apply_*(``. Échappent volontairement au radar :
   indirection ``getattr(self, '_apply_x')()``, alias de méthode
   (``h = self._apply_x; h()``), ou dispatch
   ``self.measure_handlers[...]()`` invoqué depuis un corps de handler.
   C'est un garde-fou anti-régression du motif courant, PAS une preuve
   formelle d'absence de couplage. Le code actuel ne contient aucune de
   ces indirections (vérifié), donc l'invariant tient réellement
   aujourd'hui ; ce test le maintient.

2. Contrat ``Handler`` mécanique : en l'absence de mypy/pyright branché
   (cf ``_types.py``), le Protocol ``Handler`` n'apporte aucune
   vérification runtime. Ce fichier ajoute un plancher mécanique
   minimal : ``measure_handlers`` couvre exactement 33 handlers, tous
   appelables avec la signature à 6 paramètres du Protocol (le ``self``
   étant absorbé par la liaison de méthode).
"""
import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HANDLERS_DIR = ROOT / 'budget_simulator' / 'handlers'

# Signature d'appel du Protocol Handler (handlers/_types.py), self exclu
# car measure_handlers stocke des méthodes LIÉES.
_HANDLER_PARAMS = ('measure', 'params', 'year', 'gdp', 'inflation', 'unemployment')
_EXPECTED_HANDLER_COUNT = 33


def _cross_handler_calls(path: Path):
    """Liste (handler, lineno, appelé) des appels self._apply_* dans un _apply_*."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    violations = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith('_apply_')):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            fn = sub.func
            if (isinstance(fn, ast.Attribute)
                    and fn.attr.startswith('_apply_')
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == 'self'):
                violations.append((node.name, sub.lineno, fn.attr))
    return violations


def test_no_cross_mixin_handler_calls():
    """Aucun ``_apply_*`` n'appelle un autre ``self._apply_*`` (ADR I3).

    Limite assumée : détection syntaxique du motif littéral uniquement
    (cf docstring module — indirection non couverte).
    """
    handler_files = sorted(HANDLERS_DIR.glob('*.py'))
    assert handler_files, f"Aucun handler trouvé sous {HANDLERS_DIR}"

    offenders = {}
    for path in handler_files:
        found = _cross_handler_calls(path)
        if found:
            offenders[path.name] = found

    assert not offenders, (
        "Appel(s) inter-mixin détecté(s) (violation ADR I3 — "
        "extraire la logique partagée comme méthode de l'hôte) :\n"
        + "\n".join(
            f"  {fname}: {hname}() ligne {ln} appelle self.{called}()"
            for fname, calls in offenders.items()
            for (hname, ln, called) in calls
        )
    )


def test_measure_handlers_match_handler_protocol(default_simulator):
    """``measure_handlers`` : 33 entrées, toutes à la signature Handler.

    Plancher mécanique en attendant mypy : un handler à signature
    divergente (param renommé/ajouté/supprimé) casse ici, pas seulement
    au futur type-check. ``default_simulator`` (conftest) fournit
    ``BudgetSimulatorV45(periods=10)``.
    """
    handlers = default_simulator.measure_handlers
    assert len(handlers) == _EXPECTED_HANDLER_COUNT, (
        f"Attendu {_EXPECTED_HANDLER_COUNT} handlers dans measure_handlers, "
        f"obtenu {len(handlers)} — registre désynchronisé."
    )
    offenders = {}
    for measure_id, fn in handlers.items():
        if not callable(fn):
            offenders[measure_id] = f"non appelable ({type(fn).__name__})"
            continue
        # Méthode liée → self déjà absorbé : on attend exactement les 6
        # paramètres positionnels du Protocol Handler.
        params = tuple(inspect.signature(fn).parameters)
        if params != _HANDLER_PARAMS:
            offenders[measure_id] = f"signature {params} ≠ {_HANDLER_PARAMS}"
    assert not offenders, (
        "Handler(s) non conformes au Protocol Handler (handlers/_types.py) :\n"
        + "\n".join(f"  {mid}: {why}" for mid, why in sorted(offenders.items()))
    )
