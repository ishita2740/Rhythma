"""The write routes actually enforce the cycle-log rules (issue #347).

``test_cycle_log_validation.py`` covers the rules. This file covers the
thing that was actually broken: nothing called them. A validator no route
invokes passes its own unit tests perfectly and stores ``"banana"``
anyway, so these drive real HTTP requests and then read the stored
document back to confirm what landed.

Run against the mock Firestore client with logs written through the real
``CycleService``, following ``test_cycle_history.py`` — a mocked service
would assert on what the route *passed*, which is exactly the layer under
test.
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
from core.auth import get_current_user  # noqa: E402
from core.cycle_validation import (  # noqa: E402
    MAX_NOTES_CHARS,
    MAX_SYMPTOMS,
)
import services.firestore_service as fs  # noqa: E402
from services.firestore_service import CycleService, MockFirestoreClient  # noqa: E402
from services.scoring_service import build_model_features  # noqa: E402

# Same reasoning as test_cycle_history.py: reuse whichever mock client is
# already installed rather than swapping in a fresh one, or earlier test
# modules end up holding a reference to a client nothing writes to.
if not isinstance(fs.db, MockFirestoreClient):
    fs.db = MockFirestoreClient()
db = fs.db

client = TestClient(app)

USER_ID = "validation-user"
LOG_URL = "/api/v1/cycle/log"
VALUES_URL = "/api/v1/cycle/loggable-values"

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": USER_ID,
        "username": "asha",
    }
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_db():
    db._collections = {}
    db._counters = {}
    yield
    db._collections = {}


def stored_log(start=None):
    """Read back what was actually written for a day."""
    doc_id = f"{USER_ID}_{(start or TODAY).isoformat()}"
    return db.collection("cycle_logs").document(doc_id).get().to_dict()


def log_count():
    return len(db._collections.get("cycle_logs", {}))


# ─── The route refuses what the schema refuses ─────────────────────────────


def test_the_payload_from_the_issue_is_rejected_by_the_route():
    """This exact request returned 200 on main."""
    response = client.post(
        LOG_URL,
        json={
            "start_date": "3025-01-01",
            "flow_intensity": "banana",
            "mood": " -not-a-mood",
            "symptoms": ["x" * 500] * 200,
            "sleep_hours": -5000.0,
            "stress_level": 999999,
            "notes": "n" * 50000,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert log_count() == 0, "a rejected log must not be stored"


@pytest.mark.parametrize(
    "field,value",
    [
        ("flow_intensity", "banana"),
        ("mood", "ecstatic"),
        ("sleep_hours", 900.0),
        ("sleep_hours", -1.0),
        ("stress_level", 0),
        ("stress_level", 11),
        ("notes", "n" * (MAX_NOTES_CHARS + 1)),
    ],
)
def test_each_bad_field_is_refused_on_its_own(field, value):
    response = client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), field: value}
    )

    assert response.status_code == 422
    assert log_count() == 0


def test_too_many_symptoms_are_refused():
    response = client.post(
        LOG_URL,
        json={
            "start_date": TODAY.isoformat(),
            "symptoms": [f"symptom-{i}" for i in range(MAX_SYMPTOMS + 1)],
        },
    )

    assert response.status_code == 422


def test_a_future_start_date_is_refused():
    response = client.post(
        LOG_URL, json={"start_date": (TODAY + timedelta(days=1)).isoformat()}
    )

    assert response.status_code == 422
    assert "future" in response.text


def test_an_inverted_date_range_is_refused():
    response = client.post(
        LOG_URL,
        json={
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY - timedelta(days=3)).isoformat(),
        },
    )

    assert response.status_code == 422


# ─── The route stores the normalised value ─────────────────────────────────


def test_a_good_log_is_still_accepted_and_stored():
    response = client.post(
        LOG_URL,
        json={
            "start_date": TODAY.isoformat(),
            "flow_intensity": "medium",
            "mood": "neutral",
            "symptoms": ["cramps"],
            "sleep_hours": 7.5,
            "stress_level": 3,
            "notes": "Ordinary day.",
        },
    )

    assert response.status_code == 200
    saved = stored_log()
    assert saved["flow_intensity"] == "medium"
    assert saved["sleep_hours"] == 7.5
    assert saved["symptoms"] == ["cramps"]


def test_the_stored_flow_intensity_is_canonical():
    """`scoring_service` matches against lowercase keys.

    Storing `"Heavy"` would make the entry invisible to the flow rules
    rather than merely untidy — it would fall through to the "no value
    logged" default.
    """
    client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), "flow_intensity": "  HEAVY  "}
    )

    assert stored_log()["flow_intensity"] == "heavy"


def test_stored_symptoms_are_normalised_and_deduplicated():
    client.post(
        LOG_URL,
        json={
            "start_date": TODAY.isoformat(),
            "symptoms": ["  Cramps ", "CRAMPS", "backpain"],
        },
    )

    assert stored_log()["symptoms"] == ["cramps", "back pain"]


def test_stored_notes_are_trimmed():
    client.post(
        LOG_URL,
        json={"start_date": TODAY.isoformat(), "notes": "   cramps all day   "},
    )

    assert stored_log()["notes"] == "cramps all day"


def test_a_quick_log_tile_still_writes_one_field():
    """The Home screen sends a single field; partial payloads must survive."""
    response = client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), "flow_intensity": "light"}
    )

    assert response.status_code == 200
    saved = stored_log()
    assert saved["flow_intensity"] == "light"
    assert "mood" not in saved or saved.get("mood") is None


def test_flutters_none_flow_round_trips():
    response = client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), "flow_intensity": "none"}
    )

    assert response.status_code == 200
    assert stored_log()["flow_intensity"] == "none"


# ─── The PUT route has the same rules ──────────────────────────────────────


def _existing_log_id(start=None):
    start = start or YESTERDAY
    return CycleService.upsert_log(USER_ID, start, {"flow_intensity": "medium"})


@pytest.mark.parametrize(
    "payload",
    [
        {"flow_intensity": "banana"},
        {"mood": "ecstatic"},
        {"sleep_hours": -5000.0},
        {"stress_level": 999999},
        {"notes": "n" * (MAX_NOTES_CHARS + 1)},
    ],
)
def test_the_update_route_refuses_the_same_values(payload):
    log_id = _existing_log_id()

    response = client.put(f"/api/v1/cycle/{log_id}", json=payload)

    assert response.status_code == 422


def test_an_update_normalises_before_storing():
    log_id = _existing_log_id()

    response = client.put(f"/api/v1/cycle/{log_id}", json={"flow_intensity": "HEAVY"})

    assert response.status_code == 200
    assert stored_log(YESTERDAY)["flow_intensity"] == "heavy"


def test_an_update_cannot_set_an_end_date_before_the_stored_start():
    """The payload has no `start_date`, so this needs the stored document.

    Without the read-back, `PUT` could produce a log the `POST` route
    would have refused to create.
    """
    start = TODAY - timedelta(days=2)
    log_id = _existing_log_id(start)

    response = client.put(
        f"/api/v1/cycle/{log_id}",
        json={"end_date": (start - timedelta(days=5)).isoformat()},
    )

    assert response.status_code == 422
    assert "before start_date" in response.text


def test_an_update_accepts_a_valid_end_date():
    start = TODAY - timedelta(days=4)
    log_id = _existing_log_id(start)

    response = client.put(
        f"/api/v1/cycle/{log_id}",
        json={"end_date": (start + timedelta(days=3)).isoformat()},
    )

    assert response.status_code == 200


def test_an_update_to_someone_elses_log_is_still_refused():
    """The new read-back must not become a way to probe other users' logs."""
    other_id = CycleService.upsert_log("another-user", TODAY, {"flow_intensity": "light"})

    response = client.put(
        f"/api/v1/cycle/{other_id}", json={"end_date": TODAY.isoformat()}
    )

    assert response.status_code == 403


