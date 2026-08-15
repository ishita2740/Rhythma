import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from google.api_core.exceptions import FailedPrecondition  # for missing index detection

# ─── Mock Firestore Client for Local Development ──────────────────────────
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
        if self.data:
            self.data.update(update_data)
            self.collection.store[self.id] = self.data
            
    def set(self, document_data):
        self.data = document_data.copy()
        self.collection.store[self.id] = self.data
        self.exists = True

    def set(self, set_data):
        self.collection.store[self.id] = set_data
        self.data = set_data
        self.exists = True

    def delete(self):
        if self.id in self.collection.store:
            del self.collection.store[self.id]
        self.data = None
        self.exists = False

class MockQuery:
    def __init__(self, documents):
        # documents is a list of MockDocumentReference
        self._documents = documents
        self._order_by_field = None
        self._order_by_direction = None
        self._limit_count = None

    def limit(self, count):
        self._limit_count = count
        return self

    def order_by(self, field, direction=None):
        self._order_by_field = field
        self._order_by_direction = direction or firestore.Query.ASCENDING
        return self

    def stream(self):
        # Start with the filtered documents
        docs = self._documents[:]

        # Apply sorting if requested
        if self._order_by_field:
            reverse = (self._order_by_direction == firestore.Query.DESCENDING)
            docs.sort(
                key=lambda doc: doc.data.get(self._order_by_field),
                reverse=reverse
            )

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
        # Per-collection auto-ID counter.
        #
        # Previously this counter was a class-level attribute
        # (`MockCollectionReference._next_id`), which meant every mock
        # collection — `users`, `cycle_logs`, `conversations`, etc. —
        # drew IDs from one shared incrementing sequence, so creating a
        # user then a cycle log produced `mock-doc-id-1` and
        # `mock-doc-id-2` instead of `mock-doc-id-1` in each collection.
        #
        # The counter cannot live on the instance either, because
        # `MockFirestoreClient.collection(name)` builds a *fresh*
        # `MockCollectionReference` on every call — an instance-level
        # counter would reset to 1 each time and collide immediately.
        #
        # Persisting it on the shared `db._counters` dict, keyed by
        # collection name, gives each collection its own independent
        # sequence that survives across `db.collection(name)` calls —
        # matching how real Firestore auto-IDs are namespaced
        # per-collection.
        next_id = self.db._counters.get(self.name, 0) + 1
        self.db._counters[self.name] = next_id
        doc_id = f"mock-doc-id-{next_id}"
        self.store[doc_id] = document_data
        return (None, MockDocumentReference(doc_id, document_data, self))

    def document(self, doc_id):
        data = self.store.get(doc_id)
        return MockDocumentReference(doc_id, data, self)

    def where(self, field, op, value):
        filtered = []
        for doc_id, data in self.store.items():
            if data.get(field) == value:
                filtered.append(MockDocumentReference(doc_id, data, self))
        return MockQuery(filtered)

    # These are not called directly on collection; they are chained after where
    def order_by(self, field, direction=None):
        return self

    def limit(self, count):
        return self

class MockFirestoreClient:
    def __init__(self):
        self._collections = {}
        # Per-collection auto-ID counters for MockCollectionReference.add().
        # Keyed by collection name so each collection has its own
        # independent sequence (see MockCollectionReference.add).
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
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    # Option 2: Path to JSON file
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return

    # Fallback to in-memory Firestore mock
    import sys
    print("WARNING: Firebase credentials not found. Falling back to an in-memory mock Firestore database.", file=sys.stderr)
    db = MockFirestoreClient()

initialize_firebase()


