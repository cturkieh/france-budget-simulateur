import json
import os
import subprocess
from pathlib import Path

import pytest

# `.absolute()` et PAS `.resolve()` : le repo parent (budgetlab-france) monte
# tests/ comme SYMLINK vers ce dossier — resolve() le suivrait et retomberait
# TOUJOURS sur la racine du submodule (où frontend-react/ n'existe pas), rendant
# le skipif permanent : la garde ne tournait jamais, nulle part (constaté en
# revue 2026-07-07). absolute() préserve le chemin d'invocation → depuis le
# parent la garde s'exécute ; depuis un fork moteur seul elle skippe, comme prévu.
REPO_ROOT = Path(__file__).absolute().parents[1]
SCENARIOS_JSON = REPO_ROOT / "frontend-react" / "src" / "data" / "scenarios.json"
SCENARIOS_DOC = REPO_ROOT / "docs" / "SCENARIOS_POLITIQUES.md"

# Ces tests cross-check `frontend-react/src/data/scenarios.json` ↔ bloc généré.
# Pour un fork moteur seul (sans frontend) → skip gracieux, pas d'erreur.
pytestmark = pytest.mark.skipif(
    not SCENARIOS_JSON.exists(),
    reason="frontend-react/ hors périmètre fork moteur seul",
)


def test_scenario_block_is_deterministic_and_complete():
    out1 = subprocess.run(["python3", "scripts/generate_scenario_params.py", "--stdout"],
                           capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    out2 = subprocess.run(["python3", "scripts/generate_scenario_params.py", "--stdout"],
                           capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    assert out1 == out2 and out1.strip(), "génération non déterministe ou vide"
    # Tous les scénarios présents, identifiés par leur label canonique (= libellé
    # affiché par l'app). Cross-check depuis scenarios.json : on ne réénonce pas
    # les libellés dans le test (pas de tautologie ni de duplication de source).
    data = json.loads(SCENARIOS_JSON.read_text(encoding="utf-8"))
    # Borne PLANCHER, pas un littéral à recompter à chaque ajout (l'ancien `== 8`
    # était périmé — et mort, le test ne tournant jamais, cf. commentaire REPO_ROOT).
    # Le SET exact des scénarios est verrouillé ailleurs (golden master + précalcul).
    assert len(data) >= 8, f"scenarios.json suspect : {len(data)} scénarios (< 8)"
    for sid, scenario in data.items():
        label = scenario["label"]
        assert label and label != sid, (
            f"scénario {sid} : label placeholder non substitué ({label!r})"
        )
        assert label in out1, f"scénario {sid} (label {label!r}) absent du bloc généré"
    # c'est bien un tableau Markdown
    assert "|" in out1 and "---" in out1


def test_check_mode_exits_nonzero_without_target_file():
    # --check DOIT échouer bruyamment si la cible docs/SCENARIOS_POLITIQUES.md est absente.
    # On déplace réellement le fichier (puis on le restaure exactement) pour exercer le cas.
    # Backup dans le MÊME répertoire que l'original : garantit le même système de
    # fichiers (os.rename atomique, pas de "Invalid cross-device link" en CI tmpfs).
    # Suffixe .bak : déjà couvert par .gitignore (`*.bak`) → un backup résiduel
    # (test tué mid-run) ne peut pas être committé par mégarde.
    assert SCENARIOS_DOC.exists(), "précondition : la doc cible doit exister avant le test"
    backup = SCENARIOS_DOC.with_suffix(".md.bak")
    assert not backup.exists(), f"backup résiduel d'un run précédent : {backup}"
    os.rename(SCENARIOS_DOC, backup)
    try:
        r = subprocess.run(["python3", "scripts/generate_scenario_params.py", "--check"],
                            capture_output=True, text=True, cwd=REPO_ROOT)
        assert r.returncode != 0, (
            f"--check a retourné 0 alors que la cible est absente (échec silencieux) : "
            f"stdout={r.stdout!r} stderr={r.stderr!r}"
        )
        assert r.stderr.strip(), "aucun message d'erreur sur stderr quand la cible est absente"
    finally:
        os.rename(backup, SCENARIOS_DOC)


def test_check_mode_exits_zero_when_synced():
    # Sanity : avec la cible présente et synchro, --check doit retourner 0.
    r = subprocess.run(["python3", "scripts/generate_scenario_params.py", "--check"],
                        capture_output=True, text=True, cwd=REPO_ROOT)
    assert r.returncode == 0, f"--check ≠ 0 alors que synchro attendue : {r.stderr}"
