from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user

router = APIRouter(tags=["Insights"])

@router.get("/{user_id}/scores")
async def get_scores(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"message": f"Scores for user {user_id}"}