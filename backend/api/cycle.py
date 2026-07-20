from fastapi import APIRouter, Depends, HTTPException, status
from core.auth import get_current_user
from pydantic import BaseModel
from datetime import date
from typing import Optional, List

from services.firestore_service import CycleService

# ─── Pydantic Model ──────────────────────────────────────────────────────────
class CycleLog(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None


# ─── Router ──────────────────────────────────────────────────────────────────
router = APIRouter(tags=["Cycle Tracking"])

@router.post("/log")
async def log_cycle(
    log: CycleLog,
    current_user: dict = Depends(get_current_user)
):
    """Persists a cycle log entry for `log.start_date`.

    Used both by the Home screen's quick-log tiles (which send a partial
    CycleLog — just the one field being tapped, e.g. only
    `flow_intensity` set) and the Cycle screen's "Save" button (which sends
    a full CycleLog with everything the user selected for that day).
    Either way this upserts *that day's* single document rather than
    creating a new one per call — see CycleService.upsert_log for why.
    """
    user_id = current_user["id"]
    # Only send along fields the caller actually set, so a partial (Home
    # quick-log) submission doesn't overwrite the rest of the day's
    # already-saved fields with nulls.
    fields = {k: v for k, v in log.model_dump().items() if k != "start_date" and v is not None}
    log_id = CycleService.upsert_log(user_id, log.start_date, fields)
    return {
        "message": f"Cycle logged for user {user_id}",
        "id": log_id,
        "data": log.model_dump()
    }

@router.get("/{user_id}/history")
async def get_cycle_history(
    user_id: str,
    limit: Optional[int] = 10,        # <-- Added back with default 10
    current_user: dict = Depends(get_current_user)
):
    if user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's data"
        )
    entries = CycleService.get_logs_for_user(user_id, limit=limit or 10)
    return {"message": f"History for user {user_id}", "entries": entries}