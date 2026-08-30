"""An SMS goes to the sender's own number, with the server's own text (#382).

``POST /sms/send-summary`` took both its destination and its entire
message body from the request, and compared neither against the account
making the call:

    body_text = request.message or generate_cycle_sms_summary(user_id)
    client.messages.create(body=body_text, from_=from_phone, to=request.phone_number)

So any registered account could send attacker-chosen text to any E.164
number on earth, from the project's own Twilio sending number, billed to
the project.

Most of the tests below assert on the **arguments Twilio was called
with**, not on the response status. A 200 says the request was accepted;
only ``messages.create(to=..., body=...)`` says where the message
actually went and what it said, and that is the whole question here. A
test that only checked the status code would pass against the original
code too.
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
from api.sms import (  # noqa: E402
    SMS_MAX_CHARS,
    generate_cycle_sms_summary,
    registered_phone,
)
from core.auth import create_access_token  # noqa: E402
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

SEND_URL = "/api/v1/sms/send-summary"
SETTINGS_URL = "/api/v1/sms/settings"

OWN_NUMBER = "+919876543210"
SOMEONE_ELSES_NUMBER = "+447700900123"
TWILIO_FROM = "+10000000000"

_mock_db = None


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """A fresh in-memory Firestore per test, and no leaked buckets.

    Both module bindings are patched: ``rate_limit_service`` does
    ``from services.firestore_service import db``, so it holds a
    reference of its own, and the limiter is on this route's path.
    """
    global _mock_db
    _mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", _mock_db)
    monkeypatch.setattr(_rl_mod, "db", _mock_db)
    RateLimitService.clear_all()
    yield
    RateLimitService.clear_all()
    _mock_db = None


@pytest.fixture(autouse=True)
def _twilio_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", TWILIO_FROM)


@pytest.fixture
def twilio():
    """A stand-in Twilio client that records what it was asked to send."""
    with patch("twilio.rest.Client") as MockClient:
        instance = MagicMock()
        MockClient.return_value = instance
        instance.messages.create.return_value = MagicMock(sid="SM-test")
        yield instance


def _sent(twilio):
    """The keyword arguments of the single ``messages.create`` call."""
    assert twilio.messages.create.call_count == 1
    return twilio.messages.create.call_args.kwargs


def _account(phone=OWN_NUMBER, **extra):
    """Create a user and return headers authenticating as her."""
    payload = {"email": "sana@example.com", "sms_enabled": True, **extra}
    if phone is not None:
        payload["phone"] = phone
    user_id = UserService.create_user(payload)
    token = create_access_token(data={"sub": user_id})
    return user_id, {"Authorization": f"Bearer {token}"}


# ─── The destination ──────────────────────────────────────────────────────


def test_the_summary_goes_to_the_number_on_the_account(twilio):
    _, headers = _account()

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 200, response.text
    assert _sent(twilio)["to"] == OWN_NUMBER
    assert _sent(twilio)["from_"] == TWILIO_FROM


def test_a_matching_phone_number_in_the_body_is_accepted(twilio):
    """Clients written against the old contract keep working."""
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": OWN_NUMBER}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _sent(twilio)["to"] == OWN_NUMBER


def test_someone_elses_number_is_refused_and_nothing_is_sent(twilio):
    """The bug itself: this used to be a delivery.

    Refused rather than quietly redirected to the account's own number.
    A client asking to text a number that is not the account's has a bug,
    and silently sending somewhere else would hide it.
    """
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )

    assert response.status_code == 403
    assert twilio.messages.create.call_count == 0


def test_a_refused_destination_does_not_spend_the_rate_limit(twilio):
    """A client bug must not lock the user out of the feature.

    The allowance is one message a minute. If a rejected request
    consumed it, a client sending the wrong number would cost the user a
    minute of the feature per attempt, for a request that sent nothing.
    """
    _, headers = _account()

    refused = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )
    assert refused.status_code == 403

    allowed = client.post(SEND_URL, json={}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert _sent(twilio)["to"] == OWN_NUMBER


def test_an_account_with_no_saved_number_gets_a_clear_error(twilio):
    """Not a 500, and not a message to nowhere."""
    _, headers = _account(phone=None)

    response = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )

    assert response.status_code == 409
    assert "SMS settings" in response.json()["detail"]
    assert twilio.messages.create.call_count == 0


def test_a_malformed_stored_number_is_refused_rather_than_handed_to_twilio(twilio):
    """Reachable for documents written before POST /settings validated.

    A clear 409 naming the fix beats Twilio's own error surfacing as a
    500 the user cannot act on.
    """
    _, headers = _account(phone="9876543210")  # no country code

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 409
    assert twilio.messages.create.call_count == 0


def test_the_route_requires_authentication(twilio):
    response = client.post(SEND_URL, json={"phone_number": OWN_NUMBER})

    assert response.status_code == 401
    assert twilio.messages.create.call_count == 0


def test_two_accounts_cannot_be_pointed_at_one_victim(twilio):
    """The property that made the per-user rate limit insufficient.

    Registration is open, so N accounts used to mean N messages a minute
    at any chosen number. Binding the destination to the account is what
    removes that, not the limit.
    """
    _, first = _account(phone="+919000000001")
    UserService.create_user({"email": "b@example.com", "phone": "+919000000002"})
    _, second = _account(phone="+919000000003")

    for headers in (first, second):
        response = client.post(
            SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
        )
        assert response.status_code == 403

    assert twilio.messages.create.call_count == 0


# ─── The message body ─────────────────────────────────────────────────────


def test_a_caller_supplied_message_is_never_sent(twilio):
    """The other half of the hole.

    Ignored outright rather than length-bounded: there is no text to
    bound, which is a stronger guarantee than any ceiling would be.
    """
    _, headers = _account()

    response = client.post(
        SEND_URL,
        json={"phone_number": OWN_NUMBER, "message": "Visit http://evil.example"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = _sent(twilio)["body"]
    assert "evil.example" not in body
    # `Rhythma` rather than `Rhythma Summary`: this account has no logs,
    # and since #483 the summary service says so rather than emitting a
    # fabricated "Cycle Day 1/28" line. The claim under test here is that
    # the body is ours and not the caller's, which the sender prefix
    # establishes either way.
    assert body.startswith("Rhythma")


def test_an_enormous_message_cannot_inflate_the_bill(twilio):
    """Segments are billed. An unbounded body was an unbounded charge."""
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"message": "A" * 50_000}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert len(_sent(twilio)["body"]) <= SMS_MAX_CHARS


def test_the_sent_body_is_the_generated_summary(twilio):
    """What reaches Twilio is what the summary service produced.

    The account under test has no logged cycles, so since #483 that is
    the no-anchor sentence rather than a countdown. The disclaimer
    assertion is the one that matters and is unchanged — #317 requires it
    on every surface, and it is the part most at risk of being dropped
    for space.
    """
    _, headers = _account()

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 200, response.text
    body = _sent(twilio)["body"]
    assert body.startswith("Rhythma")
    assert "Log your last period" in body
    assert "not medical/contraceptive advice" in body


# ─── generate_cycle_sms_summary ───────────────────────────────────────────


def test_the_summary_fits_one_segment():
    summary = generate_cycle_sms_summary("nobody")
    assert len(summary) <= SMS_MAX_CHARS


def test_the_disclaimer_is_all_or_nothing():
    """Half of "not medical/contraceptive advice" says something else.

    The old code fell back to ``summary[:160]``, which drops the
    disclaimer — correct — but could also slice the sentence before it.
    """
    summary = generate_cycle_sms_summary("nobody")
    if "Estimate only" in summary:
        assert summary.rstrip().endswith("medical/contraceptive advice.")


def test_a_long_summary_is_cut_at_a_word_not_through_a_number():
    """``summary[:160]`` could turn "in ~12 days" into "in ~1".

    Not a shorter summary — a different and wrong one, and a cycle
    figure is exactly what lands near the boundary. Exercised through
    the helper directly because the real sentence never gets long
    enough, which is the point: this is insurance against the wording
    being changed later.

    The marker is now `...` rather than `…` for GSM-7 text (#483):
    U+2026 is not in the GSM-7 alphabet, so appending it re-encoded the
    whole message as UCS-2 and cut the segment from 160 characters to
    70 — the trim intended to fit one segment was what made it three.
    """
    from api.sms import _fit_to_one_segment

    text = "Rhythma Summary: " + ("word " * 60) + "final"
    fitted = _fit_to_one_segment(text)

    assert len(fitted) <= SMS_MAX_CHARS
    assert fitted.endswith("...")
    assert not fitted.rstrip(".").endswith("wor")


def test_a_short_summary_is_returned_untouched():
    from api.sms import _fit_to_one_segment

    assert _fit_to_one_segment("Short.") == "Short."


# ─── registered_phone ─────────────────────────────────────────────────────


def test_registered_phone_prefers_the_same_field_the_settings_screen_shows():
    """A user must not see one number and have the summary sent to another."""
    assert registered_phone({"phone": OWN_NUMBER, "sms_phone_number": "+1"}) == (
        OWN_NUMBER
    )


def test_registered_phone_falls_back_to_the_sms_specific_field():
    assert registered_phone({"sms_phone_number": OWN_NUMBER}) == OWN_NUMBER


@pytest.mark.parametrize("user", [None, {}, {"phone": ""}, {"phone": "   "}])
def test_registered_phone_treats_blank_as_absent(user):
    assert registered_phone(user) is None


def test_settings_and_send_agree_on_the_destination(twilio):
    """The screen and the send path resolve the number the same way.

    Asserted end to end rather than by inspection: these two used to
    read the account separately, and only one of them read it at all.
    """
    _, headers = _account(phone=None, sms_phone_number=OWN_NUMBER)

    shown = client.get(SETTINGS_URL, headers=headers)
    assert shown.status_code == 200
    assert shown.json()["phoneNumber"] == OWN_NUMBER

    sent = client.post(SEND_URL, json={}, headers=headers)
    assert sent.status_code == 200, sent.text
    assert _sent(twilio)["to"] == shown.json()["phoneNumber"]


def test_a_number_saved_through_settings_becomes_the_destination(twilio):
    """The whole journey, through the public API only."""
    _, headers = _account(phone=None)

    saved = client.post(
        SETTINGS_URL,
        json={"phoneNumber": OWN_NUMBER, "enabled": True},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text

    sent = client.post(SEND_URL, json={}, headers=headers)
    assert sent.status_code == 200, sent.text
    assert _sent(twilio)["to"] == OWN_NUMBER


# ─── Unchanged behaviour ──────────────────────────────────────────────────


def test_the_rate_limit_still_applies_to_a_valid_send(twilio):
    _, headers = _account()

    first = client.post(SEND_URL, json={}, headers=headers)
    assert first.status_code == 200, first.text

    second = client.post(SEND_URL, json={}, headers=headers)
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert twilio.messages.create.call_count == 1


def test_a_twilio_failure_is_still_reported_as_a_500(twilio):
    _, headers = _account()
    twilio.messages.create.side_effect = Exception("Twilio down")

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 500
    assert "Failed to send SMS" in response.json()["detail"]


def test_missing_twilio_credentials_are_still_reported(monkeypatch, twilio):
    _, headers = _account()
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 500
    assert "Twilio credentials are not configured" in response.json()["detail"]
    assert twilio.messages.create.call_count == 0


def test_a_malformed_phone_number_in_the_body_is_still_a_422(twilio):
    """The E.164 pattern on the field is kept, even though it no longer
    selects a destination — a client sending nonsense should hear about
    it from validation rather than from a 403 about ownership."""
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": "not-a-number"}, headers=headers
    )

    assert response.status_code == 422
    assert twilio.messages.create.call_count == 0
