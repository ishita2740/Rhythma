"""Which logged days are period starts, and which gaps between them are cycles.

Every module that answers "how long is this user's cycle?" starts from the
same list of ``cycle_logs`` documents and the same ``start_date`` field.
Three of them then disagreed about what that field means, because
``start_date`` carries two jobs at once.

``CycleService.upsert_log`` writes one document per **logged day**, keyed
``{user_id}_{YYYY-MM-DD}``, and stamps ``start_date`` with that day::

    new_data = {**update_fields, "user_id": user_id, "start_date": day_start, ...}

That is the same path the Home screen's quick-log tiles take. Tapping a
mood, a sleep figure or a stress level creates a document whose
``start_date`` is today — so the field means "the day this log is about",
not "the day a period began". Both readings are live in the codebase, and
the difference only shows up in the arithmetic: subtract two adjacent
``start_date`` values and a user who logged her sleep on Monday and again
on Tuesday has had a one-day cycle.

``health_observations_service`` and ``prediction_service`` both defended
against this, independently, with the same 15-to-60-day band::

    if MIN_PLAUSIBLE_CYCLE_DAYS <= delta <= MAX_PLAUSIBLE_CYCLE_DAYS:

``scoring_service.compute_cycle_stats`` did not, and neither did the
``cycleHistory`` series built inline in ``api/dashboard.py``. So a single
``/dashboard`` response carried ``insights.averageCycleLength`` of 4.2
alongside a ``cycleConsistencyDescription`` derived from the filtered
gaps, describing the same cycles as averaging 25 days (#518).

Three copies of a rule is how the fourth place comes to be written without
it. This module is the one copy: the band, the extraction, and the two
derived series that every caller needs.

**Filtering is a mitigation, not the cure.** The defect underneath is the
overloaded ``start_date``, and separating "a day I logged something" from
"a day my period started" is a schema change and a migration. Bounding the
arithmetic stops the visible harm now and does what the rest of the
backend already does; it does not make a quick-log into a period, it only
stops it being counted as one.

**The band is deliberately wide.** 15 to 60 days is not a statement about
what is healthy — a 21-day cycle and a 45-day cycle are both real, and the
observations engine has rules that say so. It is the range outside which a
number is more likely to be a data artefact than a cycle. Narrowing it
would start discarding real cycles from the users who most need them
counted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Gaps outside this band are treated as data problems — a missed month of
#: logging, a typo'd year, or two quick-logs on consecutive days — rather
#: than as cycles.
#:
#: ``prediction_service`` declared exactly these two numbers and now imports
#: them from here, so the pair cannot drift apart again.
#:
#: ``health_observations_service`` is deliberately *not* switched over. It
#: uses the same floor of 15 but a ceiling of **90**, and moving it to 60
#: would change which observations fire for users with long cycles — a
#: clinical judgement about that module's rules, not a de-duplication.
#: Reconciling the two ceilings is worth doing and is left as its own
#: change; what mattered for #518 is that ``scoring_service`` had no bound
#: at all.
MIN_PLAUSIBLE_CYCLE_DAYS = 15
MAX_PLAUSIBLE_CYCLE_DAYS = 60

#: Bounds on a single bleed, in days, used the same way: a span outside
#: this is a mis-entered ``end_date``, not a period. Matches the range
#: ``prediction_service._period_days_from`` already applies.
MIN_PLAUSIBLE_BLEED_DAYS = 1
MAX_PLAUSIBLE_BLEED_DAYS = 15


def as_date(value: Any) -> Optional[date]:
    """Normalize whatever Firestore handed back into a plain ``date``.

    Date fields come back as ``datetime`` — or as the Firestore client's own
    ``DatetimeWithNanoseconds`` subclass — and every comparison below is
    day-math, so the time component is not merely unnecessary, it makes
    ``(newer - older).days`` depend on what time of day each log happened
    to be written.

    This lives here rather than in ``scoring_service`` because it is the
    primitive the extraction is built on, and ``scoring_service`` reaches
    Firestore. ``scoring_service`` re-exports it, so the five modules that
    already import it from there are unaffected.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def is_plausible_cycle(days: Optional[int]) -> bool:
    """Whether ``days`` could be the length of one cycle."""
    if days is None:
        return False
    return MIN_PLAUSIBLE_CYCLE_DAYS <= days <= MAX_PLAUSIBLE_CYCLE_DAYS


