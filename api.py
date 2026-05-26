# api.py — point d'entrée FastAPI du moteur france-budget-simulateur
# (AGPL-3.0). Expose /simulate, /scenarios, /health et /. CORS configurable
# via la variable d'environnement CORS_ORIGINS (CSV) — par défaut, développement
# local uniquement.
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from budget_simulator import BudgetSimulatorV45, load_default_values

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    force=True,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Simulateur Budget France API",
    description="API publique du moteur économique france-budget-simulateur (AGPL-3.0)",
    version="4.5"
)

# Origines CORS — surcharge via env var CORS_ORIGINS (séparées par virgules).
# Défaut : localhost dev seulement. Un déploiement ajoute son domaine publique.
_DEFAULT_CORS_ORIGINS = ",".join(
    f"http://localhost:{port}"
    for port in (3000, 3001, 3002, 3003, 3004, 3005, 5173, 8501)
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulationRequest(BaseModel):
    """Requête de simulation avec validation stricte."""
    mesures: dict[str, Any] | None = Field(default_factory=dict)
    periods: int = Field(default=10, ge=1, le=50)

    @field_validator('mesures')
    @classmethod
    def validate_mesures(cls, v):
        if v and len(str(v)) > 50000:
            raise ValueError('Le dictionnaire de mesures est trop volumineux')
        return v


@app.post("/simulate")
async def simulate(request: SimulationRequest):
    """Lance une simulation budgétaire.

    Notes pour les intégrations :
    - Les leviers inconnus du registre `policy_measures.json` produisent **422**
      avec la liste des clés invalides (échec bruyant côté client, pas de
      silent ignore).
    - Les valeurs hors domaine d'un levier connu (ex. `intensite` hors bornes)
      sont **clampées silencieusement** par le moteur en mode tolérant (config
      production) — le client reçoit 200 avec un résultat sur les bornes
      respectées. Pour un comportement strict (422 si hors domaine), activer
      `BUDGETLAB_STRICT=1` côté serveur.
    """
    # Instantiation moteur (chargement policy_measures.json + registre).
    # En cas d'échec systémique (fichier corrompu, schema cassé) → 500.
    try:
        sim = BudgetSimulatorV45(
            periods=request.periods,
            mesures=request.mesures
        )
    except Exception as e:
        logger.error("Échec instantiation moteur : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur initialisation moteur: {e}" if DEBUG_MODE
            else "Erreur initialisation moteur. L'incident a été journalisé."
        )

    # Validation explicite des leviers : un POST avec une clé inconnue ne doit
    # pas retourner 200 status-quo silencieusement. Le moteur tolère (continue
    # silencieux dans orchestrator.apply_measures) par compat historique —
    # l'API publique impose l'invariant côté contrat externe.
    unknown_levers = sorted(set(request.mesures or {}) - set(sim.measure_registry))
    if unknown_levers:
        logger.warning("Leviers inconnus rejetés : %s", unknown_levers)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Leviers inconnus : {unknown_levers}. "
                f"Voir GET /scenarios pour les leviers valides."
            ),
        )

    try:
        results, details, report = sim.simulate()

        if 'measure_impacts_by_year' not in report:
            # Drift de contrat moteur — échec systémique (le front affichera un
            # tableau d'impacts vide). logger.error → remontée Sentry côté infra.
            logger.error(
                "Drift contrat moteur : 'measure_impacts_by_year' absent du report "
                "(periods=%d, n_mesures=%d)",
                request.periods, len(request.mesures or {})
            )
        measure_impacts = report.pop('measure_impacts_by_year', [])

        return {
            "success": True,
            "results": results.to_dict(orient='records'),
            "details": details.to_dict(orient='records'),
            "report": report,
            "measure_impacts": measure_impacts,
            "logs": sim.debug_logs[:200] if DEBUG_MODE else []
        }
    except ValueError as e:
        # Paramètres hors domaine (clamp/range moteur) — faute client légitime.
        logger.warning("Simulation rejetée (paramètres hors domaine) : %s", e)
        raise HTTPException(
            status_code=422,
            detail=f"Paramètres invalides: {e}"
        )
    except (KeyError, AttributeError, TypeError, ZeroDivisionError) as e:
        # Bug interne du moteur (clé manquante, type incohérent, /0).
        # 500 explicite, pas 400 — distinction « faute client » vs « bug serveur ».
        logger.error("Bug moteur (%s) : %s", type(e).__name__, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du moteur ({type(e).__name__}). L'incident a été journalisé."
            if DEBUG_MODE
            else "Erreur interne du moteur. L'incident a été journalisé."
        )
    except Exception as e:
        logger.error("Erreur inattendue : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur inattendue: {e}" if DEBUG_MODE else "Erreur interne inattendue."
        )


@app.get("/scenarios")
async def get_scenarios():
    """Retourne les scénarios prédéfinis."""
    try:
        status_quo = load_default_values()
    except Exception as e:
        logger.error("Échec chargement valeurs par défaut : %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Configuration des valeurs par défaut indisponible."
        )
    return {
        "status_quo": status_quo,
        "austerite": {
            "impot_societes": {"taux": 0.33},
            "tva_rate": {"taux": 0.23},
            "retraites": {"age_depart": 64.0}
        },
        "scandinave": {
            "retraites": {"age_depart": 64.0},
            "education": {"budget": 85.0},
            "transition_ecologique": {"investissement": 25.0},
            "fraude_fiscale": {"effort": 20.0}
        },
        "relance_verte": {
            "transition_ecologique": {"investissement": 40.0},
            "education": {"budget": 85.0}
        }
    }


@app.get("/")
@app.head("/")
async def root():
    """Route racine — info API (supporte GET et HEAD pour health checks plateforme)."""
    return {
        "name": "France Budget API",
        "version": "4.5",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "simulate": "/simulate (POST)",
            "scenarios": "/scenarios (GET)",
            "documentation": "/docs"
        },
        "debug_mode": DEBUG_MODE
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "version": "4.5",
        "service": "budget-simulator-api",
        "debug_mode": DEBUG_MODE
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=DEBUG_MODE
    )
