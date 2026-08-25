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


def _run_check() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/generate_measure_registry.py", "--check"],
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


def test_check_detects_drift_red():
    """Rouge automatisé : un artefact corrompu → exit 1 + message DRIFT.

    Sauvegarde/restauration en `finally` (sûr même si l'assertion échoue)."""
    original = JSON_ARTIFACT.read_text("utf-8")
    try:
        JSON_ARTIFACT.write_text(original + "\n/* drift */\n", "utf-8")
        r = _run_check()
        assert r.returncode == 1, "la garde doit rougir sur artefact périmé"
        assert "DRIFT" in r.stderr
    finally:
        JSON_ARTIFACT.write_text(original, "utf-8")
    # Restauration effective : le nominal repasse au vert.
    assert _run_check().returncode == 0
