"""
Cycle Tracking routes.
Handles cycle log submission and retrieval.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import date

router = APIRouter()


class CycleLog(BaseModel):
    user_id: str
    start_date: date
    end_date: Optional[date] = None
    flow_intensity: Optional[str] = None   # "light", "medium", "heavy"
    mood: Optional[str] = None
    symptoms: Optional[list[str]] = []
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None     # 1–5
    notes: Optional[str] = None


@router.post("/log")
async def log_cycle(data: CycleLog):
    """
    Log a new cycle entry.
    TODO: Persist to Firestore and trigger CVI/MHS recalculation.
    """
    # Placeholder — Firestore write will go here
    return {"status": "logged", "data": data.model_dump()}


@router.get("/{user_id}/history")
async def get_cycle_history(user_id: str, limit: int = 12):
    """
    Retrieve cycle history for a user.
    TODO: Fetch from Firestore.
    """
    return {"user_id": user_id, "cycles": [], "message": "Firestore integration coming soon"}
