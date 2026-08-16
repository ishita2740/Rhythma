"""Tests for the observability layer added for issue #268.

Covers four things:

* the request-id middleware (generation, echo, propagation, isolation),
* PII redaction in log records,
* the JSON log sink,
* the unified error envelope for every class of failure.

The import of ``test_auth`` is what boots the app with ``firebase_admin``
and ``google.generativeai`` mocked out — the same pattern every other test
module in this directory uses.
"""

import json
import re
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_auth import client  # noqa: F401  (imported for its side effects)

from core import request_context
from core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    GENERIC_INTERNAL_MESSAGE,
    NotFoundError,
    RateLimitError,
    UpstreamServiceError,
    build_error_body,
    code_for_status,
    upstream_error,
)
from core.logging_config import (
    REDACTED,
    configure_logging,
    is_sensitive_key,
    redact,
    redact_headers,
)
from core.middleware import RequestContextMiddleware
from core.request_context import (
    REQUEST_ID_HEADER,
    clear_request_context,
    get_request_id,
    new_request_id,
    normalize_request_id,
    set_request_context,
)
from main import app


@pytest.fixture(autouse=True)
def _clean_context():
    """Request context is a ContextVar; leaking it across tests would make
    assertions on `error.request_id` order-dependent."""
    clear_request_context()
    yield
    clear_request_context()


@pytest.fixture
def validating_probe_route():
    """An *unauthenticated* route with a validated body.

    Every real route that validates a body also requires auth, so hitting
    one of those returns 401 before validation ever runs. A throwaway route
    isolates the 422 path.
    """
    from datetime import date
    from typing import Optional

    from pydantic import BaseModel

    class ProbePayload(BaseModel):
        start_date: date
        notes: Optional[str] = None

    route = "/__probe_validation"

    @app.post(route)
    async def _accept(payload: ProbePayload):  # pragma: no cover - via client
        return {"ok": True}

    try:
        yield route
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


# ─── Request id generation and normalization ──────────────────────────────


def test_new_request_id_is_unique_and_hex():
    first, second = new_request_id(), new_request_id()
    assert first != second
    assert re.fullmatch(r"[0-9a-f]{32}", first)


def test_normalize_request_id_accepts_well_formed_inbound_id():
    assert normalize_request_id("trace-abc-123") == "trace-abc-123"
    assert normalize_request_id("0123456789abcdef") == "0123456789abcdef"


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        "",
        "short",                       # below the 8-char minimum
        "has spaces in it",
        "inject\nnewline-into-logs",
        "semi;colon",
        "x" * 200,                     # beyond the 128-char maximum
    ],
)
def test_normalize_request_id_rejects_unsafe_input(candidate):
    """A malformed trace header must never fail the request, and must never
    be echoed back verbatim — it ends up in log output."""
    generated = normalize_request_id(candidate)
    assert generated != candidate
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_set_and_reset_request_context():
    assert get_request_id() is None
    tokens = set_request_context("req-12345678", method="GET", path="/x")
    assert get_request_id() == "req-12345678"
    assert request_context.get_request_method() == "GET"
    assert request_context.get_request_path() == "/x"
    tokens.reset()
    assert get_request_id() is None


# ─── Middleware behaviour over the real app ───────────────────────────────


def test_response_carries_request_id_header():
    response = client.get("/")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) >= 8


def test_inbound_request_id_is_echoed_back():
    response = client.get("/", headers={REQUEST_ID_HEADER: "client-trace-0001"})
    assert response.headers[REQUEST_ID_HEADER] == "client-trace-0001"


def test_malformed_inbound_request_id_is_replaced_not_echoed():
    response = client.get("/", headers={REQUEST_ID_HEADER: "bad id"})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] != "bad id"


def test_each_request_gets_a_distinct_id():
    ids = {client.get("/").headers[REQUEST_ID_HEADER] for _ in range(5)}
    assert len(ids) == 5


def test_error_responses_also_carry_the_request_id_header():
    response = client.get("/api/v1/dashboard")  # unauthenticated → 401
    assert response.status_code == 401
    assert REQUEST_ID_HEADER in response.headers


def test_request_id_in_body_matches_header():
    response = client.get("/api/v1/dashboard")
    assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_middleware_passes_through_non_http_scopes():
    """Lifespan/websocket scopes have no request identity; the middleware
    must forward them untouched rather than assuming `scope['method']`."""
    seen = {}

    async def fake_app(scope, receive, send):
        seen["type"] = scope["type"]

    middleware = RequestContextMiddleware(fake_app)

    import asyncio

    asyncio.run(middleware({"type": "lifespan"}, None, None))
    assert seen["type"] == "lifespan"


def test_quiet_paths_are_configurable():
    middleware = RequestContextMiddleware(lambda *a: None, quiet_paths={"/ping"})
    assert middleware.quiet_paths == {"/ping"}


# ─── Redaction ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "phone",
        "user_phone",
        "PHONE",
        "email",
        "password",
        "access_token",
        "Authorization",
        "id_token",
        "symptoms",
        "notes",
        "mood",
        "sleep_hours",
        "stress_level",
        "last_period",
    ],
)
def test_sensitive_keys_are_detected(key):
    assert is_sensitive_key(key) is True


