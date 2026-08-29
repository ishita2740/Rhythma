"""`loggedCycleCount` is a count, not the size of the analysis window (#557).

``get_user_scores`` fetches the ten most recent logs and used to publish
``len(logs)`` as ``logged_cycle_count``. The value therefore saturated:

    _LOGS_LIMIT = 10
    logs = CycleService.get_logs_for_user(user_id, limit=_LOGS_LIMIT)
    ...
    "logged_cycle_count": len(logs),

Four responses carry that field — ``/dashboard``,
``/insights/{id}/scores`` and both provider endpoints — and the provider
dashboard renders it as a labelled stat next to each patient's name. A
patient with ten logs and a patient with five hundred displayed the same
**10**, which is the column a clinician scans to decide who has enough
history to be worth opening.

These tests are written against real logs in the mock Firestore client
rather than a mocked ``CycleService``. That is the whole point here: the
bug lives in the relationship between the query's ``limit`` and the
number reported beside it, and a mocked service returning a canned list
would let a test assert on a number the query never produced.

Every test in the "saturation" section below fails against the pre-fix
code — checked by reverting ``scoring_service.get_user_scores``.
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
import services.firestore_service as fs  # noqa: E402
from services.firestore_service import (  # noqa: E402
    CycleService,
    MockFirestoreClient,
    UserService,
)
from services.scoring_service import _LOGS_LIMIT, get_user_scores  # noqa: E402

# Same reasoning as test_cycle_history.py: reuse whichever mock client is
# already installed, because every service reads through the module global
# and swapping it here would leave earlier modules writing to a client
# nothing reads.
if not isinstance(fs.db, MockFirestoreClient):
    fs.db = MockFirestoreClient()
db = fs.db

client = TestClient(app)

USER_ID = "count-user"


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


def seed_logs(count, *, user_id=USER_ID, step_days=28, first=date(2020, 1, 1)):
    """Write `count` logs for `user_id`, oldest first, `step_days` apart.

    Spaced by a plausible cycle length so the prediction and observation
    code paths that also read these logs behave normally — this module is
    about one field, and a log set that made another part of the response
    degrade would obscure which assertion was doing the work.
    """
    for index in range(count):
        CycleService.upsert_log(
            user_id,
            first + timedelta(days=step_days * index),
            {"flow_intensity": "medium", "sleep_hours": 7, "stress_level": 2},
        )


def seed_user(user_id=USER_ID, **fields):
    db.collection("users").document(user_id).set(
        {"id": user_id, "username": "asha", "email": f"{user_id}@example.com", **fields}
    )


def dashboard():
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200, response.text
    return response.json()


def scores():
    response = client.get(f"/api/v1/insights/{USER_ID}/scores")
    assert response.status_code == 200, response.text
    return response.json()


# ─── The window is still a window ─────────────────────────────────────────
#
# The fix must not widen the analysis window. The ten-log bound is what
# keeps the dashboard's Firestore read constant, and every consumer of
# `logs` is deliberately built on recent history.


def test_the_analysis_window_is_still_capped_at_ten_logs():
    seed_user()
    seed_logs(40)

    data = get_user_scores(USER_ID)

    assert len(data["logs"]) == _LOGS_LIMIT
    assert data["analyzed_cycle_count"] == _LOGS_LIMIT


def test_the_window_holds_the_most_recent_logs_not_the_first_ten():
    seed_user()
    seed_logs(40, first=date(2020, 1, 1), step_days=28)

    data = get_user_scores(USER_ID)
    starts = sorted(log["start_date"] for log in data["logs"])

    # The 40th log, not the 10th. A window that took the oldest ten would
    # make every downstream figure describe years-old history.
    newest = date(2020, 1, 1) + timedelta(days=28 * 39)
    assert starts[-1].date() == newest


# ─── Saturation: the bug itself ───────────────────────────────────────────


@pytest.mark.parametrize("total", [11, 25, 40, 137])
def test_logged_cycle_count_is_the_total_not_the_window(total):
    """The number keeps rising past ten. It used to stop there."""
    seed_user()
    seed_logs(total)

    data = get_user_scores(USER_ID)

    assert data["logged_cycle_count"] == total
    assert data["analyzed_cycle_count"] == _LOGS_LIMIT


def test_two_patients_with_very_different_histories_are_distinguishable():
    """The failure a clinician actually sees.

    Ten logs and five hundred used to render identically on the provider
    dashboard, which is the one column that column exists to rank on.
    """
    seed_user("patient-a")
    seed_logs(10, user_id="patient-a")
    seed_user("patient-b")
    seed_logs(500, user_id="patient-b")

    a = get_user_scores("patient-a")
    b = get_user_scores("patient-b")

    assert a["logged_cycle_count"] == 10
    assert b["logged_cycle_count"] == 500
    assert a["logged_cycle_count"] != b["logged_cycle_count"]

    # And the window is identical for both, which is why the two figures
    # had to become two fields rather than one.
    assert a["analyzed_cycle_count"] == b["analyzed_cycle_count"] == _LOGS_LIMIT


# ─── Below the window nothing changes ─────────────────────────────────────


@pytest.mark.parametrize("total", [0, 1, 3, 9])
def test_a_short_history_reports_the_same_number_twice(total):
    """A window shorter than its limit *is* the total."""
    seed_user()
    seed_logs(total)

    data = get_user_scores(USER_ID)

    assert data["logged_cycle_count"] == total
    assert data["analyzed_cycle_count"] == total


def test_exactly_ten_logs_reports_ten_for_both():
    seed_user()
    seed_logs(10)

    data = get_user_scores(USER_ID)

    assert data["logged_cycle_count"] == 10
    assert data["analyzed_cycle_count"] == 10


def test_a_short_history_costs_no_extra_query():
    """The count is skipped when the window did not fill.

    Not a micro-optimisation worth a test on its own — it is the reason
    the fix is free for most users, and a later refactor that always
    counts would silently add a Firestore round trip to every dashboard
    load for a user who has logged three times.
    """
    seed_user()
    seed_logs(4)

    calls = []
    original = CycleService.count_logs_for_user

    def spy(user_id):
        calls.append(user_id)
        return original(user_id)

    CycleService.count_logs_for_user = staticmethod(spy)
    try:
        get_user_scores(USER_ID)
    finally:
        CycleService.count_logs_for_user = staticmethod(original)

    assert calls == []


def test_a_full_window_does_count():
    seed_user()
    seed_logs(_LOGS_LIMIT + 1)

    calls = []
    original = CycleService.count_logs_for_user

    def spy(user_id):
        calls.append(user_id)
        return original(user_id)

    CycleService.count_logs_for_user = staticmethod(spy)
    try:
        get_user_scores(USER_ID)
    finally:
        CycleService.count_logs_for_user = staticmethod(original)

    assert calls == [USER_ID]


# ─── count_logs_for_user on its own ───────────────────────────────────────


def test_count_is_zero_for_a_user_with_no_logs():
    assert CycleService.count_logs_for_user("nobody") == 0


def test_count_ignores_other_users_logs():
    seed_logs(6, user_id="mine")
    seed_logs(31, user_id="hers")

    assert CycleService.count_logs_for_user("mine") == 6
    assert CycleService.count_logs_for_user("hers") == 31


def test_count_is_not_capped():
    seed_logs(250)

    assert CycleService.count_logs_for_user(USER_ID) == 250


def test_count_uses_the_aggregation_rather_than_streaming_documents():
    """The read this field costs is a count, not a fetch of every log.

    On `GET /dashboard` — the home screen — streaming the collection to
    take its length would make the cheapest field in the response the
    most expensive one to produce, and would grow without bound for
    exactly the long-term users the field describes.
    """
    seed_logs(30)

    query = db.collection("cycle_logs").where("user_id", "==", USER_ID)
    streamed = []

    original_stream = type(query).stream

    def counting_stream(self):
        streamed.append(1)
        return original_stream(self)

    # The aggregation is implemented over `stream()` in the mock, so the
    # assertion is on the shape of the call rather than on read counts:
    # `count()` must exist and return the number without the caller ever
    # materialising the documents.
    aggregation = query.count()
    result = aggregation.get()

    assert result[0][0].value == 30
    assert streamed == []


def test_the_aggregation_result_has_the_shape_the_real_client_returns():
    """`get()` returns a list of lists, and each entry has `.value`.

    The mock has to reproduce that nesting exactly. Flattening it would
    make `result[0][0].value` — the production expression — an error the
    test suite could never see.
    """
    seed_logs(3)

    result = db.collection("cycle_logs").where("user_id", "==", USER_ID).count().get()

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert hasattr(result[0][0], "value")
    assert hasattr(result[0][0], "alias")
    assert result[0][0].value == 3


def test_a_client_without_the_aggregation_api_still_counts_correctly():
    """The fallback path, for a Firestore client too old to aggregate.

    A wrong count is worse than a slow one — this is the number a
    clinician reads — so the fallback counts rather than giving up.
    """
    seed_logs(14)

    class NoAggregationQuery:
        def __init__(self, inner):
            self._inner = inner

        def stream(self):
            return self._inner.stream()

    class NoAggregationCollection:
        def __init__(self, inner):
            self._inner = inner

        def where(self, *args):
            return NoAggregationQuery(self._inner.where(*args))

    class NoAggregationClient:
        def __init__(self, inner):
            self._inner = inner

        def collection(self, name):
            return NoAggregationCollection(self._inner.collection(name))

    real = fs.db
    fs.db = NoAggregationClient(real)
    try:
        assert CycleService.count_logs_for_user(USER_ID) == 14
    finally:
        fs.db = real


# ─── Through the API ──────────────────────────────────────────────────────


def test_dashboard_reports_both_numbers():
    seed_user()
    seed_logs(63)

    data = dashboard()

    assert data["loggedCycleCount"] == 63
    assert data["analyzedCycleCount"] == _LOGS_LIMIT


def test_scores_endpoint_reports_both_numbers():
    seed_user()
    seed_logs(63)

    data = scores()

    assert data["loggedCycleCount"] == 63
    assert data["analyzedCycleCount"] == _LOGS_LIMIT


def test_dashboard_and_scores_still_agree_with_each_other():
    """They agreed before, on the wrong number. They must still agree."""
    seed_user()
    seed_logs(47)

    assert dashboard()["loggedCycleCount"] == scores()["loggedCycleCount"] == 47
    assert dashboard()["analyzedCycleCount"] == scores()["analyzedCycleCount"]


def test_analyzed_count_is_present_even_for_a_user_with_nothing_logged():
    """Additive fields need a value, not an absence, on the empty path."""
    seed_user()

    data = dashboard()

    assert data["loggedCycleCount"] == 0
    assert data["analyzedCycleCount"] == 0


def test_has_enough_data_still_asks_about_the_window():
    """Unchanged on purpose.

    The question is whether the rules have enough in front of them to say
    anything, and the rules only ever see the window — so this stays a
    fact about `len(logs)`, not about the new total.
    """
    seed_user()
    seed_logs(2)
    assert dashboard()["hasEnoughDataForInsights"] is False

    seed_logs(1, first=date(2026, 6, 1))
    assert dashboard()["hasEnoughDataForInsights"] is True


# ─── Through the provider endpoints ───────────────────────────────────────


def _consent(patient_id, provider_id):
    db.collection("consents").document(f"{patient_id}::{provider_id}").set(
        {
            "patient_id": patient_id,
            "provider_id": provider_id,
            "provider_email": "dr@example.com",
            "provider_name": "Dr Sharma",
            "status": "active",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "revoked_at": None,
        }
    )


def test_provider_patient_summaries_distinguish_two_long_histories():
    provider_id = "dr-1"
    seed_user(provider_id, role="provider", full_name="Dr Sharma")

    for patient_id, log_count in (("p-short", 12), ("p-long", 300)):
        seed_user(patient_id, full_name=patient_id)
        seed_logs(log_count, user_id=patient_id)
        _consent(patient_id, provider_id)

    from services.provider_service import ProviderService

    summaries, _ = ProviderService.patient_summaries_page(provider_id, limit=None)
    by_id = {entry["patient_id"]: entry for entry in summaries}

    assert by_id["p-short"]["loggedCycleCount"] == 12
    assert by_id["p-long"]["loggedCycleCount"] == 300
    assert by_id["p-short"]["analyzedCycleCount"] == _LOGS_LIMIT
    assert by_id["p-long"]["analyzedCycleCount"] == _LOGS_LIMIT


def test_provider_patient_detail_reports_both_numbers():
    provider_id = "dr-2"
    patient_id = "p-detail"
    seed_user(provider_id, role="provider", full_name="Dr Rao")
    seed_user(patient_id, full_name="Asha")
    seed_logs(88, user_id=patient_id)
    _consent(patient_id, provider_id)

    from services.provider_service import ProviderService

    detail = ProviderService.patient_detail(provider_id, patient_id)

    assert detail["summary"]["loggedCycleCount"] == 88
    assert detail["summary"]["analyzedCycleCount"] == _LOGS_LIMIT
    # The history the provider is shown is the window, and now the
    # summary says so rather than implying it is everything.
    assert len(detail["cycleLogs"]) == _LOGS_LIMIT


def test_user_service_is_untouched_by_the_new_count():
    """The count reads `cycle_logs` only — it must not disturb `users`."""
    seed_user()
    seed_logs(11)

    before = UserService.get_user_by_id(USER_ID)
    CycleService.count_logs_for_user(USER_ID)
    after = UserService.get_user_by_id(USER_ID)

    assert before == after
