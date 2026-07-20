from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

class UserCreate(BaseModel):
    username: str = Field(
        ...,
        min_length=6,
        max_length=30,
        description="Username (6-30 characters, alphanumeric and underscore only)"
    )
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: Optional[str] = Field(None, max_length=100)

    @field_validator('username')
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores.')
        if len(v) < 6:
            raise ValueError('Username must be at least 6 characters long.')
        if len(v) > 30:
            raise ValueError('Username must not exceed 30 characters.')
        return v

    @field_validator('password')
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long.')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
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
    age: Optional[int] = Field(None, ge=10, le=120)
    height_cm: Optional[float] = Field(None, ge=50.0, le=300.0)
    weight_kg: Optional[float] = Field(None, ge=10.0, le=500.0)
    avatar: Optional[str] = None
    language: Optional[str] = None
    last_period: Optional[str] = None          # ISO 8601 date string e.g. "2024-06-01"
    cycle_length: Optional[int] = Field(None, ge=15, le=60)
    period_duration: Optional[int] = Field(None, ge=1, le=15)
    cycle_regular: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

class UserProfileResponse(BaseModel):
    """Full profile response — auth identity merged with health profile."""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    avatar: Optional[str] = None
    language: Optional[str] = None
    last_period: Optional[str] = None
    cycle_length: Optional[int] = None
    period_duration: Optional[int] = None
    cycle_regular: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None