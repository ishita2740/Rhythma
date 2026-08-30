import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from core.auth import get_current_user
from core.model_response import ANSWER_STATUSES, interpret
from services.firestore_service import AssistantConversationService
from services.medical_knowledge_service import MedicalKnowledgeService
from services.rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)

# ─── Backward-compatible shims ────────────────────────────────────────────
# Legacy tests import these directly from api.assistant. The real rate
# limiting now lives in RateLimitService (Firestore-backed), but these
# symbols must remain importable so that test_auth.py and
# test_assistant_rate_limiter.py keep working without changes.
_assistant_rate_history: dict = {}


def is_rate_limited(user_id: str) -> Optional[int]:
    """Thin wrapper kept for backward-compatible test imports."""
    return RateLimitService.is_rate_limited(
        key=f"assistant:{user_id}",
        limit=ASSISTANT_RATE_LIMIT,
        window_seconds=ASSISTANT_RATE_WINDOW,
    )

#: Loads the curated, sourced medical reference dataset (issue #266) and
#: retrieves relevant facts to ground each assistant answer. Degrades to
#: ungrounded responses if the dataset is unavailable.
medical_knowledge_service = MedicalKnowledgeService()

ASSISTANT_RATE_LIMIT = int(os.getenv("ASSISTANT_RATE_LIMIT", "10"))
ASSISTANT_RATE_WINDOW = int(os.getenv("ASSISTANT_RATE_WINDOW", "60"))


# ─── Supported languages ──────────────────────────────────────────────────
#: The one definition of what this endpoint speaks. `GET /languages`
#: publishes it and `AssistantRequest` validates against it, so the list a
#: client is shown and the list it is judged against cannot drift apart.
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "hi", "name": "Hindi"},
    {"code": "mr", "name": "Marathi"},
    {"code": "ta", "name": "Tamil"},
    {"code": "te", "name": "Telugu"},
    {"code": "kn", "name": "Kannada"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "gu", "name": "Gujarati"},
]

SUPPORTED_LANGUAGE_CODES = frozenset(lang["code"] for lang in SUPPORTED_LANGUAGES)


# ─── Input limits ─────────────────────────────────────────────────────────
# Read from the environment at import, matching ASSISTANT_RATE_LIMIT above.
# The rate limit caps *requests*; these cap what one request may carry,
# which is what the token bill is actually made of. Ten 500 KB messages a
# minute sits comfortably inside a 10/minute limit.
ASSISTANT_MAX_MESSAGE_CHARS = int(os.getenv("ASSISTANT_MAX_MESSAGE_CHARS", "2000"))
ASSISTANT_MAX_HISTORY_MESSAGES = int(os.getenv("ASSISTANT_MAX_HISTORY_MESSAGES", "20"))
ASSISTANT_MAX_HISTORY_CHARS = int(os.getenv("ASSISTANT_MAX_HISTORY_CHARS", "2000"))

#: Ceiling on what the model may generate in one reply.
#:
#: Previously unset, so the answer ran to whatever the model's own default
#: was and the truncation that followed was an accident nobody had chosen.
#: Setting it makes the cut a decision: 1024 output tokens is a long
#: answer in English and a comfortable one in Devanagari or Tamil, which
#: cost substantially more tokens per character and were truncating first.
#: `core/model_response.py` returns the shortened text rather than
#: discarding it, so reaching this ceiling degrades the answer instead of
#: replacing it.
ASSISTANT_MAX_OUTPUT_TOKENS = int(os.getenv("ASSISTANT_MAX_OUTPUT_TOKENS", "1024"))


def to_single_line(value: str) -> str:
    """Collapse anything that could forge a new line in the prompt.

    The prompt is assembled as newline-separated instruction lines, so a
    value containing a newline can introduce a line of its own. Validation
    already restricts `language` to a known code, which closes that on its
    own; this runs anyway because the two defences are independent and this
    one costs nothing. Unicode line separators (U+2028, U+2029) and other
    control characters are stripped too — they are invisible in a payload
    and a plain `\\n` check would miss them.
    """
    # Replaced with a space rather than deleted: dropping the newline in
    # "cramps\nadvice" would glue the words into "crampsadvice" and change
    # what was said, which is a different bug from the one being fixed.
    flattened = "".join(
        " "
        if char in ("\u2028", "\u2029") or unicodedata.category(char) == "Cc"
        else char
        for char in value
    )
    return re.sub(r"\s+", " ", flattened).strip()


class ChatMessage(BaseModel):
    #: Only the two roles the prompt builder understands. Anything else was
    #: silently dropped before, so a client could send history it believed
    #: was in use and never find out otherwise.
    role: Literal["user", "model"]
    content: str = Field(
        ...,
        min_length=1,
        max_length=ASSISTANT_MAX_HISTORY_CHARS,
        description="One turn of the conversation.",
    )


class AssistantRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=ASSISTANT_MAX_MESSAGE_CHARS,
        description="The user's question. Length-capped before any model call is made.",
    )
    language: Optional[str] = Field(
        "en",
        description=(
            "One of the codes from GET /assistant/languages. Rejected with "
            "422 if it is anything else."
        ),
    )
    history: Optional[List[ChatMessage]] = Field(
        None,
        max_length=ASSISTANT_MAX_HISTORY_MESSAGES,
        description=(
            "Recent turns, used only when nothing is persisted server-side "
            "for this user."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        """A message of spaces is an empty message with extra steps."""
        if not value.strip():
            raise ValueError("Message cannot be empty.")
        return value

    @field_validator("language")
    @classmethod
    def language_must_be_supported(cls, value: Optional[str]) -> Optional[str]:
        """Reject anything not in SUPPORTED_LANGUAGE_CODES.

        This field is interpolated into the prompt as its own instruction
        line — `Language: Respond in {language}.` — directly beneath the
        system prompt that forbids diagnosing and prescribing. Unvalidated,
        it is a place for a caller to write their own instructions in the
        position the guardrails occupy. Restricting it to an eight-item
        allowlist removes the vector rather than trying to filter it.
        """
        if value is None:
            return "en"

        # Region tags are accepted and reduced to their base language:
        # the web client sends `i18n.language`, which the browser language
        # detector routinely reports as `en-US` or `hi-IN`. Refusing those
        # would break real users over a formatting difference that carries
        # no meaning for a prompt.
        normalized = value.strip().lower().replace("_", "-").split("-")[0]

        if normalized not in SUPPORTED_LANGUAGE_CODES:
            supported = ", ".join(sorted(SUPPORTED_LANGUAGE_CODES))
            raise ValueError(
                f"Unsupported language {value!r}. Supported languages: {supported}."
            )
        return normalized


class AssistantSource(BaseModel):
    """A citable source backing the answer, for the client to render as links.

    Populated from the retrieved medical references, so users can verify
    the information themselves (menstrual_insights_guidelines.md).
    """

    name: str
    title: str
    url: str
    accessedOn: str


class AssistantResponse(BaseModel):
    response: str
    language: str
    disclaimer: str = "Please consult a healthcare professional for medical advice."
    #: The sources the answer was grounded on; empty when no medical
    #: reference matched the message.
    sources: List[AssistantSource] = Field(default_factory=list)
    #: True when the model hit the output ceiling and the answer above is
    #: the shortened version rather than the whole one.
    #:
    #: Additive and defaulted, so a client written before this field
    #: existed is unaffected. It exists because the alternative to telling
    #: the client is what this endpoint used to do: throw the shortened
    #: answer away and claim a safety block instead (issue #508). A client
    #: that renders nothing for this field still shows a real answer.
    wasShortened: bool = False


SYSTEM_PROMPT = """
You are Rhythma, a compassionate and knowledgeable AI menstrual health companion designed specifically for women in India. Your purpose is to provide supportive, culturally sensitive, and medically responsible guidance on menstrual health, reproductive health, emotional well-being, and overall women's health.

Key guidelines:
- Always prioritize safety and remind users to consult a doctor for medical advice.
- Keep responses concise, empathetic, and easy to understand.
- Use simple English or the user's preferred Indian language.
- Be non-judgmental and encouraging.
- Do not provide medical diagnoses - encourage professional consultation.
- Never prescribe medication.
- If you don't know something, say so honestly.
- Always end responses that involve symptoms or health concerns with a gentle reminder to consult a healthcare professional.
"""

router = APIRouter(tags=["AI Assistant"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set. Assistant requests will fail until it is configured.")
else:
    genai.configure(api_key=GEMINI_API_KEY)


@router.post(
    "/chat",
    response_model=AssistantResponse,
    summary="Ask the AI health assistant a question",
    description=(
        "Answers a question about menstrual and reproductive health, "
        "grounded in the curated medical reference dataset and in the "
        "user's recent conversation.\n\n"
        "Input is bounded: `message` and each `history[].content` are "
        "length-capped, `history` is item-capped, `role` accepts only "
        "`user` or `model`, and `language` must be one of the codes from "
        "`GET /assistant/languages`. All of it is enforced by the request "
        "model, so an over-limit or malformed request returns `422` "
        "without a model call being made — the per-user rate limit caps "
        "requests, not the tokens inside them.\n\n"
        "Returns `429` with `Retry-After` when the per-user rate limit is "
        "exceeded."
    ),
)
async def chat(
    request: AssistantRequest,
    current_user: dict = Depends(get_current_user),
):
    # Emptiness, length and language are all settled by AssistantRequest
    # before this body runs — so an oversized or malformed request is
    # refused without a Gemini call, and without the token bill attached
    # to one.
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured.")

    user_id = current_user.get("id")

    # Rate limit check (use Firestore-backed shared RateLimitService)
    remaining = RateLimitService.is_rate_limited(
        key=f"assistant:{user_id}",
        limit=ASSISTANT_RATE_LIMIT,
        window_seconds=ASSISTANT_RATE_WINDOW,
    )
    if remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait {remaining} seconds before sending another message.",
            headers={"Retry-After": str(remaining)},
        )

    # Load persisted history from Firestore, falling back to client-provided history
    persisted = AssistantConversationService.get_recent_messages(user_id, limit=10)
    history = [ChatMessage(**m) if isinstance(m, dict) else m for m in persisted]

    if not history and request.history:
        history = request.history[-10:]

    # Ground the answer with sourced medical references. The retrieval query
    # folds in recent user turns so follow-ups like "and what about the
    # bleeding?" still match the right topic. See services/medical_knowledge_service.py.
    retrieval_query = " ".join(
        [m.content for m in history[-5:] if m.role == "user" and m.content]
        + [request.message]
    ).strip()
    references = medical_knowledge_service.retrieve(retrieval_query, limit=3)
    grounding = medical_knowledge_service.build_grounding_block(references)

    prompt_parts = [
        f"System: {SYSTEM_PROMPT}",
    ]

    if grounding:
        prompt_parts.append(f"Grounding: {grounding}")

    # `to_single_line` on a value that is already restricted to an
    # eight-item allowlist is redundant by design: if the allowlist is ever
    # widened, or a caller reaches this without going through the model,
    # the prompt still cannot gain a line it didn't ask for.
    prompt_parts.append(f"Language: Respond in {to_single_line(request.language or 'en')}.")

    prompt_parts.append("\n--- Conversation History ---")

    if history:
        for msg in history[-10:]:
            if msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "model":
                prompt_parts.append(f"Assistant: {msg.content}")
    else:
        prompt_parts.append("(No previous messages)")

    prompt_parts.extend(
        [
            "\n--- Current Message ---",
            f"User: {request.message}",
            "Assistant:",
        ]
    )

    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        response = model.generate_content(
            "\n".join(prompt_parts),
            # An explicit ceiling, so where a long answer gets cut is a
            # decision rather than whatever the model default happened to
            # be. See ASSISTANT_MAX_OUTPUT_TOKENS.
            generation_config={"max_output_tokens": ASSISTANT_MAX_OUTPUT_TOKENS},
        )

        # One reading of what the model did, in `core/model_response.py`.
        # It used to be four lines here that matched `finish_reason` as a
        # string against `"SAFETY"` and against `"2"` — and 2 is
        # MAX_TOKENS, not SAFETY, so a merely-long answer was discarded and
        # the user was told her question had tripped a safety filter
        # (issue #508). `interpret` reads the reason by value and always
        # returns showable text, so this route no longer has to decide what
        # to say when the model said nothing.
        outcome = interpret(response)

        if outcome.status not in ANSWER_STATUSES:
            # Not an error to the caller — she still gets a reply — but the
            # reason belongs in the log, named, so a recitation block can be
            # told apart from an empty candidate without reproducing it.
            logger.warning(
                "The assistant returned no usable answer (status=%s, finish_reason=%s)",
                outcome.status,
                outcome.finish_reason,
                extra={
                    "assistant_status": outcome.status,
                    "assistant_finish_reason": outcome.finish_reason,
                },
            )

        reply = outcome.text

        # Persist exchange to Firestore
        AssistantConversationService.add_messages(user_id, [
            {"role": "user", "content": request.message},
            {"role": "model", "content": reply},
        ])

        return AssistantResponse(
            response=reply,
            language=request.language or "en",
            disclaimer="Please consult a healthcare professional for medical advice.",
            sources=medical_knowledge_service.source_list(references),
            wasShortened=outcome.was_shortened,
        )
    except Exception as exc:
        logger.error("Gemini API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="AI service error. Please try again later.")


@router.get(
    "/languages",
    summary="Languages the assistant will answer in",
    description=(
        "The codes accepted by the `language` field of `POST "
        "/assistant/chat`. Served from the same list the request model "
        "validates against, so this cannot advertise a language the "
        "endpoint would then reject."
    ),
)
async def supported_languages(current_user: dict = Depends(get_current_user)):
    return SUPPORTED_LANGUAGES