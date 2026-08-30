"""The store behind every rate limit: one document per bucket.

A bucket is a list of attempt timestamps under a key
(``{policy}:{sha256}``), filtered to the policy's window on every read.
That part has always worked. What it did not do was ever let go of a
document (#499):

    timestamps = [t for t in timestamps if now - t < window]
    ...
    doc_ref.set({"timestamps": timestamps})

The filter drops expired *timestamps*. It never dropped the *document*. A
bucket whose window had fully rolled over was written back holding a
single fresh entry, and once that caller stopped coming back the document
sat there forever. The only deletion path was ``reset()``, reached after a
successful login — and deliberately only for the account-keyed bucket,
because *"a machine that just succeeded on one account has told us nothing
about the dozens of other accounts it may be working through"*. Which is
right, and which leaves the per-IP buckets with no deletion path at all.

So the collection grew with distinct callers rather than with traffic: one
document per address that ever touched ``/auth/login``, ``/auth/register``,
``/auth/refresh``, ``/auth/verify-email``, ``/auth/reset-password``,
``/provider/register`` or either chat webhook — mobile clients change
address constantly — plus one per email address ever attempted, including
ones that do not exist.

``token_store`` had the identical shape, and its docstring says what came
of it:

    **Nothing sweeps.** Entries expire when they are *looked up*, and a
    token never presented again is never looked up, so the dict only grows.

Two things close it here, both borrowed from that module:

**Every document carries an explicit expiry.** ``expires_at`` is the point
after which the bucket is provably empty — the newest attempt plus the
window it was recorded under. Without it, nothing outside this module can
tell a live bucket from a dead one: ``{"timestamps": [...]}`` does not say
which policy wrote it, so it does not say which window applies. A Firestore
TTL policy needs a timestamp field to point at, and there was none.

**A sweep runs at startup**, next to ``token_store.purge_expired()`` in
``main.py``, so a deployment with no scheduled job still stays bounded.

There is a privacy argument as well as a cost one. ``core/rate_limits.py``
hashes identifiers precisely so this collection is not a list of email
addresses:

    A key like ``login_account:sana@example.com`` would put a plaintext
    email address in a document id, in a collection nothing else treats as
    personal data, retained for as long as the document lives.

The hash answers the plaintext half. "Retained for as long as the document
lives" was the other half, and a SHA-256 of an email address is still a
stable per-person identifier — it joins against any other list of emails
by hashing them. A bucket that expires is a bucket that stops being one.

Timestamps are written as ISO-8601 strings rather than ``datetime``
objects. Reads have always accepted both and still do, so documents
already in a deployment are unaffected; writing one form means a document
has the same shape whether Firestore or the in-memory mock produced it,
and ``expires_at`` is directly comparable to the entries it summarises.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, List, Optional

from services.firestore_service import db
from utils.logger import logger

#: The longest window any policy in ``core/rate_limits.py`` configures, and
#: therefore the most generous assumption the sweep can make about a
#: document written before ``expires_at`` existed. Used only for those
#: legacy documents: a current one states its own expiry and is believed.
LEGACY_MAX_WINDOW_SECONDS = 3600


class RateLimitService:
    COLLECTION = "rate_limits"

    # ─── Storage ──────────────────────────────────────────────────────────

    @staticmethod
    def _document(key: str):
        return db.collection(RateLimitService.COLLECTION).document(key)

    @staticmethod
    def _collection():
        return db.collection(RateLimitService.COLLECTION)

    @staticmethod
    def _stream() -> Iterator[Any]:
        """Every bucket document, tolerating the in-memory mock.

        ``MockCollectionReference`` has no bare ``stream()``; walking its
        ``store`` is the fallback ``token_store`` and
        ``data_privacy_service`` already use for the same reason.
        """
        collection = RateLimitService._collection()
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

    # ─── Time ─────────────────────────────────────────────────────────────

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        """Normalise whatever a document holds into an aware ``datetime``.

        Three shapes reach this. Firestore returns its own
        ``DatetimeWithNanoseconds``; the mock client returns whatever was
        put in, which for documents written before this module started
        writing strings is a plain ``datetime``; and new writes are
        ISO-8601 text. A naive value is read as UTC — it was written by
        this process, which works in UTC throughout, and reading it as
        local time would shift a bucket by the host's offset.
        """
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    @staticmethod
    def _timestamps_from(data: Any) -> List[datetime]:
        """The attempts a document records, oldest first.

        Anything unreadable is dropped rather than carried along. A bucket
        is a count, and an entry that cannot be placed in time can neither
        be counted against the window nor used to compute a wait.

        Sorting is not decoration: ``is_rate_limited`` takes ``[0]`` as the
        oldest attempt to derive ``Retry-After``, and while this module
        appends in order, the sort is what makes that true of a document
        however it was written.
        """
        raw = (data or {}).get("timestamps", [])
        if not isinstance(raw, list):
            return []

        parsed = [RateLimitService._as_datetime(entry) for entry in raw]
        return sorted(entry for entry in parsed if entry is not None)

    # ─── Enforcement ──────────────────────────────────────────────────────

    @staticmethod
    def is_rate_limited(
        key: str,
        limit: int = 5,
        window_seconds: int = 300,
    ) -> Optional[int]:
        """Record one attempt against ``key``; return the wait if over the limit.

        ``None`` means the attempt is allowed. Otherwise the number of
        seconds until the oldest attempt in the window expires — which is
        what ``enforce()`` puts in ``Retry-After``, so a client that
        honours the header waits exactly as long as it has to.
        """
        now = datetime.now(timezone.utc)
        doc_ref = RateLimitService._document(key)
        doc = doc_ref.get()

        data = (doc.to_dict() or {}) if getattr(doc, "exists", False) else {}
        timestamps = [
            entry
            for entry in RateLimitService._timestamps_from(data)
            if now - entry < timedelta(seconds=window_seconds)
        ]

        if len(timestamps) >= limit:
            oldest = timestamps[0]
            remaining = int(
                (oldest + timedelta(seconds=window_seconds) - now).total_seconds()
            )
            RateLimitService._write(doc_ref, timestamps, window_seconds)
            return max(remaining, 1)

        timestamps.append(now)
        RateLimitService._write(doc_ref, timestamps, window_seconds)
        return None

    @staticmethod
    def _write(doc_ref, timestamps: List[datetime], window_seconds: int) -> None:
        """Persist a bucket, stamped with the point it becomes empty.

        ``expires_at`` is derived from the *newest* attempt rather than the
        oldest: the bucket is only provably empty once the last thing in it
        has aged out. Doing it here rather than at the call site means
        every write carries one — including the over-limit write, which is
        the one a caller under sustained attack keeps refreshing.

        ``window_seconds`` is stored alongside it because the expiry alone
        does not say how it was derived, and an operator looking at this
        collection should not have to guess which policy wrote a row.
        """
        newest = max(timestamps) if timestamps else datetime.now(timezone.utc)
        expires_at = newest + timedelta(seconds=max(int(window_seconds), 1))

        doc_ref.set(
            {
                "timestamps": [entry.isoformat() for entry in timestamps],
                "expires_at": expires_at.isoformat(),
                "window_seconds": int(window_seconds),
            }
        )

    @staticmethod
    def reset(key: str) -> None:
        """Remove the rate-limit entry for a single key.

        Called after a successful login so a user who mistypes her password
        is not left one attempt away from a lockout.
        """
        try:
            doc_ref = RateLimitService._document(key)
            doc_ref.delete()
        except Exception:
            pass

    # ─── Housekeeping ─────────────────────────────────────────────────────

    @staticmethod
    def purge_expired() -> int:
        """Delete buckets whose window has closed. Returns how many went.

        ``is_rate_limited`` already filters expired attempts on read, so
        this changes no decision — it exists for the buckets nobody reads
        again, which is most of them and is the whole of #499.

        Documents written before ``expires_at`` existed carry no expiry.
        Rather than deleting those on sight, their newest recorded attempt
        is compared against :data:`LEGACY_MAX_WINDOW_SECONDS` — the longest
        window any policy configures — so a legacy bucket is only swept
        once it is dead under *every* policy that could have written it.
        Deleting a live one would clear a lockout somebody is currently
        subject to, which is the one thing a housekeeping job must not do.
        A document with no readable timestamps at all has nothing to
        protect and goes.
        """
        now = datetime.now(timezone.utc)
        removed = 0

        for doc in list(RateLimitService._stream()):
            data = doc.to_dict() or {}

            expires_at = RateLimitService._as_datetime(data.get("expires_at"))
            if expires_at is None:
                timestamps = RateLimitService._timestamps_from(data)
                if timestamps:
                    expires_at = timestamps[-1] + timedelta(
                        seconds=LEGACY_MAX_WINDOW_SECONDS
                    )

            if expires_at is not None and expires_at > now:
                continue

            try:
                RateLimitService._collection().document(doc.id).delete()
                removed += 1
            except Exception:  # pragma: no cover - defensive
                pass

        if removed:
            logger.bind(removed=removed).info("Swept expired rate-limit buckets")
        return removed

    @staticmethod
    def clear_all():
        """
        Clear all rate limit entries.
        Used only for tests.
        """
        try:
            if hasattr(db, "_collections"):
                db._collections.pop(RateLimitService.COLLECTION, None)
        except Exception:
            pass
