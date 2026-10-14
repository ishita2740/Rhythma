"""What ``UserProfileUpdate.language`` is allowed to be (issue #136).

Three layers, mirroring ``test_profile_validation.py``:

The normaliser (``core/supported_languages.normalize_language``) is tested
directly — the codes a client legitimately sends, the region tags it should
have reduced, and the values it should be told about.

``UserProfileUpdate`` is tested as a model, because a rule that lives in a
module and is not wired into the schema protects nothing.

And ``PATCH /auth/profile`` is driven through the real app, because the point
of the change is that an unsupported locale never reaches Firestore — a
direct API call must not be able to bypass the client-side
``LocaleProvider.setLocale()`` restriction.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Mocks, matching the other route tests in this suite ──────────────────


class MockGemini:
    def __getattr__(self, name):
        return self

    def configure(self, *args, **kwargs):
        pass

    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    text = "Mock Gemini response"

                return MockResponse()

        return MockModel()


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"
os.environ["COOKIE_SECURE"] = "false"

_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()

from fastapi.testclient import TestClient  # noqa: E402

from core.supported_languages import (  # noqa: E402
    SUPPORTED_LANGUAGE_CODES,
    normalize_language,
)
from main import app  # noqa: E402
from models.user import UserProfileUpdate  # noqa: E402

client = TestClient(app)


# ─── Codes a client legitimately sends ────────────────────────────────────


@pytest.mark.parametrize("code", sorted(SUPPORTED_LANGUAGE_CODES))
def test_every_supported_code_is_accepted(code):
    assert normalize_language(code) == code


def test_none_passes_through_as_omission():
    assert normalize_language(None) is None


def test_an_empty_or_blank_string_is_treated_as_omission():
    assert normalize_language("") is None
    assert normalize_language("   ") is None


# ─── Region tags reduce to their base code ────────────────────────────────


@pytest.mark.parametrize(
    "sent,expected",
    [
        ("en-US", "en"),
        ("hi_IN", "hi"),
        ("PA", "pa"),
        ("  ta-IN  ", "ta"),
        ("en-GB", "en"),
    ],
)
def test_a_region_tag_is_reduced_to_its_base(sent, expected):
    assert normalize_language(sent) == expected


# ─── Values a client should be told about ─────────────────────────────────


@pytest.mark.parametrize("sent", ["fr", "klingon", "xx", "zz-ZZ", "eng"])
def test_an_unsupported_code_is_refused(sent):
    with pytest.raises(ValueError) as exc:
        normalize_language(sent)
    assert "Unsupported language" in str(exc.value)


def test_the_rejection_names_the_supported_set():
    with pytest.raises(ValueError) as exc:
        normalize_language("klingon")
    message = str(exc.value)
    # A couple of representative codes, so the user can see what would work.
    assert "en" in message and "hi" in message and "pa" in message


def test_a_value_that_is_not_text_is_refused():
    for sent in (42, 3.5, True, ["en"], {"language": "en"}):
        with pytest.raises(ValueError):
            normalize_language(sent)


def test_an_absurdly_long_value_is_refused_before_parsing():
    with pytest.raises(ValueError):
        normalize_language("en" + "x" * 5000)


# ─── Wired into the schema ────────────────────────────────────────────────


def test_the_model_accepts_a_supported_code():
    update = UserProfileUpdate(language="hi")
    assert update.language == "hi"


def test_the_model_reduces_a_region_tag():
    update = UserProfileUpdate(language="en-US")
    assert update.language == "en"


def test_the_model_refuses_an_unsupported_code():
    with pytest.raises(ValidationError) as exc:
        UserProfileUpdate(language="klingon")
    assert "language" in str(exc.value)


def test_an_update_that_omits_language_is_unaffected():
    """PATCH semantics: `model_dump()` must not start emitting a `None`."""
    update = UserProfileUpdate(full_name="Alice Doe")
    dump = update.model_dump()
    assert dump["language"] is None
    assert {k: v for k, v in dump.items() if v is not None} == {
        "full_name": "Alice Doe"
    }


# ─── Through the route ────────────────────────────────────────────────────


@pytest.fixture
def _authenticated(monkeypatch):
    """A signed-in user whose profile writes are captured rather than stored."""
    import core.auth_router as auth_router_module
    from core.auth import get_current_user

    written = {}

    def _fake_update(user_id, updates):
        written.update(updates)
        return True

    def _fake_get(user_id):
        return {
            "id": user_id,
            "email": "asha@example.com",
            "username": "ashadev",
            **written,
        }

    monkeypatch.setattr(
        auth_router_module.UserService, "update_user", staticmethod(_fake_update)
    )
    monkeypatch.setattr(
        auth_router_module.UserService, "get_user_by_id", staticmethod(_fake_get)
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "email": "asha@example.com",
    }
    yield written
    app.dependency_overrides.pop(get_current_user, None)


def test_the_route_stores_a_supported_code(_authenticated):
    response = client.patch("/api/v1/auth/profile", json={"language": "mr"})

    assert response.status_code == 200
    assert _authenticated["language"] == "mr"


def test_the_route_reduces_a_region_tag_before_storing(_authenticated):
    response = client.patch("/api/v1/auth/profile", json={"language": "hi-IN"})

    assert response.status_code == 200
    assert _authenticated["language"] == "hi"


def test_the_route_refuses_an_unsupported_code_with_a_422(_authenticated):
    response = client.patch("/api/v1/auth/profile", json={"language": "klingon"})

    assert response.status_code == 422
    assert _authenticated == {}, "nothing should have reached the store"


def test_the_422_names_the_field(_authenticated):
    response = client.patch("/api/v1/auth/profile", json={"language": "fr"})

    assert response.status_code == 422
    assert "language" in response.text


def test_other_profile_fields_still_save(_authenticated):
    """The change must not turn an ordinary update into a rejection."""
    response = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Asha", "cycle_length": 30, "language": "ta"},
    )

    assert response.status_code == 200
    assert _authenticated["cycle_length"] == 30
    assert _authenticated["language"] == "ta"
