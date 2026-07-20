"""
Rhythma AI — FastAPI Backend
Entry point for all API services.
"""
from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Direct imports from API modules
from api.health import router as health_router
from api.assistant import router as assistant_router
from api.cycle import router as cycle_router
from api.insights import router as insights_router
from api.sms import router as sms_router
from api.dashboard import router as dashboard_router

# Auth router lives in core (not in api) to avoid duplicate registration
from core.auth_router import router as auth_router

from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Rhythma backend starting up...")
    yield
    logger.info("Rhythma backend shutting down.")


app = FastAPI(
    title="Rhythma AI API",
    description="Backend for Rhythma — India's multilingual AI women's health companion",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# TODO: Tighten this in production (allow only specific origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",  # So Swagger UI works
        "http://localhost:3000",  # Your Flutter web (if you ever run it)
        "http://127.0.0.1:8000",
        "http://localhost:5173",  # Vite dev server default port (web/)
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",   # Flutter web dev server
        "http://127.0.0.1:8081",
        "http://localhost:8082",
        "http://127.0.0.1:8082",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Auth is registered first so protected-route dependencies resolve cleanly.
app.include_router(auth_router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(health_router,    prefix="/api/v1/health",    tags=["Health Check"])
app.include_router(assistant_router, prefix="/api/v1/assistant", tags=["AI Assistant"])
app.include_router(cycle_router,     prefix="/api/v1/cycle",     tags=["Cycle Tracking"])
app.include_router(insights_router,  prefix="/api/v1/insights",  tags=["Insights"])
app.include_router(sms_router,       prefix="/api/v1/sms",       tags=["SMS"])
app.include_router(dashboard_router, prefix="/api/v1",           tags=["Dashboard"])


@app.get("/")
async def root():
    return {"message": "Rhythma AI API is running 🌸", "version": "0.1.0"}