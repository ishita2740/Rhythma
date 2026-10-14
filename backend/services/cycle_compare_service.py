"""Cycle Comparison service.

Lets users compare two arbitrary date ranges of their cycle data side by
side — cycle lengths, symptom frequencies, sleep and stress averages,
flow patterns, and mood.  The response is a structured diff that makes
it easy to see what changed between periods.

Not a diagnosis.  These are statistical comparisons of logged values.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from services.firestore_service import CycleService, UserService
from services.scoring_service import as_date, compute_cycle_stats
from services.trend_service import CANONICAL_SYMPTOMS, BLEEDING_FLOWS

DISCLAIMER = (
    "These are factual comparisons of your logged data, not medical advice."
)
DISCLAIMER_KEY = "cycle_compare.disclaimer"


def _fetch_logs_in_range(user_id: str, start: date, end: date) -> List[Dict[str, Any]]:
    """Fetch cycle logs whose start_date falls within [start, end]."""
    logs = CycleService.get_logs_for_user(user_id, limit=100)
    return [
        l for l in logs
        if start <= (as_date(l.get("start_date")) or date.min) <= end
    ]


def _avg(values: List[float]) -> Optional[float]:
    return round(statistics.fmean(values), 1) if values else None


def _compute_period_stats(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate statistics for one date range."""
    cycle_lengths: List[int] = []
    for i in range(len(logs) - 1):
        newer = as_date(logs[i].get("start_date"))
        older = as_date(logs[i + 1].get("start_date"))
        if newer and older and (newer - older).days > 0:
            cycle_lengths.append((newer - older).days)

    bleeding_days: List[int] = []
    for log in logs:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start and end and end >= start:
            bleeding_days.append(max(1, (end - start).days + 1))

    sleep_values = [l["sleep_hours"] for l in logs if l.get("sleep_hours") is not None]
    stress_values = [l["stress_level"] for l in logs if l.get("stress_level") is not None]
    mood_values = [l["mood_score"] for l in logs if l.get("mood_score") is not None]

    symptom_counts: Dict[str, int] = {}
    days_with_symptoms = 0
    for log in logs:
        syms = log.get("symptoms") or []
        if syms:
            days_with_symptoms += 1
        for s in syms:
            symptom_counts[s] = symptom_counts.get(s, 0) + 1

    flow_counts: Dict[str, int] = {}
    for log in logs:
        flow = (log.get("flow_intensity") or "").strip().lower()
        if flow in BLEEDING_FLOWS:
            flow_counts[flow] = flow_counts.get(flow, 0) + 1

    symptom_freq = {
        s: round(symptom_counts.get(s, 0) / days_with_symptoms, 2)
        for s in CANONICAL_SYMPTOMS
        if days_with_symptoms > 0
    }

    return {
        "logCount": len(logs),
        "cycleLengths": cycle_lengths,
        "averageCycleLength": _avg([float(c) for c in cycle_lengths]),
        "bleedingDays": bleeding_days,
        "averageBleedingDuration": _avg([float(b) for b in bleeding_days]),
        "sleepAverage": _avg(sleep_values),
        "stressAverage": _avg(stress_values),
        "moodAverage": _avg(mood_values),
        "symptomFrequency": symptom_freq,
        "flowDistribution": flow_counts,
    }


def _direction(old_val: Optional[float], new_val: Optional[float]) -> str:
    if old_val is None or new_val is None:
        return "unknown"
    diff = new_val - old_val
    if abs(diff) < 0.2:
        return "unchanged"
    return "increased" if diff > 0 else "decreased"


def _compare_values(
    label: str, old_val: Optional[float], new_val: Optional[float], unit: str = ""
) -> Dict[str, Any]:
    delta = None
    if old_val is not None and new_val is not None:
        delta = round(new_val - old_val, 1)
    return {
        "label": label,
        "periodA": old_val,
        "periodB": new_val,
        "delta": delta,
        "direction": _direction(old_val, new_val),
        "unit": unit or None,
    }


# ─── Public API ──────────────────────────────────────────────────────────────


def compare_periods(
    user_id: str,
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
) -> Dict[str, Any]:
    """Compare two date ranges side by side.

    ``period_a`` is the earlier/baseline period.  ``period_b`` is the
    comparison period.  The response includes per-period statistics and
    a structured diff for each metric.
    """
    logs_a = _fetch_logs_in_range(user_id, period_a_start, period_a_end)
    logs_b = _fetch_logs_in_range(user_id, period_b_start, period_b_end)

    stats_a = _compute_period_stats(logs_a)
    stats_b = _compute_period_stats(logs_b)

    comparisons = [
        _compare_values("Average Cycle Length", stats_a["averageCycleLength"], stats_b["averageCycleLength"], "days"),
        _compare_values("Average Bleeding Duration", stats_a["averageBleedingDuration"], stats_b["averageBleedingDuration"], "days"),
        _compare_values("Average Sleep", stats_a["sleepAverage"], stats_b["sleepAverage"], "hours"),
        _compare_values("Average Stress", stats_a["stressAverage"], stats_b["stressAverage"], ""),
        _compare_values("Average Mood", stats_a["moodAverage"], stats_b["moodAverage"], ""),
    ]

    # Symptom-level comparisons
    symptom_diffs = []
    for s in CANONICAL_SYMPTOMS:
        old_rate = stats_a["symptomFrequency"].get(s)
        new_rate = stats_b["symptomFrequency"].get(s)
        if old_rate is not None or new_rate is not None:
            old_pct = round(old_rate * 100) if old_rate is not None else None
            new_pct = round(new_rate * 100) if new_rate is not None else None
            symptom_diffs.append(_compare_values(s, old_pct, new_pct, "%"))

    return {
        "periodA": {
            "start": period_a_start.isoformat(),
            "end": period_a_end.isoformat(),
            "stats": stats_a,
        },
        "periodB": {
            "start": period_b_start.isoformat(),
            "end": period_b_end.isoformat(),
            "stats": stats_b,
        },
        "comparisons": comparisons,
        "symptomComparisons": symptom_diffs,
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }


def compare_recent_vs_prior(user_id: str, window_days: int = 60) -> Dict[str, Any]:
    """Automatically compare the most recent window_days against the same span before it.

    Convenience endpoint — no need for the client to calculate dates.
    """
    today = date.today()
    period_b_end = today
    period_b_start = today - timedelta(days=window_days)
    period_a_end = period_b_start - timedelta(days=1)
    period_a_start = period_a_end - timedelta(days=window_days)

    return compare_periods(user_id, period_a_start, period_a_end, period_b_start, period_b_end)
