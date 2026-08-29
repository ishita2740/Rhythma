"""One error envelope for every failure the API can produce.

Before this module a client could receive three unrelated shapes:

===================================  ===========================================
``HTTPException``                    ``{"detail": "Not authorized"}``
Pydantic validation (422)            ``{"detail": [{"loc": ..., "msg": ...}]}``
Unhandled exception (500)            ``Internal Server Error`` (**plain text**)
===================================  ===========================================

Every client had to special-case all three, and none of them carried a
machine-readable code, so clients string-matched on the English ``detail``
text — which is why error messages are the one part of Rhythma that is not
localizable.

The handlers here normalize all of that into::

    {
      "detail": <unchanged, for backwards compatibility>,
      "error": {
        "code": "cycle_log_not_found",
        "message": "Cycle log not found",
        "request_id": "9f1c...",
        "details": null
      }
    }

``detail`` is deliberately preserved exactly as FastAPI produced it so
existing clients and the existing test-suite keep working; ``error`` is the
shape new code should read. ``error.code`` is stable and safe to branch on
and to use as a localization key.

The 500 handler additionally guarantees that ``str(exc)`` never reaches the
client: the real exception is logged with a traceback and correlated by
``request_id``, while the response body carries only a generic message.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.logging_config import redact
from core.request_context import REQUEST_ID_HEADER, get_request_id
from core.security_headers import secure_response
from utils.logger import logger

# ─── Application errors ───────────────────────────────────────────────────


class AppError(Exception):
    """Base class for errors raised deliberately by application code.

    Carries a stable ``code`` alongside the HTTP status so clients can
    branch on the code instead of on an English string. Raise these from
    services; the handler below turns them into the standard envelope.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Something went wrong. Please try again."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        details: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        self.headers = headers or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "The request could not be processed."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Could not validate credentials"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Not authorized"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "That resource already exists."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class UpstreamServiceError(AppError):
    """A dependency (Firestore, Gemini, Twilio) failed.

    Distinguished from :class:`InternalError` because it is the class of
    failure a client can usefully retry, and the class an operator should
    look at a dependency dashboard for rather than at our own code.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "upstream_unavailable"
    message = "A required service is temporarily unavailable. Please try again."


class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "Something went wrong. Please try again."


# ─── Envelope construction ────────────────────────────────────────────────

#: Fallback codes for ``HTTPException``s raised by code that predates
#: :class:`AppError`. Keeps the envelope's ``code`` meaningful without
#: requiring every existing ``raise HTTPException(...)`` to be rewritten.
_STATUS_CODE_NAMES: Dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    # Referenced numerically: Starlette has deprecated the
    # HTTP_413_REQUEST_ENTITY_TOO_LARGE / HTTP_422_UNPROCESSABLE_ENTITY
    # spellings in favour of ..._CONTENT_TOO_LARGE / ..._UNPROCESSABLE_CONTENT,
    # and the numbers work on both the pinned and the newer versions.
    413: "payload_too_large",
    422: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_501_NOT_IMPLEMENTED: "not_implemented",
    status.HTTP_503_SERVICE_UNAVAILABLE: "upstream_unavailable",
}

GENERIC_INTERNAL_MESSAGE = "Something went wrong. Please try again."

#: Starlette renamed ``HTTP_422_UNPROCESSABLE_ENTITY`` to
#: ``HTTP_422_UNPROCESSABLE_CONTENT`` and deprecated the old name, but the
#: pinned FastAPI in requirements.txt still ships the old one. Referring to
#: the number keeps this working on both without emitting a deprecation
#: warning on every validation error.
HTTP_422_UNPROCESSABLE = 422


def code_for_status(status_code: int) -> str:
    """Best-effort machine code for a status raised without an explicit one."""
    if status_code in _STATUS_CODE_NAMES:
        return _STATUS_CODE_NAMES[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    return "server_error"


def build_error_body(
    *,
    code: str,
    message: str,
    detail: Any,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    """Assemble the response body shared by every error handler."""
    return {
        # Preserved verbatim so pre-existing clients (and tests) that read
        # `detail` keep working. New code should read `error`.
        "detail": detail,
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
            "details": details,
        },
    }


def _response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    merged = dict(headers or {})
    request_id = get_request_id()
    if request_id:
        # The middleware normally stamps this, but a 500 raised past the
        # middleware is served by Starlette's outermost error handler, so
        # the header is set here too rather than being lost exactly when
        # it is most needed.
        merged.setdefault(REQUEST_ID_HEADER, request_id)
    return JSONResponse(status_code=status_code, content=body, headers=merged)


# ─── Handlers ─────────────────────────────────────────────────────────────


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle errors raised deliberately by application code."""
    log = logger.bind(
        error_code=exc.code,
        status_code=exc.status_code,
        path=request.url.path,
    )
    if exc.status_code >= 500:
        log.error("Application error: {}", exc.message)
    else:
        log.info("Client error: {}", exc.message)

    return _response(
        exc.status_code,
        build_error_body(
            code=exc.code,
            message=exc.message,
            detail=exc.message,
            details=redact(exc.details) if exc.details is not None else None,
        ),
        headers=exc.headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Wrap the many existing ``raise HTTPException(...)`` call sites."""
    detail = exc.detail
    message = detail if isinstance(detail, str) else code_for_status(exc.status_code)

    logger.bind(
        status_code=exc.status_code,
        path=request.url.path,
    ).info("HTTP error: {}", message)

    return _response(
        exc.status_code,
        build_error_body(
            code=code_for_status(exc.status_code),
            message=message,
            detail=detail,
        ),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422s, with the field errors reduced to a client-friendly list.

    FastAPI's raw ``errors()`` output includes an ``input`` key echoing the
    submitted value — which for this API means echoing cycle notes and
    symptoms back inside an error body. Only ``field``/``message``/``type``
    are kept.
    """
    field_errors = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part != "body"]
        field_errors.append(
            {
                "field": ".".join(location) or "body",
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )

    logger.bind(
        status_code=HTTP_422_UNPROCESSABLE,
        path=request.url.path,
        invalid_fields=[fe["field"] for fe in field_errors],
    ).info("Request validation failed")

    return _response(
        HTTP_422_UNPROCESSABLE,
        build_error_body(
            code="validation_error",
            message="Some of the submitted values are not valid.",
            # Keep FastAPI's own structure here: existing tests and clients
            # inspect `detail` for field names, and jsonable_encoder handles
            # the non-JSON-native values FastAPI can put in it.
            detail=_jsonable_errors(exc),
            details=field_errors,
        ),
    )


def _jsonable_errors(exc: RequestValidationError) -> Any:
    """FastAPI validation errors can contain non-serializable values.

    ``ValueError`` instances show up under ``ctx`` for custom validators
    (``models/user.py`` raises them), and ``JSONResponse`` would choke on
    those. Encoding defensively keeps the backwards-compatible ``detail``
    field intact instead of turning a 422 into a 500.
    """
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log everything, tell the client nothing specific.

    This is what stops ``str(e)`` — Firestore project ids, index URLs,
    internal paths — from being rendered in a client UI, while keeping the
    information an operator needs on the server side, correlated by
    request id.
    """
    logger.bind(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
    ).opt(exception=exc).error("Unhandled exception")

    response = _response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        build_error_body(
            code="internal_error",
            message=GENERIC_INTERNAL_MESSAGE,
            detail=GENERIC_INTERNAL_MESSAGE,
        ),
    )

    # This is the one response in the app that the security-headers
    # middleware cannot see (#405). Starlette hands the bare-``Exception``
    # handler to ``ServerErrorMiddleware``, which wraps the entire
    # ``add_middleware`` stack, so this response is built above that
    # middleware and never passes through its send wrapper. Applying the
    # policy here makes "every response carries the headers" actually true,
    # instead of true for every response except the riskiest one.
    return secure_response(response, request)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every handler above to ``app``.

    Order does not matter to Starlette (it dispatches on exception class),
    but the ``Exception`` entry is what upgrades the default plain-text 500
    into a JSON envelope.
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


# ─── Convenience for service-layer refactors ──────────────────────────────


def upstream_error(operation: str, exc: Exception) -> UpstreamServiceError:
    """Log a dependency failure in full, return a safe error to raise.

    Replaces the ``detail=f"Failed to ...: {str(e)}"`` pattern that
    ``services/firestore_service.py`` used in a dozen places, which
    interpolated raw Google API exceptions — project ids, collection paths,
    index-creation URLs — into a response body the client renders.
    """
    logger.bind(operation=operation, exception_type=type(exc).__name__).opt(
        exception=exc
    ).error("Upstream operation failed: {}", operation)
    return UpstreamServiceError(
        f"{operation} is temporarily unavailable. Please try again.",
        code="upstream_unavailable",
    )


__all__ = [
    "AppError",
    "BadRequestError",
    "ConflictError",
    "ForbiddenError",
    "GENERIC_INTERNAL_MESSAGE",
    "InternalError",
    "NotFoundError",
    "RateLimitError",
    "UnauthorizedError",
    "UpstreamServiceError",
    "build_error_body",
    "code_for_status",
    "register_exception_handlers",
    "upstream_error",
]
