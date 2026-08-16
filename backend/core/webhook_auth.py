"""Proving that a webhook delivery came from the platform it claims to.

Every other route in this API knows who is calling it because a signed
cookie or a bearer token says so. A webhook has neither: the caller is
Telegram's or Twilio's infrastructure, not a person, and the only thing
that distinguishes a genuine delivery from a stranger with ``curl`` is a
shared secret carried in a header.

``api/bot.py`` checked nothing at all, so both webhooks were public
endpoints that anyone could drive. This module is the check, kept apart
from the routes for two reasons:

* the two platforms authenticate completely differently — Telegram sends
  back a secret you registered with it, Twilio signs the request — and
  mixing both schemes into route bodies is how one of them ends up subtly
  wrong;
* every comparison here has to be constant-time, and that is easier to
  guarantee in one small module than at each call site.

**Configuration.** Verification for a channel is enabled by setting its
secret:

``TELEGRAM_WEBHOOK_SECRET``
    The ``secret_token`` passed to Telegram's ``setWebhook``. Telegram
    echoes it back in ``X-Telegram-Bot-Api-Secret-Token`` on every
    delivery.

``TWILIO_AUTH_TOKEN``
    Already required for sending SMS. Twilio signs each webhook with it,
    so no new secret is needed.

``WEBHOOK_PUBLIC_BASE_URL``
    Optional. Twilio signs the *public* URL it was configured with, which
    behind a proxy or a tunnel is not the URL the app sees. Set this to
    the externally visible origin (``https://api.rhythma.app``) when the
    two differ.

**When a secret is unset**, that channel's verification is skipped and a
warning is logged once per process. That is deliberate: refusing to start
would make a local ``uvicorn`` run impossible, and hard-failing every
delivery in an environment that has never configured the bot would turn
a missing feature into a paging incident. What it must not do is pass
silently, hence the warning and hence
:func:`verification_configured`, which ``/health/ready`` and the startup
report can use to say the deployment is running an unverified webhook.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Mapping, Optional
from urllib.parse import urlsplit, urlunsplit

from fastapi import Request

from utils.logger import logger

#: Header Telegram echoes the registered ``secret_token`` back in.
TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

#: Header Twilio puts its request signature in.
TWILIO_SIGNATURE_HEADER = "X-Twilio-Signature"

CHANNEL_TELEGRAM = "telegram"
CHANNEL_WHATSAPP = "whatsapp"

#: Channels whose missing-secret warning has already been logged. A
#: warning per delivery would bury the log under a message that says the
#: same thing every time.
_warned: set = set()


class WebhookVerificationError(Exception):
    """Raised when a delivery cannot be attributed to the platform.

    Carries a reason for the log. It is deliberately *not* carried into
    the HTTP response: telling an unauthenticated caller which half of
    the check it failed is free reconnaissance, and there is nothing a
    genuine platform delivery would do with the detail.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def telegram_secret() -> Optional[str]:
    value = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    return value or None


def twilio_auth_token() -> Optional[str]:
    value = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    return value or None


def verification_configured(channel: str) -> bool:
    """Whether ``channel`` can currently authenticate a delivery."""
    if channel == CHANNEL_TELEGRAM:
        return telegram_secret() is not None
    if channel == CHANNEL_WHATSAPP:
        return twilio_auth_token() is not None
    return False


def _warn_unverified(channel: str) -> None:
    if channel in _warned:
        return
    _warned.add(channel)
    logger.bind(channel=channel).warning(
        "Webhook signature verification is disabled — no secret is "
        "configured for this channel. Anyone who can reach this URL can "
        "post to it."
    )


def reset_warning_state() -> None:
    """Forget which channels have been warned about.

    Only for tests, which flip the environment between cases and would
    otherwise see the warning suppressed by an earlier test's call.
    """
    _warned.clear()


# ─── Telegram ─────────────────────────────────────────────────────────────


def verify_telegram(request: Request) -> None:
    """Check the secret token Telegram echoes back.

    Telegram's scheme is the simpler of the two: whatever string you pass
    as ``secret_token`` to ``setWebhook`` arrives in a header on every
    delivery. There is no signature over the body, so this proves only
    that the caller knows the secret — which is exactly as much as
    Telegram itself proves, and the reason the secret must not be reused
    anywhere else.

    Raises :class:`WebhookVerificationError` on a missing or wrong token.
    """
    expected = telegram_secret()
    if expected is None:
        _warn_unverified(CHANNEL_TELEGRAM)
        return

    provided = request.headers.get(TELEGRAM_SECRET_HEADER)
    if not provided:
        raise WebhookVerificationError("missing secret token header")

    # compare_digest rather than ==. A plain comparison returns as soon as
    # two bytes differ, and the time it took is a measurement of how much
    # of the prefix was right.
    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("secret token mismatch")


# ─── Twilio ───────────────────────────────────────────────────────────────


def _public_url(request: Request) -> str:
    """The URL Twilio signed, which is not always the one we received.

    Twilio computes its signature over the URL configured in its console.
    A deployment behind a proxy, a tunnel or a path-rewriting ingress sees
    a different scheme, host or port, and the signature then never matches
    no matter how correct the rest of the implementation is. Setting
    ``WEBHOOK_PUBLIC_BASE_URL`` replaces the parts that changed while
    keeping the path and query, which are the parts Twilio and the app
    always agree on.
    """
    received = str(request.url)
    base = (os.getenv("WEBHOOK_PUBLIC_BASE_URL") or "").strip()
    if not base:
        return received

    parsed_base = urlsplit(base)
    parsed_received = urlsplit(received)
    return urlunsplit(
        (
            parsed_base.scheme or parsed_received.scheme,
            parsed_base.netloc or parsed_received.netloc,
            parsed_received.path,
            parsed_received.query,
            "",
        )
    )


def twilio_signature(auth_token: str, url: str, params: Mapping[str, str]) -> str:
    """Twilio's request signature for ``url`` and ``params``.

    The algorithm, from Twilio's security documentation: take the full
    URL, append each POST parameter as ``name`` immediately followed by
    ``value`` in order of the parameter names sorted lexicographically,
    then HMAC-SHA1 the result with the account's auth token and
    base64-encode it.

    Exposed rather than inlined because it is the only part of this module
    a test can assert against directly — a test that signs with the same
    function it is testing proves nothing, so the test suite reimplements
    the concatenation and checks the two agree.
    """
    payload = url
    for name in sorted(params):
        payload += name + (params[name] or "")

    digest = hmac.new(
        auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_twilio(request: Request, params: Mapping[str, str]) -> None:
    """Check Twilio's HMAC over the request URL and form body.

    ``params`` must be the parsed form body, not the raw bytes: Twilio
    signs the decoded name/value pairs, so a body re-serialised in a
    different order would produce a different signature for the same
    request.

    Raises :class:`WebhookVerificationError` when the signature is absent
    or does not match.
    """
    auth_token = twilio_auth_token()
    if auth_token is None:
        _warn_unverified(CHANNEL_WHATSAPP)
        return

    provided = request.headers.get(TWILIO_SIGNATURE_HEADER)
    if not provided:
        raise WebhookVerificationError("missing signature header")

    expected = twilio_signature(auth_token, _public_url(request), params)
    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("signature mismatch")


__all__ = [
    "CHANNEL_TELEGRAM",
    "CHANNEL_WHATSAPP",
    "TELEGRAM_SECRET_HEADER",
    "TWILIO_SIGNATURE_HEADER",
    "WebhookVerificationError",
    "reset_warning_state",
    "telegram_secret",
    "twilio_auth_token",
    "twilio_signature",
    "verification_configured",
    "verify_telegram",
    "verify_twilio",
]
