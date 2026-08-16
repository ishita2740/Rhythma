"""Centralized loguru configuration with PII redaction.

Before this module, ``utils/logger.py`` was two lines — a bare
``from loguru import logger`` — which meant we inherited loguru's default
stderr sink and nothing else: no level control, no machine-readable
output, no request correlation, and no protection against a log line
accidentally containing a phone number or a symptom list.

This module fixes all four:

* :func:`configure_logging` is called once at import time from
  ``main.py`` and installs either a human-readable console sink (local
  development) or a single-line JSON sink (production, ``LOG_FORMAT=json``).
* Every record is stamped with the current ``request_id`` from
  :mod:`core.request_context`, so log lines from one client action can be
  correlated without threading a parameter through the call stack.
* Every record's ``extra`` payload is passed through :func:`redact`, so a
  key named ``phone``/``email``/``token``/``notes``/``symptoms`` (and
  friends) is replaced with a placeholder instead of being written out.
  Rhythma stores menstrual and mental-health data; that data must not
  reach a log aggregator in plaintext.
* stdlib ``logging`` (which is what uvicorn uses) is routed into loguru
  so we get one output format instead of two interleaved ones.

Environment variables:

``LOG_LEVEL``   ``TRACE``/``DEBUG``/``INFO``/``WARNING``/``ERROR`` (default ``INFO``)
``LOG_FORMAT``  ``console`` (default) or ``json``
``LOG_REDACT``  ``false`` disables redaction — intended for local debugging only
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Iterable, Mapping, Optional, Set

from loguru import logger

from core.request_context import get_request_id

# ─── Redaction ────────────────────────────────────────────────────────────

REDACTED = "[redacted]"

#: Keys whose values must never be written to a log sink. Matching is
#: case-insensitive and substring-based (``user_phone`` matches ``phone``),
#: because the point is to fail closed: it is better to redact a harmless
#: field than to leak a health record.
SENSITIVE_KEY_FRAGMENTS: frozenset = frozenset(
    {
        # Identity / contact
        "phone",
        "email",
        "full_name",
        "username",
        "address",
        "city",
        "state",
        # Credentials
        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "credential",
        "cookie",
        "session",
        "id_token",
        "otp",
        # Health data — the whole reason this app needs care
        "symptom",
        "symptoms",
        "notes",
        "note",
        "mood",
        "flow_intensity",
        "stress_level",
        "sleep_hours",
        "last_period",
        "weight_kg",
        "height_cm",
        "message",
        "messages",
    }
)

#: Nesting depth beyond which we stop walking a structure and emit a
#: placeholder. Guards against a self-referential dict turning a log call
#: into a hang.
_MAX_REDACT_DEPTH = 6

#: Sequences longer than this are truncated in log output. A user with 500
#: cycle logs should not be able to produce a 500-element log line.
_MAX_SEQUENCE_ITEMS = 20


def is_sensitive_key(key: Any) -> bool:
    """Whether a mapping key should have its value redacted."""
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively replace sensitive values inside ``value``.

    Only *values under sensitive keys* are replaced — the key names
    themselves are preserved, because knowing that "a phone number was
    involved" is useful for debugging while the number itself is not.

    Non-container values are returned unchanged: this function deliberately
    does not try to pattern-match phone numbers inside free text, because
    that is unreliable and would give a false sense of safety. The contract
    is "structure your log context as key/value pairs and it will be
    handled" — which is what :meth:`loguru.Logger.bind` encourages anyway.
    """
    if _depth >= _MAX_REDACT_DEPTH:
        return "[truncated]"

    if isinstance(value, Mapping):
        redacted: Dict[Any, Any] = {}
        for key, inner in value.items():
            if is_sensitive_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact(inner, _depth + 1)
        return redacted

    if isinstance(value, (list, tuple, set, frozenset)):
        items: Iterable[Any] = list(value)[:_MAX_SEQUENCE_ITEMS]
        rendered = [redact(item, _depth + 1) for item in items]
        if len(value) > _MAX_SEQUENCE_ITEMS:
            rendered.append(f"[+{len(value) - _MAX_SEQUENCE_ITEMS} more]")
        return rendered

    return value


def redact_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    """Redact an HTTP header mapping.

    Separate from :func:`redact` because header names are case-insensitive
    and the sensitive set is different (``authorization``, ``cookie``).
    """
    return {
        name: (REDACTED if is_sensitive_key(name) else value)
        for name, value in headers.items()
    }


