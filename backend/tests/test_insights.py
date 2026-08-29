import pytest
from datetime import date
from unittest.mock import patch
from test_auth import client, mock_auth_dependencies
import firebase_admin.auth

@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "mobile"}
    )
    token = token_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_cycle_service():
    # Insights reuses services.scoring_service (the shared source of
    # truth for /dashboard and /insights/{user_id}/scores) instead of
    # calling Firestore/CVI/MHS directly — see issue #86.
    with patch("services.scoring_service.CycleService") as MockCycleService:
        yield MockCycleService

@pytest.fixture
def mock_cvi():
    with patch("services.scoring_service.predict_cvi") as mock:
        mock.return_value = 42.0
        yield mock

@pytest.fixture
def mock_mhs():
    with patch("services.scoring_service.predict_mhs") as mock:
        mock.return_value = 77.5
        yield mock

_SAMPLE_LOGS = [
    {"start_date": date(2026, 5, 1), "end_date": date(2026, 5, 5), "sleep_hours": 8, "symptoms": ["cramps"]},
    {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 5), "sleep_hours": 6, "symptoms": ["headache"]},
    {"start_date": date(2026, 3, 1), "end_date": date(2026, 3, 5), "sleep_hours": 7, "symptoms": ["cramps", "bloating"]},
]


def test_get_scores_success(auth_headers, mock_cycle_service, mock_cvi, mock_mhs):
    mock_cycle_service.get_logs_for_user.return_value = _SAMPLE_LOGS
    response = client.get("/api/v1/insights/test-user-id-123/scores", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # Factual cycle stats computed from the 3 logs
    assert data["averageCycleLength"] == 30.5
    assert data["shortestCycleLength"] == 30
    assert data["longestCycleLength"] == 31
    assert data["averageBleedingDuration"] == 5.0
    assert data["hasEnoughDataForInsights"] is True
    assert data["loggedCycleCount"] == 3


def test_get_scores_unauthorized(auth_headers):
    response = client.get("/api/v1/insights/other-user-id/scores", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_get_scores_missing_fields(auth_headers):
    # Testing with missing user_id which is a path parameter, will result in 404
    response = client.get("/api/v1/insights//scores", headers=auth_headers)
    assert response.status_code == 404


def test_get_scores_invalid_payload():
    # Sending POST request to a GET endpoint
    response = client.post("/api/v1/insights/test-user-id-123/scores", json={"invalid": "payload"})
    assert response.status_code == 405 # Method Not Allowed


def test_get_scores_empty_history(auth_headers, mock_cycle_service, mock_cvi, mock_mhs):
    mock_cycle_service.get_logs_for_user.return_value = []
    mock_cvi.return_value = None
    mock_mhs.return_value = None
    response = client.get("/api/v1/insights/test-user-id-123/scores", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["averageCycleLength"] is None
    assert data["shortestCycleLength"] is None
    assert data["longestCycleLength"] is None
    assert data["averageBleedingDuration"] is None
    assert data["hasEnoughDataForInsights"] is False
    assert data["loggedCycleCount"] == 0


def test_dashboard_and_insights_return_identical_stats(auth_headers, mock_cycle_service, mock_cvi, mock_mhs):
    """Regression test for issue #86: /dashboard and
    /insights/{user_id}/scores must reuse the same computation and
    therefore always agree for the same user."""
    mock_cycle_service.get_logs_for_user.return_value = _SAMPLE_LOGS

    dashboard_response = client.get("/api/v1/dashboard", headers=auth_headers)
    insights_response = client.get("/api/v1/insights/test-user-id-123/scores", headers=auth_headers)

    assert dashboard_response.status_code == 200
    assert insights_response.status_code == 200

    dashboard_data = dashboard_response.json()
    insights_data = insights_response.json()

    assert dashboard_data["insights"]["averageCycleLength"] == insights_data["averageCycleLength"] == 30.5
    assert dashboard_data["insights"]["shortestCycleLength"] == insights_data["shortestCycleLength"] == 30
    assert dashboard_data["insights"]["longestCycleLength"] == insights_data["longestCycleLength"] == 31
    assert dashboard_data["insights"]["averageBleedingDuration"] == insights_data["averageBleedingDuration"] == 5.0
    assert dashboard_data["hasEnoughDataForInsights"] == insights_data["hasEnoughDataForInsights"] is True
    assert dashboard_data["loggedCycleCount"] == insights_data["loggedCycleCount"] == 3