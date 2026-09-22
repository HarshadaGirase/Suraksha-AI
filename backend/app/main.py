"""FastAPI entry point (CLAUDE.MD §6, §7).

WebSockets are why the backend cannot live on Vercel serverless — see §6. Run
with:  uvicorn app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.ws.audio import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

settings = get_settings()

app = FastAPI(
    title="SurakshaAI",
    description="Voice Guardian & Fraud Rescue Network",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Liveness plus which dependencies are actually configured.

    Reports configuration, not reachability: it must stay cheap enough for the
    deployment keep-alive pinger (PLAN.md C9) without burning STT credit.
    """
    return {
        "status": "ok",
        "services": {
            "stt": "configured" if settings.has_stt else "missing_key",
            "gemini": "configured" if settings.gemini_api_key not in ("", "your_key_here") else "missing_key",
            # Postgres is not installed locally yet; first needed at M2.
            "database": "configured" if settings.database_url else "not_configured",
        },
    }
