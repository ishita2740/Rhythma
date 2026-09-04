from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from core.auth import get_current_user
# `UserService` used to be imported here and was never referenced. The
# profile this module needs comes back from `get_user_scores()` — which
# fetches it once and hands it over precisely so the dashboard does not
# read the user document a second time.
from services.health_observations_service import (
    build_analysis,
    describe_consistency,
    describe_consistency_text,
    evaluate,
    top_observation,
)
from services.prediction_service import dashboard_summary, predict
from services.scoring_service import get_user_scores, compute_cycle_stats, as_date, DEFAULT_CYCLE_LENGTH
from services.trend_service import build_trends

#: How many day-documents the trends comparison reads.
#:
#: Two cycle windows is the target. At roughly one log per day a
#: two-cycle span is ~60 documents for a typical cycle length, so 120
#: leaves headroom for long cycles without letting the read grow without
#: bound. The dashboard's own `_LOGS_LIMIT` of 10 stays where it is — it
#: feeds the scoring models, which want the most recent handful.
TRENDS_LOG_LIMIT = 120


class DashboardUser(BaseModel):
    name: str


class DashboardCycle(BaseModel):
    day: Optional[int] = None
    total: int
    nextPeriodDays: Optional[int] = None


class DashboardInsights(BaseModel):
    averageCycleLength: Optional[float] = None
    shortestCycleLength: Optional[int] = None
    longestCycleLength: Optional[int] = None
    averageBleedingDuration: Optional[float] = None
    sleepHours: Optional[str] = None
    waterAvg: Optional[float] = None


class CycleHistoryEntry(BaseModel):
    start_date: str
    cycle_length: int


class DashboardPredictionRange(BaseModel):
    """How far either side of the predicted date the real one may fall."""

    earliest: Optional[str] = None
    latest: Optional[str] = None


class DashboardFertileWindow(BaseModel):
    """The estimated fertile window, and what it must not be used for.

    ``notForContraception`` is a safety flag, not decoration: it is the
    field that tells a client this window is a statistical estimate from
    logged dates and cannot be relied on to avoid pregnancy. Declaring it
    here — with a default — is what stops it going missing silently if
    ``prediction_service`` ever stops emitting it.
    """

    start: Optional[str] = None
    end: Optional[str] = None
    isEstimate: bool = True
    notForContraception: bool = True


class DashboardObservation(BaseModel):
    """The single highest-priority observation, for the Home screen.

    Nullable: a brand-new user with no logs has nothing to say yet, and a
    client written before this field existed must keep working, so it is
    additive and optional rather than a required object.
    """

    code: str
    severity: str
    title: str
    body: str
    titleKey: str
    bodyKey: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    isMedicalAdvice: bool = False
    disclaimerKey: str


class DashboardPrediction(BaseModel):
    """The compact prediction summary the Home screen renders.

    Mirrors ``services/prediction_service.py::dashboard_summary``. Fields
    are Optional because a new user with no logged period has no anchor
    date; ``isOverdue`` defaults to False in that case.

    Added alongside ``cycle``, not inside it: ``cycle.nextPeriodDays``
    keeps its existing clamped-at-zero meaning so clients written before
    this field existed are unaffected, while ``daysUntilNextPeriod`` here
    is the honest signed value.

    This class was declared twice in this module (issue #381), ~40 lines
    apart. Python kept the second, so the typed ``predictedRange`` /
    ``fertileWindow`` and the non-null ``confidence`` / ``estimateSource``
    defaults below never reached ``DashboardResponse`` — they lived on the
    copy that was silently discarded, and ``/docs`` published the two
    nested objects as untyped dicts. The two docstrings are merged here;
    ``test_dashboard_prediction_schema.py`` asserts the served schema so a
    second declaration cannot quietly win again.
    """

    nextPeriodDate: Optional[str] = None
    daysUntilNextPeriod: Optional[int] = Field(
        None, description="Negative when the period is late; not clamped."
    )
    isOverdue: bool = False
    daysOverdue: int = 0
    phase: str = "unknown"
    #: Defaults are the most conservative value, not ``None``. A client
    #: reading ``prediction.confidence`` to decide how firmly to present a
    #: date should never be handed a null it has to guess about.
    confidence: str = "low"
    estimateSource: str = "population_default"
    predictedRange: DashboardPredictionRange = Field(
        default_factory=DashboardPredictionRange
    )
    fertileWindow: DashboardFertileWindow = Field(
        default_factory=DashboardFertileWindow
    )


