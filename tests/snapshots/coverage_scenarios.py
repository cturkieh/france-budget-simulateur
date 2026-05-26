"""Mini-scénarios standalone (1 handler activé, autres à default) — Phase 0.8 du plan refactor.

Pour chaque handler du moteur, on construit un scénario où SEUL ce handler est activé
avec un paramètre dévié à mi-distance entre default et max (ou min). Ces scénarios
complètent les FULL_SCENARIOS politiques en couvrant trois cas qu'ils manquent :

1. **Couverture exhaustive** : certains handlers (`tva_rate`, `elargissement_ir`,
   `abattement_retraites`) ne sont activés par aucun FULL_SCENARIO avec une valeur
   non-default — le coverage 33/33 n'est atteignable qu'avec les standalone.
2. **Anti-compensation** : dans un scénario combiné, un bug peut être masqué par
   compensation (ex: TVA +5 Md€ et IS -5 Md€ par bug = total juste). En isolation,
   le bug se manifeste.
3. **Détection précoce** : a déjà permis de découvrir un crash silencieux dans
   `_apply_fonction_publique` (format string `{:+d}` sur float depuis JSON frontend).

Génération : depuis `policy_measures.json` (min/max), MAIS chaque clé
pilote est cross-validée contre `measure_registry.json` (vérité = handlers,
T4 dé-tautologisation) : une clé hors contrat fait échouer bruyamment.
Voir docs/REFACTOR_SPLIT_PLAN.md § Phase 0.8.

Usage:
    python tests/snapshots/coverage_scenarios.py [--out tests/snapshots/standalone_master_v1.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from budget_simulator.simulator import BudgetSimulatorV45  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TRACKED_COLUMNS = [
    'Dette/PIB %', 'Déficit/PIB %', 'Chômage %', 'Croissance %',
    'Inflation %', "Pouvoir d'Achat", 'Inegalites', 'Competitivite',
]


REGISTRY_PATH = ROOT / 'tests' / 'snapshots' / 'measure_registry.json'
# Sentinelles importées du PRODUCTEUR (source unique du contrat de
# sérialisation) — pas de re-littéral divergent ici (cf. revue T4 #1.1).
sys.path.insert(0, str(ROOT))
from scripts.generate_measure_registry import _DYNAMIC, _UNMODELED  # noqa: E402

_CONTRACT_SENTINELS = frozenset({_DYNAMIC, _UNMODELED})


def _load_registry() -> dict:
    """Registre du contrat (source de vérité = handlers).

    Sa FRAÎCHEUR est garantie par `test_measure_registry_sync` — garde
    COMPLÉMENTAIRE et CONCURRENTE (pas préalable) à ce cross-check : les
    deux doivent coexister, l'une ne rend pas l'autre redondante. Absence
    ou structure invalide = échec BRUYANT et ACTIONNABLE : sans oracle, la
    couverture standalone serait tautologique (le JSON se validant
    lui-même) — précisément ce que T4 supprime."""
    if not REGISTRY_PATH.exists():
        raise RuntimeError(
            f"registre absent ({REGISTRY_PATH}) : impossible de cross-valider "
            "les mini-scénarios contre le vrai contrat — "
            "régénérer via scripts/generate_measure_registry.py"
        )
    reg = json.loads(REGISTRY_PATH.read_text())
    if not isinstance(reg, dict) or not isinstance(reg.get('mesures'), dict):
        raise RuntimeError(
            f"registre malformé ({REGISTRY_PATH}) : clé 'mesures' (objet) "
            "absente/invalide — régénérer via "
            "scripts/generate_measure_registry.py"
        )
    return reg


def _assert_param_in_contract(measure_id: str, param: str, registry: dict) -> None:
    """Échoue BRUYAMMENT (et de façon ACTIONNABLE) si ``param`` n'est pas une

    clé réelle du contrat du handler ``measure_id``. Transforme la
    couverture standalone d'un test « JSON contre lui-même » en test
    « JSON contre la vérité (handlers) » : une clé morte ré-introduite dans
    policy_measures.json ne peut plus piloter silencieusement un
    mini-scénario. PAS de fallback sur le param suivant : c'est DÉLIBÉRÉ
    (anti-tautologie) — ne pas transformer ce raise en continue (cela
    réintroduirait la tautologie en silence)."""
    mesures = registry.get('mesures') or {}
    if measure_id not in mesures:
        raise RuntimeError(
            f"handler '{measure_id}' absent du registre — registre périmé ? "
            "régénérer via scripts/generate_measure_registry.py "
            "(test_measure_registry_sync devrait l'avoir signalé)"
        )
    real = set((mesures[measure_id].get('params') or {})) - _CONTRACT_SENTINELS
    if param not in real:
        raise RuntimeError(
            f"mini-scénario standalone '{measure_id}' piloté par '{param}' "
            f"HORS contrat (clés réelles du handler : {sorted(real)}). "
            "Clé morte dans policy_measures.json ou extracteur à étendre."
        )


def build_standalone_scenarios() -> dict[str, dict[str, dict]]:
    """Construit un mini-scénario par handler : `{handler_id: {handler_id: {param: deviated_value}}}`.

    Pour chaque handler, prend le 1er paramètre numérique et active à
    mi-distance entre default et max (ou vers min si aucun max strictement
    supérieur au défaut). La clé pilote est cross-validée contre le registre
    (vérité = handlers) : dé-tautologisation T4 — voir
    `_assert_param_in_contract`.
    """
    config = json.loads((ROOT / 'policy_measures.json').read_text())
    handler_ids = set(BudgetSimulatorV45().measure_handlers.keys())
    registry = _load_registry()

    scenarios = {}
    for measure in config['mesures']:
        m_id = measure['id']
        if m_id not in handler_ids:
            continue
        for param_name, param_cfg in measure.get('parametres', {}).items():
            if not isinstance(param_cfg, dict):
                continue
            default = param_cfg.get('valeur_defaut')
            max_val = param_cfg.get('max')
            min_val = param_cfg.get('min')
            if not isinstance(default, (int, float)):
                continue
            if isinstance(max_val, (int, float)) and max_val > default:
                deviated = round(default + (max_val - default) * 0.5, 4)
            elif isinstance(min_val, (int, float)) and min_val < default:
                deviated = round(default - (default - min_val) * 0.5, 4)
            else:
                continue
            # Oracle externe (vérité = handlers) : la clé pilote DOIT être
            # au contrat, sinon couverture tautologique → échec bruyant.
            _assert_param_in_contract(m_id, param_name, registry)
            scenarios[m_id] = {m_id: {param_name: deviated}}
            break
    return scenarios


def build_snapshot() -> dict:
    """Génère le snapshot standalone : pour chaque mini-scénario, simule et capture les colonnes tracked."""
    snapshot = {}
    for name, mesures in build_standalone_scenarios().items():
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        cols = [c for c in TRACKED_COLUMNS if c in df.columns]
        snapshot[name] = {
            'columns': cols,
            'years': list(df.index),
            'data': {c: [round(float(v), 3) for v in df[c].tolist()] for c in cols},
        }
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, help="Si fourni, écrit le snapshot JSON; sinon liste les scénarios")
    args = parser.parse_args()

    if args.out:
        args.out.write_text(json.dumps(build_snapshot(), indent=2, ensure_ascii=False))
        print(f"Snapshot écrit dans {args.out}")
    else:
        scenarios = build_standalone_scenarios()
        print(f"{len(scenarios)} mini-scénarios standalone construits")
        for k, v in scenarios.items():
            print(f"  {k}: {v[k]}")
