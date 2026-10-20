"""Portabilité de l'encodage des fichiers texte (v0.6.10, contre-audit externe V2-05).

Constat de l'audit : sous Windows sans `PYTHONUTF8=1`, `Path.read_text()` sans
`encoding=` décode les fichiers avec l'encodage de la locale (cp1252) ; les noms
de colonnes accentués des snapshots JSON (« Déficit/PIB % », « Chômage % »)
deviennent « DÃ©ficit/PIB % », « ChÃ´mage % », et le golden master standalone
(`tests/test_handler_coverage.py`) échoue alors que le moteur est correct.

Sur macOS et Linux l'encodage de la locale est UTF-8 : le défaut ne s'y voit
pas. Ce module le rend reproductible partout en SIMULANT la locale Windows dans
un sous-processus pytest : tout fichier ouvert en mode texte sans `encoding=`
y est décodé en cp1252, exactement comme sous Windows.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Encodage de la locale par défaut d'un Windows occidental (« ANSI code page »
# 1252) — celui que Python applique à un fichier texte ouvert sans `encoding=`
# quand le mode UTF-8 (PEP 540) n'est pas activé.
ENCODAGE_LOCALE_WINDOWS = "cp1252"

# Amorce exécutée dans le sous-processus : substitue l'encodage de la locale
# Windows partout où Python retomberait sur l'encodage de la locale (paramètre
# `encoding` absent). Un appel qui précise `encoding=` n'est PAS affecté.
_AMORCE_LOCALE_WINDOWS = f"""
import builtins, io, sys
_ouvrir = builtins.open
def _text_encoding(encoding, stacklevel=2):
    return {ENCODAGE_LOCALE_WINDOWS!r} if encoding is None else encoding
def _open(file, mode='r', buffering=-1, encoding=None, *args, **kwargs):
    if 'b' not in mode and encoding is None:
        encoding = {ENCODAGE_LOCALE_WINDOWS!r}
    return _ouvrir(file, mode, buffering, encoding, *args, **kwargs)
io.text_encoding = _text_encoding
builtins.open = _open
io.open = _open
import pytest
sys.exit(pytest.main(sys.argv[1:]))
"""

# Tests qui relisent un snapshot JSON aux clés accentuées. Le premier est celui
# que l'audit a vu échouer sur un clone du dépôt public seul ; les deux autres
# exigent les scénarios publiés (BUDGETLAB_SCENARIOS_JSON) et sont ignorés
# sans eux — ils échouaient de la même façon quand ils tournent.
TESTS_LECTEURS_DE_SNAPSHOTS = (
    "tests/test_handler_coverage.py::test_standalone_master_all_scenarios_match",
    "tests/test_golden_master_full.py::test_golden_master_all_scenarios_match",
    "tests/test_baseline_properties.py::test_e_non_regression_deltas_scenarios",
)


def test_snapshots_relus_a_l_identique_sous_locale_windows():
    """Rouge V2-05 (a) : sous une locale cp1252, les lecteurs de snapshots
    doivent passer comme sous UTF-8 — l'encodage d'un fichier du dépôt est une
    propriété du fichier (UTF-8), jamais de la machine qui le lit."""
    res = subprocess.run(
        [sys.executable, "-c", _AMORCE_LOCALE_WINDOWS,
         *TESTS_LECTEURS_DE_SNAPSHOTS,
         "-q", "-p", "no:cacheprovider", "--no-header"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    assert res.returncode == 0, (
        "Sous une locale Windows (cp1252), la relecture des snapshots échoue : "
        "un fichier texte est ouvert sans encoding='utf-8'.\n"
        + res.stdout[-4000:] + res.stderr[-2000:]
    )
