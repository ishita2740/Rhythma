import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.user import UserProfileUpdate


def test_user_profile_update_patch_semantics():
    # Partial update with only full_name specified
    update = UserProfileUpdate(full_name="Alice Doe")
    dump = update.model_dump(exclude_unset=True)

    assert "full_name" in dump
    assert dump["full_name"] == "Alice Doe"
    # Verify last_period_is_approximate is unset so it won't overwrite existing setting
    assert "last_period_is_approximate" not in dump
