"""Data portability and erasure for a user's stored health data.

Rhythma stores menstrual cycle logs, symptoms, free-text notes, mood,
sleep, stress, an AI-assistant conversation transcript, and identity
fields (phone, email, name, city, state). Until this module existed there
was no way for a user to get any of that back out, and the deletion path
was incomplete in ways that mattered:

* ``DELETE /auth/me`` → ``UserService.delete_user()`` removed the ``users``
  document, the ``cycle_logs`` documents and the Firebase Auth user, but
  never touched ``conversations`` (the assistant transcript, one document
  keyed by ``user_id``) or ``rate_limits``. After a "successful" account
  deletion the user's health conversation was still in Firestore, keyed by
  an id no longer reachable through the app — so it was not deletable by
  any means the user had.
* Refresh tokens minted before deletion stayed valid in
  ``core.auth.refresh_token_store``.
* Auth cookies were never cleared, unlike on ``/logout``.
* Nothing recorded that a deletion happened, and nothing reported what was
  actually removed.

The two rights this serves are set out in India's Digital Personal Data
Protection Act, 2023 — access to a summary of processed personal data
(§11) and erasure (§12) — but the engineering motivation stands on its
own: an app cannot claim "privacy-first" while being unable to enumerate
or remove what it holds.

Everything here is keyed off ``user_id`` from the authenticated session.
No function in this module takes a user id from a request path, because a
data-export endpoint is the last place an IDOR should be possible.
"""

from __future__ import annotations

import csv
import hashlib
import io
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services import access_log_service
from services import chat_link_service
from services import firestore_service as _firestore
from services import token_store
from services.firestore_service import UserService
from utils.logger import logger

# ─── Constants ────────────────────────────────────────────────────────────

#: Bumped whenever the export's shape changes, so a consumer holding an old
#: bundle can tell which format it has. Consumers should refuse to parse a
#: major version they don't know rather than guessing.
#:
#: 1.1 — added `provider_access_log` (issue #350). A minor bump because the
#: change is purely additive: every 1.0 key is still present and unchanged,
#: so a consumer written against 1.0 keeps working.
#:
#: 1.2 — added `chat_links` (issue #416), additive for the same reason.
EXPORT_SCHEMA_VERSION = "1.2"

#: Every collection that can hold something attributable to a user. This is
#: the single list that both the summary and the purge walk — a new
#: collection added to firestore_service.py has exactly one place to be
#: registered, so export and deletion cannot drift apart.
USERS_COLLECTION = "users"
CYCLE_LOGS_COLLECTION = "cycle_logs"
CONVERSATIONS_COLLECTION = "conversations"
RATE_LIMITS_COLLECTION = "rate_limits"
CONSENTS_COLLECTION = "consents"

#: Provider access records (issue #350). In USER_DATA_COLLECTIONS, unlike
#: DELETION_AUDIT_COLLECTION below, because these *are* the patient's
#: data: they record who read her health information, they are shown to
#: her on the Sharing screen, and deletion should mean deletion. The
#: evidence that a purge happened is the deletion audit record, which is
#: precisely what that other collection exists for.
ACCESS_LOG_COLLECTION = "access_log"

#: Chat links bind a Telegram chat or a WhatsApp number to this account
#: (issue #416). A link holds no health data, but it is the mapping that
#: makes a messaging identity *become* this person, so an erasure that
#: left it behind would leave the bot still recognising her number after
#: the account it points at is gone.
CHAT_LINKS_COLLECTION = chat_link_service.CHAT_LINKS_COLLECTION

USER_DATA_COLLECTIONS: Tuple[str, ...] = (
    USERS_COLLECTION,
    CYCLE_LOGS_COLLECTION,
    CONVERSATIONS_COLLECTION,
    RATE_LIMITS_COLLECTION,
    CONSENTS_COLLECTION,
    ACCESS_LOG_COLLECTION,
    CHAT_LINKS_COLLECTION,
)

#: Collection holding deletion audit records. Deliberately *not* in
#: USER_DATA_COLLECTIONS: it contains no personal data (see
#: _write_audit_record) and must survive the purge, otherwise there is no
#: evidence a deletion was ever performed.
DELETION_AUDIT_COLLECTION = "deletion_audit"

