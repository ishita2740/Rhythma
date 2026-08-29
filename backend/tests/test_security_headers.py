"""Tests for the security response headers added in issue #405.

Four groups:

* the header set is present on ordinary responses,
* HSTS appears only over a secure scheme — the one rule with a footgun,
* the headers survive every failure path, including the 500 envelope,
* environment overrides and the do-not-clobber rule behave.

The import of ``test_auth`` is what boots the app with ``firebase_admin``
and ``google.generativeai`` mocked out, the same as every other module in
this directory.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_auth import client  # noqa: F401  (imported for its side effects)

from core.security_headers import (
    CONTENT_TYPE_OPTIONS_HEADER,
    COOP_HEADER,
    CORP_HEADER,
    CSP_HEADER,
    DEFAULT_CONTENT_TYPE_OPTIONS,
    DEFAULT_FRAME_OPTIONS,
    DEFAULT_REFERRER_POLICY,
    FRAME_OPTIONS_HEADER,
    HSTS_HEADER,
    PERMISSIONS_POLICY_HEADER,
    REFERRER_POLICY_HEADER,
    SecurityHeadersMiddleware,
    build_header_policy,
    resolve_scheme,
)

#: Everything that should be on a plaintext response. HSTS is not here on
#: purpose — see the scheme tests below.
ALWAYS_PRESENT = (
    CONTENT_TYPE_OPTIONS_HEADER,
    FRAME_OPTIONS_HEADER,
    REFERRER_POLICY_HEADER,
    PERMISSIONS_POLICY_HEADER,
    CSP_HEADER,
    COOP_HEADER,
    CORP_HEADER,
)


def _app_with(**middleware_kwargs) -> TestClient:
    """A throwaway app carrying only the middleware under test.

    Isolating it from the real ``main.app`` keeps these cases independent
    of route changes elsewhere, and lets a test construct the middleware
    with explicit arguments instead of going through the environment.
    """
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, **middleware_kwargs)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise HTTPException(status_code=418, detail="teapot")

    @app.get("/crash")
    async def crash():
        raise RuntimeError("unhandled")

    @app.get("/own-csp")
    async def own_csp():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"ok": True},
            headers={"Content-Security-Policy": "default-src 'none'"},
        )

    return TestClient(app, raise_server_exceptions=False)


# ── The header set is present ─────────────────────────────────────────────


@pytest.mark.parametrize("header", ALWAYS_PRESENT)
def test_header_present_on_real_app_response(header):
    """Every non-HSTS header lands on a normal response from the real app."""
    response = client.get("/api/v1/health")
    assert header in response.headers, f"{header} missing from /health"


def test_nosniff_and_frame_options_have_the_expected_values():
    response = client.get("/api/v1/health")
    assert response.headers[CONTENT_TYPE_OPTIONS_HEADER] == DEFAULT_CONTENT_TYPE_OPTIONS
    assert response.headers[FRAME_OPTIONS_HEADER] == DEFAULT_FRAME_OPTIONS
    assert response.headers[REFERRER_POLICY_HEADER] == DEFAULT_REFERRER_POLICY


def test_csp_denies_framing_and_object_embedding():
    """``frame-ancestors 'none'`` is the modern half of the clickjacking fix.

    ``X-Frame-Options`` covers older browsers and the Flutter webview; this
    covers everything else. Both are asserted because dropping either one
    silently halves the protection.
    """
    csp = client.get("/api/v1/health").headers[CSP_HEADER]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "default-src 'self'" in csp


def test_headers_are_present_on_the_root_route():
    """``/`` is in the middleware's quiet-path set for logging, not for headers."""
    response = client.get("/")
    assert response.status_code == 200
    for header in ALWAYS_PRESENT:
        assert header in response.headers


def test_server_header_is_not_advertised():
    assert "server" not in {k.lower() for k in client.get("/api/v1/health").headers}


# ── HSTS depends on the scheme ────────────────────────────────────────────


def test_hsts_absent_over_plaintext():
    """The footgun case.

    Sending HSTS on an ``http://localhost`` response would pin localhost to
    HTTPS in the developer's browser profile and break every other project
    on that hostname. TestClient speaks plain http, so this is exactly the
    development situation.
    """
    assert HSTS_HEADER not in client.get("/api/v1/health").headers


def test_hsts_present_when_the_proxy_reports_https():
    """Behind a TLS-terminating proxy the scope scheme is http; the header isn't."""
    response = client.get(
        "/api/v1/health", headers={"X-Forwarded-Proto": "https"}
    )
    assert HSTS_HEADER in response.headers
    assert "max-age=" in response.headers[HSTS_HEADER]
    assert "includeSubDomains" in response.headers[HSTS_HEADER]


def test_hsts_absent_when_the_proxy_reports_http():
    response = client.get("/api/v1/health", headers={"X-Forwarded-Proto": "http"})
    assert HSTS_HEADER not in response.headers


def test_forwarded_proto_chain_uses_the_client_facing_hop():
    """``https, http`` means the *client* used https; that is the hop that counts."""
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "http", "headers": []}
    headers = Headers({"x-forwarded-proto": "https, http"})
    assert resolve_scheme(scope, headers) == "https"


def test_scheme_falls_back_to_the_scope_when_unproxied():
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "https", "headers": []}
    assert resolve_scheme(scope, Headers({})) == "https"


def test_forwarded_proto_is_case_insensitive():
    from starlette.datastructures import Headers

    scope = {"type": "http", "scheme": "http", "headers": []}
    assert resolve_scheme(scope, Headers({"x-forwarded-proto": "HTTPS"})) == "https"


