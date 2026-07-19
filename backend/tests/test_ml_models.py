import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# Ensure backend directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.cvi_model import predict_cvi
from models.mhs_model import predict_mhs

# Mock cycle logs (5 cycles)
MOCK_LOGS = [
    {"cycle_length": 28, "flow_duration": 5, "flow_intensity": 2, "symptom_count": 1, "stress_avg": 2.0, "sleep_avg": 8.0},
    {"cycle_length": 29, "flow_duration": 4, "flow_intensity": 2, "symptom_count": 0, "stress_avg": 3.0, "sleep_avg": 7.0},
    {"cycle_length": 27, "flow_duration": 5, "flow_intensity": 3, "symptom_count": 2, "stress_avg": 2.0, "sleep_avg": 8.0},
    {"cycle_length": 28, "flow_duration": 6, "flow_intensity": 1, "symptom_count": 1, "stress_avg": 1.0, "sleep_avg": 9.0},
    {"cycle_length": 28, "flow_duration": 5, "flow_intensity": 2, "symptom_count": 0, "stress_avg": 2.0, "sleep_avg": 8.0},
]

def test_cvi_heuristic_fallback():
    # Force _load_model to return None
    with patch("models.cvi_model._load_model", return_value=None):
        score = predict_cvi(MOCK_LOGS)
        assert score is not None
        # Heuristic CVI calculation:
        # std_dev of lengths: std_dev([28, 29, 27, 28, 28])
        # lengths = [28, 29, 27, 28, 28]
        # mean = 28.0. std_dev = sqrt((0 + 1 + 1 + 0 + 0)/5) = sqrt(0.4) ≈ 0.63245
        # heuristic = min(100.0, 0.63245 * 8 + 30) ≈ 35.059
        # expected round(heuristic, 1) = 35.1
        assert round(score, 1) == 35.1

def test_mhs_heuristic_fallback():
    # Force _load_model to return None for both CVI and MHS
    with patch("models.cvi_model._load_model", return_value=None), \
         patch("models.mhs_model._load_model", return_value=None):
        score = predict_mhs(MOCK_LOGS)
        assert score is not None
        # Verify it falls back and returns a valid score
        assert 0.0 <= score <= 100.0

def test_cvi_trained_model_mocked():
    # Mock the XGBoost model to return a fixed prediction
    mock_model = MagicMock()
    mock_model.predict.return_value = [55.5]
    
    with patch("models.cvi_model._load_model", return_value=mock_model):
        score = predict_cvi(MOCK_LOGS)
        assert score == 55.5
        mock_model.predict.assert_called_once()

def test_mhs_trained_model_mocked():
    # Mock the Logistic Regression model to return a fixed probability
    mock_model = MagicMock()
    # predict_proba returns a 2D array, e.g., [[prob_class_0, prob_class_1]]
    mock_model.predict_proba.return_value = [[0.2, 0.8]]
    
    with patch("models.cvi_model._load_model", return_value=None), \
         patch("models.mhs_model._load_model", return_value=mock_model):
        score = predict_mhs(MOCK_LOGS)
        assert score == 80.0
        mock_model.predict_proba.assert_called_once()

def test_insufficient_data():
    # CVI requires >= 3 logs
    assert predict_cvi(MOCK_LOGS[:2]) is None
    # MHS requires >= 2 logs
    assert predict_mhs(MOCK_LOGS[:1]) is None

def test_cvi_real_model():
    score = predict_cvi(MOCK_LOGS)
    assert score is not None
    assert 0.0 <= score <= 100.0

def test_mhs_real_model():
    score = predict_mhs(MOCK_LOGS)
    assert score is not None
    assert 0.0 <= score <= 100.0
