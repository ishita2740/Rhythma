"""Named rate-limit policies for the API's unauthenticated entry points.

Before this module the only rate-limited auth route was
``POST /auth/firebase-login``, which called ``RateLimitService`` inline with
magic numbers. Every other route in ``core/auth_router.py`` — including the
email/password login the web app actually uses — accepted unlimited attempts.

The pieces here are deliberately small:

``RateLimitPolicy``
    A named bucket with its own limit and window, both overridable from the
    environment so a deployment can tighten them without a code change (the
    same pattern ``ASSISTANT_RATE_LIMIT`` / ``ASSISTANT_RATE_WINDOW``
    already use). One policy per *thing being protected*, not one global
    number: a password guess and a password-reset email have very different
    costs, and giving them a shared budget means whichever is noisier
    starves the other.

``enforce`` / ``clear``
    The only two operations a route needs. ``enforce`` raises the 429 —
    routes never build that response themselves, so ``Retry-After`` cannot
    be forgotten on one route and present on another.

Identifiers are hashed before they reach Firestore. A key like
``login_account:sana@example.com`` would put a plaintext email address in a
document id, in a collection nothing else treats as personal data, retained
for as long as the document lives. The hash is as usable as a bucket key and
carries none of that.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status

from services.rate_limit_service import RateLimitService


@dataclass(frozen=True)
class RateLimitPolicy:
    """One named bucket: how many attempts, over how long, and what to say.

    ``limit`` and ``window_seconds`` are read from the environment on every
    access rather than captured at import. That costs an ``os.getenv`` per
    request — nothing next to a Firestore round trip — and buys two things:
    a deployment can change a limit without a restart, and tests can adjust
    one policy with ``monkeypatch.setenv`` instead of reaching into module
    state.
    """

    #: Short identifier. Used as the environment-variable stem and as the
    #: prefix of the Firestore document id, so buckets stay separate.
    name: str
    default_limit: int
    default_window: int
    #: Shown to the user. ``{seconds}`` is filled with the real wait.
    message: str

    @property
    def env_prefix(self) -> str:
        return f"RATE_LIMIT_{self.name.upper()}"

    def _env_int(self, suffix: str, fallback: int) -> int:
        raw = os.getenv(f"{self.env_prefix}_{suffix}")
        if raw is None:
            return fallback
        try:
            value = int(raw)
        except ValueError:
            return fallback
        # A zero or negative limit would disable the protection entirely,
        # which is much more likely to be a typo in a deploy config than a
        # deliberate choice. Fall back rather than silently open the gate.
        return value if value > 0 else fallback

    @property
    def limit(self) -> int:
        return self._env_int("MAX", self.default_limit)

    @property
    def window_seconds(self) -> int:
        return self._env_int("WINDOW", self.default_window)

    def key_for(self, identifier: str) -> str:
        """Firestore document id for one client under this policy."""
        digest = hashlib.sha256(identifier.strip().lower().encode("utf-8"))
        return f"{self.name}:{digest.hexdigest()[:32]}"


# ─── Policies ─────────────────────────────────────────────────────────────
#
# Login is limited on two independent keys. Per-IP alone is defeated by
# spreading guesses for one account across a botnet; per-account alone is
# defeated by walking the user table from a single address, one guess each.
# Neither key subsumes the other, so both are checked.

LOGIN_IP = RateLimitPolicy(
    name="login_ip",
    default_limit=10,
    default_window=900,
    message="Too many login attempts from this device. Please try again in {seconds} seconds.",
)

LOGIN_ACCOUNT = RateLimitPolicy(
    name="login_account",
    default_limit=5,
    default_window=900,
    message="Too many failed login attempts for this account. Please try again in {seconds} seconds.",
)

FIREBASE_LOGIN_IP = RateLimitPolicy(
    name="firebase_login_ip",
    # 10 per 5 minutes — the values this route already used inline, kept
    # deliberately so migrating it to a policy is not a behaviour change.
    default_limit=10,
    default_window=300,
    message="Too many login attempts. Please wait {seconds} seconds.",
)

REGISTER_IP = RateLimitPolicy(
    name="register_ip",
    default_limit=5,
    default_window=3600,
    message="Too many accounts created from this device. Please try again in {seconds} seconds.",
)

# Provider registration is checked against REGISTER_IP *as well as* this
# policy, so the two routes share one ceiling on account creation from a
# single address rather than each handing out its own budget. This second,
# tighter bucket exists because the two routes are not equally risky: a
# provider account is the one that can read other people's cycle logs once
# a patient consents, and a genuine clinic signing its staff up does not
# need to create more than a couple of accounts an hour from one address.
PROVIDER_REGISTER_IP = RateLimitPolicy(
    name="provider_register_ip",
    default_limit=3,
    default_window=3600,
    message=(
        "Too many provider accounts created from this device. "
        "Please try again in {seconds} seconds."
    ),
)

# Requesting a reset link mints a token and (once email delivery is wired
# up) sends mail to an address the requester chose, not one they proved they
# own. Limited per account so it cannot be used to flood one inbox, and per
# IP so it cannot be used to flood many.
PASSWORD_RESET_REQUEST_ACCOUNT = RateLimitPolicy(
    name="password_reset_request_account",
    default_limit=3,
    default_window=3600,
    message="A reset link was already requested for this account. Please try again in {seconds} seconds.",
)

PASSWORD_RESET_REQUEST_IP = RateLimitPolicy(
    name="password_reset_request_ip",
    default_limit=10,
    default_window=3600,
    message="Too many password reset requests. Please try again in {seconds} seconds.",
)

# Submitting a reset or verification token is a guess at a secret. Tighter
# than the request side: there is no legitimate reason to submit five wrong
# tokens in an hour.
PASSWORD_RESET_CONFIRM_IP = RateLimitPolicy(
    name="password_reset_confirm_ip",
    default_limit=5,
    default_window=3600,
    message="Too many password reset attempts. Please try again in {seconds} seconds.",
)

EMAIL_VERIFY_IP = RateLimitPolicy(
    name="email_verify_ip",
    default_limit=10,
    default_window=3600,
    message="Too many verification attempts. Please try again in {seconds} seconds.",
)

VERIFICATION_RESEND_ACCOUNT = RateLimitPolicy(
    name="verification_resend_account",
    default_limit=3,
    default_window=3600,
    message="A verification email was already sent. Please try again in {seconds} seconds.",
)

# The chat webhooks are the only routes in the API a stranger can reach
# without credentials of any kind, and each delivery costs a signature
# check and at least one Firestore read. Generous enough that a busy bot
# is never throttled — Telegram delivers one update per message, and a
# single deployment's traffic arrives from a handful of Telegram and
# Twilio egress addresses — and low enough that an unauthenticated flood
# stops being free.
BOT_WEBHOOK_IP = RateLimitPolicy(
    name="bot_webhook_ip",
    default_limit=60,
    default_window=60,
    message="Too many webhook deliveries. Please retry in {seconds} seconds.",
)

# A link code is a bearer credential for one account, so the budget is
# per account rather than per address: several users behind one clinic's
# NAT must not share a ceiling. Five an hour is well past what connecting
# a phone takes, and far short of what walking the code space would need.
BOT_LINK_CODE_ACCOUNT = RateLimitPolicy(
    name="bot_link_code_account",
    default_limit=5,
    default_window=3600,
    message=(
        "Too many connection codes requested. Please try again in "
        "{seconds} seconds."
    ),
)

# Refresh is called by a legitimate client roughly once per access-token
# lifetime, but a client with a clock problem or a retry loop can call it
# far more often, so the ceiling is generous rather than tight.
TOKEN_REFRESH_IP = RateLimitPolicy(
    name="token_refresh_ip",
    default_limit=30,
    default_window=300,
    message="Too many token refresh attempts. Please try again in {seconds} seconds.",
)


# ─── Operations ───────────────────────────────────────────────────────────

def client_ip(request: Optional[Request]) -> str:
    """Best-effort client address, honouring ``X-Forwarded-For``.

    Returns ``"unknown"`` when there is no address to read — which buckets
    every such caller together. That is the safe direction: an attacker who
    manages to hide their address gets a *shared*, quickly-exhausted budget
    rather than an exemption.
    """
    if request is None:
        return "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce(policy: RateLimitPolicy, identifier: str) -> None:
    """Record one attempt against ``policy``; raise 429 if over the limit.

    ``Retry-After`` carries the real number of seconds until the oldest
    attempt in the window expires, not a fixed guess, so a client that
    honours the header waits exactly as long as it has to.
    """
    remaining = RateLimitService.is_rate_limited(
        key=policy.key_for(identifier),
        limit=policy.limit,
        window_seconds=policy.window_seconds,
    )
    if remaining is None:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=policy.message.format(seconds=remaining),
        headers={"Retry-After": str(remaining)},
    )


def clear(policy: RateLimitPolicy, identifier: str) -> None:
    """Drop the recorded attempts for one client under one policy.

    Called after a *successful* login so a user who mistypes her password
    three times and then gets it right is not left one attempt away from a
    lockout for the next quarter of an hour. Only the per-account bucket is
    cleared on success; the per-IP bucket is not, because a machine that
    just succeeded on one account has told us nothing about the dozens of
    other accounts it may be working through.
    """
    RateLimitService.reset(policy.key_for(identifier))
