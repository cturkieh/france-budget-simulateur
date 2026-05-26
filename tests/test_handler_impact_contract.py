"""Contrat de clés des ImpactsDict — détecteur de dérive.

Un typo d'une clé canonique dans un handler (ex. ``chomages`` au lieu de
``chomage``) serait silencieusement ignoré par l'agrégation macro = bug
invisible. Ce test itère les 33 handlers, collecte les clés d'``ImpactsDict``
émises sur 10 ans, et échoue si une clé sort de l'ensemble connu (canonique
+ traçabilité allowlistée). L'allowlist est bâtie depuis la réalité ; toute
nouvelle clé légitime doit y être ajoutée consciemment. Contexte (LOW
préventif, pas de durcissement des collecteurs) : REFACTOR_SPLIT_PLAN.md.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import HANDLER_FAILED_KEY
from tests.snapshots.coverage_scenarios import build_standalone_scenarios

# Clés agrégées LUES par le moteur macro (cf handlers/_types.py).
CANONICAL_KEYS = frozenset({
    'depenses', 'recettes', 'pouvoir_achat', 'gini', 'competitivite', 'chomage',
})

# Clés de traçabilité / métadonnée émises par certains handlers, conservées
# dans le retour mais IGNORÉES par l'agrégation macro (cf _types.py).
# Observées en exécutant les 33 handlers — toute nouvelle entrée doit être
# ajoutée ICI consciemment (et pas par accident côté handler).
TRACEABILITY_KEYS = frozenset({
    'aides_sociales', 'ambulatoire', 'cotisations', 'emploi', 'fp',
    'franchise_forfaits', 'hopital', 'niches_reduction', 'phasing_admin',
    'phasing_struct', 'pib_sante_pct', 'prevention_budget',
    'prevention_organisation', 'taux',
    'description',      # str — métadonnée libellé (_apply_asu)
    'rabot_details',    # dict — tolérance ImpactsDict documentée (_apply_rabot_uniforme)
})

# Clés d'infrastructure (échec handler / message d'erreur) posées par
# l'orchestrateur, pas par les handlers eux-mêmes.
INFRA_KEYS = frozenset({HANDLER_FAILED_KEY, 'erreur'})

ALLOWED_KEYS = CANONICAL_KEYS | TRACEABILITY_KEYS | INFRA_KEYS


def _toggle_param_ids() -> dict[str, list[str]]:
    """{measure_id: [param_names...]} de TOUS les params binaires (toggle 0/1).

    `build_standalone_scenarios` dévie tout param à MI-distance default↔max.
    Pour un toggle binaire (ex. `abattement_retraites.reforme_active`), 0.5
    ≠ activé → le handler ne tourne pas, n'émet aucune clé, et le contrat
    serait vert sans rien vérifier (faux négatif). On force CHAQUE toggle à
    sa valeur ACTIVANTE (1) pour que le handler s'exécute réellement —
    liste (pas un seul) car une mesure peut en avoir plusieurs
    (`rabot_uniforme` : 3 `exclure_*`).
    """
    config = json.loads((ROOT / 'policy_measures.json').read_text())
    toggles: dict[str, list[str]] = {}
    for measure in config['mesures']:
        for pname, pcfg in measure.get('parametres', {}).items():
            if not isinstance(pcfg, dict):
                continue
            is_toggle = pcfg.get('type') == 'toggle' or (
                pcfg.get('min') == 0 and pcfg.get('max') == 1
                and pcfg.get('step') == 1
            )
            if is_toggle:
                toggles.setdefault(measure['id'], []).append(pname)
    return toggles


@pytest.fixture(scope="module")
def emitted_keys_by_handler():
    """{handler_id: set(clés émises sur 10 ans)} pour les 33 handlers.

    Les params toggle sont forcés à leur valeur activante (cf
    `_toggle_param_ids`) pour qu'AUCUN handler ne reste silencieux — sinon
    la garde de non-vacuité (`test_every_handler_emits_at_least_one_key`)
    transforme l'oubli en échec bruyant plutôt qu'en faux négatif.
    """
    toggles = _toggle_param_ids()
    result = {}
    for hid, mesures in build_standalone_scenarios().items():
        mesures = {m: dict(p) for m, p in mesures.items()}
        # Force TOUS les toggles du handler à leur valeur activante, qu'ils
        # soient ou non le param choisi par build_standalone_scenarios.
        for tparam in toggles.get(hid, []):
            mesures.setdefault(hid, {})[tparam] = 1
        sim = BudgetSimulatorV45(periods=10, mesures=mesures)
        _, _, report = sim.simulate()
        keys = set()
        for year_block in report.get('measure_impacts_by_year', []):
            for mid, impacts in year_block.items():
                if mid == 'Année':
                    continue
                assert isinstance(impacts, dict), (
                    f"{hid}: l'ImpactsDict de '{mid}' n'est pas un dict "
                    f"(got {type(impacts).__name__}) — contrat de retour violé."
                )
                keys.update(impacts.keys())
        result[hid] = keys
    return result


def test_all_33_handlers_covered(emitted_keys_by_handler):
    """L'infra standalone active bien 33 handlers (garde-fou anti-régression)."""
    assert len(emitted_keys_by_handler) == 33, (
        f"Attendu 33 handlers couverts, obtenu {len(emitted_keys_by_handler)}. "
        f"build_standalone_scenarios() a dérivé — vérifier policy_measures.json."
    )


