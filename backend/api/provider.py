"""Provider dashboard endpoints (issue #267).

Healthcare professionals register and log in through their own flow, then
see only the patients who have explicitly granted them consent. Consent
grant/list/revoke live on this router too: they are the patient side of
the same feature, and keeping the new surface in one place makes the
consent contract (and its tests) easy to follow.

Issue #346: this router's own account flow originally predated both the
password policy (#330) and the named rate-limit policies (#329), and had
picked up neither. It hashed whatever password it was given — a single
character was accepted — and metered login with an inline call carrying
its own magic numbers, while registration was not metered at all.

The rule this module now follows is that a provider account is held to
*at least* the standard a patient account is held to, never a lower one.
That is not symmetry for its own sake: this is the account that reads
other people's cycle logs once they consent, so the weaker of the two
doors is the one worth closing first. Everything below is imported from
the same modules ``core/auth_router.py`` uses, rather than reimplemented,
so the two flows cannot drift apart again.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from core import auth_router as auth_router_module
from core.email_identity import normalize_email
from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from core.password_policy import enforce_password_policy
from core.rate_limits import (
    LOGIN_ACCOUNT,
    LOGIN_IP,
    PROVIDER_REGISTER_IP,
    REGISTER_IP,
    clear as clear_rate_limit,
    enforce as enforce_rate_limit,
)
from services import access_log_service
from services.firestore_service import UserService
from services.provider_service import (
    DEFAULT_CONSENTS_PAGE,
    DEFAULT_PATIENTS_PAGE,
    MAX_CONSENTS_PAGE,
    MAX_PATIENTS_PAGE,
    ConsentService,
    ProviderService,
)

router = APIRouter(tags=["Provider Dashboard"])

#: Ceilings on the free-text fields a provider supplies at registration.
#: These are stored on the user document and shown to patients on the
#: sharing screen, so they are neither unbounded nor a place to paste an
#: essay. The numbers are generous for real names, specialties and
#: registration numbers and small enough that the document stays small.
MAX_NAME_CHARS = 120
MAX_SPECIALTY_CHARS = 120
MAX_LICENSE_CHARS = 64


class RegisterProviderRequest(BaseModel):
    email: EmailStr
    #: Deliberately not length-bounded here. The policy in
    #: ``core/password_policy.py`` owns every password rule, including both
    #: the minimum and the bcrypt byte ceiling, and it reports *all*
    #: failures at once so a form can show them together. A ``Field``
    #: constraint would pre-empt that with a bare 422 carrying none of the
    #: policy's own error codes.
    password: str
    username: Optional[str] = Field(None, max_length=MAX_NAME_CHARS)
    full_name: Optional[str] = Field(None, max_length=MAX_NAME_CHARS)
    specialty: Optional[str] = Field(None, max_length=MAX_SPECIALTY_CHARS)
    license_number: Optional[str] = Field(None, max_length=MAX_LICENSE_CHARS)


class ProviderLoginRequest(BaseModel):
    email: EmailStr
    password: str


class GrantConsentRequest(BaseModel):
    provider_email: EmailStr


def _clean(value: Optional[str]) -> Optional[str]:
    """Trim a free-text field, treating whitespace-only as absent.

    A ``full_name`` of ``"   "`` is not a name; storing it would make
    ``full_name or username or email`` in ``provider_service`` pick the
    blank string and render an empty provider on the patient's sharing
    screen.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _require_role(current_user: dict, role: str) -> dict:
    if current_user.get("role", "patient") != role:
        if role == "provider":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A healthcare provider account is required",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A patient account is required",
        )
    return current_user


