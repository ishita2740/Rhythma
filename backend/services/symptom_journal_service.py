"""Symptom Pattern Analyzer service.

Lets users log detailed symptom entries with severity, location, triggers,
and notes — then aggregates entries into pattern reports: frequency by
day-of-week, severity trends, co-occurring symptoms, and trigger
correlations.

Not a diagnosis.  These are descriptions of what the user logged.
"""

from __future__ import annotations

import statistics
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.firestore_service import db, upstream_error

COLLECTION = "symptom_entries"

# Canonical symptom categories used across the app
SYMPTOM_CATEGORIES = [
    "cramps", "headache", "bloating", "acne", "fatigue",
    "backache", "breast_tenderness", "nausea", "insomnia", "mood_swings",
]

SEVERITY_LEVELS = {"mild", "moderate", "severe"}

# Common triggers users can tag
TRIGGER_OPTIONS = [
    "stress", "poor_sleep", "dehydration", "caffeine",
    "alcohol", "heavy_meal", "exercise", "none",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _entries_col(user_id: str):
    return db.collection(COLLECTION).document(user_id).collection("entries")


def _entry_doc_id() -> str:
    return str(uuid.uuid4())[:12]


# ─── CRUD ────────────────────────────────────────────────────────────────────


def create_entry(
    user_id: str,
    symptom: str,
    severity: str,
    entry_date: date,
    location: Optional[str] = None,
    triggers: Optional[List[str]] = None,
    notes: Optional[str] = None,
    mood_score: Optional[int] = None,
) -> Dict[str, Any]:
    """Log a symptom entry."""
    if symptom not in SYMPTOM_CATEGORIES:
        raise ValueError(f"Invalid symptom '{symptom}'.")
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"Severity must be one of {SEVERITY_LEVELS}.")
    if mood_score is not None and not (1 <= mood_score <= 5):
        raise ValueError("mood_score must be between 1 and 5.")

    entry_id = _entry_doc_id()
    now = _now_utc()

    entry: Dict[str, Any] = {
        "id": entry_id,
        "user_id": user_id,
        "symptom": symptom,
        "severity": severity,
        "date": entry_date.isoformat(),
        "location": (location or "").strip() or None,
        "triggers": [t for t in (triggers or []) if t in TRIGGER_OPTIONS],
        "notes": (notes or "").strip()[:500],
        "mood_score": mood_score,
        "created_at": now,
        "updated_at": now,
    }

    try:
        _entries_col(user_id).document(entry_id).set(entry)
        return entry
    except Exception as e:
        raise upstream_error("Saving symptom entry", e)