def test_every_handler_emits_at_least_one_key(emitted_keys_by_handler):
    """Chaque handler émet ≥1 clé — sinon le contrat serait vert à vide.

    Sans cette garde, un handler non déclenché par son mini-scénario
    (ex. toggle mal dévié) collecte un set vide → `keys - ALLOWED = set()`
    → `test_no_unknown_impact_key_emitted` passe SANS rien vérifier sur ce
    handler. Ce test convertit ce faux négatif en échec explicite.
    """
    silent = sorted(h for h, keys in emitted_keys_by_handler.items() if not keys)
    assert not silent, (
        f"Handler(s) n'émettant AUCUNE clé d'impact : {silent}. "
        "Leur mini-scénario ne les active pas (toggle non géré par "
        "`_toggle_param_ids` ? param non numérique ?). Le contrat de clés "
        "est aveugle sur eux tant que ce n'est pas corrigé."
    )


def test_no_handler_crashed(emitted_keys_by_handler):
    """Aucun handler n'a crashé (catch absorbé hors BUDGETLAB_STRICT).

    En mode tolérant (défaut hors `make test-strict`), l'orchestrateur
    absorbe un crash handler en posant `{erreur, _handler_failed,
    depenses:0, recettes:0}`. Ces clés sont toutes allowlistées → la garde
    de non-vacuité ET le détecteur de dérive resteraient verts sur un
    handler en échec. Ce test ferme l'angle mort, indépendamment du mode.
    """
    crashed = sorted(
        h for h, keys in emitted_keys_by_handler.items()
        if HANDLER_FAILED_KEY in keys or 'erreur' in keys
    )
    assert not crashed, (
        f"Handler(s) en échec runtime dans leur mini-scénario : {crashed}. "
        "Le catch tolérant de l'orchestrateur l'a absorbé (clés "
        f"{HANDLER_FAILED_KEY!r}/'erreur' posées) — le contrat de clés est "
        "aveugle sur eux. Rejouer en BUDGETLAB_STRICT=1 pour la trace."
    )


def test_no_unknown_impact_key_emitted(emitted_keys_by_handler):
    """Aucune clé d'ImpactsDict hors de l'ensemble connu (détecteur de dérive)."""
    offenders = {
        hid: sorted(keys - ALLOWED_KEYS)
        for hid, keys in emitted_keys_by_handler.items()
        if keys - ALLOWED_KEYS
    }
    assert not offenders, (
        "Clé(s) d'ImpactsDict inconnue(s) détectée(s) :\n"
        + "\n".join(f"  {hid} → {ks}" for hid, ks in offenders.items())
        + "\n\nSi typo d'une clé canonique "
        + f"({sorted(CANONICAL_KEYS)}) : corriger le handler (sinon le moteur "
        "macro l'ignore silencieusement). Si clé légitime nouvelle : l'ajouter "
        "à TRACEABILITY_KEYS dans ce fichier (décision consciente, cf "
        "docs/REFACTOR_SPLIT_PLAN.md item lot A3)."
    )
