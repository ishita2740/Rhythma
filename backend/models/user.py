from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

from core.profile_validation import normalize_last_period

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

class UserProfileUpdate(BaseModel):
    """PATCH-semantics profile update — all fields optional.

    Stores extended health and preference data on the existing Firestore
    user document alongside the authentication fields.  Only non-None
    fields are written so callers can do partial updates safely.
    """
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=10, le=120)
    height_cm: Optional[float] = Field(None, ge=50.0, le=300.0)
    weight_kg: Optional[float] = Field(None, ge=10.0, le=500.0)
    avatar: Optional[str] = None
    language: Optional[str] = None
    last_period: Optional[str] = Field(
        None,
        description=(
            "Start date of the most recent period, as YYYY-MM-DD. A full "
            "ISO-8601 timestamp is accepted and reduced to its date. "
            "Cannot be in the future or more than ten years ago."
        ),
    )
    last_period_is_approximate: Optional[bool] = None
    cycle_length: Optional[int] = Field(None, ge=15, le=60)
    period_duration: Optional[int] = Field(None, ge=1, le=15)
    cycle_regular: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    phone: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value and not re.fullmatch(r"^\+[1-9]\d{1,14}$", value):
            raise ValueError(
                "Phone number must be in E.164 format, e.g. +919876543210."
            )
        return value
        
    city: Optional[str] = None
    state: Optional[str] = None

    @field_validator("last_period")
    def validate_last_period(cls, value: Optional[str]) -> Optional[str]:
        """Reject a last period that is malformed, in the future, or ancient.

        Every other field on this model is bounded — `age` is 10-120,
        `cycle_length` is 15-60, `period_duration` is 1-15 — and this one
        was free text, despite being the anchor `prediction_service` hangs
        the whole forecast off. A value it cannot parse silently empties
        the Home screen; a value in the future gives the user a fertile
        window computed from a period that has not happened (#501).

        The rules live in `core/profile_validation` rather than here, for
        the reason `core/cycle_validation` gives for holding the log rules:
        so a second profile write path cannot skip them.
        """
        return normalize_last_period(value)


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
    phone: Optional[str] = None
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