def list_entries(
    user_id: str,
    limit: int = 50,
    symptom: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Query entries with optional filters, newest first."""
    try:
        results = []
        for doc in _entries_col(user_id).stream():
            data = doc.to_dict()
            if symptom and data.get("symptom") != symptom:
                continue
            d = data.get("date", "")
            if start_date and d < start_date.isoformat():
                continue
            if end_date and d > end_date.isoformat():
                continue
            results.append(data)
        results.sort(key=lambda e: e.get("date", ""), reverse=True)
        return results[:limit]
    except Exception as e:
        raise upstream_error("Loading symptom entries", e)


def get_entry(user_id: str, entry_id: str) -> Optional[Dict[str, Any]]:
    """One entry by id, ownership checked."""
    try:
        doc = _entries_col(user_id).document(entry_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data
    except Exception as e:
        raise upstream_error("Loading symptom entry", e)


def delete_entry(user_id: str, entry_id: str) -> bool:
    """Delete a single entry."""
    entry = get_entry(user_id, entry_id)
    if not entry:
        return False
    try:
        _entries_col(user_id).document(entry_id).delete()
        return True
    except Exception as e:
        raise upstream_error("Deleting symptom entry", e)


# ─── Pattern Analysis ────────────────────────────────────────────────────────


def frequency_report(user_id: str, days: int = 90) -> Dict[str, Any]:
    """How often each symptom was logged in the past N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        counts: Counter = Counter()
        for doc in _entries_col(user_id).stream():
            data = doc.to_dict()
            if data.get("date", "") >= cutoff:
                counts[data.get("symptom", "unknown")] += 1

        total = sum(counts.values())
        items = [
            {"symptom": s, "count": c, "percentage": round(c / total * 100) if total else 0}
            for s, c in counts.most_common()
        ]
        return {"days": days, "total_entries": total, "symptoms": items}
    except Exception as e:
        raise upstream_error("Computing frequency report", e)


def severity_trend(user_id: str, symptom: str, days: int = 60) -> Dict[str, Any]:
    """Weekly average severity for one symptom over the past N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    severity_map = {"mild": 1, "moderate": 2, "severe": 3}

    try:
        by_week: Dict[str, List[int]] = defaultdict(list)
        for doc in _entries_col(user_id).stream():
            data = doc.to_dict()
            if data.get("symptom") != symptom:
                continue
            if data.get("date", "") < cutoff:
                continue
            sev = severity_map.get(data.get("severity", ""), 0)
            if sev:
                # ISO week key
                dt = date.fromisoformat(data["date"])
                week_key = dt.strftime("%Y-W%U")
                by_week[week_key].append(sev)

        weeks = sorted(by_week.keys())
        trend = [
            {"week": w, "avg_severity": round(statistics.fmean(by_week[w]), 2), "entries": len(by_week[w])}
            for w in weeks
        ]

        # Direction
        direction = "stable"
        if len(trend) >= 2:
            first_half = statistics.fmean([t["avg_severity"] for t in trend[:len(trend)//2]])
            second_half = statistics.fmean([t["avg_severity"] for t in trend[len(trend)//2:]])
            diff = second_half - first_half
            if diff > 0.3:
                direction = "worsening"
            elif diff < -0.3:
                direction = "improving"

        return {"symptom": symptom, "days": days, "direction": direction, "weekly_trend": trend}
    except Exception as e:
        raise upstream_error("Computing severity trend", e)


def co_occurrence(user_id: str, days: int = 90) -> Dict[str, Any]:
    """Which symptoms appear on the same days most often."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        day_symptoms: Dict[str, set] = defaultdict(set)
        for doc in _entries_col(user_id).stream():
            data = doc.to_dict()
            if data.get("date", "") >= cutoff:
                day_symptoms[data["date"]].add(data.get("symptom", ""))

        pair_counts: Counter = Counter()
        for symptoms in day_symptoms.values():
            symptom_list = sorted(symptoms)
            for i in range(len(symptom_list)):
                for j in range(i + 1, len(symptom_list)):
                    pair_counts[(symptom_list[i], symptom_list[j])] += 1

        pairs = [
            {"symptom_a": a, "symptom_b": b, "co_occurring_days": c}
            for (a, b), c in pair_counts.most_common(10)
        ]
        return {"days": days, "total_days_logged": len(day_symptoms), "top_pairs": pairs}
    except Exception as e:
        raise upstream_error("Computing co-occurrence", e)


def trigger_analysis(user_id: str, symptom: Optional[str] = None, days: int = 90) -> Dict[str, Any]:
    """How often each trigger appears across entries, optionally filtered by symptom."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        trigger_counts: Counter = Counter()
        total = 0
        for doc in _entries_col(user_id).stream():
            data = doc.to_dict()
            if data.get("date", "") < cutoff:
                continue
            if symptom and data.get("symptom") != symptom:
                continue
            total += 1
            for t in data.get("triggers", []):
                trigger_counts[t] += 1

        items = [
            {"trigger": t, "count": c, "percentage": round(c / total * 100) if total else 0}
            for t, c in trigger_counts.most_common()
        ]
        return {
            "days": days,
            "symptom_filter": symptom,
            "total_entries": total,
            "triggers": items,
        }
    except Exception as e:
        raise upstream_error("Computing trigger analysis", e)
