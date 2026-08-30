import os
import sys
import pytest
from unittest.mock import MagicMock

# Ensure backend directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Mock firebase_admin ──────────────────────────────────────────────────
mock_firebase_admin = MagicMock(_apps={})
sys.modules["firebase_admin"] = mock_firebase_admin
sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

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
                    text = "mock response"
                return MockResponse()
        return MockModel()

sys.modules["google.generativeai"] = MockGemini()

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

from services.firestore_service import MockFirestoreClient, UserService
import services.firestore_service as fs

db = MockFirestoreClient()
fs.db = db


def test_user_delete_cascades_user_and_cycle_logs():
    """Verify that deleting a user removes their user doc and cycle logs."""
    user_id = "test-cascade-user"

    db.collection("users").document(user_id).set({
        "email": "cascade@example.com",
        "username": "cascade_user",
    })

    db.collection("cycle_logs").document("log1").set({
        "user_id": user_id,
        "start_date": "2026-08-15",
    })

    UserService.delete_user(user_id)

    assert not db.collection("users").document(user_id).get().exists
    assert not db.collection("cycle_logs").document("log1").get().exists


def test_user_delete_is_idempotent():
    """Deleting a user that doesn't exist should not raise."""
    result = UserService.delete_user("nonexistent-user-id")
    assert isinstance(result, dict)
