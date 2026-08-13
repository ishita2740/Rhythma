"""Inbound chat webhooks, and the route that links a chat to an account.

Every other route in this API is reached by a signed-in client. These two
are reached by Telegram and by Twilio, and before this module was
rewritten they were reached by anybody: neither checked a signature,
neither was rate-limited, and both took the identity whose health data
they would read straight out of the request body.

The order of work in a webhook handler is the whole security story, so it
is the same in both and it is deliberate:

1. **Rate-limit on the network address.** Ahead of verification, because
   an unverified flood is exactly the traffic worth shedding first, and
   because signature checking is the most expensive thing here.
2. **Verify the delivery** against the platform's shared secret. A
   failure is a flat 401 with no detail — a caller who cannot authenticate
   is not owed a reason.
3. **Resolve the chat to an account** through ``chat_link_service``. The
   payload's chat id is a *lookup key*, never an identity: an unlinked
   chat resolves to ``None`` and gets public text back.
4. **Compose a reply** in ``ChatbotService``, which by then cannot see
   anything the caller supplied about who they are.

Replies go back in each platform's own response shape. Telegram reads a
JSON body describing a method to call; Twilio reads TwiML. The previous
WhatsApp handler returned ``{"status": "success", ...}``, which Twilio
ignores, so nothing was ever delivered.
"""

from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.rate_limits import BOT_LINK_CODE_ACCOUNT, BOT_WEBHOOK_IP, client_ip, enforce
from core.webhook_auth import (
    CHANNEL_TELEGRAM,
    CHANNEL_WHATSAPP,
    WebhookVerificationError,
    verification_configured,
    verify_telegram,
    verify_twilio,
)
from services.chat_link_service import (
    SUPPORTED_CHANNELS,
    issue_link_code,
    links_for_user,
    resolve_user_id,
)
from services.chatbot_service import ChatbotService
from utils.logger import logger

router = APIRouter(tags=["Chatbot Engine"])


class LinkCodeRequest(BaseModel):
    channel: str = Field(
        "telegram",
        description="Which bot the code is for: telegram or whatsapp.",
    )


class LinkCodeResponse(BaseModel):
    code: str
    channel: str
    expiresInSeconds: int


class LinkedChat(BaseModel):
    channel: str
    chatId: str
    linkedAt: Optional[str] = None


class LinkedChatsResponse(BaseModel):
    links: list[LinkedChat]


def _reject_unverified(channel: str, exc: WebhookVerificationError) -> HTTPException:
    """One 401 for every verification failure, with the reason in the log.

    The reason is useful to whoever is configuring the bot and useless to
    anyone else, so it goes where the first group can read it.
    """
    logger.bind(channel=channel, reason=exc.reason).warning(
        "Rejected an unverified webhook delivery"
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="This webhook could not be verified.",
    )


# ─── Telegram ─────────────────────────────────────────────────────────────


@router.post(
    "/telegram/webhook",
    summary="Telegram bot webhook",
    description=(
        "Receives Telegram bot updates. Authenticated by the "
        "`X-Telegram-Bot-Api-Secret-Token` header, which must match the "
        "`secret_token` registered with `setWebhook` — set it as "
        "`TELEGRAM_WEBHOOK_SECRET`. Rate-limited per source address.\n\n"
        "A chat only receives personal data once it has been linked to a "
        "Rhythma account with a code from `POST /bot/link-code`; the chat "
        "id in the payload is never treated as an account id."
    ),
)
async def telegram_webhook(request: Request, payload: Dict[str, Any]):
    enforce(BOT_WEBHOOK_IP, f"{CHANNEL_TELEGRAM}:{client_ip(request)}")

    try:
        verify_telegram(request)
    except WebhookVerificationError as exc:
        raise _reject_unverified(CHANNEL_TELEGRAM, exc)

    # `message` for a normal send, `edited_message` for a correction. A
    # payload with neither (a poll answer, a chat-member change) is
    # acknowledged and ignored — Telegram retries anything that is not a
    # 2xx, so answering an update we do not handle with an error would
    # have it redelivered forever.
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "").strip()
    text = message.get("text") or ""

    if not chat_id:
        return {"ok": True}

    user_id = resolve_user_id(CHANNEL_TELEGRAM, chat_id)
    reply = ChatbotService.process_incoming_message(
        text=text,
        channel=CHANNEL_TELEGRAM,
        chat_id=chat_id,
        user_id=user_id,
    )

    # Answering the webhook with the method to call saves an outbound
    # request per message. `parse_mode` is deliberately absent: the reply
    # is plain text, and declaring Markdown means any stray underscore in
    # it makes Telegram reject the whole send.
    return {"method": "sendMessage", "chat_id": chat_id, "text": reply}