def test_an_update_to_a_missing_log_is_a_404():
    response = client.put(
        "/api/v1/cycle/no-such-log", json={"end_date": TODAY.isoformat()}
    )

    assert response.status_code == 404


def test_an_empty_update_is_still_a_400():
    """Pre-existing behaviour; the new validators must not change it."""
    log_id = _existing_log_id()

    assert client.put(f"/api/v1/cycle/{log_id}", json={}).status_code == 400


# ─── Downstream effect: the reason this matters ────────────────────────────


def test_an_unknown_flow_intensity_can_no_longer_reach_the_scorer():
    """The harm the issue describes, asserted end to end.

    `build_model_features` buckets flow with `.get(value, default)`, so
    `"banana"` scored as medium — indistinguishable from a real medium
    entry, and MHS moved because of it. The fix is that the value can no
    longer be stored, so this asserts on what is *in the database* after a
    rejected write rather than on the mapping in isolation.
    """
    client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), "flow_intensity": "banana"}
    )

    logs = CycleService.get_logs_for_user(USER_ID, limit=10)
    assert logs == []
    assert build_model_features(logs) == []


def test_explicit_none_flow_no_longer_scores_as_medium():
    """`none` had no entry in the map and fell through to the medium default.

    A user recording no bleeding was fed to the model as an average period
    day. It now scores zero, extending the ordinal scale in the only
    direction that makes sense.
    """
    features = build_model_features([{"start_date": TODAY, "flow_intensity": "none"}])
    assert features[0]["flow_intensity"] == 0

    absent = build_model_features([{"start_date": TODAY}])
    assert absent[0]["flow_intensity"] == 2, "absence is still the midpoint"


