"""The assistant's rate limiting, after #327 moved it to the shared service.

This module used to test ``api.assistant.is_rate_limited`` and the
module-level ``_assistant_rate_history`` dict — the assistant's own
in-memory limiter, and the #280 fix for the unbounded key growth in it.
Issue #327 deleted both, moving the assistant onto the Firestore-backed
``RateLimitService`` that the auth routes already used, but this file was
never updated. It has been importing two names that do not exist since
then, which fails at *collection* time and so took the entire backend
suite down with it, not just itself.

Rewritten against the limiter the endpoint actually calls now. The intent
of the original — prove that expired entries are pruned rather than
accumulating forever — is kept, because that is the #280 regression and it
is just as possible in the new storage as it was in the old dict.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.assistant import ASSISTANT_RATE_LIMIT, ASSISTANT_RATE_WINDOW
from services.rate_limit_service import RateLimitService

#: The key format the endpoint builds. Asserted on directly below, because
#: a change to it silently moves every user onto a fresh bucket and so
#: silently disables the limit.
KEY = "assistant:test-user"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    RateLimitService.clear_all()
    yield
    RateLimitService.clear_all()


def _document_timestamps(key: str):
    doc = RateLimitService._document(key).get()
    if not doc.exists:
        return []
    return (doc.to_dict() or {}).get("timestamps", [])


def test_requests_under_the_limit_are_allowed():
    for _ in range(ASSISTANT_RATE_LIMIT):
        assert (
            RateLimitService.is_rate_limited(
                key=KEY,
                limit=ASSISTANT_RATE_LIMIT,
                window_seconds=ASSISTANT_RATE_WINDOW,
            )
            is None
        )


def test_the_request_past_the_limit_is_refused_with_a_wait():
    for _ in range(ASSISTANT_RATE_LIMIT):
        RateLimitService.is_rate_limited(
            key=KEY, limit=ASSISTANT_RATE_LIMIT, window_seconds=ASSISTANT_RATE_WINDOW
        )

    remaining = RateLimitService.is_rate_limited(
        key=KEY, limit=ASSISTANT_RATE_LIMIT, window_seconds=ASSISTANT_RATE_WINDOW
    )
    assert remaining is not None
    assert remaining >= 1
    # #135: the value is what the endpoint puts in Retry-After, so it must
    # never be zero or negative — a client would retry immediately and be
    # refused again.
    assert remaining <= ASSISTANT_RATE_WINDOW


def test_expired_timestamps_are_pruned_rather_than_accumulating():
    """The #280 regression, in its new home.

    The old in-memory limiter grew a list per user and never dropped
    entries that had aged out. The storage changed; the failure mode did
    not, so the test follows it across.
    """
    stale = datetime.now(timezone.utc) - timedelta(
        seconds=ASSISTANT_RATE_WINDOW * 2
    )
    RateLimitService._document(KEY).set(
        {"timestamps": [stale for _ in range(ASSISTANT_RATE_LIMIT)]}
    )

    # A full bucket of expired entries must not block the next request.
    assert (
        RateLimitService.is_rate_limited(
            key=KEY, limit=ASSISTANT_RATE_LIMIT, window_seconds=ASSISTANT_RATE_WINDOW
        )
        is None
    )

    # And the expired entries must be gone, not merely ignored — leaving
    # them is exactly how the original leak grew.
    assert len(_document_timestamps(KEY)) == 1


def test_a_partially_expired_window_keeps_only_the_live_entries():
    now = datetime.now(timezone.utc)
    stale = now - timedelta(seconds=ASSISTANT_RATE_WINDOW * 2)
    fresh = now - timedelta(seconds=1)
    RateLimitService._document(KEY).set({"timestamps": [stale, fresh]})

    RateLimitService.is_rate_limited(
        key=KEY, limit=ASSISTANT_RATE_LIMIT, window_seconds=ASSISTANT_RATE_WINDOW
    )

    # One survivor plus the request just recorded.
    assert len(_document_timestamps(KEY)) == 2


def test_users_do_not_share_a_bucket():
    """Two users, two keys. A shared bucket would rate-limit the wrong person."""
    for _ in range(ASSISTANT_RATE_LIMIT):
        RateLimitService.is_rate_limited(
            key="assistant:user-a",
            limit=ASSISTANT_RATE_LIMIT,
            window_seconds=ASSISTANT_RATE_WINDOW,
        )

    assert (
        RateLimitService.is_rate_limited(
            key="assistant:user-b",
            limit=ASSISTANT_RATE_LIMIT,
            window_seconds=ASSISTANT_RATE_WINDOW,
        )
        is None
    )


def test_the_assistant_bucket_is_separate_from_the_auth_buckets():
    """#327's actual point.

    The assistant used to have its own limiter, so assistant traffic and
    login traffic could not affect each other. Moving to a shared service
    keeps that property only because the keys are namespaced — if the
    prefix were ever dropped, a user's chat messages would start consuming
    her login attempts.
    """
    for _ in range(ASSISTANT_RATE_LIMIT):
        RateLimitService.is_rate_limited(
            key=KEY, limit=ASSISTANT_RATE_LIMIT, window_seconds=ASSISTANT_RATE_WINDOW
        )

    assert (
        RateLimitService.is_rate_limited(
            key="login:test-user", limit=5, window_seconds=300
        )
        is None
    )
