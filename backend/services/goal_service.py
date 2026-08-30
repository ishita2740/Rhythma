"""Health Goal Tracker service.

Allows users to create wellness goals (sleep, hydration, exercise, etc.),
log daily check-ins, and track streaks and weekly completion rates.

Not a diagnosis or medical recommendation.  All goals are user-defined
wellness habits; the service records what the user *chose* to track and
how they reported doing — it never evaluates whether a goal is medically
appropriate.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.firestore_service import db, upstream_error

# ─── Collection name ────────────────────────────────────────────────────────
COLLECTION = "health_goals"
CHECKIN_COLLECTION = "goal_checkins"

# ─── Predefined goal templates ──────────────────────────────────────────────
# Users can pick from these or create custom goals.

GOAL_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "sleep_7h",
        "title": "Sleep 7+ hours",
        "category": "sleep",
        "description": "Aim for at least 7 hours of sleep each night.",
        "unit": "hours",
        "target_value": 7.0,
        "icon": "bed",
    },
    {
        "template_id": "water_8glasses",
        "title": "Drink 8 glasses of water",
        "category": "hydration",
        "description": "Stay hydrated throughout the day.",
        "unit": "glasses",
        "target_value": 8.0,
        "icon": "droplet",
    },
    {
        "template_id": "walk_30min",
        "title": "Walk 30 minutes",
        "category": "exercise",
        "description": "Get at least 30 minutes of walking.",
        "unit": "minutes",
        "target_value": 30.0,
        "icon": "footprints",
    },
    {
        "template_id": "meditate_10min",
        "title": "Meditate 10 minutes",
        "category": "mindfulness",
        "description": "Practice mindfulness for 10 minutes.",
        "unit": "minutes",
        "target_value": 10.0,
        "icon": "brain",
    },
    {
        "template_id": "fruits_veggies",
        "title": "Eat 5 servings of fruits & vegetables",
        "category": "nutrition",
        "description": "Aim for 5 servings of fruits and veggies.",
        "unit": "servings",
        "target_value": 5.0,
        "icon": "apple",
    },
]

VALID_CATEGORIES = {"sleep", "hydration", "exercise", "mindfulness", "nutrition", "custom"}
MAX_GOALS_PER_USER = 15


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _user_goals_col(user_id: str):
    """A sub-collection scoped to one user, keyed by deterministic goal id."""
    return db.collection(COLLECTION).document(user_id).collection("goals")


def _user_checkins_col(user_id: str):
    return db.collection(CHECKIN_COLLECTION).document(user_id).collection("checkins")


def _checkin_doc_id(target_date: date) -> str:
    return target_date.isoformat()


# ─── Goal CRUD ───────────────────────────────────────────────────────────────


def create_goal(
    user_id: str,
    title: str,
    category: str,
    target_value: Optional[float] = None,
    unit: Optional[str] = None,
    description: Optional[str] = None,
    template_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new wellness goal for a user.

    Returns the created goal document including its generated id.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}")

    existing = list_goals(user_id)
    if len(existing) >= MAX_GOALS_PER_USER:
        raise ValueError(f"Maximum of {MAX_GOALS_PER_USER} goals per user reached.")

    goal_id = str(uuid.uuid4())[:12]
    now = _now_utc()

    goal_data: Dict[str, Any] = {
        "id": goal_id,
        "user_id": user_id,
        "title": title.strip(),
        "category": category,
        "target_value": target_value,
        "unit": unit,
        "description": (description or "").strip(),
        "template_id": template_id,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    try:
        _user_goals_col(user_id).document(goal_id).set(goal_data)
        return goal_data
    except Exception as e:
        raise upstream_error("Creating your goal", e)


def list_goals(user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Return all goals for a user, newest first."""
    try:
        goals = []
        for doc in _user_goals_col(user_id).stream():
            data = doc.to_dict()
            if not include_inactive and not data.get("is_active", True):
                continue
            goals.append(data)
        goals.sort(key=lambda g: g.get("created_at", ""), reverse=True)
        return goals
    except Exception as e:
        raise upstream_error("Loading your goals", e)


