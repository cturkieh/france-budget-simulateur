"""Version du moteur publiée par GET /health (champ ``moteur_version``).

Deux versions successives du moteur peuvent servir le même contrat /simulate (une release de
paramètres ne change pas la signature des réponses) : un déploiement qui doit attendre une version
précise ne peut pas la reconnaître à la forme des réponses. ``/health`` publie donc la version, lue
dans une source unique : ``budget_simulator.__version__``. Aucun autre fichier du moteur ne recopie
ce numéro ; le CHANGELOG, qui décrit chaque version, doit commencer par la même.
"""
import importlib.util
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
API_FILE = RACINE / "api.py"
CHANGELOG = RACINE / "CHANGELOG.md"
FORME = re.compile(r"\d+\.\d+\.\d+")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location("api_version_publiee", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


def test_version_source_unique_au_bon_format():
    import budget_simulator
    version = getattr(budget_simulator, "__version__", None)
    assert isinstance(version, str) and FORME.fullmatch(version), version


def test_health_publie_la_version_du_moteur(client):
    import budget_simulator
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("moteur_version") == f"v{budget_simulator.__version__}"


def test_changelog_commence_par_la_version_publiee():
    """La première entrée du CHANGELOG est la version que le code publie (pas de numéro oublié)."""
    import budget_simulator
    premiere = re.search(r"^## \[v(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(encoding="utf-8"), re.M)
    assert premiere, "aucune entrée « ## [vX.Y.Z] » dans le CHANGELOG"
    assert premiere.group(1) == budget_simulator.__version__


def test_numero_jamais_recopie_dans_le_code():
    """Le numéro n'apparaît qu'une fois dans le code Python du moteur (sa source unique)."""
    import budget_simulator
    v = re.escape(budget_simulator.__version__)
    occurrences = [
        str(p.relative_to(RACINE))
        for p in [API_FILE, *sorted((RACINE / "budget_simulator").rglob("*.py"))]
        if re.search(rf"[\"']v?{v}[\"']", p.read_text(encoding="utf-8"))
    ]
    assert occurrences == ["budget_simulator/__init__.py"], occurrences
