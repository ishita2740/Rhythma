"""Security headers every response carries, and the reasoning behind each.

Issue #405. Before this module the backend sent exactly what uvicorn and
FastAPI put on the wire — ``server``, ``content-type``, ``content-length``,
``date``, plus the ``X-Request-ID`` from :mod:`core.middleware`. Nothing
told the browser not to sniff a content type, not to frame the response,
not to leak the path in a ``Referer``, and not to try plaintext again next
time.

That matters more here than it would on a generic API. Authentication is
HttpOnly cookies (``core/auth_router.py``) and both clients send them
automatically (``withCredentials`` on web, cookie jar on Flutter), so the
browser will attach a live session to any request an attacker can induce
it to make. The cookie flags stop the cookie being *read*; they do nothing
about the response being *framed* or the connection being *downgraded*.
And the data on the other side of that session is menstrual and
reproductive health history, which is not the kind of leak a password
rotation fixes.

Written as raw ASGI rather than ``BaseHTTPMiddleware`` for the same reason
:class:`core.middleware.RequestContextMiddleware` is: ``BaseHTTPMiddleware``
runs the downstream app in a separate anyio task, and the request-context
``ContextVar`` this app relies on is only visible when everything stays in
one task. A plain ASGI callable keeps that property.

Every default is overridable from the environment so that a deploy can
loosen one header — most likely the CSP, for whatever the docs UI needs —
without a code change and without turning the rest off.
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Tuple

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ── Defaults ──────────────────────────────────────────────────────────────
#
# Each of these is the value we want in production. Local development
# overrides come from the environment, not from branching on a debug flag,
# so what runs in CI is the same code path that runs in production.

#: Two years, subdomains included, and preload-eligible. The long max-age is
#: the point of HSTS — a short one leaves a window where a downgrade still
#: works. Note this is only ever *sent* over HTTPS; see ``_wants_hsts``.
DEFAULT_HSTS = "max-age=63072000; includeSubDomains; preload"

#: Blocks the MIME-sniffing path where a JSON error body carrying
#: user-supplied text gets re-interpreted as HTML and executed. The error
#: envelope in ``core/errors.py`` echoes request-derived values, so this is
#: not a hypothetical shape.
DEFAULT_CONTENT_TYPE_OPTIONS = "nosniff"

#: Belt to the CSP's braces. ``frame-ancestors`` is the modern control and
#: is set below, but ``X-Frame-Options`` is still what older browsers and
#: some embedded webviews actually obey — and the Flutter app ships a
#: webview.
DEFAULT_FRAME_OPTIONS = "DENY"

#: Send the origin, never the path. Provider routes put a patient id in the
#: URL (``/api/v1/provider/patients/{patient_id}``); a full-path ``Referer``
#: hands that identifier to any third-party host the browser talks to next.
DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"

#: The API has no use for any of these. Disavowing them costs nothing and
#: shrinks what an injected script could reach.
DEFAULT_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=(), "
    "xr-spatial-tracking=()"
)

#: Default-deny, with the narrowest allowances that keep ``/docs`` and
#: ``/redoc`` working — Swagger UI and ReDoc are served from a CDN and both
#: inject inline styles. If those pages are ever disabled in production this
#: can tighten to ``default-src 'none'`` via the environment.
DEFAULT_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "upgrade-insecure-requests"
)

#: Isolation headers. Cheap, and they close the cross-origin read paths that
#: Spectre-style attacks depend on. ``same-origin-allow-popups`` rather than
#: plain ``same-origin`` so an OAuth-style popup flow stays possible later.
DEFAULT_COOP = "same-origin-allow-popups"
DEFAULT_CORP = "same-origin"

#: ``Server: uvicorn`` advertises the stack for free. Removing it is not a
#: security control on its own — anyone determined will fingerprint the app
#: anyway — but there is no reason to volunteer it.
DEFAULT_STRIP_SERVER_HEADER = True

#: Values that mean "do not send this header at all", so a deploy can drop
#: one header without editing code.
_DISABLED_VALUES = frozenset({"", "off", "none", "disabled", "false", "0"})

#: Header names, lowercased, in the order they are applied. Order has no
#: protocol significance; it makes the emitted set predictable for tests.
HSTS_HEADER = "strict-transport-security"
CONTENT_TYPE_OPTIONS_HEADER = "x-content-type-options"
FRAME_OPTIONS_HEADER = "x-frame-options"
REFERRER_POLICY_HEADER = "referrer-policy"
PERMISSIONS_POLICY_HEADER = "permissions-policy"
CSP_HEADER = "content-security-policy"
COOP_HEADER = "cross-origin-opener-policy"
CORP_HEADER = "cross-origin-resource-policy"

#: Schemes that count as already-secure when deciding whether to send HSTS.
_SECURE_SCHEMES = frozenset({"https", "wss"})

#: Forwarded-proto header names, in precedence order. The app is expected to
#: run behind a proxy that terminates TLS, so ``scope["scheme"]`` is
#: routinely ``http`` even when the user is on ``https``.
_FORWARDED_PROTO_HEADERS: Tuple[str, ...] = (
    "x-forwarded-proto",
    "x-forwarded-protocol",
    "x-forwarded-scheme",
)


def _env(name: str, default: str) -> str:
    """Environment override for one header value.

    An unset variable takes the default. A variable set to one of
    :data:`_DISABLED_VALUES` disables the header. Anything else is used
    verbatim — no parsing, because these are opaque policy strings and a
    validator here would only ever be wrong about a directive it had not
    heard of yet.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip()


