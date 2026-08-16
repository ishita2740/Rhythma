"""Tests for data export and account erasure (issue #270).

These run against the in-memory mock Firestore that
``firestore_service.initialize_firebase()`` falls back to, seeded directly,
rather than against mocked service classes. That is deliberate: the bug
this PR fixes was a *missed collection*, and a test that mocks the service
layer cannot catch a missed collection — it can only re-assert whatever the
mock was told to return.
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
import firebase_admin.auth

from test_auth import client, mock_auth_dependencies

from services import data_privacy_service as privacy
from services.data_privacy_service import (
    CONVERSATIONS_COLLECTION,
    CYCLE_LOGS_COLLECTION,
    DELETION_AUDIT_COLLECTION,
    EXPORT_SCHEMA_VERSION,
    RATE_LIMITS_COLLECTION,
    USERS_COLLECTION,
    build_cycle_logs_csv,
    build_data_summary,
    build_export_bundle,
    clear_deletion_tokens,
    delete_account,
    deletion_record_for,
    export_filename,
    issue_deletion_token,
    purge_user_data,
    verify_deletion_token,
)
from services import firestore_service as fs

USER_ID = "test-user-id-123"
OTHER_USER_ID = "someone-else-456"


# ─── Fixtures ─────────────────────────────────────────────────────────────


def _reset_collections():
    """Drop every mock collection so each test starts from a known state."""
    collections = getattr(fs.db, "_collections", None)
    if collections is not None:
        collections.clear()
    counters = getattr(fs.db, "_counters", None)
    if counters is not None:
        counters.clear()


@pytest.fixture(autouse=True)
def _clean_state():
    from core.auth import refresh_token_store
    from services.rate_limit_service import RateLimitService

    def _reset():
        client.cookies.clear()
        refresh_token_store.clear()
        clear_deletion_tokens()
        # RateLimitService holds its own module-level `db` reference, which
        # may point at a different mock client than `fs.db` (test_assistant
        # swaps the global out at import time). Clearing through its own
        # helper hits the store it actually writes to; clearing only
        # `fs.db` would leave the login limiter primed and make *other*
        # modules' auth fixtures fail with a 429.
        RateLimitService.clear_all()
        _reset_collections()

    _reset()
    yield
    _reset()


@pytest.fixture
def seeded_user():
    """A user with data in every collection, including the two the old
    deletion path never touched."""
    fs.db.collection(USERS_COLLECTION).document(USER_ID).set(
        {
            "phone": "+1234567890",
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "$2b$12$notarealhash",
            "age": 28,
            "cycle_length": 29,
            "city": "Pune",
            "state": "Maharashtra",
            "sms_enabled": True,
            "sms_phone_number": "+1234567890",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )

    for index, day in enumerate((1, 29, 57)):
        fs.db.collection(CYCLE_LOGS_COLLECTION).document(f"{USER_ID}_log{index}").set(
            {
                "user_id": USER_ID,
                "start_date": datetime(2026, 3, 1, tzinfo=timezone.utc)
                + timedelta(days=day),
                "end_date": datetime(2026, 3, 5, tzinfo=timezone.utc)
                + timedelta(days=day),
                "flow_intensity": "medium",
                "symptoms": ["cramps", "headache"],
                "notes": f"note {index}",
                "sleep_hours": 7.5,
                "stress_level": 3,
            }
        )

    fs.db.collection(CONVERSATIONS_COLLECTION).document(USER_ID).set(
        {
            "user_id": USER_ID,
            "messages": [
                {"role": "user", "content": "why are my cramps worse this month?"},
                {"role": "model", "content": "Cramps can vary for many reasons..."},
            ],
            "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        }
    )

    fs.db.collection(RATE_LIMITS_COLLECTION).document(f"sms:{USER_ID}").set(
        {"timestamps": [datetime.now(timezone.utc)]}
    )
    fs.db.collection(RATE_LIMITS_COLLECTION).document(f"assistant:{USER_ID}").set(
        {"timestamps": [datetime.now(timezone.utc)]}
    )

    # A second user's data, to prove the purge is scoped.
    fs.db.collection(USERS_COLLECTION).document(OTHER_USER_ID).set({"phone": "+1999"})
    fs.db.collection(CYCLE_LOGS_COLLECTION).document("other_log").set(
        {"user_id": OTHER_USER_ID, "start_date": datetime(2026, 3, 1, tzinfo=timezone.utc)}
    )
    fs.db.collection(CONVERSATIONS_COLLECTION).document(OTHER_USER_ID).set(
        {"user_id": OTHER_USER_ID, "messages": [{"role": "user", "content": "hi"}]}
    )
    fs.db.collection(RATE_LIMITS_COLLECTION).document(f"sms:{OTHER_USER_ID}").set(
        {"timestamps": []}
    )
    return USER_ID


@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid",
    }
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "mobile"},
    )
    return {"Authorization": f"Bearer {token_response.json()['access_token']}"}


# ─── Inventory ────────────────────────────────────────────────────────────


def test_summary_counts_every_category(seeded_user):
    summary = build_data_summary(USER_ID)
    by_key = {c["key"]: c for c in summary["categories"]}

    assert by_key["identity_and_profile"]["recordCount"] == 1
    assert by_key["cycle_logs"]["recordCount"] == 3
    assert by_key["assistant_conversation"]["recordCount"] == 2
    assert by_key["rate_limits"]["recordCount"] == 2


def test_summary_reports_the_date_range_of_logs(seeded_user):
    logs = next(
        c for c in build_data_summary(USER_ID)["categories"] if c["key"] == "cycle_logs"
    )
    assert logs["earliestEntry"] == "2026-03-02"
    assert logs["latestEntry"] == "2026-04-27"


def test_summary_lists_field_names_not_values(seeded_user):
    """This is the "what do you have on me" surface, not the export."""
    summary = json.dumps(build_data_summary(USER_ID))
    assert "city" in summary          # the field name is listed
    assert "Pune" not in summary      # the value is not
    assert "note 0" not in summary


def test_summary_never_lists_the_password_field(seeded_user):
    summary = build_data_summary(USER_ID)
    identity = next(c for c in summary["categories"] if c["key"] == "identity_and_profile")
    assert "password" not in identity["storedFields"]


def test_summary_of_an_empty_account_is_all_zeros():
    summary = build_data_summary("nobody")
    assert summary["totalRecords"] == 0


def test_summary_does_not_create_a_conversation_document():
    """AssistantConversationService.get_or_create() writes an empty document
    as a side effect — during a deletion flow that would recreate the thing
    being deleted."""
    build_data_summary("brand-new-user")
    assert "brand-new-user" not in fs.db._collections.get(CONVERSATIONS_COLLECTION, {})


# ─── Export ───────────────────────────────────────────────────────────────


def test_export_is_versioned(seeded_user):
    assert build_export_bundle(USER_ID)["schema_version"] == EXPORT_SCHEMA_VERSION


def test_export_includes_every_category(seeded_user):
    bundle = build_export_bundle(USER_ID)
    assert bundle["profile"]["city"] == "Pune"
    assert len(bundle["cycle_logs"]) == 3
    assert bundle["assistant_conversation"]["message_count"] == 2
    assert bundle["sms_settings"]["enabled"] is True


def test_export_includes_free_text_notes_and_symptoms(seeded_user):
    """The fields most likely to be quietly dropped from an export are the
    ones a user most wants back."""
    log = build_export_bundle(USER_ID)["cycle_logs"][0]
    assert log["notes"].startswith("note")
    assert log["symptoms"] == ["cramps", "headache"]


def test_export_includes_assistant_conversation_messages(seeded_user):
    """Chat history that contains personal health context must be included
    in the export (issue #325)."""
    bundle = build_export_bundle(USER_ID)
    convo = bundle["assistant_conversation"]
    assert convo["message_count"] == 2
    messages = convo["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "cramps" in messages[0]["content"]
    assert messages[1]["role"] == "model"
    assert "Cramps" in messages[1]["content"]


def test_deletion_removes_chat_history_and_user_confirms(seeded_user):
    """Full deletion flow must remove chat history so the user can confirm
    it is gone (issue #325)."""
    # Verify conversation exists before deletion
    before = build_export_bundle(USER_ID)
    assert before["assistant_conversation"]["message_count"] == 2

    # Delete
    delete_account(USER_ID)

    # Verify conversation is gone
    after = build_export_bundle(USER_ID)
    assert after["assistant_conversation"]["message_count"] == 0
    assert after["assistant_conversation"]["messages"] == []


def test_export_excludes_the_password_hash(seeded_user):
    bundle = build_export_bundle(USER_ID)
    assert "password" not in bundle["profile"]
    assert "notarealhash" not in json.dumps(bundle)


def test_export_serializes_datetimes_as_iso_strings(seeded_user):
    bundle = build_export_bundle(USER_ID)
    # Would raise TypeError if anything were left as a datetime.
    json.dumps(bundle)
    assert bundle["cycle_logs"][0]["start_date"].startswith("2026-")


def test_export_is_scoped_to_the_requesting_user(seeded_user):
    bundle = build_export_bundle(USER_ID)
    assert all(log["user_id"] == USER_ID for log in bundle["cycle_logs"])


def test_export_of_an_empty_account_still_has_the_envelope():
    bundle = build_export_bundle("nobody")
    assert bundle["schema_version"] == EXPORT_SCHEMA_VERSION
    assert bundle["cycle_logs"] == []


def test_csv_has_fixed_ordered_columns(seeded_user):
    rows = list(csv.DictReader(io.StringIO(build_cycle_logs_csv(USER_ID))))
    assert list(rows[0].keys()) == list(privacy.CSV_COLUMNS)
    assert len(rows) == 3


def test_csv_flattens_symptoms_without_needing_quoting(seeded_user):
    rows = list(csv.DictReader(io.StringIO(build_cycle_logs_csv(USER_ID))))
    assert rows[0]["symptoms"] == "cramps;headache"


def test_csv_of_an_empty_account_is_a_header_only():
    output = build_cycle_logs_csv("nobody")
    assert output.strip() == ",".join(privacy.CSV_COLUMNS)


def test_export_filename_does_not_contain_the_user_id():
    """Exports land in Downloads folders, get emailed, and show up in
    screen shares."""
    name = export_filename(USER_ID, "json")
    assert USER_ID not in name
    assert name.endswith(".json")


# ─── Deletion tokens ──────────────────────────────────────────────────────


def test_token_round_trip():
    token, ttl = issue_deletion_token(USER_ID)
    assert ttl == privacy.DELETION_TOKEN_TTL_SECONDS
    assert verify_deletion_token(USER_ID, token) is True


def test_token_is_single_use():
    token, _ = issue_deletion_token(USER_ID)
    assert verify_deletion_token(USER_ID, token) is True
    assert verify_deletion_token(USER_ID, token) is False


def test_token_expires():
    from services import token_store

    token, _ = issue_deletion_token(USER_ID)

    # Backdating the stored expiry beats sleeping for the TTL. Written
    # through the store rather than by mutating a dict in place, since
    # #417 moved these out of process memory.
    doc_id = token_store.document_id(token_store.KIND_ACCOUNT_DELETION, USER_ID)
    collection = fs.db.collection(token_store.TOKENS_COLLECTION)
    stored = collection.document(doc_id).get().to_dict()
    stored["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    collection.document(doc_id).set(stored)

    assert verify_deletion_token(USER_ID, token) is False


def test_token_is_not_valid_for_another_user():
    token, _ = issue_deletion_token(USER_ID)
    assert verify_deletion_token(OTHER_USER_ID, token) is False


def test_wrong_token_is_rejected():
    issue_deletion_token(USER_ID)
    assert verify_deletion_token(USER_ID, "not-the-token") is False


def test_verifying_without_ever_issuing_is_rejected():
    assert verify_deletion_token(USER_ID, "anything") is False


# ─── Purge ────────────────────────────────────────────────────────────────


def test_purge_removes_the_assistant_conversation(seeded_user):
    """The regression this whole issue is about: the old delete path
    reported success while leaving the health conversation in Firestore."""
    counts = purge_user_data(USER_ID)
    assert counts[CONVERSATIONS_COLLECTION] == 1
    assert USER_ID not in fs.db._collections[CONVERSATIONS_COLLECTION]


def test_purge_removes_rate_limit_documents(seeded_user):
    """These are keyed `sms:{user_id}` with no user_id field inside, which
    is exactly why a query-based delete missed them."""
    counts = purge_user_data(USER_ID)
    assert counts[RATE_LIMITS_COLLECTION] == 2
    assert f"sms:{USER_ID}" not in fs.db._collections[RATE_LIMITS_COLLECTION]


def test_purge_removes_logs_and_the_user_document(seeded_user):
    counts = purge_user_data(USER_ID)
    assert counts[CYCLE_LOGS_COLLECTION] == 3
    assert counts[USERS_COLLECTION] == 1


def test_purge_leaves_other_users_untouched(seeded_user):
    purge_user_data(USER_ID)
    assert OTHER_USER_ID in fs.db._collections[USERS_COLLECTION]
    assert "other_log" in fs.db._collections[CYCLE_LOGS_COLLECTION]
    assert OTHER_USER_ID in fs.db._collections[CONVERSATIONS_COLLECTION]
    assert f"sms:{OTHER_USER_ID}" in fs.db._collections[RATE_LIMITS_COLLECTION]


def test_purge_is_idempotent(seeded_user):
    """A client retrying after a dropped response should not see a failure
    for work that already succeeded."""
    first = purge_user_data(USER_ID)
    second = purge_user_data(USER_ID)
    assert sum(first.values()) > 0
    assert sum(second.values()) == 0


def test_purge_covers_every_registered_collection(seeded_user):
    """Guards against a collection being added to USER_DATA_COLLECTIONS but
    never actually deleted."""
    counts = purge_user_data(USER_ID)
    assert set(counts) == set(privacy.USER_DATA_COLLECTIONS)


# ─── Connected chats (issue #416) ─────────────────────────────────────────


def _link_a_chat(user_id=USER_ID, channel="telegram", chat_id="500100"):
    from services import chat_link_service

    code = chat_link_service.issue_link_code(user_id, channel)["code"]
    assert chat_link_service.redeem_link_code(channel, chat_id, code) == user_id


def test_summary_counts_connected_chats(seeded_user):
    _link_a_chat()

    by_key = {c["key"]: c for c in build_data_summary(USER_ID)["categories"]}

    assert by_key["chat_links"]["recordCount"] == 1
    assert "chat_id" in by_key["chat_links"]["storedFields"]


def test_export_includes_connected_chats(seeded_user):
    _link_a_chat()

    bundle = build_export_bundle(USER_ID)

    assert bundle["chat_links"]["link_count"] == 1
    assert bundle["chat_links"]["links"][0]["chat_id"] == "500100"


def test_deleting_the_account_disconnects_its_chats(seeded_user):
    """A link outliving the account would leave the bot still recognising
    a number whose account is gone."""
    from services import chat_link_service

    _link_a_chat()

    counts = purge_user_data(USER_ID)

    assert counts[privacy.CHAT_LINKS_COLLECTION] == 1
    assert chat_link_service.resolve_user_id("telegram", "500100") is None


def test_deleting_the_account_revokes_outstanding_link_codes(seeded_user):
    from services import chat_link_service

    code = chat_link_service.issue_link_code(USER_ID, "telegram")["code"]

    purge_user_data(USER_ID)

    assert chat_link_service.redeem_link_code("telegram", "500200", code) is None


def test_another_users_chat_link_survives_the_purge(seeded_user):
    from services import chat_link_service

    _link_a_chat()
    _link_a_chat(user_id=OTHER_USER_ID, chat_id="500300")

    purge_user_data(USER_ID)

    assert chat_link_service.resolve_user_id("telegram", "500300") == OTHER_USER_ID


def test_delete_account_revokes_refresh_tokens(seeded_user):
    from core.auth import create_refresh_token, refresh_token_store, verify_refresh_token

    token = create_refresh_token(USER_ID)
    assert verify_refresh_token(token) == USER_ID

    delete_account(USER_ID)
    assert verify_refresh_token(token) is None
    assert refresh_token_store == {}


def test_delete_account_writes_an_audit_record(seeded_user):
    delete_account(USER_ID)
    record = deletion_record_for(USER_ID)
    assert record is not None
    assert record["deleted_counts"][CYCLE_LOGS_COLLECTION] == 3


def test_audit_record_contains_no_personal_data(seeded_user):
    delete_account(USER_ID)
    record = json.dumps(deletion_record_for(USER_ID))
    assert USER_ID not in record
    assert "+1234567890" not in record
    assert "test@example.com" not in record


def test_audit_collection_survives_the_purge(seeded_user):
    """Otherwise there is no evidence a deletion was ever performed."""
    delete_account(USER_ID)
    assert DELETION_AUDIT_COLLECTION not in privacy.USER_DATA_COLLECTIONS
    assert fs.db._collections[DELETION_AUDIT_COLLECTION]


def test_user_service_delete_delegates_to_the_single_cascade(seeded_user):
    """UserService.delete_user() used to implement its own partial cascade;
    the point of the change is that there is now exactly one."""
    from services.firestore_service import UserService

    counts = UserService.delete_user(USER_ID)
    assert counts[CONVERSATIONS_COLLECTION] == 1
    assert USER_ID not in fs.db._collections[CONVERSATIONS_COLLECTION]


# ─── Endpoints ────────────────────────────────────────────────────────────


def test_summary_endpoint(auth_headers, seeded_user):
    response = client.get("/api/v1/privacy/summary", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["userId"] == USER_ID


def test_export_endpoint_returns_a_download(auth_headers, seeded_user):
    response = client.get("/api/v1/privacy/export", headers=auth_headers)
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["schema_version"] == EXPORT_SCHEMA_VERSION


def test_export_endpoint_csv_format(auth_headers, seeded_user):
    response = client.get("/api/v1/privacy/export?format=csv", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "start_date" in response.text


def test_export_endpoint_rejects_an_unknown_format(auth_headers, seeded_user):
    assert client.get("/api/v1/privacy/export?format=xml", headers=auth_headers).status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/privacy/summary"),
        ("get", "/api/v1/privacy/export"),
        ("get", "/api/v1/privacy/deletion-status"),
    ],
)
def test_privacy_endpoints_require_authentication(method, path):
    assert getattr(client, method)(path).status_code == 401


def test_delete_endpoint_requires_authentication():
    assert client.post("/api/v1/privacy/delete-account", json={}).status_code == 401


def test_delete_without_a_token_returns_a_preview_and_deletes_nothing(
    auth_headers, seeded_user
):
    response = client.post(
        "/api/v1/privacy/delete-account", json={}, headers=auth_headers
    )
    assert response.status_code == 202
    body = response.json()
    assert body["confirmationToken"]
    assert body["impact"]["totalRecords"] > 0
    assert "cannot be undone" in body["warning"]
    # Nothing was destroyed by asking.
    assert USER_ID in fs.db._collections[USERS_COLLECTION]


def test_delete_with_a_token_performs_the_deletion(auth_headers, seeded_user):
    token = client.post(
        "/api/v1/privacy/delete-account", json={}, headers=auth_headers
    ).json()["confirmationToken"]

    response = client.post(
        "/api/v1/privacy/delete-account",
        json={"confirmationToken": token},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totalDeleted"] == 7  # 1 user + 3 logs + 1 convo + 2 rate limits
    assert body["deletedCounts"][CONVERSATIONS_COLLECTION] == 1
    assert USER_ID not in fs.db._collections[USERS_COLLECTION]


def test_delete_with_a_bad_token_is_rejected(auth_headers, seeded_user):
    response = client.post(
        "/api/v1/privacy/delete-account",
        json={"confirmationToken": "forged"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert USER_ID in fs.db._collections[USERS_COLLECTION]


def test_delete_clears_the_auth_cookies(auth_headers, seeded_user):
    token = client.post(
        "/api/v1/privacy/delete-account", json={}, headers=auth_headers
    ).json()["confirmationToken"]
    response = client.post(
        "/api/v1/privacy/delete-account",
        json={"confirmationToken": token},
        headers=auth_headers,
    )
    set_cookie = response.headers.get("set-cookie", "")
    assert "rhythma_access_token=" in set_cookie


def test_deletion_status_before_and_after(auth_headers, seeded_user):
    before = client.get("/api/v1/privacy/deletion-status", headers=auth_headers).json()
    assert before["accountExists"] is True
    assert before["deletedAt"] is None

    delete_account(USER_ID)

    after = deletion_record_for(USER_ID)
    assert after["deleted_counts"][USERS_COLLECTION] == 1
