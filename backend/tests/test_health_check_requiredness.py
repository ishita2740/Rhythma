"""Whether a dependency is required must not depend on how it failed (#548).

`health_check_service` is built on one distinction, stated in its own
module docstring: Firestore being mocked is *down* and should stop an
instance taking traffic; Gemini or Twilio being unconfigured is
*degraded* and should not. `HealthReport.ready` enforces it by reading
`component.required`.

But `required` only existed on the paths where a check got as far as
returning a `ComponentHealth`. On the two paths where it did not —
`FutureTimeout` and a bare `Exception` — `_run_one` built its own result
and hardcoded `required=True`. So an optional probe *returning*
`degraded` kept the instance in rotation while the same probe *hanging*
took it out, with readiness decided by which branch the failure happened
to take.

The tests below drive the failure paths for a genuinely optional check
and assert on readiness, because readiness is the whole contract with a
platform health probe — `_run_one` returning the right dataclass field is
a step on the way there, not the thing that was broken for users.

`test_declared_requiredness_matches_what_each_check_returns` is the
drift guard: `CHECK_SPECS` is now the single source of truth for
readiness, so a check whose own return value disagrees with its
declaration is a bug in one of the two, and this file is where that is
noticed.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockGemini:
    def __getattr__(self, name):
        return self

    def configure(self, *args, **kwargs):
        pass

    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    text = "Mock Gemini response"

                return MockResponse()

        return MockModel()


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app  # noqa: E402
import services.health_check_service as hc  # noqa: E402
from services.health_check_service import (  # noqa: E402
    CHECK_SPECS,
    CheckSpec,
    ComponentHealth,
    STATUS_DEGRADED,
    STATUS_DOWN,
    STATUS_OK,
    run_checks,
)

client = TestClient(app)


@pytest.fixture
def working_db(monkeypatch):
    """A Firestore stand-in that is neither the mock client nor broken.

    `check_firestore` refuses `MockFirestoreClient` by design, so a test
    about *other* components needs something that is not it and does not
    raise, or firestore fails and drowns out what is being asserted.
    """

    class _Working:
        def collection(self, name):
            return self

        def document(self, doc_id):
            return self

        def get(self):
            return None

    monkeypatch.setattr(hc, "check_firestore", lambda: ComponentHealth(
        name="firestore", status=STATUS_OK, required=True, detail="Connected."
    ))
    return _Working()


def _with_specs(monkeypatch, specs):
    monkeypatch.setattr(hc, "CHECK_SPECS", tuple(specs))


def _optional_spec(run):
    return CheckSpec(name="sms", required=False, run=run)


def _component(report, name):
    return next(c for c in report.components if c.name == name)


# ─── The failure paths keep the declared requiredness ─────────────────────


def test_a_raising_optional_check_does_not_fail_readiness(monkeypatch):
    """The bug: Twilio's *config* check blowing up emptied the fleet."""

    def explodes():
        raise RuntimeError("probe blew up")

    _with_specs(monkeypatch, [_optional_spec(explodes)])
    report = run_checks(timeout=1.0)

    assert _component(report, "sms").status == STATUS_DOWN
    assert _component(report, "sms").required is False
    assert report.ready is True, "an optional probe raising took the instance out"


def test_a_hanging_optional_check_does_not_fail_readiness(monkeypatch):
    """The likelier version: any optional probe that does network work.

    `_run_one` bounds every check at three seconds by default. The moment
    an optional probe reaches out to Gemini or Twilio, a slow third party
    becomes a fleet-wide outage on that stopwatch.
    """

    def hangs():
        time.sleep(5)

    _with_specs(monkeypatch, [_optional_spec(hangs)])

    started = time.perf_counter()
    report = run_checks(timeout=0.2)
    elapsed = time.perf_counter() - started

    assert elapsed < 3, f"run_checks inherited the hang ({elapsed:.1f}s)"
    assert _component(report, "sms").status == STATUS_DOWN
    assert "did not respond" in _component(report, "sms").detail
    assert report.ready is True


def test_a_raising_required_check_still_fails_readiness(monkeypatch):
    """The other direction, so the fix is not just "always ready"."""

    def explodes():
        raise RuntimeError("firestore is gone")

    _with_specs(
        monkeypatch, [CheckSpec(name="firestore", required=True, run=explodes)]
    )
    report = run_checks(timeout=1.0)

    assert report.ready is False


def test_a_hanging_required_check_still_fails_readiness(monkeypatch):
    def hangs():
        time.sleep(5)

    _with_specs(
        monkeypatch, [CheckSpec(name="firestore", required=True, run=hangs)]
    )
    report = run_checks(timeout=0.2)

    assert report.ready is False


# ─── Reported under one name, however it failed ───────────────────────────


def test_a_failed_check_is_reported_under_its_declared_name(monkeypatch):
    """`check_auth_config` was `auth` on success and `auth_config` on timeout.

    One component under two names, differing precisely when an operator
    is grepping their dashboards for it.
    """

    def check_auth_config():
        raise RuntimeError("boom")

    _with_specs(
        monkeypatch, [CheckSpec(name="auth", required=True, run=check_auth_config)]
    )
    report = run_checks(timeout=1.0)

    assert [c.name for c in report.components] == ["auth"]


# ─── The declarations and the checks agree ────────────────────────────────


def test_declared_requiredness_matches_what_each_check_returns(
    monkeypatch, working_db
):
    """`CHECK_SPECS` now gates readiness; it must not drift from the checks.

    Every check is run for real. The config checks read the environment,
    which is set at the top of this module, and `check_firestore` is
    stubbed by the `working_db` fixture — this is about the `name` and
    `required` each check declares, not about whether the dependency is
    up.
    """
    for spec in CHECK_SPECS:
        result = spec.run()
        assert result.name == spec.name, (
            f"{spec.name!r} returns a component named {result.name!r}"
        )
        assert result.required is spec.required, (
            f"{spec.name!r} is declared required={spec.required} "
            f"but returns required={result.required}"
        )


def test_the_optional_checks_are_the_ones_the_docstring_names():
    """Firestore and auth stop traffic; the assistant and SMS do not."""
    required = {spec.name for spec in CHECK_SPECS if spec.required}
    optional = {spec.name for spec in CHECK_SPECS if not spec.required}

    assert required == {"firestore", "auth"}
    assert optional == {"assistant", "sms"}


def test_checks_still_exposes_the_plain_callables():
    """The pre-`CheckSpec` shape, kept for callers that only want to run them."""
    assert hc.CHECKS == [spec.run for spec in CHECK_SPECS]


def test_an_unregistered_check_is_treated_as_required():
    """A check nobody has classified should be noticed, not ignored."""

    def check_something_new():
        raise RuntimeError("boom")

    result = hc._run_one(check_something_new, timeout=1.0)

    assert result.required is True
    assert result.name == "something_new"


# ─── Through HTTP, because the status code is the actual contract ─────────


def test_ready_stays_200_when_an_optional_check_raises(monkeypatch, working_db):
    def explodes():
        raise RuntimeError("probe blew up")

    _with_specs(
        monkeypatch,
        [
            CheckSpec(
                name="firestore",
                required=True,
                run=lambda: ComponentHealth(
                    "firestore", STATUS_OK, True, "Connected."
                ),
            ),
            _optional_spec(explodes),
        ],
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["status"] == STATUS_DOWN
    assert [c["name"] for c in body["components"]] == ["firestore", "sms"]


def test_ready_is_503_when_a_required_check_raises(monkeypatch):
    def explodes():
        raise RuntimeError("firestore is gone")

    _with_specs(
        monkeypatch, [CheckSpec(name="firestore", required=True, run=explodes)]
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