def _is_disabled(value: str) -> bool:
    return value.strip().lower() in _DISABLED_VALUES


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _DISABLED_VALUES


def build_header_policy() -> Dict[str, str]:
    """The non-HSTS headers to apply, read from the environment once.

    HSTS is deliberately excluded: whether to send it is a per-request
    decision (it depends on the scheme the request arrived on), so it
    cannot be baked into a static mapping.
    """
    candidates = (
        (CONTENT_TYPE_OPTIONS_HEADER, _env("SECURITY_CONTENT_TYPE_OPTIONS", DEFAULT_CONTENT_TYPE_OPTIONS)),
        (FRAME_OPTIONS_HEADER, _env("SECURITY_FRAME_OPTIONS", DEFAULT_FRAME_OPTIONS)),
        (REFERRER_POLICY_HEADER, _env("SECURITY_REFERRER_POLICY", DEFAULT_REFERRER_POLICY)),
        (PERMISSIONS_POLICY_HEADER, _env("SECURITY_PERMISSIONS_POLICY", DEFAULT_PERMISSIONS_POLICY)),
        (CSP_HEADER, _env("SECURITY_CSP", DEFAULT_CSP)),
        (COOP_HEADER, _env("SECURITY_COOP", DEFAULT_COOP)),
        (CORP_HEADER, _env("SECURITY_CORP", DEFAULT_CORP)),
    )
    return {name: value for name, value in candidates if not _is_disabled(value)}


def resolve_scheme(scope: Scope, headers: Headers) -> str:
    """The scheme the *client* used, not the one that reached this process.

    Behind a TLS-terminating proxy ``scope["scheme"]`` is ``http`` for a
    request the user made over ``https``. Trusting the forwarded header is
    what makes HSTS work in that deployment. It is also why HSTS must never
    be sent unconditionally — see :func:`_wants_hsts`.

    A comma-joined value (``https, http``) comes from a chain of proxies;
    the left-most entry is the one closest to the client.
    """
    for header in _FORWARDED_PROTO_HEADERS:
        forwarded = headers.get(header)
        if forwarded:
            first = forwarded.split(",")[0].strip().lower()
            if first:
                return first
    return str(scope.get("scheme", "http")).lower()


def _wants_hsts(scheme: str) -> bool:
    """Whether this response should carry HSTS.

    Only over a secure scheme, and this is the one rule in the module worth
    stating twice. HSTS on a plaintext response is ignored by a spec-
    compliant browser, but the failure mode when it is *not* ignored is
    severe and entirely self-inflicted: a developer hitting
    ``http://localhost:8000`` would pin ``localhost`` to HTTPS in their
    browser profile, breaking every other local project on that hostname
    until they manually clear the pin. Gating on the scheme means the
    header is simply never present in development, so there is nothing to
    get wrong.
    """
    return scheme in _SECURE_SCHEMES


