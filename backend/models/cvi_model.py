"""
Cycle Variability Index (CVI) Model
Score: 0–100. Higher = more irregular / higher hormonal variability.

Input features per cycle:
- cycle_length (int): days between period start dates
- flow_duration (int): days of bleeding
- flow_intensity (int): 1=light, 2=medium, 3=heavy
- symptom_count (int): number of symptoms logged
- stress_avg (float): average stress 1–5 over cycle
- sleep_avg (float): average sleep hours over cycle

The model is trained offline with XGBoost and exported via joblib.
This module loads the saved model and exposes a predict() function.
"""

import os
import numpy as np
from typing import Optional

# Lazy-load the model to avoid import-time overhead
_model = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "cvi_model.joblib")


def _load_model():
    global _model
    if _model is None:
        try:
            import joblib
            _model = joblib.load(_MODEL_PATH)
        except FileNotFoundError:
            _model = None  # Model not yet trained — use heuristic fallback
    return _model


def predict_cvi(cycle_logs: list[dict]) -> Optional[float]:
    """
    Predict the CVI score (0–100) from a list of recent cycle logs.
    Requires at least 3 cycle logs for a meaningful score.

    Returns None if there is insufficient data.
    """
    if len(cycle_logs) < 3:
        return None

    # Extract features from the last 6 cycles (or fewer if not available)
    recent = cycle_logs[:6]
    lengths = [log.get("cycle_length", 28) for log in recent]
    flows = [log.get("flow_duration", 5) for log in recent]
    stresses = [log.get("stress_avg", 2.5) for log in recent]
    sleeps = [log.get("sleep_avg", 7.0) for log in recent]

    # Feature vector
    features = np.array([[
        np.mean(lengths),
        np.std(lengths),
        np.mean(flows),
        np.std(flows),
        max(lengths) - min(lengths),  # cycle length range
        np.mean(stresses),
        np.mean(sleeps),
        len(recent),
    ]])

    model = _load_model()

    if model is not None:
        # Use the trained XGBoost model
        raw = float(model.predict(features)[0])
        return max(0.0, min(100.0, raw))
    else:
        # Heuristic fallback until model is trained
        std_dev = float(np.std(lengths))
        # High std dev → high CVI
        heuristic_cvi = min(100.0, std_dev * 8 + 30)
        return round(heuristic_cvi, 1)


def risk_level(cvi: float) -> str:
    """Map a CVI score to a risk tier."""
    if cvi < 30:
        return "low"
    elif cvi < 65:
        return "medium"
    else:
        return "high"
