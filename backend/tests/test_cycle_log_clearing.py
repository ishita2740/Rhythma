"""A logged value can be taken back (issue #549).

Both write routes stripped every `None` before touching Firestore:

    fields = {k: v for k, v in log.model_dump().items() if ... v is not None}

`model_dump()` cannot tell an omitted field from one explicitly sent as
`null` — both are `None` — so the filter that implements "merge, don't
clobber what wasn't sent" also implemented "you may never send a
clearing". A mis-tapped flow intensity, a sleep value typed as 12 instead
of 2, a note naming a partner or a clinic: all editable, none removable.
Deleting the whole day was the only way out, and it took the rest of the
day with it.

`PUT /cycle/{log_id}` with `{"notes": null}` went further and answered
"No fields provided for update". A field *was* provided; the handler
discarded it and reported the discarding as the caller's mistake.

Two notes on what is asserted here.

The tests read the stored document back through `GET /{user_id}/history`
rather than inspecting the mock's `store`. "Is the field gone?" is only
meaningfully answered by what a subsequent read returns, and the history
route is what the clients actually call.

And the merge behaviour is asserted alongside the clearing in almost
every case. The risk in this change is not that clearing stops working —
it is that clearing starts happening to fields nobody mentioned, which
would silently destroy data on every quick-log tap. That is the property
worth the extra line in each test.
"""

import os
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
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
                    text = "Mock Gemini response"

                return MockResponse()

        return MockModel()


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app  # noqa: E402
from core.auth import create_access_token  # noqa: E402
from services.firestore_service import (  # noqa: E402
    CycleService,
    MockFirestoreClient,
    UserService,
)

import services.firestore_service as _fs_mod  # noqa: E402

client = TestClient(app)

LOG_URL = "/api/v1/cycle/log"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setattr(_fs_mod, "db", MockFirestoreClient())


@pytest.fixture
def account():
    user_id = UserService.create_user(
        {"email": "sana@example.com", "username": "sanakumar"}
    )
    token = create_access_token(data={"sub": user_id})
    return user_id, {"Authorization": f"Bearer {token}"}


