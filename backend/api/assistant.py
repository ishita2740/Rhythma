"""
AI Assistant routes — powered by Gemini API.
Supports multilingual queries in Hindi, Marathi, Tamil, and English.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter()


class AssistantRequest(BaseModel):
    message: str
    language: Optional[str] = "en"   # "hi", "mr", "ta", "en"
    user_id: Optional[str] = None
    conversation_history: Optional[list] = []


class AssistantResponse(BaseModel):
    reply: str
    language_detected: str
    disclaimer: str = (
        "This is for educational awareness only. "
        "Consult a qualified healthcare professional for medical advice."
    )


SYSTEM_PROMPT = """
You are Rhythma, a compassionate and knowledgeable AI menstrual health companion 
designed specifically for women in India. You:

- Respond in the same language the user writes in (Hindi, Marathi, Tamil, or English)
- Provide clear, accessible health education about menstrual health, PCOD, hormones, and wellbeing
- Use a warm, non-judgmental, supportive tone
- Never diagnose or prescribe — always recommend consulting a doctor for medical decisions
- Are culturally sensitive to Indian contexts, family dynamics, and social realities
- Simplify complex medical information without losing accuracy

Always end responses that involve symptoms or health concerns with a gentle reminder 
to consult a healthcare professional if symptoms persist.
"""


@router.post("/chat", response_model=AssistantResponse)
async def chat(request: AssistantRequest):
    """
    Send a message to the Rhythma AI assistant.
    Powered by Gemini API with multilingual support.
    """
    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API key not configured")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        # Build conversation history for context
        history = []
        for msg in request.conversation_history:
            history.append({
                "role": msg.get("role", "user"),
                "parts": [msg.get("text", "")]
            })

        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(request.message)

        return AssistantResponse(
            reply=response.text,
            language_detected=request.language or "en",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {str(e)}")


@router.get("/languages")
async def supported_languages():
    """Returns the list of supported languages for the AI assistant."""
    return {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "hi", "name": "Hindi (हिन्दी)"},
            {"code": "mr", "name": "Marathi (मराठी)"},
            {"code": "ta", "name": "Tamil (தமிழ்)"},
        ]
    }
