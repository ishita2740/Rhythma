"""Health Export Summary service.

Generates structured health summary documents from a user's logged data,
suitable for sharing with healthcare providers or for personal records.

Pulls cycle statistics, symptom patterns, trend data, and scoring into a
single organised payload.  No clinical interpretation is added — the
summary reports what was logged and computed statistics, never a diagnosis.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from services.firestore_service import CycleService, UserService
from services.scoring_service import compute_cycle_stats, get_user_scores
from services.trend_service import build_trends, to_day_records, CANONICAL_SYMPTOMS

DISCLAIMER = (
    "This report summarises data you logged in Rhythma. It is not a "
    "medical diagnosis and should not be used as one. Share it with your "
    "healthcare provider as context, not as a clinical assessment."
)
DISCLAIMER_KEY = "export_summary.disclaimer"

#: How many cycle logs to pull for the summary.
_SUMMARY_LOG_LIMIT = 30

#: How far back to look for symptom/sleep/stress patterns in days.
_PATTERN_WINDOW_DAYS = 90


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _symptom_frequency(logs: List[Dict[str, Any]]) -> Dict[str, float]:
    """Percentage of logged days each canonical symptom appeared."""
    days_with_symptoms = [l for l in logs if l.get("symptoms")]
    if not days_with_symptoms:
        return {}
    return {
        s: round(
            sum(1 for l in days_with_symptoms if s in (l.get("symptoms") or []))
            / len(days_with_symptoms),
            2,
        )
        for s in CANONICAL_SYMPTOMS
    }


def _sleep_summary(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = [l["sleep_hours"] for l in logs if l.get("sleep_hours") is not None]
    if not values:
        return {"average": None, "min": None, "max": None, "sampleCount": 0}
    return {
        "average": round(sum(values) / len(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "sampleCount": len(values),
    }


def _stress_summary(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = [l["stress_level"] for l in logs if l.get("stress_level") is not None]
    if not values:
        return {"average": None, "min": None, "max": None, "sampleCount": 0}
    return {
        "average": round(sum(values) / len(values), 1),
        "min": min(values),
        "max": max(values),
        "sampleCount": len(values),
    }


def _mood_summary(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = [l["mood_score"] for l in logs if l.get("mood_score") is not None]
    if not values:
        return {"average": None, "sampleCount": 0}
    return {
        "average": round(sum(values) / len(values), 1),
        "sampleCount": len(values),
    }


def _bleeding_pattern(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summary of flow intensity distribution across logged days."""
    from services.trend_service import BLEEDING_FLOWS
    counts: Dict[str, int] = {}
    for log in logs:
        flow = (log.get("flow_intensity") or "").strip().lower()
        if flow in BLEEDING_FLOWS:
            counts[flow] = counts.get(flow, 0) + 1
    total = sum(counts.values())
    return {
        "distribution": {k: v for k, v in sorted(counts.items())},
        "totalBleedingDays": total,
    }


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_summary(user_id: str) -> Dict[str, Any]:
    """Build a complete health export summary for the user.

    Returns a structured dict with cycle stats, symptom patterns, sleep
    and stress summaries, mood data, trend comparisons, and user profile
    info — everything a provider needs in one read.
    """
    score_data = get_user_scores(user_id)
    logs = score_data["logs"]
    profile = UserService.get_user_by_id(user_id) or {}

    cycle_stats = compute_cycle_stats(logs)
    symptom_freq = _symptom_frequency(logs)
    sleep = _sleep_summary(logs)
    stress = _stress_summary(logs)
    mood = _mood_summary(logs)
    bleeding = _bleeding_pattern(logs)

    # Trend comparison (recent vs prior)
    trend_data = build_trends(logs)

    # Date range of data
    from services.scoring_service import as_date
    dates = [as_date(l.get("start_date")) for l in logs if as_date(l.get("start_date"))]
    date_range = None
    if dates:
        date_range = {
            "earliest": min(dates).isoformat(),
            "latest": max(dates).isoformat(),
        }

    # User info (redacted — no email or phone in export)
    user_info = {
        "username": profile.get("username", "User"),
        "age": profile.get("age"),
        "cycleLengthDeclared": profile.get("cycle_length"),
    }

    return {
        "generatedAt": date.today().isoformat(),
        "user": user_info,
        "dateRange": date_range,
        "cycleStatistics": {
            "averageCycleLength": cycle_stats["average_cycle_length"],
            "shortestCycleLength": cycle_stats["shortest_cycle_length"],
            "longestCycleLength": cycle_stats["longest_cycle_length"],
            "averageBleedingDuration": cycle_stats["average_bleeding_duration"],
            "loggedCycleCount": score_data["logged_cycle_count"],
            "hasEnoughData": score_data["has_enough_data_for_insights"],
        },
        "symptomFrequency": symptom_freq,
        "sleepSummary": sleep,
        "stressSummary": stress,
        "moodSummary": mood,
        "bleedingPattern": bleeding,
        "trends": {
            "basis": trend_data.get("basis"),
            "notEnoughData": trend_data.get("notEnoughData", True),
            "statements": trend_data.get("trends", []),
        },
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }


def generate_provider_brief(user_id: str) -> Dict[str, Any]:
    """A shorter, provider-focused version of the summary.

    Omits raw trend statements and mood data; keeps the clinical
    essentials: cycle stats, symptom frequencies, sleep/stress averages.
    """
    full = generate_summary(user_id)
    return {
        "generatedAt": full["generatedAt"],
        "user": full["user"],
        "dateRange": full["dateRange"],
        "cycleStatistics": full["cycleStatistics"],
        "symptomFrequency": full["symptomFrequency"],
        "sleepAverage": full["sleepSummary"].get("average"),
        "stressAverage": full["stressSummary"].get("average"),
        "bleedingDaysLogged": full["bleedingPattern"]["totalBleedingDays"],
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }
