import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from google.api_core.exceptions import FailedPrecondition


logger = logging.getLogger(__name__)


# Firestore's "remove this key" sentinel. Imported from the Google client
# rather than through `firebase_admin.firestore` because the test suite
# replaces `firebase_admin` with a `MagicMock` — every attribute of which
# is a fresh mock rather than the real sentinel, so `value is DELETE_FIELD`
# would silently mean something different under test than in production.
from google.cloud.firestore_v1 import DELETE_FIELD

# `upstream_error` logs the real Firestore exception (with traceback and the
# current request id) and returns a safe error to raise. It replaces the
# `detail=f"...: {str(e)}"` pattern that used to interpolate raw Google API
# exceptions — project ids, collection paths, index-creation URLs — straight
# into a response body the client renders. See core/errors.py and issue #268.
from core.errors import upstream_error

# The one definition of "are these two addresses the same person?". Applied
# in this module, not only at the routes, so a lookup cannot be performed
# with a form of the address the write path would never have stored (#380).
from core.email_identity import normalize_email

# ─── Mock Firestore Client for Local Development ──────────────────────────
#
# Every backend test runs against this (`initialize_firebase()` falls back
# to it with no credentials, which is the CI configuration), so a place
# where it is *more permissive* than the client it stands in for is a place
# where a test can pass for the wrong reason. Issue #384 covers three:
#
#   - `MockDocumentReference.set` was defined twice. The second won, and it
#     stored the caller's dict by reference — so mutating a payload after
#     writing it silently rewrote the "stored" document, and two documents
#     written from one dict were the same object.
#   - `MockCollectionReference.order_by` and `.limit` accepted their
#     arguments and discarded them, returning an unordered, unlimited
#     result set rather than raising.
#   - `MockDocumentReference.update` no-op'd on a missing document, where
#     real Firestore raises `NotFound`.
#
# The rule below is that the mock may be *narrower* than Firestore — it
# implements the operators this codebase uses and refuses the rest loudly —
# but never looser.


class MockNotFound(Exception):
    """What ``update`` on a missing document raises.

    Real Firestore raises ``google.api_core.exceptions.NotFound``. The
    real class is not used here because constructing one pulls in
    ``google.api_core``'s error hierarchy for what is a local test double,
    and because callers should be catching ``Exception`` around a write
    anyway — the point is that the write *fails* rather than silently
    reporting success on a document that does not exist.
    """


class MockDocumentReference:
    def __init__(self, doc_id, data, collection):
        self.id = doc_id
        self.data = data
        self.collection = collection
        self.exists = data is not None

    def get(self):
        return self

    def to_dict(self):
        return self.data.copy() if self.data is not None else None

    def update(self, update_data):
        """Merge fields into an existing document.

        Raises when the document does not exist, as Firestore's ``update``
        does. It used to return silently, so ``UserService.update_user``
        on a deleted account "succeeded" under test and would have raised
        in production — precisely the asymmetry a test double exists to
        prevent.

        ``DELETE_FIELD`` removes the key rather than storing the sentinel
        (issue #549). Without this the mock would keep a
        ``Sentinel`` object in the document and hand it back on the next
        read, so a test covering a field being cleared would see the
        field still present — and holding something no client could
        parse. The rule for this mock is that it may be narrower than
        Firestore but never looser, and silently storing a write
        instruction as a value is looser.
        """
        if not self.exists or self.data is None:
            raise MockNotFound(
                f"No document to update: {self.collection.name}/{self.id}"
            )
        merged = dict(self.data)
        for key, value in _copy_document(update_data).items():
            if value is DELETE_FIELD:
                merged.pop(key, None)
            else:
                merged[key] = value
        self.data = merged
        self.collection.store[self.id] = merged

    def set(self, document_data):
        """Replace the document, storing a copy.

        The copy is the point. Firestore serialises on write, so the
        stored document is not the caller's object; the surviving
        duplicate of this method stored the dict by reference, which made
        a later mutation of that dict an invisible write.

        ``DELETE_FIELD`` is rejected rather than handled, because real
        Firestore rejects it too: there is nothing to delete in a document
        that is being created. A caller that means "leave this out" should
        leave it out.
        """
        if document_data and any(
            value is DELETE_FIELD for value in document_data.values()
        ):
            raise ValueError(
                "DELETE_FIELD cannot be used in set(); omit the field instead"
            )
        stored = _copy_document(document_data)
        self.collection.store[self.id] = stored
        self.data = stored
        self.exists = True

    def delete(self):
        if self.id in self.collection.store:
            del self.collection.store[self.id]

        self.data = None
        self.exists = False


