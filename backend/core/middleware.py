"""ASGI middleware that gives every request an identity and a log line.

Written as raw ASGI rather than Starlette's ``BaseHTTPMiddleware`` on
purpose. ``BaseHTTPMiddleware`` runs the downstream application in a
separate anyio task, which makes ``ContextVar`` lifetimes subtle — exactly
the thing :mod:`core.request_context` depends on. A plain ASGI callable
runs in the same task as the endpoint, so the request id set here is
visible to every log call underneath it, including the ones inside the
exception handlers.
"""

from __future__ import annotations

import time
from typing import Iterable, Optional, Set

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.request_context import (
    REQUEST_ID_HEADER,
    normalize_request_id,
    set_request_context,
)
from utils.logger import logger

#: Paths that are logged at DEBUG instead of INFO. Kubernetes-style liveness
#: probes and the docs assets would otherwise dominate the log volume while
#: telling an operator nothing.
DEFAULT_QUIET_PATHS: Set[str] = {
    "/",
    "/api/v1/health",
    "/api/v1/health/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}

#: Requests slower than this are logged at WARNING regardless of status, so
#: a slow Firestore query surfaces without anyone having to go looking.
SLOW_REQUEST_MS = 1500.0


class RequestContextMiddleware:
    """Assign a request id, time the request, emit one access log line.

    Responsibilities, in order:

    1. Reuse a well-formed inbound ``X-Request-ID`` (so a trace started on
       the client continues here) or mint a new one.
    2. Bind it — plus method and path — into the request context, where the
       loguru patcher and the error handlers pick it up automatically.
    3. Echo the id back on the response so a user can quote it in a bug
       report and an operator can find the matching log line.
    4. Emit exactly one structured access log line per request, with the
       status and duration, at a level chosen from the outcome.
    """

    def __init__(
        self,
        app: ASGIApp,
        quiet_paths: Optional[Iterable[str]] = None,
        slow_request_ms: float = SLOW_REQUEST_MS,
    ) -> None:
        self.app = app
        self.quiet_paths = set(quiet_paths) if quiet_paths is not None else set(DEFAULT_QUIET_PATHS)
        self.slow_request_ms = slow_request_ms

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Lifespan and websocket scopes have no request identity to
            # assign; pass them through untouched.
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = normalize_request_id(headers.get(REQUEST_ID_HEADER))
        method = scope.get("method", "-")
        path = scope.get("path", "-")

        tokens = set_request_context(request_id, method=method, path=path)
        started = time.perf_counter()
        status_code = 500  # assume the worst until told otherwise

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Let it propagate to Starlette's error handling — which now
            # produces the JSON envelope from core.errors — but log the
            # access line first so the failed request is never missing
            # from the access log.
            self._log_access(
                method=method,
                path=path,
                status_code=500,
                duration_ms=self._elapsed_ms(started),
                query=scope.get("query_string", b""),
                client=scope.get("client"),
                failed=True,
            )
            raise
        else:
            self._log_access(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=self._elapsed_ms(started),
                query=scope.get("query_string", b""),
                client=scope.get("client"),
                failed=False,
            )
        finally:
            tokens.reset()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def _log_access(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        query: bytes,
        client,
        failed: bool,
    ) -> None:
        bound = logger.bind(
            http_method=method,
            http_path=path,
            http_status=status_code,
            duration_ms=duration_ms,
            # The query string is recorded but never the parsed values:
            # `?user_id=...` is useful, and anything sensitive is a design
            # error we would want visible in the log rather than hidden.
            has_query=bool(query),
            client_ip=client[0] if client else None,
        )

        message = "{} {} → {} ({}ms)".format(method, path, status_code, duration_ms)

        if failed or status_code >= 500:
            bound.error(message)
        elif status_code >= 400:
            bound.warning(message)
        elif duration_ms >= self.slow_request_ms:
            bound.warning("Slow request: " + message)
        elif path in self.quiet_paths:
            bound.debug(message)
        else:
            bound.info(message)


__all__ = ["DEFAULT_QUIET_PATHS", "SLOW_REQUEST_MS", "RequestContextMiddleware"]
