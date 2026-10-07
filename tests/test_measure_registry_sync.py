"""Garde CI : le registre commité DOIT refléter le code (zéro drift).

`docs/MEASURE_REGISTRY.md` + `tests/snapshots/measure_registry.json` sont
GÉNÉRÉS. Toute PR modifiant une lecture de `params` (ou `INTENSITE_DOMAINS`)
sans régénérer fait ROUGIR `--check`. Rouge ET vert testés automatiquement
(pas seulement "prouvé manuellement").
"""
import subprocess
import sys
from pathlib import Path

import pytest

# `.absolute()` et PAS `.resolve()` : le repo parent (budgetlab-france) monte
# tests/ comme SYMLINK vers ce dossier — resolve() le suivrait et retomberait
# TOUJOURS sur la racine du submodule (où frontend-react/ n'existe pas),
# rendant le skipif ci-dessous PERMANENT. C'est exactement ce qui s'est passé :
# la garde n'a jamais tourné, nulle part, et le générateur a pu casser au
# découpage du composant front sans que rien ne rougisse (constaté au lot 7 ;
# même piège, même fix que `test_scenario_params_sync.py`, corrigé lui en
# 2026-07-07). absolute() préserve le chemin d'invocation → depuis le parent la
# garde s'exécute ; depuis un fork moteur seul elle skippe, comme prévu.
ROOT = Path(__file__).absolute().parent.parent
JSON_ARTIFACT = ROOT / "tests" / "snapshots" / "measure_registry.json"

# `generate_measure_registry.py --check` parse les TROIS sources front du
# niveau « sliders » (ALL_VARIABLES / LEVER_META / convertToAPIFormat).
# Skipif fork moteur seul — condition SOURCÉE DU SCRIPT, jamais recopiée.
sys.path.insert(0, str(ROOT))
from scripts.generate_measure_registry import front_disponible  # noqa: E402

pytestmark = pytest.mark.skipif(
    not front_disponible(),
    reason="frontend-react/ hors périmètre fork moteur seul",
)


def _run_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/generate_measure_registry.py", "--check", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_registry_in_sync_with_code():
    """Chemin nominal : artefacts commités == sortie du code → exit 0."""
    r = _run_check()
    assert r.returncode == 0, (
        f"Registre désynchronisé du code.\n{r.stderr}\n"
        "Régénérer puis recommiter docs/MEASURE_REGISTRY.md ET "
        "tests/snapshots/measure_registry.json."
    )


def test_check_detects_drift_red(tmp_path):
    """Rouge automatisé : un artefact corrompu → exit 1 + message DRIFT.

    v0.6.7 : sur des COPIES (`--out-md/--out-json` désignent les artefacts
    comparés). La version précédente corrompait le fichier commité EN PLACE
    le temps du sous-processus : toute lecture concurrente (deux suites pytest
    en parallèle, `make test` + `make test-strict`) voyait un JSON tronqué
    (« Extra data »), et un arrêt brutal entre l'écriture et le `finally`
    laissait l'artefact corrompu dans l'arbre."""
    md = tmp_path / "MEASURE_REGISTRY.md"
    js = tmp_path / "measure_registry.json"
    md.write_text((ROOT / "docs" / "MEASURE_REGISTRY.md").read_text("utf-8"), "utf-8")
    original = JSON_ARTIFACT.read_text("utf-8")
    js.write_text(original, "utf-8")
    assert _run_check("--out-md", str(md), "--out-json", str(js)).returncode == 0
    js.write_text(original + "\n/* drift */\n", "utf-8")
    r = _run_check("--out-md", str(md), "--out-json", str(js))
    assert r.returncode == 1, "la garde doit rougir sur artefact périmé"
    assert "DRIFT" in r.stderr
    # L'artefact commité n'a jamais été touché.
    assert JSON_ARTIFACT.read_text("utf-8") == original
