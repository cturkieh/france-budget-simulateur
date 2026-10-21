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

# Endpoints qui DOIVENT être publiés (OpenAPI) et servis par l'API
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

# Corps des requêtes valides des endpoints requis qui en exigent un.
REQUETES_VALIDES = {
    ("POST", "/simulate"): {"mesures": {}, "periods": 3},
}

# Réponses d'une route inexistante : 404 (chemin inconnu) ou 405 (chemin connu,
# méthode non servie).
CODES_ROUTE_ABSENTE = frozenset({404, 405})


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


# Fixtures au niveau du module (et non méthodes de classe à portée « class »,
# forme dépréciée par pytest 9.1 — PytestRemovedIn10Warning).
@pytest.fixture(scope="module")
def client(api_module):
    from fastapi.testclient import TestClient
    return TestClient(api_module.app)


@pytest.fixture(scope="module")
def operations_publiees(client) -> set:
    """(MÉTHODE, chemin) de chaque opération publiée dans /openapi.json."""
    r = client.get("/openapi.json")
    assert r.status_code == 200, f"/openapi.json indisponible : {r.status_code}"
    return {
        (methode.upper(), chemin)
        for chemin, operations in r.json()["paths"].items()
        for methode in operations
    }


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
    """Endpoints requis / interdits, testés par le CONTRAT PUBLIC de l'API.

    v0.6.10 (contre-audit externe, V2-05) : l'ancienne version lisait
    `app.routes`, une structure INTERNE de FastAPI. Avec fastapi 0.142.2
    (permis par requirements.txt), les routes d'un routeur inclus y sont
    encapsulées dans un `_IncludedRouter` sans attribut `methods` : le test
    annonçait à tort l'absence de GET /scenarios et POST /simulate — et, pire,
    ne voyait plus un endpoint interdit qui aurait été ajouté au routeur
    (faux vert). On lit désormais ce que l'API publie (`/openapi.json`) et on
    appelle chaque endpoint : deux sources indépendantes de la version.
    """

    def test_app_loads(self, api_module):
        assert hasattr(api_module, "app"), "api.py doit exposer `app: FastAPI`"

    def test_required_endpoints_present(self, operations_publiees):
        missing = REQUIRED_ENDPOINTS - operations_publiees
        assert not missing, f"Endpoints publics requis absents : {sorted(missing)}"

    @pytest.mark.parametrize("methode,chemin", sorted(REQUIRED_ENDPOINTS))
    def test_required_endpoint_repond(self, client, methode, chemin):
        """Appel réel : l'endpoint répond 200 sur une requête valide (pas
        seulement « décrit » par OpenAPI)."""
        corps = REQUETES_VALIDES.get((methode, chemin))
        r = client.request(methode, chemin, json=corps)
        assert r.status_code == 200, (
            f"{methode} {chemin} : attendu 200, reçu {r.status_code} — {r.text[:200]}")

    def test_forbidden_endpoints_absent(self, client, operations_publiees):
        leaked = FORBIDDEN_ENDPOINTS & operations_publiees
        assert not leaked, f"Endpoints privés présents dans api.py : {sorted(leaked)}"
        # Appel réel : couvre aussi une route cachée (`include_in_schema=False`)
        # qu'OpenAPI ne décrit pas.
        repondent = {
            (methode, chemin) for methode, chemin in FORBIDDEN_ENDPOINTS
            if client.request(methode, chemin, json={}).status_code
            not in CODES_ROUTE_ABSENTE
        }
        assert not repondent, f"Endpoints privés servis par l'API : {sorted(repondent)}"


def lectures_de_routes(source: str, nom_fichier: str = "<source>") -> list:
    """Lignes où le code lit un attribut `.routes` (table de routage interne),
    en accès direct ou par `getattr(<objet>, "routes"[, défaut])`."""
    return [noeud.lineno for noeud in ast.walk(ast.parse(source, filename=nom_fichier))
            if (isinstance(noeud, ast.Attribute) and noeud.attr == "routes")
            or (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "getattr" and len(noeud.args) >= 2
                and isinstance(noeud.args[1], ast.Constant)
                and noeud.args[1].value == "routes")]


class TestContratSansStructureInterne:
    """Garde durable V2-05 (b) : aucun test du dépôt ne lit la table de routage
    interne d'une app FastAPI/Starlette (`.routes`) — sa forme change d'une
    version à l'autre ; le contrat est ce que l'API publie et sert."""

    @pytest.mark.parametrize("code,attendu", [
        ("app.routes", 1),
        ("[r.path for r in api.app.routes]", 1),
        ("getattr(app, 'routes')", 1),
        ("getattr(app, 'routes', [])", 1),
        ("app.router", 0),
        ("getattr(app, 'title')", 0),
        ("'routes'", 0),
    ])
    def test_detecteur_routes(self, code, attendu):
        assert len(lectures_de_routes(code)) == attendu

    def test_aucun_test_ne_lit_app_routes(self):
        dossier = Path(__file__).resolve().parent
        fautes = []
        for chemin in sorted(dossier.rglob("*.py")):
            for ligne in lectures_de_routes(chemin.read_text(encoding="utf-8"), str(chemin)):
                fautes.append(f"{chemin.relative_to(dossier)}:{ligne}")
        assert not fautes, (
            "Introspection de la structure interne du routage (`.routes`) — "
            f"tester via /openapi.json et TestClient : {fautes}")


class TestErrorMapping:
    """Contrat HTTP : faute client → 422, bug serveur → 500. Voir /simulate docstring."""

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