# ─── Provider account ────────────────────────────────────────────────────


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_provider(data: RegisterProviderRequest, request: Request):
    """Create a provider account, separate from the patient ``/auth/register``
    flow. Same user store, ``role=provider`` attached at creation.

    The order of the three checks below matters and mirrors
    ``/auth/register`` exactly:

    1. **Rate limits first.** They are the cheapest check, and running them
       ahead of the email lookup is what stops the 409/201 split from being
       an account-enumeration oracle a caller can query at will. Two
       policies apply — ``REGISTER_IP``, shared with the patient route so
       one address cannot get a second budget by switching flows, and the
       tighter ``PROVIDER_REGISTER_IP``.
    2. **Password policy second**, still before the lookup, so a weak
       password is refused on its own terms rather than the response
       depending on whether the address happened to be taken too.
    3. **Existence check last.**
    """
    enforce_rate_limit(REGISTER_IP, auth_router_module.get_client_ip(request))
    enforce_rate_limit(PROVIDER_REGISTER_IP, auth_router_module.get_client_ip(request))

    email = normalize_email(data.email)
    username = _clean(data.username)

    # Raises WeakPasswordError (422, code `weak_password`) listing every
    # rule broken. Passing email and username lets the policy reject a
    # password built out of the account's own identifiers.
    enforce_password_policy(data.password, email=email, username=username)

    # The raw address, not the canonical one: `get_user_by_email`
    # normalises internally, and passing the string as typed additionally
    # lets it match an account created before #380 under a different
    # capitalisation. Only what is *stored* below is canonicalised.
    existing = UserService.get_user_by_email(data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_data = {
        "email": email,
        "password": get_password_hash(data.password),
        "email_verified": False,
        "role": "provider",
        "username": username,
        "full_name": _clean(data.full_name),
        "specialty": _clean(data.specialty),
        "license_number": _clean(data.license_number),
    }
    try:
        user_id = UserService.create_user(user_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider registration failed",
        ) from e

    return {
        "id": user_id,
        "email": email,
        "role": "provider",
        "message": "Provider account created.",
    }


@router.post("/login")
async def login_provider(
    data: ProviderLoginRequest, request: Request, response: Response
):
    """Provider login. Rejects patient accounts outright.

    Metered on the same two keys as ``/auth/login``, and on the same
    buckets rather than parallel ones. Sharing them is the point: an
    attacker working through a password list must not be handed a fresh
    allowance simply by pointing the same guesses at a different route.

    Both keys are needed. Per-IP alone is defeated by spreading guesses for
    one account across many addresses; per-account alone is defeated by
    walking the user table from a single address, one guess each. Both are
    checked before the lookup, so an unknown address is throttled exactly
    like a known one and the limit is not itself an enumeration signal.
    """
    email = normalize_email(data.email)

    enforce_rate_limit(LOGIN_IP, auth_router_module.get_client_ip(request))
    enforce_rate_limit(LOGIN_ACCOUNT, email)

    # Raw for the lookup, canonical for the rate-limit bucket above —
    # see the note in `register_provider`.
    user = UserService.get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    stored_hash = user.get("password")
    password_ok = bool(stored_hash) and verify_password(data.password, stored_hash)

    # The password is verified before the role is reported on, so a wrong
    # password gets the same 401 whether or not the address belongs to a
    # provider. Checking the role first would turn this route into a
    # detector for which registered addresses are clinician accounts —
    # answerable without knowing any password at all.
    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.get("role") != "provider":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is not a healthcare provider account",
        )

    # Correct password: forget this account's recent attempts, so a few
    # typos before a successful login don't leave her one mistake from a
    # lockout. The per-IP bucket is deliberately left alone — a machine
    # that just succeeded on one account has said nothing about the others
    # it may be working through. Cleared only after the role check passes,
    # so a patient repeatedly hitting the wrong login form does not reset
    # her own budget on every attempt.
    clear_rate_limit(LOGIN_ACCOUNT, email)

    access_token = create_access_token(
        data={"sub": user["id"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(user["id"])

    auth_router_module._set_auth_cookie(response, access_token)
    auth_router_module._set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email_verified": user.get("email_verified", False),
        "user_id": user["id"],
        "role": "provider",
    }


@router.get("/me")
async def provider_me(current_user: dict = Depends(get_current_user)):
    """The provider's own profile."""
    _require_role(current_user, "provider")
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user


# ─── Consent (patient side) ──────────────────────────────────────────────


@router.post("/consents", status_code=status.HTTP_201_CREATED)
async def grant_consent(
    data: GrantConsentRequest, current_user: dict = Depends(get_current_user)
):
    """A patient grants a provider access to her shared data.

    The address goes through untouched: ``ConsentService.grant`` looks the
    provider up with ``UserService.get_user_by_email``, which canonicalises
    on its own *and* falls back to the exact string when no canonical row
    matches. So a patient who types her doctor's address with different
    capitalisation than he registered with still finds him rather than
    getting "no provider found" — including when his account predates
    #380 and is stored mixed-case.
    """
    _require_role(current_user, "patient")
    return ConsentService.grant(current_user["id"], data.provider_email)


@router.get("/consents")
async def list_consents(
    limit: int = Query(
        DEFAULT_CONSENTS_PAGE,
        ge=1,
        le=MAX_CONSENTS_PAGE,
        description="How many consents to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many consents to skip."),
    current_user: dict = Depends(get_current_user),
):
    """A patient lists everyone she has shared data with, newest first.

    Each consent carries ``viewCount`` and ``lastAccessedAt`` (issue
    #350). Folded in here rather than served separately so the Sharing
    screen can render "last viewed 2 days ago" beside each provider
    without a second round trip — and because permission and use belong
    on the same row. Knowing who *could* look is only half of what a
    patient needs; knowing who *did* is the half that lets her act.

    Paged the same way cycle history and the access log are (#331, #406).
    The enrichment runs over the page rather than the whole list, so the
    ``summary_for_patient`` join does not grow with a patient's history of
    revoked consents.
    """
    _require_role(current_user, "patient")
    consents, has_more = ConsentService.list_page_for_patient(
        current_user["id"], limit=limit, offset=offset
    )
    access = access_log_service.summary_for_patient(current_user["id"])

    for consent in consents:
        stats = access.get(consent.get("provider_id")) or {}
        consent["viewCount"] = stats.get("viewCount", 0)
        consent["lastAccessedAt"] = stats.get("lastAccessedAt")

    return {
        "consents": consents,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(consents),
            "hasMore": has_more,
            "nextOffset": offset + len(consents) if has_more else None,
        },
    }


@router.get("/access-log")
async def list_access_log(
    limit: int = Query(
        access_log_service.DEFAULT_ACCESS_LOG_PAGE,
        ge=1,
        le=access_log_service.MAX_ACCESS_LOG_PAGE,
        description="How many entries to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many entries to skip."),
    current_user: dict = Depends(get_current_user),
):
    """When a provider read this patient's records, newest first.

    Patient-only, and scoped to ``current_user["id"]`` rather than to a
    path parameter, so there is no cross-user authorization check to get
    wrong. A provider cannot read this: her side of the relationship is
    the thing being recorded, and letting the subject of an audit trail
    read it is how audit trails stop being useful.

    Paged the same way cycle history is (#331) — ``hasMore`` comes from
    reading one past the page rather than from a count.
    """
    _require_role(current_user, "patient")
    entries, has_more = access_log_service.list_for_patient(
        current_user["id"], limit=limit, offset=offset
    )

    return {
        "entries": entries,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(entries),
            "hasMore": has_more,
            "nextOffset": offset + len(entries) if has_more else None,
        },
    }


