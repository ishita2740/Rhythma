"""Paging on the two provider list endpoints (issue #406).

``/cycle/history`` (#331) and ``/provider/access-log`` were already paged.
``/provider/patients`` and ``/provider/consents`` were not: both returned
the entire collection, always, with no ``limit`` accepted and no ``page``
returned.

``/patients`` is the expensive one. Building a single summary costs a
profile read, a scoring pass over that patient's cycle logs, *and* an
access-log write, so an unbounded list multiplied three kinds of work by
the size of the provider's roster on every dashboard render. Several
assertions below are about *how much work happens*, not about the payload,
because trimming the response while leaving the fan-out in place would
look like a fix and not be one.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_auth import client, mock_auth_dependencies  # noqa: F401,E402

import services.firestore_service as fs  # noqa: E402
import services.provider_service as provider_service  # noqa: E402
from main import app  # noqa: E402
from core.auth import get_current_user  # noqa: E402
from services.provider_service import (  # noqa: E402
    CONSENTS_COLLECTION,
    DEFAULT_CONSENTS_PAGE,
    DEFAULT_PATIENTS_PAGE,
    MAX_CONSENTS_PAGE,
    MAX_PATIENTS_PAGE,
    ConsentService,
    ProviderService,
)

PATIENTS_URL = "/api/v1/provider/patients"
CONSENTS_URL = "/api/v1/provider/consents"

PROVIDER_ID = "provider-1"
PATIENT_ID = "patient-1"


@pytest.fixture(autouse=True)
def _clean_store():
    fs.db._collections = {}
    yield
    fs.db._collections = {}
    app.dependency_overrides.clear()


def _as(user_id: str, role: str):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "username": user_id,
        "role": role,
    }


def _seed_consents(count: int, *, provider_id=PROVIDER_ID, status_="active"):
    """``count`` consents from distinct patients to one provider.

    ``created_at`` is spaced a minute apart so the newest-first order is
    unambiguous — a paging test on rows that sort equal proves nothing.
    """
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        patient_id = f"patient-{index:03d}"
        fs.db.collection(CONSENTS_COLLECTION).document(
            f"{patient_id}::{provider_id}"
        ).set(
            {
                "patient_id": patient_id,
                "provider_id": provider_id,
                "status": status_,
                "created_at": base + timedelta(minutes=index),
                "updated_at": base + timedelta(minutes=index),
            }
        )
        fs.db.collection("users").document(patient_id).set(
            {"id": patient_id, "full_name": f"Patient {index:03d}", "age": 30}
        )
    fs.db.collection("users").document(provider_id).set(
        {"id": provider_id, "full_name": "Dr Provider", "role": "provider"}
    )


# ── /provider/patients ────────────────────────────────────────────────────


def test_the_default_page_is_bounded():
    _seed_consents(DEFAULT_PATIENTS_PAGE + 5)
    _as(PROVIDER_ID, "provider")

    body = client.get(PATIENTS_URL).json()

    assert len(body["patients"]) == DEFAULT_PATIENTS_PAGE
    assert body["page"]["limit"] == DEFAULT_PATIENTS_PAGE
    assert body["page"]["hasMore"] is True
    assert body["page"]["nextOffset"] == DEFAULT_PATIENTS_PAGE


def test_the_envelope_matches_the_other_paged_endpoints():
    """Same five fields as /cycle/history and /provider/access-log.

    A client author should not have to read the source of each list to
    learn which shape comes back; #349 is what happens when they guess.
    """
    _seed_consents(3)
    _as(PROVIDER_ID, "provider")

    page = client.get(PATIENTS_URL).json()["page"]

    assert set(page) == {"limit", "offset", "count", "hasMore", "nextOffset"}


def test_a_custom_limit_is_honoured():
    _seed_consents(10)
    _as(PROVIDER_ID, "provider")

    body = client.get(f"{PATIENTS_URL}?limit=3").json()

    assert len(body["patients"]) == 3
    assert body["page"]["count"] == 3
    assert body["page"]["hasMore"] is True


def test_paging_walks_the_whole_roster_without_repeats_or_gaps():
    """The property that actually matters, asserted end to end."""
    _seed_consents(25)
    _as(PROVIDER_ID, "provider")

    seen = []
    offset = 0
    while True:
        body = client.get(f"{PATIENTS_URL}?limit=7&offset={offset}").json()
        seen.extend(row["patient_id"] for row in body["patients"])
        if not body["page"]["hasMore"]:
            break
        offset = body["page"]["nextOffset"]

    assert len(seen) == 25
    assert len(set(seen)) == 25, "a patient appeared on two pages"


def test_the_last_page_reports_no_next_offset():
    _seed_consents(5)
    _as(PROVIDER_ID, "provider")

    body = client.get(f"{PATIENTS_URL}?limit=10").json()

    assert body["page"]["hasMore"] is False
    assert body["page"]["nextOffset"] is None


def test_an_offset_past_the_end_is_an_empty_page_not_an_error():
    _seed_consents(3)
    _as(PROVIDER_ID, "provider")

    body = client.get(f"{PATIENTS_URL}?offset=500").json()

    assert body["patients"] == []
    assert body["page"]["hasMore"] is False
    assert body["page"]["nextOffset"] is None


@pytest.mark.parametrize("limit", [0, -1, MAX_PATIENTS_PAGE + 1, 100000])
def test_an_out_of_range_limit_is_rejected(limit):
    """#331's lesson: ``?limit=-1`` reached a slice as ``docs[:-1]``."""
    _seed_consents(2)
    _as(PROVIDER_ID, "provider")

    assert client.get(f"{PATIENTS_URL}?limit={limit}").status_code == 422


