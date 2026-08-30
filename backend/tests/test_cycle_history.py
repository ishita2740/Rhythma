"""Paging and filtering on GET /cycle/{user_id}/history (issue #331).

These tests run against the mock Firestore client with real logs written
through `CycleService.upsert_log`, rather than against a mocked service.
That matters here: the bug this replaces was a bad `limit` reaching a
Python slice as `docs[:-1]`, which a mocked service would have hidden
completely — the assertion would have been about what the route *passed*,
not about what came back.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
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
from services.firestore_service import CycleService, MockFirestoreClient  # noqa: E402

# Reuse the mock client already installed by whichever test module imported
# first, rather than swapping in a fresh one. `services.firestore_service.db`
# is a module global that every service reads through, so replacing it here
# would leave earlier test modules holding a reference to a client nothing
# writes to any more — the services would write to this one while their
# assertions read the old one. Same hazard test_privacy.py documents.
if not isinstance(fs.db, MockFirestoreClient):
    fs.db = MockFirestoreClient()
db = fs.db

client = TestClient(app)

USER_ID = "history-user"
OTHER_USER_ID = "someone-else"

HISTORY_URL = f"/api/v1/cycle/{USER_ID}/history"


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


def seed_logs(count, first=date(2026, 1, 1), step_days=28, user_id=USER_ID):
    """Write `count` logs, oldest first, `step_days` apart.

    Returns the start dates newest-first, which is the order the endpoint
    returns them in — so a test can compare against it directly.
    """
    starts = [first + timedelta(days=step_days * i) for i in range(count)]
    for index, start in enumerate(starts):
        CycleService.upsert_log(user_id, start, {"flow_intensity": "medium", "notes": f"log {index}"})
    return [start.isoformat() for start in reversed(starts)]


def returned_dates(response):
    return [entry["start_date"][:10] for entry in response.json()["entries"]]


def start_day(start):
    """Normalize a ``date`` or ``datetime`` start_date to its day string."""
    return start.date().isoformat() if isinstance(start, datetime) else start.isoformat()


def seed_raw_logs(*starts, user_id=USER_ID):
    """Write logs straight into the mock store, bypassing ``upsert_log``.

    ``upsert_log`` always coerces ``start_date`` to a UTC-midnight datetime,
    so it can never produce the mixed ``date``/``datetime`` shape this suite
    needs to exercise. Writing to the backing store directly reproduces the
    documents a migrated or legacy Firestore collection can legitimately
    hold (issue #129).
    """
    store = db.collection("cycle_logs").store
    for index, start in enumerate(starts):
        store[f"mixed-{user_id}-{index}"] = {
            "user_id": user_id,
            "start_date": start,
            "flow_intensity": "medium",
            "created_at": datetime.now(timezone.utc),
        }


# ─── Defaults and backwards compatibility ─────────────────────────────────


def test_no_query_parameters_returns_the_most_recent_entries_newest_first():
    """The call every current client makes must behave exactly as before."""
    expected = seed_logs(5)

    response = client.get(HISTORY_URL)

    assert response.status_code == 200
    assert returned_dates(response) == expected


def test_the_default_page_size_is_bounded():
    seed_logs(30)

    response = client.get(HISTORY_URL)

    assert response.status_code == 200
    assert len(response.json()["entries"]) == 20
    assert response.json()["page"]["limit"] == 20


def test_an_empty_history_is_a_200_with_an_empty_page():
    response = client.get(HISTORY_URL)

    assert response.status_code == 200
    assert response.json()["entries"] == []
    assert response.json()["page"]["hasMore"] is False
    assert response.json()["page"]["nextOffset"] is None


# ─── limit validation ─────────────────────────────────────────────────────


def test_a_negative_limit_is_rejected_rather_than_silently_dropping_a_log():
    """`?limit=-1` used to slice as docs[:-1] — all but the oldest entry.

    Not an error, not empty, and not what was asked for. The worst kind of
    bug: a plausible-looking answer.
    """
    seed_logs(4)

    response = client.get(HISTORY_URL, params={"limit": -1})

    assert response.status_code == 422


def test_a_zero_limit_is_rejected_rather_than_looking_like_no_logs():
    seed_logs(4)

    response = client.get(HISTORY_URL, params={"limit": 0})

    assert response.status_code == 422


def test_an_enormous_limit_is_rejected():
    """An unbounded response is the wrong default on a 2G connection."""
    seed_logs(3)

    response = client.get(HISTORY_URL, params={"limit": 100000})

    assert response.status_code == 422


def test_the_maximum_page_size_is_accepted():
    response = client.get(HISTORY_URL, params={"limit": 100})

    assert response.status_code == 200


def test_a_non_numeric_limit_is_rejected():
    response = client.get(HISTORY_URL, params={"limit": "all"})

    assert response.status_code == 422


def test_a_negative_offset_is_rejected():
    response = client.get(HISTORY_URL, params={"offset": -5})

    assert response.status_code == 422


# ─── Paging ───────────────────────────────────────────────────────────────


def test_offset_pages_through_the_history():
    expected = seed_logs(10)

    first = client.get(HISTORY_URL, params={"limit": 4, "offset": 0})
    second = client.get(HISTORY_URL, params={"limit": 4, "offset": 4})
    third = client.get(HISTORY_URL, params={"limit": 4, "offset": 8})

    assert returned_dates(first) == expected[0:4]
    assert returned_dates(second) == expected[4:8]
    assert returned_dates(third) == expected[8:10]


def test_paging_neither_repeats_nor_skips_an_entry():
    """Walk the whole history a page at a time and compare with one read."""
    expected = seed_logs(13)

    collected = []
    offset = 0
    while True:
        response = client.get(HISTORY_URL, params={"limit": 5, "offset": offset})
        page = response.json()
        collected.extend(entry["start_date"][:10] for entry in page["entries"])
        if not page["page"]["hasMore"]:
            break
        offset = page["page"]["nextOffset"]

    assert collected == expected
    assert len(collected) == len(set(collected))


def test_has_more_is_true_while_entries_remain():
    seed_logs(10)

    response = client.get(HISTORY_URL, params={"limit": 4})

    assert response.json()["page"]["hasMore"] is True
    assert response.json()["page"]["nextOffset"] == 4


def test_has_more_is_false_on_the_last_page():
    seed_logs(10)

    response = client.get(HISTORY_URL, params={"limit": 4, "offset": 8})

    assert response.json()["page"]["hasMore"] is False
    assert response.json()["page"]["nextOffset"] is None


def test_has_more_is_false_when_the_page_lands_exactly_on_the_end():
    """The off-by-one worth pinning: 8 logs, page size 4, second page.

    A naive `len(entries) == limit` check would report another page here
    and hand the client an empty one.
    """
    seed_logs(8)

    response = client.get(HISTORY_URL, params={"limit": 4, "offset": 4})

    assert len(response.json()["entries"]) == 4
    assert response.json()["page"]["hasMore"] is False


def test_an_offset_past_the_end_returns_an_empty_page_not_an_error():
    seed_logs(3)

    response = client.get(HISTORY_URL, params={"offset": 50})

    assert response.status_code == 200
    assert response.json()["entries"] == []
    assert response.json()["page"]["hasMore"] is False


def test_the_extra_document_is_not_leaked_into_the_page():
    """`has_more` is computed from a limit+1 fetch — that row must not ship."""
    seed_logs(6)

    response = client.get(HISTORY_URL, params={"limit": 3})

    assert len(response.json()["entries"]) == 3
    assert response.json()["page"]["count"] == 3


# ─── Date filtering ───────────────────────────────────────────────────────


def test_a_date_range_returns_only_that_window():
    seed_logs(6, first=date(2026, 1, 1), step_days=30)

    response = client.get(
        HISTORY_URL,
        params={"start_date": "2026-02-01", "end_date": "2026-04-30"},
    )

    # Seeded 30 days apart from 1 Jan: 1 Jan, 31 Jan, 2 Mar, 1 Apr, 1 May,
    # 31 May. Only the two inside the window come back.
    assert returned_dates(response) == ["2026-04-01", "2026-03-02"]


def test_both_bounds_are_inclusive():
    seed_logs(3, first=date(2026, 3, 1), step_days=1)

    response = client.get(
        HISTORY_URL,
        params={"start_date": "2026-03-01", "end_date": "2026-03-03"},
    )

    assert returned_dates(response) == ["2026-03-03", "2026-03-02", "2026-03-01"]


def test_a_single_day_window_returns_that_day():
    """start_date == end_date must return the day, not nothing."""
    seed_logs(3, first=date(2026, 3, 1), step_days=1)

    response = client.get(
        HISTORY_URL,
        params={"start_date": "2026-03-02", "end_date": "2026-03-02"},
    )

    assert returned_dates(response) == ["2026-03-02"]


def test_start_date_alone_is_an_open_ended_window():
    seed_logs(4, first=date(2026, 1, 1), step_days=30)

    response = client.get(HISTORY_URL, params={"start_date": "2026-03-01"})

    assert returned_dates(response) == ["2026-04-01", "2026-03-02"]


def test_end_date_alone_is_an_open_ended_window():
    seed_logs(4, first=date(2026, 1, 1), step_days=30)

    response = client.get(HISTORY_URL, params={"end_date": "2026-02-01"})

    assert returned_dates(response) == ["2026-01-31", "2026-01-01"]


def test_an_inverted_range_is_rejected_not_silently_empty():
    """Otherwise a caller bug reads as 'you logged nothing in March'."""
    seed_logs(4)

    response = client.get(
        HISTORY_URL,
        params={"start_date": "2026-06-01", "end_date": "2026-01-01"},
    )

    assert response.status_code == 422
    assert "end_date" in str(response.json()["detail"])


def test_a_malformed_date_is_rejected():
    response = client.get(HISTORY_URL, params={"start_date": "last-tuesday"})

    assert response.status_code == 422


def test_a_window_with_no_logs_is_an_empty_page():
    seed_logs(3, first=date(2026, 1, 1), step_days=1)

    response = client.get(
        HISTORY_URL,
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == []


def test_paging_and_filtering_compose():
    seed_logs(10, first=date(2026, 1, 1), step_days=1)

    first = client.get(
        HISTORY_URL,
        params={"start_date": "2026-01-03", "end_date": "2026-01-08", "limit": 3},
    )
    second = client.get(
        HISTORY_URL,
        params={
            "start_date": "2026-01-03",
            "end_date": "2026-01-08",
            "limit": 3,
            "offset": 3,
        },
    )

    assert returned_dates(first) == ["2026-01-08", "2026-01-07", "2026-01-06"]
    assert returned_dates(second) == ["2026-01-05", "2026-01-04", "2026-01-03"]
    assert second.json()["page"]["hasMore"] is False


# ─── Authorization ────────────────────────────────────────────────────────


def test_another_users_history_is_still_forbidden():
    response = client.get(f"/api/v1/cycle/{OTHER_USER_ID}/history")

    assert response.status_code == 403


def test_the_authorization_check_survives_every_new_parameter():
    """Paging must not become a way around the ownership check."""
    for params in (
        {"limit": 5},
        {"offset": 2},
        {"start_date": "2026-01-01"},
        {"end_date": "2026-12-31"},
        {"limit": 5, "offset": 5, "start_date": "2026-01-01", "end_date": "2026-12-31"},
    ):
        response = client.get(f"/api/v1/cycle/{OTHER_USER_ID}/history", params=params)
        assert response.status_code == 403, params


def test_another_users_logs_never_appear_in_a_page():
    """Filtering is by user first; a wide date range must not cross accounts."""
    mine = seed_logs(3, first=date(2026, 1, 1), step_days=1)
    seed_logs(3, first=date(2026, 1, 1), step_days=1, user_id=OTHER_USER_ID)

    response = client.get(HISTORY_URL, params={"limit": 100})

    assert returned_dates(response) == mine


# ─── Response shape ───────────────────────────────────────────────────────


def test_the_page_metadata_describes_the_request():
    seed_logs(10)

    body = client.get(HISTORY_URL, params={"limit": 3, "offset": 2}).json()

    assert body["page"] == {
        "limit": 3,
        "offset": 2,
        "count": 3,
        "total_count": 10,
        "hasMore": True,
        "nextOffset": 5,
    }


def test_entries_keep_the_fields_clients_already_read():
    """Typing the response must not silently drop Firestore's own fields."""
    CycleService.upsert_log(
        USER_ID,
        date(2026, 5, 1),
        {"flow_intensity": "heavy", "mood": "tired", "sleep_hours": 6.5},
    )

    entry = client.get(HISTORY_URL).json()["entries"][0]

    assert entry["flow_intensity"] == "heavy"
    assert entry["mood"] == "tired"
    assert entry["sleep_hours"] == 6.5
    assert entry["id"]
    assert entry["user_id"] == USER_ID
    assert entry["created_at"]


def test_a_partial_log_is_returned_as_stored():
    """Quick-log tiles write one field for a day; that is normal, not broken."""
    CycleService.upsert_log(USER_ID, date(2026, 5, 2), {"flow_intensity": "light"})

    entry = client.get(HISTORY_URL).json()["entries"][0]

    assert entry["flow_intensity"] == "light"
    assert entry["mood"] is None


# ─── Service layer ────────────────────────────────────────────────────────


def test_get_logs_page_returns_entries_and_a_has_more_flag():
    seed_logs(5)

    entries, has_more, total_count = CycleService.get_logs_page(USER_ID, limit=2)

    assert len(entries) == 2
    assert has_more is True
    assert total_count == 5


def test_get_logs_for_user_still_works_for_its_existing_callers():
    """The dashboard, predictions, insights and scoring all use this."""
    expected = seed_logs(4)

    logs = CycleService.get_logs_for_user(USER_ID, limit=3)

    assert [log["start_date"].date().isoformat() for log in logs] == expected[:3]


def test_get_logs_for_user_sorts_mixed_datetime_and_date_start_dates():
    """``start_date`` can be stored as either a bare ``date`` or a
    ``datetime``; ordering must interleave them by actual day, newest first.

    This is the edge case the old Python-side sort in ``get_logs_for_user``
    handled via a normalizing key before the composite-index query (PR
    #155) moved sorting into Firestore's ``order_by``. Python's default
    sort raises ``TypeError`` comparing ``date`` and ``datetime`` directly,
    so this pins the behavior so a future refactor cannot silently
    reintroduce incorrect ordering. See issue #129.
    """
    seed_raw_logs(
        date(2026, 2, 1),
        datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        date(2026, 4, 1),
    )

    logs = CycleService.get_logs_for_user(USER_ID, limit=10)

    assert [start_day(log["start_date"]) for log in logs] == [
        "2026-04-01",
        "2026-03-01",
        "2026-02-01",
    ]


def test_get_logs_for_user_limits_after_sorting_mixed_start_dates():
    """``limit`` applies to the *sorted* result, not to write order."""
    seed_raw_logs(
        date(2026, 1, 3),
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        date(2026, 1, 2),
    )

    logs = CycleService.get_logs_for_user(USER_ID, limit=2)

    assert [start_day(log["start_date"]) for log in logs] == [
        "2026-01-03",
        "2026-01-02",
    ]
