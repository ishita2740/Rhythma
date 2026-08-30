"""Symptom Pattern Analyzer API routes.

Endpoints for logging symptom entries, querying history, and retrieving
pattern reports (frequency, severity trends, co-occurrence, triggers).
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services import symptom_journal_service as svc

router = APIRouter(tags=["Symptom Journal"])


# ─── Models ──────────────────────────────────────────────────────────────────


class EntryCreateRequest(BaseModel):
    symptom: str
    severity: str = Field(..., description="mild, moderate, or severe")
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    location: Optional[str] = Field(None, max_length=100)
    triggers: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=500)
    mood_score: Optional[int] = Field(None, ge=1, le=5)


class EntryResponse(BaseModel):
    id: str
    symptom: str
    severity: str
    date: str
    location: Optional[str] = None
    triggers: List[str] = []
    notes: str = ""
    mood_score: Optional[int] = None


class FrequencyItem(BaseModel):
    symptom: str
    count: int
    percentage: int


class FrequencyResponse(BaseModel):
    days: int
    total_entries: int
    symptoms: List[FrequencyItem]


class SeverityTrendWeek(BaseModel):
    week: str
    avg_severity: float
    entries: int


class SeverityTrendResponse(BaseModel):
    symptom: str
    days: int
    direction: str
    weekly_trend: List[SeverityTrendWeek]


class CoOccurrencePair(BaseModel):
    symptom_a: str
    symptom_b: str
    co_occurring_days: int


class CoOccurrenceResponse(BaseModel):
    days: int
    total_days_logged: int
    top_pairs: List[CoOccurrencePair]


class TriggerItem(BaseModel):
    trigger: str
    count: int
    percentage: int


class TriggerAnalysisResponse(BaseModel):
    days: int
    symptom_filter: Optional[str] = None
    total_entries: int
    triggers: List[TriggerItem]


# ─── Entry CRUD ──────────────────────────────────────────────────────────────


@router.post(
    "/symptom-journal/entries",
    response_model=EntryResponse,
    status_code=201,
    summary="Log a symptom entry",
)
async def create_entry(
    body: EntryCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        target_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        return svc.create_entry(
            user_id=current_user["id"],
            symptom=body.symptom,
            severity=body.severity,
            entry_date=target_date,
            location=body.location,
            triggers=body.triggers,
            notes=body.notes,
            mood_score=body.mood_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/symptom-journal/entries",
    response_model=List[EntryResponse],
    summary="List symptom entries with optional filters",
)
async def list_entries(
    limit: int = 50,
    symptom: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    return svc.list_entries(current_user["id"], limit=limit, symptom=symptom, start_date=sd, end_date=ed)


@router.get(
    "/symptom-journal/entries/{entry_id}",
    response_model=EntryResponse,
    summary="Get a single symptom entry",
)
async def get_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    entry = svc.get_entry(current_user["id"], entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete(
    "/symptom-journal/entries/{entry_id}",
    status_code=204,
    summary="Delete a symptom entry",
)
async def delete_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    if not svc.delete_entry(current_user["id"], entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")


# ─── Pattern Analysis ────────────────────────────────────────────────────────


@router.get(
    "/symptom-journal/reports/frequency",
    response_model=FrequencyResponse,
    summary="Symptom frequency report",
)
async def get_frequency(
    days: int = 90,
    current_user: dict = Depends(get_current_user),
):
    return svc.frequency_report(current_user["id"], days=days)


@router.get(
    "/symptom-journal/reports/severity-trend",
    response_model=SeverityTrendResponse,
    summary="Weekly severity trend for one symptom",
)
async def get_severity_trend(
    symptom: str,
    days: int = 60,
    current_user: dict = Depends(get_current_user),
):
    return svc.severity_trend(current_user["id"], symptom=symptom, days=days)


@router.get(
    "/symptom-journal/reports/co-occurrence",
    response_model=CoOccurrenceResponse,
    summary="Symptoms that co-occur on the same days",
)
async def get_co_occurrence(
    days: int = 90,
    current_user: dict = Depends(get_current_user),
):
    return svc.co_occurrence(current_user["id"], days=days)


@router.get(
    "/symptom-journal/reports/triggers",
    response_model=TriggerAnalysisResponse,
    summary="Trigger frequency analysis",
)
async def get_triggers(
    symptom: Optional[str] = None,
    days: int = 90,
    current_user: dict = Depends(get_current_user),
):
    return svc.trigger_analysis(current_user["id"], symptom=symptom, days=days)
