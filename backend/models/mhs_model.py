"""
Menstrual Health Score (MHS) Model
Score: 0–100. Higher = better holistic menstrual health.

Composite of:
  - CVI (cycle variability)    — 30% weight
  - Sleep quality              — 20% weight
  - Stress levels              — 20% weight
  - Symptom severity           — 15% weight
  - Lifestyle (exercise/diet)  — 15% weight

The score is a weighted average of five component scores,
computed directly from cycle logs and profile data.

Planned: Replace this hand-written weighted average with a
Logistic Regression ensemble trained on anonymized synthetic
data.

Lifestyle score uses `exercise_frequency` and `diet_type` from
the user profile.  These fields need to be added to the
`UserProfileUpdate` / `UserProfileResponse` Pydantic models in
`backend/models/user.py` (tracked in issue #112).  Until then
the default fallback of 70.0 is used.
"""

from typing import Optional
from .cvi_model import predict_cvi

# ── Lifestyle score mapping ────────────────────────────────────────────
# Expected profile keys (add to UserProfileUpdate/UserProfileResponse):
#   - exercise_frequency: "daily", "weekly", "rarely", "never"
#   - diet_type:          "balanced", "vegetarian", "vegan", "high_protein"

_EXERCISE_SCORES = {
    "daily": 100.0,
    "weekly": 70.0,
    "rarely": 30.0,
    "never": 0.0,
}

_DIET_SCORES = {
    "balanced": 100.0,
    "vegetarian": 80.0,
    "vegan": 70.0,
    "high_protein": 80.0,
}

_DEFAULT_EXERCISE_SCORE = 50.0
_DEFAULT_DIET_SCORE = 50.0
_FALLBACK_LIFESTYLE_SCORE = 70.0


def _compute_lifestyle_score(profile: Optional[dict]) -> float:
    """Compute the lifestyle component score (0–100) from profile data.

    Uses `exercise_frequency` and `diet_type` values from the profile
    dict.  Falls back to sensible defaults when the profile or its
    relevant keys are missing.

    Mapping:
        exercise_frequency | score
        -------------------+-------
        daily              | 100
        weekly             |  70
        rarely             |  30
        never              |   0
        missing/unknown    |  50

        diet_type      | score
        ---------------+-------
        balanced       | 100
        vegetarian     |  80
        vegan          |  70
        high_protein   |  80
        missing/unknown|  50

    Composite: (exercise_score + diet_score) / 2
    """
    if profile is None:
        return _FALLBACK_LIFESTYLE_SCORE

    exercise_score = _EXERCISE_SCORES.get(
        profile.get("exercise_frequency"), _DEFAULT_EXERCISE_SCORE
    )
    diet_score = _DIET_SCORES.get(
        profile.get("diet_type"), _DEFAULT_DIET_SCORE
    )
    return (exercise_score + diet_score) / 2.0


def predict_mhs(cycle_logs: list[dict], profile: Optional[dict] = None) -> Optional[float]:
    """
    Predict the Menstrual Health Score (0–100) for a user.

    Args:
        cycle_logs: List of recent cycle log dicts (most recent first).
        profile:    Optional user profile with lifestyle attributes
                    (exercise_frequency, diet_type).

    Returns None if there is insufficient data (< 2 logs).
    """
    if len(cycle_logs) < 2:
        return None

    recent = cycle_logs[:3]

    # Component scores (each 0–100, higher = better)

    # 1. CVI component (inverted — low variability = high score)
    cvi = predict_cvi(cycle_logs)
    cvi_score = 100 - (cvi or 50)

    # 2. Sleep score
    sleep_avg = sum(log.get("sleep_avg", 7.0) for log in recent) / len(recent)
    # Optimal is 7–9 hours; penalise deviations
    sleep_score = max(0.0, 100 - abs(sleep_avg - 8) * 15)

    # 3. Stress score (inverted)
    stress_avg = sum(log.get("stress_avg", 2.5) for log in recent) / len(recent)
    stress_score = max(0.0, 100 - (stress_avg - 1) * 25)

    # 4. Symptom severity score
    symptom_counts = [log.get("symptom_count", 0) for log in recent]
    avg_symptoms = sum(symptom_counts) / len(symptom_counts)
    symptom_score = max(0.0, 100 - avg_symptoms * 10)

    # 5. Lifestyle score from profile (falls back to 70.0 if unavailable)
    lifestyle_score = _compute_lifestyle_score(profile)

    # Weighted composite
    mhs = (
        cvi_score       * 0.30
        + sleep_score   * 0.20
        + stress_score  * 0.20
        + symptom_score * 0.15
        + lifestyle_score * 0.15
    )

    return round(max(0.0, min(100.0, mhs)), 1)


def mhs_label(score: float) -> str:
    if score >= 75:
        return "Good"
    elif score >= 50:
        return "Fair"
    else:
        return "Needs attention"
