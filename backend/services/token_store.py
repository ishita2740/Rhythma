"""Where short-lived auth tokens actually live.

Refresh tokens, password-reset tokens, email-verification tokens and
account-deletion confirmations were held in four module-level dicts —
three in ``core/auth.py``, one in ``services/data_privacy_service.py``.
Everything else in this codebase that has to outlive a request is in
Firestore. These were in the process's heap, and that has four
consequences that all surface somewhere else as a bug:

* **A restart signs everyone out.** The access cookie lasts minutes; the
  refresh cookie is what keeps a session alive. After a deploy the dict
  is empty, ``/auth/refresh`` answers 401, and the web client's
  interceptor redirects to ``/login``. Every user, on every deploy.
* **More than one worker makes it intermittent.** Each process has its
  own copy, so whether a session survives depends on which worker the
  load balancer picked. A reset link works only if the click happens to
  land on the worker that minted it.
* **Revocation stops at the process boundary.** ``logout-all`` and the
  account-deletion cascade both walk one dict, so on a multi-worker
  deploy they clear the sessions held by whichever process served the
  request and leave the rest valid. For a deletion that is a receipt
  claiming something that did not happen.
* **Nothing sweeps.** Entries expire when they are *looked up*, and a
  token never presented again is never looked up, so the dict only grows.

This module is one small persistent store behind all four. It follows
``rate_limit_service``'s shape — a collection, a document per key — with
three things that matter:

**Only hashes are stored.** A token or an email address is hashed into
the document id and the raw value is never written. A dump of the
collection is not a set of working credentials, and it is not a list of
who uses the app.

**Every row carries an explicit expiry**, so a read can reject a stale
entry without trusting a deletion to have happened, and ``purge_expired``
can sweep on its own schedule.

**Refresh rows carry their ``user_id``**, which is what makes
"revoke everything for this account" a query rather than a scan of one
process's memory.

The mock Firestore client the local setup falls back to is a dict too, so
in mock mode this is no more durable than what it replaces. That is fine
and deliberate: mock mode is for tests and for a laptop, and the
behaviour under test is the store's contract, not its persistence.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, MutableMapping, Optional

from services import firestore_service as _firestore
from utils.logger import logger

#: One collection for every kind of token, namespaced by the ``kind``
#: prefix in the document id. One collection rather than four because
#: they share a shape and a sweep, and because a Firestore deployment
#: pays for indexes per collection.
TOKENS_COLLECTION = "auth_tokens"

#: Namespaces. Values are part of the stored document ids, so changing
#: one invalidates every token of that kind — which is a legitimate thing
#: to want, and never something to do by accident.
KIND_REFRESH = "refresh"
KIND_PASSWORD_RESET = "password_reset"
KIND_EMAIL_VERIFICATION = "email_verification"
KIND_ACCOUNT_DELETION = "account_deletion"

ALL_KINDS = (
    KIND_REFRESH,
    KIND_PASSWORD_RESET,
    KIND_EMAIL_VERIFICATION,
    KIND_ACCOUNT_DELETION,
)


def _collection():
    """The collection off the *live* Firestore handle.

    Deliberately not ``from services.firestore_service import db``. That
    global is reassigned by ``initialize_firebase()`` and by several test
    modules, and a handle captured at import would pin this module to
    whichever client existed then — reading and writing a different
    database from the rest of the process.
    """
    return _firestore.db.collection(TOKENS_COLLECTION)


def hash_value(value: str) -> str:
    """The one hash used for both tokens and email keys."""
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def document_id(kind: str, key: str) -> str:
    """``kind:hash``. The hash is of the *already-hashed-or-not* key.

    Callers pass whatever identifies the row — a raw token, a normalized
    email address — and it is hashed here, so no call site can forget to.
    """
    return f"{kind}:{hash_value(key)}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> Optional[datetime]:
    """Firestore hands back a ``datetime``; a mock may hand back a string."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _stream() -> Iterator[Any]:
    """Every token document, tolerating the in-memory mock.

    ``MockCollectionReference`` has no bare ``stream()``; walking its
    ``store`` is the fallback ``data_privacy_service`` already uses.
    """
    collection = _collection()
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


# ─── Operations ───────────────────────────────────────────────────────────


def put(
    kind: str,
    key: str,
    payload: Dict[str, Any],
    ttl: timedelta,
) -> None:
    """Store one token row, replacing any row with the same key.

    Replacing rather than appending is what makes "requesting a new reset
    link invalidates the old one" true by construction: reset and
    verification rows are keyed by email address, so there is only ever
    one live token per address.
    """
    document = dict(payload)
    document["kind"] = kind
    document["expires_at"] = (_now() + ttl).isoformat()
    document["created_at"] = _now().isoformat()
    _collection().document(document_id(kind, key)).set(document)


def get(kind: str, key: str) -> Optional[Dict[str, Any]]:
    """One row, or ``None`` if it is absent or expired.

    An expired row is deleted on the way out. Reading is the only moment
    we are certain a specific row is stale *and* cheap to remove, so the
    sweep in ``purge_expired`` is a backstop rather than the mechanism.
    """
    try:
        doc = _collection().document(document_id(kind, key)).get()
    except Exception:  # pragma: no cover - defensive
        logger.bind(kind=kind).warning("Could not read an auth token record")
        return None

    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    expires_at = _as_datetime(data.get("expires_at"))
    if expires_at is None or expires_at <= _now():
        delete(kind, key)
        return None
    return data


