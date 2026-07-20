from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from core.auth import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash,
    verify_password,
    get_current_user,
)
from models.user import UserCreate, UserResponse, UserProfileUpdate, UserProfileResponse
from services.firestore_service import UserService
from typing import Dict, List

router = APIRouter(tags=["Authentication"])

# ─── Rate Limiting ──────────────────────────────────────────────────────────
# In-memory stores for rate limiting (resets on server restart)
login_attempts: Dict[str, List[datetime]] = {}
register_attempts: Dict[str, List[datetime]] = {}

def is_rate_limited(
    attempts_store: Dict[str, List[datetime]],
    key: str,
    limit: int = 5,
    window_seconds: int = 300,
) -> bool:
    """
    Returns True if the key has exceeded the allowed number of attempts
    within the rolling time window.
    """
    now = datetime.now(timezone.utc)
    # Clean old entries
    if key in attempts_store:
        attempts_store[key] = [
            t for t in attempts_store[key]
            if now - t < timedelta(seconds=window_seconds)
        ]
    else:
        attempts_store[key] = []

    if len(attempts_store[key]) >= limit:
        return True

    attempts_store[key].append(now)
    return False

def get_client_ip(request: Request) -> str:
    """Extract the client's IP address from the request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host or "unknown"

# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(request: Request, user_data: UserCreate):
    # Rate limit by IP address (10 attempts per 5 minutes)
    client_ip = get_client_ip(request)
    if is_rate_limited(register_attempts, client_ip, limit=10, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait 5 minutes."
        )

    # ─── Check for an existing account ──────────────────────────────────
    # Check both username and email regardless of whether the first check
    # already found a match, and return one identical message either way.
    # Returning distinct "Username already exists" vs "Email already
    # exists" responses (or short-circuiting on the first match) lets an
    # attacker enumerate which specific accounts exist on the system by
    # trying registrations — this keeps the *existence* check useful for
    # legitimate re-registration attempts without revealing which field
    # matched.
    existing_username = UserService.get_user_by_username(user_data.username)
    existing_email = UserService.get_user_by_email(user_data.email)
    if existing_username or existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this username or email already exists"
        )

    # ─── Hash password and create user ─────────────────────────────────
    hashed_password = get_password_hash(user_data.password)
    user_dict = user_data.model_dump()
    user_dict["password"] = hashed_password

    user_id = UserService.create_user(user_dict)
    created_user = UserService.get_user_by_id(user_id)

    return UserResponse(
        id=created_user["id"],
        username=created_user["username"],
        email=created_user["email"],
        full_name=created_user.get("full_name"),
        created_at=created_user["created_at"],
        updated_at=created_user.get("updated_at")
    )


@router.post("/token")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # Rate limit by username (5 attempts per 5 minutes)
    key = form_data.username or "unknown"
    if is_rate_limited(login_attempts, key, limit=5, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait 5 minutes."
        )

    user = UserService.get_user_by_username(form_data.username)
    if not user:
        user = UserService.get_user_by_email(form_data.username)

    # Generic error message: same for missing user or wrong password
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Returns the signed-in user's basic identity.

    This is deliberately lightweight — its main purpose is to double as a
    token-validation check: `get_current_user` already raises 401 if the
    token is expired, malformed, or the account no longer exists, so a
    successful response here means the stored token is genuinely still
    good (used by the Flutter app at launch, see main.dart).
    """
    return current_user


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Returns the full profile for the authenticated user.

    Fetches the complete Firestore user document which contains both the
    authentication fields (username, email) and any health/preference
    fields written during onboarding or Edit Profile (age, height, cycle
    data, avatar, language, etc.).
    """
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Merges profile fields onto the authenticated user's Firestore document.

    Uses PATCH semantics: only fields explicitly provided (non-None) are
    written.  This allows the Flutter app to send partial updates (e.g.
    just avatar or just cycle_length) without clobbering unrelated fields.

    Reuses the existing UserService.update_user() method — no new
    service layer introduced.
    """
    updates = {k: v for k, v in profile_data.model_dump().items() if v is not None}
    if updates:
        UserService.update_user(current_user["id"], updates)
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user