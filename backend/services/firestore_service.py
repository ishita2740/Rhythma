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
        if self.data is not None:
            self.data.update(update_data)
            self.collection.store[self.id] = self.data

    def set(self, document_data):
        self.data = document_data.copy()
        self.collection.store[self.id] = self.data
        self.exists = True

    def delete(self):
        if self.id in self.collection.store:
            del self.collection.store[self.id]

        self.data = None
        self.exists = False


class MockQuery:
    def __init__(self, documents):
        self._documents = documents
        self._order_by_field = None
        self._order_by_direction = None
        self._limit_count = None

    def limit(self, count):
        self._limit_count = count
        return self

    def order_by(self, field, direction=None):
        self._order_by_field = field
        self._order_by_direction = (
            direction or firestore.Query.ASCENDING
        )
        return self

    def stream(self):
        docs = self._documents[:]

        if self._order_by_field:
            reverse = (
                self._order_by_direction
                == firestore.Query.DESCENDING
            )

            docs.sort(
                key=lambda doc: doc.data.get(
                    self._order_by_field
                ),
                reverse=reverse,
            )

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

        self.store[doc_id] = document_data

        return (
            None,
            MockDocumentReference(
                doc_id,
                document_data,
                self,
            ),
        )

    def document(self, doc_id):
        data = self.store.get(doc_id)

        return MockDocumentReference(
            doc_id,
            data,
            self,
        )

    def where(self, field, op, value):
        filtered = []

        for doc_id, data in self.store.items():
            if data.get(field) == value:
                filtered.append(
                    MockDocumentReference(
                        doc_id,
                        data,
                        self,
                    )
                )

        return MockQuery(filtered)

    def order_by(self, field, direction=None):
        return self

    def limit(self, count):
        return self


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
    def create_user(
        user_data: Dict[str, Any]
    ) -> str:
        """Create a new user document in Firestore."""
        try:
            now = datetime.now(timezone.utc)

            user_data["created_at"] = now
            user_data["updated_at"] = now

            doc_ref = db.collection(
                "users"
            ).add(user_data)

            return doc_ref[1].id

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {str(e)}",
            )

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )

    @staticmethod
    def get_user_by_email(
        email: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a user by email."""
        try:
            users = (
                db.collection("users")
                .where("email", "==", email)
                .limit(1)
                .stream()
            )

            for user in users:
                data = user.to_dict()
                data["id"] = user.id
                return data

            return None

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user: {str(e)}",
            )

    @staticmethod
    def update_user(
        user_id: str,
        update_data: Dict[str, Any],
    ) -> bool:
        """Update a user document and set updated_at."""
        try:
            update_data["updated_at"] = datetime.now(
                timezone.utc
            )

            doc_ref = (
                db.collection("users")
                .document(user_id)
            )

            doc_ref.update(update_data)

            return True

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update user: {str(e)}",
            )

    @staticmethod
    def delete_user(user_id: str) -> None:
        """Delete a user and all associated data."""
        try:
            user = UserService.get_user_by_id(user_id)

            if not user:
                return

            phone = user.get("phone")

            # Delete all related user collections.
            #
            # IMPORTANT:
            # Verify that each collection actually stores the owning
            # user's ID in a field named "user_id".
            user_collections = [
                "cycle_logs",
                "emergency_contacts",
                "consents",
            ]

            for col in user_collections:
                try:
                    docs = (
                        db.collection(col)
                        .where("user_id", "==", user_id)
                        .stream()
                    )

                    for doc in docs:
                        try:
                            doc.reference.delete()
                        except AttributeError:
                            # Support the local Mock Firestore client.
                            doc.delete()

                except Exception as e:
                    logger.error(
                        "Failed to delete user data from "
                        "collection '%s' for user '%s': %s",
                        col,
                        user_id,
                        str(e),
                        exc_info=True,
                    )

                    raise HTTPException(
                        status_code=(
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        ),
                        detail=(
                            f"Failed to delete user data "
                            f"from {col}"
                        ),
                    )

            # Delete conversation document keyed by user_id.
            try:
                (
                    db.collection("conversations")
                    .document(user_id)
                    .delete()
                )

            except Exception as e:
                logger.error(
                    "Failed to delete conversation "
                    "for user '%s': %s",
                    user_id,
                    str(e),
                    exc_info=True,
                )

                raise HTTPException(
                    status_code=(
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    detail=(
                        "Failed to delete user "
                        "conversation data"
                    ),
                )

            # Delete from Firebase Auth.
            if phone:
                try:
                    from firebase_admin import auth

                    fb_user = (
                        auth.get_user_by_phone_number(phone)
                    )

                    auth.delete_user(fb_user.uid)

                except auth.UserNotFoundError:
                    # User does not exist in Firebase Auth.
                    pass

                except Exception as e:
                    logger.error(
                        "Failed to delete Firebase Auth "
                        "user for '%s': %s",
                        user_id,
                        str(e),
                        exc_info=True,
                    )

                    raise HTTPException(
                        status_code=(
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        ),
                        detail="Failed to delete Firebase Auth user",
                    )

            # Delete the main user document last.
            (
                db.collection("users")
                .document(user_id)
                .delete()
            )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(
                "Failed to delete user '%s': %s",
                user_id,
                str(e),
                exc_info=True,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete user: {str(e)}",
            )


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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save cycle log: {str(e)}",
            )

    @staticmethod
    def get_logs_for_user(
        user_id: str,
        limit: int = 10,
    ) -> list:
        """Return a user's cycle logs, most recent first."""
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to fetch cycle logs: {str(e)}"
                ),
            )

    @staticmethod
    def _log_doc_id(
        user_id: str,
        log_date: date,
    ) -> str:
        return f"{user_id}_{log_date.isoformat()}"

    @staticmethod
    def upsert_log(
        user_id: str,
        log_date: date,
        fields: Dict[str, Any],
    ) -> str:
        """Create or update a cycle log for a specific day."""
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

            update_fields = dict(fields)

            for key, value in list(
                update_fields.items()
            ):
                if (
                    isinstance(value, date)
                    and not isinstance(value, datetime)
                ):
                    update_fields[key] = (
                        datetime.combine(
                            value,
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        )
                    )

            if existing.exists:
                update_fields["updated_at"] = now
                doc_ref.update(update_fields)

                return doc_id

            new_data = {
                **update_fields,
                "user_id": user_id,
                "start_date": day_start,
                "created_at": now,
            }

            doc_ref.set(new_data)

            return doc_id

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save cycle log: {str(e)}",
            )

    @staticmethod
    def update_log(
        user_id: str,
        log_id: str,
        fields: Dict[str, Any],
    ) -> str:
        """Update a specific cycle log by ID."""
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

            update_fields = dict(fields)

            for key, value in list(
                update_fields.items()
            ):
                if (
                    isinstance(value, date)
                    and not isinstance(value, datetime)
                ):
                    update_fields[key] = (
                        datetime.combine(
                            value,
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        )
                    )

            update_fields["updated_at"] = (
                datetime.now(timezone.utc)
            )

            doc_ref.update(update_fields)

            return log_id

        except HTTPException:
            raise

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to update cycle log: {str(e)}"
                ),
            )

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to delete cycle log: {str(e)}"
                ),
            )


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
