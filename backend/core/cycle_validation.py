"""What a cycle log is allowed to contain (issue #347).

``CycleLog`` typed its fields and constrained none of them. Pydantic
checked that ``sleep_hours`` was a number; nothing checked it was a number
of hours. A single request could store a period starting in the year 3025,
negative five thousand hours of sleep, a hundred thousand characters of
symptom strings and a 50 KB note, and be answered with a 200.

That is not only untidy. The rows are read back by
``scoring_service.build_model_features``, ``health_observations_service``
and ``provider_service.patient_detail``, none of which re-validate — they
are not wrong to trust the row, because the write endpoint is the thing
that was supposed to establish it was trustworthy. So a flow intensity of
``"banana"`` reached ``_FLOW_INTENSITY_TO_SCORE.get(..., 2)`` and scored
as **medium**, indistinguishable from a real medium entry, and one absurd
``sleep_hours`` dragged the ``avgSleepHours`` shown to a clinician to
nonsense.

Everything about what a log may contain lives in this module, so the two
write routes (``POST /cycle/log`` and ``PUT /cycle/{log_id}``) cannot
drift apart, and so a client can be told the rules rather than having to
rediscover them.

Design notes:

*The vocabularies are not invented here.* They are what the two clients
already send — ``web/src/pages/CyclePage.tsx`` and
``rhythma_flutter/lib/utils/log_options.dart``. The set of values the
product supports has always been small and known; it just was not written
down anywhere the server could enforce it, so it lived in two UIs that
happened to agree. Reading the clients rather than choosing fresh values
is what makes this a validation change and not a behaviour change.

*Choices are rejected; symptoms are not.* Flow, mood, stress and sleep are
tap targets — there is no legitimate way for a client to produce a value
outside the list, so a value outside it is a bug worth surfacing. Symptoms
are different: a user genuinely can experience something that is not one
of the seven chips, and free-text symptom entry is a plausible future
feature. Unknown symptoms are therefore normalised and kept, bounded in
count and length, rather than refused.

*Rejecting beats silently correcting.* Clamping ``sleep_hours=-5000`` to
zero would store a number the user never entered and never told her. A 422
tells her client immediately, while the entry is still on screen.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, List, Optional, Sequence

# ─── Vocabularies ─────────────────────────────────────────────────────────

#: Flow intensities both clients offer. ``none`` is in the list because the
#: Flutter quick-log sheet sends it (``LogOptions.flow``); omitting it would
#: reject a value the shipped mobile app produces, turning a validation fix
#: into a mobile outage. The web app offers the other three.
FLOW_INTENSITIES: Sequence[str] = ("none", "spotting", "light", "medium", "heavy", "very_heavy")

#: The five moods behind the emoji in both clients.
MOODS: Sequence[str] = ("happy", "neutral", "sad", "frustrated", "loved")

#: Symptoms the clients offer as chips. Used to normalise spelling — an
#: unknown symptom is still accepted, see :func:`normalize_symptoms`.
KNOWN_SYMPTOMS: Sequence[str] = (
    "cramps",
    "headache",
    "bloating",
    "fatigue",
    "nausea",
    "acne",
    "back pain",
    "severe pain",
    "fainting",
)

#: Spellings seen from clients that mean a known symptom. Kept small and
#: obvious: this is for joining up ``backpain`` and ``back_pain`` with
#: ``back pain``, not for guessing at free text.
_SYMPTOM_ALIASES = {
    "backpain": "back pain",
    "back_pain": "back pain",
    "lower back pain": "back pain",
    "cramp": "cramps",
    "period cramps": "cramps",
    "head ache": "headache",
    "tiredness": "fatigue",
    "tired": "fatigue",
    "nauseous": "nausea",
    "faint": "fainting",
    "passed out": "fainting",
    "severe cramps": "severe pain",
    "bad pain": "severe pain",
}

# ─── Bounds ───────────────────────────────────────────────────────────────

#: A day has 24 hours. The upper bound is the physical one rather than a
#: clinical opinion about how much sleep is plausible — the point is to
#: exclude impossible values, not to argue with a user who slept 14 hours.
MIN_SLEEP_HOURS = 0.0
MAX_SLEEP_HOURS = 24.0

#: 1-5, matching what both clients send (``{1, 3, 5}`` from the three-bucket
#: pickers) and what the MHS model's feature comments describe. Deliberately
#: the full 1-5 range rather than only the three values the pickers offer,
#: so a future five-point slider does not need a server change.
MIN_STRESS_LEVEL = 1
MAX_STRESS_LEVEL = 5

#: Free text attached to one day. Long enough for a paragraph about how a
#: cycle felt, short enough that a log document stays small and a CSV export
#: cell stays readable.
MAX_NOTES_CHARS = 2000

#: No day has fifty distinct symptoms; a request carrying that many is a
#: loop, not a person. The per-item cap is what stops ``symptoms`` being
#: used as an unbounded text field once the count is capped.
MAX_SYMPTOMS = 25
MAX_SYMPTOM_CHARS = 40

#: How far back a log may be dated. Ten years covers importing a history
#: from another app, which is the only reason to log something old, and
#: still excludes a zero-padded or mis-parsed year like ``0202``.
MAX_LOG_AGE_DAYS = 3653  # ten years, allowing for leap days

#: How long a single period may be recorded as lasting. Cycles that run
#: long are exactly what this app exists to surface, so the ceiling is well
#: past any clinical threshold — it is here to catch an ``end_date`` typed
#: with the wrong year, not to second-guess a user.
MAX_PERIOD_DURATION_DAYS = 90


# ─── Normalisers ──────────────────────────────────────────────────────────
#
# Each raises ValueError. Pydantic turns that into the standard 422
# envelope with the field's location attached, so these never need to know
# about HTTP.


def _describe(allowed: Iterable[str]) -> str:
    return ", ".join(allowed)


def normalize_choice(
    value: Optional[str], allowed: Sequence[str], field: str
) -> Optional[str]:
    """Casefold and check ``value`` against a fixed vocabulary.

    ``None`` passes through: a log is built up over time, and a request
    that omits a field is not the same as one that sets it to nonsense.
    An empty or whitespace-only string is treated as omission too, since
    that is what a client clearing a selection tends to send.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")

    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in allowed:
        raise ValueError(
            f"{field} must be one of: {_describe(allowed)} (got {value!r})"
        )
    return cleaned


