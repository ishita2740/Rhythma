"""Health Goal Tracker API routes.

Endpoints for creating wellness goals, logging daily check-ins,
viewing streaks, and pulling a weekly completion summary.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services import goal_service

router = APIRouter(tags=["Health Goals"])


# ─── Request / Response models ──────────────────────────────────────────────


class GoalCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., description="sleep, hydration, exercise, mindfulness, nutrition, or custom")
    target_value: Optional[float] = Field(None, description="Numeric target, e.g. 7 for 7 hours")
    unit: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = Field(None, max_length=300)
    template_id: Optional[str] = Field(None, description="Predefined template id to base this goal on")


class CheckinRequest(BaseModel):
    goal_id: str
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    completed: bool = True
    actual_value: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=300)


class GoalResponse(BaseModel):
    id: str
    title: str
    category: str
    target_value: Optional[float] = None
    unit: Optional[str] = None
    description: str = ""
    template_id: Optional[str] = None
    is_active: bool = True


class GoalWithStreakResponse(GoalResponse):
    current_streak: int = 0
    longest_streak: int = 0
    total_completed: int = 0


class CheckinResponse(BaseModel):
    goal_id: str
    date: str
    completed: bool
    actual_value: Optional[float] = None
    notes: str = ""


class DailySummaryResponse(BaseModel):
    date: str
    total_goals: int
    completed_goals: int
    completion_rate: int
    checkins: List[CheckinResponse]


class StreakResponse(BaseModel):
    goal_id: str
    current_streak: int
    longest_streak: int
    total_completed: int


class GoalTemplateResponse(BaseModel):
    template_id: str
    title: str
    category: str
    description: str
    unit: str
    target_value: float
    icon: str


class WeeklySummaryGoal(BaseModel):
    goal_id: str
    title: str
    category: str
    completed_days: int
    total_days: int
    completion_rate: int


class WeeklySummaryResponse(BaseModel):
    period: dict
    goals: List[WeeklySummaryGoal]
    overall_completion_rate: int


# ─── Goal endpoints ──────────────────────────────────────────────────────────


@router.get(
    "/goals/templates",
    response_model=List[GoalTemplateResponse],
    summary="Get available goal templates",
)
async def get_goal_templates(current_user: dict = Depends(get_current_user)):
    return goal_service.GOAL_TEMPLATES


@router.post(
    "/goals",
    response_model=GoalResponse,
    status_code=201,
    summary="Create a new health goal",
)
async def create_goal(
    body: GoalCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = goal_service.create_goal(
            user_id=current_user["id"],
            title=body.title,
            category=body.category,
            target_value=body.target_value,
            unit=body.unit,
            description=body.description,
            template_id=body.template_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get(
    "/goals",
    response_model=List[GoalWithStreakResponse],
    summary="List all active goals with streak info",
)
async def list_goals(current_user: dict = Depends(get_current_user)):
    goals = goal_service.list_goals(current_user["id"])
    results = []
    for goal in goals:
        streak = goal_service.compute_streak(current_user["id"], goal["id"])
        results.append({
            **goal,
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
            "total_completed": streak["total_completed"],
        })
    return results


@router.get(
    "/goals/{goal_id}",
    response_model=GoalResponse,
    summary="Get a single goal",
)
async def get_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
    goal = goal_service.get_goal(current_user["id"], goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.delete(
    "/goals/{goal_id}",
    summary="Deactivate a goal",
    status_code=204,
)
async def deactivate_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
    removed = goal_service.deactivate_goal(current_user["id"], goal_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Goal not found")


# ─── Check-in endpoints ──────────────────────────────────────────────────────


@router.post(
    "/goals/checkin",
    response_model=CheckinResponse,
    status_code=201,
    summary="Log a daily check-in for a goal",
)
async def log_checkin(
    body: CheckinRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        target_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        result = goal_service.log_checkin(
            user_id=current_user["id"],
            goal_id=body.goal_id,
            checkin_date=target_date,
            completed=body.completed,
            actual_value=body.actual_value,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get(
    "/goals/checkin/{target_date}",
    response_model=DailySummaryResponse,
    summary="Get all check-ins for a date",
)
async def get_daily_checkins(
    target_date: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        dt = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    checkins = goal_service.get_checkins_for_date(current_user["id"], dt)
    completed = sum(1 for c in checkins if c.get("completed"))
    total = len(goal_service.list_goals(current_user["id"]))
    rate = round(completed / total * 100) if total > 0 else 0

    return {
        "date": dt.isoformat(),
        "total_goals": total,
        "completed_goals": completed,
        "completion_rate": rate,
        "checkins": [
            {
                "goal_id": c["goal_id"],
                "date": c["date"],
                "completed": c["completed"],
                "actual_value": c.get("actual_value"),
                "notes": c.get("notes", ""),
            }
            for c in checkins
        ],
    }


# ─── Streak endpoint ────────────────────────────────────────────────────────


@router.get(
    "/goals/{goal_id}/streak",
    response_model=StreakResponse,
    summary="Get streak data for a goal",
)
async def get_streak(goal_id: str, current_user: dict = Depends(get_current_user)):
    goal = goal_service.get_goal(current_user["id"], goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    streak = goal_service.compute_streak(current_user["id"], goal_id)
    return {"goal_id": goal_id, **streak}


# ─── Weekly summary ──────────────────────────────────────────────────────────


@router.get(
    "/goals/summary/weekly",
    response_model=WeeklySummaryResponse,
    summary="Get weekly completion summary across all goals",
)
async def get_weekly_summary(current_user: dict = Depends(get_current_user)):
    return goal_service.weekly_summary(current_user["id"])
