"""Whether this instance is actually working (issue #348).

``api/health.py`` was fourteen lines and touched nothing:

    return {"status": "ok", "service": "Rhythma API"}

That is a liveness probe, and a fine one. The problem was that it was the
*only* health signal the service exposed, and several dependencies can be
independently broken while the process runs happily.

The one that matters most: ``firestore_service`` falls back to an
in-memory ``MockFirestoreClient`` when credentials are missing, logging a
warning and carrying on. A deployment with a malformed service account
starts, serves traffic, accepts registrations and cycle logs — and loses
all of it on the next restart. The old endpoint returned ``ok`` throughout.
That is the single most damaging failure this app can have and it was
invisible to any monitor.

Three ideas hold this module together.

**Liveness and readiness are different questions.** "Is this process
wedged, should the platform restart it?" must not depend on Firestore — if
it did, a Firestore outage would restart-loop every instance for a problem
a restart cannot fix. "Should this instance receive traffic?" must depend
on Firestore, because an instance backed by a mock database should not be
serving. One always-200 endpoint gives the wrong answer to one of them.

**Required and optional are different too.** Gemini or Twilio being
unconfigured is *degraded*: the assistant and SMS summaries stop working
and the core cycle-tracking product does not. Firestore being mocked is
*down*. That distinction belongs in the response, not in the head of
whoever reads it.

That distinction is declared in ``CHECK_SPECS`` and read on every path,
which it was not always (issue #548). ``required`` used to live only
inside the ``ComponentHealth`` a check returns, so on the paths where a
check *didn't* return one — it timed out, or it raised — ``_run_one``
invented ``required=True``. An optional dependency answering ``degraded``
kept the instance in rotation; the same dependency hanging took it out.
Readiness was decided by which branch a failure happened to take, and the
timeout is three seconds by default, so one slow third party could empty
the load balancer over a feature most users never touch.

**A health check must not be the thing that hangs.** Every dependency probe
runs with its own timeout, so a wedged Firestore turns into a fast "down"
rather than a health endpoint that never answers — which would escalate a
degraded backend into an unresponsive one.

Nothing here returns a secret. Configuration checks report *configured* or
*not configured* and never a value, a prefix, or a project id: an
unauthenticated endpoint is the last place a key fragment should surface.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from utils.logger import logger

# ─── Status vocabulary ────────────────────────────────────────────────────

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"

#: Worst-to-best, so an overall verdict is a max() over components rather
#: than a chain of ifs that has to be kept consistent in two places.
_SEVERITY = {STATUS_OK: 0, STATUS_DEGRADED: 1, STATUS_DOWN: 2}

#: How long any single dependency probe may take. Deliberately short: this
#: endpoint is polled by a platform health check on a schedule, and a probe
#: slower than the poll interval is a queue, not a check.
DEFAULT_CHECK_TIMEOUT_SECONDS = float(os.getenv("HEALTH_CHECK_TIMEOUT", "3.0"))

#: Document the Firestore probe reads. A fixed id in its own collection, so
#: the probe never touches user data and cannot be confused with it.
HEALTH_PROBE_COLLECTION = "health_probe"
HEALTH_PROBE_DOCUMENT = "readiness"


@dataclass
class ComponentHealth:
    """One dependency's verdict.

    ``required`` is what separates "this instance should stop taking
    traffic" from "one feature is unavailable". It is a property of the
    dependency, not of the failure, so it is set where the check is
    declared rather than decided when something breaks.
    """

    name: str
    status: str
    required: bool
    detail: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "required": self.required,
            "detail": self.detail,
            "durationMs": round(self.duration_ms, 2),
        }


@dataclass
class HealthReport:
    status: str
    components: List[ComponentHealth] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """Ready unless something *required* is down.

        A degraded optional dependency deliberately does not fail
        readiness. Pulling an instance out of rotation because Twilio is
        unconfigured would take the whole app down to protect a feature
        most users never touch.
        """
        return not any(
            component.required and component.status == STATUS_DOWN
            for component in self.components
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "components": [component.to_dict() for component in self.components],
        }


# ─── Build metadata ───────────────────────────────────────────────────────


def build_info() -> Dict[str, Optional[str]]:
    """Which build is serving.

    ``/`` has always returned a hardcoded ``"version": "0.1.0"`` that has
    never changed, so after a deploy there was no way to confirm which
    commit was actually live. These come from the environment because they
    are a property of the build, not of the source — a value committed to
    the tree is stale the moment it is committed.
    """
    commit = os.getenv("GIT_COMMIT") or os.getenv("VERCEL_GIT_COMMIT_SHA")
    return {
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "commit": (commit[:12] if commit else "unknown"),
        "builtAt": os.getenv("BUILD_TIME", "unknown"),
        "environment": os.getenv("APP_ENV", "development"),
    }


# ─── Individual checks ────────────────────────────────────────────────────


def _configured(var: str) -> bool:
    value = os.getenv(var)
    return bool(value and value.strip())


def check_firestore() -> ComponentHealth:
    """Round-trip the real database, and refuse to accept the mock.

    Two failure modes, deliberately reported differently.

    A *mock* client means credentials were missing at startup. The process
    is healthy and every write is going to memory that vanishes on
    restart. Nothing is throwing, so only an explicit type check can catch
    it — which is why this does not simply test that a read succeeds. A
    read against the mock succeeds beautifully.

    An *unreachable* client means credentials were fine and the database is
    not answering. Both are ``down`` and both should stop this instance
    taking traffic, but an operator needs to know which one they are
    looking at, so the detail strings differ.
    """
    from services import firestore_service as fs

    client = fs.db

    if client is None:
        return ComponentHealth(
            name="firestore",
            status=STATUS_DOWN,
            required=True,
            detail="No Firestore client was initialised.",
        )

    if isinstance(client, fs.MockFirestoreClient):
        return ComponentHealth(
            name="firestore",
            status=STATUS_DOWN,
            required=True,
            detail=(
                "Running on the in-memory mock database. Firebase credentials "
                "are missing or unreadable; all data is lost on restart."
            ),
        )

    # A read rather than a write: this endpoint may be polled every few
    # seconds for the life of the deployment, and a write probe on that
    # schedule is a cost and a contention point for no extra signal. A
    # document that does not exist still proves the round trip worked.
    client.collection(HEALTH_PROBE_COLLECTION).document(HEALTH_PROBE_DOCUMENT).get()

    return ComponentHealth(
        name="firestore",
        status=STATUS_OK,
        required=True,
        detail="Connected.",
    )


def check_auth_config() -> ComponentHealth:
    """``JWT_SECRET`` must be set for any token to be issued or verified.

    ``core/auth.py`` raises at import when it is missing, so a process that
    is running has one. Reported anyway: "the check exists and passes" is
    a more useful thing for an operator to read than the absence of a line.
    """
    if not _configured("JWT_SECRET"):
        return ComponentHealth(
            name="auth",
            status=STATUS_DOWN,
            required=True,
            detail="JWT_SECRET is not configured; tokens cannot be issued.",
        )
    return ComponentHealth(
        name="auth",
        status=STATUS_OK,
        required=True,
        detail="Signing key configured.",
    )


def check_assistant_config() -> ComponentHealth:
    """Gemini. Optional: the cycle-tracking product works without it."""
    if not _configured("GEMINI_API_KEY"):
        return ComponentHealth(
            name="assistant",
            status=STATUS_DEGRADED,
            required=False,
            detail="GEMINI_API_KEY is not configured; /assistant/chat will fail.",
        )
    return ComponentHealth(
        name="assistant",
        status=STATUS_OK,
        required=False,
        detail="API key configured.",
    )


def check_sms_config() -> ComponentHealth:
    """Twilio. Optional, and reports *which* of the three is missing.

    ``/sms/send-summary`` needs all three and currently discovers a missing
    one at the moment a user taps send. Naming them here is the difference
    between a five-second fix and reading the route's source.
    """
    required_vars = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER")
    missing = [name for name in required_vars if not _configured(name)]

    if len(missing) == len(required_vars):
        return ComponentHealth(
            name="sms",
            status=STATUS_DEGRADED,
            required=False,
            detail="Twilio is not configured; SMS summaries are unavailable.",
        )
    if missing:
        return ComponentHealth(
            name="sms",
            status=STATUS_DEGRADED,
            required=False,
            detail=(
                "Twilio is partially configured; missing: "
                f"{', '.join(missing)}. SMS summaries will fail at send time."
            ),
        )
    return ComponentHealth(
        name="sms",
        status=STATUS_OK,
        required=False,
        detail="Credentials configured.",
    )


@dataclass(frozen=True)
class CheckSpec:
    """A check, plus the two facts about it that outlive its return value.

    ``required`` used to live only inside the ``ComponentHealth`` each
    check builds, which meant it existed only on the paths where the
    check got as far as returning one. On the paths where it did not —
    it timed out, or it raised — ``_run_one`` had to invent a value, and
    it invented ``True`` for every check (issue #548). So an optional
    dependency *returning* ``degraded`` kept the instance in rotation
    while the same dependency *hanging* took it out, with readiness
    decided by which branch the failure happened to take.

    Whether a dependency is required is a property of the dependency. It
    belongs next to the check, where every path can read it, not in one
    of the check's possible outputs.

    ``name`` is here for the same reason. ``_run_one`` used to recover it
    from ``check.__name__.replace("check_", "")``, so ``check_auth_config``
    was reported as ``auth`` when it succeeded and ``auth_config`` when it
    timed out — one component under two names, depending on how it
    failed, which is precisely when an operator is grepping for it.
    """

    name: str
    required: bool
    run: Callable[[], ComponentHealth]


#: Every check, in the order they are reported. Firestore first because it
#: is the one that matters; the config checks are cheap and cannot hang.
#:
#: The ``required`` column here is the single source of truth for
#: readiness. ``test_declared_requiredness_matches_what_each_check_returns``
#: asserts it against what each check builds, so the two cannot drift.
CHECK_SPECS: Tuple[CheckSpec, ...] = (
    CheckSpec("firestore", True, check_firestore),
    CheckSpec("auth", True, check_auth_config),
    CheckSpec("assistant", False, check_assistant_config),
    CheckSpec("sms", False, check_sms_config),
)

#: The plain callables, in the same order. Kept because it is the shape
#: this module exported before ``CheckSpec`` existed, and it reads better
#: than ``[spec.run for spec in CHECK_SPECS]`` at every call site that
#: only wants to run them.
CHECKS: List[Callable[[], ComponentHealth]] = [spec.run for spec in CHECK_SPECS]


def _spec_for(check: Callable[[], ComponentHealth]) -> CheckSpec:
    """The declaration for ``check``, or a conservative stand-in.

    A caller passing its own function — a test double, or a check added
    to a list but not to ``CHECK_SPECS`` — gets ``required=True``. That is
    the safe direction to be wrong in: a check nobody has classified
    failing should stop an instance taking traffic, and being noticed, in
    preference to being silently ignored.
    """
    for spec in CHECK_SPECS:
        if spec.run is check:
            return spec
    name = getattr(check, "__name__", "check").replace("check_", "")
    return CheckSpec(name=name, required=True, run=check)


# ─── Running them ─────────────────────────────────────────────────────────


def _run_one(
    check: Callable[[], ComponentHealth],
    timeout: float,
    spec: Optional[CheckSpec] = None,
) -> ComponentHealth:
    """Run one check, bounded in time and incapable of raising.

    A check that throws or hangs must become a *result*, never an
    exception escaping into the response. An endpoint whose job is to
    report failure is the worst possible place to have an unhandled one.

    The thread is not cancellable — Python cannot interrupt a blocking
    socket read — so a timed-out probe leaves a thread parked until its
    own network timeout fires. That is accepted deliberately: the
    alternative is a health endpoint that inherits the hang. The executor
    is per-call rather than a module-level pool so parked threads cannot
    accumulate into a poisoned pool that starves later checks.

    Note the explicit ``shutdown(wait=False)`` rather than a ``with``
    block. ``ThreadPoolExecutor.__exit__`` calls ``shutdown(wait=True)``,
    which blocks until the parked thread finishes — so the timeout would
    be measured, reported, and then silently waited out anyway, and the
    endpoint would hang for exactly as long as the dependency did. That is
    the whole failure this function exists to prevent, and it is subtle
    enough that ``test_a_hanging_check_becomes_a_result_not_a_hang``
    asserts on elapsed wall-clock rather than on the returned status.

    The ``name`` and ``required`` on the two failure results come from
    ``spec`` rather than being invented here (issue #548). Both used to
    be: the name from ``check.__name__``, and ``required`` from a
    hardcoded ``True``. The second is the one that mattered — it made a
    *hung* optional probe fail readiness where the same probe *returning*
    ``down`` would not have, so a slow third party could pull every
    healthy instance out of rotation on a three-second stopwatch.
    """
    spec = spec or _spec_for(check)
    started = time.perf_counter()
    pool = ThreadPoolExecutor(max_workers=1)

    def _failed(detail: str) -> ComponentHealth:
        return ComponentHealth(
            name=spec.name,
            status=STATUS_DOWN,
            required=spec.required,
            detail=detail,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    try:
        result = pool.submit(check).result(timeout=timeout)
        result.duration_ms = (time.perf_counter() - started) * 1000
        pool.shutdown(wait=False)
        return result
    except FutureTimeout:
        pool.shutdown(wait=False, cancel_futures=True)
        logger.warning(f"Health check {spec.name!r} timed out after {timeout}s")
        return _failed(f"Check did not respond within {timeout} seconds.")
    except Exception as exc:
        pool.shutdown(wait=False)
        # The exception text is logged, not returned. A raw Google API
        # error carries project ids, collection paths and index-creation
        # URLs — see the reasoning behind `upstream_error` in core/errors.
        logger.exception(f"Health check {spec.name!r} raised: {exc}")
        return _failed("Check failed. See server logs for details.")


def run_checks(timeout: Optional[float] = None) -> HealthReport:
    """Every dependency check, with an overall verdict.

    Sequential rather than concurrent. There are four checks, three of
    which are ``os.getenv`` calls, so the wall clock is one Firestore round
    trip either way — and a thread pool sized to the check list is more
    machinery than a sub-millisecond saving justifies.
    """
    limit = timeout if timeout is not None else DEFAULT_CHECK_TIMEOUT_SECONDS
    components = [
        _run_one(spec.run, limit, spec=spec) for spec in CHECK_SPECS
    ]

    overall = STATUS_OK
    for component in components:
        if _SEVERITY[component.status] > _SEVERITY[overall]:
            overall = component.status

    return HealthReport(status=overall, components=components)


def liveness() -> Dict[str, Any]:
    """Process-only. Touches no dependency, by design.

    If this were to depend on Firestore, an outage would make every
    instance fail liveness and the orchestrator would restart-loop the
    entire fleet over something a restart cannot fix.
    """
    return {
        "status": STATUS_OK,
        "service": "Rhythma API",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }
