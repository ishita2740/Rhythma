import sys
import os
from datetime import datetime, timezone, timedelta
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.auth import refresh_token_store, cleanup_expired_refresh_tokens, _hash_token


def test_cleanup_expired_refresh_tokens():
    expired_hash = _hash_token("expired_test_token")
    valid_hash = _hash_token("valid_test_token")

    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=1)

    refresh_token_store[expired_hash] = {"user_id": "u1", "expires_at": past}
    refresh_token_store[valid_hash] = {"user_id": "u2", "expires_at": future}

    cleanup_expired_refresh_tokens()

    assert expired_hash not in refresh_token_store
    assert valid_hash in refresh_token_store

    # Cleanup
    refresh_token_store.pop(valid_hash, None)