def _post(headers, **payload):
    body = {"start_date": TODAY.isoformat(), **payload}
    response = client.post(LOG_URL, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response


def _stored(user_id, headers, when=TODAY):
    """The day's log as a client would read it back."""
    response = client.get(
        f"/api/v1/cycle/{user_id}/history",
        params={"start_date": when.isoformat(), "end_date": when.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert len(entries) == 1, f"expected one entry, got {len(entries)}"
    return entries[0]


# ─── POST /cycle/log ──────────────────────────────────────────────────────


def test_a_null_removes_a_logged_value(account):
    """The mis-tap: log heavy, take it back, and have it stay taken back."""
    user_id, headers = account
    _post(headers, flow_intensity="heavy")
    assert _stored(user_id, headers)["flow_intensity"] == "heavy"

    _post(headers, flow_intensity=None)

    assert _stored(user_id, headers).get("flow_intensity") is None


def test_clearing_one_field_leaves_the_rest_of_the_day_alone(account):
    """The risk in this change, asserted directly."""
    user_id, headers = account
    _post(headers, flow_intensity="heavy", mood="sad", sleep_hours=8.0)

    _post(headers, flow_intensity=None)

    entry = _stored(user_id, headers)
    assert entry.get("flow_intensity") is None
    assert entry["mood"] == "sad"
    assert entry["sleep_hours"] == 8.0


def test_an_omitted_field_is_still_left_alone(account):
    """Quick-log tiles send one field; they must not wipe the others."""
    user_id, headers = account
    _post(headers, flow_intensity="heavy", mood="sad")

    _post(headers, sleep_hours=7.0)

    entry = _stored(user_id, headers)
    assert entry["flow_intensity"] == "heavy"
    assert entry["mood"] == "sad"
    assert entry["sleep_hours"] == 7.0


def test_every_loggable_field_can_be_cleared(account):
    """Not a sample — each of these is a value a user might want back."""
    user_id, headers = account
    _post(
        headers,
        flow_intensity="heavy",
        mood="sad",
        sleep_hours=12.0,
        stress_level=5,
        symptoms=["cramps"],
        notes="mentioned it to Dr Rao",
    )

    _post(
        headers,
        flow_intensity=None,
        mood=None,
        sleep_hours=None,
        stress_level=None,
        symptoms=None,
        notes=None,
    )

    entry = _stored(user_id, headers)
    for field in (
        "flow_intensity",
        "mood",
        "sleep_hours",
        "stress_level",
        "symptoms",
        "notes",
    ):
        assert entry.get(field) is None, f"{field} survived a clearing"


def test_an_empty_symptom_list_clears_the_list(account):
    """Unticking every chip is a clearing, not a no-op."""
    user_id, headers = account
    _post(headers, symptoms=["cramps", "headache"])

    _post(headers, symptoms=[])

    assert _stored(user_id, headers)["symptoms"] == []


def test_a_whitespace_only_note_clears_it(account):
    """`normalize_notes` already folds this to None; now that means something."""
    user_id, headers = account
    _post(headers, notes="took ibuprofen")

    _post(headers, notes="   ")

    assert _stored(user_id, headers).get("notes") is None


def test_clearing_a_field_that_was_never_logged_is_harmless(account):
    """No document yet, nothing to delete — and no error either."""
    user_id, headers = account

    _post(headers, mood="happy", flow_intensity=None)

    entry = _stored(user_id, headers)
    assert entry["mood"] == "happy"
    assert entry.get("flow_intensity") is None


def test_a_cleared_value_does_not_come_back_as_a_sentinel(account):
    """Firestore's DELETE_FIELD is an instruction, never a stored value.

    Asserted because the mock had to learn about the sentinel for these
    tests to run at all, and a mock that stored it instead of acting on
    it would make every test above pass while a real deployment served
    clients an unparseable object.
    """
    user_id, headers = account
    _post(headers, mood="sad")
    _post(headers, mood=None)

    raw = CycleService.get_log(user_id, f"{user_id}_{TODAY.isoformat()}")
    assert "mood" not in raw


# ─── PUT /cycle/{log_id} ──────────────────────────────────────────────────


def test_a_null_only_update_is_accepted_not_a_400(account):
    """The false error: "No fields provided" when a field was provided."""
    user_id, headers = account
    _post(headers, notes="mentioned it to Dr Rao")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"notes": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id, headers).get("notes") is None


def test_an_empty_update_body_is_still_a_400(account):
    """The 400 keeps its meaning — it just becomes true."""
    user_id, headers = account
    _post(headers, mood="sad")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(f"/api/v1/cycle/{log_id}", json={}, headers=headers)

    assert response.status_code == 400
    assert "No fields provided" in response.json()["detail"]


def test_an_update_clears_one_field_and_leaves_the_others(account):
    user_id, headers = account
    _post(headers, mood="sad", stress_level=4, notes="rough day")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"stress_level": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    entry = _stored(user_id, headers)
    assert entry.get("stress_level") is None
    assert entry["mood"] == "sad"
    assert entry["notes"] == "rough day"


def test_a_null_end_date_clears_it_without_a_range_check(account):
    """A clearing has nothing to compare against, so it skips the check."""
    user_id, headers = account
    _post(headers, end_date=TODAY.isoformat())
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"end_date": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id, headers).get("end_date") is None


def test_an_inverted_end_date_is_still_refused(account):
    """The range check still runs for an actual date."""
    user_id, headers = account
    _post(headers, mood="sad")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}",
        json={"end_date": (TODAY - timedelta(days=3)).isoformat()},
        headers=headers,
    )

    assert response.status_code == 422


def test_an_update_still_refuses_someone_elses_log(account):
    """Ownership is unchanged; the clearing path must not bypass it."""
    _, headers = account
    other_id = UserService.create_user({"email": "other@example.com"})
    CycleService.upsert_log(other_id, TODAY, {"mood": "happy"})

    response = client.put(
        f"/api/v1/cycle/{other_id}_{TODAY.isoformat()}",
        json={"mood": None},
        headers=headers,
    )

    assert response.status_code == 403


# ─── Validation still applies to a value that is not a clearing ───────────


def test_an_out_of_range_value_is_still_refused(account):
    _, headers = account

    response = client.post(
        LOG_URL,
        json={"start_date": TODAY.isoformat(), "stress_level": 99},
        headers=headers,
    )

    assert response.status_code == 422


def test_an_unknown_flow_intensity_is_still_refused(account):
    _, headers = account

    response = client.post(
        LOG_URL,
        json={"start_date": TODAY.isoformat(), "flow_intensity": "torrential"},
        headers=headers,
    )

    assert response.status_code == 422


# ─── The mock is not looser than Firestore ────────────────────────────────


def test_the_mock_refuses_the_delete_sentinel_in_set():
    """Real Firestore does; a mock that allowed it would hide a real bug."""
    from google.cloud.firestore_v1 import DELETE_FIELD

    db = MockFirestoreClient()
    doc = db.collection("cycle_logs").document("new-doc")

    with pytest.raises(ValueError, match="DELETE_FIELD"):
        doc.set({"mood": DELETE_FIELD})


def test_the_mock_removes_a_key_rather_than_storing_the_sentinel():
    from google.cloud.firestore_v1 import DELETE_FIELD

    db = MockFirestoreClient()
    collection = db.collection("cycle_logs")
    collection.document("d").set({"mood": "sad", "notes": "keep me"})

    collection.document("d").update({"mood": DELETE_FIELD})

    stored = collection.document("d").get().to_dict()
    assert stored == {"notes": "keep me"}