def get_goal(user_id: str, goal_id: str) -> Optional[Dict[str, Any]]:
    """Fetch one goal by id, with ownership check."""
    try:
        doc = _user_goals_col(user_id).document(goal_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data
    except Exception as e:
        raise upstream_error("Loading your goal", e)


def deactivate_goal(user_id: str, goal_id: str) -> bool:
    """Soft-delete a goal by setting is_active=False."""
    goal = get_goal(user_id, goal_id)
    if not goal:
        return False
    try:
        _user_goals_col(user_id).document(goal_id).update({
            "is_active": False,
            "updated_at": _now_utc(),
        })
        return True
    except Exception as e:
        raise upstream_error("Deactivating your goal", e)


# ─── Daily check-ins ─────────────────────────────────────────────────────────


def log_checkin(
    user_id: str,
    goal_id: str,
    checkin_date: date,
    completed: bool = True,
    actual_value: Optional[float] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record or update a daily check-in for a goal.

    One check-in per goal per day — a second call overwrites the first.
    """
    goal = get_goal(user_id, goal_id)
    if not goal:
        raise ValueError("Goal not found or not owned by user.")

    now = _now_utc()
    doc_id = f"{goal_id}_{_checkin_doc_id(checkin_date)}"

    checkin_data: Dict[str, Any] = {
        "user_id": user_id,
        "goal_id": goal_id,
        "date": checkin_date.isoformat(),
        "completed": completed,
        "actual_value": actual_value,
        "notes": (notes or "").strip() if notes else "",
        "created_at": now,
        "updated_at": now,
    }

    try:
        doc_ref = _user_checkins_col(user_id).document(doc_id)
        existing = doc_ref.get()
        if existing.exists:
            checkin_data["created_at"] = existing.to_dict().get("created_at", now)
            checkin_data["updated_at"] = now
        doc_ref.set(checkin_data)
        return checkin_data
    except Exception as e:
        raise upstream_error("Saving your check-in", e)


def get_checkins_for_date(user_id: str, target_date: date) -> List[Dict[str, Any]]:
    """All check-ins for a given date."""
    try:
        results = []
        for doc in _user_checkins_col(user_id).stream():
            data = doc.to_dict()
            if data.get("date") == target_date.isoformat():
                results.append(data)
        return results
    except Exception as e:
        raise upstream_error("Loading your check-ins", e)


def get_checkins_for_goal(
    user_id: str, goal_id: str, days: int = 30
) -> List[Dict[str, Any]]:
    """Recent check-ins for one goal, newest first, limited to ``days``."""
    cutoff = date.today() - timedelta(days=days)
    try:
        results = []
        for doc in _user_checkins_col(user_id).stream():
            data = doc.to_dict()
            if data.get("goal_id") != goal_id:
                continue
            if data.get("date", "") < cutoff.isoformat():
                continue
            results.append(data)
        results.sort(key=lambda c: c.get("date", ""), reverse=True)
        return results
    except Exception as e:
        raise upstream_error("Loading check-in history", e)


# ─── Streak & analytics ──────────────────────────────────────────────────────


def compute_streak(user_id: str, goal_id: str) -> Dict[str, Any]:
    """Compute the current and longest streak for a goal.

    A streak is a consecutive run of completed=True days ending today
    or yesterday (yesterday counts because today may not be logged yet).
    """
    try:
        all_checkins = []
        for doc in _user_checkins_col(user_id).stream():
            data = doc.to_dict()
            if data.get("goal_id") == goal_id:
                all_checkins.append(data)

        completed_dates = sorted(
            set(
                data["date"]
                for data in all_checkins
                if data.get("completed")
            )
        )

        if not completed_dates:
            return {"current_streak": 0, "longest_streak": 0, "total_completed": 0}

        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        # Current streak: count backwards from today/yesterday
        current_streak = 0
        check_date = date.today()
        if today not in completed_dates:
            check_date = date.today() - timedelta(days=1)
            if check_date.isoformat() not in completed_dates:
                return {
                    "current_streak": 0,
                    "longest_streak": _longest_streak(completed_dates),
                    "total_completed": len(completed_dates),
                }

        while check_date.isoformat() in completed_dates:
            current_streak += 1
            check_date -= timedelta(days=1)

        longest = _longest_streak(completed_dates)

        return {
            "current_streak": current_streak,
            "longest_streak": max(current_streak, longest),
            "total_completed": len(completed_dates),
        }
    except Exception as e:
        raise upstream_error("Computing streak", e)


def _longest_streak(sorted_dates_iso: List[str]) -> int:
    """Longest consecutive run in a sorted list of ISO date strings."""
    if not sorted_dates_iso:
        return 0
    longest = 1
    run = 1
    for i in range(1, len(sorted_dates_iso)):
        prev = date.fromisoformat(sorted_dates_iso[i - 1])
        curr = date.fromisoformat(sorted_dates_iso[i])
        if (curr - prev).days == 1:
            run += 1
            longest = max(longest, run)
        elif (curr - prev).days > 1:
            run = 1
    return longest


def weekly_summary(user_id: str) -> Dict[str, Any]:
    """Completion rates for each active goal over the past 7 days."""
    today = date.today()
    start = today - timedelta(days=6)

    try:
        goals = list_goals(user_id)
        goal_summaries = []

        for goal in goals:
            completed_count = 0
            total_days = 7
            for doc in _user_checkins_col(user_id).stream():
                data = doc.to_dict()
                if (
                    data.get("goal_id") == goal["id"]
                    and data.get("completed")
                    and start.isoformat() <= data.get("date", "") <= today.isoformat()
                ):
                    completed_count += 1

            rate = round(completed_count / total_days * 100) if total_days > 0 else 0
            goal_summaries.append({
                "goal_id": goal["id"],
                "title": goal["title"],
                "category": goal["category"],
                "completed_days": completed_count,
                "total_days": total_days,
                "completion_rate": rate,
            })

        overall = (
            round(sum(g["completed_days"] for g in goal_summaries) / 7)
            if goal_summaries
            else 0
        )

        return {
            "period": {"start": start.isoformat(), "end": today.isoformat()},
            "goals": goal_summaries,
            "overall_completion_rate": overall,
        }
    except Exception as e:
        raise upstream_error("Computing weekly summary", e)