# ─── WhatsApp / Twilio ────────────────────────────────────────────────────


def _twiml(reply: str) -> Response:
    """Twilio's expected response shape.

    The body is XML-escaped rather than interpolated. Replies are composed
    from our own constants today, but one of them already interpolates a
    channel name, and an unescaped ``&`` is enough to make Twilio treat
    the whole document as malformed and deliver nothing.
    """
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(reply)}</Message></Response>"
    )
    return Response(content=body, media_type="application/xml")


@router.post(
    "/whatsapp/webhook",
    summary="WhatsApp (Twilio) bot webhook",
    description=(
        "Receives Twilio WhatsApp messages as a form post and replies "
        "with TwiML. Authenticated by the `X-Twilio-Signature` header, "
        "verified against `TWILIO_AUTH_TOKEN`; set "
        "`WEBHOOK_PUBLIC_BASE_URL` when the app sits behind a proxy that "
        "rewrites the URL Twilio signed.\n\n"
        "As with Telegram, the sender's number is a lookup key and not an "
        "identity — an unlinked number receives no personal data, however "
        "closely it matches one on an account."
    ),
)
async def whatsapp_webhook(request: Request):
    enforce(BOT_WEBHOOK_IP, f"{CHANNEL_WHATSAPP}:{client_ip(request)}")

    # Twilio signs the decoded form pairs, so the body has to be parsed
    # before verification rather than after it.
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}

    try:
        verify_twilio(request, params)
    except WebhookVerificationError as exc:
        raise _reject_unverified(CHANNEL_WHATSAPP, exc)

    chat_id = (params.get("From") or "").strip()
    text = params.get("Body") or ""

    if not chat_id:
        return _twiml(
            "Rhythma could not tell which number this message came from."
        )

    user_id = resolve_user_id(CHANNEL_WHATSAPP, chat_id)
    reply = ChatbotService.process_incoming_message(
        text=text,
        channel=CHANNEL_WHATSAPP,
        chat_id=chat_id,
        user_id=user_id,
    )
    return _twiml(reply)


# ─── Linking, from the app ────────────────────────────────────────────────


@router.post(
    "/link-code",
    response_model=LinkCodeResponse,
    summary="Generate a code that connects a chat to this account",
    description=(
        "Returns a short single-use code, valid for a few minutes, to "
        "send to the bot as `link <code>`. Generating a new code "
        "invalidates any previous one for the same channel.\n\n"
        "This is the only way a chat can be bound to an account: the "
        "webhooks never infer identity from a chat id or a phone number."
    ),
)
async def create_link_code(
    payload: LinkCodeRequest,
    current_user: dict = Depends(get_current_user),
):
    channel = (payload.channel or "").strip().lower()
    if channel not in SUPPORTED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported channel. Supported channels: "
                f"{', '.join(sorted(SUPPORTED_CHANNELS))}."
            ),
        )

    user_id = current_user["id"]

    # Per account, not per address. A code is a bearer credential for the
    # account that asked for it, so the budget that matters is how many
    # one account may have minted — a shared connection would otherwise
    # let one noisy user exhaust everyone else's.
    enforce(BOT_LINK_CODE_ACCOUNT, user_id)

    if not verification_configured(channel):
        # Not a refusal: local development has no secrets and still needs
        # to be able to link. It is worth one line in the log that a code
        # was minted for a channel whose deliveries nobody is checking.
        logger.bind(channel=channel).warning(
            "Issuing a chat link code for a channel with no webhook "
            "verification configured"
        )

    return issue_link_code(user_id, channel)


@router.get(
    "/links",
    response_model=LinkedChatsResponse,
    summary="Chats connected to this account",
    description=(
        "Lists the messaging chats currently linked to the authenticated "
        "account, so a user can see what a settings screen would need to "
        "offer her a way to disconnect."
    ),
)
async def list_links(current_user: dict = Depends(get_current_user)):
    return {
        "links": [
            {
                "channel": link.get("channel", ""),
                "chatId": link.get("chat_id", ""),
                "linkedAt": link.get("linked_at"),
            }
            for link in links_for_user(current_user["id"])
        ]
    }
