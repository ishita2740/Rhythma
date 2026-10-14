"""Cycle Comparison API routes.

Endpoints for comparing two time periods of cycle data side by side,
with structured diffs for each metric.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services import cycle_compare_service as svc

router = APIRouter(tags=["Cycle Comparison"])


# ─── Request / Response models ──────────────────────────────────────────────


class CompareRequest(BaseModel):
    period_a_start: str = Field(..., description="Earlier period start (YYYY-MM-DD)")
    period_a_end: str = Field(..., description="Earlier period end (YYYY-MM-DD)")
    period_b_start: str = Field(..., description="Comparison period start (YYYY-MM-DD)")
    period_b_end: str = Field(..., description="Comparison period end (YYYY-MM-DD)")


class PeriodStats(BaseModel):
    logCount: int = 0
    cycleLengths: List[int] = []
    averageCycleLength: Optional[float] = None
    bleedingDays: List[int] = []
    averageBleedingDuration: Optional[float] = None
    sleepAverage: Optional[float] = None
    stressAverage: Optional[float] = None
    moodAverage: Optional[float] = None
    symptomFrequency: Dict[str, float] = {}
    flowDistribution: Dict[str, int] = {}


class PeriodInfo(BaseModel):
    start: str
    end: str
    stats: PeriodStats


class ValueComparison(BaseModel):
    label: str
    periodA: Optional[float] = None
    periodB: Optional[float] = None
    delta: Optional[float] = None
    direction: str = "unknown"
    unit: Optional[str] = None


class CompareResponse(BaseModel):
    periodA: PeriodInfo
    periodB: PeriodInfo
    comparisons: List[ValueComparison]
    symptomComparisons: List[ValueComparison]
    disclaimer: str
    disclaimerKey: str


class AutoCompareResponse(CompareResponse):
    pass


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "/cycle/compare",
    response_model=CompareResponse,
    summary="Compare two custom date ranges",
    description=(
        "Compare cycle data between two user-defined periods. Returns "
        "per-period statistics and structured diffs for cycle length, "
        "bleeding, sleep, stress, mood, and symptom frequencies."
    ),
)
async def compare_custom(
    body: CompareRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        a_start = date.fromisoformat(body.period_a_start)
        a_end = date.fromisoformat(body.period_a_end)
        b_start = date.fromisoformat(body.period_b_start)
        b_end = date.fromisoformat(body.period_b_end)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    if a_start > a_end or b_start > b_end:
        raise HTTPException(status_code=400, detail="Period start must be before or equal to end.")
    if a_start >= b_start:
        raise HTTPException(status_code=400, detail="Period A must end before Period B starts.")

    return svc.compare_periods(
        current_user["id"], a_start, a_end, b_start, b_end
    )


@router.get(
    "/cycle/compare/recent",
    response_model=AutoCompareResponse,
    summary="Auto-compare recent vs prior period",
    description=(
        "Automatically compares the most recent N days against the same "
        "span immediately before it. Default window is 60 days."
    ),
)
async def compare_recent(
    window_days: int = 60,
    current_user: dict = Depends(get_current_user),
):
    if window_days < 14 or window_days > 365:
        raise HTTPException(status_code=400, detail="window_days must be between 14 and 365.")
    return svc.compare_recent_vs_prior(current_user["id"], window_days=window_days)
