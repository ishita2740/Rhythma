"""Safety handling for the assistant's *responses*, exercised for real.

This file used to contain two tests that reimplemented the route's logic
inside the test body::

    finish_reason = str(getattr(first_candidate, "finish_reason", ""))
    if "SAFETY" in finish_reason or finish_reason == "2":
        reply = "..."

Nothing imported. The assertions therefore held whatever the route did,
which is why they were green throughout the whole life of #508 — the
route was treating MAX_TOKENS (2) as a safety block and this file could
not have noticed. A test that owns a copy of the code it is testing is
not a test of that code.

Both cases below now go through `core.model_response.interpret`, which is
the function the route calls. The exhaustive per-reason coverage lives in
`test_model_response.py`; these two are kept, with their original intent,
as the direct regression pair.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.model_response import (  # noqa: E402
    MESSAGE_SAFETY,
    STATUS_BLOCKED_SAFETY,
    STATUS_UNAVAILABLE,
    interpret,
)


class MockCandidate:
    def __init__(self, finish_reason, text=None):
        self.finish_reason = finish_reason
        self.content = MockContent(text)


class MockContent:
    def __init__(self, text):
        self.parts = [MockPart(text)] if text else []


class MockPart:
    def __init__(self, text):
        self.text = text


class MockBlockedResponse:
    def __init__(self, finish_reason="SAFETY", text=None):
        self.candidates = [MockCandidate(finish_reason, text)]

    @property
    def text(self):
        raise ValueError(
            "Quick accessor for 'text' requires a valid response with "
            "non-empty candidates"
        )


def test_gemini_safety_response_handling():
    """A safety-blocked candidate produces the safety message."""
    outcome = interpret(MockBlockedResponse("SAFETY"))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.is_answer is False


def test_gemini_safety_response_handling_by_numeric_reason():
    """The same block arriving as the bare value 3 rather than the name.

    The old string match required the name; this is the case that fell
    through it into `response.text`, which raises.
    """
    outcome = interpret(MockBlockedResponse(3))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY


def test_gemini_value_error_fallback():
    """An unrecognized reason with no text still yields showable text.

    `MockBlockedResponse.text` raises, exactly as the SDK accessor does on
    a candidate with no readable parts. Nothing may propagate out of
    `interpret`.
    """
    outcome = interpret(MockBlockedResponse("UNKNOWN"))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text.strip()
    assert outcome.is_answer is False
