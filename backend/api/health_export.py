"""Health Export Summary API routes.

Endpoints for generating structured health reports suitable for
sharing with healthcare providers or for personal records.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from core.auth import get_current_user
from services import health_export_service as svc

router = APIRouter(tags=["Health Export"])


# ─── Response models ─────────────────────────────────────────────────────────


class CycleStatsModel(BaseModel):
    averageCycleLength: Optional[float] = None
    shortestCycleLength: Optional[int] = None
    longestCycleLength: Optional[int] = None
    averageBleedingDuration: Optional[float] = None
    loggedCycleCount: int = 0
    hasEnoughData: bool = False


class SleepStressSummary(BaseModel):
    average: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    sampleCount: int = 0


class MoodSummaryModel(BaseModel):
    average: Optional[float] = None
    sampleCount: int = 0


class BleedingPatternModel(BaseModel):
    distribution: Dict[str, int] = {}
    totalBleedingDays: int = 0


class TrendStatementModel(BaseModel):
    metric: str = ""
    direction: str = ""
    key: str = ""
    text: str = ""
    evidence: Dict[str, Any] = {}


class TrendsModel(BaseModel):
    basis: Optional[str] = None
    notEnoughData: bool = True
    statements: List[TrendStatementModel] = []


class ExportSummaryResponse(BaseModel):
    generatedAt: str
    user: Dict[str, Any]
    dateRange: Optional[Dict[str, str]] = None
    cycleStatistics: CycleStatsModel
    symptomFrequency: Dict[str, float] = {}
    sleepSummary: SleepStressSummary
    stressSummary: SleepStressSummary
    moodSummary: MoodSummaryModel
    bleedingPattern: BleedingPatternModel
    trends: TrendsModel
    disclaimer: str
    disclaimerKey: str


class ProviderBriefResponse(BaseModel):
    generatedAt: str
    user: Dict[str, Any]
    dateRange: Optional[Dict[str, str]] = None
    cycleStatistics: CycleStatsModel
    symptomFrequency: Dict[str, float] = {}
    sleepAverage: Optional[float] = None
    stressAverage: Optional[float] = None
    bleedingDaysLogged: int = 0
    disclaimer: str
    disclaimerKey: str


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get(
    "/export/summary",
    response_model=ExportSummaryResponse,
    summary="Generate a full health export summary",
    description=(
        "Returns a structured health report with cycle statistics, symptom "
        "frequencies, sleep/stress/mood summaries, bleeding patterns, and "
        "trend comparisons. Designed for sharing with healthcare providers "
        "or for personal records."
    ),
)
async def get_export_summary(
    current_user: dict = Depends(get_current_user),
):
    return svc.generate_summary(current_user["id"])


@router.get(
    "/export/provider-brief",
    response_model=ProviderBriefResponse,
    summary="Generate a concise provider-focused brief",
    description=(
        "A shorter version of the full export, keeping only the clinical "
        "essentials: cycle stats, symptom frequencies, and sleep/stress "
        "averages. Omits raw trends and mood data."
    ),
)
async def get_provider_brief(
    current_user: dict = Depends(get_current_user),
):
    return svc.generate_provider_brief(current_user["id"])
