from datetime import datetime, timedelta, timezone
from typing import Optional

from services.firestore_service import db


class RateLimitService:
    COLLECTION = "rate_limits"

    @staticmethod
    def _document(key: str):
        return db.collection(RateLimitService.COLLECTION).document(key)

    @staticmethod
    def is_rate_limited(
        key: str,
        limit: int = 5,
        window_seconds: int = 300,
    ) -> Optional[int]:
        now = datetime.now(timezone.utc)
        doc_ref = RateLimitService._document(key)
        doc = doc_ref.get()

        raw_timestamps = []
        if doc.exists:
            data = doc.to_dict() or {}
            raw_timestamps = data.get("timestamps", [])

        timestamps = []
        for t in raw_timestamps:
            if isinstance(t, str):
                try:
                    dt = datetime.fromisoformat(t)
                    timestamps.append(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
                except Exception:
                    pass
            elif isinstance(t, datetime):
                timestamps.append(t if t.tzinfo else t.replace(tzinfo=timezone.utc))

        timestamps = [
            t for t in timestamps
            if now - t < timedelta(seconds=window_seconds)
        ]

        if len(timestamps) >= limit:
            oldest = timestamps[0]
            remaining = int(
                (oldest + timedelta(seconds=window_seconds) - now).total_seconds()
            )

            doc_ref.set({"timestamps": timestamps})
            return max(remaining, 1)

        timestamps.append(now)
        doc_ref.set({"timestamps": timestamps})
        return None

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