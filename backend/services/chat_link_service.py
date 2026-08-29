"""Binding a messaging-platform chat to a Rhythma account.

The chatbot added in #404 treated the chat id in the webhook payload as
though it were a Rhythma user id:

    user_id = str(chat.get("id") or "telegram_user")
    ...
    score_data = get_user_scores(user_id)

Two different things go wrong with that. A real Telegram chat id is a
number Telegram assigned and has nothing to do with any account here, so
the intended path could never find the right user's data. And the value
arrives in the request body, so a caller who writes a Rhythma user id
there instead is asking for that user's records — which the code would
then fetch and read back, to a caller holding no credentials.

An identity a caller can type is not an identity. This module is the
missing indirection: a chat is *linked* to an account by a code the user
generates while signed in to the app and then sends to the bot, and the
webhook resolves ``(channel, chat_id)`` to a user id through the stored
link or not at all.

**Why a code rather than a phone number.** WhatsApp deliveries carry the
sender's number, and the account may have the same number saved, so
matching on it is tempting. It is also the same mistake in a new
costume: the number is in the request body, and anyone who knows a user's
phone number could then read her cycle history. The code is a secret the
user has to have been signed in to obtain.

**Codes are short-lived and single-use.** They are eight characters from
an unambiguous alphabet because a user types them into a chat window,
often on a phone, sometimes reading them off another screen. That is
short enough to guess if it were long-lived, so a code expires in ten
minutes, is consumed on first use, and redemption is rate-limited per
chat by the caller in ``api/bot.py``.

Only the hash of a code is stored, for the same reason password hashes
are: a dump of the collection should not be a list of working codes.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services import firestore_service as _firestore
from utils.logger import logger

#: One document per linked chat, id ``{channel}:{chat_id}``. Keyed that
#: way rather than by user id because the lookup that happens on every
#: delivery is chat → user, and a document id read is the one Firestore
#: operation that needs no index and no query.
CHAT_LINKS_COLLECTION = "chat_links"

#: Pending, unredeemed codes. Separate from the links themselves so that
#: expiring an unused code never touches a live link.
CHAT_LINK_CODES_COLLECTION = "chat_link_codes"

#: No ``0``/``O``, no ``1``/``I``/``L``. A code that is read aloud or
#: copied off a screen loses to those pairs more often than the extra
#: entropy is worth.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8

DEFAULT_CODE_TTL_SECONDS = 600

SUPPORTED_CHANNELS = ("telegram", "whatsapp")


def code_ttl_seconds() -> int:
    """How long a freshly issued code stays redeemable."""
    raw = os.getenv("CHAT_LINK_CODE_TTL_SECONDS")
    if raw is None:
        return DEFAULT_CODE_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CODE_TTL_SECONDS
    # A non-positive TTL would make every code expire before it could be
    # read, which is a typo in a deploy config rather than a policy.
    return value if value > 0 else DEFAULT_CODE_TTL_SECONDS


def normalize_code(raw: str) -> str:
    """Fold a typed code into the form the hash was taken over.

    Users paste codes with spaces around them, type them in lower case,
    and split them with a hyphen because that is what codes usually look
    like. None of that changes which code was meant.
    """
    return "".join(ch for ch in (raw or "").upper() if ch in CODE_ALPHABET)


def _hash_code(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("utf-8")).hexdigest()


def link_document_id(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _collection(name: str):
    """A collection off the *live* Firestore handle.

    Deliberately not ``from services.firestore_service import db``.
    That global is reassigned — ``initialize_firebase()`` sets it, and
    several test modules swap in a fresh ``MockFirestoreClient`` — so a
    handle captured at import time pins this module to whichever client
    existed then, and it would read and write a different database from
    the rest of the process. ``data_privacy_service`` learned this the
    same way and its ``_db()`` carries the same note.
    """
    return _firestore.db.collection(name)


def _stream(name: str):
    """Every document in a collection, tolerating the in-memory mock.

    ``MockCollectionReference`` has no bare ``stream()``; walking its
    ``store`` is the fallback ``data_privacy_service`` already uses for
    the same reason.
    """
    collection = _collection(name)
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


# ─── Issuing ──────────────────────────────────────────────────────────────


def issue_link_code(user_id: str, channel: str) -> Dict[str, Any]:
    """Mint a code for ``user_id`` to send to ``channel``'s bot.

    Any code this user had outstanding for the same channel is dropped
    first. Leaving several live at once would mean a code read off a
    screenshot from an hour ago still works, and a user who reissues
    because the first code did not arrive expects the first one to stop
    being a key.
    """
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"Unsupported channel {channel!r}.")

    revoke_codes_for(user_id, channel=channel)

    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    ttl = code_ttl_seconds()
    expires_at = _now() + timedelta(seconds=ttl)

    _collection(CHAT_LINK_CODES_COLLECTION).document(_hash_code(code)).set(
        {
            "user_id": user_id,
            "channel": channel,
            "expires_at": expires_at.isoformat(),
            "created_at": _now().isoformat(),
        }
    )

    # The code itself is returned and never logged. It is a bearer
    # credential for the few minutes it lives.
    logger.bind(channel=channel).info("Issued a chat link code")
    return {"code": code, "channel": channel, "expiresInSeconds": ttl}


def revoke_codes_for(user_id: str, channel: Optional[str] = None) -> int:
    """Drop this user's outstanding codes, optionally for one channel."""
    removed = 0
    for doc in list(_stream(CHAT_LINK_CODES_COLLECTION)):
        data = doc.to_dict() or {}
        if data.get("user_id") != user_id:
            continue
        if channel is not None and data.get("channel") != channel:
            continue
        _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
        removed += 1
    return removed