def test_a_negative_offset_is_rejected():
    _seed_consents(2)
    _as(PROVIDER_ID, "provider")

    assert client.get(f"{PATIENTS_URL}?offset=-1").status_code == 422


def test_newest_share_comes_first():
    _seed_consents(5)
    _as(PROVIDER_ID, "provider")

    names = [row["patient_id"] for row in client.get(PATIENTS_URL).json()["patients"]]

    assert names == sorted(names, reverse=True)


def test_revoked_consents_are_still_excluded():
    """Paging must not become a way to see a patient who revoked."""
    _seed_consents(3)
    fs.db.collection(CONSENTS_COLLECTION).document(
        f"patient-001::{PROVIDER_ID}"
    ).update({"status": "revoked"})
    _as(PROVIDER_ID, "provider")

    ids = [row["patient_id"] for row in client.get(PATIENTS_URL).json()["patients"]]

    assert "patient-001" not in ids
    assert len(ids) == 2


def test_a_patient_cannot_read_the_provider_list():
    _seed_consents(2)
    _as(PATIENT_ID, "patient")

    assert client.get(PATIENTS_URL).status_code == 403


# ── The cost, not just the payload ────────────────────────────────────────


def test_only_the_page_is_scored(monkeypatch):
    """The assertion this whole issue is about.

    Slicing the finished summaries would produce a correct-looking
    response and leave the scoring pass running for the entire roster.
    The slice has to happen on the consents, before the fan-out.
    """
    _seed_consents(30)
    _as(PROVIDER_ID, "provider")

    scored = []
    original = provider_service.get_user_scores

    def counting_scores(user_id):
        scored.append(user_id)
        return original(user_id)

    monkeypatch.setattr(provider_service, "get_user_scores", counting_scores)

    client.get(f"{PATIENTS_URL}?limit=5")

    assert len(scored) == 5, f"scored {len(scored)} patients for a 5-row page"


def test_only_the_page_is_access_logged(monkeypatch):
    """#350's rows follow the page, and are more truthful for it.

    A provider who loaded page one did not look at page four, so writing
    an access record for page four's patients would tell them their data
    was viewed when it was not.
    """
    _seed_consents(30)
    _as(PROVIDER_ID, "provider")

    recorded = []
    original = provider_service.access_log_service.record

    def counting_record(**kwargs):
        recorded.append(kwargs["patient_id"])
        return original(**kwargs)

    monkeypatch.setattr(
        provider_service.access_log_service, "record", counting_record
    )

    client.get(f"{PATIENTS_URL}?limit=4")

    assert len(recorded) == 4


def test_profile_reads_scale_with_the_page_not_the_roster(monkeypatch):
    """Thirty consents, a six-row page, and the reads follow the page.

    The exact count is pinned rather than bounded loosely, because it
    documents something worth knowing: each row costs *two* profile reads,
    not one. ``patient_summaries_page`` looks the patient up, and
    ``get_user_scores`` looks the same patient up again internally. Plus
    one for the provider's own display name, that is ``2n + 1``.

    The duplicate is pre-existing and orthogonal to #406 — it was there
    when the endpoint was unbounded, where it mattered far more. It is
    left alone here so this change stays a paging change, but the number
    is asserted so that halving it later is a visible improvement rather
    than an invisible one, and so that a regression back to roster-sized
    reads fails loudly.
    """
    _seed_consents(30)
    _as(PROVIDER_ID, "provider")

    reads = []
    original = provider_service.UserService.get_user_by_id

    def counting_get(user_id):
        reads.append(user_id)
        return original(user_id)

    monkeypatch.setattr(
        provider_service.UserService, "get_user_by_id", staticmethod(counting_get)
    )

    client.get(f"{PATIENTS_URL}?limit=6")

    assert len(reads) == 6 * 2 + 1
    # The point of the issue: nothing scales with the 30 seeded consents.
    assert len(reads) < 30


# ── /provider/consents ────────────────────────────────────────────────────


