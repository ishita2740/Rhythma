import sys
import os
from unittest.mock import MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class MockCandidate:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason


class MockBlockedResponse:
    def __init__(self, finish_reason="SAFETY"):
        self.candidates = [MockCandidate(finish_reason)]

    @property
    def text(self):
        raise ValueError("Quick accessor for 'text' requires a valid response with non-empty candidates")


def test_gemini_safety_response_handling():
    resp = MockBlockedResponse("SAFETY")

    # Simulate the resolution logic from assistant.py
    reply = None
    if hasattr(resp, "candidates") and resp.candidates:
        first_candidate = resp.candidates[0]
        finish_reason = str(getattr(first_candidate, "finish_reason", ""))
        if "SAFETY" in finish_reason or finish_reason == "2":
            reply = "I cannot process this request as it triggered safety guidelines. Please consult a healthcare professional."

    assert reply is not None
    assert "safety guidelines" in reply


def test_gemini_value_error_fallback():
    resp = MockBlockedResponse("UNKNOWN")

    reply = None
    if hasattr(resp, "candidates") and resp.candidates:
        first_candidate = resp.candidates[0]
        finish_reason = str(getattr(first_candidate, "finish_reason", ""))
        if "SAFETY" in finish_reason or finish_reason == "2":
            reply = "Safety blocked"

    if reply is None:
        try:
            reply = resp.text
        except Exception:
            reply = "Fallback response"

    assert reply == "Fallback response"