def purge_expired_codes() -> int:
    """Delete codes whose window has closed.

    Redemption already refuses an expired code, so this is housekeeping
    rather than a control. It runs on issue and on redeem so the
    collection cannot accumulate indefinitely on a deployment with no
    scheduled job.
    """
    now = _now()
    removed = 0
    for doc in list(_stream(CHAT_LINK_CODES_COLLECTION)):
        expires_at = _as_datetime((doc.to_dict() or {}).get("expires_at"))
        if expires_at is None or expires_at <= now:
            _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
            removed += 1
    return removed


# ─── Redeeming ────────────────────────────────────────────────────────────


def redeem_link_code(channel: str, chat_id: str, code: str) -> Optional[str]:
    """Bind ``(channel, chat_id)`` to the account that issued ``code``.

    Returns the user id on success and ``None`` when the code is unknown,
    expired, or was issued for a different channel. The caller reports all
    three the same way — an attacker walking the code space must not be
    able to tell "wrong code" from "right code, wrong channel".
    """
    normalized = normalize_code(code)
    if len(normalized) != CODE_LENGTH:
        return None

    doc = _collection(CHAT_LINK_CODES_COLLECTION).document(_hash_code(normalized)).get()
    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    if data.get("channel") != channel:
        return None

    expires_at = _as_datetime(data.get("expires_at"))
    if expires_at is None or expires_at <= _now():
        _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
        return None

    user_id = data.get("user_id")
    if not user_id:
        return None

    # Consumed before the link is written. If writing the link then fails,
    # the user retries with a fresh code; the alternative ordering leaves
    # a live code behind after a successful link.
    _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()

    _collection(CHAT_LINKS_COLLECTION).document(link_document_id(channel, chat_id)).set(
        {
            "user_id": user_id,
            "channel": channel,
            "chat_id": str(chat_id),
            "linked_at": _now().isoformat(),
        }
    )
    purge_expired_codes()

    logger.bind(channel=channel).info("Linked a chat to an account")
    return user_id


def resolve_user_id(channel: str, chat_id: str) -> Optional[str]:
    """The account this chat is linked to, or ``None``.

    This is the only way a webhook is allowed to learn who it is talking
    to. Everything downstream of it treats ``None`` as "answer with
    public help text and nothing personal".
    """
    if not chat_id:
        return None
    try:
        doc = (
            _collection(CHAT_LINKS_COLLECTION)
            .document(link_document_id(channel, str(chat_id)))
            .get()
        )
    except Exception:  # pragma: no cover - defensive
        logger.bind(channel=channel).warning("Could not read chat link")
        return None

    if not getattr(doc, "exists", False):
        return None
    return (doc.to_dict() or {}).get("user_id") or None


def unlink(channel: str, chat_id: str) -> bool:
    """Forget a chat's link. Returns whether there was one."""
    doc_id = link_document_id(channel, str(chat_id))
    doc = _collection(CHAT_LINKS_COLLECTION).document(doc_id).get()
    if not getattr(doc, "exists", False):
        return False
    _collection(CHAT_LINKS_COLLECTION).document(doc_id).delete()
    logger.bind(channel=channel).info("Unlinked a chat from an account")
    return True


def links_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Every chat linked to an account, newest field order preserved.

    Used by the privacy inventory and by the deletion cascade — a link
    ties a messaging identity to a health account and is exactly the kind
    of record an erasure request means.
    """
    found: List[Dict[str, Any]] = []
    for doc in _stream(CHAT_LINKS_COLLECTION):
        data = doc.to_dict() or {}
        if data.get("user_id") != user_id:
            continue
        entry = dict(data)
        entry["id"] = doc.id
        found.append(entry)
    return found


def clear_all() -> None:
    """Empty both collections. Test fixtures only."""
    for name in (CHAT_LINKS_COLLECTION, CHAT_LINK_CODES_COLLECTION):
        try:
            if hasattr(_firestore.db, "_collections"):
                _firestore.db._collections.pop(name, None)
        except Exception:  # pragma: no cover - defensive
            pass


__all__ = [
    "CHAT_LINKS_COLLECTION",
    "CHAT_LINK_CODES_COLLECTION",
    "CODE_ALPHABET",
    "CODE_LENGTH",
    "SUPPORTED_CHANNELS",
    "clear_all",
    "code_ttl_seconds",
    "issue_link_code",
    "link_document_id",
    "links_for_user",
    "normalize_code",
    "purge_expired_codes",
    "redeem_link_code",
    "resolve_user_id",
    "revoke_codes_for",
    "unlink",
]
