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

from typing import Any, Dict, List

from services.cycle_periods import as_date, bleed_durations, partition_gaps
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
_LOGS_LIMIT = 10


# `as_date` is re-exported rather than defined here. It moved to
# `services.cycle_periods` alongside the rest of the log-date handling, and
# five modules already import it from this one — keeping the name importable
# here avoids churning all of them for a move.


def compute_cycle_stats(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Factual cycle statistics from raw CycleLog history.

    Returns a dict with:
        average_cycle_length: mean days between consecutive period starts.
        shortest_cycle_length: minimum cycle length observed.
        longest_cycle_length: maximum cycle length observed.
        average_bleeding_duration: mean number of bleeding days (from
            start_date to end_date, inclusive).
        analyzed_cycle_count: how many cycles the three figures above are
            based on.
        excluded_gap_count: how many day-gaps were discarded as not being
            cycles at all.

    All values are ``None`` when there is not enough data to support them —
    fewer than two distinct logged dates a plausible cycle apart, or no log
    carrying both a start and an end date. ``None`` rather than a default,
    so a client can distinguish "we don't know yet" from a measurement.

    The gaps come from :func:`services.cycle_periods.partition_gaps` rather
    than from an inline subtraction over adjacent logs (#518). The inline
    version's only filter was ``(newer - older).days > 0``, and
    ``start_date`` is stamped on every logged *day*, not only on period
    starts — so two quick-logs on consecutive days were counted as a
    one-day cycle. That is how this function came to report a 4.2-day
    average and a 1-day shortest cycle for a user whose real cycles were 22
    and 28 days, in the same ``/dashboard`` response whose
    ``cycleConsistencyDescription`` — built from the filtered gaps — said
    25.

    The two figures now come from one extraction, so they cannot disagree.
    """
    kept, discarded = partition_gaps(logs)
    bleeding_days = bleed_durations(logs)

    avg_cycle = round(sum(kept) / len(kept), 1) if kept else None
    min_cycle = min(kept) if kept else None
    max_cycle = max(kept) if kept else None
    avg_bleed = (
        round(sum(bleeding_days) / len(bleeding_days), 1) if bleeding_days else None
    )

    return {
        "average_cycle_length": avg_cycle,
        "shortest_cycle_length": min_cycle,
        "longest_cycle_length": max_cycle,
        "average_bleeding_duration": avg_bleed,
        "analyzed_cycle_count": len(kept),
        "excluded_gap_count": len(discarded),
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
            logged_cycle_count: total number of logs fetched.
            profile: the user's profile dict (or None), so callers that
                need it for features beyond the two scores — e.g. the
                dashboard's cycle prediction — don't fetch it a second
                time.
    """
    logs = CycleService.get_logs_for_user(user_id, limit=_LOGS_LIMIT)
    features = build_model_features(logs)
    profile = UserService.get_user_by_id(user_id)

    mhs = predict_mhs(features, profile=profile)
    cvi = predict_cvi(features)
    cvi_risk = risk_level(cvi).capitalize() if cvi is not None else None

    return {
        "logs": logs,
        "profile": profile,
        "mhs": mhs,
        "cvi": cvi,
        "cvi_risk": cvi_risk,
        "has_enough_data_for_insights": len(logs) >= 3,
        "logged_cycle_count": len(logs),
    }