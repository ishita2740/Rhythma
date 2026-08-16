import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MockGemini:
    last_prompt = None
    def __getattr__(self, name):
        return self
    def configure(self, *args, **kwargs):
        pass
    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, prompt, *args, **kwargs):
                MockGemini.last_prompt = prompt
                class MockResponse:
                    text = "Mock Gemini response"
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
from core.auth import get_current_user
import services.firestore_service as fs
from services.firestore_service import MockFirestoreClient

# Force db to be the mock client for these tests
fs.db = MockFirestoreClient()

client = TestClient(app)

TEST_USER_ID = "test-user-id"

def override_get_current_user():
    return {"id": TEST_USER_ID, "username": "testuser"}

@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_db():
    fs.db._collections = {}
    yield
    fs.db._collections = {}
    MockGemini.last_prompt = None


def test_chat_success():
    payload = {"message": "What is a normal cycle length?"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["language"] == "en"
    assert "disclaimer" in data


def test_chat_with_language():
    payload = {"message": "How are you?", "language": "hi"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "hi"
    assert "response" in data


def test_chat_empty_message():
    # 422, not the old ad-hoc 400: emptiness is now decided by the request
    # model alongside every other input rule, so all bad input on this
    # route is shaped the same way (issue #332).
    payload = {"message": "   "}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 422
    assert "empty" in str(response.json()["detail"]).lower()


def test_chat_unauthorized():
    app.dependency_overrides.clear()
    payload = {"message": "Hello"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 401


def test_languages_success():
    response = client.get("/api/v1/assistant/languages")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    codes = [lang["code"] for lang in data]
    assert "en" in codes
    assert "hi" in codes
    assert "mr" in codes
    assert "bn" not in codes


def test_languages_unauthorized():
    app.dependency_overrides.clear()
    response = client.get("/api/v1/assistant/languages")
    assert response.status_code == 401


def test_chat_with_history():
    payload = {
        "message": "Tell me more",
        "history": [
            {"role": "user", "content": "What is PCOS?"},
            {"role": "model", "content": "PCOS is a hormonal disorder."},
        ]
    }
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200
    assert "response" in response.json()


def test_chat_persists_conversation():
    payload = {"message": "What is a normal cycle length?"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200

    doc = fs.db.collection("conversations").document(TEST_USER_ID).get()
    assert doc.exists
    data = doc.to_dict()
    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "What is a normal cycle length?"
    assert data["messages"][1]["role"] == "model"
    assert data["messages"][1]["content"] == "Mock Gemini response"


def test_chat_grounds_with_sourced_medical_references():
    payload = {"message": "Tell me about PCOS"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    prompt = MockGemini.last_prompt
    assert prompt is not None
    assert "Trusted Medical Reference" in prompt
    assert "who.int/news-room/fact-sheets/detail/polycystic-ovary-syndrome" in prompt
    assert "Topic:" in prompt
    assert "Source:" in prompt

    # The response carries the same sources structurally, so the client can
    # render "verify it yourself" links.
    sources = data["sources"]
    assert sources, "expected grounded sources in the response"
    assert any(
        source["url"] == "https://www.who.int/news-room/fact-sheets/detail/polycystic-ovary-syndrome"
        for source in sources
    )
    for source in sources:
        assert set(source) == {"name", "title", "url", "accessedOn"}
        assert source["url"].startswith("https://")


def test_chat_without_medical_topic_has_no_grounding():
    payload = {"message": "Hello, how are you today?"}
    response = client.post("/api/v1/assistant/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    prompt = MockGemini.last_prompt
    assert prompt is not None
    assert "Trusted Medical Reference" not in prompt
    assert data["sources"] == []
