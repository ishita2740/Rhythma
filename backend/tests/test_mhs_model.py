import pytest
from unittest.mock import patch
from models.mhs_model import predict_mhs, mhs_label, _compute_lifestyle_score

@pytest.fixture(autouse=True)
def mock_cvi_no_model():
    """Ensure the XGBoost model in CVI is not loaded to test the heuristic fallback deterministically."""
    with patch("models.cvi_model._load_model", return_value=None):
        yield

def test_predict_mhs_insufficient_data():
    """MHS requires at least 2 logs."""
    assert predict_mhs([]) is None
    assert predict_mhs([{}]) is None

def test_predict_mhs_two_logs():
    """With exactly 2 logs, CVI cannot be calculated, so CVI defaults to 50.
    cvi_score = 100 - 50 = 50. 50 * 0.30 = 15.0
    sleep: 8.0 -> score 100 -> 20.0
    stress: 1.0 -> score 100 -> 20.0
    symptoms: 0 -> score 100 -> 15.0
    lifestyle: 70 -> score 70 -> 10.5
    Total: 80.5
    """
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 2
    assert predict_mhs(logs) == 80.5

def test_predict_mhs_happy_path():
    """Optimal values across 3 logs.
    cvi = 30.0 -> score 70.0 -> 21.0
    sleep = 8.0 -> score 100 -> 20.0
    stress = 1.0 -> score 100 -> 20.0
    symptoms = 0 -> score 100 -> 15.0
    lifestyle = 70.0 -> 10.5
    Total: 86.5
    """
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    assert predict_mhs(logs) == 86.5

def test_predict_mhs_missing_optional_fields():
    """Missing fields should use defaults.
    CVI: lengths default to 28 -> cvi=30.0 -> score 70.0 -> 21.0
    Sleep: default 7.0 -> score max(0, 100 - 1*15) = 85.0 -> 17.0
    Stress: default 2.5 -> score max(0, 100 - 1.5*25) = 62.5 -> 12.5
    Symptoms: default 0 -> score 100.0 -> 15.0
    Lifestyle: 10.5
    Total: 21.0 + 17.0 + 12.5 + 15.0 + 10.5 = 76.0
    """
    logs = [{}, {}, {}]
    assert predict_mhs(logs) == 76.0

def test_predict_mhs_worst_case():
    """Values resulting in minimum possible score.
    CVI: high variance (lengths 14 and 42) -> 100.0 -> cvi_score 0.0 -> 0.0
    Sleep: 24.0 -> max(0, 100 - 16*15) = 0.0 -> 0.0
    Stress: 5.0 -> max(0, 100 - 4*25) = 0.0 -> 0.0
    Symptoms: 10 -> max(0, 100 - 100) = 0.0 -> 0.0
    Lifestyle: 70.0 -> 10.5
    Total: 10.5
    """
    logs = [
        {"cycle_length": 14, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10},
        {"cycle_length": 42, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10},
        {"cycle_length": 14, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10}
    ]
    assert predict_mhs(logs) == 10.5

def test_predict_mhs_zero_values():
    """Zeros for sleep and stress.
    CVI: 28 -> cvi=30.0 -> score 70.0 -> 21.0
    Sleep: 0.0 -> max(0, 100 - 8*15) = 0.0 -> 0.0
    Stress: 0.0 -> max(0, 100 - (-1)*25) = 125.0 -> 25.0 (wait, is it capped at 100? No, max(0, 100 - (stress_avg - 1)*25) has no upper bound clamp before the final weighted sum clamp). 
    Let's calculate: stress_score = 100 - (0-1)*25 = 125.0 -> 125 * 0.20 = 25.0
    Symptoms: 0 -> score 100 -> 15.0
    Lifestyle: 70.0 -> 10.5
    Total: 21.0 + 0.0 + 25.0 + 15.0 + 10.5 = 71.5
    """
    logs = [{"cycle_length": 28, "sleep_avg": 0.0, "stress_avg": 0.0, "symptom_count": 0}] * 3
    assert predict_mhs(logs) == 71.5

def test_mhs_label():
    assert mhs_label(0.0) == "Needs attention"
    assert mhs_label(49.9) == "Needs attention"
    assert mhs_label(50.0) == "Fair"
    assert mhs_label(74.9) == "Fair"
    assert mhs_label(75.0) == "Good"
    assert mhs_label(100.0) == "Good"


# ── Lifestyle score tests ─────────────────────────────────────────────────

def test_lifestyle_fallback_default():
    """No profile returns the default fallback of 70.0."""
    assert _compute_lifestyle_score(None) == 70.0


def test_lifestyle_fallback_empty_profile():
    """Empty profile returns neutral 50 (unknown exercise + unknown diet)."""
    assert _compute_lifestyle_score({}) == 50.0


def test_lifestyle_daily_balanced():
    """Daily exercise + balanced diet = perfect 100."""
    profile = {"exercise_frequency": "daily", "diet_type": "balanced"}
    assert _compute_lifestyle_score(profile) == 100.0


def test_lifestyle_weekly_vegetarian():
    """Weekly exercise + vegetarian diet = (70+80)/2 = 75."""
    profile = {"exercise_frequency": "weekly", "diet_type": "vegetarian"}
    assert _compute_lifestyle_score(profile) == 75.0


def test_lifestyle_rarely_vegan():
    """Rarely exercise + vegan diet = (30+70)/2 = 50."""
    profile = {"exercise_frequency": "rarely", "diet_type": "vegan"}
    assert _compute_lifestyle_score(profile) == 50.0


def test_lifestyle_never_high_protein():
    """Never exercise + high protein diet = (0+80)/2 = 40."""
    profile = {"exercise_frequency": "never", "diet_type": "high_protein"}
    assert _compute_lifestyle_score(profile) == 40.0


def test_lifestyle_unknown_values():
    """Unrecognised values get the default 50 each, so (50+50)/2 = 50."""
    profile = {"exercise_frequency": "extreme", "diet_type": "paleo"}
    assert _compute_lifestyle_score(profile) == 50.0


def test_lifestyle_partial_only_exercise():
    """Only exercise_frequency present; diet_type missing defaults to 50."""
    profile = {"exercise_frequency": "daily"}
    assert _compute_lifestyle_score(profile) == 75.0


def test_lifestyle_partial_only_diet():
    """Only diet_type present; exercise_frequency missing defaults to 50."""
    profile = {"diet_type": "balanced"}
    assert _compute_lifestyle_score(profile) == 75.0


def test_predict_mhs_with_profile():
    """MHS with full profile data.
    cvi = 30.0 -> score 70.0 -> 21.0
    sleep = 8.0 -> score 100 -> 20.0
    stress = 1.0 -> score 100 -> 20.0
    symptoms = 0 -> score 100 -> 15.0
    lifestyle = 100.0 -> 15.0  (daily exercise + balanced diet)
    Total: 91.0
    """
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    profile = {"exercise_frequency": "daily", "diet_type": "balanced"}
    assert predict_mhs(logs, profile=profile) == 91.0


def test_predict_mhs_with_profile_no_lifestyle_fields():
    """MHS with profile missing lifestyle keys uses neutral 50 for lifestyle.
    cvi = 30.0 -> score 70.0 -> 21.0
    sleep = 8.0 -> score 100 -> 20.0
    stress = 1.0 -> score 100 -> 20.0
    symptoms = 0 -> score 100 -> 15.0
    lifestyle = 50.0 (neutral) -> 7.5
    Total: 83.5
    """
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    profile = {"age": 25, "city": "Delhi"}
    assert predict_mhs(logs, profile=profile) == 83.5
