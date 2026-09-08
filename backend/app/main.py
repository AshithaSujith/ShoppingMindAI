import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from app.api.search import router as search_router
from app.api.session import router as session_router
from app.api.dashboard import router as dashboard_router
from app.database.database import Base, engine
from app.core.config import get_settings

import app.database.models  # noqa: F401


settings = get_settings()
logging.basicConfig(level=str(settings["log_level"]), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("shoppingmind")

app = FastAPI(
    title="ShoppingMindAI Agent API",
    version="1.0.0",
    docs_url="/docs" if settings["environment"] != "production" else None,
    redoc_url="/redoc" if settings["environment"] != "production" else None,
)
AGENT_MODE = bool(settings["agent_mode"])

if settings["auto_create_tables"]:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        # Keep health and non-database routes available when PostgreSQL is
        # temporarily unavailable; readiness reports the degraded state.
        logger.exception("Database table creation skipped during startup")

allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
    if host.strip()
]
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts or ["localhost", "127.0.0.1", "0.0.0.0"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings["cors_origins"]),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

app.include_router(search_router)
app.include_router(session_router)
app.include_router(dashboard_router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "ShoppingMindAI Agent API", "status": "ok"}


@app.get("/health/live", tags=["health"])
async def liveness():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok", "agent_mode": AGENT_MODE}
    except Exception:
        logger.exception("Readiness check failed")
        return {"status": "degraded", "database": "unavailable", "agent_mode": AGENT_MODE}


@app.get("/agent/status", tags=["health"])
async def agent_status():
    return {
        "status": "ok",
        "agent_mode": AGENT_MODE,
        "pipeline": "crewai_agent" if AGENT_MODE else "original_parser",
    }