def _copy_document(data):
    """A shallow copy of a document payload, for storing or returning.

    Shallow, not deep. Firestore's own round trip rebuilds every value,
    so a deep copy would be the more faithful choice — but the documents
    here carry ``datetime`` values and the occasional list, a deep copy on
    every read would be a real cost in a suite of ~900 tests, and the
    failure this guards against is rebinding or mutating the *top-level*
    dict. A test that mutates a nested list in place is not a pattern
    anything in this codebase uses.
    """
    return dict(data) if data is not None else None


def _mock_order_key(value):
    """Sort key for ``order_by`` in the mock query.

    ``start_date`` (and anything else date-like) can legitimately be stored
    as a bare ``date`` or as a ``datetime``; Firestore treats both as the
    same point-in-time type, so a query ordering on such a field must
    interleave them by actual value, not crash. Python's default sort
    raises ``TypeError`` comparing ``date`` and ``datetime`` directly, so
    the mock normalizes them to a common type — mirroring the sort key the
    old Python-side fallback in ``get_logs_for_user`` used before the
    composite-index query (issue #129).
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    return value


#: Comparison operators the mock query understands, matching the subset of
#: Firestore's operators this codebase actually uses.
_MOCK_OPERATORS = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    ">": lambda left, right: left is not None and left > right,
    ">=": lambda left, right: left is not None and left >= right,
    "<": lambda left, right: left is not None and left < right,
    "<=": lambda left, right: left is not None and left <= right,
}


class MockQuery:
    """One step of a query chain.

    Every builder returns a *new* ``MockQuery`` rather than mutating and
    returning ``self``, which is how Firestore's own query objects behave:

        base = collection.where("user_id", "==", uid)
        page = base.limit(20)
        head = base.limit(1)

    ``page`` and ``head`` are two queries there. With builders that
    mutated in place they were one object, and the second call silently
    rewrote the first — a shared-base-query pattern that reads perfectly
    fine and would quietly return the wrong page.
    """

    def __init__(self, documents):
        self._documents = documents
        self._order_by_field = None
        self._order_by_direction = None
        self._limit_count = None
        self._offset_count = 0

    def _derive(self, documents=None):
        """A copy of this query, optionally over a narrower document set."""
        clone = MockQuery(self._documents if documents is None else documents)
        clone._order_by_field = self._order_by_field
        clone._order_by_direction = self._order_by_direction
        clone._limit_count = self._limit_count
        clone._offset_count = self._offset_count
        return clone

    def limit(self, count):
        clone = self._derive()
        clone._limit_count = count
        return clone

    def offset(self, count):
        """Skip the first ``count`` results, as Firestore's offset does."""
        clone = self._derive()
        clone._offset_count = count
        return clone

    def order_by(self, field, direction=None):
        clone = self._derive()
        clone._order_by_field = field
        clone._order_by_direction = direction or firestore.Query.ASCENDING
        return clone

    def where(self, field, op, value):
        """Narrow an existing query further.

        Only the collection had a `where` before, so a second filter — a
        date range on top of the `user_id` match, say — had nowhere to go
        and would have silently returned an unfiltered query.
        """
        compare = _MOCK_OPERATORS.get(op)
        if compare is None:
            raise NotImplementedError(f"MockQuery does not support the {op!r} operator")

        filtered = [
            doc for doc in self._documents if compare((doc.data or {}).get(field), value)
        ]
        return self._derive(filtered)

    def count(self):
        class _CountAggregation:
            def __init__(self, count_val):
                self.val = count_val

            def get(self):
                # google-cloud-firestore format: list of list of namedtuples/objects with .value
                class ResultObj:
                    def __init__(self, v):
                        self.value = v
                return [[ResultObj(self.val)]]
        return _CountAggregation(len(self._documents))

    def stream(self):
        docs = self._documents[:]

        if self._order_by_field:
            reverse = (
                self._order_by_direction
                == firestore.Query.DESCENDING
            )

            docs.sort(
                key=lambda doc: _mock_order_key((doc.data or {}).get(self._order_by_field)),
                reverse=reverse
            )

        # Offset before limit, matching Firestore: `.offset(10).limit(5)`
        # returns results 11-15, not the first five of everything after 10.
        if self._offset_count:
            docs = docs[self._offset_count:]

        # Apply limit if requested
        if self._limit_count is not None:
            docs = docs[:self._limit_count]

        for doc in docs:
            yield doc


