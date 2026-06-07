"""
Rhythma AI — FastAPI Backend
Entry point for all API services.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import health, assistant, cycle, insights, sms
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Rhythma backend starting up...")
    # Future: initialise Firestore client, load ML models here
    yield
    logger.info("Rhythma backend shutting down.")


app = FastAPI(
    title="Rhythma AI API",
    description="Backend for Rhythma — India's multilingual AI women's health companion",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api/v1/health",    tags=["Health Check"])
app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["AI Assistant"])
app.include_router(cycle.router,     prefix="/api/v1/cycle",     tags=["Cycle Tracking"])
app.include_router(insights.router,  prefix="/api/v1/insights",  tags=["Insights"])
app.include_router(sms.router,       prefix="/api/v1/sms",       tags=["SMS"])


@app.get("/")
async def root():
    return {"message": "Rhythma AI API is running 🌸", "version": "0.1.0"}
