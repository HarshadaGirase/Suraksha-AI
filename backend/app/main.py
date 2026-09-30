"""FastAPI entry point (CLAUDE.MD §6, §7).

WebSockets are why the backend cannot live on Vercel serverless — see §6. Run
with:  uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import pool
from app.docs.routes import router as docs_router
from app.tts.routes import router as tts_router
from app.ws.audio import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

settings = get_settings()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # A missing or unreachable database must not stop the app booting: the STT
    # pipeline does not need it, and a dead /ws/audio reads as a broken product
    # (PLAN.md open risks).
    await pool.connect(settings)
    yield
    await pool.disconnect()


app = FastAPI(
    title="SurakshaAI",
    description="Voice Guardian & Fraud Rescue Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(docs_router)
app.include_router(tts_router)


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Liveness, plus the state of each dependency.

    STT and Gemini report configuration only — probing them would burn credit
    on every keep-alive ping (PLAN.md open risks). The database reports real
    reachability, because "configured but unreachable" is the failure that
    actually bites during a demo, and a SELECT 1 is free.
    """
    return {
        "status": "ok",
        "services": {
            "stt": (
                "online" if settings.stt_live
                else "disabled" if settings.has_stt
                else "missing_key"
            ),
            "gemini": "configured" if settings.has_gemini else "missing_key",
            "database": "online" if await pool.healthy() else (
                "unreachable" if settings.database_url else "not_configured"
            ),
        },
    }
