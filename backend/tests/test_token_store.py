"""Auth tokens outliving the process that minted them (issue #417).

Refresh, reset, verification and deletion tokens were four module-level
dicts. The tests below are written against the consequences of that
rather than against the storage: a token minted "on another worker"
resolves here, a revocation reaches sessions this process never saw, and
nothing accumulates forever.

"Another worker" is simulated by writing through ``token_store``
directly and reading back through ``core.auth``, and vice versa. Two real
processes cannot be spun up in a unit test, but the property that failed
across them — that the two paths disagree about what exists — is exactly
what a shared store makes untestable, and a shared *dict* would fail
these cases the moment the dict were per-process.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_auth import client  # noqa: F401,E402

import services.firestore_service as fs  # noqa: E402
from services import token_store  # noqa: E402
from core.auth import (  # noqa: E402
    create_refresh_token,
    generate_reset_token,
    generate_verification_token,
    refresh_token_store,
    reset_token_store,
    revoke_all_user_refresh_tokens,
    revoke_refresh_token,
    verification_token_store,
    verify_email_token,
    verify_refresh_token,
    verify_reset_token,
)

USER_ID = "token-store-user"
OTHER_USER_ID = "token-store-other"
EMAIL = "asha@example.com"


@pytest.fixture(autouse=True)
def _clean_store():
    token_store.clear()
    yield
    token_store.clear()


# ─── Refresh tokens ───────────────────────────────────────────────────────


def test_a_refresh_token_round_trips():
    token = create_refresh_token(USER_ID)

    assert verify_refresh_token(token) == USER_ID


def test_an_unknown_refresh_token_verifies_to_nobody():
    assert verify_refresh_token("not-a-token") is None


def test_a_refresh_token_survives_the_module_being_reimported():
    """The dict this replaces did not.

    Reaching the row through ``token_store`` rather than through the
    ``core.auth`` global is the closest a single process gets to "a
    different worker looked it up".
    """
    token = create_refresh_token(USER_ID)

    entry = token_store.get(token_store.KIND_REFRESH, token)

    assert entry is not None
    assert entry["user_id"] == USER_ID


def test_a_token_written_by_another_worker_is_accepted():
    token_store.put(
        token_store.KIND_REFRESH,
        "minted-elsewhere",
        {"user_id": USER_ID},
        timedelta(days=7),
    )

    assert verify_refresh_token("minted-elsewhere") == USER_ID


def test_an_expired_refresh_token_is_refused_and_dropped():
    token = create_refresh_token(USER_ID)
    _expire(token_store.KIND_REFRESH, token)

    assert verify_refresh_token(token) is None
    assert token_store.get(token_store.KIND_REFRESH, token) is None


def test_revoking_one_token_leaves_the_others():
    keep = create_refresh_token(USER_ID)
    drop = create_refresh_token(USER_ID)

    revoke_refresh_token(drop)

    assert verify_refresh_token(drop) is None
    assert verify_refresh_token(keep) == USER_ID


def test_revoke_all_ends_every_session_for_the_account():
    """What ``logout-all`` and account deletion depend on.

    Against a per-process dict this cleared only the sessions the
    handling worker happened to hold.
    """
    tokens = [create_refresh_token(USER_ID) for _ in range(3)]
    someone_else = create_refresh_token(OTHER_USER_ID)

    revoke_all_user_refresh_tokens(USER_ID)

    assert all(verify_refresh_token(token) is None for token in tokens)
    assert verify_refresh_token(someone_else) == OTHER_USER_ID


def test_revoke_all_reaches_sessions_this_path_never_created():
    token_store.put(
        token_store.KIND_REFRESH,
        "session-from-another-worker",
        {"user_id": USER_ID},
        timedelta(days=7),
    )

    revoke_all_user_refresh_tokens(USER_ID)

    assert verify_refresh_token("session-from-another-worker") is None


def test_the_raw_token_is_never_written_down():
    token = create_refresh_token(USER_ID)

    stored_ids = list(fs.db._collections.get(token_store.TOKENS_COLLECTION, {}))

    assert all(token not in doc_id for doc_id in stored_ids)
    assert token_store.document_id(token_store.KIND_REFRESH, token) in stored_ids


# ─── Reset and verification tokens ────────────────────────────────────────


def test_a_reset_token_round_trips():
    token = generate_reset_token(EMAIL)

    assert verify_reset_token(EMAIL, token) is True


def test_a_reset_token_is_single_use():
    token = generate_reset_token(EMAIL)
    verify_reset_token(EMAIL, token)

    assert verify_reset_token(EMAIL, token) is False


def test_a_wrong_guess_does_not_burn_the_real_reset_token():
    """Otherwise anyone who can post one bad token cancels a live reset."""
    token = generate_reset_token(EMAIL)

    assert verify_reset_token(EMAIL, "wrong") is False
    assert verify_reset_token(EMAIL, token) is True


def test_requesting_a_second_link_invalidates_the_first():
    first = generate_reset_token(EMAIL)
    second = generate_reset_token(EMAIL)

    assert verify_reset_token(EMAIL, first) is False
    assert verify_reset_token(EMAIL, second) is True


def test_a_reset_token_is_filed_under_the_canonical_address():
    """The link is requested and clicked with different spellings."""
    token = generate_reset_token("Asha@Example.COM")

    assert verify_reset_token("asha@example.com", token) is True


def test_an_expired_reset_token_is_refused():
    token = generate_reset_token(EMAIL)
    _expire(token_store.KIND_PASSWORD_RESET, EMAIL)

    assert verify_reset_token(EMAIL, token) is False


def test_the_email_address_is_not_stored_in_the_document_id():
    generate_reset_token(EMAIL)

    stored_ids = list(fs.db._collections.get(token_store.TOKENS_COLLECTION, {}))

    assert all(EMAIL not in doc_id for doc_id in stored_ids)


def test_a_verification_token_round_trips_and_is_single_use():
    token = generate_verification_token(EMAIL)

    assert verify_email_token(EMAIL, token) is True
    assert verify_email_token(EMAIL, token) is False


def test_reset_and_verification_tokens_do_not_collide():
    """Same key, different namespace — one must not satisfy the other."""
    reset = generate_reset_token(EMAIL)
    generate_verification_token(EMAIL)

    assert verify_email_token(EMAIL, reset) is False
    assert verify_reset_token(EMAIL, reset) is True


# ─── Housekeeping ─────────────────────────────────────────────────────────


def test_expired_rows_are_swept():
    """A token nobody presents again is never read, so nothing else
    removes it. This is why the dicts only ever grew."""
    live = create_refresh_token(USER_ID)
    stale = create_refresh_token(OTHER_USER_ID)
    _expire(token_store.KIND_REFRESH, stale)

    removed = token_store.purge_expired()

    assert removed == 1
    assert verify_refresh_token(live) == USER_ID


def test_sweeping_can_be_scoped_to_one_kind():
    stale_refresh = create_refresh_token(USER_ID)
    generate_reset_token(EMAIL)
    _expire(token_store.KIND_REFRESH, stale_refresh)
    _expire(token_store.KIND_PASSWORD_RESET, EMAIL)

    removed = token_store.purge_expired(token_store.KIND_REFRESH)

    assert removed == 1
    assert len(token_store.entries_of_kind(token_store.KIND_PASSWORD_RESET)) == 1


# ─── The compatibility views ──────────────────────────────────────────────


def test_the_exported_names_still_behave_like_mappings():
    """The suite reaches into these directly; they are views, not copies."""
    create_refresh_token(USER_ID)

    assert len(refresh_token_store) == 1
    refresh_token_store.clear()
    assert refresh_token_store == {}


def test_the_three_views_stay_separate():
    create_refresh_token(USER_ID)
    generate_reset_token(EMAIL)
    generate_verification_token(EMAIL)

    assert len(refresh_token_store) == 1
    assert len(reset_token_store) == 1
    assert len(verification_token_store) == 1


# ─── Helpers ──────────────────────────────────────────────────────────────


def _expire(kind, key):
    """Backdate a row's expiry.

    Rewriting the stored timestamp beats sleeping: the behaviour under
    test is "the window has closed", not "some seconds elapsed".
    """
    doc_id = token_store.document_id(kind, key)
    collection = fs.db.collection(token_store.TOKENS_COLLECTION)
    data = collection.document(doc_id).get().to_dict()
    data["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    collection.document(doc_id).set(data)
