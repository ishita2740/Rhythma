"""
Rhythma AI — FastAPI Backend
Entry point for all API services.
"""
from dotenv import load_dotenv

load_dotenv()

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging is configured before any other project module is imported, so
# that anything logged during import (Firestore's mock-mode warning, model
# loading, etc.) already lands in the configured sink rather than loguru's
# default one.
from core.logging_config import configure_logging

configure_logging()

# Direct imports from API modules
from api.health import router as health_router
from api.assistant import router as assistant_router
from api.cycle import router as cycle_router
from api.insights import router as insights_router
from api.sms import router as sms_router
from api.dashboard import router as dashboard_router
from api.privacy import router as privacy_router
from api.provider import router as provider_router
from api.health_export import router as health_export_router

# Auth router lives in core (not in api) to avoid duplicate registration
from core.auth_router import router as auth_router

from api.bot import router as bot_router
from core.errors import register_exception_handlers
from core.middleware import RequestContextMiddleware
from core.request_context import REQUEST_ID_HEADER
from core.security_headers import SecurityHeadersMiddleware
from services.health_check_service import build_info, run_checks

from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    info = build_info()
    logger.bind(
        log_format=os.getenv("LOG_FORMAT", "console"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        version=info["version"],
        commit=info["commit"],
        environment=info["environment"],
    ).info("Rhythma backend starting up...")

    # Report the dependency picture once at startup, so a misconfigured
    # deploy is visible in the first few log lines rather than only to
    # whoever thinks to curl /health/ready. Every branch below is a log
    # call: a health check must never be able to stop the app booting,
    # and refusing to start on a degraded optional dependency would be a
    # far worse failure than the one being reported (#348).
    try:
        report = run_checks()
        for component in report.components:
            if component.status == "ok":
                continue
            log = logger.error if component.required else logger.warning
            log(f"Dependency {component.name!r} is {component.status}: {component.detail}")
        if not report.ready:
            logger.error(
                "Backend started NOT READY — /health/ready will return 503."
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Startup health check could not run: {exc}")

    # Expired auth tokens are dropped when they are read, and a token
    # nobody presents again is never read — so before #417 moved these
    # out of process memory the store only ever grew. One sweep at
    # startup keeps the collection bounded without needing a scheduled
    # job, and it is cheap: the rows it walks are the ones already past
    # their expiry.
    #
    # Imported here rather than at module level. `main.py`'s import block
    # is where every feature branch adds its one line, so they collide on
    # merge over nothing but adjacency; this is the only place in the
    # module that uses the store, and `api/sms.py` already imports its
    # client the same way.
    from services import token_store

    try:
        removed = token_store.purge_expired()
        if removed:
            logger.info(f"Swept {removed} expired auth token(s) at startup.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Could not sweep expired auth tokens: {exc}")

    # `rate_limits` has the same shape and had the same problem (#499). A
    # bucket is only ever rewritten, never deleted — `reset()` runs after a
    # successful login and deliberately only for the account-keyed half —
    # so the collection grew by one permanent document per address and per
    # attempted email address, forever. Swept here rather than in a job for
    # the same reason as the tokens above: a deployment with no scheduler
    # should still stay bounded, and the rows this walks are the ones
    # already past their expiry.
    from services.rate_limit_service import RateLimitService

    try:
        removed = RateLimitService.purge_expired()
        if removed:
            logger.info(f"Swept {removed} expired rate-limit bucket(s) at startup.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Could not sweep expired rate-limit buckets: {exc}")

    yield
    logger.info("Rhythma backend shutting down.")


app = FastAPI(
    title="Rhythma AI API",
    description="Backend for Rhythma — India's multilingual AI women's health companion",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Read allowed origins from environment variable (comma-separated).
# Defaults to localhost URLs for local development.
_default_origins = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
]
raw = os.getenv("ALLOWED_ORIGINS")
if raw:
    allowed_origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    origin_regex = None
else:
    allowed_origins = _default_origins
    origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

# ── Middleware ────────────────────────────────────────────────────────────────
# Registration order matters: Starlette runs the *last* registered middleware
# outermost. RequestContextMiddleware is added first so CORSMiddleware wraps
# it — CORS preflight (OPTIONS) is then answered without generating an access
# log line, while every real request still gets an id before any handler runs.
app.add_middleware(RequestContextMiddleware)

# Security headers sit between the two (#405): inside CORS, so a preflight is
# still answered by CORSMiddleware without being decorated — the browser reads
# a preflight response itself and never renders it — and outside the request
# context middleware, so the headers land on the error envelope too. Every
# response, including a 500, passes through here.
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers hide non-safelisted response headers from JavaScript unless
    # they are explicitly exposed. Without this the web client cannot read
    # the request id and so cannot show it in an error message.
    expose_headers=[REQUEST_ID_HEADER],
)

# ── Error handling ────────────────────────────────────────────────────────────
# Normalizes HTTPException, validation errors and unhandled exceptions into a
# single response envelope carrying a stable machine-readable code and the
# request id. See core/errors.py.
register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────
# Auth is registered first so protected-route dependencies resolve cleanly.
app.include_router(auth_router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(health_router,    prefix="/api/v1/health",    tags=["Health Check"])
app.include_router(assistant_router, prefix="/api/v1/assistant", tags=["AI Assistant"])
app.include_router(cycle_router,     prefix="/api/v1/cycle",     tags=["Cycle Tracking"])
app.include_router(insights_router,  prefix="/api/v1/insights",  tags=["Insights"])
app.include_router(sms_router,       prefix="/api/v1/sms",       tags=["SMS"])
app.include_router(dashboard_router, prefix="/api/v1",           tags=["Dashboard"])
app.include_router(bot_router,       prefix="/api/v1/bot",       tags=["Chatbot Engine"])
app.include_router(privacy_router,   prefix="/api/v1/privacy",   tags=["Privacy"])
app.include_router(provider_router,  prefix="/api/v1/provider",  tags=["Provider Dashboard"])
app.include_router(health_export_router, prefix="/api/v1",  tags=["Health Export"])


@app.get("/")
async def root():
    # The version used to be a string literal here that had never changed,
    # so after a deploy there was no way to confirm which commit was live.
    # It now comes from the same build metadata /health reports (#348).
    info = build_info()
    return {
        "message": "Rhythma AI API is running 🌸",
        "version": info["version"],
        "commit": info["commit"],
    }