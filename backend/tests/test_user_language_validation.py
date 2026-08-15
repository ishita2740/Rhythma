import sys
import os
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.user import UserProfileUpdate


def test_user_profile_update_valid_language():
    update = UserProfileUpdate(language="hi")
    assert update.language == "hi"

    update_caps = UserProfileUpdate(language="EN")
    assert update_caps.language == "en"


def test_user_profile_update_invalid_language():
    with pytest.raises(ValidationError):
        UserProfileUpdate(language="unsupported_xyz")
