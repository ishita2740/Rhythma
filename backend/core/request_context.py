"""Per-request context that any code in the call stack can read.

The problem this solves: a log line emitted deep inside
``services/scoring_service.py`` has no idea which HTTP request it belongs
to, and threading a ``request_id`` parameter through every service
function would be invasive and easy to forget.

``contextvars`` gives us the same ergonomics as a thread-local, but it is
async-safe: each request handled by the event loop gets its own copy, so
two concurrent requests can never read each other's id. The values are
set once by :class:`core.middleware.RequestContextMiddleware` and read
by the loguru patcher in :mod:`core.logging_config` and by the exception
handlers in :mod:`core.errors`.

Nothing here imports FastAPI or loguru on purpose — this module sits at
the bottom of the dependency graph so it can be imported from anywhere
without creating a cycle.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

# Inbound request ids are echoed back to the client and written into logs,
# so they are untrusted input. Accept only a conservative character set and
# a bounded length; anything else is replaced with a freshly generated id
# rather than rejected, because a malformed trace header should never turn
# a working request into an error.
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[Optional[str]] = ContextVar("rhythma_request_id", default=None)
_request_method: ContextVar[Optional[str]] = ContextVar("rhythma_request_method", default=None)
_request_path: ContextVar[Optional[str]] = ContextVar("rhythma_request_path", default=None)


def new_request_id() -> str:
    """Generate a fresh request id.

    UUID4 hex without dashes: short enough to read out over a support call,
    wide enough that collisions are not a practical concern.
    """
    return uuid.uuid4().hex


def normalize_request_id(candidate: Optional[str]) -> str:
    """Return a safe request id, reusing ``candidate`` when it looks sane.

    Honouring an inbound ``X-Request-ID`` lets a trace started by a mobile
    client (or an upstream proxy) continue through the backend, which is
    the whole point of a correlation id. Honouring it *blindly* would let a
    caller inject newlines into our log output, so it is validated first.
    """
    if candidate and _REQUEST_ID_PATTERN.match(candidate):
        return candidate
    return new_request_id()


def set_request_context(
    request_id: str,
    method: Optional[str] = None,
    path: Optional[str] = None,
) -> "RequestContextTokens":
    """Bind the current request's identity, returning reset tokens."""
    return RequestContextTokens(
        request_id=_request_id.set(request_id),
        method=_request_method.set(method),
        path=_request_path.set(path),
    )


class RequestContextTokens:
    """Handles returned by :func:`set_request_context` for cleanup.

    ContextVars set inside an ASGI application are not automatically
    unwound, and in a test process the same task can serve many requests,
    so the middleware resets them explicitly in a ``finally`` block.
    """

    __slots__ = ("request_id", "method", "path")

    def __init__(
        self,
        request_id: Token,
        method: Token,
        path: Token,
    ) -> None:
        self.request_id = request_id
        self.method = method
        self.path = path

    def reset(self) -> None:
        for var, token in (
            (_request_id, self.request_id),
            (_request_method, self.method),
            (_request_path, self.path),
        ):
            try:
                var.reset(token)
            except ValueError:
                # The token was created in a different context (can happen
                # if a middleware ordering change moves the set/reset pair
                # across a task boundary). Falling back to a plain clear is
                # correct enough and must never mask the real response.
                var.set(None)


def get_request_id() -> Optional[str]:
    """The current request's id, or ``None`` outside a request."""
    return _request_id.get()


def get_request_method() -> Optional[str]:
    return _request_method.get()


def get_request_path() -> Optional[str]:
    return _request_path.get()


def clear_request_context() -> None:
    """Drop all request context. Used by tests."""
    _request_id.set(None)
    _request_method.set(None)
    _request_path.set(None)
