"""
Menstrual Health Score (MHS) Model
Score: 0–100. Higher = better holistic menstrual health.

Composite of:
  - CVI (cycle variability)    — 30% weight
  - Sleep quality              — 20% weight
  - Stress levels              — 20% weight
  - Symptom severity           — 15% weight
  - Lifestyle (exercise/diet)  — 15% weight

The full model is a Logistic Regression ensemble trained on
anonymized synthetic data. This module provides the scoring logic
and a placeholder for the trained .joblib artifact.
"""

from typing import Optional
from .cvi_model import predict_cvi


def predict_mhs(cycle_logs: list[dict], profile: Optional[dict] = None) -> Optional[float]:
    """
    Predict the Menstrual Health Score (0–100) for a user.

    Args:
        cycle_logs: List of recent cycle log dicts (most recent first).
        profile:    Optional user profile with lifestyle attributes.

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

    # 5. Lifestyle placeholder (will use profile data when available)
    lifestyle_score = 70.0  # Default until tracking is wired

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