def is_plausible_bleed(days: Optional[int]) -> bool:
    """Whether ``days`` could be the length of one period."""
    if days is None:
        return False
    return MIN_PLAUSIBLE_BLEED_DAYS <= days <= MAX_PLAUSIBLE_BLEED_DAYS


def period_starts(logs: Sequence[Dict[str, Any]]) -> List[date]:
    """The distinct dates in ``logs``, most recent first.

    De-duplicated and re-sorted rather than trusting the caller's ordering.
    ``CycleService.get_logs_for_user`` returns newest-first, but every
    number downstream depends on that holding, and a silently reversed list
    produces confidently wrong statistics rather than an error.

    Two logs on the same day are one date here. That cannot happen through
    ``upsert_log``, whose document id is derived from the day, but it can
    happen to data written before that was true.
    """
    seen = {
        start
        for start in (as_date(log.get("start_date")) for log in logs or [])
        if start is not None
    }
    return sorted(seen, reverse=True)


def all_gaps(logs: Sequence[Dict[str, Any]]) -> List[int]:
    """Day counts between consecutive logged dates, newest gap first.

    Unfiltered. Exposed so a caller can report what was discarded, and so
    the difference between this and :func:`cycle_gaps` is visible in tests
    rather than implied.
    """
    starts = period_starts(logs)
    return [(newer - older).days for newer, older in zip(starts, starts[1:])]


def cycle_gaps(logs: Sequence[Dict[str, Any]]) -> List[int]:
    """Gaps that could plausibly be cycles, newest first."""
    return [gap for gap in all_gaps(logs) if is_plausible_cycle(gap)]


def partition_gaps(logs: Sequence[Dict[str, Any]]) -> Tuple[List[int], List[int]]:
    """``(kept, discarded)`` gaps, both newest first.

    The discarded list is what lets an endpoint say *why* an average is
    based on two cycles when the user has thirty logs, instead of leaving
    her to wonder where the rest went.
    """
    kept: List[int] = []
    discarded: List[int] = []
    for gap in all_gaps(logs):
        (kept if is_plausible_cycle(gap) else discarded).append(gap)
    return kept, discarded


def bleed_durations(logs: Sequence[Dict[str, Any]]) -> List[int]:
    """Inclusive bleed lengths from logs that carry both dates.

    A log with no ``end_date`` contributes nothing rather than a default:
    "she hasn't logged an end date yet" and "the period lasted one day" are
    different facts, and inventing the difference is what
    ``health_observations_service._bleeding_days`` refuses to do for the
    same reason.
    """
    durations: List[int] = []
    for log in logs or []:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start is None or end is None:
            continue
        span = (end - start).days + 1
        if is_plausible_bleed(span):
            durations.append(span)
    return durations


def cycle_history(logs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The chart series: one entry per cycle, oldest first.

    ``start_date`` on each entry is the start of the *later* period — the
    one the length was measured up to — which is what the existing
    ``/dashboard`` payload means by it and what the trend charts on both
    clients already plot against.
    """
    starts = period_starts(logs)
    history: List[Dict[str, Any]] = []
    # `starts` is newest-first; walk it backwards so the series comes out
    # oldest-first, which is the order a trend chart draws.
    for newer, older in zip(starts, starts[1:]):
        length = (newer - older).days
        if is_plausible_cycle(length):
            history.append(
                {"start_date": newer.isoformat(), "cycle_length": length}
            )
    history.reverse()
    return history


__all__ = [
    "MAX_PLAUSIBLE_BLEED_DAYS",
    "MAX_PLAUSIBLE_CYCLE_DAYS",
    "MIN_PLAUSIBLE_BLEED_DAYS",
    "MIN_PLAUSIBLE_CYCLE_DAYS",
    "all_gaps",
    "as_date",
    "bleed_durations",
    "cycle_gaps",
    "cycle_history",
    "is_plausible_bleed",
    "is_plausible_cycle",
    "partition_gaps",
    "period_starts",
]
