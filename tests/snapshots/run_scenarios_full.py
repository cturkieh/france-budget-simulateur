"""Génère un snapshot complet des 8 scénarios politiques avec leurs apiMeasures EXACTES.

SOURCE UNIQUE : les apiMeasures sont lues depuis
``frontend-react/src/data/scenarios.json`` — le MÊME fichier qu'importe
``frontend-react/src/pages/ScenariosPage.jsx`` (POLITICAL_SCENARIOS[*].apiMeasures).
Plus de copie manuelle : le JSX (prod) fait foi, ce module ne fait que le lire.
Toute divergence JSX <-> snapshot est désormais structurellement impossible.

Usage:
    python3 tests/snapshots/run_scenarios_full.py [--out tests/snapshots/<name>.json]
"""
import os
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from budget_simulator.constants import POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45


# Source partagée scenarios.json : le frontend (`ScenariosPage.jsx`) importe le
# même fichier dans le repo principal. Pour un fork moteur seul (sans frontend),
# on accepte une copie fixture embarquée (`tests/fixtures/scenarios.json`) — sinon
# `SCENARIOS = {}` et les tests dépendant des scénarios politiques skippent
# gracieusement (cf `test_political_scenarios_2027.py`, `test_scenario_params_sync.py`).
#
# Override via `BUDGETLAB_SCENARIOS_JSON` : utilisé par les consommateurs qui
# intègrent ce moteur via git submodule (cf budgetlab-france/conftest.py).
# Le `Path.resolve()` ci-dessous suit les symlinks et casse la détection
# automatique quand `tests/` est un symlink — l'env var contourne ce cas.
#
# Principe fail-fast : si l'override est défini mais pointe vers un fichier
# inexistant, on lève immédiatement. Retomber silencieusement sur les
# candidates par défaut MASQUERAIT exactement le bug que l'override prétend
# corriger (l'utilisateur croit son override actif, mais c'est le défaut
# qui est chargé).
_ENV_OVERRIDE = (os.environ.get("BUDGETLAB_SCENARIOS_JSON") or "").strip() or None
if _ENV_OVERRIDE is not None:
    _OVERRIDE_PATH = Path(_ENV_OVERRIDE)
    if not _OVERRIDE_PATH.exists():
        raise FileNotFoundError(
            f"BUDGETLAB_SCENARIOS_JSON={_ENV_OVERRIDE!r} pointe vers un fichier "
            "inexistant. Corrigez le path ou unset la variable pour revenir à "
            "la résolution automatique."
        )
    _SCENARIOS_CANDIDATES = (_OVERRIDE_PATH,)
else:
    _SCENARIOS_CANDIDATES = (
        Path(__file__).resolve().parents[2] / "frontend-react" / "src" / "data" / "scenarios.json",
        Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "scenarios.json",
    )


def _locate_scenarios_json() -> Path | None:
    """Première source `scenarios.json` disponible (repo principal ou fixture fork)."""
    for candidate in _SCENARIOS_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _load_raw() -> dict:
    path = _locate_scenarios_json()
    if path is None:
        return {}
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    missing = [sid for sid, d in raw.items() if "apiMeasures" not in d]
    if missing:
        raise KeyError(f"Clé 'apiMeasures' absente pour : {missing} dans {path}")
    # Profils temporels (release E, chantier W1) : champ FACULTATIF, même forme
    # que l'API ({"levier.parametre": {forme, annee?}}). Mal formé = erreur, pas
    # un scénario sans calendrier en silence (le moteur valide le contenu).
    mal_formes = [sid for sid, d in raw.items()
                  if d.get("profils") is not None and not isinstance(d["profils"], dict)]
    if mal_formes:
        raise TypeError(f"Champ 'profils' non objet pour : {mal_formes} dans {path}")
    return raw


def _load_scenarios() -> dict:
    return {sid: d["apiMeasures"] for sid, d in _RAW.items()}


_SCENARIOS_JSON = _locate_scenarios_json()
_RAW = _load_raw()
# Interface historique préservée : {scenario_id: apiMeasures} (consommée par
# test_political_scenarios_2027.py et test_golden_master_full.py).
SCENARIOS = _load_scenarios()
# Profils temporels de chaque scénario (release E, contrat § 2.3) : {} sans
# calendrier ; transmis au moteur avec les mesures (fiche = simulateur =
# précalcul = golden master).
PROFILS = {sid: dict(d.get("profils") or {}) for sid, d in _RAW.items()}


