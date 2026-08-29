"""The chat webhooks, and what they refuse to do (issue #416).

Three properties are worth more than the rest of this file put together,
and each has a test named after it:

* an unverified delivery is refused;
* a chat that has not been linked to an account cannot read one, however
  the caller spells the identity in the payload;
* the identity used to fetch data comes from the stored link and never
  from the request.

The last one is the regression that matters. The route this replaces read
``payload["message"]["chat"]["id"]`` and passed it to ``get_user_scores``,
so posting a Rhythma user id there returned that user's cycle summary to
an unauthenticated caller.
"""

import base64
import hashlib
import hmac
import os
import sys
from datetime import datetime, timedelta, timezone

import firebase_admin.auth
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_auth import client, mock_auth_dependencies  # noqa: F401,E402

import services.chat_link_service as chat_link_service  # noqa: E402
import services.firestore_service as fs  # noqa: E402
from core import webhook_auth  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

TELEGRAM_URL = "/api/v1/bot/telegram/webhook"
WHATSAPP_URL = "/api/v1/bot/whatsapp/webhook"
LINK_CODE_URL = "/api/v1/bot/link-code"
LINKS_URL = "/api/v1/bot/links"

SECRET = "telegram-webhook-secret-for-tests"

#: The id ``mock_auth_dependencies`` signs tokens for.
USER_ID = "test-user-id-123"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """A fresh store and no configured secrets for every test.

    Secrets are set per test rather than globally: half these cases are
    about what happens when verification *is* configured and half about
    the unconfigured local-development path, and a leaked environment
    variable would silently turn one into the other.
    """

    def _reset():
        client.cookies.clear()
        RateLimitService.clear_all()
        collections = getattr(fs.db, "_collections", None)
        if collections is not None:
            collections.clear()

    _reset()
    webhook_auth.reset_warning_state()
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("WEBHOOK_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("CHAT_LINK_CODE_TTL_SECONDS", raising=False)
    yield
    _reset()


@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid",
    }
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "mobile"},
    )
    # Registering cost one attempt against the login limiter; clearing it
    # keeps a test that asserts on a *different* limiter from tripping
    # over this one.
    RateLimitService.clear_all()
    return {"Authorization": f"Bearer {token_response.json()['access_token']}"}


def _telegram_update(chat_id, text):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": text}}


def _seed_user_with_logs(user_id=USER_ID):
    """An account with cycle history, so there is something to leak."""
    fs.db.collection("users").document(user_id).set(
        {"username": "webhooktester", "email": "webhook@example.com"}
    )
    for index, offset in enumerate((0, 28)):
        fs.db.collection("cycle_logs").document(f"{user_id}_log{index}").set(
            {
                "user_id": user_id,
                "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=offset),
                "end_date": datetime(2026, 1, 5, tzinfo=timezone.utc)
                + timedelta(days=offset),
                "flow_intensity": "medium",
            }
        )
    return user_id


# ─── Verification ─────────────────────────────────────────────────────────