class MockCollectionReference:
    def __init__(self, name, db):
        self.name = name
        self.db = db

        if name not in db._collections:
            db._collections[name] = {}

        self.store = db._collections[name]

    def add(self, document_data):
        next_id = self.db._counters.get(self.name, 0) + 1
        self.db._counters[self.name] = next_id

        doc_id = f"mock-doc-id-{next_id}"
        # Stored as a copy, for the same reason `set` copies: what is
        # written must not stay tied to the caller's dict.
        stored = _copy_document(document_data)
        self.store[doc_id] = stored
        return (None, MockDocumentReference(doc_id, stored, self))

    def document(self, doc_id):
        data = self.store.get(doc_id)

        return MockDocumentReference(
            doc_id,
            data,
            self,
        )

    def _all_documents(self):
        """Every document in this collection, as references."""
        return [
            MockDocumentReference(doc_id, data, self)
            for doc_id, data in list(self.store.items())
        ]

    def stream(self):
        """Every document, unfiltered — as ``CollectionReference.stream`` does.

        This did not exist, so ``data_privacy_service`` and
        ``access_log_service`` each carry a fallback that reaches past the
        public API into the mock's private ``store`` dict:

            store = getattr(collection, "store", None)

        Production code should not have to know a test double's internals
        to work. Those fallbacks are now dead paths kept only for safety;
        they can be deleted once nothing else stands in for Firestore.
        """
        yield from self._all_documents()

    def where(self, field, op, value):
        return MockQuery(self._all_documents()).where(field, op, value)

    def count(self):
        return MockQuery(self._all_documents()).count()

    # `order_by`, `limit` and `offset` used to be no-ops on the collection
    # that returned `self`, accepting their arguments and discarding them.
    # The comment above them said they were "not called directly on
    # collection", which was an assumption the code did not enforce — and a
    # caller who did reach them got an unordered, unlimited result set and
    # no error, so a test asserting "the newest entry is first" would have
    # passed on insertion order and failed against real Firestore.
    #
    # They now build the same `MockQuery` that `where` does, so a chain
    # behaves identically whether or not it starts with a filter.

    def order_by(self, field, direction=None):
        return MockQuery(self._all_documents()).order_by(field, direction)

    def limit(self, count):
        return MockQuery(self._all_documents()).limit(count)

    def offset(self, count):
        return MockQuery(self._all_documents()).offset(count)


class MockFirestoreClient:
    def __init__(self):
        self._collections = {}
        self._counters = {}

    def collection(self, name):
        return MockCollectionReference(name, self)


# ─── Initialize Firebase (only once) ──────────────────────────────────────

db = None


def initialize_firebase():
    global db

    if firebase_admin._apps:
        db = firestore.client()
        return

    # Option 1: JSON string from environment
    cred_json = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON"
    )

    if cred_json:
        cred = credentials.Certificate(
            json.loads(cred_json)
        )
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    # Option 2: Path to JSON file
    cred_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH"
    )

    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    # Fallback to in-memory Firestore mock
    import sys

    print(
        "WARNING: Firebase credentials not found. "
        "Falling back to an in-memory mock Firestore database.",
        file=sys.stderr,
    )

    db = MockFirestoreClient()


initialize_firebase()


# ─── User Service ─────────────────────────────────────────────────────────

