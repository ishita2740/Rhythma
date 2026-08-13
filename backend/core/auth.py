import bcrypt
import secrets
import hashlib
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from services.firestore_service import UserService

# --- Configuration ---
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET must be set in environment variables. Generate one using `python -c 'import secrets; print(secrets.token_urlsafe(32))'` and add it to .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_MINUTES = 15
VERIFY_TOKEN_EXPIRE_HOURS = 24

COOKIE_NAME = "rhythma_access_token"
REFRESH_COOKIE_NAME = "rhythma_refresh_token"
# auto_error=False: don't reject immediately when there's no Authorization
# header - a web client may still have a valid session cookie.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/firebase-login", auto_error=False)

# --- In-memory Stores ---
# Refresh tokens: token_hash -> {"user_id": str, "expires_at": datetime}
refresh_token_store: Dict[str, dict] = {}
# Reset tokens: email -> {"token_hash": str, "expires_at": datetime}
reset_token_store: Dict[str, dict] = {}
# Verification tokens: email -> {"token_hash": str, "expires_at": datetime}
verification_token_store: Dict[str, dict] = {}

# --- Password Functions ---
def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- Token Functions ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def cleanup_expired_refresh_tokens():
    now = datetime.now(timezone.utc)
    expired = [k for k, v in refresh_token_store.items() if now > v.get("expires_at", now)]
    for k in expired:
        refresh_token_store.pop(k, None)


def create_refresh_token(user_id: str) -> str:
    cleanup_expired_refresh_tokens()
    token = secrets.token_urlsafe(48)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_store[token_hash] = {"user_id": user_id, "expires_at": expires_at}
    return token

def verify_refresh_token(token: str) -> Optional[str]:
    token_hash = _hash_token(token)
    entry = refresh_token_store.get(token_hash)
    if not entry:
        return None
    if datetime.now(timezone.utc) > entry["expires_at"]:
        refresh_token_store.pop(token_hash, None)
        return None
    return entry["user_id"]

def revoke_refresh_token(token: str):
    token_hash = _hash_token(token)
    refresh_token_store.pop(token_hash, None)

def revoke_all_user_refresh_tokens(user_id: str):
    to_remove = [h for h, e in refresh_token_store.items() if e["user_id"] == user_id]
    for h in to_remove:
        refresh_token_store.pop(h, None)

def generate_reset_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    reset_token_store[email] = {"token_hash": token_hash, "expires_at": expires_at}
    return token

def verify_reset_token(email: str, token: str) -> bool:
    entry = reset_token_store.get(email)
    if not entry:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        reset_token_store.pop(email, None)
        return False
    if entry["token_hash"] != _hash_token(token):
        return False
    reset_token_store.pop(email, None)
    return True

def generate_verification_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=VERIFY_TOKEN_EXPIRE_HOURS)
    verification_token_store[email] = {"token_hash": token_hash, "expires_at": expires_at}
    return token

def verify_email_token(email: str, token: str) -> bool:
    entry = verification_token_store.get(email)
    if not entry:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        verification_token_store.pop(email, None)
        return False
    if entry["token_hash"] != _hash_token(token):
        return False
    verification_token_store.pop(email, None)
    return True

# --- Token Verification ---
async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Mobile clients send authorization: Bearer <token>
    # Web clients send it via the httpOnly cookie instead.
    if not token:
        token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = UserService.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return {
        "id": user["id"],
        "phone": user.get("phone"),
        "username": user.get("username"),
        "email": user.get("email")
    }
