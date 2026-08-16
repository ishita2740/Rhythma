import sys
import os
from datetime import datetime, timezone, timedelta
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.rate_limit_service import RateLimitService


def test_rate_limit_service_handles_iso_strings_and_naive_datetimes():
    now_iso = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    now_naive = datetime.now() - timedelta(seconds=20)

    # Mock Firestore doc containing string and naive timestamps
    class MockDoc:
        exists = True
        def to_dict(self):
            return {"timestamps": [now_iso, now_naive]}

    class MockDocRef:
        def get(self):
            return MockDoc()
        def set(self, data):
            pass

    original_doc = RateLimitService._document
    RateLimitService._document = staticmethod(lambda key: MockDocRef())

    try:
        # Check rate limiting safely without TypeError
        res = RateLimitService.is_rate_limited("test_key", limit=5, window_seconds=60)
        assert res is None
    finally:
        RateLimitService._document = original_doc