class UserService:
    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> str:
        """Create a new user document in Firestore."""
        try:
            now = datetime.now(timezone.utc)
            user_data["created_at"] = now
            user_data["updated_at"] = now
            doc_ref = db.collection("users").add(user_data)
            return doc_ref[1].id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {str(e)}"
            )

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by username."""
        try:
            users = db.collection("users").where("username", "==", username).limit(1).stream()
            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data
            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}"
            )

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by email."""
        try:
            users = db.collection("users").where("email", "==", email).limit(1).stream()
            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data
            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}"
            )

    @staticmethod
    def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by phone number."""
        try:
            users = db.collection("users").where("phone", "==", phone).limit(1).stream()
            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data
            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}"
            )

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by Firestore document ID."""
        try:
            doc = db.collection("users").document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data
            return None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}"
            )

    @staticmethod
    def update_user(user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a user document and set updated_at."""
        try:
            update_data["updated_at"] = datetime.now(timezone.utc)
            doc_ref = db.collection("users").document(user_id)
            doc_ref.update(update_data)
            return True
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update user: {str(e)}"
            )

    @staticmethod
    def delete_user(user_id: str) -> None:
        """Delete a user document and their cycle logs, and from Firebase Auth."""
        try:
            user = UserService.get_user_by_id(user_id)
            if not user:
                return

            phone = user.get("phone")

            # Delete all related user collections (cycle_logs, emergency_contacts, consents, conversations)
            user_collections = ["cycle_logs", "emergency_contacts", "consents"]
            for col in user_collections:
                try:
                    docs = db.collection(col).where("user_id", "==", user_id).stream()
                    for d in docs:
                        try:
                            d.reference.delete()
                        except AttributeError:
                            d.delete()
                except Exception:
                    pass

            # Delete conversation document keyed by user_id
            try:
                db.collection("conversations").document(user_id).delete()
            except Exception:
                pass

            # Delete from Firebase Auth
            if phone:
                try:
                    import firebase_admin.auth
                    fb_user = firebase_admin.auth.get_user_by_phone_number(phone)
                    firebase_admin.auth.delete_user(fb_user.uid)
                except Exception as e:
                    # Ignore if the user is not found in Firebase Auth
                    pass

            # Delete user document
            db.collection("users").document(user_id).delete()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete user: {str(e)}"
            )


class CycleService:
    """Persists and retrieves per-user cycle logs in Firestore."""

    @staticmethod
    def create_log(user_id: str, log_data: Dict[str, Any]) -> str:
        """Create a new cycle log document for a user, always as a new
        document (no day-based upsert).

        Not currently called by `POST /cycle/log` — that endpoint now uses
        `upsert_log` so repeated logs on the same day merge into one
        document instead of creating duplicates. Kept here in case a
        future feature genuinely wants multiple entries per day (e.g. an
        explicit "add another entry" action) rather than day-level upsert
        semantics.
        """
        try:
            data = dict(log_data)
            # Firestore's client stores Python `date` values fine, but to
            # keep this consistent and avoid surprises with the query below,
            # normalize any bare `date` values to UTC `datetime`s.
            from datetime import date as date_type
            for key, value in list(data.items()):
                if isinstance(value, date_type) and not isinstance(value, datetime):
                    data[key] = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

            data["user_id"] = user_id
            data["created_at"] = datetime.now(timezone.utc)
            doc_ref = db.collection("cycle_logs").add(data)
            return doc_ref[1].id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save cycle log: {str(e)}"
            )

    @staticmethod
    def get_logs_for_user(user_id: str, limit: int = 10) -> list:
        """Return a user's cycle logs, most recent (by start_date) first.

        Uses Firestore's native sorting and limiting to fetch only the
        required number of documents. This requires a composite index on
        `(user_id, start_date desc)` for performance.

        If the index is missing, Firestore raises a FailedPrecondition
        exception with a direct link to create it. That error is preserved
        in the response (status 503) so the admin can use the link directly.

        For users with > 500 logs, consider adding pagination (offset/limit)
        to avoid large data transfers.
        """
        try:
            query = (
                db.collection("cycle_logs")
                .where("user_id", "==", user_id)
                .order_by("start_date", direction=firestore.Query.DESCENDING)
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
            # Missing composite index – treat as a configuration issue
            # and preserve the original error message (includes the link)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e)
            )
        except Exception as e:
            # Other Firestore errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch cycle logs: {str(e)}"
            )

    @staticmethod
    def _log_doc_id(user_id: str, log_date: date) -> str:
        return f"{user_id}_{log_date.isoformat()}"

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
        """
        try:
            doc_id = CycleService._log_doc_id(user_id, log_date)
            doc_ref = db.collection("cycle_logs").document(doc_id)
            existing = doc_ref.get()

            day_start = datetime.combine(log_date, datetime.min.time(), tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            update_fields = dict(fields)

            for key, value in list(update_fields.items()):
                if isinstance(value, date) and not isinstance(value, datetime):
                    update_fields[key] = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

            if existing.exists:
                update_fields["updated_at"] = now
                doc_ref.update(update_fields)
                return doc_id

            new_data = {**update_fields, "user_id": user_id, "start_date": day_start, "created_at": now}
            doc_ref.set(new_data)
            return doc_id
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save cycle log: {str(e)}"
            )

    @staticmethod
    def update_log(user_id: str, log_id: str, fields: Dict[str, Any]) -> str:
        """Update a specific cycle log by ID."""
        try:
            doc_ref = db.collection("cycle_logs").document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found"
                )
                
            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this log"
                )
                
            update_fields = dict(fields)
            for key, value in list(update_fields.items()):
                if isinstance(value, date) and not isinstance(value, datetime):
                    update_fields[key] = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
            
            update_fields["updated_at"] = datetime.now(timezone.utc)
            doc_ref.update(update_fields)
            return log_id
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update cycle log: {str(e)}"
            )

    @staticmethod
    def delete_log(user_id: str, log_id: str) -> None:
        """Delete a specific cycle log by ID."""
        try:
            doc_ref = db.collection("cycle_logs").document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cycle log not found"
                )
                
            if doc.to_dict().get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this log"
                )
                
            doc_ref.delete()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cycle log: {str(e)}"
            )


# ─── Maximum number of messages kept per conversation ────────────────────
MAX_CONVERSATION_MESSAGES = 50


class AssistantConversationService:
    """Persists assistant chat messages per user in Firestore.

    Each user has a single document in the ``conversations`` collection,
    keyed by ``user_id``, with a capped ``messages`` array.  When the
    array reaches ``MAX_CONVERSATION_MESSAGES`` (50) the oldest messages
    are trimmed so new ones always fit — effectively a rolling window of
    the most recent exchanges.

    This guarantees the document never grows large enough to hit
    Firestore's 1 MiB per-document limit (each message is ~200 bytes,
    so 50 messages is ~10 KiB) and keeps retrieval of the most recent N
    messages a single document read.
    """

    COLLECTION = "conversations"

    @staticmethod
    def get_or_create(user_id: str) -> dict:
        now = datetime.now(timezone.utc)
        doc_ref = db.collection(AssistantConversationService.COLLECTION).document(user_id)
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
    def get_recent_messages(user_id: str, limit: int = 10) -> list:
        conversation = AssistantConversationService.get_or_create(user_id)
        return conversation.get("messages", [])[-limit:]

    @staticmethod
    def add_messages(user_id: str, new_messages: list) -> None:
        now = datetime.now(timezone.utc)
        doc_ref = db.collection(AssistantConversationService.COLLECTION).document(user_id)
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
        current = doc.to_dict().get("messages", [])
        current.extend(new_messages)
        if len(current) > MAX_CONVERSATION_MESSAGES:
            current = current[-MAX_CONVERSATION_MESSAGES:]
        doc_ref.update({
            "messages": current,
            "updated_at": now,
        })
