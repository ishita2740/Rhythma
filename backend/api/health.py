"""Health endpoints (issue #348).

Three routes, because "is the process alive?", "should this instance take
traffic?" and "what exactly is wrong?" are three questions and collapsing
them into one always-200 endpoint answers at most one of them correctly.

``GET /health/`` keeps its original ``{"status", "service"}`` keys and
its 200, and gains ``ready``, ``build`` and ``components``.

One deliberate behaviour change, called out because it is the only one:
``status`` is now the *worst component's* status rather than the constant
``"ok"``. So a deployment with Twilio unconfigured reports ``degraded``
where it used to report ``ok``. That is the point of the issue — the old
value was a constant and carried no information — but it does mean a
caller asserting ``status == "ok"`` sees a change, which is why
``ready`` exists as the boolean a caller should branch on instead.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from services.health_check_service import (
    STATUS_DOWN,
    build_info,
    liveness,
    run_checks,
)

router = APIRouter(tags=["Health"])


class ComponentModel(BaseModel):
    name: str = Field(..., description="Dependency identifier, e.g. `firestore`.")
    status: str = Field(..., description="One of: ok, degraded, down.")
    required: bool = Field(
        ...,
        description=(
            "Whether a failure of this component should stop the instance "
            "receiving traffic. Gemini and Twilio are optional: the "
            "cycle-tracking product works without either. Firestore is not."
        ),
    )
    detail: str = Field(
        ...,
        description=(
            "Human-readable explanation. Never contains a credential, a key "
            "fragment or a project identifier."
        ),
    )
    durationMs: float = Field(..., description="How long this check took.")


class BuildModel(BaseModel):
    version: str
    commit: str = Field(
        ..., description="Short commit SHA, or `unknown` outside a build."
    )
    builtAt: str
    environment: str


class HealthResponse(BaseModel):
    """The detailed view.

    ``status`` and ``service`` are the two keys the original endpoint
    returned and are unchanged, so existing clients keep working.
    """

    status: str = Field(..., description="Worst component status: ok, degraded or down.")
    service: str = "Rhythma API"
    ready: bool = Field(
        ..., description="False when a *required* component is down."
    )
    checkedAt: str
    build: BuildModel
    components: List[ComponentModel]


class LivenessResponse(BaseModel):
    status: str
    service: str
    checkedAt: str


class ReadinessResponse(BaseModel):
    status: str
    ready: bool
    checkedAt: str
    components: List[ComponentModel]


def _checked_at() -> str:
    return liveness()["checkedAt"]


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Detailed health check",
    description=(
        "Per-dependency status, whether each one is required for readiness, "
        "how long each check took, and which build is serving.\n\n"
        "Always returns 200 — this route is for a human or a dashboard "
        "reading the detail, so a 503 here would hide the very breakdown "
        "that was asked for. Use `/health/ready` for a machine-readable "
        "verdict with a status code.\n\n"
        "`status` and `service` are unchanged from the original response, so "
        "clients reading only those keep working."
    ),
)
async def health_check() -> Dict[str, Any]:
    report = run_checks()
    return {
        **report.to_dict(),
        "service": "Rhythma API",
        "checkedAt": _checked_at(),
        "build": build_info(),
    }


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Is this process running? Touches no dependency and always returns "
        "200 if it can answer at all.\n\n"
        "Deliberately independent of Firestore. A liveness probe that failed "
        "during a database outage would make the orchestrator restart-loop "
        "every instance over something a restart cannot fix."
    ),
)
async def health_live() -> Dict[str, Any]:
    return liveness()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Should this instance receive traffic? Round-trips Firestore and "
        "returns **503** when a required dependency is down — including when "
        "the backend has fallen back to the in-memory mock database, which "
        "accepts writes and loses them on restart.\n\n"
        "A degraded *optional* dependency (Gemini, Twilio) does not fail "
        "readiness: taking an instance out of rotation because SMS is "
        "unconfigured would remove the whole app to protect one feature."
    ),
    responses={503: {"description": "A required dependency is unavailable."}},
)
async def health_ready(response: Response) -> Dict[str, Any]:
    report = run_checks()

    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": report.status,
        "ready": report.ready,
        "checkedAt": _checked_at(),
        "components": [component.to_dict() for component in report.components],
    }
