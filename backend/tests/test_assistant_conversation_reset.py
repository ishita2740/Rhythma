"""Clearing the assistant conversation, and the store's other two defects.

Issue #509. Three separate things, one root cause — this store was
written as though it were a private cache, when it is the conversation
the model is given and the one the user believes she controls.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

sys.modules["firebase_admin"] = MagicMock(_apps={})
sys.modules["firebase_admin.auth"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()


class _StubGenai:
    def configure(self, *args, **kwargs):
        pass

    def GenerativeModel(self, *args, **kwargs):
        class _Model:
            def generate_content(self, prompt, *args, **kwargs):
                _StubGenai.last_prompt = prompt

                class _Part:
                    text = "A reply."

                class _Content:
                    parts = [_Part()]

                class _Candidate:
                    finish_reason = 1
                    content = _Content()

                class _Response:
                    candidates = [_Candidate()]
                    text = "A reply."

                return _Response()

        return _Model()


sys.modules.setdefault("google.generativeai", _StubGenai())

import api.assistant as assistant_api  # noqa: E402
from core.auth import get_current_user  # noqa: E402
from main import app  # noqa: E402
import services.firestore_service as fs  # noqa: E402
from services.firestore_service import (  # noqa: E402
    MAX_CONVERSATION_MESSAGES,
    AssistantConversationService,
    MockFirestoreClient,
)

fs.db = MockFirestoreClient()

client = TestClient(app)

_user_ids = iter(f"conversation-user-{n}" for n in range(1000))
CURRENT_USER = {"id": "conversation-user-0", "username": "testuser"}


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    CURRENT_USER["id"] = next(_user_ids)
    app.dependency_overrides[get_current_user] = lambda: dict(CURRENT_USER)
    monkeypatch.setattr(assistant_api, "genai", _StubGenai())
    fs.db._collections = {}
    yield
    app.dependency_overrides.clear()


def _uid():
    return CURRENT_USER["id"]


def _turns(n):
    return [{"role": "user", "content": f"message {i}"} for i in range(n)]


# ─── The regression: clearing has to clear what the model is given ────────


def test_clearing_removes_the_conversation_the_prompt_is_built_from():
    """The whole issue, end to end.

    Ask, clear, ask again — the second prompt must not contain the first
    exchange. Before this change the clear did not exist, and the route
    loaded the stored transcript on every turn regardless of what the
    client had dropped locally.
    """
    first = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Could I be pregnant?"},
    )
    assert first.status_code == 200
    assert "Could I be pregnant?" in _StubGenai.last_prompt

    cleared = client.delete("/api/v1/assistant/conversation")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] is True
    assert cleared.json()["messagesRemoved"] == 2

    second = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What foods are high in iron?"},
    )
    assert second.status_code == 200

    prompt = _StubGenai.last_prompt
    assert "What foods are high in iron?" in prompt
    assert "Could I be pregnant?" not in prompt


def test_clearing_deletes_the_document_rather_than_emptying_it():
    client.post("/api/v1/assistant/chat", json={"message": "Hello"})
    assert fs.db.collection("conversations").document(_uid()).get().exists

    client.delete("/api/v1/assistant/conversation")

    assert not fs.db.collection("conversations").document(_uid()).get().exists


def test_clearing_an_empty_conversation_is_a_200_not_a_404():
    """Idempotent: "already clear" is the outcome the caller asked for."""
    response = client.delete("/api/v1/assistant/conversation")

    assert response.status_code == 200
    assert response.json() == {"cleared": True, "messagesRemoved": 0}


def test_the_removed_count_is_what_was_actually_stored():
    AssistantConversationService.add_messages(_uid(), _turns(7))

    body = client.delete("/api/v1/assistant/conversation").json()

    assert body["messagesRemoved"] == 7


def test_clearing_requires_a_session():
    app.dependency_overrides.clear()
    assert client.delete("/api/v1/assistant/conversation").status_code == 401


def test_clearing_only_ever_touches_the_callers_own_conversation():
    """There is no user id a caller can name on this route."""
    other = "someone-else"
    AssistantConversationService.add_messages(other, _turns(3))
    AssistantConversationService.add_messages(_uid(), _turns(2))

    client.delete("/api/v1/assistant/conversation")

    assert AssistantConversationService.get_recent_messages(other) != []
    assert AssistantConversationService.get_recent_messages(_uid()) == []


# ─── Reading must not write ───────────────────────────────────────────────


def test_reading_an_absent_conversation_creates_nothing():
    assert AssistantConversationService.get_recent_messages(_uid()) == []

    assert not fs.db.collection("conversations").document(_uid()).get().exists


def test_get_conversation_returns_none_without_writing():
    assert AssistantConversationService.get_conversation(_uid()) is None
    assert not fs.db.collection("conversations").document(_uid()).get().exists


def test_get_or_create_still_creates_for_callers_that_want_it():
    """Kept deliberately; only the read path stopped using it."""
    AssistantConversationService.get_or_create(_uid())

    assert fs.db.collection("conversations").document(_uid()).get().exists


# ─── Appending ────────────────────────────────────────────────────────────


def test_add_messages_creates_the_document_when_absent():
    AssistantConversationService.add_messages(_uid(), _turns(2))

    stored = AssistantConversationService.get_conversation(_uid())
    assert stored["user_id"] == _uid()
    assert len(stored["messages"]) == 2


def test_add_messages_appends_rather_than_replacing():
    AssistantConversationService.add_messages(_uid(), [{"role": "user", "content": "one"}])
    AssistantConversationService.add_messages(_uid(), [{"role": "user", "content": "two"}])

    contents = [m["content"] for m in AssistantConversationService.get_recent_messages(_uid())]
    assert contents == ["one", "two"]


def test_add_messages_keeps_created_at_across_appends():
    AssistantConversationService.add_messages(_uid(), _turns(1))
    created = AssistantConversationService.get_conversation(_uid())["created_at"]

    AssistantConversationService.add_messages(_uid(), _turns(1))

    assert AssistantConversationService.get_conversation(_uid())["created_at"] == created


def test_add_messages_ignores_an_empty_append():
    AssistantConversationService.add_messages(_uid(), [])

    assert not fs.db.collection("conversations").document(_uid()).get().exists


def test_the_rolling_window_still_caps_at_fifty():
    AssistantConversationService.add_messages(_uid(), _turns(MAX_CONVERSATION_MESSAGES + 10))

    messages = AssistantConversationService.get_conversation(_uid())["messages"]
    assert len(messages) == MAX_CONVERSATION_MESSAGES
    # Oldest dropped, newest kept.
    assert messages[-1]["content"] == f"message {MAX_CONVERSATION_MESSAGES + 9}"


def test_get_recent_messages_returns_the_tail():
    AssistantConversationService.add_messages(_uid(), _turns(6))

    recent = AssistantConversationService.get_recent_messages(_uid(), limit=2)
    assert [m["content"] for m in recent] == ["message 4", "message 5"]


# ─── The transactional path ───────────────────────────────────────────────
#
# The in-memory mock has no `transaction()`, so the fallback is what every
# other test above exercises. These two cover the branch that runs against
# a real Firestore, with a stand-in transaction — the only way to assert it
# without a live database.


class _RecordingTransaction:
    def __init__(self, store):
        self.store = store
        self.reads = 0
        self.committed = False

    def set(self, doc_ref, data):
        self.store["written"] = data

    def commit(self):
        self.committed = True


class _Snapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _TransactionalDoc:
    def __init__(self, existing, transaction):
        self.existing = existing
        self.transaction = transaction

    def get(self, transaction=None):
        assert transaction is self.transaction, "the read must join the transaction"
        self.transaction.reads += 1
        return _Snapshot(self.existing)


def test_appending_reads_and_writes_inside_one_transaction():
    store = {}
    transaction = _RecordingTransaction(store)
    doc = _TransactionalDoc({"messages": [{"role": "user", "content": "earlier"}]}, transaction)

    AssistantConversationService._append_in_transaction(
        transaction,
        doc,
        lambda existing: {
            "messages": list(existing["messages"]) + [{"role": "user", "content": "later"}]
        },
    )

    assert transaction.reads == 1
    assert transaction.committed is True
    assert [m["content"] for m in store["written"]["messages"]] == ["earlier", "later"]


def test_a_transaction_that_cannot_start_falls_back_rather_than_dropping_the_turn():
    """A store that cannot run a transaction must still keep the exchange."""

    class _NoTransactionDb(MockFirestoreClient):
        def transaction(self):
            raise RuntimeError("transactions unavailable")

    original = fs.db
    fs.db = _NoTransactionDb()
    try:
        AssistantConversationService.add_messages(_uid(), _turns(2))
        assert len(AssistantConversationService.get_recent_messages(_uid())) == 2
    finally:
        fs.db = original


# ─── Account deletion still reaches this collection ───────────────────────


def test_conversations_remain_in_the_deletion_cascade():
    from services import data_privacy_service

    assert (
        data_privacy_service.CONVERSATIONS_COLLECTION
        in data_privacy_service.USER_DATA_COLLECTIONS
    )
