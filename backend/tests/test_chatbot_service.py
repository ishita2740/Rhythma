import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.chatbot_service import ChatbotService


def test_chatbot_service_help_command():
    reply = ChatbotService.process_incoming_message(user_id="user_123", text="help", channel="telegram")
    assert "Rhythma AI Companion" in reply
    assert "status" in reply


def test_chatbot_service_status_command():
    reply = ChatbotService.process_incoming_message(user_id="user_123", text="status", channel="whatsapp")
    assert "Cycle Status" in reply or "Rhythma Companion" in reply


def test_chatbot_service_health_question():
    reply = ChatbotService.process_incoming_message(user_id="user_123", text="What causes period cramps?", channel="telegram")
    assert "Rhythma Assistant" in reply
    assert "Telegram" in reply