def test_a_rejected_sleep_value_cannot_skew_a_provider_average():
    """`provider_service` means `sleep_hours` with no re-validation."""
    client.post(
        LOG_URL, json={"start_date": TODAY.isoformat(), "sleep_hours": -5000.0}
    )
    client.post(
        LOG_URL,
        json={"start_date": YESTERDAY.isoformat(), "sleep_hours": 7.0},
    )

    values = [
        log["sleep_hours"]
        for log in CycleService.get_logs_for_user(USER_ID, limit=10)
        if log.get("sleep_hours") is not None
    ]
    assert values == [7.0]


# ─── The description endpoint ──────────────────────────────────────────────


def test_loggable_values_is_served():
    response = client.get(VALUES_URL)

    assert response.status_code == 200
    body = response.json()
    assert "light" in body["flowIntensities"]
    assert "happy" in body["moods"]
    assert body["symptomsAreOpenEnded"] is True
    assert body["limits"]["stressLevel"]["max"] == 5


def test_every_advertised_value_is_accepted_by_the_route():
    """The described vocabulary and the enforced one must not drift.

    Driven through HTTP rather than the schema, because "the endpoint says
    a client may send this" and "the write route accepts it" are the two
    things that have to agree.
    """
    described = client.get(VALUES_URL).json()

    for value in described["flowIntensities"]:
        response = client.post(
            LOG_URL, json={"start_date": TODAY.isoformat(), "flow_intensity": value}
        )
        assert response.status_code == 200, f"advertised flow {value!r} was refused"

    for value in described["moods"]:
        response = client.post(
            LOG_URL, json={"start_date": TODAY.isoformat(), "mood": value}
        )
        assert response.status_code == 200, f"advertised mood {value!r} was refused"

    for value in described["knownSymptoms"]:
        response = client.post(
            LOG_URL, json={"start_date": TODAY.isoformat(), "symptoms": [value]}
        )
        assert response.status_code == 200, f"advertised symptom {value!r} was refused"


def test_loggable_values_requires_authentication():
    app.dependency_overrides.clear()
    try:
        assert client.get(VALUES_URL).status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"id": USER_ID}
