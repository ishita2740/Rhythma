import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import date

# Ensure backend directory is on the Python path
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

# ─── Set environment variables ─────────────────────────────────────────────
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

# ─── Mock firebase_admin ──────────────────────────────────────────────────
# Reuse existing mock if already set up (e.g., by test_auth.py) to avoid
# module contamination that breaks cross-test mock consistency.
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

# ─── Import main after mocks ──────────────────────────────────────────────
from main import app
from core.auth import get_current_user
import services.firestore_service as fs
from services.firestore_service import MockFirestoreClient, CycleService

# Force db to be the mock client for these tests
fs.db = MockFirestoreClient()
db = fs.db

client = TestClient(app)

TEST_USER_ID = "test-user-id"
OTHER_USER_ID = "other-user-id"

# Mock current user dependency
def override_get_current_user():
    return {"id": TEST_USER_ID, "username": "testuser"}

@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_db():
    # Clear and reset the MockFirestoreClient state before each test
    db._collections = {}
    yield
    db._collections = {}


@pytest.fixture
def test_log_id():
    """Create a sample cycle log for the test user and return its ID."""
    return CycleService.upsert_log(
        TEST_USER_ID,
        date(2026, 7, 24),
        {"flow_intensity": "medium", "mood": "happy"}
    )


@pytest.fixture
def other_user_log_id():
    """Create a sample cycle log for another user and return its ID."""
    return CycleService.upsert_log(
        OTHER_USER_ID,
        date(2026, 7, 24),
        {"flow_intensity": "light", "mood": "sad"}
    )


@pytest.fixture
def mock_cycle_service():
    """Patch CycleService at the router level for tests that don't need real DB state."""
    with patch("api.cycle.CycleService") as MockCycleService:
        yield MockCycleService


# ─── POST /cycle/log ────────────────────────────────────────────────────────

def test_log_cycle_success(mock_cycle_service):
    mock_cycle_service.upsert_log.return_value = "log-123"
    payload = {
        "start_date": "2026-05-01",
        "flow_intensity": "medium",
        "symptoms": ["cramps"]
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 200
    assert response.json()["id"] == "log-123"
    # assert the payload is included in the response
    assert response.json()["data"]["flow_intensity"] == "medium"

def test_log_cycle_missing_required_fields(mock_cycle_service):
    payload = {
        "flow_intensity": "medium"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "start_date" in str(response.json()["detail"])

def test_log_cycle_invalid_dates(mock_cycle_service):
    payload = {
        "start_date": "not-a-date"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "start_date" in str(response.json()["detail"])

def test_log_cycle_invalid_payload(mock_cycle_service):
    payload = {
        "start_date": "2026-05-01",
        "sleep_hours": "not-a-number"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "sleep_hours" in str(response.json()["detail"])


# ─── GET /cycle/{user_id}/history ──────────────────────────────────────────

def test_get_cycle_history_success(mock_cycle_service):
    mock_cycle_service.get_logs_page.return_value = (
        [{"id": "log-1", "start_date": "2026-05-01", "flow_intensity": "medium"}],
        False,
    )
    response = client.get(f"/api/v1/cycle/{TEST_USER_ID}/history")
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1
    mock_cycle_service.get_logs_page.assert_called_once_with(
        TEST_USER_ID, limit=20, offset=0, start_date=None, end_date=None
    )

def test_get_cycle_history_unauthorized(mock_cycle_service):
    response = client.get(f"/api/v1/cycle/{OTHER_USER_ID}/history")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to view this user's data"

def test_get_cycle_history_empty_history(mock_cycle_service):
    mock_cycle_service.get_logs_page.return_value = ([], False)
    response = client.get(f"/api/v1/cycle/{TEST_USER_ID}/history")
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 0


# ─── PUT /cycle/{log_id} ────────────────────────────────────────────────────

def test_update_cycle_log_success(test_log_id):
    """Test successful update of an existing cycle log."""
    update_data = {
        "flow_intensity": "heavy",
        "notes": "Updated note"
    }
    response = client.put(f"/api/v1/cycle/{test_log_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == f"Cycle log {test_log_id} updated"

    # Verify the database actually updated
    doc = db.collection("cycle_logs").document(test_log_id).get()
    doc_data = doc.to_dict()
    assert doc_data["flow_intensity"] == "heavy"
    assert doc_data["notes"] == "Updated note"
    # Original field should still exist if not overwritten
    assert doc_data["mood"] == "happy"


def test_update_cycle_log_missing_log():
    """Test updating a log that doesn't exist returns 404."""
    update_data = {"flow_intensity": "heavy"}
    response = client.put("/api/v1/cycle/non-existent-id", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Cycle log not found"


def test_update_cycle_log_unauthorized(other_user_log_id):
    """Test updating another user's log returns 403."""
    update_data = {"flow_intensity": "heavy"}
    response = client.put(f"/api/v1/cycle/{other_user_log_id}", json=update_data)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this log"


def test_update_cycle_log_empty_payload(test_log_id):
    """Test updating with empty payload returns 400."""
    # Sending all nulls via empty JSON object
    response = client.put(f"/api/v1/cycle/{test_log_id}", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "No fields provided for update"


# ─── DELETE /cycle/{log_id} ─────────────────────────────────────────────────

def test_delete_cycle_log_success(test_log_id):
    """Test successful deletion of an existing cycle log."""
    response = client.delete(f"/api/v1/cycle/{test_log_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == f"Cycle log {test_log_id} deleted"

    # Verify the document is gone
    doc = db.collection("cycle_logs").document(test_log_id).get()
    assert not doc.exists


def test_delete_cycle_log_missing_log():
    """Test deleting a log that doesn't exist returns 404."""
    response = client.delete("/api/v1/cycle/non-existent-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cycle log not found"


def test_delete_cycle_log_unauthorized(other_user_log_id):
    """Test deleting another user's log returns 403."""
    response = client.delete(f"/api/v1/cycle/{other_user_log_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this log"