class UserService:

    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> str:
        """Create a new user document in Firestore.

        The email is canonicalised here rather than only at the routes.
        Three call sites create users today — ``/auth/register``,
        ``/provider/register`` and the Firebase phone flow — and before
        #380 only one of them normalised, which is how the same person
        could hold two accounts differing by a capital letter. Doing it at
        the single write path means a fourth call site added later cannot
        reintroduce that.
        """
        try:
            now = datetime.now(timezone.utc)
            if user_data.get("email") is not None:
                user_data["email"] = normalize_email(user_data["email"])
            user_data["created_at"] = now
            user_data["updated_at"] = now

            doc_ref = db.collection(
                "users"
            ).add(user_data)

            return doc_ref[1].id

        except Exception as e:
            raise upstream_error("Creating your account", e)

    @staticmethod
    def get_user_by_username(
        username: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a user by username."""
        try:
            users = (
                db.collection("users")
                .where("username", "==", username)
                .limit(1)
                .stream()
            )

            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def _first_user_where(field: str, value: Any) -> Optional[Dict[str, Any]]:
        """The first user matching one equality filter, or ``None``."""
        for user in db.collection("users").where(field, "==", value).limit(1).stream():
            data = user.to_dict()
            data["id"] = user.id
            return data
        return None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by email, regardless of how it was capitalised.

        Two queries, not one, and the second only runs on a miss.

        The canonical form is tried first: everything written since #380
        is stored lower-cased, so this is the single query that answers
        virtually every call. The fallback exists for documents created
        *before* that — ``Sana@Example.com`` is sitting in ``users``
        exactly as it was typed, and a query for the lower-cased form
        will never find it. Firestore's ``==`` is byte-exact and it has no
        case-insensitive operator, so the alternative to a second query is
        an offline backfill that must complete before the fix can ship.

        The cost is one extra read on a miss — which, for a login, is
        already the slow path — and it disappears on its own as accounts
        are re-created or a backfill is run. It is deliberately *not* a
        collection scan: only the exact string the caller supplied is
        tried, so a legacy row is found when the user types the address
        the way she originally did, and nothing here degrades with the
        size of the user table.
        """
        try:
            normalized = normalize_email(email)
            user = UserService._first_user_where("email", normalized)
            if user is not None:
                return user

            raw = (email or "").strip()
            if raw and raw != normalized:
                return UserService._first_user_where("email", raw)
            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def get_user_by_phone(
        phone: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a user by phone number."""
        try:
            users = (
                db.collection("users")
                .where("phone", "==", phone)
                .limit(1)
                .stream()
            )

            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def get_user_by_id(
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a user by Firestore document ID."""
        try:
            doc = (
                db.collection("users")
                .document(user_id)
                .get()
            )

            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data

            return None

        except Exception as e:
            raise upstream_error("Loading your profile", e)

    @staticmethod
    def update_user(user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a user document and set updated_at.

        An ``email`` in the payload goes through the same canonicalisation
        ``create_user`` applies, so a profile edit cannot put a row back
        into the mixed-case state the lookup fallback above exists to
        cope with.
        """
        try:
            if update_data.get("email") is not None:
                update_data["email"] = normalize_email(update_data["email"])
            update_data["updated_at"] = datetime.now(timezone.utc)
            doc_ref = db.collection("users").document(user_id)
            doc_ref.update(update_data)

            return True

        except Exception as e:
            raise upstream_error("Saving your profile", e)

    @staticmethod
    def delete_user(user_id: str) -> Dict[str, int]:
        """Delete everything stored for a user. Returns per-collection counts.

        Delegates to ``DataPrivacyService.purge_user_data()`` rather than
        implementing the cascade here. This method used to do it inline and
        covered only ``users``, ``cycle_logs`` and Firebase Auth — it never
        touched ``conversations`` (the assistant chat transcript, one
        document keyed by ``user_id``) or the ``rate_limits`` documents
        keyed ``sms:{user_id}``. So a "successfully deleted" account left
        the user's health conversation in Firestore indefinitely, keyed by
        an id no longer reachable through the app.

        Keeping exactly one implementation of the cascade is what stops
        that class of omission from recurring: a new collection is
        registered once, in ``USER_DATA_COLLECTIONS``, and both deletion
        and the data-summary inventory pick it up.

        The import is local to avoid an import cycle — the privacy service
        imports this module for ``UserService`` and ``db``.
        """
        try:
            from services.data_privacy_service import purge_user_data

            return purge_user_data(user_id)
        except Exception as e:
            raise upstream_error("Deleting your account", e)


# ─── Cycle Service ────────────────────────────────────────────────────────

class CycleService:
    """Persists and retrieves per-user cycle logs in Firestore."""

    @staticmethod
    def create_log(
        user_id: str,
        log_data: Dict[str, Any],
    ) -> str:
        """Create a new cycle log document for a user."""
        try:
            data = dict(log_data)

            for key, value in list(data.items()):
                if (
                    isinstance(value, date)
                    and not isinstance(value, datetime)
                ):
                    data[key] = datetime.combine(
                        value,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )

            data["user_id"] = user_id
            data["created_at"] = datetime.now(
                timezone.utc
            )

            doc_ref = (
                db.collection("cycle_logs")
                .add(data)
            )

            return doc_ref[1].id

        except Exception as e:
            raise upstream_error("Saving your cycle log", e)

    @staticmethod
    def _as_day_start(value) -> datetime:
        """Normalize a date to the UTC midnight `upsert_log` stores."""
        if isinstance(value, datetime):
            return value
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    @staticmethod
    def get_logs_page(
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        start_date=None,
        end_date=None,
    ) -> tuple:
        """One page of a user's logs, newest first, plus whether more exist.

        Returns ``(entries, has_more)``.

        ``has_more`` comes from asking Firestore for ``limit + 1`` documents
        and checking whether the extra one arrived, rather than from a
        separate count query. A count is a second round trip that grows
        with the collection, and "is there another page" is the only thing
        a client actually needs to render a Next button. The cost of the
        approach is one extra document read per page — flat, and cheaper
        than the count at any history size.

        Both date bounds are inclusive and are normalized to the UTC
        midnight `upsert_log` writes, so `start_date == end_date` returns
        that one day rather than nothing.

        Requires the same composite index on ``(user_id, start_date desc)``
        the unpaginated query needed; a date filter on the field already
        being ordered adds no further index requirement.
        """
        try:
            query = db.collection("cycle_logs").where("user_id", "==", user_id)

            if start_date is not None:
                query = query.where(
                    "start_date", ">=", CycleService._as_day_start(start_date)
                )
            if end_date is not None:
                query = query.where(
                    "start_date", "<=", CycleService._as_day_start(end_date)
                )

            # Get total count
            try:
                # Firestore's count() aggregation
                total_count = query.count().get()[0][0].value
            except AttributeError:
                # Fallback for mock if something goes wrong, though mock is updated
                total_count = len(list(query.stream()))

            query = query.order_by(
                "start_date", direction=firestore.Query.DESCENDING
            )

            # Fetch one older log (offset - 1) if possible to compute cycle_length for the newest log on this page
            fetch_offset = max(0, offset - 1) if offset > 0 else 0
            extra_fetch = 1 if offset > 0 else 0

            if offset:
                query = query.offset(fetch_offset)

            # limit + extra_fetch + 1 (for has_more)
            query = query.limit(limit + extra_fetch + 1)

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)

            # If we fetched an extra newer log, use it to compute cycle_length for results[1], then remove it
            has_more = len(results) > limit + extra_fetch

            # Slice down to just what we fetched + extra
            results = results[:limit + extra_fetch]

            # Compute cycle_length: days to next log (which is before it in the list)
            # E.g., results = [Oct 10, Oct 5, Oct 1] -> Oct 5 cycle length = (10 - 5) = 5 days.
            for i in range(len(results) - 1, -1, -1):
                if i > 0:
                    curr_date = CycleService._as_day_start(results[i]["start_date"])
                    next_date = CycleService._as_day_start(results[i - 1]["start_date"])
                    results[i]["cycle_length"] = (next_date - curr_date).days
                else:
                    # Newest log returned from query has no "next" log in this set
                    results[i]["cycle_length"] = None

            if extra_fetch and results:
                # Remove the extra newer log we fetched just for length computation
                results.pop(0)

            return results, has_more, total_count
        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            raise upstream_error("Loading your cycle history", e)

    @staticmethod
    def get_logs_for_user(user_id: str, limit: int = 10) -> list:
        """Return a user's cycle logs, most recent (by start_date) first.

        Uses Firestore's native sorting and limiting to fetch only the
        required number of documents. This requires a composite index on
        `(user_id, start_date desc)` for performance.

        If the index is missing, Firestore raises a FailedPrecondition
        exception with a direct link to create it. That error is preserved
        in the response (status 503) so the admin can use the link directly.

        Kept as the plain "most recent N" call used by the dashboard,
        predictions, insights and scoring, none of which page. Anything
        that needs a window rather than a prefix should use
        :meth:`get_logs_page`.
        """
        try:
            query = (
                db.collection("cycle_logs")
                .where("user_id", "==", user_id)
                .order_by(
                    "start_date",
                    direction=firestore.Query.DESCENDING,
                )
                .limit(limit)
            )

            docs = query.stream()
            results = []

            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)

            return results

        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )

        except Exception as e:
            # Other Firestore errors
            raise upstream_error("Loading your cycle history", e)

    @staticmethod
    def _log_doc_id(
        user_id: str,
        log_date: date,
    ) -> str:
        return f"{user_id}_{log_date.isoformat()}"

    @staticmethod
    def _prepare_write(fields: Dict[str, Any], *, for_new_document: bool) -> Dict[str, Any]:
        """Normalise a caller's field dict into something Firestore takes.

        Two conversions, both about the difference between a value and an
        instruction.

        A bare ``date`` becomes a UTC-midnight ``datetime``, matching what
        the rest of this class stores, so a query ordering on the field
        does not have to interleave two types.

        A ``None`` becomes ``DELETE_FIELD`` — "remove this key" — which is
        what makes a logged value removable at all (issue #549). It used
        to be impossible: the routes stripped every ``None`` before
        calling in here, so a mis-tapped flow intensity or a note naming a
        clinic could be *edited* but never taken back, and deleting the
        whole day was the only way out.

        ``for_new_document`` is the one asymmetry. Firestore's ``set``
        refuses the sentinel, correctly — there is nothing to delete in a
        document being created — so a clearing of a field that has never
        been written is simply dropped. That is not a special case so much
        as the same answer arrived at more cheaply: the field ends up
        absent either way.
        """
        prepared: Dict[str, Any] = {}
        for key, value in fields.items():
            if value is None:
                if not for_new_document:
                    prepared[key] = DELETE_FIELD
                continue
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(
                    value, datetime.min.time(), tzinfo=timezone.utc
                )
            prepared[key] = value
        return prepared

    @staticmethod
    def upsert_log(user_id: str, log_date: date, fields: Dict[str, Any]) -> str:
        """Create or update *that day's* cycle log with O(1) lookup.

        Uses a deterministic document ID (`{user_id}_{YYYY-MM-DD}`) so
        upsert is a direct get/update-or-set — no full-collection scan.

        Backs the single `POST /cycle/log` endpoint for both the Home
        screen's quick-log tiles (a partial `fields` dict — just the one
        thing being tapped, e.g. `{"flow_intensity": "light"}`) and the
        Cycle screen's "Save" button (a full `fields` dict with everything
        selected for that day).

        A field whose value is ``None`` is *removed* rather than skipped
        (issue #549). The route only passes a key the caller actually
        sent, so an omitted field never reaches here and cannot be
        cleared by accident — the distinction the merge semantics depend
        on is drawn there, where the request body is still visible.
        """
        try:
            doc_id = CycleService._log_doc_id(
                user_id,
                log_date,
            )

            doc_ref = (
                db.collection("cycle_logs")
                .document(doc_id)
            )

            existing = doc_ref.get()

            day_start = datetime.combine(
                log_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )

            now = datetime.now(timezone.utc)

            if existing.exists:
                update_fields = CycleService._prepare_write(
                    fields, for_new_document=False
                )
                update_fields["updated_at"] = now
                doc_ref.update(update_fields)

                return doc_id

            new_data = {
                **CycleService._prepare_write(fields, for_new_document=True),
                "user_id": user_id,
                "start_date": day_start,
                "created_at": now,
            }
            doc_ref.set(new_data)

            return doc_id

        except Exception as e:
            raise upstream_error("Saving your cycle log", e)

    @staticmethod
    def get_log(user_id: str, log_id: str) -> Dict[str, Any]:
        """One log by id, ownership checked (issue #347).

        Added so a partial update can be validated against the values
        already stored — `PUT /cycle/{log_id}` carries an `end_date` but no
        `start_date`, and "does this end date come before the start date?"
        cannot be answered from the payload alone.

        Raises the same 404/403 as :meth:`update_log` and :meth:`delete_log`
        rather than returning ``None``, so a caller cannot accidentally
        treat "not yours" as "not found" or, worse, as "no constraint to
        check".
        """
        try:
            doc = db.collection("cycle_logs").document(log_id).get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found"
                )

            data = doc.to_dict() or {}
            if data.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this log"
                )

            data["id"] = doc.id
            return data
        except HTTPException:
            raise
        except Exception as e:
            raise upstream_error("Loading your cycle log", e)

    @staticmethod
    def update_log(user_id: str, log_id: str, fields: Dict[str, Any]) -> str:
        """Update a specific cycle log by ID.

        A field whose value is ``None`` is removed, on the same terms as
        :meth:`upsert_log` — see ``_prepare_write`` (issue #549).
        """
        try:
            doc_ref = (
                db.collection("cycle_logs")
                .document(log_id)
            )

            doc = doc_ref.get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found",
                )

            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Not authorized to update this log"
                    ),
                )

            update_fields = CycleService._prepare_write(
                fields, for_new_document=False
            )
            update_fields["updated_at"] = datetime.now(timezone.utc)
            doc_ref.update(update_fields)

            return log_id

        except HTTPException:
            raise

        except Exception as e:
            raise upstream_error("Updating your cycle log", e)

    @staticmethod
    def delete_log(
        user_id: str,
        log_id: str,
    ) -> None:
        """Delete a specific cycle log by ID."""
        try:
            doc_ref = (
                db.collection("cycle_logs")
                .document(log_id)
            )

            doc = doc_ref.get()

            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found",
                )

            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Not authorized to delete this log"
                    ),
                )

            doc_ref.delete()

        except HTTPException:
            raise

        except Exception as e:
            raise upstream_error("Deleting your cycle log", e)


# ─── Maximum number of messages kept per conversation ────────────────────

MAX_CONVERSATION_MESSAGES = 50


# ─── Assistant Conversation Service ──────────────────────────────────────

class AssistantConversationService:
    """Persists assistant chat messages per user in Firestore."""

    COLLECTION = "conversations"

    @staticmethod
    def get_or_create(user_id: str) -> dict:
        now = datetime.now(timezone.utc)

        doc_ref = (
            db.collection(
                AssistantConversationService.COLLECTION
            )
            .document(user_id)
        )

        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()

        conversation = {
            "user_id": user_id,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

        doc_ref.set(conversation)

        return conversation

    @staticmethod
    def get_recent_messages(
        user_id: str,
        limit: int = 10,
    ) -> list:
        conversation = (
            AssistantConversationService.get_or_create(
                user_id
            )
        )

        return conversation.get(
            "messages",
            [],
        )[-limit:]

    @staticmethod
    def add_messages(
        user_id: str,
        new_messages: list,
    ) -> None:
        now = datetime.now(timezone.utc)

        doc_ref = (
            db.collection(
                AssistantConversationService.COLLECTION
            )
            .document(user_id)
        )

        doc = doc_ref.get()

        if not doc.exists:
            conversation = {
                "user_id": user_id,
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }

            doc_ref.set(conversation)
            doc = doc_ref.get()

        current = doc.to_dict().get(
            "messages",
            [],
        )

        current.extend(new_messages)

        if len(current) > MAX_CONVERSATION_MESSAGES:
            current = current[
                -MAX_CONVERSATION_MESSAGES:
            ]

        doc_ref.update(
            {
                "messages": current,
                "updated_at": now,
            }
        )