@pytest.mark.parametrize("key", ["user_id", "status", "duration_ms", "count", "path"])
def test_non_sensitive_keys_are_not_flagged(key):
    assert is_sensitive_key(key) is False


def test_is_sensitive_key_ignores_non_string_keys():
    assert is_sensitive_key(42) is False
    assert is_sensitive_key(None) is False


def test_redact_replaces_sensitive_values_but_keeps_keys():
    redacted = redact({"user_id": "u1", "phone": "+919876543210"})
    assert redacted["user_id"] == "u1"
    assert redacted["phone"] == REDACTED
    assert "phone" in redacted  # the key survives; only the value is hidden


def test_redact_walks_nested_structures():
    payload = {
        "request": {
            "body": {"notes": "cramps since morning", "start_date": "2026-05-01"},
        },
        "logs": [{"symptoms": ["cramps"], "id": "log-1"}],
    }
    redacted = redact(payload)
    assert redacted["request"]["body"]["notes"] == REDACTED
    assert redacted["request"]["body"]["start_date"] == "2026-05-01"
    assert redacted["logs"][0]["symptoms"] == REDACTED
    assert redacted["logs"][0]["id"] == "log-1"


def test_redact_truncates_long_sequences():
    redacted = redact({"ids": list(range(50))})
    assert len(redacted["ids"]) == 21  # 20 items + the "+N more" marker
    assert "more" in str(redacted["ids"][-1])


def test_redact_stops_at_max_depth():
    deep = current = {}
    for _ in range(12):
        current["next"] = {}
        current = current["next"]
    assert "[truncated]" in str(redact(deep))


def test_redact_leaves_scalars_alone():
    assert redact("plain string") == "plain string"
    assert redact(7) == 7
    assert redact(None) is None


def test_redact_headers_hides_authorization_and_cookie():
    headers = redact_headers(
        {"Authorization": "Bearer abc.def", "Cookie": "s=1", "Accept": "application/json"}
    )
    assert headers["Authorization"] == REDACTED
    assert headers["Cookie"] == REDACTED
    assert headers["Accept"] == "application/json"


# ─── Log sinks ────────────────────────────────────────────────────────────


def test_json_sink_emits_one_parseable_line(capsys):
    from utils.logger import logger

    configure_logging(level="INFO", log_format="json", force=True)
    try:
        tokens = set_request_context("req-json-0001", method="GET", path="/x")
        try:
            logger.bind(user_id="u-1", phone="+919876543210").info("hello sink")
        finally:
            tokens.reset()

        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
        payloads = [json.loads(ln) for ln in lines]
        record = next(p for p in payloads if p["message"] == "hello sink")

        assert record["level"] == "INFO"
        assert record["request_id"] == "req-json-0001"
        assert record["context"]["user_id"] == "u-1"
        assert record["context"]["phone"] == REDACTED
    finally:
        configure_logging(level="INFO", log_format="console", force=True)


def test_json_sink_serializes_non_json_native_context(capsys):
    """A datetime or a Firestore sentinel in the bound context must degrade
    to a string rather than raising inside the sink and taking the request
    down with it."""
    from datetime import datetime

    from utils.logger import logger

    configure_logging(level="INFO", log_format="json", force=True)
    try:
        logger.bind(when=datetime(2026, 5, 1, 12, 0)).info("with datetime")
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
        record = next(
            json.loads(ln) for ln in lines if json.loads(ln)["message"] == "with datetime"
        )
        assert "2026-05-01" in record["context"]["when"]
    finally:
        configure_logging(level="INFO", log_format="console", force=True)


def test_records_outside_a_request_still_format():
    """`{extra[request_id]}` is in the console format string, so a record
    logged outside any request must still have the key or formatting
    raises KeyError."""
    from utils.logger import logger

    configure_logging(level="INFO", log_format="console", force=True)
    clear_request_context()
    logger.info("startup-style message")  # must not raise


# ─── Error envelope ───────────────────────────────────────────────────────


def test_code_for_status_known_and_unknown():
    assert code_for_status(404) == "not_found"
    assert code_for_status(429) == "rate_limited"
    assert code_for_status(418) == "client_error"
    assert code_for_status(599) == "server_error"


def test_build_error_body_shape():
    body = build_error_body(code="x_code", message="msg", detail="msg", details=[1])
    assert body["detail"] == "msg"
    assert body["error"]["code"] == "x_code"
    assert body["error"]["message"] == "msg"
    assert body["error"]["details"] == [1]
    assert "request_id" in body["error"]


def test_http_exception_gets_the_envelope_and_keeps_detail():
    """Backwards compatibility matters here: existing clients and tests read
    `detail`, so it must survive alongside the new `error` object."""
    response = client.get("/api/v1/dashboard")
    body = response.json()
    assert response.status_code == 401
    assert body["detail"] == "Could not validate credentials"
    assert body["error"]["code"] == "unauthorized"


