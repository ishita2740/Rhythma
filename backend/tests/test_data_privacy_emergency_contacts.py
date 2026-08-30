import os
import sys
import pytest
from unittest.mock import MagicMock

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

from services.firestore_service import UserService


def test_user_delete_is_idempotent():
    """Deleting a user that doesn't exist should not raise."""
    result = UserService.delete_user("nonexistent-user-id")
    assert isinstance(result, dict)
