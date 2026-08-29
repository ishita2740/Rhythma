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

from core.cycle_validation import KNOWN_SYMPTOMS, canonical_symptom
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


def compute_symptom_frequency(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How often each symptom occurs across the logs, and out of how many.

    Returns ``{"frequencies": {symptom: fraction}, "sample_size": int}``.

    Two things about this were wrong where it used to live, inline in
    ``api/dashboard.py``, and both pushed the same way — they made the
    handful of symptoms the card drew look more dominant than the record
    supports.

    **The denominator was the wrong set.** It was ``len(logs_with_symptoms)``:

        logs_with_symptoms = [l for l in logs if l.get("symptoms")]
        symptom_frequency = {
            s: round(sum(1 for l in logs_with_symptoms if s in ...) / len(logs_with_symptoms), 2)
            ...
        }

    Days the user logged sleep, mood or flow and no symptom were removed
    from the sample *before* the division, so they could not pull any
    percentage down and the figure could only ever be inflated. Two cramp
    days out of ten logged days reported 67% instead of 20%, and the
    overstatement grew the more diligently a user logged, because every
    symptom-free day she recorded was discarded rather than counted. The
    degenerate case is the common one: log symptoms exactly once and
    everything in that entry reads 100%.

    Here the denominator is every log in the window. A logged day without
    cramps is a day without cramps.

    **The vocabulary was four fixed strings** — ``cramps``, ``headache``,
    ``bloating``, ``acne`` — while ``core/cycle_validation`` offers nine
    chips and is explicit that the list is open-ended:

        *Choices are rejected; symptoms are not. [...] Unknown symptoms are
        therefore normalised and kept, bounded in count and length, rather
        than refused.*

    So ``fatigue``, ``nausea``, ``back pain``, ``severe pain`` and
    ``fainting`` were accepted at the door and then silently uncounted,
    along with anything a future free-text entry produces. Every symptom
    present in the logs is reported now.

    The nine known chips are always included when there is anything to
    report, at ``0.0`` if they never occurred. That is deliberate: a client
    drawing a fixed row of bars keeps drawing them, and "you did not report
    this" is a real answer rather than a missing key.

    ``{}`` with a non-zero ``sample_size`` is the "no symptoms logged at
    all" case, kept distinct from ``sample_size == 0`` ("nothing logged at
    all"). Both render as an empty state; only one of them means the user
    has told us something.

    Stored values are run back through :func:`canonical_symptom` before
    counting. Documents written before the write path normalised — or by a
    client that sent ``"Cramps"`` — otherwise fail an exact-match test
    against ``"cramps"`` and vanish from their own summary.
    """
    sample_size = len(logs)
    if sample_size == 0:
        return {"frequencies": {}, "sample_size": 0}

    counts: Dict[str, int] = {}
    for log in logs:
        # A symptom listed twice on one day is still one day with that
        # symptom; `seen` keeps a duplicated entry from counting twice and
        # producing a fraction above 1.0.
        seen = set()
        for raw in log.get("symptoms") or []:
            if not isinstance(raw, str):
                continue
            symptom = canonical_symptom(raw)
            if not symptom or symptom in seen:
                continue
            seen.add(symptom)
            counts[symptom] = counts.get(symptom, 0) + 1

    if not counts:
        return {"frequencies": {}, "sample_size": sample_size}

    # Known chips first, in the order `cycle_validation` declares them, then
    # anything else the user logged, alphabetically. A stable order keeps
    # the response diffable and stops a client that iterates the map from
    # reshuffling its bars between refreshes.
    ordered = list(KNOWN_SYMPTOMS) + sorted(set(counts) - set(KNOWN_SYMPTOMS))

    return {
        "frequencies": {
            symptom: round(counts.get(symptom, 0) / sample_size, 2)
            for symptom in ordered
        },
        "sample_size": sample_size,
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