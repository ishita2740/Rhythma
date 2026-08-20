"""Which address a request actually came from (issue #498).

Every per-IP rate limit in ``core/rate_limits.py`` is keyed on one string,
and that string used to be whatever the caller put in ``X-Forwarded-For``:

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first

``X-Forwarded-For`` is a request header. Anyone can send it, nothing here
checked that the request had passed through a proxy at all, and the entry
taken was the *left-most* — the one hop in the list that no proxy vouches
for. Since ``policy.key_for()`` hashes the identifier into a document id, a
different header value is a different bucket with a full fresh budget, so
incrementing a header defeated the limit:

    POST /auth/reset-password  X-Forwarded-For: 1.2.3.4   → 1/5 used
    POST /auth/reset-password  X-Forwarded-For: 1.2.3.5   → 1/5 used

``PASSWORD_RESET_CONFIRM_IP``, ``EMAIL_VERIFY_IP``, ``REGISTER_IP``,
``PROVIDER_REGISTER_IP``, ``FIREBASE_LOGIN_IP``, ``TOKEN_REFRESH_IP`` and
``BOT_WEBHOOK_IP`` have no second key, so for those routes that is not a
weakened limit but no limit at all. The reset-token one is the sharp end:
five guesses an hour at a password-reset token becomes unlimited guesses.

**The header still has to be read.** Ignoring it is not the fix. The
intended deployment sits behind a platform load balancer, where
``request.client.host`` is the balancer and every real user's address is
only in the header — bucketing on the socket would put the entire world in
one bucket, which fails much louder and just as wrongly.

The missing idea is that the header is trustworthy exactly as far back as
the chain of proxies *you operate*, and the old code had no notion of
where that chain ended. So:

**A deployment declares its proxies.** ``TRUSTED_PROXY_IPS`` lists the
addresses or CIDR blocks requests legitimately arrive from. Unset means
"nothing is in front of this process", and then the header is not read at
all — which is the right default for someone running ``uvicorn`` directly,
and the one that fails safe if the variable is forgotten.

**The address taken is the right-most one that is not ours.** A proxy
appends its view of its peer to the right of the list, so reading from the
right is reading the part of the header that was written by software we
control, and the first entry that is not one of our own proxies is the
last hop nobody downstream could have forged. Everything to its left is
client-supplied and is discarded.

**``*`` is allowed, and it means something narrower than it looks.** Some
platforms — Cloud Run, Render, a Vercel rewrite — do not publish a stable
set of egress addresses for their own balancer, so there is nothing to put
in ``TRUSTED_PROXY_IPS``. ``*`` accepts any peer as a proxy and leans
entirely on ``TRUSTED_PROXY_HOPS`` to say how many entries at the right of
the list that platform appends. That is weaker than naming addresses and
strictly stronger than trusting the left-most entry, because the attacker
can no longer choose which entry is read.

Nothing here decides policy. It answers one question — who is calling —
and ``rate_limits.client_ip()`` is a thin wrapper over it so no route has
to know any of this.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Iterable, List, Optional, Sequence

# ─── Configuration ────────────────────────────────────────────────────────

#: Comma-separated addresses or CIDR blocks that requests legitimately
#: arrive from. ``*`` accepts any peer. Empty or unset disables forwarded
#: headers entirely.
TRUSTED_PROXY_IPS_ENV = "TRUSTED_PROXY_IPS"

#: How many entries at the *right* of ``X-Forwarded-For`` were appended by
#: infrastructure we run and should therefore be skipped over. Zero — the
#: default — means the right-most entry is already the client, which is
#: what a single reverse proxy in front of the app produces.
TRUSTED_PROXY_HOPS_ENV = "TRUSTED_PROXY_HOPS"

#: Wildcard value for :data:`TRUSTED_PROXY_IPS_ENV`.
TRUST_ANY_PEER = "*"

#: Returned when there is no address to read. Deliberately a value, not
#: ``None``: unattributable callers share one quickly-exhausted bucket
#: rather than escaping the limit, and a caller that manages to hide its
#: address should not be rewarded for it.
UNKNOWN_ADDRESS = "unknown"

#: ``X-Forwarded-For`` is a list a client can make as long as it likes, and
#: a thousand comma-separated entries is a valid HTTP request. Parsing is
#: cheap but not free, and the entries past a realistic proxy depth cannot
#: influence the answer anyway, so the tail is dropped rather than walked.
MAX_FORWARDED_ENTRIES = 32

#: One IPv6 address is 45 characters at its longest. Anything past this in
#: a single entry is not an address, so it is refused before parsing.
MAX_ADDRESS_CHARS = 64


def _env(name: str) -> str:
    """Read configuration on every call rather than at import.

    Matches how ``RateLimitPolicy`` reads its own limits, and for the same
    reasons: a deployment can correct a misconfigured proxy list without a
    restart, and a test can set one with ``monkeypatch.setenv`` instead of
    reaching into module state.
    """
    return (os.getenv(name) or "").strip()


def trusted_proxy_spec() -> List[str]:
    """The configured proxy entries, as written.

    Returned unparsed so the caller can distinguish "not configured" from
    "configured with something unparseable" — the second is a deploy
    mistake worth surfacing, the first is an ordinary local run.
    """
    raw = _env(TRUSTED_PROXY_IPS_ENV)
    if not raw:
        return []
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def trusted_proxy_hops() -> int:
    """How many right-hand entries belong to infrastructure we run.

    A negative or unparseable value is a typo in a deploy config rather
    than a policy, and the direction that fails safe is zero — skipping
    fewer entries can only move the answer further right, towards the part
    of the header a client cannot write.
    """
    raw = _env(TRUSTED_PROXY_HOPS_ENV)
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if value > 0 else 0


def _parse_networks(entries: Sequence[str]) -> List[ipaddress._BaseNetwork]:
    """Turn the configured entries into networks, dropping what will not parse.

    A bare address becomes a single-host network, so membership is one
    operation regardless of which form was configured. An entry that is
    neither is skipped rather than raising: one typo in a comma-separated
    list must not take the whole rate limiter down, and the effect of
    skipping is that the peer it was meant to cover stops being trusted —
    which is the safe direction.
    """
    networks: List[ipaddress._BaseNetwork] = []
    for entry in entries:
        if entry == TRUST_ANY_PEER:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return networks


def _as_ip(value: str) -> Optional[ipaddress._BaseAddress]:
    """Parse one address, tolerating the shapes proxies actually emit.

    Two of those are worth handling rather than rejecting:

    * a port suffix — ``203.0.113.5:41234`` — which some proxies append
      even though the header is specified as addresses only;
    * an IPv6 address in brackets, with or without a port, which is how it
      has to be written whenever a port might follow.

    An IPv4-mapped IPv6 address (``::ffff:203.0.113.5``) is folded to its
    IPv4 form so the same client is one bucket rather than two.
    """
    text = (value or "").strip()
    if not text or len(text) > MAX_ADDRESS_CHARS:
        return None

    if text.startswith("["):
        closing = text.find("]")
        if closing == -1:
            return None
        text = text[1:closing]
    elif text.count(":") == 1:
        # Exactly one colon is a v4 address with a port. More than one is
        # a bare v6 address, where a colon means something else entirely.
        text = text.split(":", 1)[0]

    try:
        parsed = ipaddress.ip_address(text)
    except ValueError:
        return None

    mapped = getattr(parsed, "ipv4_mapped", None)
    return mapped or parsed


def _is_trusted(address: Optional[ipaddress._BaseAddress], networks: Iterable) -> bool:
    if address is None:
        return False
    return any(address in network for network in networks)


def forwarded_chain(header_value: Optional[str]) -> List[str]:
    """The ``X-Forwarded-For`` entries that are actually addresses.

    Left to right, which is client-first — the order the header is defined
    in and the order the resolution below walks backwards through.
    Anything that does not parse as an address is dropped rather than
    carried along as a string, because a bucket key that is not an address
    is a bucket key an attacker chose.
    """
    if not header_value:
        return []

    parsed: List[str] = []
    for entry in header_value.split(",")[:MAX_FORWARDED_ENTRIES]:
        address = _as_ip(entry)
        if address is not None:
            parsed.append(str(address))
    return parsed


# ─── Resolution ───────────────────────────────────────────────────────────


def resolve_client_address(
    peer: Optional[str],
    forwarded_header: Optional[str] = None,
) -> str:
    """The address to attribute a request to.

    ``peer`` is the socket address the request actually arrived from — the
    one value in this function nobody can forge. Everything else is a claim
    that has to earn its way past it.

    The order is the whole of the security argument:

    1. No peer at all is :data:`UNKNOWN_ADDRESS`. There is nothing to
       verify a header against, so the header is not read.
    2. No configured proxies means nothing is in front of this process, so
       a forwarded header is a fabrication and the peer is the answer.
    3. A peer that is not one of the configured proxies connected to us
       directly, whatever it claims about hops before it. Its own address
       is the answer.
    4. Only then is the header read, right to left, skipping our own
       proxies and the configured hop count. The first entry left standing
       is the last hop nobody downstream could have written.
    5. A header that is entirely our own proxies, or empty, falls back to
       the peer rather than to ``unknown`` — an internal address is a
       worse bucket key than a good one and a better one than none.
    """
    if not peer:
        return UNKNOWN_ADDRESS

    spec = trusted_proxy_spec()
    if not spec:
        return peer

    trust_any = TRUST_ANY_PEER in spec
    networks = _parse_networks(spec)

    peer_address = _as_ip(peer)
    if not trust_any and not _is_trusted(peer_address, networks):
        # A direct connection from someone who is not a proxy we run. The
        # header, if there is one, is theirs to write and worth nothing.
        return peer

    chain = forwarded_chain(forwarded_header)
    if not chain:
        return peer

    remaining_hops = trusted_proxy_hops()
    for candidate in reversed(chain):
        if remaining_hops > 0:
            remaining_hops -= 1
            continue
        if _is_trusted(_as_ip(candidate), networks):
            # Another of our own proxies. Keep walking left; the client is
            # further out than this.
            continue
        return candidate

    return peer


def client_address(request: Optional[object]) -> str:
    """:func:`resolve_client_address` for a Starlette/FastAPI request.

    Split from the resolution itself so the interesting part is a pure
    function of two strings and can be tested without constructing a
    request — the same reason ``web/src/api/retry.ts`` keeps its policy
    decisions out of the axios instance.

    Attribute access is defensive because this is reached from a rate
    limiter: a request object shaped differently than expected must
    degrade to :data:`UNKNOWN_ADDRESS` rather than raise inside
    ``enforce()`` and turn a rate-limit check into a 500.
    """
    if request is None:
        return UNKNOWN_ADDRESS

    try:
        headers = getattr(request, "headers", None)
        forwarded = headers.get("X-Forwarded-For") if headers is not None else None
    except Exception:  # pragma: no cover - defensive
        forwarded = None

    try:
        client = getattr(request, "client", None)
        peer = getattr(client, "host", None) if client is not None else None
    except Exception:  # pragma: no cover - defensive
        peer = None

    return resolve_client_address(peer, forwarded)


__all__ = [
    "MAX_ADDRESS_CHARS",
    "MAX_FORWARDED_ENTRIES",
    "TRUSTED_PROXY_HOPS_ENV",
    "TRUSTED_PROXY_IPS_ENV",
    "TRUST_ANY_PEER",
    "UNKNOWN_ADDRESS",
    "client_address",
    "forwarded_chain",
    "resolve_client_address",
    "trusted_proxy_hops",
    "trusted_proxy_spec",
]
