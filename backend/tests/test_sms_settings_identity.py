"""Saving SMS settings must not touch the account's identity (issue #547).

``POST /sms/settings`` wrote the number it was given into ``phone`` as
well as ``sms_phone_number``:

    UserService.update_user(current_user["id"], {
        "phone": phone or "",
        "sms_phone_number": phone or "",
        "sms_enabled": settings.enabled,
    })

``phone`` is what ``firebase_login`` resolves an account by, via
``UserService.get_user_by_phone``. So an SMS preferences screen was
editing the credential, and ``phone or ""`` meant clearing the box and
unticking the toggle *erased* it.

Two things about how this file is written.

The assertions are on **the stored user document**, not on the response
body. A 200 says the request was accepted; only ``users/{id}.phone``
says whether the login number survived, and a test that checked the
response would have passed against the original code too — it echoed the
number back either way.

And the sign-in test drives the real ``firebase_login`` route rather than
asserting on a field. "You can no longer log in" is the actual failure
issue #547 describes; a field assertion is a proxy for it, and a proxy is
what let this ship.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Mock google.generativeai ──────────────────────────────────────────────
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

# ─── Mock firebase_admin ──────────────────────────────────────────────────
_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app  # noqa: E402
from api.sms import SMSSettings, registered_phone  # noqa: E402
from core.auth import create_access_token  # noqa: E402
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

SETTINGS_URL = "/api/v1/sms/settings"
FIREBASE_LOGIN_URL = "/api/v1/auth/firebase-login"

LOGIN_NUMBER = "+919876543210"
SECOND_HANDSET = "+919000000001"


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """A fresh in-memory Firestore per test, and no leaked buckets."""
    mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", mock_db)
    monkeypatch.setattr(_rl_mod, "db", mock_db)
    RateLimitService.clear_all()
    yield
    RateLimitService.clear_all()


def _account(phone=LOGIN_NUMBER, **extra):
    """Create a user and return ``(user_id, auth headers)``."""
    payload = {"email": "sana@example.com", **extra}
    if phone is not None:
        payload["phone"] = phone
    user_id = UserService.create_user(payload)
    token = create_access_token(data={"sub": user_id})
    return user_id, {"Authorization": f"Bearer {token}"}


def _stored(user_id):
    return UserService.get_user_by_id(user_id) or {}


# ─── The credential is not a setting on this screen ───────────────────────


def test_saving_a_number_does_not_move_the_login_number():
    """The core of #547: `phone` is who she is, not where texts go."""
    user_id, headers = _account()

    response = client.post(
        SETTINGS_URL,
        json={"phoneNumber": SECOND_HANDSET, "enabled": True},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id)["phone"] == LOGIN_NUMBER
    assert _stored(user_id)["sms_phone_number"] == SECOND_HANDSET


def test_turning_summaries_off_does_not_erase_the_login_number():
    """`phone or ""` used to write an empty string over the credential."""
    user_id, headers = _account()

    response = client.post(
        SETTINGS_URL, json={"phoneNumber": "", "enabled": False}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id)["phone"] == LOGIN_NUMBER


def test_the_account_can_still_sign_in_after_the_settings_are_cleared():
    """The failure #547 describes, driven end to end rather than by proxy.

    Before the fix this posted `phone: ""`, `get_user_by_phone` matched
    nothing, and `firebase_login` took its create-a-new-account branch —
    so the second login below returned a *different* user id and the
    original account, with its whole cycle history, became unreachable.
    """
    user_id, headers = _account()

    client.post(
        SETTINGS_URL, json={"phoneNumber": "", "enabled": False}, headers=headers
    )

    with patch("firebase_admin.auth.verify_id_token") as verify:
        verify.return_value = {"phone_number": LOGIN_NUMBER, "uid": "firebase-uid"}
        login = client.post(
            FIREBASE_LOGIN_URL,
            json={"id_token": "valid"},
            headers={"X-Client-Platform": "mobile"},
        )

    assert login.status_code == 200, login.text
    body = login.json()
    assert body["is_new_user"] is False, (
        "signing in after clearing SMS settings created a second account"
    )

    # `is_new_user` is the route's own account-was-created signal; this is
    # the same claim checked from the other side, so the test does not
    # depend on that flag being reported correctly.
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["id"] == user_id