class DashboardResponse(BaseModel):
    user: DashboardUser
    cycle: DashboardCycle
    insights: DashboardInsights
    hasEnoughDataForInsights: bool
    loggedCycleCount: int
    cycleHistory: list[CycleHistoryEntry]
    symptomFrequency: dict[str, float]
    recentStressLevel: Optional[int] = None
    #: Highest-severity factual observation about the user's logged data,
    #: computed from the logs already fetched above — so the Home screen
    #: needs no second round trip. Full list lives at
    #: GET /insights/{user_id}/observations.
    topObservation: Optional[DashboardObservation] = None
    #: Descriptive consistency label (consistent / slightly_variable /
    #: variable / unknown), per menstrual_insights_guidelines.md's summary
    #: card guidance — a word, not a score.
    cycleConsistency: str = "unknown"
    #: Plain-language description of cycle consistency derived from actual
    #: variability data.  References cycle lengths and spread, not a
    #: numeric score or risk label.
    cycleConsistencyDescription: str = ""
    #: "When is my next period?" — the overdue-aware prediction summary.
    #: Additive and nullable so clients written before this field existed
    #: keep working.
    prediction: Optional[DashboardPrediction] = None


router = APIRouter(tags=["Dashboard"])


class TrendWindow(BaseModel):
    """One side of the comparison, so a client can show what was compared."""

    start: str
    end: str
    days: int
    loggedDays: int


class TrendComparedWindows(BaseModel):
    previous: TrendWindow
    current: TrendWindow


class TrendStatementModel(BaseModel):
    """One comparison, as a key plus the numbers behind it.

    ``text`` is an English fallback. Clients that have a translation
    should render ``key`` and interpolate ``evidence`` themselves — the
    same contract ``ObservationModel`` states for ``titleKey``/``bodyKey``,
    which is why every number in the sentence is also in the dict.
    """

    metric: str = Field(
        ..., description="sleep, stress, or a symptom name such as cramps."
    )
    direction: str = Field(..., description="increased, decreased, or unchanged.")
    key: str
    text: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class TrendsResponse(BaseModel):
    #: The original four fields, unchanged in name, type and position, so
    #: clients written against the previous shape keep working. Everything
    #: below is additive.
    sleep: Optional[str] = None
    stress: Optional[str] = None
    symptoms: Dict[str, str] = Field(default_factory=dict)
    notEnoughData: bool = False

    basis: Optional[str] = Field(
        None,
        description=(
            "What was actually compared: `cycle` when two cycle windows "
            "were reconstructed from logged flow, `recent_logs` when no "
            "period could be found and the logged days were split in half "
            "instead. Null when there was nothing to compare."
        ),
    )
    comparedWindows: Optional[TrendComparedWindows] = Field(
        None,
        description=(
            "The two windows the statements describe. Present so a client "
            "can show the reader which spans are being compared rather "
            "than asking them to trust a bare sentence."
        ),
    )
    trends: List[TrendStatementModel] = Field(
        default_factory=list,
        description=(
            "Every statement, with a localization key and the values that "
            "produced it."
        ),
    )
    disclaimer: str = ""
    disclaimerKey: str = ""


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get dashboard data",
    description="Returns the user's current cycle summary, factual cycle statistics (average/shortest/longest cycle length, average bleeding duration), sleep average, cycle history, symptom frequencies, and recent stress level. All insight data is computed server-side directly from CycleLog history.",
)
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]

    score_data = get_user_scores(user_id)
    logs = score_data["logs"]

    avg_cycle_length = DEFAULT_CYCLE_LENGTH
    cycle_day = None
    next_period_days = None

    if logs:
        most_recent_start = as_date(logs[0].get("start_date"))
        if most_recent_start:
            raw_day = (date.today() - most_recent_start).days + 1
            cycle_day = max(1, raw_day)

        if len(logs) >= 2:
            deltas = []
            for i in range(len(logs) - 1):
                newer = as_date(logs[i].get("start_date"))
                older = as_date(logs[i + 1].get("start_date"))
                if newer and older and (newer - older).days > 0:
                    deltas.append((newer - older).days)
            if deltas:
                avg_cycle_length = round(sum(deltas) / len(deltas))

        if cycle_day is not None:
            next_period_days = max(avg_cycle_length - cycle_day, 0)

    avg_sleep = None
    sleep_values = [l.get("sleep_hours") for l in logs if l.get("sleep_hours") is not None]
    if sleep_values:
        avg_sleep = round(sum(sleep_values) / len(sleep_values), 1)

    avg_water = None
    water_values = [l.get("water_intake") for l in logs if l.get("water_intake") is not None]
    if water_values:
        avg_water = round(sum(water_values) / len(water_values), 1)

    cycle_history = []
    ordered = list(reversed(logs))
    for i in range(1, len(ordered)):
        newer = as_date(ordered[i].get("start_date"))
        older = as_date(ordered[i - 1].get("start_date"))
        if newer and older and (newer - older).days > 0:
            cycle_history.append({
                "start_date": newer.isoformat(),
                "cycle_length": (newer - older).days,
            })

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

    # Observations reuse the logs already fetched above rather than
    # re-querying Firestore, so the Home screen still costs one round trip
    # and one read path. `build_analysis` is called separately from
    # `evaluate` only because the consistency label needs the analysis
    # object; both are pure functions over the same list.
    observations = evaluate(logs)
    highest = top_observation(observations)
    analysis = build_analysis(logs)
    consistency = describe_consistency(analysis)
    consistency_text = describe_consistency_text(analysis)

    # The prediction summary reuses the same logs (and the profile already
    # fetched for scoring) so the Home screen needs no extra read. It is the
    # overdue-aware "when is my next period?" answer; the legacy clamped
    # `cycle.nextPeriodDays` above is kept untouched for existing clients.
    prediction = dashboard_summary(
        predict(logs, profile=score_data.get("profile"), today=date.today())
    )

    cycle_stats = compute_cycle_stats(logs)

    return {
        "user": {
            "name": current_user.get("username") or "User"
        },
        "cycle": {
            "day": cycle_day,
            "total": avg_cycle_length,
            "nextPeriodDays": next_period_days,
        },
        "insights": {
            "averageCycleLength": cycle_stats["average_cycle_length"],
            "shortestCycleLength": cycle_stats["shortest_cycle_length"],
            "longestCycleLength": cycle_stats["longest_cycle_length"],
            "averageBleedingDuration": cycle_stats["average_bleeding_duration"],
            "sleepHours": f"{avg_sleep}h" if avg_sleep is not None else None,
            "waterAvg": avg_water,
        },
        "hasEnoughDataForInsights": score_data["has_enough_data_for_insights"],
        "loggedCycleCount": score_data["logged_cycle_count"],
        "cycleHistory": cycle_history,
        "symptomFrequency": symptom_frequency,
        "recentStressLevel": recent_stress_level,
        "topObservation": highest.to_dict() if highest else None,
        "cycleConsistency": consistency,
        "cycleConsistencyDescription": consistency_text,
        "prediction": prediction,
    }


