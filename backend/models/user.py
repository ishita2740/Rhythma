from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

class UserCreate(BaseModel):
    phone: str = Field(..., description="Phone number with country code")
    username: Optional[str] = Field(
        None,
        min_length=6,
        max_length=30,
        description="Username (6-30 characters, alphanumeric and underscore only)"
    )
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)

    @field_validator('username')
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores.')
        if len(v) < 6:
            raise ValueError('Username must be at least 6 characters long.')
        if len(v) > 30:
            raise ValueError('Username must not exceed 30 characters.')
        return v

class UserLogin(BaseModel):
    phone: str

class UserResponse(BaseModel):
    id: str
    phone: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

#: Fields an explicit ``null`` may remove from a profile (issue #533).
#:
#: The route used to filter its payload with ``if v is not None``, which
#: is what makes PATCH semantics work at all — without it, sending
#: ``{"age": 30}`` would blank the other fifteen fields. But it also made
#: an explicit ``null`` indistinguishable from an omitted field, so *no*
#: field on this model could ever be cleared. A user who emptied the Age
#: box and saved got a 200 and her old age back.
#:
#: ``model_dump(exclude_unset=True)`` tells the two cases apart. This set
#: says which of them a client is allowed to clear. It is an allowlist
#: rather than "everything": clearing an identity key through a profile
#: PATCH is not something a client should be able to ask for by accident,
#: which is why ``email`` and ``phone`` are absent — they are changed by
#: being given a new value, never by being emptied.
CLEARABLE_PROFILE_FIELDS = frozenset(
    {
        "full_name",
        "age",
        "height_cm",
        "weight_kg",
        "avatar",
        "language",
        "last_period",
        "last_period_is_approximate",
        "cycle_length",
        "period_duration",
        "cycle_regular",
        "notifications_enabled",
        "city",
        "state",
    }
)


class UserProfileUpdate(BaseModel):
    """PATCH-semantics profile update — all fields optional.

    Stores extended health and preference data on the existing Firestore
    user document alongside the authentication fields.

    **Omitted and ``null`` are different things (issue #533).** A field
    the request does not mention is left alone. A field sent explicitly as
    ``null`` is *cleared*, provided it is in
    :data:`CLEARABLE_PROFILE_FIELDS`. The route reads
    ``model_dump(exclude_unset=True)`` to tell them apart; it used to read
    ``model_dump()``, which reports every field with ``None`` for the ones
    that were never sent, so the two cases collapsed into one and nothing
    could be removed from a profile at all.

    The fields are declared in one block, with the validator after them.
    They used to be interleaved — ``city`` and ``state`` sat *below*
    ``validate_phone`` — which is legal and is why the duplicate ``phone``
    on :class:`UserProfileResponse` went unnoticed for as long as it did.
    """

    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=10, le=120)
    height_cm: Optional[float] = Field(None, ge=50.0, le=300.0)
    weight_kg: Optional[float] = Field(None, ge=10.0, le=500.0)
    avatar: Optional[str] = None
    language: Optional[str] = None
    last_period: Optional[str] = None          # ISO 8601 date string e.g. "2024-06-01"
    last_period_is_approximate: Optional[bool] = None
    cycle_length: Optional[int] = Field(None, ge=15, le=60)
    period_duration: Optional[int] = Field(None, ge=1, le=15)
    cycle_regular: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value and not re.fullmatch(r"^\+[1-9]\d{1,14}$", value):
            raise ValueError(
                "Phone number must be in E.164 format, e.g. +919876543210."
            )
        return value

class UserProfileResponse(BaseModel):
    """Full profile response — auth identity merged with health profile."""
    id: str
    phone: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    avatar: Optional[str] = None
    language: Optional[str] = None
    last_period: Optional[str] = None
    last_period_is_approximate: Optional[bool] = None
    cycle_length: Optional[int] = None
    period_duration: Optional[int] = None
    cycle_regular: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    # `phone` was declared twice in this class, ~15 lines apart. Both
    # declarations were identical so the second simply won, which is why
    # nobody noticed. #381 was the same pattern with a worse outcome:
    # `DashboardPrediction` was declared twice, the second won, and the
    # typed fields on the first were silently dropped from the served
    # schema. The duplicate is removed; `phone` is declared once, above.
    city: Optional[str] = None
    state: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScoresResponse(BaseModel):
    """Response model for GET /insights/{user_id}/scores.

    Returns factual cycle statistics computed directly from CycleLog
    history, with no clinical scoring model involved.
    """
    averageCycleLength: Optional[float] = Field(
        None, description="Mean days between consecutive period start dates."
    )
    shortestCycleLength: Optional[int] = Field(
        None, description="Shortest observed cycle length in days."
    )
    longestCycleLength: Optional[int] = Field(
        None, description="Longest observed cycle length in days."
    )
    averageBleedingDuration: Optional[float] = Field(
        None, description="Mean bleeding duration in days (start_date to end_date, inclusive)."
    )
    hasEnoughDataForInsights: bool = False
    loggedCycleCount: int = 0