# ─── Loguru wiring ────────────────────────────────────────────────────────

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<level>{level: <8}</level> "
    "<cyan>{extra[request_id]}</cyan> "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
    "<level>{message}</level>"
)

#: Record fields copied verbatim into the JSON sink output. Everything else
#: in ``extra`` is nested under ``context``.
_JSON_BASE_FIELDS = ("timestamp", "level", "logger", "message", "request_id")

_configured = False


def _patch_record(record: Dict[str, Any]) -> None:
    """loguru patcher: stamp the request id and redact bound context.

    Runs for *every* record, including ones emitted by third-party code
    routed through :class:`InterceptHandler`, which is exactly why
    redaction lives here rather than at each call site.
    """
    extra = record["extra"]

    # `{extra[request_id]}` appears in the console format string, so it has
    # to exist on every record or formatting raises KeyError.
    extra.setdefault("request_id", "-")

    request_id = get_request_id()
    if request_id:
        extra["request_id"] = request_id

    if _redaction_enabled():
        for key in list(extra.keys()):
            if key == "request_id":
                continue
            if is_sensitive_key(key):
                extra[key] = REDACTED
            else:
                extra[key] = redact(extra[key])


#: Resolved once in :func:`configure_logging` rather than read from the
#: environment on every log record. Two reasons: the patcher runs on the hot
#: path of every request, and reading env vars there makes the logging layer
#: an invisible participant in any test that patches ``os.getenv``.
_redact_enabled = True


def _redaction_enabled() -> bool:
    return _redact_enabled


def _resolve_redaction_setting() -> bool:
    return os.getenv("LOG_REDACT", "true").strip().lower() not in {"false", "0", "no"}


def _json_sink(message: Any) -> None:
    """Serialize one loguru record as a single line of JSON on stdout.

    loguru ships ``serialize=True``, but its envelope nests everything
    under ``record`` and includes fields (elapsed, thread, process) that
    make log search noisier without helping. A hand-rolled sink keeps the
    top level flat and stable, which is what a log query has to rely on.
    """
    record = message.record
    payload: Dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": f"{record['name']}:{record['function']}:{record['line']}",
        "message": record["message"],
        "request_id": record["extra"].get("request_id", "-"),
    }

    context = {k: v for k, v in record["extra"].items() if k != "request_id"}
    if context:
        payload["context"] = context

    if record["exception"] is not None:
        exc = record["exception"]
        payload["exception"] = {
            "type": getattr(exc.type, "__name__", str(exc.type)),
            "value": str(exc.value),
        }

    # `default=str` keeps the sink total: a datetime or a Firestore
    # sentinel in the context must degrade to a string, never raise and
    # take the request down with it.
    sys.stdout.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")


class InterceptHandler(logging.Handler):
    """Route stdlib ``logging`` records into loguru.

    uvicorn, httpx and firebase-admin all log through the stdlib. Without
    this, production output is two different formats interleaved and only
    half of it carries a request id.
    """

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - thin adapter
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk out of the logging module's own frames so the reported
        # source location is the real caller, not logging/__init__.py.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _intercepted_logger_names() -> Set[str]:
    return {
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "httpx",
        "httpcore",
        "google",
        "firebase_admin",
    }


def configure_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    force: bool = False,
) -> None:
    """Install Rhythma's log configuration. Idempotent unless ``force``.

    Called from ``main.py`` at import time so that any module logging
    during startup already gets the configured sink.
    """
    global _configured, _redact_enabled
    if _configured and not force:
        return

    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    resolved_format = (log_format or os.getenv("LOG_FORMAT") or "console").lower()
    _redact_enabled = _resolve_redaction_setting()

    logger.remove()
    logger.configure(patcher=_patch_record)

    if resolved_format == "json":
        logger.add(
            _json_sink,
            level=resolved_level,
            backtrace=False,
            # diagnose=False matters in production: loguru's diagnose mode
            # prints local variable values in tracebacks, which for this
            # codebase would mean printing cycle logs.
            diagnose=False,
            enqueue=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=resolved_level,
            format=_CONSOLE_FORMAT,
            colorize=True,
            backtrace=True,
            diagnose=False,
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in _intercepted_logger_names():
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    _configured = True


__all__ = [
    "REDACTED",
    "SENSITIVE_KEY_FRAGMENTS",
    "InterceptHandler",
    "configure_logging",
    "is_sensitive_key",
    "redact",
    "redact_headers",
]
