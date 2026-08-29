"""
Shared score-computation service.

This module provides two categories of output:

1. **Factual cycle statistics** (average / shortest / longest cycle length,
   average bleeding duration) computed directly from CycleLog history with
   no model inference.  These are the primary stats surfaced to clients
   since Issue #300.

2. Legacy CVI/MHS scores (kept internally for the provider dashboard which
   still depends on them).  They are *not* exposed through /dashboard or
   /scores any longer.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from services.firestore_service import CycleService, UserService
from models.cvi_model import predict_cvi, risk_level
from models.mhs_model import predict_mhs

# Default assumed cycle length (days) when there isn't enough history
# to compute a real average.
DEFAULT_CYCLE_LENGTH = 28

# `none` is included because the Flutter quick-log sheet sends it
# (`LogOptions.flow`). Without an entry it fell through to the "no value
# logged" default below and scored as *medium* — so a user explicitly
# recording no bleeding was fed to the model as an average period day.
# Zero extends the existing ordinal scale in the only direction that makes
# sense: none < light < medium < heavy.
_FLOW_INTENSITY_TO_SCORE = {"none": 0, "spotting": 1, "light": 1, "medium": 2, "heavy": 3, "very_heavy": 4}

# What to assume when a log carries no flow intensity at all. Distinct from
# `none`, which is a value the user chose: this is the absence of an answer,
# and the midpoint is the least-assuming stand-in for it.
_FLOW_INTENSITY_WHEN_ABSENT = 2

# Number of most-recent cycle logs fetched for scoring. Matches the
# previous behavior of api/dashboard.py.
#
# This is an *analysis window*, not a cap on what the user has. Every
# consumer here is deliberately built on recent history — predictions
# weight recent cycles, the observation rules describe "lately" — and
# this is what bounds the Firestore read that feeds them.
#
# It is emphatically not a count of anything. Publishing `len(logs)` as
# `loggedCycleCount` is issue #557: the value saturates at ten, so a
# patient with ten logs and a patient with five hundred were reported
# identically to a clinician. The window size is now returned under its
# own name, and the total is counted separately.
_LOGS_LIMIT = 10


def as_date(value: Any) -> Optional[date]:
    """Firestore returns date/datetime fields as datetime (or its own
    DatetimeWithNanoseconds subclass); normalize everything to a plain
    `date` for day-math."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def compute_cycle_stats(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute factual cycle statistics directly from raw CycleLog history.

    Returns a dict with:
        average_cycle_length: mean days between consecutive period start dates.
        shortest_cycle_length: minimum cycle length observed.
        longest_cycle_length: maximum cycle length observed.
        average_bleeding_duration: mean number of bleeding days (from
            start_date to end_date, inclusive).

    All values are ``None`` when there is insufficient data (fewer than
    2 logs for cycle lengths, fewer than 1 log with an end_date for
    bleeding duration).  Values are rounded to one decimal place.
    """
    # logs are newest-first
    cycle_lengths: List[int] = []
    bleeding_days: List[int] = []

    for i in range(len(logs) - 1):
        newer = as_date(logs[i].get("start_date"))
        older = as_date(logs[i + 1].get("start_date"))
        if newer and older and (newer - older).days > 0:
            cycle_lengths.append((newer - older).days)

    for log in logs:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start and end and end >= start:
            bleeding_days.append(max(1, (end - start).days + 1))

    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths), 1) if cycle_lengths else None
    min_cycle = min(cycle_lengths) if cycle_lengths else None
    max_cycle = max(cycle_lengths) if cycle_lengths else None
    avg_bleed = round(sum(bleeding_days) / len(bleeding_days), 1) if bleeding_days else None

    return {
        "average_cycle_length": avg_cycle,
        "shortest_cycle_length": min_cycle,
        "longest_cycle_length": max_cycle,
        "average_bleeding_duration": avg_bleed,
    }


def build_model_features(logs_newest_first: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert raw CycleLog documents into the feature shape the CVI/MHS
    models expect (see models/cvi_model.py and models/mhs_model.py)."""
    features = []
    for i, log in enumerate(logs_newest_first):
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))

        cycle_length = None
        if i + 1 < len(logs_newest_first):
            older_start = as_date(logs_newest_first[i + 1].get("start_date"))
            if start and older_start and (start - older_start).days > 0:
                cycle_length = (start - older_start).days

        if start and end and end >= start:
            flow_duration = max(1, (end - start).days + 1)
        else:
            flow_duration = 5
        flow_intensity = _FLOW_INTENSITY_TO_SCORE.get(
            (log.get("flow_intensity") or "").lower(), _FLOW_INTENSITY_WHEN_ABSENT
        )

        stress = log.get("stress_level")
        sleep = log.get("sleep_hours")

        features.append({
            "cycle_length": cycle_length if cycle_length is not None else DEFAULT_CYCLE_LENGTH,
            "flow_duration": flow_duration,
            "flow_intensity": flow_intensity,
            "symptom_count": len(log.get("symptoms") or []),
            "stress_avg": stress if stress is not None else 2.5,
            "sleep_avg": sleep if sleep is not None else 7.0,
        })
    return features


def get_user_scores(user_id: str) -> Dict[str, Any]:
    """Fetch a user's recent cycle logs and compute their CVI/MHS scores.

    This is the ONLY place in the codebase that should call
    `predict_cvi` / `predict_mhs`. Any endpoint that needs a user's
    scores (dashboard, insights, future SMS summaries, etc.) should
    call this function rather than re-deriving features or calling the
    models directly, so there is exactly one code path that can drift
    from the models' expected input shape.

    Returns:
        A dict with:
            logs: the raw, most-recent-first CycleLog list (so callers
                that need more than scores, like the dashboard's cycle
                day/history, don't have to fetch it again).
            mhs: the Menstrual Health Score (0-100) or None if there's
                insufficient history.
            cvi: the raw Cycle Variability Index (0-100) or None.
            cvi_risk: the capitalized risk tier for `cvi` ("Low" /
                "Medium" / "High") or None.
            has_enough_data_for_insights: whether there are enough logs
                (>=3) for a meaningful CVI; lets clients distinguish
                "no data yet" from "computed a low score".
            logged_cycle_count: how many cycle logs this user has, in
                total. Counted, not inferred from `logs` — see #557.
            analyzed_cycle_count: how many of them the numbers above were
                computed from, i.e. `len(logs)`, at most `_LOGS_LIMIT`.
                Kept as a separate field rather than left to be derived,
                because "we looked at 10 of your 63 cycles" is a sentence
                a client can only write if it is given both numbers.
            profile: the user's profile dict (or None), so callers that
                need it for features beyond the two scores — e.g. the
                dashboard's cycle prediction — don't fetch it a second
                time.
    """
    logs = CycleService.get_logs_for_user(user_id, limit=_LOGS_LIMIT)
    features = build_model_features(logs)
    profile = UserService.get_user_by_id(user_id)

    # Only worth a second query when the window came back full. A short
    # window *is* the total — there was nothing left for the limit to cut
    # — so counting again would be a Firestore round trip to learn a
    # number already in hand. This is the common case: most users have
    # fewer than ten logs, and they pay nothing for the fix.
    analyzed_cycle_count = len(logs)
    if analyzed_cycle_count < _LOGS_LIMIT:
        logged_cycle_count = analyzed_cycle_count
    else:
        logged_cycle_count = CycleService.count_logs_for_user(user_id)

    mhs = predict_mhs(features, profile=profile)
    cvi = predict_cvi(features)
    cvi_risk = risk_level(cvi).capitalize() if cvi is not None else None

    return {
        "logs": logs,
        "profile": profile,
        "mhs": mhs,
        "cvi": cvi,
        "cvi_risk": cvi_risk,
        # Asked of the window, deliberately. The question is whether
        # there is enough history *in front of the rules* to say
        # anything, and the rules only ever see the window.
        "has_enough_data_for_insights": len(logs) >= 3,
        "logged_cycle_count": logged_cycle_count,
        "analyzed_cycle_count": analyzed_cycle_count,
    }