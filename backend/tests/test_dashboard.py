import pytest
from datetime import date
from unittest.mock import patch
from test_auth import client, mock_auth_dependencies
import firebase_admin.auth
from services.scoring_service import build_model_features

@pytest.fixture(autouse=True)
def _clear_client_state():
    client.cookies.clear()

@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )
    token = token_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_cycle_service():
    # CycleService now lives behind services.scoring_service (the shared
    # source of truth for /dashboard and /insights/{user_id}/scores),
    # not api.dashboard directly — see services/scoring_service.py.
    with patch("services.scoring_service.CycleService") as MockCycleService:
        yield MockCycleService

@pytest.fixture
def mock_cvi():
    with patch("services.scoring_service.predict_cvi") as mock:
        mock.return_value = 0.5
        yield mock

@pytest.fixture
def mock_mhs():
    with patch("services.scoring_service.predict_mhs") as mock:
        mock.return_value = 8.0
        yield mock

def test_build_model_features_month_boundaries():
    logs = [
        {"start_date": date(2026, 3, 1), "end_date": date(2026, 3, 5), "flow_intensity": "heavy"},
        {"start_date": date(2026, 1, 31), "end_date": date(2026, 2, 4), "flow_intensity": "medium"},
    ]
    features = build_model_features(logs)
    assert len(features) == 2
    assert features[0]["cycle_length"] == 29
    assert features[0]["flow_duration"] == 5
    assert features[0]["flow_intensity"] == 3
    assert features[1]["cycle_length"] == 28 # default for oldest

def test_build_model_features_year_transitions():
    logs = [
        {"start_date": date(2026, 1, 5), "end_date": date(2026, 1, 9)},
        {"start_date": date(2025, 12, 10), "end_date": date(2025, 12, 14)},
    ]
    features = build_model_features(logs)
    assert features[0]["cycle_length"] == 26
    
def test_build_model_features_leap_year():
    logs = [
        {"start_date": date(2024, 3, 1), "end_date": date(2024, 3, 5)},
        {"start_date": date(2024, 2, 1), "end_date": date(2024, 2, 5)},
    ]
    features = build_model_features(logs)
    assert features[0]["cycle_length"] == 29
    
def test_build_model_features_single_cycle():
    logs = [
        {"start_date": date(2026, 5, 1), "end_date": date(2026, 5, 5)},
    ]
    features = build_model_features(logs)
    assert features[0]["cycle_length"] == 28

def test_build_model_features_long_history():
    logs = [
        {"start_date": date(2026, 5, 1)},
        {"start_date": date(2026, 4, 1)},
        {"start_date": date(2026, 3, 1)},
        {"start_date": date(2026, 2, 1)},
        {"start_date": date(2026, 1, 1)},
    ]
    features = build_model_features(logs)
    assert len(features) == 5
    assert features[0]["cycle_length"] == 30
    assert features[1]["cycle_length"] == 31
    
def test_build_model_features_empty_history():
    assert build_model_features([]) == []
    
def test_build_model_features_invalid_date_input():
    logs = [
        {"start_date": "not-a-date", "end_date": None},
        {"start_date": None}
    ]
    features = build_model_features(logs)
    assert len(features) == 2
    assert features[0]["cycle_length"] == 28
    assert features[0]["flow_duration"] == 5

import datetime

class MockDate(datetime.date):
    @classmethod
    def today(cls):
        return datetime.date(2026, 5, 10)

@patch("api.dashboard.date", MockDate)
def test_dashboard_api_success(auth_headers, mock_cycle_service, mock_cvi, mock_mhs):
    mock_cycle_service.get_logs_for_user.return_value = [
        {"start_date": MockDate(2026, 5, 1), "end_date": MockDate(2026, 5, 5), "sleep_hours": 8, "symptoms": ["cramps"]},
        {"start_date": MockDate(2026, 4, 1), "end_date": MockDate(2026, 4, 5), "sleep_hours": 6, "symptoms": ["headache"]},
        {"start_date": MockDate(2026, 3, 1), "end_date": MockDate(2026, 3, 5), "sleep_hours": 7, "symptoms": ["cramps", "bloating"]},
    ]
    response = client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["cycle"]["day"] == 10
    assert data["cycle"]["total"] == 30
    # Factual cycle stats computed from the 3 logs
    assert data["insights"]["averageCycleLength"] == 30.5
    assert data["insights"]["shortestCycleLength"] == 30
    assert data["insights"]["longestCycleLength"] == 31
    assert data["insights"]["averageBleedingDuration"] == 5.0
    assert data["insights"]["sleepHours"] == "7.0h"
    assert data["hasEnoughDataForInsights"] is True
    assert data["loggedCycleCount"] == 3
    assert "cramps" in data["symptomFrequency"]

def test_dashboard_api_empty_data(auth_headers, mock_cycle_service, mock_cvi, mock_mhs):
    mock_cycle_service.get_logs_for_user.return_value = []
    response = client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["cycle"]["day"] is None
    assert data["loggedCycleCount"] == 0
    assert data["hasEnoughDataForInsights"] is False

def test_dashboard_validation_failures():
    client.cookies.clear()
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401