def normalize_symptoms(value: Optional[Any]) -> Optional[List[str]]:
    """Clean a symptom list without refusing symptoms we don't know about.

    Casefolds, collapses internal whitespace, maps a few known alternate
    spellings onto the canonical chip value, drops blanks and duplicates,
    and preserves the order the client sent so a UI rendering it back does
    not reshuffle. Unknown entries survive; only impossible ones (blank,
    over-long, or too many) are refused.
    """
    if value is None:
        return None
    if isinstance(value, str):
        # A bare string is almost certainly a client that meant to send a
        # one-item list. Accepting it silently would let `"cramps"` be
        # stored where `["cramps"]` was meant, and `len(symptoms)` — which
        # `build_model_features` uses as `symptom_count` — would then count
        # six characters instead of one symptom.
        raise ValueError("symptoms must be a list, not a single string")
    if not isinstance(value, (list, tuple)):
        raise ValueError("symptoms must be a list")

    cleaned: List[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("every symptom must be text")
        # Collapse runs of whitespace so "back   pain" matches "back pain".
        normalized = " ".join(item.split()).lower()
        if not normalized:
            continue
        normalized = _SYMPTOM_ALIASES.get(normalized, normalized)
        if len(normalized) > MAX_SYMPTOM_CHARS:
            raise ValueError(
                f"each symptom must be at most {MAX_SYMPTOM_CHARS} characters "
                f"(got {len(normalized)})"
            )
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    if len(cleaned) > MAX_SYMPTOMS:
        raise ValueError(
            f"at most {MAX_SYMPTOMS} symptoms can be logged for one day "
            f"(got {len(cleaned)})"
        )
    return cleaned


def normalize_notes(value: Optional[str]) -> Optional[str]:
    """Trim a note and bound its length. Whitespace-only becomes ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("notes must be text")

    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_NOTES_CHARS:
        raise ValueError(
            f"notes must be at most {MAX_NOTES_CHARS} characters "
            f"(got {len(trimmed)})"
        )
    return trimmed


def validate_sleep_hours(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    # bool is a subclass of int; `sleep_hours: true` should not become 1.0.
    if isinstance(value, bool):
        raise ValueError("sleep_hours must be a number")
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        raise ValueError("sleep_hours must be a real number")
    if not MIN_SLEEP_HOURS <= numeric <= MAX_SLEEP_HOURS:
        raise ValueError(
            f"sleep_hours must be between {MIN_SLEEP_HOURS} and "
            f"{MAX_SLEEP_HOURS} (got {value})"
        )
    return numeric


def validate_stress_level(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("stress_level must be a number")
    if not MIN_STRESS_LEVEL <= value <= MAX_STRESS_LEVEL:
        raise ValueError(
            f"stress_level must be between {MIN_STRESS_LEVEL} and "
            f"{MAX_STRESS_LEVEL} (got {value})"
        )
    return value


def earliest_loggable_date(today: Optional[date] = None) -> date:
    return (today or date.today()) - timedelta(days=MAX_LOG_AGE_DAYS)


def validate_start_date(value: date, *, today: Optional[date] = None) -> date:
    """A period cannot start in the future or a century ago.

    The future check matters beyond plausibility: ``prediction_service``
    takes the most recent logged start as "where this user is in her
    cycle", so one log dated next year makes every prediction and the
    current-cycle-day readout wrong until it is deleted. The web calendar
    already disables future days; nothing stopped a direct request.
    """
    reference = today or date.today()
    if value > reference:
        raise ValueError(
            f"start_date cannot be in the future (got {value.isoformat()}, "
            f"today is {reference.isoformat()})"
        )
    floor = earliest_loggable_date(reference)
    if value < floor:
        raise ValueError(
            f"start_date cannot be before {floor.isoformat()} "
            f"(got {value.isoformat()})"
        )
    return value


def validate_end_date(
    start: Optional[date], end: Optional[date], *, today: Optional[date] = None
) -> Optional[date]:
    """Check ``end_date`` against ``start_date`` when both are present.

    ``scoring_service.build_model_features`` already carries a defensive
    clamp for an inverted range (``if start and end and end >= start``,
    else a flow duration of 5). That clamp is a workaround for this check
    being missing; it stays, because logs written before this change still
    have to be read, but new writes should not need it.
    """
    if end is None:
        return None
    reference = today or date.today()
    if end > reference:
        raise ValueError(
            f"end_date cannot be in the future (got {end.isoformat()})"
        )
    if start is not None:
        if end < start:
            raise ValueError(
                f"end_date ({end.isoformat()}) cannot be before start_date "
                f"({start.isoformat()})"
            )
        span = (end - start).days + 1
        if span > MAX_PERIOD_DURATION_DAYS:
            raise ValueError(
                f"a single period cannot span more than "
                f"{MAX_PERIOD_DURATION_DAYS} days (got {span})"
            )
    return end


# ─── Client-facing description ────────────────────────────────────────────


def loggable_values() -> dict:
    """The rules, described for a client to render or validate against.

    Served by ``GET /cycle/loggable-values`` so the options a user is shown
    come from the same place as the rules she is judged against, rather
    than being retyped in each client and going stale — the same reasoning
    behind ``GET /auth/password-requirements``.
    """
    return {
        "flowIntensities": list(FLOW_INTENSITIES),
        "moods": list(MOODS),
        "knownSymptoms": list(KNOWN_SYMPTOMS),
        "symptomsAreOpenEnded": True,
        "limits": {
            "sleepHours": {"min": MIN_SLEEP_HOURS, "max": MAX_SLEEP_HOURS},
            "stressLevel": {"min": MIN_STRESS_LEVEL, "max": MAX_STRESS_LEVEL},
            "notesMaxChars": MAX_NOTES_CHARS,
            "maxSymptoms": MAX_SYMPTOMS,
            "symptomMaxChars": MAX_SYMPTOM_CHARS,
            "maxPeriodDurationDays": MAX_PERIOD_DURATION_DAYS,
            "earliestLoggableDate": earliest_loggable_date().isoformat(),
        },
    }