@router.delete("/consents/{consent_id}")
async def revoke_consent(
    consent_id: str, current_user: dict = Depends(get_current_user)
):
    """A patient revokes a provider's access."""
    _require_role(current_user, "patient")
    return ConsentService.revoke(current_user["id"], consent_id)


# ─── Provider view ───────────────────────────────────────────────────────


@router.get("/patients")
async def list_patients(
    limit: int = Query(
        DEFAULT_PATIENTS_PAGE,
        ge=1,
        le=MAX_PATIENTS_PAGE,
        description="How many patients to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many patients to skip."),
    current_user: dict = Depends(get_current_user),
):
    """Providers see only patients with an active consent, newest share first.

    Paged (#406). This endpoint had no ceiling of any kind, and it is the
    most expensive list in the API to serve: each card costs a profile
    read, a scoring pass over that patient's cycle logs, and an access-log
    write. A clinic-scale roster turned one dashboard render into hundreds
    of Firestore operations, growing with every new consent.

    The slice is applied to the consents before that fan-out begins, so
    the cost of a page is the size of the page rather than the size of the
    roster.
    """
    _require_role(current_user, "provider")
    patients, has_more = ProviderService.patient_summaries_page(
        current_user["id"], limit=limit, offset=offset
    )
    return {
        "patients": patients,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(patients),
            "hasMore": has_more,
            "nextOffset": offset + len(patients) if has_more else None,
        },
    }


@router.get("/patients/{patient_id}")
async def patient_detail(
    patient_id: str, current_user: dict = Depends(get_current_user)
):
    """Provider view of one patient's shared data."""
    _require_role(current_user, "provider")
    return ProviderService.patient_detail(current_user["id"], patient_id)
