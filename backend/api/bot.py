from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.chatbot_service import ChatbotService

router = APIRouter(tags=["Chatbot Engine"])


class TelegramWebhookRequest(BaseModel):
    update_id: Optional[int] = None
    message: Optional[Dict[str, Any]] = None


class WhatsAppWebhookRequest(BaseModel):
    From: Optional[str] = None
    Body: Optional[str] = None
    UserPhone: Optional[str] = None


@router.post("/telegram/webhook")
async def telegram_webhook(payload: Dict[str, Any]):
    """Webhook endpoint for Telegram Bot updates."""
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    user_id = str(chat.get("id") or "telegram_user")
    text = message.get("text") or ""

    reply = ChatbotService.process_incoming_message(user_id=user_id, text=text, channel="telegram")

    return {
        "method": "sendMessage",
        "chat_id": user_id,
        "text": reply,
        "parse_mode": "Markdown",
    }


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(payload: Dict[str, Any]):
    """Webhook endpoint for WhatsApp / Twilio updates."""
    from_phone = payload.get("From") or payload.get("UserPhone") or "whatsapp_user"
    body = payload.get("Body") or payload.get("text") or ""

    reply = ChatbotService.process_incoming_message(user_id=from_phone, text=body, channel="whatsapp")

    return {
        "status": "success",
        "to": from_phone,
        "message": reply,
    }
