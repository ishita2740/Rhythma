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

import os
import numpy as np
from typing import Optional
from .cvi_model import predict_cvi

# Lazy-load the model to avoid import-time overhead
_model = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "mhs_model.joblib")


def _load_model():
    global _model
    if _model is None:
        try:
            import joblib
            _model = joblib.load(_MODEL_PATH)
        except Exception:
            _model = None  # Model not yet trained — use heuristic fallback
    return _model


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

    # Check if we can use the trained model
    model = _load_model()
    if model is not None:
        try:
            import pandas as pd
            features = pd.DataFrame([[
                cvi_score,
                sleep_score,
                stress_score,
                symptom_score,
                lifestyle_score
            ]], columns=[
                'cvi_score', 'sleep_score', 'stress_score', 'symptom_score', 'lifestyle_score'
            ])
            prob_healthy = float(model.predict_proba(features)[0][1])
            return round(prob_healthy * 100, 1)
        except Exception:
            pass  # Fall back to heuristic if inference fails

    # Weighted composite fallback
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
