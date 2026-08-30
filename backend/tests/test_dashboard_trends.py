import pytest
from datetime import date, timedelta
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


# ─── The new response fields (#484) ───────────────────────────────────────
#
# The four assertions above are the original contract and are unchanged:
# `sleep`, `stress`, `symptoms` and `notEnoughData` keep their names,
# types and meanings so clients written against the previous shape keep
# working. Everything below is additive.
#
# The comparison arithmetic itself is covered in test_trend_service.py,
# against the pure function. These tests are about what the *route*
# serves.


def _cycle_logs(MockDate):
    """Two complete cycles plus one in progress, with flow logged.

    Flow is what makes a period reconstructable — there is no
    period-start flag in the data — so this is the fixture that exercises
    `basis: "cycle"` rather than the `recent_logs` fallback.
    """
    logs = []
    for start_month, start_day, sleep in ((3, 1, 5), (3, 29, 8)):
        for offset in range(5):
            day = MockDate(2026, start_month, start_day) + timedelta(days=offset)
            logs.append(
                {
                    "start_date": day,
                    "flow_intensity": "medium",
                    "sleep_hours": sleep,
                    "stress_level": 3,
                    "symptoms": ["cramps"],
                }
            )
    for offset in range(3):
        logs.append(
            {
                "start_date": MockDate(2026, 4, 26) + timedelta(days=offset),
                "flow_intensity": "medium",
            }
        )
    return logs


def test_trends_reports_which_windows_it_compared(auth_headers, mock_auth_dependencies):
    """`basis` is what stops the response claiming a comparison it did not make."""
    from api.dashboard import date as _date

    class MockDate(_date):
        @classmethod
        def today(cls):
            return date(2026, 5, 10)

    with patch("api.dashboard.date", MockDate):
        with patch("services.scoring_service.CycleService") as MockCycleService:
            MockCycleService.get_logs_for_user.return_value = _cycle_logs(MockDate)
            response = client.get("/api/v1/dashboard/trends", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["basis"] == "cycle"
    assert data["comparedWindows"]["previous"]["start"] == "2026-03-01"
    assert data["comparedWindows"]["previous"]["end"] == "2026-03-28"
    assert data["comparedWindows"]["current"]["start"] == "2026-03-29"
    # The cycle in progress on 10 May is excluded: it is partial.
    assert data["comparedWindows"]["current"]["end"] == "2026-04-25"


def test_trends_serves_a_key_and_evidence_for_every_statement(
    auth_headers, mock_auth_dependencies
):
    """A Tamil user's trends card cannot be Tamil without these."""
    from api.dashboard import date as _date

    class MockDate(_date):
        @classmethod
        def today(cls):
            return date(2026, 5, 10)

    with patch("api.dashboard.date", MockDate):
        with patch("services.scoring_service.CycleService") as MockCycleService:
            MockCycleService.get_logs_for_user.return_value = _cycle_logs(MockDate)
            response = client.get("/api/v1/dashboard/trends", headers=auth_headers)

    data = response.json()

    assert data["trends"], data
    sleep = next(t for t in data["trends"] if t["metric"] == "sleep")
    assert sleep["key"] == "trends.sleep.increased"
    assert sleep["evidence"]["previous"] == 5.0
    assert sleep["evidence"]["current"] == 8.0
    # Five nights in each window, so "average" is a true description.
    assert sleep["evidence"]["averaged"] is True
    assert data["disclaimerKey"] == "insights.disclaimer"


def test_trends_reads_enough_history_to_span_two_cycles(
    auth_headers, mock_auth_dependencies
):
    """The default limit of 10 documents cannot hold two cycle windows.

    Left at the default, window reconstruction would fall back to
    `recent_logs` for exactly the users who log the most.
    """
    from api.dashboard import date as _date, TRENDS_LOG_LIMIT

    class MockDate(_date):
        @classmethod
        def today(cls):
            return date(2026, 5, 10)

    with patch("api.dashboard.date", MockDate):
        with patch("services.scoring_service.CycleService") as MockCycleService:
            MockCycleService.get_logs_for_user.return_value = _cycle_logs(MockDate)
            client.get("/api/v1/dashboard/trends", headers=auth_headers)

    assert MockCycleService.get_logs_for_user.call_args.kwargs["limit"] == TRENDS_LOG_LIMIT
    assert TRENDS_LOG_LIMIT >= 60


def test_trends_with_no_logs_reports_not_enough_data(
    auth_headers, mock_auth_dependencies
):
    with patch("services.scoring_service.CycleService") as MockCycleService:
        MockCycleService.get_logs_for_user.return_value = []
        response = client.get("/api/v1/dashboard/trends", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["notEnoughData"] is True
    assert data["basis"] is None
    assert data["trends"] == []
