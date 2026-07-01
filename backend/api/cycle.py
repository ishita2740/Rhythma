"""
Cycle Tracking routes.
Handles cycle log submission, retrieval, and basic analytics.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
import firebase_admin
from firebase_admin import firestore

router = APIRouter()
db = firestore.client()

class CycleLog(BaseModel):
    user_id: str
    start_date: date
    end_date: Optional[date] = None
    flow_intensity: Optional[str] = Field(None, pattern="^(light|medium|heavy)$")
    mood: Optional[str] = None
    symptoms: List[str] = []
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    stress_level: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None

@router.post("/log")
async def log_cycle(data: CycleLog):
    """
    Log a new cycle entry to Firestore.
    """
    try:
        # Prepare data for Firestore (convert dates to datetime objects/strings)
        log_data = data.model_dump()
        log_data["start_date"] = datetime.combine(data.start_date, datetime.min.time())
        if data.end_date:
            log_data["end_date"] = datetime.combine(data.end_date, datetime.min.time())

        log_data["created_at"] = firestore.SERVER_TIMESTAMP

        # Store in user's sub-collection
        doc_ref = db.collection("users").document(data.user_id).collection("cycle_logs").document()
        doc_ref.set(log_data)

        # TODO: Trigger MHS (Mental Health Score) update based on mood/stress

        return {
            "status": "success",
            "log_id": doc_ref.id,
            "message": "Cycle data recorded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log cycle: {str(e)}")
@router.get("/{user_id}/history")
async def get_cycle_history(user_id: str, limit: int = 12):
    """
    Retrieve recent cycle history for a user.
    """
    try:
        logs_ref = db.collection("users").document(user_id).collection("cycle_logs")
        query = logs_ref.order_by("start_date", direction=firestore.Query.DESCENDING).limit(limit)

        docs = query.stream()
        history = []

        for doc in docs:
            log = doc.to_dict()
            # Convert timestamps back to strings for JSON serializability
            if "start_date" in log and log["start_date"]:
                log["start_date"] = log["start_date"].date().isoformat()
            if "end_date" in log and log["end_date"]:
                log["end_date"] = log["end_date"].date().isoformat()
            if "created_at" in log and log["created_at"]:
                log["created_at"] = log["created_at"].isoformat()

            log["id"] = doc.id
            history.append(log)

        return {
            "user_id": user_id,
            "count": len(history),
            "cycles": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")

@router.get("/{user_id}/stats")
async def get_cycle_stats(user_id: str):
    """
    Calculates simple statistics like average cycle length.
    """
    # Logic to fetch last 3 cycles and calculate average gap
    # This is a placeholder for more advanced analytics
    return {"user_id": user_id, "average_cycle_length": "Calculating..."}

