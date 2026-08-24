"""`POST /assistant/chat` end to end, for each thing the model can do.

`test_model_response.py` covers the reading in isolation. This file covers
the wiring: that the route asks for the outcome, renders its text, reports
`wasShortened`, and persists the same reply it returned.

The test double here carries `candidates` with a `finish_reason` and real
`content.parts`, unlike the minimal `text`-only double in
`test_assistant.py`. That difference is not incidental — a double with no
`finish_reason` cannot exercise the branch that #508 lived in, which is
part of why the bug went unnoticed.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Doubles, installed before `main` is imported ─────────────────────────

_PENDING = {"finish_reason": 1, "texts": ["A normal cycle is 21 to 35 days."]}


class FakePart:
    def __init__(self, text):
        self.text = text


class FakeContent:
    def __init__(self, texts):
        self.parts = [FakePart(t) for t in texts]


class FakeCandidate:
    def __init__(self, finish_reason, texts):
        self.finish_reason = finish_reason
        self.content = FakeContent(texts)


class FakeResponse:
    def __init__(self, finish_reason, texts):
        self.candidates = [FakeCandidate(finish_reason, texts)]

    @property
    def text(self):
        # The live accessor raises for a blocked or truncated candidate.
        # Raising here proves the route never depends on it.
        raise ValueError("Quick accessor for 'text' requires a valid response")


class MockGemini:
    """Stands in for the `genai` module the route holds a reference to.

    Installed by the fixture with `monkeypatch.setattr`, not by assigning
    into `sys.modules`. Several test modules install a `google.generativeai`
    stub at import time, and `api.assistant` binds `genai` once when it is
    first imported — so whichever module happened to load first would decide
    which double the route uses. Under `pytest tests/` that is not this one,
    and the tests here would silently exercise another file's stub.
    """

    last_config = None

    def configure(self, *args, **kwargs):
        pass

    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, prompt, *args, **kwargs):
                MockGemini.last_config = kwargs.get("generation_config")
                return FakeResponse(_PENDING["finish_reason"], _PENDING["texts"])

        return MockModel()


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

sys.modules["firebase_admin"] = MagicMock(_apps={})
sys.modules["firebase_admin.auth"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

import api.assistant as assistant_api  # noqa: E402
from api.assistant import ASSISTANT_MAX_OUTPUT_TOKENS  # noqa: E402
from core.auth import get_current_user  # noqa: E402
from core.model_response import (  # noqa: E402
    MESSAGE_RECITATION,
    MESSAGE_SAFETY,
    TRUNCATION_NOTE,
)
from main import app  # noqa: E402
import services.firestore_service as fs  # noqa: E402
from services.firestore_service import MockFirestoreClient  # noqa: E402

fs.db = MockFirestoreClient()

client = TestClient(app)

#: A fresh id per test. The assistant is rate-limited at 10 requests a
#: minute *per user*, and `RateLimitService` binds its Firestore handle at
#: import rather than looking it up live — so resetting `fs.db` here does
#: not clear its buckets, and several tests in one minute under one id
#: would start returning 429 partway through the file. A distinct id per
#: test is the smallest thing that keeps each one independent.
_user_ids = iter(f"finish-reason-user-{n}" for n in range(1000))
CURRENT_USER = {"id": "finish-reason-user-0", "username": "testuser"}


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    CURRENT_USER["id"] = next(_user_ids)
    app.dependency_overrides[get_current_user] = lambda: dict(CURRENT_USER)
    monkeypatch.setattr(assistant_api, "genai", MockGemini())
    MockGemini.last_config = None
    fs.db._collections = {}
    yield
    app.dependency_overrides.clear()


def _reply(finish_reason, texts=("An answer.",)):
    _PENDING["finish_reason"] = finish_reason
    _PENDING["texts"] = list(texts)
    response = client.post(
        "/api/v1/assistant/chat", json={"message": "How long is a normal cycle?"}
    )
    assert response.status_code == 200
    return response.json()


# ─── The regression ───────────────────────────────────────────────────────


def test_a_truncated_answer_reaches_the_user_instead_of_a_safety_message():
    body = _reply(2, ["Cramping in the first two days is common, and warmth"])

    assert "Cramping in the first two days is common" in body["response"]
    assert TRUNCATION_NOTE in body["response"]
    assert body["wasShortened"] is True
    # What it used to say instead.
    assert "safety guidelines" not in body["response"]


def test_an_ordinary_answer_is_not_marked_shortened():
    body = _reply(1, ["A normal cycle is 21 to 35 days."])

    assert body["response"] == "A normal cycle is 21 to 35 days."
    assert body["wasShortened"] is False


def test_a_safety_block_returns_the_safety_message():
    body = _reply(3, [])

    assert body["response"] == MESSAGE_SAFETY
    assert body["wasShortened"] is False


def test_a_recitation_block_is_reported_as_itself():
    body = _reply(4, [])

    assert body["response"] == MESSAGE_RECITATION


def test_the_route_never_reads_the_raising_text_accessor():
    """Every case above goes through a response whose `.text` raises.

    If the route still touched it, these would be 500s rather than 200s.
    """
    for reason in (1, 2, 3, 4, 5):
        _reply(reason, ["Some text."])


# ─── The output ceiling ───────────────────────────────────────────────────


def test_an_explicit_output_ceiling_is_sent_with_every_request():
    _reply(1, ["Short."])

    assert MockGemini.last_config == {"max_output_tokens": ASSISTANT_MAX_OUTPUT_TOKENS}
    assert ASSISTANT_MAX_OUTPUT_TOKENS > 0


# ─── Persistence ──────────────────────────────────────────────────────────


def test_the_persisted_reply_is_the_one_the_user_was_shown():
    body = _reply(2, ["A partial answer"])

    doc = fs.db.collection("conversations").document(CURRENT_USER["id"]).get()
    messages = doc.to_dict()["messages"]

    assert messages[-1]["role"] == "model"
    assert messages[-1]["content"] == body["response"]


def test_a_blocked_turn_is_persisted_as_what_the_user_saw():
    body = _reply(3, [])

    doc = fs.db.collection("conversations").document(CURRENT_USER["id"]).get()
    messages = doc.to_dict()["messages"]

    assert messages[-1]["content"] == body["response"] == MESSAGE_SAFETY
