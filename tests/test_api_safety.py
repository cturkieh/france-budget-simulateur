"""
Garde-fou : api.py ne doit JAMAIS contenir de dépendance à un orchestrateur
IA tiers (ex. Moonshot/Kimi), à une infrastructure de monitoring privée
(ex. Sentry), ni à des endpoints non documentés ici.

Ce test bloque toute PR qui réintroduirait une telle dépendance dans le
moteur public. Le moteur reste auto-suffisant — un fork doit pouvoir
le déployer sans clé API tierce.
"""
import ast
import importlib.util
import re
from pathlib import Path

import pytest

API_FILE = Path(__file__).resolve().parent.parent / "api.py"

# Patterns interdits dans api.py (case-insensitive sauf indication).
# Chaque pattern documente la raison du retrait Phase 3.
FORBIDDEN_PATTERNS = [
    (r"\bKIMI\b", "clé/config Moonshot — privée"),
    (r"kimi_available", "variable Moonshot"),
    (r"moonshot", "fournisseur IA privé"),
    (r"sentry_setup", "module monitoring instance officielle"),
    (r"init_sentry", "appel monitoring instance officielle"),
    (r"sentry_sdk", "SDK Sentry — réservé à l'instance officielle"),
    (r"\bSENTRY_DSN\b", "variable d'env Sentry — instance officielle"),
    (r"sentry\.io", "URL Sentry hardcodée"),
    (r"captureException", "API Sentry — instance officielle"),
    (r"claude-analysis", "endpoint IA privé"),
    (r"error-report", "endpoint monitoring privé (arbitré retiré 2026-05-24)"),
    (r"AIAnalysisRequest", "modèle pydantic IA privée"),
    (r"AIAnalysisResponse", "modèle pydantic IA privée"),
]

# Endpoints qui DOIVENT être présents dans api.py
REQUIRED_ENDPOINTS = {
    ("POST", "/simulate"),
    ("GET", "/scenarios"),
    ("GET", "/"),
    ("HEAD", "/"),
    ("GET", "/health"),
}

# Endpoints qui DOIVENT être ABSENTS
FORBIDDEN_ENDPOINTS = {
    ("POST", "/api/claude-analysis"),
    ("POST", "/api/error-report"),
}


@pytest.fixture(scope="module")
def api_public_source() -> str:
    if not API_FILE.exists():
        pytest.fail(f"api.py introuvable à {API_FILE} — Phase 3 étape 2 non démarrée")
    return API_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def api_module():
    """Charge api.py comme module Python.

    Le bloc ``if __name__ == "__main__"`` ne s'exécute pas (le module est
    chargé sous le nom ``api_safety_check``, pas ``__main__``).
    Aucun enregistrement dans ``sys.modules`` n'est nécessaire — le fichier
    ne fait pas d'auto-import.
    """
    if not API_FILE.exists():
        pytest.fail(f"api.py introuvable à {API_FILE}")
    spec = importlib.util.spec_from_file_location("api_safety_check", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestForbiddenPatterns:
    """Aucune référence privée ne doit apparaître dans api.py."""

    @pytest.mark.parametrize("pattern,reason", FORBIDDEN_PATTERNS)
    def test_pattern_absent(self, api_public_source: str, pattern: str, reason: str):
        match = re.search(pattern, api_public_source, flags=re.IGNORECASE)
        if match is not None:
            start = max(0, match.start() - 30)
            end = min(len(api_public_source), match.end() + 30)
            context = api_public_source[start:end]
            pytest.fail(
                f"api.py contient pattern interdit /{pattern}/ ({reason}). "
                f"Match {match.group(0)!r} à offset {match.start()}. "
                f"Contexte : {context!r}"
            )


class TestSyntaxAndStructure:
    def test_parses_as_python(self, api_public_source: str):
        try:
            ast.parse(api_public_source)
        except SyntaxError as e:
            pytest.fail(f"api.py n'est pas un fichier Python valide : {e}")

    def test_no_httpx_import(self, api_public_source: str):
        # httpx servait uniquement à appeler Kimi → import inutile en version publique
        assert "import httpx" not in api_public_source, (
            "import httpx présent dans api.py mais utilisé uniquement par "
            "/api/claude-analysis (retiré). Supprimer l'import."
        )


class TestFastAPIRoutes:
    def test_app_loads(self, api_module):
        assert hasattr(api_module, "app"), "api.py doit exposer `app: FastAPI`"

    def test_required_endpoints_present(self, api_module):
        app = api_module.app
        routes = {
            (method, route.path)
            for route in app.routes
            if hasattr(route, "methods")
            for method in route.methods
        }
        missing = REQUIRED_ENDPOINTS - routes
        assert not missing, f"Endpoints publics requis absents : {sorted(missing)}"

    def test_forbidden_endpoints_absent(self, api_module):
        app = api_module.app
        routes = {
            (method, route.path)
            for route in app.routes
            if hasattr(route, "methods")
            for method in route.methods
        }
        leaked = FORBIDDEN_ENDPOINTS & routes
        assert not leaked, f"Endpoints privés présents dans api.py : {sorted(leaked)}"


class TestErrorMapping:
    """Contrat HTTP : faute client → 422, bug serveur → 500. Voir /simulate docstring."""

    @pytest.fixture(scope="class")
    def client(self, api_module):
        from fastapi.testclient import TestClient
        return TestClient(api_module.app)

    def test_pydantic_validation_periods_too_large(self, client):
        # periods=999 hors `le=50` Field → 422 Pydantic natif
        r = client.post("/simulate", json={"mesures": {}, "periods": 999})
        assert r.status_code == 422, f"attendu 422, reçu {r.status_code} — {r.text}"

    def test_unknown_lever_returns_422(self, client):
        # Levier inconnu doit échouer bruyamment, pas retourner 200 status-quo
        r = client.post("/simulate", json={
            "mesures": {"levier_completement_inexistant": {"foo": 1}},
            "periods": 3,
        })
        assert r.status_code == 422, f"attendu 422, reçu {r.status_code} — {r.text}"
        assert "levier_completement_inexistant" in r.text, (
            "Le détail 422 doit nommer le(s) levier(s) inconnu(s)"
        )

    def test_valid_payload_returns_200(self, client):
        # Sanity check : payload valide → 200
        r = client.post("/simulate", json={"mesures": {}, "periods": 3})
        assert r.status_code == 200, f"attendu 200, reçu {r.status_code} — {r.text[:200]}"
        body = r.json()
        assert body.get("success") is True
        assert "results" in body and "report" in body

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"