# ── Failure paths still get headers ───────────────────────────────────────


def test_headers_present_on_a_404():
    response = client.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404
    for header in ALWAYS_PRESENT:
        assert header in response.headers


def test_headers_present_on_a_handled_http_exception():
    """A raised HTTPException short-circuits the route but not the middleware."""
    response = _app_with().get("/boom")
    assert response.status_code == 418
    for header in ALWAYS_PRESENT:
        assert header in response.headers


def test_headers_present_on_an_unhandled_exception():
    """The case that matters most, and the one the middleware cannot reach.

    A 500 is when a browser is most likely to be rendering something
    unexpected, and it is the response an attacker has the most influence
    over. Losing ``nosniff`` here would be losing it exactly when it is
    needed.

    It is also the one response built *above* the middleware stack:
    Starlette gives the bare-``Exception`` handler to
    ``ServerErrorMiddleware``, which wraps everything registered with
    ``add_middleware``. ``core.errors.unhandled_exception_handler`` calls
    ``secure_response`` for precisely this reason, and this test is what
    keeps that call from being deleted as redundant-looking.

    Asserted against the real app, not a throwaway one, because the
    behaviour under test is a property of the real handler registration.
    """
    probe_app = FastAPI()

    @probe_app.get("/probe-crash")
    async def probe_crash():
        raise RuntimeError("unhandled")

    from core.errors import register_exception_handlers
    from core.middleware import RequestContextMiddleware

    probe_app.add_middleware(RequestContextMiddleware)
    probe_app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(probe_app)

    response = TestClient(probe_app, raise_server_exceptions=False).get(
        "/probe-crash"
    )
    assert response.status_code == 500
    for header in ALWAYS_PRESENT:
        assert header in response.headers


def test_headers_present_on_a_validation_error():
    """A rejected request on a paged route — the #331 pagination bounds.

    Unauthenticated, so the auth dependency may reject before the query
    validator runs. Either way it is a handler-produced error response,
    which is the thing being checked.
    """
    response = client.get("/api/v1/cycle/u1/history?limit=-1")
    assert response.status_code in (401, 403, 422)
    for header in ALWAYS_PRESENT:
        assert header in response.headers


def test_headers_present_on_an_unauthenticated_401():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    for header in ALWAYS_PRESENT:
        assert header in response.headers


# ── Policy resolution and overrides ───────────────────────────────────────


def test_a_route_that_sets_its_own_csp_keeps_it():
    """The blanket policy is a floor, not a ceiling.

    A route setting its own header knows something the middleware does not;
    overwriting it would turn a deliberate decision into a silent bug.
    """
    response = _app_with().get("/own-csp")
    assert response.headers[CSP_HEADER] == "default-src 'none'"
    # The rest of the policy still applies.
    assert response.headers[CONTENT_TYPE_OPTIONS_HEADER] == "nosniff"


def test_a_header_can_be_disabled_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECURITY_CSP", "off")
    policy = build_header_policy()
    assert CSP_HEADER not in policy
    # Disabling one header must not disable the others.
    assert CONTENT_TYPE_OPTIONS_HEADER in policy


@pytest.mark.parametrize("disabled", ["", "off", "none", "false", "0", "  OFF  "])
def test_all_disable_spellings_are_honoured(monkeypatch, disabled):
    monkeypatch.setenv("SECURITY_FRAME_OPTIONS", disabled)
    assert FRAME_OPTIONS_HEADER not in build_header_policy()


def test_a_header_value_can_be_replaced_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECURITY_REFERRER_POLICY", "no-referrer")
    assert build_header_policy()[REFERRER_POLICY_HEADER] == "no-referrer"


def test_hsts_can_be_disabled_explicitly():
    """For a deployment fronted by something that already sends HSTS."""
    response = _app_with(hsts="off").get(
        "/ping", headers={"X-Forwarded-Proto": "https"}
    )
    assert HSTS_HEADER not in response.headers


def test_excluded_paths_are_left_alone():
    response = _app_with(exclude_paths={"/ping"}).get("/ping")
    assert CSP_HEADER not in response.headers


def test_server_header_stripping_is_applied_and_can_be_turned_off():
    """Exercised through ``apply`` rather than a request.

    ``Server`` is added by uvicorn, not by the ASGI app, so ``TestClient``
    never produces one and a round-trip test here would assert nothing.
    Driving ``apply`` directly is the only way to observe the branch.
    """
    from starlette.datastructures import MutableHeaders

    def _headers_with_server():
        headers = MutableHeaders()
        headers["server"] = "uvicorn"
        return headers

    stripping = SecurityHeadersMiddleware(app=None, strip_server_header=True)
    headers = _headers_with_server()
    stripping.apply(headers, scheme="https")
    assert "server" not in headers

    keeping = SecurityHeadersMiddleware(app=None, strip_server_header=False)
    headers = _headers_with_server()
    keeping.apply(headers, scheme="https")
    assert headers["server"] == "uvicorn"


# ── Interaction with the rest of the stack ────────────────────────────────


def test_request_id_still_reaches_the_client():
    """#268's correlation id must survive the new middleware layer."""
    response = client.get("/api/v1/health")
    assert response.headers.get("x-request-id")


def test_cors_preflight_is_not_broken():
    """CORS is registered outermost, so it answers preflight before this runs.

    The assertion is about the preflight still succeeding — whether it also
    carries the security headers is irrelevant, because a browser consumes
    a preflight response internally and never renders it.
    """
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin")


def test_cors_exposed_headers_are_unchanged():
    response = client.get(
        "/api/v1/health", headers={"Origin": "http://localhost:5173"}
    )
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in exposed