def test_telegram_delivery_without_the_secret_is_refused(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(TELEGRAM_URL, json=_telegram_update(4242, "help"))

    assert response.status_code == 401


def test_telegram_delivery_with_the_wrong_secret_is_refused(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(
        TELEGRAM_URL,
        json=_telegram_update(4242, "help"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET + "x"},
    )

    assert response.status_code == 401


def test_telegram_delivery_with_the_right_secret_is_answered(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(
        TELEGRAM_URL,
        json=_telegram_update(4242, "help"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "sendMessage"
    assert body["chat_id"] == "4242"
    assert "status" in body["text"]


def test_the_rejection_says_nothing_about_which_check_failed(monkeypatch):
    """A caller who cannot authenticate is not owed a reason."""
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    missing = client.post(TELEGRAM_URL, json=_telegram_update(1, "help"))
    wrong = client.post(
        TELEGRAM_URL,
        json=_telegram_update(1, "help"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: "nope"},
    )

    assert missing.json()["detail"] == wrong.json()["detail"]


def test_an_unconfigured_channel_still_serves_local_development():
    """No secret set — the delivery is processed rather than refused.

    Hard-failing here would make a local ``uvicorn`` run impossible and
    would turn "the bot was never configured" into an outage. What must
    not happen is that it passes *silently*, which is what
    ``verification_configured`` is for.
    """
    assert webhook_auth.verification_configured("telegram") is False

    response = client.post(TELEGRAM_URL, json=_telegram_update(99, "help"))

    assert response.status_code == 200


# ─── Twilio's signature ───────────────────────────────────────────────────


def _sign(auth_token, url, params):
    """Twilio's algorithm, written out independently of the module.

    Signing with the function under test would prove only that it agrees
    with itself.
    """
    payload = url + "".join(name + params[name] for name in sorted(params))
    digest = hmac.new(
        auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_twilio_signature_matches_an_independent_implementation():
    params = {"Body": "status", "From": "whatsapp:+919876543210", "To": "whatsapp:+14155238886"}
    url = "https://api.rhythma.app/api/v1/bot/whatsapp/webhook"

    assert webhook_auth.twilio_signature("token", url, params) == _sign("token", url, params)


def test_whatsapp_delivery_without_a_signature_is_refused(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")

    response = client.post(WHATSAPP_URL, data={"From": "whatsapp:+91", "Body": "help"})

    assert response.status_code == 401


def test_whatsapp_delivery_with_a_valid_signature_is_answered(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("WEBHOOK_PUBLIC_BASE_URL", "http://testserver")

    params = {"From": "whatsapp:+919876543210", "Body": "help"}
    signature = _sign("twilio-token", f"http://testserver{WHATSAPP_URL}", params)

    response = client.post(
        WHATSAPP_URL,
        data=params,
        headers={webhook_auth.TWILIO_SIGNATURE_HEADER: signature},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Response><Message>" in response.text


def test_a_signature_for_a_different_body_does_not_verify(monkeypatch):
    """The signature covers the parameters, not just the URL."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("WEBHOOK_PUBLIC_BASE_URL", "http://testserver")

    signed_for = {"From": "whatsapp:+919876543210", "Body": "help"}
    signature = _sign("twilio-token", f"http://testserver{WHATSAPP_URL}", signed_for)

    response = client.post(
        WHATSAPP_URL,
        data={"From": "whatsapp:+919876543210", "Body": "status"},
        headers={webhook_auth.TWILIO_SIGNATURE_HEADER: signature},
    )

    assert response.status_code == 401


# ─── The identity in the payload is not an identity ───────────────────────


def test_a_user_id_in_the_payload_reads_nobody(monkeypatch):
    """The regression this issue was filed for.

    Posting a real Rhythma user id as the chat id used to return that
    user's logged cycle count and health scores to an unauthenticated
    caller. It now resolves to no link, so the reply is the public prompt.
    """
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    user_id = _seed_user_with_logs()

    response = client.post(
        TELEGRAM_URL,
        json=_telegram_update(user_id, "status"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    assert response.status_code == 200
    text = response.json()["text"]
    assert "not connected to a Rhythma account" in text
    assert "cycle day" not in text.lower()


def test_an_unlinked_chat_asking_for_status_gets_no_numbers(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    _seed_user_with_logs()

    response = client.post(
        TELEGRAM_URL,
        json=_telegram_update(555001, "status"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    text = response.json()["text"]
    assert not any(char.isdigit() for char in text.replace("ABCD2345", ""))


# ─── Linking ──────────────────────────────────────────────────────────────


def test_link_code_requires_authentication():
    assert client.post(LINK_CODE_URL, json={"channel": "telegram"}).status_code == 401


def test_a_code_links_the_chat_and_then_status_works(monkeypatch, auth_headers):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    issued = client.post(LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers)
    assert issued.status_code == 200
    code = issued.json()["code"]
    assert len(code) == chat_link_service.CODE_LENGTH

    linked = client.post(
        TELEGRAM_URL,
        json=_telegram_update(778899, f"link {code}"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )
    assert "now connected" in linked.json()["text"]

    status_reply = client.post(
        TELEGRAM_URL,
        json=_telegram_update(778899, "status"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )
    text = status_reply.json()["text"]
    # Either a cycle summary or the "nothing logged yet" line, but never
    # the unlinked prompt.
    assert "not connected to a Rhythma account" not in text


def test_a_code_cannot_be_used_twice(monkeypatch, auth_headers):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]
    secret_header = {webhook_auth.TELEGRAM_SECRET_HEADER: SECRET}

    client.post(TELEGRAM_URL, json=_telegram_update(1001, f"link {code}"), headers=secret_header)
    second = client.post(
        TELEGRAM_URL, json=_telegram_update(1002, f"link {code}"), headers=secret_header
    )

    assert "did not work" in second.json()["text"]


def test_issuing_a_new_code_invalidates_the_previous_one(auth_headers):
    first = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]
    client.post(LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers)

    assert chat_link_service.redeem_link_code("telegram", "2001", first) is None


def test_an_expired_code_is_refused(monkeypatch, auth_headers):
    monkeypatch.setenv("CHAT_LINK_CODE_TTL_SECONDS", "1")
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]

    # Rewriting the stored expiry beats sleeping: the behaviour under test
    # is "the window has closed", not "one second has elapsed".
    import services.chat_link_service as links

    doc_id = links._hash_code(code)
    stored = links._collection(links.CHAT_LINK_CODES_COLLECTION).document(doc_id).get().to_dict()
    stored["expires_at"] = "2020-01-01T00:00:00+00:00"
    links._collection(links.CHAT_LINK_CODES_COLLECTION).document(doc_id).set(stored)

    assert links.redeem_link_code("telegram", "3001", code) is None


def test_a_code_issued_for_one_channel_does_not_link_another(auth_headers):
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]

    assert chat_link_service.redeem_link_code("whatsapp", "whatsapp:+91", code) is None


def test_codes_are_stored_hashed(auth_headers):
    """A dump of the collection must not be a list of working codes."""
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]

    stored_ids = list(fs.db._collections[chat_link_service.CHAT_LINK_CODES_COLLECTION])
    assert code not in stored_ids
    assert chat_link_service._hash_code(code) in stored_ids


def test_a_typed_code_is_forgiven_its_formatting(auth_headers):
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]
    typed = f" {code[:4].lower()}-{code[4:].lower()} "

    assert chat_link_service.redeem_link_code("telegram", "4001", typed) is not None


def test_unlink_stops_the_chat_reading_the_account(monkeypatch, auth_headers):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    secret_header = {webhook_auth.TELEGRAM_SECRET_HEADER: SECRET}
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]
    client.post(TELEGRAM_URL, json=_telegram_update(5001, f"link {code}"), headers=secret_header)

    client.post(TELEGRAM_URL, json=_telegram_update(5001, "unlink"), headers=secret_header)
    after = client.post(TELEGRAM_URL, json=_telegram_update(5001, "status"), headers=secret_header)

    assert "not connected to a Rhythma account" in after.json()["text"]


def test_links_are_listed_for_the_owning_account(monkeypatch, auth_headers):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    code = client.post(
        LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
    ).json()["code"]
    client.post(
        TELEGRAM_URL,
        json=_telegram_update(6001, f"link {code}"),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    listed = client.get(LINKS_URL, headers=auth_headers)

    assert listed.status_code == 200
    assert [link["chatId"] for link in listed.json()["links"]] == ["6001"]


def test_an_unsupported_channel_is_rejected(auth_headers):
    response = client.post(
        LINK_CODE_URL, json={"channel": "signal"}, headers=auth_headers
    )

    assert response.status_code == 400


# ─── Rate limiting ────────────────────────────────────────────────────────


def test_the_webhook_is_rate_limited_per_address(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("RATE_LIMIT_BOT_WEBHOOK_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_BOT_WEBHOOK_IP_WINDOW", "60")
    RateLimitService.clear_all()
    secret_header = {webhook_auth.TELEGRAM_SECRET_HEADER: SECRET}

    statuses = [
        client.post(
            TELEGRAM_URL, json=_telegram_update(7001, "help"), headers=secret_header
        ).status_code
        for _ in range(4)
    ]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


def test_the_rate_limit_applies_before_verification(monkeypatch):
    """An unverified flood is the traffic most worth shedding early.

    Checking a signature is the most expensive thing these routes do, so
    doing it for every request in a flood is exactly backwards.
    """
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("RATE_LIMIT_BOT_WEBHOOK_IP_MAX", "2")
    RateLimitService.clear_all()

    statuses = [
        client.post(TELEGRAM_URL, json=_telegram_update(7002, "help")).status_code
        for _ in range(3)
    ]

    assert statuses[:2] == [401, 401]
    assert statuses[2] == 429


def test_link_codes_are_rate_limited_per_account(monkeypatch, auth_headers):
    monkeypatch.setenv("RATE_LIMIT_BOT_LINK_CODE_ACCOUNT_MAX", "2")
    RateLimitService.clear_all()

    statuses = [
        client.post(
            LINK_CODE_URL, json={"channel": "telegram"}, headers=auth_headers
        ).status_code
        for _ in range(3)
    ]

    assert statuses == [200, 200, 429]


# ─── Payloads that are not messages ───────────────────────────────────────


def test_an_update_with_no_message_is_acknowledged(monkeypatch):
    """Telegram redelivers anything that is not a 2xx.

    Answering an update type we do not handle with an error would have it
    retried forever.
    """
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(
        TELEGRAM_URL,
        json={"update_id": 7, "poll_answer": {"poll_id": "1"}},
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_an_edited_message_is_handled_like_a_new_one(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(
        TELEGRAM_URL,
        json={"update_id": 8, "edited_message": {"chat": {"id": 8001}, "text": "help"}},
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    assert "status" in response.json()["text"]


def test_an_empty_message_gets_a_pointer_to_help(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)

    response = client.post(
        TELEGRAM_URL,
        json=_telegram_update(8002, "   "),
        headers={webhook_auth.TELEGRAM_SECRET_HEADER: SECRET},
    )

    assert "help" in response.json()["text"]


def test_the_twiml_reply_escapes_its_body(monkeypatch):
    """An unescaped ``&`` makes Twilio discard the whole document."""
    monkeypatch.setenv("WEBHOOK_PUBLIC_BASE_URL", "http://testserver")

    from api.bot import _twiml

    body = _twiml("sleep & stress <today>").body.decode("utf-8")

    assert "&amp;" in body and "&lt;today&gt;" in body
    assert "<today>" not in body
