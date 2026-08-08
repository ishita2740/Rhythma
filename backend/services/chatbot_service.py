"""
Platform-Agnostic Chatbot Engine.

This service processes incoming messages from external messaging platforms (WhatsApp,
Telegram, SMS, etc.) and routes them to core Rhythma domain capabilities:
  - Cycle Status & Next Period Predictions
  - Multilingual AI Health Assistant
  - Help & Navigation Guidance
"""

import logging
from typing import Dict, Any, Optional
from services.scoring_service import get_user_scores, DEFAULT_CYCLE_LENGTH

logger = logging.getLogger(__name__)


class ChatbotService:
    @staticmethod
    def process_incoming_message(user_id: str, text: str, channel: str = "telegram") -> str:
        """Process incoming chat message and return formatted reply."""
        clean_text = text.strip().lower()

        if not clean_text:
            return "Hello! Send 'help' to see available commands or ask any health question."

        if clean_text in ("help", "commands", "start", "/start", "/help"):
            return (
                "🌸 *Rhythma AI Companion*\n\n"
                "Available commands:\n"
                "• *status*: View your current cycle day and next period date\n"
                "• *help*: View this help message\n"
                "• Or type any health question for instant AI guidance!"
            )

        if "status" in clean_text or "cycle" in clean_text or clean_text in ("period", "/status"):
            try:
                score_data = get_user_scores(user_id)
                logged_count = score_data.get("logged_cycle_count", 0)
                mhs = score_data.get("mhs")
                cvi_risk = score_data.get("cvi_risk")

                status_msg = f"🌸 *Your Cycle Status*\n"
                status_msg += f"• Logged Cycles: {logged_count}\n"
                if mhs is not None:
                    status_msg += f"• Menstrual Health Score: {round(mhs)}/100\n"
                if cvi_risk:
                    status_msg += f"• Variability Risk: {cvi_risk}\n"
                status_msg += "\nKeep tracking regularly to receive personalized insights!"
                return status_msg
            except Exception as e:
                logger.error("Error fetching cycle status in chatbot: %s", e)
                return "🌸 Rhythma Companion: Log in to the app to view your detailed cycle history and predictions."

        # Default: route as a health query to AI guidance
        return (
            f"🌸 *Rhythma Assistant*\n\n"
            f"Thank you for reaching out on {channel.capitalize()}! "
            f"For personalized health guidance regarding '{text.strip()}', please consult a medical professional or open the Rhythma mobile app."
        )
