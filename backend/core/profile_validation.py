"""What a health profile is allowed to contain (issue #501).

``core/cycle_validation.py`` was written because ``CycleLog`` typed its
fields and constrained none of them, and its opening line applies word for
word to the profile beside it:

    Pydantic checked that ``sleep_hours`` was a number; nothing checked it
    was a number of hours.

``UserProfileUpdate`` bounds nearly everything — ``age`` is ``ge=10,
le=120``, ``cycle_length`` is ``ge=15, le=60``, ``period_duration`` is
``ge=1, le=15``, ``phone`` has an E.164 validator — and leaves the one
field the entire product hangs off as free text:

    last_period: Optional[str] = None          # ISO 8601 date string

The comment states the format. Nothing enforced it, so
``{"last_period": "yesterday"}`` and ``{"last_period": "2027-01-01"}`` were
both 200s, and both reached Firestore.

Neither fails loudly afterwards, which is the problem.

**A malformed value empties the Home screen in silence.**
``prediction_service._last_period_start()`` does
``date.fromisoformat(declared[:10])`` inside a ``try`` and returns ``None``
on ``ValueError``; ``predict()`` then takes its no-anchor branch and
returns ``phase=unknown`` with every date ``None``. The user has just
saved her profile, been told nothing was wrong, and is looking at a screen
with no cycle day, no next period and no fertile window. The parse failure
is swallowed rather than logged, so there is no server-side signal either.

**A future value produces confident nonsense rather than nothing.**
``predict()`` computes ``cycle_day = (today - last_start).days + 1`` with
no bounds check. A ``last_period`` a month ahead makes that about −30;
``current_cycle_day`` is suppressed, but ``phase_for()`` is still called
with the negative number and still returns a phase, and
``ovulation_date``, ``fertile_window_start`` and ``fertile_window_end`` are
all computed and returned as real dates. Both clients render them. A
fertile-window date is the one output where being confidently wrong has
consequences off the screen.

Three rules, and they are the ones ``cycle_validation`` already argues for.

*Reject rather than silently correct.* Clamping a future date to today
would store a date the user never entered and never tell her. A 422 tells
her client immediately, while the entry is still on screen.

*Be tolerant about shape, strict about meaning.* ``2026-06-01`` and
``2026-06-01T00:00:00Z`` are the same answer from two clients, and
refusing the second would be pedantry. A date in the future is not a shape
problem and is refused.

*Normalise on the way in.* One stored form means
``date.fromisoformat(declared[:10])`` downstream is reading something
known, rather than something that happened to survive.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

# ─── Bounds ───────────────────────────────────────────────────────────────

#: How far back a declared last period may be dated. Matches
#: ``cycle_validation.MAX_LOG_AGE_DAYS`` deliberately: a user importing a
#: history from another app, or returning after years away, is exactly the
#: case both bounds exist to allow, and a profile that may name a date a
#: log may not would be an odd pair of rules to explain. It still excludes
#: a mis-parsed or zero-padded year like ``0202``.
MAX_LAST_PERIOD_AGE_DAYS = 3653  # ten years, allowing for leap days

#: How far ahead of the server's own date a client may be.
#:
#: Not a tolerance for wrong answers — a grace for right ones. The server
#: works in UTC; the user does not. At 01:00 on the 21st in Kolkata it is
#: still 19:30 on the 20th in UTC, so a picker that offers "today" and
#: sends ``2026-08-21`` is sending a date the server has not reached.
#: Refusing it would make the app reject the most common answer there is,
#: for users in exactly the timezones this app is built for. One day covers
#: every inhabited offset in both directions; two days would start
#: accepting a genuinely wrong answer.
FUTURE_GRACE_DAYS = 1

#: Length of a bare ``YYYY-MM-DD``. Anything longer has to be a timestamp,
#: and anything much longer is not a date at all — checked before parsing
#: so a megabyte of text is refused rather than handed to a parser.
MAX_DATE_CHARS = 64


# ─── Normaliser ───────────────────────────────────────────────────────────
#
# Raises ValueError. Pydantic turns that into the standard 422 envelope
# with the field's location attached, so this never needs to know about
# HTTP — the same arrangement ``cycle_validation`` uses.


def normalize_last_period(value: Any) -> Optional[str]:
    """Validate a declared last-period start and return it as ``YYYY-MM-DD``.

    ``None`` passes through: a profile is built up over time, and a request
    that omits the field is not the same as one that sets it to nonsense.
    An empty or whitespace-only string is treated as omission too, since
    that is what a client clearing the field tends to send — and storing
    ``""`` would be worse than storing nothing, because
    ``isinstance(declared, str)`` downstream is true for it.

    Accepted:

    * ``2026-06-01``
    * ``2026-06-01T09:30:00`` and ``...Z`` and ``...+05:30`` — the same
      answer from a client that formats a ``DateTime`` rather than a date.
      The time is discarded; a period starts on a day.

    Refused, each with a message naming what was wrong:

    * anything that is not text, or is longer than a date could be
    * anything that does not parse as a calendar date, including
      ``2026-02-30`` and ``01/06/2026``
    * a date beyond today plus :data:`FUTURE_GRACE_DAYS`
    * a date more than :data:`MAX_LAST_PERIOD_AGE_DAYS` ago
    """
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
    elif isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) > MAX_DATE_CHARS:
            raise ValueError(
                "last_period must be a date in YYYY-MM-DD form"
            )
        parsed = _parse_date(text)
    else:
        raise ValueError("last_period must be a date in YYYY-MM-DD form")

    _check_range(parsed)
    return parsed.isoformat()


def _parse_date(text: str) -> date:
    """The calendar date a client meant, from either shape it sends.

    ``date.fromisoformat`` is tried first and is the whole answer for a
    bare date. For a timestamp, ``datetime.fromisoformat`` handles the
    offset forms; a trailing ``Z`` is rewritten to ``+00:00`` because
    Python did not accept it before 3.11 and this codebase supports 3.11,
    which is close enough to the boundary to be worth not depending on.

    Deliberately *not* ``text[:10]``. Truncating turns ``01/06/2026`` into
    ``01/06/2026``'s first ten characters and then fails with a message
    about a string nobody sent, and it would quietly accept
    ``2026-06-01-garbage``.
    """
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(candidate).date()
    except ValueError:
        raise ValueError(
            f"last_period must be a date in YYYY-MM-DD form (got {text!r})"
        ) from None


def _check_range(parsed: date) -> None:
    today = datetime.now(timezone.utc).date()

    latest = today + timedelta(days=FUTURE_GRACE_DAYS)
    if parsed > latest:
        raise ValueError(
            "last_period cannot be in the future "
            f"(got {parsed.isoformat()}, today is {today.isoformat()})"
        )

    earliest = today - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS)
    if parsed < earliest:
        raise ValueError(
            "last_period is too far in the past "
            f"(got {parsed.isoformat()}, the earliest accepted is "
            f"{earliest.isoformat()})"
        )


__all__ = [
    "FUTURE_GRACE_DAYS",
    "MAX_DATE_CHARS",
    "MAX_LAST_PERIOD_AGE_DAYS",
    "normalize_last_period",
]
