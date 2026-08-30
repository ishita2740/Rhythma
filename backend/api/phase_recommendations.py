"""Cycle Phase Wellness Advisor API routes.

Endpoints for retrieving phase-aware wellness recommendations
for sleep, nutrition, exercise, and self-care.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services import phase_recommendations_service as svc

router = APIRouter(tags=["Phase Recommendations"])


# ─── Response models ─────────────────────────────────────────────────────────


class RecommendationItem(BaseModel):
    title: str
    body: str
    tipKey: str


class CategoryResponse(BaseModel):
    phase: str
    category: str
    recommendations: List[RecommendationItem]
    disclaimer: str
    disclaimerKey: str


class AllRecommendationsResponse(BaseModel):
    phase: str
    categories: Dict[str, List[RecommendationItem]]
    disclaimer: str
    disclaimerKey: str


class PhaseOverview(BaseModel):
    phase: str
    categories: Dict[str, List[RecommendationItem]]


class PhasesSummaryResponse(BaseModel):
    phases: Dict[str, Dict[str, List[RecommendationItem]]]
    phaseOrder: List[str]
    disclaimer: str
    disclaimerKey: str


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get(
    "/phase-recommendations",
    response_model=AllRecommendationsResponse,
    summary="Get all wellness recommendations for the current phase",
    description=(
        "Returns sleep, nutrition, exercise, and self-care recommendations "
        "tailored to the user's current menstrual cycle phase, detected from "
        "their logged data. Not medical advice."
    ),
)
async def get_all_recommendations(
    current_user: dict = Depends(get_current_user),
):
    return svc.get_all_recommendations(current_user["id"])


@router.get(
    "/phase-recommendations/{category}",
    response_model=CategoryResponse,
    summary="Get recommendations for one category",
    description=(
        "Returns phase-aware recommendations for a single wellness category: "
        "sleep, nutrition, exercise, or self_care."
    ),
)
async def get_category_recommendations(
    category: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        return svc.get_category_recommendations(current_user["id"], category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/phase-recommendations/phases/overview",
    response_model=PhasesSummaryResponse,
    summary="Static overview of all phases and their recommendations",
    description=(
        "Returns recommendations for every cycle phase without requiring "
        "user data. Useful for onboarding education or an informational page."
    ),
)
async def get_phases_overview(
    current_user: dict = Depends(get_current_user),
):
    return svc.get_all_phases_summary()