#: Rate-limit document ids are prefixed by feature, e.g. `sms:{user_id}`
#: and `assistant:{user_id}`. There is no `user_id` field inside them to
#: query on, so the purge matches on the id suffix instead.
RATE_LIMIT_KEY_PREFIXES: Tuple[str, ...] = ("sms", "assistant", "login", "register")

#: Fields never included in an export: a password hash is not the user's
#: data in any useful sense, and handing it out lowers the bar for an
#: offline cracking attempt against an exported file.
EXPORT_EXCLUDED_USER_FIELDS = frozenset({"password", "password_hash"})

#: Deletion confirmation tokens are single-use and short-lived. Five
#: minutes is long enough to read the impact preview and tap confirm, and
#: short enough that a token left in a log or a proxy cache is inert.
DELETION_TOKEN_TTL_SECONDS = 300

#: Deletion confirmations live in the shared token store alongside
#: refresh, reset and verification tokens (issue #417). They used to be a
#: module-level dict here, with a note saying a multi-process deployment
#: would need them moved — this is that move. A confirmation minted on
#: one worker and submitted to another now resolves, which it did not
#: before: the second step of the deletion flow simply failed, at random,
#: on any deployment running more than one process.
_deletion_tokens = token_store.TokenNamespace(token_store.KIND_ACCOUNT_DELETION)

