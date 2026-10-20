"""Garde CI (v0.6.10, V2-04) : le module des noms admis DOIT refléter le code.

``budget_simulator/engine/_noms_parametres.py`` est GÉNÉRÉ par
``scripts/generate_measure_registry.py`` (même extracteur que
``docs/MEASURE_REGISTRY.md``) et consommé à l'exécution par la porte des noms.
Contrairement à ``test_measure_registry_sync.py``, cette garde ne lit PAS le
frontend (``--noms``) : elle tourne aussi sur le dépôt public seul. Rouge ET
vert testés automatiquement.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# `.absolute()` et PAS `.resolve()` : même piège de symlink que
# test_measure_registry_sync.py (tests/ monté en symlink par le dépôt parent).
ROOT = Path(__file__).absolute().parent.parent
MODULE = ROOT / "budget_simulator" / "engine" / "_noms_parametres.py"
REGISTRE = ROOT / "tests" / "snapshots" / "measure_registry.json"

sys.path.insert(0, str(ROOT))
from scripts.generate_measure_registry import (  # noqa: E402
    _DYNAMIC, _UNMODELED, _cles_reelles, _noms_formule)
from budget_simulator.engine._noms_parametres import NOMS_PARAMETRES_ADMIS  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/generate_measure_registry.py", "--noms", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_noms_admis_synchro_avec_le_code():
    r = _run("--check")
    assert r.returncode == 0, (
        f"Module des noms admis désynchronisé du code.\n{r.stderr}\n"
        "Régénérer : python scripts/generate_measure_registry.py --noms")


def test_check_noms_detecte_la_derive(tmp_path):
    """Rouge automatisé, sur une COPIE (le module commité n'est jamais touché)."""
    copie = tmp_path / "_noms_parametres.py"
    original = MODULE.read_text("utf-8")
    copie.write_text(original, "utf-8")
    assert _run("--check", "--out-noms", str(copie)).returncode == 0
    # La faute de frappe du contre-audit, ajoutée à la main au contrat.
    derive = original.replace("'tva_rate': frozenset({'taux'})",
                              "'tva_rate': frozenset({'taux', 'tauxx'})")
    assert derive != original
    copie.write_text(derive, "utf-8")
    r = _run("--check", "--out-noms", str(copie))
    assert r.returncode == 1 and "DRIFT" in r.stderr
    assert MODULE.read_text("utf-8") == original


def test_noms_admis_identiques_au_registre_publie():
    """Même extracteur, deux artefacts : le registre public commité et le
    module d'exécution disent la même chose, levier par levier."""
    registre = json.loads(REGISTRE.read_text("utf-8"))["mesures"]
    for mid, m in registre.items():
        cles = {k for k in m["params"] if k not in (_DYNAMIC, _UNMODELED)}
        assert NOMS_PARAMETRES_ADMIS[mid] == cles, mid


def test_formules_lues_comme_le_corps_d_une_lambda():
    assert _noms_formule("defense", "p.get('budget', 50) - 50") == {"budget": {"default": 50}}
    assert set(_noms_formule("x", "p['a'] + p.get('b', 0)")) == {"a", "b"}


@pytest.mark.parametrize("formule", ["", None, "p.get('a' +"])
def test_formule_illisible_echec_dur(formule):
    with pytest.raises(RuntimeError, match="indérivables"):
        _noms_formule("x", formule)


def test_acces_non_modelisable_echec_dur():
    """Une clé dynamique rendrait la liste des noms fausse : refus de générer
    (jamais un levier qui laisserait tout passer)."""
    params = _noms_formule("x", "p.get(cle_variable, 0)")
    assert _DYNAMIC in params
    with pytest.raises(RuntimeError, match="non modélisable"):
        _cles_reelles("x", params)
