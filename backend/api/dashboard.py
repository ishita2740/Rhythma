from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from core.auth import get_current_user
from services.firestore_service import CycleService
from models.cvi_model import predict_cvi, risk_level
from models.mhs_model import predict_mhs

router = APIRouter(tags=["Dashboard"])

_DEFAULT_CYCLE_LENGTH = 28
_FLOW_INTENSITY_TO_SCORE = {"light": 1, "medium": 2, "heavy": 3}


def _as_date(value: Any) -> Optional[date]:
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


def _build_model_features(logs_newest_first: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert raw CycleLog documents into the feature shape the CVI/MHS
    models expect (see models/cvi_model.py and models/mhs_model.py)."""
    features = []
    for i, log in enumerate(logs_newest_first):
        start = _as_date(log.get("start_date"))
        end = _as_date(log.get("end_date"))

        cycle_length = None
        if i + 1 < len(logs_newest_first):
            older_start = _as_date(logs_newest_first[i + 1].get("start_date"))
            if start and older_start:
                cycle_length = (start - older_start).days

        flow_duration = (end - start).days + 1 if start and end else 5
        flow_intensity = _FLOW_INTENSITY_TO_SCORE.get(
            (log.get("flow_intensity") or "").lower(), 2
        )

        features.append({
            "cycle_length": cycle_length or _DEFAULT_CYCLE_LENGTH,
            "flow_duration": flow_duration,
            "flow_intensity": flow_intensity,
            "symptom_count": len(log.get("symptoms") or []),
            "stress_avg": log.get("stress_level") or 2.5,
            "sleep_avg": log.get("sleep_hours") or 7.0,
        })
    return features


@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]

    # Most recent first, matches what CycleService.get_logs_for_user returns.
    logs = CycleService.get_logs_for_user(user_id, limit=10)

    avg_cycle_length = _DEFAULT_CYCLE_LENGTH
    cycle_day = None
    next_period_days = None

    if logs:
        most_recent_start = _as_date(logs[0].get("start_date"))
        if most_recent_start:
            cycle_day = (date.today() - most_recent_start).days + 1

        if len(logs) >= 2:
            deltas = []
            for i in range(len(logs) - 1):
                newer = _as_date(logs[i].get("start_date"))
                older = _as_date(logs[i + 1].get("start_date"))
                if newer and older and (newer - older).days > 0:
                    deltas.append((newer - older).days)
            if deltas:
                avg_cycle_length = round(sum(deltas) / len(deltas))

        if cycle_day is not None:
            next_period_days = max(avg_cycle_length - cycle_day, 0)

    features = _build_model_features(logs)
    mhs = predict_mhs(features)
    cvi = predict_cvi(features)

    avg_sleep = None
    sleep_values = [l.get("sleep_hours") for l in logs if l.get("sleep_hours") is not None]
    if sleep_values:
        avg_sleep = round(sum(sleep_values) / len(sleep_values), 1)

    # Per-cycle length history (oldest first, so a client can plot it
    # left-to-right as a trend line) — the gap in days between each
    # consecutive pair of logged start_dates. `logs` is newest-first, so
    # walk it in reverse.
    cycle_history = []
    ordered = list(reversed(logs))
    for i in range(1, len(ordered)):
        newer = _as_date(ordered[i].get("start_date"))
        older = _as_date(ordered[i - 1].get("start_date"))
        if newer and older and (newer - older).days > 0:
            cycle_history.append({
                "start_date": newer.isoformat(),
                "cycle_length": (newer - older).days,
            })

    # Symptom frequency: fraction of logs-with-any-symptom-data that
    # recorded each canonical symptom. Computed here (not left for the
    # client to derive from local Hive history) so Insights only ever
    # needs this one endpoint.
    canonical_symptoms = ["cramps", "headache", "bloating", "acne"]
    logs_with_symptoms = [l for l in logs if l.get("symptoms")]
    symptom_frequency = {
        s: round(
            sum(1 for l in logs_with_symptoms if s in (l.get("symptoms") or [])) / len(logs_with_symptoms),
            2,
        )
        for s in canonical_symptoms
    } if logs_with_symptoms else {}

    recent_stress_level = logs[0].get("stress_level") if logs else None

    return {
        "user": {
            "name": current_user.get("username", "User")
        },
        "cycle": {
            "day": cycle_day,
            "total": avg_cycle_length,
            "nextPeriodDays": next_period_days,
        },
        "insights": {
            "mhs": mhs,
            "cvi": risk_level(cvi).capitalize() if cvi is not None else None,
            "sleepHours": f"{avg_sleep}h" if avg_sleep is not None else None,
        },
        # Lets the client tell "no data yet" apart from "computed a low
        # score" — the CVI/MHS models need >=3 / >=2 logs respectively to
        # return a real number rather than None.
        "hasEnoughDataForInsights": len(logs) >= 3,
        "loggedCycleCount": len(logs),
        # Used by Insights' trend chart. Empty until there are at least 2
        # logged cycles to compute a gap between.
        "cycleHistory": cycle_history,
        # Used by Insights' symptom-pattern bars and the "recent stress"
        # mini-card — both computed here so the client never falls back to
        # deriving anything from local Hive history for this screen.
        "symptomFrequency": symptom_frequency,
        "recentStressLevel": recent_stress_level,
    }