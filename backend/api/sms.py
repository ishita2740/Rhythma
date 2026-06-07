"""
SMS routes — weekly health summaries via Twilio.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter()


class SMSRequest(BaseModel):
    user_id: str
    phone_number: str   # E.164 format, e.g. +919876543210
    summary_type: str = "weekly"


@router.post("/send-summary")
async def send_sms_summary(request: SMSRequest):
    """
    Send a health summary SMS to the user via Twilio.
    TODO: Generate personalised summary from Firestore data.
    """
    try:
        from twilio.rest import Client

        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        if not all([account_sid, auth_token, from_number]):
            raise HTTPException(status_code=500, detail="Twilio not configured")

        client = Client(account_sid, auth_token)

        # TODO: Replace with real personalised summary from user data
        summary = (
            "🌸 Your Rhythma Weekly Summary:\n"
            "Cycle day 14 · Health score: 78/100 · "
            "Stay hydrated and keep tracking! Reply STOP to unsubscribe."
        )

        message = client.messages.create(
            body=summary,
            from_=from_number,
            to=request.phone_number,
        )

        return {"status": "sent", "sid": message.sid}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMS error: {str(e)}")