def test_one_account_cannot_claim_another_accounts_login_number():
    """The collision is removed rather than guarded — nothing writes it."""
    victim_id, _ = _account()
    _, attacker_headers = _account(
        phone="+919000000002", email="other@example.com"
    )

    response = client.post(
        SETTINGS_URL,
        json={"phoneNumber": LOGIN_NUMBER, "enabled": True},
        headers=attacker_headers,
    )

    assert response.status_code == 200, response.text
    assert UserService.get_user_by_phone(LOGIN_NUMBER)["id"] == victim_id


# ─── A toggle is not a deletion ───────────────────────────────────────────


def test_omitting_the_number_keeps_the_saved_one():
    """A client sending only the toggle must not forget the destination."""
    user_id, headers = _account(phone=None)

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": SECOND_HANDSET, "enabled": True},
        headers=headers,
    )
    response = client.post(SETTINGS_URL, json={"enabled": False}, headers=headers)

    assert response.status_code == 200, response.text
    assert _stored(user_id)["sms_phone_number"] == SECOND_HANDSET
    assert _stored(user_id)["sms_enabled"] is False
    assert response.json()["phoneNumber"] == SECOND_HANDSET


def test_an_explicitly_empty_number_does_forget_it():
    """Clearing the box is a real intention and is still honoured."""
    user_id, headers = _account(phone=None)

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": SECOND_HANDSET, "enabled": True},
        headers=headers,
    )
    client.post(SETTINGS_URL, json={"phoneNumber": "", "enabled": False}, headers=headers)

    assert _stored(user_id)["sms_phone_number"] == ""


def test_phone_was_submitted_reads_the_keys_the_json_carried():
    """`None` and "absent" are indistinguishable once parsed; this isn't."""
    assert SMSSettings(enabled=False).phone_was_submitted is False
    assert SMSSettings(phoneNumber="", enabled=False).phone_was_submitted is True
    assert (
        SMSSettings(phoneNumber=LOGIN_NUMBER, enabled=True).phone_was_submitted
        is True
    )


# ─── What the screen shows is what would be sent ──────────────────────────


def test_the_response_is_the_number_a_summary_would_go_to():
    """Not an echo of the request: after a clear, the fallback applies."""
    user_id, headers = _account()

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": SECOND_HANDSET, "enabled": True},
        headers=headers,
    )
    cleared = client.post(
        SETTINGS_URL, json={"phoneNumber": "", "enabled": False}, headers=headers
    )

    assert cleared.json()["phoneNumber"] == LOGIN_NUMBER
    assert registered_phone(_stored(user_id)) == LOGIN_NUMBER


def test_the_settings_screen_shows_the_number_that_was_saved():
    """`sms_phone_number` wins over `phone`, or saving would be a no-op."""
    _, headers = _account()

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": SECOND_HANDSET, "enabled": True},
        headers=headers,
    )
    shown = client.get(SETTINGS_URL, headers=headers)

    assert shown.status_code == 200
    assert shown.json()["phoneNumber"] == SECOND_HANDSET


def test_an_account_with_no_sms_number_still_shows_its_own(monkeypatch):
    """The fallback: nothing changes for accounts that never used this."""
    _, headers = _account()

    shown = client.get(SETTINGS_URL, headers=headers)

    assert shown.json()["phoneNumber"] == LOGIN_NUMBER


# ─── Validation is unchanged ──────────────────────────────────────────────


def test_enabling_without_a_number_is_still_refused():
    _, headers = _account(phone=None)

    response = client.post(SETTINGS_URL, json={"enabled": True}, headers=headers)

    assert response.status_code == 400
    assert "phone number is required" in response.json()["detail"]


def test_a_malformed_number_is_still_refused_and_writes_nothing():
    user_id, headers = _account()

    response = client.post(
        SETTINGS_URL, json={"phoneNumber": "12345", "enabled": True}, headers=headers
    )

    assert response.status_code == 400
    assert "E.164" in response.json()["detail"]
    assert _stored(user_id)["phone"] == LOGIN_NUMBER
    assert "sms_phone_number" not in _stored(user_id)
