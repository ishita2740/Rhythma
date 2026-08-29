"""Access-log reads filter in the query, not after it (issue #541).

``_entries_for_patient`` streamed the entire ``access_log`` collection and
dropped the rows that did not match:

    for doc in _stream_all():
        data = doc.to_dict() or {}
        if data.get("patient_id") != patient_id:
            continue

while the docstring directly above it stated the precondition its own cost
argument rested on — *"The collection is filtered by ``patient_id`` first,
so this sorts one patient's own records — tens, not thousands"*. There was
no ``where``.

**What these tests assert, and why.** From the response body a
query-filtered read and a scan-then-filter read are indistinguishable:
both return exactly this patient's rows in exactly the same order. That is
precisely why this survived, and it is why the assertions below count the
documents the collection hands out rather than the rows the caller gets
back. A test on the payload alone would have passed against the old code.

This was never a data leak. The filter ran before anything was returned
and ``/provider/access-log`` is scoped to ``current_user["id"]``. It is
cost — and ``access_log`` is the fastest-growing collection in the schema,
one row per patient per provider-dashboard render.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_auth import client, mock_auth_dependencies  # noqa: F401,E402

import services.firestore_service as fs  # noqa: E402
from services import access_log_service  # noqa: E402
from services.access_log_service import (  # noqa: E402
    ACCESS_LOG_COLLECTION,
    VIEW_PATIENT_DETAIL,
    VIEW_PATIENT_LIST,
    count_for_patient,
    doc_ids_for_user,
    list_for_patient,
    summary_for_patient,
)

PATIENT = "patient-under-test"
PROVIDER = "provider-1"


@pytest.fixture(autouse=True)
def _clean_store():
    fs.db._collections = {}
    fs.db._counters = {}
    yield
    fs.db._collections = {}
    fs.db._counters = {}


def _seed(patient_id: str, count: int, *, provider_id: str = PROVIDER, base_minute: int = 0):
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for index in range(count):
        fs.db.collection(ACCESS_LOG_COLLECTION).add(
            {
                "patient_id": patient_id,
                "provider_id": provider_id,
                "provider_name": "Dr Provider",
                "view": VIEW_PATIENT_DETAIL,
                "consent_id": f"{patient_id}::{provider_id}",
                "accessed_at": base + timedelta(minutes=base_minute + index),
            }
        )


class _CountingCollection:
    """Wraps the mock collection and records how it was asked for data.

    The two things worth knowing are (a) whether an equality filter was
    issued at all, and (b) how many documents were actually handed over —
    because "returns the right rows" is true of both the old code and the
    new one.
    """

    def __init__(self, inner, log):
        self._inner = inner
        self._log = log

    def where(self, field, op, value):
        self._log["filters"].append((field, op, value))
        return _CountingQuery(self._inner.where(field, op, value), self._log)

    def stream(self):
        self._log["bare_streams"] += 1
        for doc in self._inner.stream():
            self._log["documents"] += 1
            yield doc

    def add(self, data):
        return self._inner.add(data)

    def document(self, doc_id):
        self._log["documents"] += 1
        return self._inner.document(doc_id)

    @property
    def store(self):
        self._log["store_reads"] += 1
        return self._inner.store


class _CountingQuery:
    def __init__(self, inner, log):
        self._inner = inner
        self._log = log

    def where(self, field, op, value):
        self._log["filters"].append((field, op, value))
        return _CountingQuery(self._inner.where(field, op, value), self._log)

    def stream(self):
        for doc in self._inner.stream():
            self._log["documents"] += 1
            yield doc


@pytest.fixture
def observed(monkeypatch):
    """Watch every call `access_log_service` makes to its collection."""
    log = {"filters": [], "bare_streams": 0, "documents": 0, "store_reads": 0}
    real_db = fs.db

    class _ObservedDb:
        def collection(self, name):
            inner = real_db.collection(name)
            if name != ACCESS_LOG_COLLECTION:
                return inner
            return _CountingCollection(inner, log)

    monkeypatch.setattr(access_log_service, "_db", lambda: _ObservedDb())
    return log


# ─── The filter runs in the query ────────────────────────────────────────


def test_list_for_patient_filters_in_the_query(observed):
    _seed(PATIENT, 3)

    list_for_patient(PATIENT)

    assert ("patient_id", "==", PATIENT) in observed["filters"]
    assert observed["bare_streams"] == 0, "the whole collection was streamed"
    assert observed["store_reads"] == 0, "reached past the public API into the mock"


def test_the_read_scales_with_this_patient_not_the_collection(observed):
    """200 rows for other patients, 3 for ours. The read touches 3.

    The assertion is on documents deserialised, not on rows returned — the
    old code returned the same 3 and read all 203 to find them.
    """
    _seed("someone-else", 200)
    _seed(PATIENT, 3, base_minute=500)

    entries, _ = list_for_patient(PATIENT)

    assert len(entries) == 3
    assert observed["documents"] == 3


def test_summary_for_patient_filters_in_the_query(observed):
    """The one that runs on every Sharing screen open, per consent page."""
    _seed("someone-else", 50)
    _seed(PATIENT, 2, base_minute=500)

    summary = summary_for_patient(PATIENT)

    assert summary[PROVIDER]["viewCount"] == 2
    assert ("patient_id", "==", PATIENT) in observed["filters"]
    assert observed["documents"] == 2


def test_count_for_patient_filters_in_the_query(observed):
    _seed("someone-else", 40)
    _seed(PATIENT, 5, base_minute=500)

    assert count_for_patient(PATIENT) == 5
    assert observed["documents"] == 5


def test_doc_ids_for_user_issues_two_filtered_queries_not_one_scan(observed):
    _seed("someone-else", 60)
    _seed(PATIENT, 4, base_minute=500)

    ids = doc_ids_for_user(PATIENT)

    assert len(ids) == 4
    assert observed["bare_streams"] == 0
    assert ("patient_id", "==", PATIENT) in observed["filters"]
    assert ("provider_id", "==", PATIENT) in observed["filters"]
    assert observed["documents"] == 4


def test_doc_ids_for_user_returns_each_row_once_when_a_user_is_on_both_sides():
    """Otherwise the cascade tries to delete the same document twice."""
    fs.db.collection(ACCESS_LOG_COLLECTION).add(
        {
            "patient_id": PATIENT,
            "provider_id": PATIENT,
            "view": VIEW_PATIENT_LIST,
            "accessed_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        }
    )

    ids = doc_ids_for_user(PATIENT)

    assert len(ids) == 1
    assert len(ids) == len(set(ids))


def test_doc_ids_for_user_still_covers_the_provider_side():
    """A provider closing her account must not leave rows naming her."""
    _seed("some-patient", 3, provider_id=PROVIDER)

    assert len(doc_ids_for_user(PROVIDER)) == 3


# ─── Behaviour that must not have changed ────────────────────────────────


def test_another_patients_rows_are_never_returned():
    _seed("someone-else", 5)
    _seed(PATIENT, 2, base_minute=500)

    entries, _ = list_for_patient(PATIENT)

    assert {entry["providerId"] for entry in entries} == {PROVIDER}
    assert count_for_patient("someone-else") == 5
    assert count_for_patient("nobody") == 0


def test_newest_first_order_is_preserved():
    _seed(PATIENT, 5)

    entries, _ = list_for_patient(PATIENT)
    timestamps = [entry["accessedAt"] for entry in entries]

    assert timestamps == sorted(timestamps, reverse=True)


def test_paging_contract_is_unchanged():
    """`hasMore` still comes from reading one past the page (#331/#350)."""
    _seed(PATIENT, 25)

    first, has_more = list_for_patient(PATIENT, limit=20, offset=0)
    second, still_more = list_for_patient(PATIENT, limit=20, offset=20)

    assert len(first) == 20 and has_more is True
    assert len(second) == 5 and still_more is False
    assert {entry["id"] for entry in first}.isdisjoint(
        {entry["id"] for entry in second}
    )


def test_an_empty_history_is_an_empty_page():
    entries, has_more = list_for_patient(PATIENT)

    assert entries == []
    assert has_more is False
    assert summary_for_patient(PATIENT) == {}
    assert doc_ids_for_user(PATIENT) == []


def test_a_row_without_a_timestamp_does_not_break_the_sort():
    """Sorting is still done in Python, so it still has to tolerate this."""
    fs.db.collection(ACCESS_LOG_COLLECTION).add(
        {"patient_id": PATIENT, "provider_id": PROVIDER, "view": VIEW_PATIENT_LIST}
    )
    _seed(PATIENT, 2)

    entries, _ = list_for_patient(PATIENT)

    assert len(entries) == 3


def test_record_still_writes_a_readable_row():
    access_log_service.record(
        provider_id=PROVIDER,
        patient_id=PATIENT,
        view=VIEW_PATIENT_DETAIL,
        consent_id="consent-1",
        provider_name="Dr Provider",
    )

    entries, _ = list_for_patient(PATIENT)

    assert len(entries) == 1
    assert entries[0]["providerName"] == "Dr Provider"
    assert entries[0]["view"] == VIEW_PATIENT_DETAIL


def test_the_python_side_fallback_still_filters():
    """A stand-in with neither `where` nor `stream` must not return the lot.

    The fallback exists for a client that implements neither; it filters in
    Python because it has nothing else to filter with. If it ever stopped
    filtering, a caller would silently receive another patient's rows —
    which is the one way this could become the leak it never was.
    """

    class _StoreOnlyCollection:
        def __init__(self, inner):
            self.store = inner.store
            self._inner = inner

        def document(self, doc_id):
            return self._inner.document(doc_id)

    real_db = fs.db

    class _StoreOnlyDb:
        def collection(self, name):
            return _StoreOnlyCollection(real_db.collection(name))

    _seed("someone-else", 4)
    _seed(PATIENT, 2, base_minute=500)

    original = access_log_service._db
    access_log_service._db = lambda: _StoreOnlyDb()
    try:
        entries, _ = list_for_patient(PATIENT)
    finally:
        access_log_service._db = original

    assert len(entries) == 2