class SecurityHeadersMiddleware:
    """Attach security headers to every HTTP response.

    Registered in ``main.py`` between :class:`RequestContextMiddleware` and
    ``CORSMiddleware``. Starlette runs the last-registered middleware
    outermost, so that ordering puts CORS on the outside — preflight is
    answered before this runs, which is correct, because an ``OPTIONS``
    preflight response is consumed by the browser's CORS machinery and
    never rendered.

    The headers are applied on ``http.response.start``, which is the one
    message every response passes through: a normal return, a raised
    ``HTTPException``, a validation failure, and the 500 envelope from
    :mod:`core.errors` all emit it. There is no path that produces a
    response body without it, so there is no path that escapes the headers.
    """

    def __init__(
        self,
        app: ASGIApp,
        headers: Optional[Dict[str, str]] = None,
        hsts: Optional[str] = None,
        strip_server_header: Optional[bool] = None,
        exclude_paths: Optional[Iterable[str]] = None,
    ) -> None:
        self.app = app
        # Resolved once at construction. Reading the environment per request
        # would let a test's monkeypatch leak into unrelated requests, and
        # the values cannot change under a running process anyway.
        self.headers = build_header_policy() if headers is None else dict(headers)
        resolved_hsts = _env("SECURITY_HSTS", DEFAULT_HSTS) if hsts is None else hsts
        self.hsts = None if _is_disabled(resolved_hsts) else resolved_hsts
        self.strip_server_header = (
            _env_flag("SECURITY_STRIP_SERVER_HEADER", DEFAULT_STRIP_SERVER_HEADER)
            if strip_server_header is None
            else strip_server_header
        )
        self.exclude_paths = set(exclude_paths or ())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Websocket and lifespan scopes have no response headers to
            # decorate. Passing them straight through also keeps this
            # middleware safe to leave registered if websockets are added.
            await self.app(scope, receive, send)
            return

        if scope.get("path") in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        scheme = resolve_scheme(scope, Headers(scope=scope))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.apply(MutableHeaders(scope=message), scheme=scheme)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def apply(self, headers: MutableHeaders, *, scheme: str) -> None:
        """Write the policy onto one response's headers.

        Existing values win. A route that set its own ``Content-Security-
        Policy`` — an embed endpoint, say — knows something this middleware
        does not, and silently overwriting it would turn a deliberate
        decision into a confusing bug. The blanket policy is a floor, not a
        ceiling.
        """
        for name, value in self.headers.items():
            if name not in headers:
                headers[name] = value

        if self.hsts and _wants_hsts(scheme) and HSTS_HEADER not in headers:
            headers[HSTS_HEADER] = self.hsts

        if self.strip_server_header and "server" in headers:
            del headers["server"]


def applied_header_names(*, secure: bool = True) -> List[str]:
    """Header names this middleware would set. Used by tests and /health."""
    names = list(build_header_policy().keys())
    if secure and not _is_disabled(_env("SECURITY_HSTS", DEFAULT_HSTS)):
        names.append(HSTS_HEADER)
    return names


# ── The one response the middleware cannot reach ──────────────────────────

_fallback_middleware: Optional[SecurityHeadersMiddleware] = None


def _fallback() -> SecurityHeadersMiddleware:
    """A middleware instance used only for its :meth:`apply`, built once."""
    global _fallback_middleware
    if _fallback_middleware is None:
        _fallback_middleware = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]
    return _fallback_middleware


def reset_fallback_cache() -> None:
    """Drop the memoized policy so a test's monkeypatched env is honoured."""
    global _fallback_middleware
    _fallback_middleware = None


def secure_response(response, request=None):
    """Apply the policy to a response built *above* the middleware stack.

    There is exactly one such response, and finding it took a test.
    ``register_exception_handlers`` installs a handler for bare ``Exception``
    (``core/errors.py``), and Starlette does not route that one through
    ``ExceptionMiddleware`` with the others — it hands it to
    ``ServerErrorMiddleware``, which is the outermost layer of the stack,
    above everything registered with ``add_middleware``. So the 500 envelope
    is constructed *outside* this middleware and never passes through its
    ``send`` wrapper.

    Which means that without this function the response that most needs
    ``nosniff`` — a 500, the one most likely to be rendering something
    unexpected and the one an attacker has the most influence over — was the
    only response in the application that did not get it.

    Called from the unhandled-exception handler. The other three handlers
    run inside ``ExceptionMiddleware``, which sits below this middleware,
    and are already covered.
    """
    scheme = "http"
    if request is not None:
        try:
            scheme = resolve_scheme(request.scope, request.headers)
        except Exception:  # pragma: no cover - defensive
            # A header-parsing failure must never turn a 500 into a crash
            # inside the 500 handler.
            scheme = "http"
    _fallback().apply(MutableHeaders(raw=response.raw_headers), scheme=scheme)
    return response


__all__ = [
    "CONTENT_TYPE_OPTIONS_HEADER",
    "COOP_HEADER",
    "CORP_HEADER",
    "CSP_HEADER",
    "DEFAULT_CONTENT_TYPE_OPTIONS",
    "DEFAULT_COOP",
    "DEFAULT_CORP",
    "DEFAULT_CSP",
    "DEFAULT_FRAME_OPTIONS",
    "DEFAULT_HSTS",
    "DEFAULT_PERMISSIONS_POLICY",
    "DEFAULT_REFERRER_POLICY",
    "DEFAULT_STRIP_SERVER_HEADER",
    "FRAME_OPTIONS_HEADER",
    "HSTS_HEADER",
    "PERMISSIONS_POLICY_HEADER",
    "REFERRER_POLICY_HEADER",
    "SecurityHeadersMiddleware",
    "applied_header_names",
    "build_header_policy",
    "reset_fallback_cache",
    "resolve_scheme",
    "secure_response",
]