@router.get(
    "/dashboard/trends",
    response_model=TrendsResponse,
    summary="Get simple trends for sleep, stress and symptoms",
    description=(
        "Compares two windows of the user's logged data and returns "
        "plain-language trend statements for sleep, stress and symptom "
        "frequencies.\n\n"
        "`basis` says what was compared. When at least two periods can be "
        "reconstructed from logged flow it is `cycle`, and the windows run "
        "from one period start to the day before the next — the cycle "
        "currently in progress is excluded, because averaging a few days "
        "of a new cycle against a whole previous one is a comparison "
        "between a sample and a population. When no period has been "
        "logged it is `recent_logs`, and the logged days are split in half "
        "by count instead; the field exists so the response never claims a "
        "cycle comparison it did not make.\n\n"
        "Every statement also appears in `trends` with a stable `key` and "
        "an `evidence` dict, matching the contract "
        "`/insights/{user_id}/observations` uses: `text` is an English "
        "fallback and a client with a translation should render the key.\n\n"
        "Returns `notEnoughData=true` when there are not two comparable "
        "windows, or when neither window recorded a value for anything."
    ),
)
async def get_trends(current_user: dict = Depends(get_current_user)):
    """Trends for the authenticated user.

    This route used to do the comparison itself, on ``logs[0]`` against
    ``logs[1]`` — two adjacent *day* documents, since ``upsert_log`` keys
    one document per calendar day — while describing the result as a
    period-over-period average (issue #484). The arithmetic now lives in
    ``services/trend_service.py``, where it operates on reconstructed
    cycle windows and can be tested without a request.

    ``get_logs_for_user``'s default limit is deliberately raised here:
    the default of 10 documents cannot hold two cycle windows for anyone
    who logs more than a handful of days per cycle, so the window
    reconstruction would fall back to ``recent_logs`` for exactly the
    users with the most data.
    """
    user_id = current_user["id"]
    # Reuse the same scoring_service-backed logs the dashboard uses.
    from services.scoring_service import CycleService

    logs = CycleService.get_logs_for_user(user_id, limit=TRENDS_LOG_LIMIT)

    return build_trends(logs, today=date.today())
