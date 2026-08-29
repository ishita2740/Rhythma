from fastapi import APIRouter, Depends, HTTPException, Query, status
from core.auth import get_current_user
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.cycle_validation import (
    FLOW_INTENSITIES,
    MOODS,
    loggable_values,
    normalize_choice,
    normalize_notes,
    normalize_symptoms,
    validate_end_date,
    validate_sleep_hours,
    validate_start_date,
    validate_stress_level,
)
from services.firestore_service import CycleService, UserService
from services.prediction_service import DEFAULT_FORECAST_HORIZON, predict


class _LoggableFields(BaseModel):
    """The fields a cycle log carries, and the rules they obey (issue #347).

    Shared by ``CycleLog`` and ``CycleLogUpdate`` because the POST and the
    PUT write to the same document and had the same gap. Keeping the
    validators in one base is what stops a rule being added to one route
    and forgotten on the other — the failure mode ``core/password_policy``
    was written to avoid on register-vs-reset.

    The rules themselves live in ``core/cycle_validation``; these are only
    the hooks that attach them. Validators raise ``ValueError``, which
    Pydantic reports through the standard 422 envelope with the offending
    field's location attached, so a client is told *which* field it got
    wrong rather than being handed a bare rejection.
    """

    end_date: Optional[date] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("flow_intensity")
    @classmethod
    def _check_flow(cls, value):
        return normalize_choice(value, FLOW_INTENSITIES, "flow_intensity")

    @field_validator("mood")
    @classmethod
    def _check_mood(cls, value):
        return normalize_choice(value, MOODS, "mood")

    @field_validator("symptoms")
    @classmethod
    def _check_symptoms(cls, value):
        return normalize_symptoms(value)

    @field_validator("sleep_hours")
    @classmethod
    def _check_sleep(cls, value):
        return validate_sleep_hours(value)

    @field_validator("stress_level")
    @classmethod
    def _check_stress(cls, value):
        return validate_stress_level(value)

    @field_validator("notes")
    @classmethod
    def _check_notes(cls, value):
        return normalize_notes(value)


class CycleLog(_LoggableFields):
    start_date: date

    @field_validator("start_date")
    @classmethod
    def _check_start(cls, value):
        return validate_start_date(value)

    @model_validator(mode="after")
    def _check_range(self):
        # Cross-field, so it cannot be a field validator: an inverted range
        # is a property of the pair, not of either date on its own.
        validate_end_date(self.start_date, self.end_date)
        return self


class CycleLogUpdate(_LoggableFields):
    """A partial update to an existing log.

    ``end_date`` is bounded on its own here — there is no ``start_date`` in
    the payload to compare it against, since the route addresses an
    existing document by id. It is still checked against the *stored*
    start date in :func:`update_cycle_log`, where that value is available.

    Every field defaults to ``None``, which is also what an explicit
    ``null`` parses to, so this model on its own cannot distinguish "not
    sent" from "sent empty". :func:`_submitted_fields` reads
    ``model_fields_set`` to recover the difference — see the note there
    for why it matters (issue #549).
    """

    @field_validator("end_date")
    @classmethod
    def _check_end_alone(cls, value):
        return validate_end_date(None, value)


class CycleLogResponse(BaseModel):
    message: str
    id: str
    data: CycleLog


class CycleHistoryEntry(BaseModel):
    """One stored log, as it comes back from Firestore.

    Every field but ``id`` is optional because a log is built up over
    time — the Home screen's quick-log tiles write a single field for the
    day, so a document holding only ``flow_intensity`` is normal, not
    corrupt. ``model_config`` allows the extra keys Firestore carries
    (``user_id``, ``created_at``, ``updated_at``) through untouched, so
    typing the response does not silently drop fields the clients already
    read.
    """

    model_config = {"extra": "allow"}

    id: str
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None


class CycleHistoryPage(BaseModel):
    """Where this page sits, and whether there is another one."""

    limit: int = Field(..., description="How many entries were requested.")
    offset: int = Field(..., description="How many entries were skipped.")
    count: int = Field(..., description="How many entries this page holds.")
    hasMore: bool = Field(
        ...,
        description=(
            "True when at least one more entry exists past this page. "
            "Derived from fetching one extra document rather than from a "
            "count query, so paging costs no extra round trip."
        ),
    )
    nextOffset: Optional[int] = Field(
        None,
        description="Offset for the next page, or null when this is the last one.",
    )


