"""Page boundaries on /provider/patients when a patient is gone (issue #538).

``/provider/patients`` slices the consents before the fan-out — that is
what #406 bought and it is right. What was wrong is that the envelope was
assembled from two numbers taken on either side of a filter that can drop
rows:

    window = consents[offset : offset + limit + 1]
    has_more = len(window) > limit          # measured on the consents
    ...
        if not patient:
            continue                        # <- row dropped here

    "nextOffset": offset + len(patients)    # measured on the summaries

So the offset the client resumed from was short by exactly the number of
skips, and the next page re-served consents the previous one had already
consumed.

The duplicate card is the visible symptom. The one that reaches a user is
the audit trail: every summary written also writes an access-log row, so
re-serving a consent recorded a second "your data was viewed" entry for a
view that happened once. ``test_a_full_walk_records_exactly_one_view_per_patient``
is the assertion this file exists for.

A consent whose patient has deleted her account is a real state, not a
contrived one: ``data_privacy_service`` removes the user document, and the
consent is a relationship record living in its own collection.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_auth import client, mock_auth_dependencies  # noqa: F401,E402

import services.firestore_service as fs  # noqa: E402
from main import app  # noqa: E402
from core.auth import get_current_user  # noqa: E402
from services.access_log_service import ACCESS_LOG_COLLECTION  # noqa: E402
from services.provider_service import (  # noqa: E402
    CONSENTS_COLLECTION,
    ProviderService,
)

PATIENTS_URL = "/api/v1/provider/patients"

PROVIDER_ID = "provider-1"


@pytest.fixture(autouse=True)
def _clean_store():
    fs.db._collections = {}
    fs.db._counters = {}
    yield
    fs.db._collections = {}
    fs.db._counters = {}
    app.dependency_overrides.clear()


def _as_provider():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": PROVIDER_ID,
        "username": PROVIDER_ID,
        "role": "provider",
    }


def _seed(count: int, *, deleted: set[int] = frozenset()):
    """``count`` active consents; the indices in ``deleted`` get no user doc.

    ``created_at`` is spaced a minute apart so newest-first is unambiguous
    — a paging test over rows that sort equal proves nothing.
    """
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        patient_id = f"patient-{index:03d}"
        fs.db.collection(CONSENTS_COLLECTION).document(
            f"{patient_id}::{PROVIDER_ID}"
        ).set(
            {
                "patient_id": patient_id,
                "provider_id": PROVIDER_ID,
                "status": "active",
                "created_at": base + timedelta(minutes=index),
                "updated_at": base + timedelta(minutes=index),
            }
        )
        if index in deleted:
            continue
        fs.db.collection("users").document(patient_id).set(
            {"id": patient_id, "full_name": f"Patient {index:03d}", "age": 30}
        )
    fs.db.collection("users").document(PROVIDER_ID).set(
        {"id": PROVIDER_ID, "full_name": "Dr Provider", "role": "provider"}
    )


def _walk(limit: int):
    """Page to the end the way the dashboard's "Load more" does.

    Follows the server's ``nextOffset`` rather than counting rows locally,
    because that is exactly what ``ProviderDashboardPage`` does:

        setNextOffset(page.page?.hasMore ? page.page.nextOffset : null);

    Bounded so a non-advancing offset fails as an assertion rather than
    hanging the suite.
    """
    seen = []
    offset = 0
    for _ in range(50):
        body = client.get(f"{PATIENTS_URL}?limit={limit}&offset={offset}").json()
        seen.extend(p["patient_id"] for p in body["patients"])
        page = body["page"]
        if not page["hasMore"]:
            return seen
        assert page["nextOffset"] is not None
        assert page["nextOffset"] > offset, "nextOffset must advance"
        offset = page["nextOffset"]
    pytest.fail("paging did not terminate")


def _access_rows():
    collection = fs.db.collection(ACCESS_LOG_COLLECTION)
    return [doc.to_dict() for doc in collection.stream()]


# ─── The reproduction ────────────────────────────────────────────────────


def test_the_next_page_does_not_repeat_patients_from_this_one():
    """25 consents, three of them for accounts that no longer exist.

    Page one consumed consents 0-19 and reported ``nextOffset: 17``, so
    17, 18 and 19 were served again on page two.
    """
    _seed(25, deleted={2, 5, 9})
    _as_provider()

    first = client.get(f"{PATIENTS_URL}?limit=20&offset=0").json()
    second = client.get(
        f"{PATIENTS_URL}?limit=20&offset={first['page']['nextOffset']}"
    ).json()

    ids = [p["patient_id"] for p in first["patients"]] + [
        p["patient_id"] for p in second["patients"]
    ]

    assert len(ids) == len(set(ids)), "a patient appeared on two pages"


def test_a_full_walk_records_exactly_one_view_per_patient():
    """The half of this that reaches a patient.

    Each summary writes a ``patient_list`` access row by construction, so a
    consent served twice records a view that happened once as two. A
    patient checking whether her clinician looked at her records twice this
    week cannot tell a real second visit from a paging artifact.
    """
    _seed(25, deleted={2, 5, 9})
    _as_provider()

    _walk(limit=20)

    views = [row["patient_id"] for row in _access_rows()]

    assert len(views) == len(set(views)), "a view was recorded twice"
    assert len(views) == 22, "one row per surviving patient, no more, no fewer"


def test_a_full_walk_visits_every_consent_exactly_once():
    _seed(25, deleted={2, 5, 9})
    _as_provider()

    seen = _walk(limit=7)

    assert len(seen) == len(set(seen))
    assert len(seen) == 22
    assert "patient-002" not in seen


# ─── Short pages and dead ends ───────────────────────────────────────────


def test_a_page_is_full_when_the_roster_can_fill_it():
    """The skips are absorbed inside the request, not handed back.

    Ten consents, the four most-recent shares dead, a page of five: the
    client asked for five and five exist, so five come back. The old slice
    returned two — it consumed six consents, four of which vanished.
    """
    _seed(10, deleted={9, 8, 7, 6})
    _as_provider()

    body = client.get(f"{PATIENTS_URL}?limit=5&offset=0").json()

    assert len(body["patients"]) == 5
    assert body["page"]["count"] == 5


def test_a_run_of_deleted_patients_does_not_produce_a_load_more_that_loads_nothing():
    """``hasMore`` never consulted the filter.

    A page whose consents were all deleted patients returned
    ``count: 0, hasMore: true``: the dashboard drew "Load more", the click
    fetched another empty page, and the button stayed.
    """
    _seed(6, deleted={0, 1, 2, 3, 4, 5})
    _as_provider()

    body = client.get(f"{PATIENTS_URL}?limit=3&offset=0").json()

    assert body["patients"] == []
    assert body["page"]["hasMore"] is False
    assert body["page"]["nextOffset"] is None


def test_the_last_page_closes_even_when_it_ends_on_deleted_patients():
    _seed(8, deleted={6, 7})
    _as_provider()

    seen = _walk(limit=3)

    assert len(seen) == 6


# ─── The page object ─────────────────────────────────────────────────────


def test_consumed_counts_consents_not_summaries():
    # Newest-share-first, so patient-009 and patient-007 are the ones that
    # land on the first page.
    _seed(10, deleted={9, 7})
    _as_provider()

    page = ProviderService.patient_summaries_page(PROVIDER_ID, limit=4, offset=0)

    assert len(page.summaries) == 4
    assert page.skipped == 2
    assert page.consumed == 6
    assert page.next_offset == 6


def test_next_offset_is_none_on_the_last_page():
    _seed(3)
    _as_provider()

    page = ProviderService.patient_summaries_page(PROVIDER_ID, limit=20, offset=0)

    assert page.has_more is False
    assert page.next_offset is None
    assert page.skipped == 0


def test_limit_none_still_returns_the_whole_roster():
    """The service-layer callers that predate paging."""
    _seed(25, deleted={4})
    _as_provider()

    page = ProviderService.patient_summaries_page(PROVIDER_ID, limit=None)

    assert len(page.summaries) == 24
    assert page.has_more is False
    assert len(ProviderService.patient_summaries(PROVIDER_ID)) == 24


def test_an_offset_past_the_end_is_an_empty_last_page():
    _seed(3)
    _as_provider()

    body = client.get(f"{PATIENTS_URL}?limit=5&offset=99").json()

    assert body["patients"] == []
    assert body["page"]["hasMore"] is False
    assert body["page"]["nextOffset"] is None


# ─── Unchanged behaviour ─────────────────────────────────────────────────


def test_the_envelope_keeps_its_shape():
    """No client has to move in step with this."""
    _seed(3)
    _as_provider()

    page = client.get(PATIENTS_URL).json()["page"]

    assert set(page) == {"limit", "offset", "count", "hasMore", "nextOffset"}


def test_newest_share_first_is_preserved_across_skips():
    _seed(6, deleted={1, 4})
    _as_provider()

    seen = _walk(limit=2)

    assert seen == ["patient-005", "patient-003", "patient-002", "patient-000"]


def test_the_fan_out_still_stops_at_the_page(monkeypatch):
    """The property #406 bought, re-asserted against the new loop.

    A skipped consent costs one profile read and nothing else — no scoring
    pass, no access-log write — so walking past dead rows cannot quietly
    reintroduce roster-sized work.
    """
    _seed(30, deleted={29, 28})
    _as_provider()

    import services.provider_service as provider_service

    scored = []
    original = provider_service.get_user_scores

    def counting_scores(user_id):
        scored.append(user_id)
        return original(user_id)

    monkeypatch.setattr(provider_service, "get_user_scores", counting_scores)

    client.get(f"{PATIENTS_URL}?limit=6")

    assert len(scored) == 6