def pour_le_mode(mesures: dict, annee_debut=None) -> dict:
    """Mesures d'un scénario telles que le MODE les accepte.

    Mode historique (``annee_debut`` absent ou égal à 2026) : sans la recette
    d'une seule année, que le moteur y refuse faute de calendrier (contrat de
    la release E, § 2.1 : 422 en strict, levier retiré et correction tracée en
    tolérant). Depuis la release de paramètres P (v0.8.1), des scénarios
    publiés en portent une : le mode historique les évalue sans elle, comme le
    fait le moteur en tolérant, sans la correction. Mode cadre : mesures
    inchangées (même objet)."""
    from budget_simulator.engine.cadre import LEVIERS_REFUSES_EN_MODE_HISTORIQUE
    if annee_debut is not None and annee_debut > POLICY_START_YEAR:
        return mesures
    if not LEVIERS_REFUSES_EN_MODE_HISTORIQUE & set(mesures):
        return mesures
    return {k: v for k, v in mesures.items() if k not in LEVIERS_REFUSES_EN_MODE_HISTORIQUE}


YEAR_IDX_2029 = 4
PA_KEY = "Pouvoir d'Achat"
# 'Gini' = nom RÉEL de la colonne d'inégalités émise par le moteur (orchestrator.py). L'ancien
# 'Inegalites' ne correspondait à AUCUNE colonne du DataFrame → silencieusement filtré (cf. l.~117),
# d'où l'absence d'inégalités dans les snapshots. Gini placé EN DERNIER → ajout pur : l'ordre des
# colonnes existantes (Dette…Competitivite) est préservé, les snapshots restent additifs (0 drift).
TRACKED_COLUMNS = ['Dette/PIB %', 'Déficit/PIB %', 'Chômage %', 'Croissance %', 'Inflation %',
                   PA_KEY, 'Competitivite', 'Gini']


def _fmt_metric(data: dict, key: str, idx: int, w: int = 8) -> str:
    v = data.get(key, [None] * 11)[idx]
    return f"{v:>{w}}" if v is not None else f"{'N/A':>{w}}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='tests/snapshots/golden_master_pa_before_fix.json')
    # v0.7.0 : année de début des programmes (absente = mode historique, le
    # golden master v1 ; 2028 = golden master du cadre 2027-2032).
    parser.add_argument('--annee-debut', type=int, default=None)
    args = parser.parse_args()

    # En mode CLI (régénération de snapshot), un dict SCENARIOS vide produirait
    # un JSON {} apparemment "réussi" — silent failure pour un mainteneur fork.
    # On exige une source explicite (frontend-react/.../scenarios.json ou
    # tests/fixtures/scenarios.json) sinon exit non-nul avec message clair.
    if not SCENARIOS:
        candidates = "\n  - ".join(str(p) for p in _SCENARIOS_CANDIDATES)
        print(
            "ERREUR : aucune source `scenarios.json` trouvée. Régénération impossible.\n"
            f"Candidats tentés :\n  - {candidates}\n"
            "Embarquer une copie dans `tests/fixtures/scenarios.json` (forks moteur seul).",
            file=sys.stderr,
        )
        sys.exit(2)

    snapshot = {}
    print(f"{'Scenario':<24} {'Dette':>8} {'Déficit':>9} {'Chômage':>9} {'Croiss':>9} {'PA':>8} {'Comp':>8} {'Gini':>8}")
    print("-" * 92)
    for name, mesures in SCENARIOS.items():
        # Calendriers en mode cadre seulement : le mode historique n'en a pas
        # (le moteur les refuserait, correction tracée).
        mode_cadre = args.annee_debut is not None and args.annee_debut > POLICY_START_YEAR
        sim = BudgetSimulatorV45(periods=10, mesures=pour_le_mode(mesures, args.annee_debut),
                                 annee_debut=args.annee_debut,
                                 profils=(PROFILS.get(name) or None) if mode_cadre else None)
        df_main, _, _ = sim.simulate()
        available = [c for c in TRACKED_COLUMNS if c in df_main.columns]
        snapshot[name] = {
            'columns': available,
            'years': list(df_main.index),
            'data': {col: [round(float(v), 3) if v is not None else None for v in df_main[col].tolist()] for col in available}
        }
        d = snapshot[name]['data']
        print(f"{name:<24} {_fmt_metric(d, 'Dette/PIB %', YEAR_IDX_2029)} "
              f"{_fmt_metric(d, 'Déficit/PIB %', YEAR_IDX_2029, 9)} "
              f"{_fmt_metric(d, 'Chômage %', YEAR_IDX_2029, 9)} "
              f"{_fmt_metric(d, 'Croissance %', YEAR_IDX_2029, 9)} "
              f"{_fmt_metric(d, PA_KEY, YEAR_IDX_2029)} "
              f"{_fmt_metric(d, 'Competitivite', YEAR_IDX_2029)} "
              f"{_fmt_metric(d, 'Gini', YEAR_IDX_2029)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nSnapshot saved: {out}")


if __name__ == '__main__':
    main()
