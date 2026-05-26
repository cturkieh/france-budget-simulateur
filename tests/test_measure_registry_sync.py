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

ROOT = Path(__file__).resolve().parent.parent
JSON_ARTIFACT = ROOT / "tests" / "snapshots" / "measure_registry.json"

# `generate_measure_registry.py --check` parse `frontend-react/.../ExploreCreateSection.jsx`
# pour le niveau "sliders" du registre. Skipif fork moteur seul.
_FRONT_JSX = ROOT / "frontend-react" / "src" / "components" / "ExploreCreateSection.jsx"
pytestmark = pytest.mark.skipif(
    not _FRONT_JSX.exists(),
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
