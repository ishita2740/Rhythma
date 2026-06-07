"""
Insights routes.
Returns CVI (Cycle Variability Index) and MHS (Menstrual Health Score).
"""

from fastapi import APIRouter
router = APIRouter()


@router.get("/{user_id}/scores")
async def get_scores(user_id: str):
    """
    Returns the latest CVI and MHS scores for a user.
    TODO: Run XGBoost + Logistic Regression models on stored cycle data.
    """
    return {
        "user_id": user_id,
        "cvi": None,
        "mhs": None,
        "risk_level": None,   # "low", "medium", "high"
        "message": "ML model integration coming soon",
    }
