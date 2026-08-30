"""What happens to a rate-limit bucket after nobody comes back (issue #499).

The enforcement behaviour is covered by ``test_auth_rate_limits.py``. What
is under test here is the other half of a bucket's life: that it carries an
expiry, that something eventually deletes it, and — the part worth being
careful about — that the sweep cannot delete a bucket somebody is still
locked out by.

Everything runs against ``MockFirestoreClient`` through the module-level
``db`` handle the service reads, which is the same handle the rest of the
suite swaps out, so the collection here is a plain dict and can be
inspected directly.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.rate_limit_service as rate_limit_service  # noqa: E402
from services.firestore_service import MockFirestoreClient  # noqa: E402
from services.rate_limit_service import (  # noqa: E402
    LEGACY_MAX_WINDOW_SECONDS,
    RateLimitService,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch):
    """A fresh in-memory database per test.

    ``_document`` and ``_collection`` both resolve ``db`` as a module
    global at call time, so replacing it here is enough — no reference
    captured at import can outlive the swap.
    """
    monkeypatch.setattr(rate_limit_service, "db", MockFirestoreClient())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _documents() -> dict:
    """The raw collection, so assertions can be about documents existing.

    ``MockFirestoreClient._collections`` is a plain dict of dicts keyed by
    collection name; ``MockCollectionReference`` is a view onto one of
    them, built fresh on every ``db.collection(...)`` call.
    """
    return rate_limit_service.db._collections.get(RateLimitService.COLLECTION, {})


def _write_raw(key: str, payload: dict) -> None:
    RateLimitService._document(key).set(payload)


def _read_raw(key: str) -> dict:
    return RateLimitService._document(key).get().to_dict() or {}


# ─── Every write says when it dies ────────────────────────────────────────


def test_a_recorded_attempt_carries_an_expiry():
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)

    stored = _read_raw("login_ip:abc")

    assert "expires_at" in stored
    assert stored["window_seconds"] == 300


def test_the_expiry_is_the_newest_attempt_plus_the_window():
    """Newest, not oldest — the bucket is empty only once the last one ages out."""
    before = _now()
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    after = _now()

    expires_at = RateLimitService._as_datetime(_read_raw("login_ip:abc")["expires_at"])

    assert before + timedelta(seconds=300) <= expires_at
    assert expires_at <= after + timedelta(seconds=300)


def test_the_expiry_moves_forward_with_each_attempt():
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    first = _read_raw("login_ip:abc")["expires_at"]

    # A second attempt one minute later.
    _write_raw(
        "login_ip:abc",
        {
            "timestamps": [(_now() - timedelta(seconds=60)).isoformat()],
            "expires_at": first,
            "window_seconds": 300,
        },
    )
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    second = _read_raw("login_ip:abc")["expires_at"]

    assert second > first


def test_the_over_limit_write_carries_an_expiry_too():
    """The bucket a caller under sustained attack keeps refreshing."""
    for _ in range(3):
        RateLimitService.is_rate_limited("login_ip:abc", limit=3, window_seconds=300)

    blocked = RateLimitService.is_rate_limited("login_ip:abc", limit=3, window_seconds=300)

    assert blocked is not None
    assert "expires_at" in _read_raw("login_ip:abc")


def test_timestamps_are_written_as_strings():
    """One document shape whichever backend produced it."""
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)

    stored = _read_raw("login_ip:abc")

    assert all(isinstance(entry, str) for entry in stored["timestamps"])


# ─── The sweep ────────────────────────────────────────────────────────────


def test_purge_deletes_a_bucket_whose_window_has_closed():
    _write_raw(
        "login_ip:dead",
        {
            "timestamps": [(_now() - timedelta(hours=2)).isoformat()],
            "expires_at": (_now() - timedelta(hours=1)).isoformat(),
            "window_seconds": 900,
        },
    )

    assert RateLimitService.purge_expired() == 1
    assert "login_ip:dead" not in _documents()


def test_purge_leaves_a_live_bucket_alone():
    RateLimitService.is_rate_limited("login_ip:live", limit=5, window_seconds=900)

    assert RateLimitService.purge_expired() == 0
    assert "login_ip:live" in _documents()


def test_purge_does_not_release_someone_who_is_currently_locked_out():
    """The failure mode a housekeeping job must not have.

    Three attempts against a limit of three, so the next call is refused.
    A sweep in between must not hand the caller a fresh budget.
    """
    for _ in range(3):
        RateLimitService.is_rate_limited("login_ip:blocked", limit=3, window_seconds=900)

    RateLimitService.purge_expired()

    assert (
        RateLimitService.is_rate_limited("login_ip:blocked", limit=3, window_seconds=900)
        is not None
    )


def test_purge_reports_how_many_it_took():
    for n in range(4):
        _write_raw(
            f"login_ip:dead{n}",
            {
                "timestamps": [(_now() - timedelta(hours=2)).isoformat()],
                "expires_at": (_now() - timedelta(hours=1)).isoformat(),
                "window_seconds": 900,
            },
        )
    RateLimitService.is_rate_limited("login_ip:live", limit=5, window_seconds=900)

    assert RateLimitService.purge_expired() == 4
    assert list(_documents()) == ["login_ip:live"]


def test_purge_on_an_empty_collection_is_a_no_op():
    assert RateLimitService.purge_expired() == 0


def test_an_expiry_exactly_now_is_expired():
    """A boundary that has to fall one way; the safe one is "gone"."""
    _write_raw(
        "login_ip:edge",
        {"timestamps": [], "expires_at": _now().isoformat(), "window_seconds": 900},
    )

    assert RateLimitService.purge_expired() == 1


# ─── Documents written before this change ─────────────────────────────────


def test_a_legacy_bucket_older_than_every_window_is_swept():
    """No `expires_at`, and its newest attempt predates the longest window."""
    _write_raw(
        "login_ip:legacy-old",
        {"timestamps": [(_now() - timedelta(seconds=LEGACY_MAX_WINDOW_SECONDS + 60)).isoformat()]},
    )

    assert RateLimitService.purge_expired() == 1


def test_a_recent_legacy_bucket_is_kept():
    """It could still be live under a long-window policy, so it is left.

    This is the conservative half of the rule: without an `expires_at`
    there is no way to know which policy wrote the document, so the sweep
    assumes the most generous window any of them uses.
    """
    _write_raw(
        "login_ip:legacy-recent",
        {"timestamps": [(_now() - timedelta(seconds=60)).isoformat()]},
    )

    assert RateLimitService.purge_expired() == 0
    assert "login_ip:legacy-recent" in _documents()


def test_a_legacy_bucket_holding_naive_datetimes_is_still_read():
    """The mock client stored whatever it was given, which was `datetime`.

    Naive, and read as UTC — this codebase works in UTC throughout, so a
    naive value it produced is a UTC one with the marker missing. Written
    here the same way rather than with a bare `datetime.now()`, which
    would make the assertion depend on the host's offset.
    """
    naive_utc = (_now() - timedelta(seconds=LEGACY_MAX_WINDOW_SECONDS + 60)).replace(
        tzinfo=None
    )
    _write_raw("login_ip:legacy-naive", {"timestamps": [naive_utc]})

    assert RateLimitService.purge_expired() == 1


def test_a_bucket_with_nothing_readable_in_it_is_swept():
    """Nothing to protect: no expiry, and no timestamp that parses."""
    _write_raw("login_ip:junk", {"timestamps": ["not-a-timestamp", None, 42]})

    assert RateLimitService.purge_expired() == 1


def test_a_bucket_with_no_fields_at_all_is_swept():
    _write_raw("login_ip:empty", {})

    assert RateLimitService.purge_expired() == 1


def test_an_unparseable_expiry_falls_back_to_the_timestamps():
    _write_raw(
        "login_ip:bad-expiry",
        {
            "timestamps": [(_now() - timedelta(seconds=30)).isoformat()],
            "expires_at": "sometime next week",
        },
    )

    # Recent attempt, so the legacy rule keeps it rather than the unusable
    # `expires_at` deleting it.
    assert RateLimitService.purge_expired() == 0


# ─── Reading documents this module did not write ──────────────────────────


def test_a_legacy_document_is_still_enforced_correctly():
    """Existing deployments must not have their buckets reset by the upgrade."""
    recent = [(_now() - timedelta(seconds=n)).isoformat() for n in (30, 20, 10)]
    _write_raw("login_ip:mixed", {"timestamps": recent})

    assert (
        RateLimitService.is_rate_limited("login_ip:mixed", limit=3, window_seconds=900)
        is not None
    )


def test_a_timestamps_field_that_is_not_a_list_is_ignored():
    _write_raw("login_ip:wrong-type", {"timestamps": "yesterday"})

    assert (
        RateLimitService.is_rate_limited("login_ip:wrong-type", limit=1, window_seconds=900)
        is None
    )


def test_retry_after_is_measured_from_the_oldest_attempt_whatever_the_order():
    """`is_rate_limited` takes `[0]`; the sort is what makes that the oldest."""
    unordered = [
        (_now() - timedelta(seconds=10)).isoformat(),
        (_now() - timedelta(seconds=200)).isoformat(),
        (_now() - timedelta(seconds=100)).isoformat(),
    ]
    _write_raw("login_ip:unordered", {"timestamps": unordered})

    remaining = RateLimitService.is_rate_limited(
        "login_ip:unordered", limit=3, window_seconds=300
    )

    # The oldest is 200s into a 300s window, so about 100s left — not the
    # ~290s the 10-second-old entry would give.
    assert remaining is not None
    assert 90 <= remaining <= 105


# ─── reset() still works ──────────────────────────────────────────────────


def test_reset_removes_the_document_entirely():
    RateLimitService.is_rate_limited("login_account:abc", limit=5, window_seconds=900)

    RateLimitService.reset("login_account:abc")

    assert "login_account:abc" not in _documents()