def delete(kind: str, key: str) -> bool:
    """Drop one row. Returns whether there was one to drop."""
    doc_id = document_id(kind, key)
    try:
        existing = _collection().document(doc_id).get()
        if not getattr(existing, "exists", False):
            return False
        _collection().document(doc_id).delete()
        return True
    except Exception:  # pragma: no cover - defensive
        logger.bind(kind=kind).warning("Could not delete an auth token record")
        return False


def delete_for_user(kind: str, user_id: str) -> int:
    """Drop every row of ``kind`` belonging to ``user_id``.

    This is the operation that ``logout-all`` and the account-deletion
    cascade need, and the one that a per-process dict could not provide
    across workers.
    """
    removed = 0
    for doc in list(_stream()):
        data = doc.to_dict() or {}
        if data.get("kind") != kind or data.get("user_id") != user_id:
            continue
        try:
            _collection().document(doc.id).delete()
            removed += 1
        except Exception:  # pragma: no cover - defensive
            logger.bind(kind=kind).warning("Could not revoke an auth token record")
    return removed


def keys_of_kind(kind: str) -> List[str]:
    """Document ids of one kind. For the compatibility mapping and tests."""
    return [
        doc.id for doc in _stream() if (doc.to_dict() or {}).get("kind") == kind
    ]


def entries_of_kind(kind: str) -> Dict[str, Dict[str, Any]]:
    """Every live row of one kind, keyed by document id."""
    found: Dict[str, Dict[str, Any]] = {}
    for doc in _stream():
        data = doc.to_dict() or {}
        if data.get("kind") == kind:
            found[doc.id] = data
    return found


def purge_expired(kind: Optional[str] = None) -> int:
    """Delete rows whose window has closed.

    Reads already refuse an expired row, so this exists for the rows
    nobody reads again — which is most of them, and is the reason the
    dicts this replaces only ever grew.
    """
    now = _now()
    removed = 0
    for doc in list(_stream()):
        data = doc.to_dict() or {}
        if kind is not None and data.get("kind") != kind:
            continue
        expires_at = _as_datetime(data.get("expires_at"))
        if expires_at is not None and expires_at > now:
            continue
        try:
            _collection().document(doc.id).delete()
            removed += 1
        except Exception:  # pragma: no cover - defensive
            pass
    if removed:
        logger.bind(removed=removed).info("Swept expired auth tokens")
    return removed


def clear(kind: Optional[str] = None) -> None:
    """Empty the store, or one namespace of it. Test fixtures only."""
    if kind is None:
        try:
            if hasattr(_firestore.db, "_collections"):
                _firestore.db._collections.pop(TOKENS_COLLECTION, None)
                return
        except Exception:  # pragma: no cover - defensive
            pass

    for doc in list(_stream()):
        if kind is not None and (doc.to_dict() or {}).get("kind") != kind:
            continue
        try:
            _collection().document(doc.id).delete()
        except Exception:  # pragma: no cover - defensive
            pass


# ─── Compatibility mapping ────────────────────────────────────────────────


class TokenNamespace(MutableMapping):
    """A dict-shaped view over one namespace of the store.

    ``core.auth`` exported ``refresh_token_store``, ``reset_token_store``
    and ``verification_token_store`` as plain dicts, and the test suite
    reaches into all three — clearing them between cases, asserting a
    revocation emptied one, listing the keys of another to check an email
    address was canonicalised before it was filed.

    Those assertions are about behaviour that still holds, so rather than
    rewrite them to a new API and lose the coverage in the process, the
    three names now point at one of these. It is a genuine view, not a
    copy: writes go to the store and reads come back from it.

    New code should call the module functions. This exists so moving the
    storage was one change rather than two.
    """

    def __init__(self, kind: str):
        self.kind = kind

    def __getitem__(self, key: str) -> Dict[str, Any]:
        entries = entries_of_kind(self.kind)
        if key in entries:
            return entries[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        document = dict(value)
        document["kind"] = self.kind
        expires_at = document.get("expires_at")
        if isinstance(expires_at, datetime):
            document["expires_at"] = expires_at.isoformat()
        _collection().document(key).set(document)

    def __delitem__(self, key: str) -> None:
        try:
            _collection().document(key).delete()
        except Exception:  # pragma: no cover - defensive
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(entries_of_kind(self.kind))

    def __len__(self) -> int:
        return len(entries_of_kind(self.kind))

    def clear(self) -> None:  # type: ignore[override]
        clear(self.kind)

    def __eq__(self, other: Any) -> bool:
        """Compare against a plain dict, so ``store == {}`` still reads.

        ``Mapping`` does not define ``__eq__``, so without this the
        emptiness assertions in the test suite would compare identities
        and silently always fail.
        """
        if isinstance(other, dict):
            return entries_of_kind(self.kind) == other
        return NotImplemented

    def __hash__(self):  # pragma: no cover - mutable, never a key
        raise TypeError("TokenNamespace is unhashable")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"TokenNamespace({self.kind!r}, {len(self)} entries)"


__all__ = [
    "ALL_KINDS",
    "KIND_ACCOUNT_DELETION",
    "KIND_EMAIL_VERIFICATION",
    "KIND_PASSWORD_RESET",
    "KIND_REFRESH",
    "TOKENS_COLLECTION",
    "TokenNamespace",
    "clear",
    "delete",
    "delete_for_user",
    "document_id",
    "entries_of_kind",
    "get",
    "hash_value",
    "keys_of_kind",
    "purge_expired",
    "put",
]