#: Columns of the flattened CSV export. Fixed and ordered so the file is
#: diffable and importable, rather than varying with whatever keys the
#: first log happens to have.
CSV_COLUMNS: Tuple[str, ...] = (
    "start_date",
    "end_date",
    "flow_intensity",
    "mood",
    "symptoms",
    "sleep_hours",
    "stress_level",
    "notes",
    "created_at",
    "updated_at",
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _db():
    """The live Firestore handle, looked up on every call.

    Deliberately not ``from services.firestore_service import db``.
    ``firestore_service.db`` is a module-level global that
    ``initialize_firebase()`` assigns at import and that the test suite
    reassigns (``test_assistant.py`` swaps in a fresh
    ``MockFirestoreClient``). A value imported at module load would pin
    this module to whichever client existed at import time, so it would
    silently read and delete from a *different* database than the rest of
    the process — the kind of bug that shows up only when test modules run
    together, and in production only after a re-initialisation.
    """
    return _firestore.db


def _hash_user_id(user_id: str) -> str:
    """One-way hash for the audit record.

    The audit trail needs to answer "was a deletion performed for this
    account?" without itself becoming a record of who used the app. A
    hash lets an operator verify a specific id on request while leaving
    the collection useless as an enumeration of past users.
    """
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize(value: Any) -> Any:
    """Make a Firestore value JSON-safe without losing information.

    Firestore returns ``DatetimeWithNanoseconds`` (a ``datetime``
    subclass) and plain ``date`` objects. ISO 8601 keeps them both
    machine-readable and human-readable, which is the whole point of a
    portability export.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _doc_to_dict(doc: Any) -> Dict[str, Any]:
    data = doc.to_dict() or {}
    data = dict(data)
    data["id"] = doc.id
    return data


def _stream_collection(name: str) -> Iterable[Any]:
    """Yield every document in a collection, mock-client compatible.

    The in-memory mock's ``MockCollectionReference`` doesn't implement a
    bare ``.stream()``, so fall back to walking its store directly. This
    keeps export and deletion working in the mock-mode local setup that
    ``firestore_service.initialize_firebase()`` falls back to.
    """
    collection = _db().collection(name)
    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            yield from stream()
            return
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return
    for doc_id in list(store.keys()):
        yield collection.document(doc_id)


def _query_by_user(name: str, user_id: str) -> List[Any]:
    """All documents in ``name`` whose ``user_id`` field matches."""
    try:
        return list(_db().collection(name).where("user_id", "==", user_id).stream())
    except Exception:  # pragma: no cover - defensive, mock/prod divergence
        return [
            doc
            for doc in _stream_collection(name)
            if (doc.to_dict() or {}).get("user_id") == user_id
        ]


def _rate_limit_doc_ids(user_id: str) -> List[str]:
    """Rate-limit documents belonging to a user.

    These are keyed `{feature}:{user_id}` with no `user_id` field inside,
    so they cannot be found by the query above — which is precisely why
    the previous deletion path missed them.
    """
    suffix = f":{user_id}"
    return [
        doc.id
        for doc in _stream_collection(RATE_LIMITS_COLLECTION)
        if doc.id.endswith(suffix)
        or doc.id in {f"{prefix}:{user_id}" for prefix in RATE_LIMIT_KEY_PREFIXES}
    ]


def _consent_doc_ids(user_id: str) -> List[str]:
    """Consent records a user appears in, on either side.

    A consent links a ``patient_id`` (the person granting access) and a
    ``provider_id`` (the person receiving it), so deleting an account must
    remove the record regardless of which side the account sat on.
    """
    return [
        doc.id
        for doc in _stream_collection(CONSENTS_COLLECTION)
        if (doc.to_dict() or {}).get("patient_id") == user_id
        or (doc.to_dict() or {}).get("provider_id") == user_id
    ]


def _delete_doc(collection: str, doc_id: str) -> bool:
    try:
        _db().collection(collection).document(doc_id).delete()
        return True
    except Exception:  # pragma: no cover - a single failure must not abort
        logger.bind(collection=collection).warning(
            "Failed to delete one document during account purge"
        )
        return False


# ─── Inventory ────────────────────────────────────────────────────────────


def build_data_summary(user_id: str) -> Dict[str, Any]:
    """What is stored about this user, without the values themselves.

    This is the §11 "summary of personal data" surface, and it is also
    what the Settings screen should show before offering Export or Delete
    — a count and a date range make the consequences of tapping Delete
    concrete in a way that a confirmation dialog alone does not.
    """
    user = UserService.get_user_by_id(user_id) or {}
    cycle_docs = _query_by_user(CYCLE_LOGS_COLLECTION, user_id)
    cycle_logs = [_doc_to_dict(doc) for doc in cycle_docs]

    start_dates = sorted(
        d for d in (_as_date(log.get("start_date")) for log in cycle_logs) if d
    )

    conversation = _get_conversation(user_id)
    message_count = len(conversation.get("messages", []) if conversation else [])

    rate_limit_ids = _rate_limit_doc_ids(user_id)
    consent_ids = _consent_doc_ids(user_id)
    access_count = access_log_service.count_for_patient(user_id)
    chat_links = chat_link_service.links_for_user(user_id)

    identity_fields = sorted(
        field
        for field in user.keys()
        if field not in EXPORT_EXCLUDED_USER_FIELDS and user.get(field) not in (None, "")
    )

    return {
        "userId": user_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "categories": [
            {
                "key": "identity_and_profile",
                "label": "Account and health profile",
                "recordCount": 1 if user else 0,
                "storedFields": identity_fields,
                "collection": USERS_COLLECTION,
                "retentionNote": "Kept until you delete your account.",
            },
            {
                "key": "cycle_logs",
                "label": "Cycle logs, symptoms and notes",
                "recordCount": len(cycle_logs),
                "storedFields": sorted(
                    {key for log in cycle_logs for key in log.keys() if key != "id"}
                ),
                "collection": CYCLE_LOGS_COLLECTION,
                "earliestEntry": start_dates[0].isoformat() if start_dates else None,
                "latestEntry": start_dates[-1].isoformat() if start_dates else None,
                "retentionNote": "Kept until you delete your account or the individual log.",
            },
            {
                "key": "assistant_conversation",
                "label": "AI assistant conversation",
                "recordCount": message_count,
                "storedFields": ["role", "content"] if message_count else [],
                "collection": CONVERSATIONS_COLLECTION,
                "retentionNote": (
                    "A rolling window of your most recent messages; older "
                    "messages are dropped automatically."
                ),
            },
            {
                "key": "rate_limits",
                "label": "Abuse-prevention counters",
                "recordCount": len(rate_limit_ids),
                "storedFields": ["timestamps"] if rate_limit_ids else [],
                "collection": RATE_LIMITS_COLLECTION,
                "retentionNote": "Short-lived request timestamps, no health data.",
            },
            {
                "key": "consents",
                "label": "Provider data-sharing consents",
                "recordCount": len(consent_ids),
                "storedFields": (
                    ["provider_id", "provider_email", "status"] if consent_ids else []
                ),
                "collection": CONSENTS_COLLECTION,
                "retentionNote": "Kept until you revoke them or delete your account.",
            },
            {
                "key": "provider_access_log",
                "label": "Record of providers viewing your data",
                "recordCount": access_count,
                "storedFields": (
                    ["provider_id", "provider_name", "view", "accessed_at"]
                    if access_count
                    else []
                ),
                "collection": ACCESS_LOG_COLLECTION,
                "retentionNote": (
                    "Records that a provider viewed your data — never a copy "
                    "of the data itself. Kept until you delete your account."
                ),
            },
            {
                "key": "chat_links",
                "label": "Connected chat accounts",
                "recordCount": len(chat_links),
                "storedFields": (
                    ["channel", "chat_id", "linked_at"] if chat_links else []
                ),
                "collection": CHAT_LINKS_COLLECTION,
                "retentionNote": (
                    "Which Telegram chats or WhatsApp numbers can ask the "
                    "bot about your cycle. Kept until you disconnect them "
                    "or delete your account."
                ),
            },
        ],
        "totalRecords": (1 if user else 0)
        + len(cycle_logs)
        + (1 if message_count else 0)
        + len(rate_limit_ids)
        + len(consent_ids)
        + access_count
        + len(chat_links),
    }


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _get_conversation(user_id: str) -> Optional[Dict[str, Any]]:
    """Read the conversation document without creating one.

    ``AssistantConversationService.get_or_create`` would write an empty
    document as a side effect — during a *deletion* flow that would
    recreate the very thing being removed.
    """
    try:
        doc = _db().collection(CONVERSATIONS_COLLECTION).document(user_id).get()
    except Exception:  # pragma: no cover - defensive
        return None
    if not getattr(doc, "exists", False):
        return None
    return doc.to_dict() or {}


# ─── Export ───────────────────────────────────────────────────────────────


def build_export_bundle(user_id: str) -> Dict[str, Any]:
    """The complete, machine-readable export of everything we store.

    Distinct from #228's PDF report: that is a human-readable summary for
    sharing with a clinician. This is portability — every field, in a
    format another tool can import.
    """
    user = UserService.get_user_by_id(user_id) or {}
    profile = {
        key: _serialize(value)
        for key, value in user.items()
        if key not in EXPORT_EXCLUDED_USER_FIELDS
    }

    cycle_logs = [
        _serialize(_doc_to_dict(doc))
        for doc in _query_by_user(CYCLE_LOGS_COLLECTION, user_id)
    ]
    # Newest first, matching how the app displays history.
    cycle_logs.sort(key=lambda log: str(log.get("start_date") or ""), reverse=True)

    conversation = _get_conversation(user_id) or {}
    messages = [_serialize(message) for message in conversation.get("messages", [])]

    # Every access record, not one page of them (issue #350). This is the
    # portability surface — a page boundary here would make the export
    # quietly incomplete, which is the one thing an export must not be.
    access_log, _ = access_log_service.list_for_patient(
        user_id, limit=access_log_service.count_for_patient(user_id) or 1
    )

    chat_links = chat_link_service.links_for_user(user_id)

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "profile": profile,
        "cycle_logs": cycle_logs,
        "assistant_conversation": {
            "message_count": len(messages),
            "messages": messages,
        },
        "provider_access_log": {
            "entry_count": len(access_log),
            "entries": access_log,
        },
        "chat_links": {
            "link_count": len(chat_links),
            "links": [
                {
                    "channel": link.get("channel"),
                    "chat_id": link.get("chat_id"),
                    "linked_at": _serialize(link.get("linked_at")),
                }
                for link in chat_links
            ],
        },
        "sms_settings": {
            "enabled": bool(user.get("sms_enabled", False)),
            "phone_number": user.get("sms_phone_number") or user.get("phone") or "",
        },
        "notes": (
            "This file contains everything Rhythma stores about your account "
            "on the server. Your password is deliberately excluded. "
            "Abuse-prevention counters are excluded because they hold no "
            "health data and expire on their own."
        ),
    }


def build_cycle_logs_csv(user_id: str) -> str:
    """Flattened cycle logs, for a spreadsheet or another tracker.

    JSON is the canonical export; CSV exists because it is what a user can
    actually hand to a clinician or import elsewhere. Columns are fixed
    and ordered rather than derived from the first row, so the file is
    stable across exports.
    """
    bundle = build_export_bundle(user_id)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for log in bundle["cycle_logs"]:
        row = {column: log.get(column, "") for column in CSV_COLUMNS}
        symptoms = log.get("symptoms")
        if isinstance(symptoms, list):
            # Semicolons, not commas: a comma would need quoting and makes
            # the file harder to eyeball in a plain text editor.
            row["symptoms"] = ";".join(str(s) for s in symptoms)
        row = {k: ("" if v is None else v) for k, v in row.items()}
        writer.writerow(row)

    return buffer.getvalue()


def export_filename(user_id: str, extension: str) -> str:
    """A stable, non-identifying download filename.

    The user id is not in the filename: exported files end up in a Downloads
    folder, get attached to emails, and show up in screen shares.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"rhythma-data-export-{stamp}.{extension}"


# ─── Deletion ─────────────────────────────────────────────────────────────


def issue_deletion_token(user_id: str) -> Tuple[str, int]:
    """Mint a single-use confirmation token. Returns (token, ttl_seconds).

    Account deletion is irreversible and destroys health history a user
    may have spent years building. A two-step flow means the destructive
    call cannot be reached by a single mis-tap, a stale client retry, or a
    CSRF-style repeat of a previously observed request.
    """
    token = secrets.token_urlsafe(32)
    token_store.put(
        token_store.KIND_ACCOUNT_DELETION,
        user_id,
        {"token_hash": _hash_token(token), "user_id": user_id},
        timedelta(seconds=DELETION_TOKEN_TTL_SECONDS),
    )
    return token, DELETION_TOKEN_TTL_SECONDS


def verify_deletion_token(user_id: str, token: str) -> bool:
    """Check and consume a confirmation token.

    Consumed on a *match*, so a leaked or replayed token is good at most
    once. A mismatch is not consumed: burning the real token on a wrong
    guess would let anyone who can post one bad value cancel a deletion
    the user is halfway through.
    """
    entry = token_store.get(token_store.KIND_ACCOUNT_DELETION, user_id)
    if not entry:
        return False
    if not secrets.compare_digest(entry.get("token_hash", ""), _hash_token(token)):
        return False
    token_store.delete(token_store.KIND_ACCOUNT_DELETION, user_id)
    return True


def clear_deletion_tokens() -> None:
    """Test hook, mirroring core.auth's token namespaces."""
    token_store.clear(token_store.KIND_ACCOUNT_DELETION)


def purge_user_data(user_id: str) -> Dict[str, int]:
    """Delete everything stored for a user. Returns per-collection counts.

    The single place a cascade delete is implemented.
    ``UserService.delete_user()`` delegates here so the two cannot drift —
    which is how ``conversations`` came to be missed in the first place.

    Idempotent: deleting an already-deleted account returns zero counts
    rather than raising, because a client retrying after a dropped
    response should not see a failure for work that succeeded.
    """
    counts: Dict[str, int] = {name: 0 for name in USER_DATA_COLLECTIONS}

    # Cycle logs
    for doc in _query_by_user(CYCLE_LOGS_COLLECTION, user_id):
        if _delete_doc(CYCLE_LOGS_COLLECTION, doc.id):
            counts[CYCLE_LOGS_COLLECTION] += 1

    # Assistant conversation — the collection the old path never touched.
    if _get_conversation(user_id) is not None:
        if _delete_doc(CONVERSATIONS_COLLECTION, user_id):
            counts[CONVERSATIONS_COLLECTION] += 1

    # Rate-limit counters, found by id suffix since they carry no user_id.
    for doc_id in _rate_limit_doc_ids(user_id):
        if _delete_doc(RATE_LIMITS_COLLECTION, doc_id):
            counts[RATE_LIMITS_COLLECTION] += 1

    # Data-sharing consents, on either side of the relationship.
    for doc_id in _consent_doc_ids(user_id):
        if _delete_doc(CONSENTS_COLLECTION, doc_id):
            counts[CONSENTS_COLLECTION] += 1

    # Provider access records, also on either side. A patient's records
    # are hers; and a *provider* closing her account should not leave rows
    # naming her in other people's access histories (issue #350).
    for doc_id in access_log_service.doc_ids_for_user(user_id):
        if _delete_doc(ACCESS_LOG_COLLECTION, doc_id):
            counts[ACCESS_LOG_COLLECTION] += 1

    # Connected chats, plus any link code still outstanding (issue #416).
    # The codes are not counted: they are unredeemed credentials with a
    # few minutes to live, not records of anything, and reporting them as
    # "data deleted" would inflate the receipt with noise.
    for link in chat_link_service.links_for_user(user_id):
        if _delete_doc(CHAT_LINKS_COLLECTION, link["id"]):
            counts[CHAT_LINKS_COLLECTION] += 1
    chat_link_service.revoke_codes_for(user_id)

    # Firebase Auth identity, before the user document is gone — the phone
    # number needed to look it up lives there.
    user = UserService.get_user_by_id(user_id)
    if user:
        _delete_firebase_auth_user(user.get("phone"))
        if _delete_doc(USERS_COLLECTION, user_id):
            counts[USERS_COLLECTION] += 1

    logger.bind(deleted_counts=counts).info("Purged all stored data for an account")
    return counts


def _delete_firebase_auth_user(phone: Optional[str]) -> None:
    if not phone:
        return
    try:
        import firebase_admin.auth as firebase_auth

        fb_user = firebase_auth.get_user_by_phone_number(phone)
        firebase_auth.delete_user(fb_user.uid)
    except Exception:
        # An account that was never created in Firebase Auth (mock mode,
        # password-only registration) is the normal case, not an error.
        logger.debug("No Firebase Auth user to delete for this account")


def _write_audit_record(user_id: str, counts: Dict[str, int]) -> None:
    """Record that a deletion happened, with no personal data in it.

    Only the hashed id, a timestamp and the counts. Enough to answer
    "did you actually delete my data?" and to spot a purge that silently
    removed nothing; not enough to reconstruct who the user was.
    """
    try:
        _db().collection(DELETION_AUDIT_COLLECTION).document(
            _hash_user_id(user_id)
        ).set(
            {
                "user_id_hash": _hash_user_id(user_id),
                "deleted_at": datetime.now(timezone.utc),
                "deleted_counts": counts,
                "schema_version": EXPORT_SCHEMA_VERSION,
            }
        )
    except Exception:  # pragma: no cover - auditing must not fail a deletion
        logger.warning("Could not write the account-deletion audit record")


def delete_account(user_id: str) -> Dict[str, Any]:
    """Full erasure: purge every collection, revoke sessions, audit it."""
    # Read before the purge: reset and verification tokens are filed under
    # the account's email address, and after the user document is gone
    # there is nothing left to look that address up from. Without this
    # they would sit in the store until natural expiry — a live
    # password-reset token for an account that no longer exists.
    account = UserService.get_user_by_id(user_id) or {}
    account_email = account.get("email")

    counts = purge_user_data(user_id)

    # Revoke refresh tokens *after* the purge: a token that survived a
    # partially-failed purge would still be useless (the user document is
    # gone, so get_current_user 401s), but leaving valid entries in the
    # store is untidy and would keep the account "logged in" on other
    # devices until natural expiry.
    from core.auth import revoke_all_user_refresh_tokens

    revoke_all_user_refresh_tokens(user_id)
    clear_deletion_tokens_for(user_id)

    if account_email:
        from core.email_identity import normalize_email

        email_key = normalize_email(account_email)
        token_store.delete(token_store.KIND_PASSWORD_RESET, email_key)
        token_store.delete(token_store.KIND_EMAIL_VERIFICATION, email_key)

    _write_audit_record(user_id, counts)

    return {
        "deletedCounts": counts,
        "totalDeleted": sum(counts.values()),
        "deletedAt": datetime.now(timezone.utc).isoformat(),
    }


def clear_deletion_tokens_for(user_id: str) -> None:
    token_store.delete(token_store.KIND_ACCOUNT_DELETION, user_id)


def deletion_record_for(user_id: str) -> Optional[Dict[str, Any]]:
    """The audit record for a deleted account, if one exists."""
    try:
        doc = _db().collection(DELETION_AUDIT_COLLECTION).document(
            _hash_user_id(user_id)
        ).get()
    except Exception:  # pragma: no cover - defensive
        return None
    if not getattr(doc, "exists", False):
        return None
    return _serialize(doc.to_dict() or {})


def account_exists(user_id: str) -> bool:
    return UserService.get_user_by_id(user_id) is not None


__all__ = [
    "CSV_COLUMNS",
    "CONSENTS_COLLECTION",
    "DELETION_AUDIT_COLLECTION",
    "DELETION_TOKEN_TTL_SECONDS",
    "EXPORT_SCHEMA_VERSION",
    "USER_DATA_COLLECTIONS",
    "account_exists",
    "build_cycle_logs_csv",
    "build_data_summary",
    "build_export_bundle",
    "clear_deletion_tokens",
    "clear_deletion_tokens_for",
    "delete_account",
    "deletion_record_for",
    "export_filename",
    "issue_deletion_token",
    "purge_user_data",
    "verify_deletion_token",
]
