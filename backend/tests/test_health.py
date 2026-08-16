import os
import sys
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MockGemini:
    def __getattr__(self, name):
        return self
    def configure(self, *args, **kwargs):
        pass
    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    text = ""
                return MockResponse()
        return MockModel()

sys.modules["google.generativeai"] = MockGemini()

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

sys.modules["firebase_admin"] = MagicMock(_apps={})
sys.modules["firebase_admin.auth"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app

client = TestClient(app)


def test_health_check():
    """The route still answers 200 and still names the service.

    ``status`` is no longer asserted to be ``"ok"``. It used to be a
    constant — the handler was a single `return` and touched nothing — so
    the assertion held for a backend running entirely on the in-memory
    mock database, which is the failure #348 is about. It is now the worst
    component's status, and in a test environment with no Twilio
    credentials that is legitimately ``degraded``.

    ``ready`` is the boolean a caller should branch on, and it is asserted
    here instead. Per-component behaviour lives in
    ``test_health_checks.py``.
    """
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Rhythma API"
    assert data["status"] in ("ok", "degraded", "down")
    assert "ready" in data