class CycleHistoryResponse(BaseModel):
    message: str
    entries: List[CycleHistoryEntry]
    page: CycleHistoryPage


class CycleLogUpdateResponse(BaseModel):
    message: str
    id: str
    updated_fields: dict


class CycleLogDeleteResponse(BaseModel):
    message: str
    id: str


class CycleLengthEstimateModel(BaseModel):
    days: int = Field(..., description="Estimated cycle length in days.")
    source: str = Field(
        ...,
        description=(
            "Where the estimate came from: logged_history, "
            "declared_cycle_length (from onboarding), or population_default."
        ),
    )
    confidence: str = Field(..., description="high, medium, or low.")
    sampleSize: int = Field(
        ..., description="Number of past cycles the estimate is based on."
    )
    spreadDays: float = Field(
        ..., description="Typical variation between this user's cycles, in days."
    )
    excludedCycleLengths: List[int] = Field(
        default_factory=list,
        description=(
            "Cycle lengths discarded as implausible or as statistical "
            "outliers, listed so the estimate is auditable."
        ),
    )


class PredictedRange(BaseModel):
    earliest: Optional[str] = None
    latest: Optional[str] = None


class OvulationEstimate(BaseModel):
    date: Optional[str] = None
    isEstimate: bool = True


class FertileWindowEstimate(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    isEstimate: bool = True
    notForContraception: bool = True


class PredictionResponse(BaseModel):
    today: str
    cycleLength: CycleLengthEstimateModel
    lastPeriodStart: Optional[str] = None
    currentCycleDay: Optional[int] = None
    phase: str
    nextPeriodDate: Optional[str] = None
    daysUntilNextPeriod: Optional[int] = Field(
        None,
        description=(
            "Negative when the period is late. Deliberately not clamped at "
            "zero — 'due today' and 'five days late' are different answers."
        ),
    )
    isOverdue: bool = False
    daysOverdue: int = 0
    predictedRange: PredictedRange
    ovulation: OvulationEstimate
    fertileWindow: FertileWindowEstimate
    upcomingPeriods: List[str] = Field(default_factory=list)
    confidence: str
    disclaimer: str


router = APIRouter(tags=["Cycle Tracking"])


def _submitted_fields(model: BaseModel, *, skip: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """The fields the request body actually carried, values included.

    ``model_dump()`` cannot tell an omitted field from one explicitly sent
    as ``null`` — both come back as ``None`` — so the ``if v is not None``
    filter that used to stand in for PATCH semantics also made a clearing
    impossible to express (issue #549). A user could correct a mis-tapped
    flow intensity but never remove it, and ``{"notes": null}`` was
    answered with "No fields provided for update", which was not true.

    ``model_fields_set`` records which keys were present in the JSON, so
    the two cases separate cleanly: a key that is absent is left alone, a
    key that is present and ``null`` is a request to remove it. Both go
    down to ``CycleService``, which turns the second into Firestore's
    ``DELETE_FIELD``.

    Note this reads the *submitted* keys, not the *changed* ones. Sending
    a field its stored value is still a write, and should be: a client
    that resends the day's whole state is describing the day, not diffing
    it.
    """
    dumped = model.model_dump()
    return {
        key: value
        for key, value in dumped.items()
        if key in model.model_fields_set and key not in skip
    }


def _as_date(value: Any) -> Optional[date]:
    """Firestore hands dates back as ``datetime``; the validators want ``date``.

    Mirrors ``scoring_service.as_date``. Not imported from there because
    that module is the scoring pipeline and this is a route concern, and a
    route reaching into the scoring service for a date cast would be the
    kind of dependency that makes the scoring service hard to change.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


@router.get(
    "/loggable-values",
    summary="The values this server accepts in a cycle log",
    description=(
        "The flow intensities, moods and symptom suggestions a client may "
        "offer, and the bounds on the numeric and free-text fields.\n\n"
        "Served so the options a user is shown come from the same place as "
        "the rules she is judged against, rather than being retyped in each "
        "client and going stale — the same reasoning behind "
        "`GET /auth/password-requirements`.\n\n"
        "`symptomsAreOpenEnded` is true: `knownSymptoms` is the suggested "
        "chip set, not a closed list, and a symptom outside it is accepted "
        "so long as it is within the length and count limits."
    ),
)
async def get_loggable_values(current_user: dict = Depends(get_current_user)):
    """Authenticated only because every other route on this router is.

    Nothing here is sensitive — it is the same information the clients
    already hardcode — but an unauthenticated hole in an otherwise
    authenticated router is the sort of thing that gets copied.
    """
    return loggable_values()


@router.post(
    "/log",
    response_model=CycleLogResponse,
    summary="Log a cycle entry",
    description=(
        "Creates or updates a cycle log entry for the specified start "
        "date. Partial payloads (e.g. only `flow_intensity` from a "
        "quick-log tile) are merged without overwriting previously saved "
        "fields for that day.\n\n"
        "A field sent as `null` is **removed** from the stored log; a "
        "field left out of the body is left alone. The two are different "
        "requests — omitting `mood` keeps yesterday's answer, sending "
        "`\"mood\": null` takes it back — which is what lets a user undo "
        "something she logged by mistake. `\"symptoms\": []` clears the "
        "list."
    ),
)
async def log_cycle(
    log: CycleLog,
    current_user: dict = Depends(get_current_user)
):
    """Write the day, including the parts of it the user has taken back.

    Only keys the request body carried are written, so the Home screen's
    quick-log tiles still merge — sending ``flow_intensity`` alone does
    not disturb the mood logged an hour earlier.

    A key sent as ``null`` clears the stored value (issue #549). The Cycle
    screen's chips are toggles; deselecting one used to be dropped by an
    ``is not None`` filter here, so the screen reported "Saved to your
    account", reloaded, and lit the chip back up.
    """
    user_id = current_user["id"]
    fields = _submitted_fields(log, skip=("start_date",))
    log_id = CycleService.upsert_log(user_id, log.start_date, fields)
    return {
        "message": f"Cycle logged for user {user_id}",
        "id": log_id,
        "data": log,
    }


#: Ceiling on one page. High enough that a month view or a year of period
#: starts fits in a single request, low enough that no response can grow
#: without bound on a 2G connection.
MAX_HISTORY_PAGE = 100

#: What a client gets when it asks for nothing in particular.
DEFAULT_HISTORY_PAGE = 20


@router.get(
    "/{user_id}/history",
    response_model=CycleHistoryResponse,
    summary="Get cycle history",
    description=(
        "Returns a page of the user's cycle log entries, ordered by date "
        "descending.\n\n"
        "`limit` and `offset` page through the history; `start_date` and "
        "`end_date` (both inclusive, `YYYY-MM-DD`) restrict it to a window, "
        "so a client can ask for a specific month rather than only for the "
        "most recent N entries.\n\n"
        "The `page` object reports where this page sits and whether another "
        "one exists. `hasMore` comes from fetching one extra document, not "
        "from a count query, so paging costs no additional round trip.\n\n"
        "Calling with no query parameters returns the most recent entries, "
        "newest first, exactly as before."
    ),
)
async def get_cycle_history(
    user_id: str,
    limit: int = Query(
        DEFAULT_HISTORY_PAGE,
        ge=1,
        le=MAX_HISTORY_PAGE,
        description="How many entries to return (1-100).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="How many entries to skip, for paging.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Only return entries on or after this date (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Only return entries on or before this date (inclusive).",
    ),
    current_user: dict = Depends(get_current_user)
):
    """One page of the user's own history.

    The bounds on ``limit`` are the point of this signature. It used to be
    an unvalidated ``Optional[int]`` passed straight into the query, where
    ``?limit=-1`` reached a Python slice as ``docs[:-1]`` and returned
    every log *except the oldest* — not an error, not empty, and not what
    anyone asked for — while ``?limit=100000`` was accepted and would
    serialize an entire history into one response. Both are now a 422 from
    FastAPI's own validation, before any handler code runs.
    """
    if user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's data"
        )

    # Checked here rather than by a validator because it is a relationship
    # between two parameters, not a property of either one. An inverted
    # range is a bug in the caller; returning an empty list would let it
    # look like "you have no logs in March".
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must not be after end_date",
        )

    entries, has_more = CycleService.get_logs_page(
        user_id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "message": f"History for user {user_id}",
        "entries": entries,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(entries),
            "hasMore": has_more,
            "nextOffset": offset + len(entries) if has_more else None,
        },
    }


@router.get(
    "/predictions",
    response_model=PredictionResponse,
    summary="Predict the next period, fertile window and current phase",
    description=(
        "Returns the authenticated user's predicted next period date with an "
        "explicit earliest/latest range and a confidence tier, her current "
        "cycle day and phase, an estimated ovulation date and fertile window, "
        "and the next few predicted period start dates.\n\n"
        "The cycle-length estimate is an exponentially weighted mean of "
        "recent cycles with outlier rejection, falling back to the length "
        "declared during onboarding and then to a population default; the "
        "`cycleLength.source` field says which was used.\n\n"
        "`daysUntilNextPeriod` goes negative when a period is late — it is "
        "deliberately not clamped at zero. Ovulation and the fertile window "
        "are statistical estimates from logged dates and are not "
        "contraceptive guidance."
    ),
)
async def get_cycle_predictions(
    horizon: int = Query(
        DEFAULT_FORECAST_HORIZON,
        ge=1,
        le=12,
        description="How many future period start dates to project.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Predictions for the authenticated user.

    Operates on ``current_user["id"]`` rather than a path parameter, so
    there is no cross-user authorization check to get wrong.

    Note this route is declared before ``PUT/DELETE /{log_id}`` but after
    ``/{user_id}/history``; ``/predictions`` is a fixed segment so it can
    never be shadowed by the ``{log_id}`` routes, which are on different
    methods anyway.
    """
    user_id = current_user["id"]
    logs = CycleService.get_logs_for_user(user_id, limit=12)
    profile = UserService.get_user_by_id(user_id) or {}

    return predict(logs, profile=profile, horizon=horizon).to_dict()


@router.put(
    "/{log_id}",
    response_model=CycleLogUpdateResponse,
    summary="Update a cycle log",
    description=(
        "Updates one or more fields of an existing cycle log entry. Only "
        "the fields included in the request body are modified; all other "
        "existing fields are preserved.\n\n"
        "A field included as `null` is removed from the stored log. "
        "`{\"notes\": null}` is a valid update rather than a `400`."
    ),
)
async def update_cycle_log(
    log_id: str,
    log_update: CycleLogUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Change some of a day's fields, including back to nothing.

    ``{"notes": null}`` is a valid update. It used to be a 400 saying "No
    fields provided for update" — a field *was* provided, the handler
    discarded it, and then reported the discarding as the caller's
    mistake (issue #549). The 400 now fires only when the body genuinely
    carried nothing.
    """
    user_id = current_user["id"]
    fields = _submitted_fields(log_update)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    # The schema bounded `end_date` on its own, but "is this end date before
    # the start date?" needs the start date, which is not in the payload —
    # this route addresses an existing document by id. Read it and finish
    # the check here, so an update cannot produce a log the POST route
    # would have refused to create.
    #
    # A `null` end_date is a clearing and has nothing to compare against,
    # so it skips the check rather than failing it.
    if fields.get("end_date") is not None:
        existing = CycleService.get_log(user_id, log_id)
        stored_start = _as_date(existing.get("start_date"))
        try:
            validate_end_date(stored_start, fields["end_date"])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    CycleService.update_log(user_id, log_id, fields)
    return {
        "message": f"Cycle log {log_id} updated",
        "id": log_id,
        "updated_fields": fields
    }


@router.delete(
    "/{log_id}",
    response_model=CycleLogDeleteResponse,
    summary="Delete a cycle log",
    description="Permanently removes a cycle log entry identified by its ID.",
)
async def delete_cycle_log(
    log_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    CycleService.delete_log(user_id, log_id)
    return {
        "message": f"Cycle log {log_id} deleted",
        "id": log_id
    }
