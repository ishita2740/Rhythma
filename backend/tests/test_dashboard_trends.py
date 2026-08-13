import pytest
from datetime import date
from unittest.mock import patch
from test_auth import client, mock_auth_dependencies
import firebase_admin.auth


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


def test_trends_endpoint_not_enough_data(auth_headers, mock_auth_dependencies):
    with patch("services.scoring_service.CycleService") as MockCycleService:
        MockCycleService.get_logs_for_user.return_value = [{"start_date": date(2026, 5, 1)}]
        response = client.get("/api/v1/dashboard/trends", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["notEnoughData"] is True


def test_trends_endpoint_statements(auth_headers, mock_auth_dependencies):
    from api.dashboard import date as _date

    class MockDate(_date):
        @classmethod
        def today(cls):
            return date(2026, 5, 10)

    with patch("api.dashboard.date", MockDate):
        with patch("services.scoring_service.CycleService") as MockCycleService:
            MockCycleService.get_logs_for_user.return_value = [
                {"start_date": MockDate(2026, 5, 1), "end_date": MockDate(2026, 5, 5), "sleep_hours": 8, "stress_level": 3, "symptoms": ["cramps"]},
                {"start_date": MockDate(2026, 4, 1), "end_date": MockDate(2026, 4, 5), "sleep_hours": 6, "stress_level": 2, "symptoms": ["headache"]},
            ]
            response = client.get("/api/v1/dashboard/trends", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert "sleep" in data and data["sleep"] is not None
            assert "increased" in data["sleep"]
            assert "stress" in data and "increased" in data["stress"]
            assert "symptoms" in data
            assert data["symptoms"].get("cramps") is not None