def test_validation_error_envelope_lists_fields(validating_probe_route):
    probe = TestClient(app, raise_server_exceptions=False)
    response = probe.post(validating_probe_route, json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    fields = [item["field"] for item in body["error"]["details"]]
    assert "start_date" in fields
    # Legacy shape preserved for existing consumers, which is what
    # backend/tests/test_cycle.py asserts on.
    assert "start_date" in str(body["detail"])


def test_validation_error_does_not_echo_submitted_values(validating_probe_route):
    """FastAPI's raw error list includes an `input` key echoing what was
    submitted — for this API that would mean echoing symptoms and notes back
    inside an error body."""
    probe = TestClient(app, raise_server_exceptions=False)
    response = probe.post(
        validating_probe_route,
        json={"start_date": "not-a-date", "notes": "very private note"},
    )
    assert response.status_code == 422
    assert "very private note" not in json.dumps(response.json()["error"])


@pytest.mark.parametrize(
    "error_cls,expected_status,expected_code",
    [
        (BadRequestError, 400, "bad_request"),
        (ForbiddenError, 403, "forbidden"),
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (RateLimitError, 429, "rate_limited"),
        (UpstreamServiceError, 503, "upstream_unavailable"),
    ],
)
def test_app_errors_map_to_status_and_code(error_cls, expected_status, expected_code):
    probe = TestClient(app, raise_server_exceptions=False)
    route = f"/__probe_app_error_{expected_status}"

    @app.get(route)
    async def _raise():  # pragma: no cover - invoked through the client
        raise error_cls()

    try:
        response = probe.get(route)
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


def test_app_error_accepts_custom_code_and_details():
    probe = TestClient(app, raise_server_exceptions=False)
    route = "/__probe_custom_app_error"

    @app.get(route)
    async def _raise():  # pragma: no cover - invoked through the client
        raise NotFoundError(
            "Cycle log not found",
            code="cycle_log_not_found",
            details={"log_id": "abc"},
        )

    try:
        body = probe.get(route).json()
        assert body["error"]["code"] == "cycle_log_not_found"
        assert body["error"]["message"] == "Cycle log not found"
        assert body["error"]["details"] == {"log_id": "abc"}
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


def test_app_error_details_are_redacted():
    probe = TestClient(app, raise_server_exceptions=False)
    route = "/__probe_app_error_redaction"

    @app.get(route)
    async def _raise():  # pragma: no cover - invoked through the client
        raise BadRequestError("bad", details={"phone": "+919876543210"})

    try:
        body = probe.get(route).json()
        assert body["error"]["details"]["phone"] == REDACTED
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


def test_unhandled_exception_returns_json_not_plaintext():
    """Previously this produced Starlette's plain-text `Internal Server
    Error`, which every client tried to parse as JSON."""
    probe = TestClient(app, raise_server_exceptions=False)
    route = "/__probe_boom"

    @app.get(route)
    async def _boom():  # pragma: no cover - invoked through the client
        raise RuntimeError("firestore project rhythma-prod-1234 index missing")

    try:
        response = probe.get(route)
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "internal_error"
        assert body["error"]["message"] == GENERIC_INTERNAL_MESSAGE
        # The internal detail must never reach the client.
        assert "rhythma-prod-1234" not in json.dumps(body)
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


def test_http_exception_headers_are_preserved():
    """429 responses carry Retry-After (issue #135); the envelope must not
    drop headers set on the original HTTPException."""
    probe = TestClient(app, raise_server_exceptions=False)
    route = "/__probe_retry_after"

    @app.get(route)
    async def _limited():  # pragma: no cover - invoked through the client
        raise HTTPException(
            status_code=429, detail="Slow down", headers={"Retry-After": "42"}
        )

    try:
        response = probe.get(route)
        assert response.headers["Retry-After"] == "42"
        assert response.json()["error"]["code"] == "rate_limited"
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


def test_non_string_http_detail_is_handled():
    probe = TestClient(app, raise_server_exceptions=False)
    route = "/__probe_dict_detail"

    @app.get(route)
    async def _structured():  # pragma: no cover - invoked through the client
        raise HTTPException(status_code=400, detail={"field": "start_date"})

    try:
        body = probe.get(route).json()
        assert body["detail"] == {"field": "start_date"}
        assert body["error"]["code"] == "bad_request"
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != route
        ]


# ─── upstream_error helper ────────────────────────────────────────────────


def test_upstream_error_returns_safe_message_and_logs_original():
    original = RuntimeError("project=rhythma-prod index url https://console.cloud...")
    with patch("core.errors.logger") as mock_logger:
        error = upstream_error("Fetching cycle logs", original)

    assert isinstance(error, UpstreamServiceError)
    assert error.status_code == 503
    assert "rhythma-prod" not in error.message
    assert "Fetching cycle logs" in error.message
    mock_logger.bind.assert_called_once()


def test_app_error_status_override():
    error = AppError("custom", code="weird", status_code=418)
    assert error.status_code == 418
    assert error.code == "weird"