def _seed_patient_consents(count: int):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        provider_id = f"prov-{index:03d}"
        fs.db.collection(CONSENTS_COLLECTION).document(
            f"{PATIENT_ID}::{provider_id}"
        ).set(
            {
                "patient_id": PATIENT_ID,
                "provider_id": provider_id,
                "status": "active",
                "created_at": base + timedelta(minutes=index),
                "updated_at": base + timedelta(minutes=index),
            }
        )


def test_consents_default_page_is_bounded():
    _seed_patient_consents(DEFAULT_CONSENTS_PAGE + 4)
    _as(PATIENT_ID, "patient")

    body = client.get(CONSENTS_URL).json()

    assert len(body["consents"]) == DEFAULT_CONSENTS_PAGE
    assert body["page"]["hasMore"] is True


def test_consents_custom_limit_and_offset():
    _seed_patient_consents(10)
    _as(PATIENT_ID, "patient")

    first = client.get(f"{CONSENTS_URL}?limit=4").json()
    second = client.get(f"{CONSENTS_URL}?limit=4&offset=4").json()

    assert len(first["consents"]) == 4
    assert len(second["consents"]) == 4
    first_ids = {row["id"] for row in first["consents"]}
    second_ids = {row["id"] for row in second["consents"]}
    assert first_ids.isdisjoint(second_ids)


def test_consents_revoked_entries_are_still_listed():
    """Unlike /patients, this list is a history and includes revoked rows."""
    _seed_patient_consents(3)
    fs.db.collection(CONSENTS_COLLECTION).document(
        f"{PATIENT_ID}::prov-001"
    ).update({"status": "revoked"})
    _as(PATIENT_ID, "patient")

    body = client.get(CONSENTS_URL).json()

    assert len(body["consents"]) == 3


def test_the_access_enrichment_still_lands_on_paged_rows():
    """#350's viewCount / lastAccessedAt must survive the slice."""
    _seed_patient_consents(5)
    _as(PATIENT_ID, "patient")

    body = client.get(f"{CONSENTS_URL}?limit=2").json()

    assert len(body["consents"]) == 2
    for consent in body["consents"]:
        assert "viewCount" in consent
        assert "lastAccessedAt" in consent


@pytest.mark.parametrize("limit", [0, -1, MAX_CONSENTS_PAGE + 1])
def test_consents_out_of_range_limit_is_rejected(limit):
    _seed_patient_consents(2)
    _as(PATIENT_ID, "patient")

    assert client.get(f"{CONSENTS_URL}?limit={limit}").status_code == 422


def test_a_provider_cannot_read_the_consent_list():
    _seed_patient_consents(2)
    _as(PROVIDER_ID, "provider")

    assert client.get(CONSENTS_URL).status_code == 403


# ── Service layer ─────────────────────────────────────────────────────────


def test_the_unpaged_summary_helper_still_returns_everything():
    """Kept for service-layer callers that predate the page method."""
    _seed_consents(25)

    assert len(ProviderService.patient_summaries(PROVIDER_ID)) == 25


def test_sorting_survives_a_string_created_at():
    """A Firestore round trip can hand back an ISO string, not a datetime.

    Comparing those against each other mid-sort raises TypeError, which
    would turn a paged read into a 500 on real Firestore while passing
    against the mock.
    """
    fs.db.collection(CONSENTS_COLLECTION).document("a::p").set(
        {
            "patient_id": "a",
            "provider_id": "p",
            "status": "active",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    fs.db.collection(CONSENTS_COLLECTION).document("b::p").set(
        {
            "patient_id": "b",
            "provider_id": "p",
            "status": "active",
            "created_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
        }
    )

    consents = ConsentService.list_active_for_provider("p")

    assert [row["patient_id"] for row in consents] == ["b", "a"]


def test_sorting_survives_a_missing_created_at():
    fs.db.collection(CONSENTS_COLLECTION).document("a::p").set(
        {"patient_id": "a", "provider_id": "p", "status": "active"}
    )
    fs.db.collection(CONSENTS_COLLECTION).document("b::p").set(
        {
            "patient_id": "b",
            "provider_id": "p",
            "status": "active",
            "created_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
        }
    )

    consents = ConsentService.list_active_for_provider("p")

    assert [row["patient_id"] for row in consents] == ["b", "a"]


def test_the_page_boundary_is_stable_across_identical_timestamps():
    """Two consents created in the same instant must not swap places.

    A boundary that moves between requests is a row the caller either
    sees twice or never sees at all.
    """
    same = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for name in ("a", "b", "c", "d"):
        fs.db.collection(CONSENTS_COLLECTION).document(f"{name}::p").set(
            {
                "patient_id": name,
                "provider_id": "p",
                "status": "active",
                "created_at": same,
            }
        )

    first = [row["patient_id"] for row in ConsentService.list_active_for_provider("p")]
    second = [row["patient_id"] for row in ConsentService.list_active_for_provider("p")]

    assert first == second
