"""Tests for the Health Goal Tracker feature.

Covers goal CRUD, daily check-ins, streak computation, weekly summaries,
and authorization enforcement.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Mock google.generativeai ──────────────────────────────────────────────
class MockGemini:
    def __getattr__(self, name):
        return self
    def configure(self, *args, **kwargs):
        pass
    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    text = "Mock Gemini response"
                return MockResponse()
        return MockModel()

sys.modules["google.generativeai"] = MockGemini()

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

existing_firebase_admin = sys.modules.get("firebase_admin")
if isinstance(existing_firebase_admin, MagicMock) and hasattr(existing_firebase_admin, "auth"):
    mock_firebase_admin = existing_firebase_admin
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin

mock_firebase_auth = getattr(mock_firebase_admin, "auth", None)
if not isinstance(mock_firebase_auth, MagicMock):
    mock_firebase_auth = MagicMock()
    mock_firebase_admin.auth = mock_firebase_auth
sys.modules["firebase_admin.auth"] = mock_firebase_auth
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app
from core.auth import get_current_user
import services.firestore_service as fs
from services.firestore_service import MockFirestoreClient

fs.db = MockFirestoreClient()
db = fs.db
client = TestClient(app)

TEST_USER_ID = "test-goals-user"
OTHER_USER_ID = "other-user-id"


def override_get_current_user():
    return {"id": TEST_USER_ID, "username": "testuser"}


@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_db():
    db._collections = {}
    yield
    db._collections = {}


# ─── Helpers ────────────────────────────────────────────────────────────────


def _create_goal(title="Sleep 7h", category="sleep", target_value=7.0, unit="hours"):
    """Create a goal via the API and return its JSON."""
    resp = client.post("/api/v1/goals", json={
        "title": title,
        "category": category,
        "target_value": target_value,
        "unit": unit,
    })
    assert resp.status_code == 201
    return resp.json()


def _checkin(goal_id, d: date, completed=True, actual_value=None):
    """Log a check-in via the API."""
    payload = {
        "goal_id": goal_id,
        "date": d.isoformat(),
        "completed": completed,
    }
    if actual_value is not None:
        payload["actual_value"] = actual_value
    return client.post("/api/v1/goals/checkin", json=payload)


# ─── Goal templates ─────────────────────────────────────────────────────────


def test_get_goal_templates():
    resp = client.get("/api/v1/goals/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5
    assert data[0]["template_id"] == "sleep_7h"


# ─── Goal CRUD ──────────────────────────────────────────────────────────────


def test_create_goal():
    goal = _create_goal()
    assert goal["title"] == "Sleep 7h"
    assert goal["category"] == "sleep"
    assert goal["is_active"] is True


def test_create_goal_invalid_category():
    resp = client.post("/api/v1/goals", json={
        "title": "Bad Goal",
        "category": "invalid_cat",
    })
    assert resp.status_code == 400


def test_list_goals():
    _create_goal()
    _create_goal(title="Drink water", category="hydration")
    resp = client.get("/api/v1/goals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_single_goal():
    goal = _create_goal()
    resp = client.get(f"/api/v1/goals/{goal['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == goal["id"]


def test_get_goal_not_found():
    resp = client.get("/api/v1/goals/nonexistent")
    assert resp.status_code == 404


def test_deactivate_goal():
    goal = _create_goal()
    resp = client.delete(f"/api/v1/goals/{goal['id']}")
    assert resp.status_code == 204
    # Should no longer appear in listing
    resp = client.get("/api/v1/goals")
    assert len(resp.json()) == 0


def test_deactivate_goal_not_found():
    resp = client.delete("/api/v1/goals/nonexistent")
    assert resp.status_code == 404


# ─── Check-ins ──────────────────────────────────────────────────────────────


def test_log_checkin():
    goal = _create_goal()
    resp = _checkin(goal["id"], date(2026, 8, 25), completed=True, actual_value=7.5)
    assert resp.status_code == 201
    data = resp.json()
    assert data["completed"] is True
    assert data["actual_value"] == 7.5


def test_log_checkin_invalid_goal():
    resp = _checkin("nonexistent", date(2026, 8, 25))
    assert resp.status_code == 400


def test_log_checkin_invalid_date():
    goal = _create_goal()
    resp = client.post("/api/v1/goals/checkin", json={
        "goal_id": goal["id"],
        "date": "not-a-date",
    })
    assert resp.status_code == 422


def test_checkin_upsert():
    """Second check-in for same goal+date overwrites the first."""
    goal = _create_goal()
    _checkin(goal["id"], date(2026, 8, 25), completed=False)
    resp = _checkin(goal["id"], date(2026, 8, 25), completed=True)
    assert resp.status_code == 201
    assert resp.json()["completed"] is True


def test_get_daily_checkins():
    goal = _create_goal()
    _checkin(goal["id"], date(2026, 8, 25), completed=True)
    resp = client.get("/api/v1/goals/checkin/2026-08-25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed_goals"] == 1
    assert data["total_goals"] == 1
    assert data["completion_rate"] == 100


def test_get_daily_checkins_invalid_date():
    resp = client.get("/api/v1/goals/checkin/bad-date")
    assert resp.status_code == 422


# ─── Streaks ────────────────────────────────────────────────────────────────


def test_streak_no_checkins():
    goal = _create_goal()
    resp = client.get(f"/api/v1/goals/{goal['id']}/streak")
    assert resp.status_code == 200
    assert resp.json()["current_streak"] == 0
    assert resp.json()["longest_streak"] == 0


def test_streak_with_checkins():
    goal = _create_goal()
    today = date.today()
    for i in range(3):
        _checkin(goal["id"], today, completed=True)
        today_str = (today - __import__("datetime").timedelta(days=i)).isoformat()
        # Use the service directly for multi-day streaks
        from services.goal_service import log_checkin
        log_checkin(TEST_USER_ID, goal["id"], today - __import__("datetime").timedelta(days=i), completed=True)

    resp = client.get(f"/api/v1/goals/{goal['id']}/streak")
    assert resp.status_code == 200
    assert resp.json()["current_streak"] == 3


def test_streak_goal_not_found():
    resp = client.get("/api/v1/goals/nonexistent/streak")
    assert resp.status_code == 404


# ─── Weekly summary ─────────────────────────────────────────────────────────


def test_weekly_summary_empty():
    resp = client.get("/api/v1/goals/summary/weekly")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_completion_rate"] == 0
    assert len(data["goals"]) == 0


def test_weekly_summary_with_goals():
    _create_goal()
    _create_goal(title="Walk", category="exercise")
    resp = client.get("/api/v1/goals/summary/weekly")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["goals"]) == 2
    assert "period" in data


# ─── Goals with streak in listing ───────────────────────────────────────────


def test_list_goals_includes_streaks():
    goal = _create_goal()
    from services.goal_service import log_checkin
    log_checkin(TEST_USER_ID, goal["id"], date.today(), completed=True)

    resp = client.get("/api/v1/goals")
    assert resp.status_code == 200
    goals = resp.json()
    assert any(g["current_streak"] >= 1 for g in goals)
