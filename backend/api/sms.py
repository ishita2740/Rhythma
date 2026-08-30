"""SMS summaries, sent only to the number on the account (issue #382).

``POST /send-summary`` used to take its destination and its whole message
body straight from the request:

    body_text = request.message or generate_cycle_sms_summary(user_id)
    client.messages.create(body=body_text, from_=from_phone, to=request.phone_number)

Neither was compared against the caller's own account, which made any
registered user an SMS relay: attacker-chosen text, to any E.164 number
on earth, arriving from the project's own Twilio sending number, billed
to the project. On a health app aimed at women in India that is the
project's name attached to whatever a stranger wants to send, and its
sender reputation spent doing it.

Two rules now hold, and both are enforced here rather than trusted to a
client:

**The destination is the number saved on the caller's account.** Not a
number in the body. A request carrying a different one is refused rather
than quietly redirected, so a client with the wrong idea is told so.

**The body is generated server-side.** A caller-supplied ``message`` is
no longer sent. That is a stronger guarantee than length-bounding one
would be — there is no text to bound — and it costs nothing real: the
only thing this endpoint is for is the cycle summary, and the summary is
built from data the server already holds.

*What* that generated body says now lives in
``services/sms_summary_service.py`` (issue #483). This module used to
compute its own cycle-length average and its own clamped
``max(avg - day, 0)`` countdown — the calculation
``services/prediction_service.py`` exists to replace — so the SMS could
not express a late period and disagreed with the Home screen of the same
account. Routing decisions (who may send, where it goes, how often) stay
here; the sentence is somebody else's job.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from core.auth import get_current_user
from services.firestore_service import UserService
from services.rate_limit_service import RateLimitService
from services.sms_summary_service import (
    GSM7_SINGLE_SEGMENT,
    build_summary,
    fit_to_budget,
)
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import os
import re

PHONE_PATTERN = r"^\+[1-9]\d{1,14}$"

#: The single-segment GSM-7 ceiling, re-exported so the name keeps
#: working for callers written before the summary moved out.
#:
#: It is no longer *the* ceiling. A Devanagari or Tamil summary cannot be
#: sent in GSM-7 at all, and a UCS-2 segment holds 70 characters — too
#: few for a summary and its safety disclaimer together. The real budget
#: is per-message and depends on the text's own encoding; see
#: ``sms_summary_service.segment_budget``.
SMS_MAX_CHARS = GSM7_SINGLE_SEGMENT


class SMSRequest(BaseModel):
    """What a client may ask for. Note how little of it is honoured.

    Both fields are retained so existing clients keep compiling, and both
    are deliberately inert:

    ``phone_number`` is *checked*, not used. When present it must be the
    number already on the account; it never selects a destination.

    ``message`` is ignored outright. It used to become the SMS body
    verbatim, which is the hole this module's docstring describes.
    """

    phone_number: Optional[str] = Field(
        None,
        pattern=PHONE_PATTERN,
        description=(
            "Optional. If given, must match the number saved on your "
            "account — it does not choose where the message goes. Omit it."
        ),
    )
    message: Optional[str] = Field(
        None,
        description=(
            "Ignored. The summary is generated server-side from your own "
            "logged cycle data. Kept only so older clients still validate."
        ),
    )


def registered_phone(user: Optional[Dict[str, Any]]) -> Optional[str]:
    """The number this account has on file, or ``None``.

    Reads the same two fields, in the same order, as ``GET /settings`` —
    ``phone`` is written by the Firebase phone-login flow, and
    ``sms_phone_number`` by ``POST /settings``. A user must not be shown
    one number on the settings screen and have a summary sent to another.
    """
    if not user:
        return None
    candidate = (user.get("phone") or user.get("sms_phone_number") or "").strip()
    return candidate or None


#: Kept as a name because tests and older callers import it. The
#: implementation moved to ``sms_summary_service.fit_to_budget``, which
#: differs in one respect: the ceiling it trims to is derived from the
#: text's own encoding rather than fixed at 160, so a Tamil summary is
#: measured against a UCS-2 budget instead of a GSM-7 one it could never
#: have been sent under.
_fit_to_one_segment = fit_to_budget


def generate_cycle_sms_summary(user_id: str) -> str:
    """This user's summary, in her own language, as one SMS body.

    A thin adapter now: it fetches, and ``sms_summary_service`` decides
    what to say. The cycle arithmetic that used to live here — an
    unweighted mean over the last ten *day* documents, and a
    ``max(avg - day, 0)`` countdown that clamped "five days late" to
    "~0 days" — is gone in favour of ``prediction_service.predict()``,
    which is what every other surface of the app already reads (#483).

    ``get_user_scores`` is called rather than ``CycleService`` directly
    because it returns the logs *and* the profile from one pass, and the
    profile is needed twice over: for the declared cycle length the
    prediction falls back to, and for the language to write in.
    """
    from datetime import date

    from services.scoring_service import get_user_scores

    score_data = get_user_scores(user_id)

    return build_summary(
        score_data.get("logs") or [],
        profile=score_data.get("profile"),
        today=date.today(),
    )


class SMSSettings(BaseModel):
    phoneNumber: Optional[str] = ""
    enabled: bool = False

    @property
    def normalized_phone(self) -> Optional[str]:
        return self.phoneNumber.strip() if self.phoneNumber else None


class SMSSettingsResponse(BaseModel):
    phoneNumber: str
    enabled: bool


class SMSSendResponse(BaseModel):
    message: str
    sid: str


router = APIRouter(tags=["SMS"])

# Legacy compatibility for existing tests
# SMS rate limiting is now handled by Firestore RateLimitService
sms_history = []


@router.get(
    "/settings",
    response_model=SMSSettingsResponse,
    summary="Get SMS notification settings",
    description="Returns the user's current SMS notification preferences, including the registered phone number and whether SMS summaries are enabled.",
)
async def get_sms_settings(current_user: dict = Depends(get_current_user)):
    user = UserService.get_user_by_id(current_user["id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "phoneNumber": registered_phone(user) or "",
        "enabled": bool(user.get("sms_enabled", False)),
    }


@router.post(
    "/settings",
    response_model=SMSSettingsResponse,
    summary="Save SMS notification settings",
    description="Updates the user's SMS notification preferences. A phone number is required when enabling SMS summaries, and must be in E.164 format.",
)
async def save_sms_settings(
    settings: SMSSettings,
    current_user: dict = Depends(get_current_user),
):
    phone = settings.normalized_phone
    if settings.enabled and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phone number is required to enable SMS summaries.",
        )
    if phone and not re.match(PHONE_PATTERN, phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number must be in E.164 format, e.g. +919876543210.",
        )

    UserService.update_user(
        current_user["id"],
        {
            "phone": phone or "",
            "sms_phone_number": phone or "",
            "sms_enabled": settings.enabled,
        },
    )
    return {"phoneNumber": phone or "", "enabled": settings.enabled}


@router.post(
    "/send-summary",
    response_model=SMSSendResponse,
    summary="Send SMS summary",
    description=(
        "Sends your cycle summary by SMS **to the number saved on your own "
        "account**. Rate-limited to one message per 60 seconds per user.\n\n"
        "The destination is not a request parameter. `phone_number` is "
        "optional and, when present, must match the number already on the "
        "account — supplying a different one is a `403`, not a redirect. "
        "`message` is ignored: the body is generated server-side from your "
        "logged cycle data.\n\n"
        "Both fields are retained only so clients written against the "
        "previous contract still validate. New client work should send an "
        "empty body.\n\n"
        "Returns `409` when no number is saved yet — save one through "
        "`POST /sms/settings` first."
    ),
)
async def send_sms_summary(
    request: SMSRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send this user's summary to this user's number.

    The destination is resolved from the account *before* anything else
    happens, and a mismatched ``phone_number`` is refused rather than
    ignored: a client asking to text a number that is not the account's
    has a bug, and silently redirecting the message would hide it.

    Both checks run ahead of the rate limiter deliberately. A refused
    request sends nothing and costs nothing, so spending the user's
    one-per-minute allowance on it would mean a client bug locks her out
    of the feature for a minute at a time.
    """
    user_id = current_user["id"]

    user = UserService.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    destination = registered_phone(user)
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No phone number is saved on this account. "
                "Save one in SMS settings before sending a summary."
            ),
        )

    if not re.match(PHONE_PATTERN, destination):
        # Reachable only for a document written before `POST /settings`
        # validated the field. Better a clear 409 than handing Twilio a
        # string it will reject with its own error.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The phone number saved on this account is not in E.164 "
                "format. Please save it again in SMS settings."
            ),
        )

    if request.phone_number and request.phone_number != destination:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Summaries are only sent to the phone number saved on your "
                "own account."
            ),
        )

    remaining = RateLimitService.is_rate_limited(
        key=f"sms:{user_id}",
        limit=1,
        window_seconds=60,
    )

    if remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait 60 seconds before sending another SMS.",
            headers={"Retry-After": str(int(remaining))},
        )

    # `request.message` is deliberately not consulted. It used to become
    # the SMS body verbatim, which is what let one account send arbitrary
    # text from the project's sending number.
    body_text = generate_cycle_sms_summary(user_id)

    try:
        from twilio.rest import Client
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Twilio is not installed. Please install it with `pip install twilio`."
        )

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    if not account_sid or not auth_token or not from_phone:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials are not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env."
        )

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body_text,
            from_=from_phone,
            to=destination,
        )
        return {"message": "SMS sent successfully", "sid": message.sid}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SMS: {str(e)}"
        )
