"""What `core/model_response.interpret` says for each thing the model can do.

The bug in #508 survived because `test_assistant_safety.py` asserted
against an inline *copy* of the route's logic rather than importing it, so
the test and the route could never disagree — a test shaped so that it
passes no matter what the code under test does. Everything here imports
the real function.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.model_response import (  # noqa: E402
    FINISH_MAX_TOKENS,
    FINISH_OTHER,
    FINISH_RECITATION,
    FINISH_REASON_UNSPECIFIED,
    FINISH_SAFETY,
    FINISH_STOP,
    MESSAGE_EMPTY,
    MESSAGE_RECITATION,
    MESSAGE_SAFETY,
    MESSAGE_UNAVAILABLE,
    STATUS_BLOCKED_RECITATION,
    STATUS_BLOCKED_SAFETY,
    STATUS_OK,
    STATUS_TRUNCATED,
    STATUS_UNAVAILABLE,
    TRUNCATION_NOTE,
    candidate_text,
    finish_reason_name,
    finish_reason_value,
    interpret,
    response_text,
)


# ─── Doubles ──────────────────────────────────────────────────────────────
#
# Shaped like the SDK's objects rather than like dicts, because the code
# under test reads attributes and the difference is the whole point of
# `finish_reason_value`.


class FakePart:
    def __init__(self, text):
        self.text = text


class FakeContent:
    def __init__(self, texts):
        self.parts = [FakePart(t) for t in texts]


class FakeCandidate:
    def __init__(self, finish_reason, texts=()):
        self.finish_reason = finish_reason
        self.content = FakeContent(texts) if texts else FakeContent([])


class FakeResponse:
    """A response whose `.text` raises, as the real one does when blocked."""

    def __init__(self, candidates, prompt_feedback=None):
        self.candidates = candidates
        if prompt_feedback is not None:
            self.prompt_feedback = prompt_feedback

    @property
    def text(self):
        raise ValueError(
            "Quick accessor for 'text' requires a valid response with "
            "non-empty candidates"
        )


class FakeTextOnlyResponse:
    """The other shape: no readable parts, but `.text` works."""

    def __init__(self, text, candidates=None):
        self.text = text
        self.candidates = candidates if candidates is not None else []


class ProtoLikeEnum(int):
    """An int subclass whose `str()` is the qualified name, like the SDK's."""

    def __new__(cls, value, name):
        obj = super().__new__(cls, value)
        obj._name = name
        return obj

    def __str__(self):
        return f"FinishReason.{self._name}"


class FakeBlockFeedback:
    def __init__(self, block_reason):
        self.block_reason = block_reason


# ─── finish_reason_value ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        (3, FINISH_SAFETY),
        ("3", FINISH_SAFETY),
        ("SAFETY", FINISH_SAFETY),
        ("safety", FINISH_SAFETY),
        ("FinishReason.SAFETY", FINISH_SAFETY),
        (2, FINISH_MAX_TOKENS),
        ("MAX_TOKENS", FINISH_MAX_TOKENS),
        (1, FINISH_STOP),
        ("STOP", FINISH_STOP),
        (0, FINISH_REASON_UNSPECIFIED),
        (4, FINISH_RECITATION),
        (5, FINISH_OTHER),
    ],
)
def test_finish_reason_value_reads_every_shape(raw, expected):
    assert finish_reason_value(raw) == expected


def test_finish_reason_value_reads_a_proto_like_enum():
    """The shape the SDK actually hands back: int-like, name-ish `str()`."""
    assert finish_reason_value(ProtoLikeEnum(FINISH_SAFETY, "SAFETY")) == FINISH_SAFETY
    assert (
        finish_reason_value(ProtoLikeEnum(FINISH_MAX_TOKENS, "MAX_TOKENS"))
        == FINISH_MAX_TOKENS
    )


@pytest.mark.parametrize("raw", [None, "", "   ", "NOT_A_REASON", object()])
def test_finish_reason_value_is_none_for_anything_unrecognized(raw):
    assert finish_reason_value(raw) is None


def test_finish_reason_value_refuses_a_bool():
    """`bool` is an `int` subclass; True must not read as MAX_TOKENS-ish."""
    assert finish_reason_value(True) is None
    assert finish_reason_value(False) is None


def test_finish_reason_name_round_trips_and_labels_the_unknown():
    assert finish_reason_name(FINISH_SAFETY) == "SAFETY"
    assert finish_reason_name(FINISH_MAX_TOKENS) == "MAX_TOKENS"
    assert finish_reason_name(None) is None
    assert finish_reason_name(99) == "UNKNOWN_99"


# ─── The regression this issue is about ───────────────────────────────────


def test_max_tokens_returns_the_answer_not_a_safety_accusation():
    """The #508 regression, stated directly.

    finish_reason 2 is MAX_TOKENS. The old code matched `== "2"` in the
    safety branch, threw the generated text away, and told the user her
    question triggered safety guidelines.
    """
    answer = "Cramps in the first two days are common. Warmth and rest help"
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, [answer])]))

    assert outcome.status == STATUS_TRUNCATED
    assert outcome.was_shortened is True
    assert outcome.is_answer is True
    assert outcome.from_model is True
    assert answer in outcome.text
    assert TRUNCATION_NOTE in outcome.text
    # The specific wrong thing it used to say.
    assert "safety guidelines" not in outcome.text
    assert outcome.finish_reason == "MAX_TOKENS"


def test_max_tokens_with_no_text_at_all_is_unavailable_not_truncated():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, [])]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_UNAVAILABLE
    assert outcome.was_shortened is False


def test_a_real_safety_block_is_detected_by_value():
    """finish_reason 3 matched neither half of the old condition."""
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_SAFETY)]))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.is_answer is False
    assert outcome.from_model is False
    assert outcome.finish_reason == "SAFETY"


def test_a_safety_block_arriving_as_a_bare_number_is_still_detected():
    """The case the old `"SAFETY" in str(...)` check missed outright."""
    outcome = interpret(FakeResponse([FakeCandidate(3)]))
    assert outcome.status == STATUS_BLOCKED_SAFETY


def test_a_safety_block_arriving_as_a_name_is_still_detected():
    outcome = interpret(FakeResponse([FakeCandidate("SAFETY")]))
    assert outcome.status == STATUS_BLOCKED_SAFETY


def test_the_safety_message_does_not_blame_the_person_asking():
    """Wording is the point of this branch, so it is asserted.

    The old message — "this request triggered safety guidelines" — reads as
    an accusation, and was being shown most often to people whose question
    was entirely ordinary.
    """
    lowered = MESSAGE_SAFETY.lower()
    assert "your request" not in lowered
    assert "triggered" not in lowered
    assert "healthcare professional" in lowered


# ─── The reasons that were never handled at all ───────────────────────────


def test_recitation_gets_its_own_message():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_RECITATION)]))

    assert outcome.status == STATUS_BLOCKED_RECITATION
    assert outcome.text == MESSAGE_RECITATION
    assert outcome.finish_reason == "RECITATION"


def test_other_with_text_is_still_an_answer():
    """`OTHER` is not a refusal. If there is text, show it."""
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_OTHER, ["Here is what I know."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "Here is what I know."
    assert outcome.finish_reason == "OTHER"


def test_other_without_text_is_unavailable():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_OTHER)]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_EMPTY


def test_an_unknown_future_reason_with_text_is_not_treated_as_a_failure():
    outcome = interpret(FakeResponse([FakeCandidate(97, ["An answer."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "An answer."
    assert outcome.finish_reason == "UNKNOWN_97"


# ─── The ordinary path ────────────────────────────────────────────────────


def test_stop_returns_the_text_unchanged():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_STOP, ["Plain answer."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "Plain answer."
    assert outcome.was_shortened is False
    assert outcome.from_model is True


def test_multipart_text_is_joined_in_order():
    outcome = interpret(
        FakeResponse([FakeCandidate(FINISH_STOP, ["Part one. ", "Part two."])])
    )
    assert outcome.text == "Part one. Part two."


def test_text_is_read_from_parts_even_when_the_accessor_raises():
    """`response.text` raising is why a truncated answer was unreachable."""
    response = FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, ["Reachable."])])

    with pytest.raises(ValueError):
        _ = response.text

    assert candidate_text(response.candidates[0]) == "Reachable."
    assert "Reachable." in interpret(response).text


def test_response_text_falls_back_to_the_accessor_when_parts_are_absent():
    assert response_text(FakeTextOnlyResponse("  From the accessor.  ")) == (
        "From the accessor."
    )


def test_response_text_is_empty_rather_than_raising():
    assert response_text(FakeResponse([])) == ""


# ─── No candidates at all ─────────────────────────────────────────────────


def test_no_candidates_and_no_text_is_unavailable():
    outcome = interpret(FakeResponse([]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_UNAVAILABLE
    assert outcome.finish_reason is None


def test_no_candidates_but_readable_text_is_still_an_answer():
    """Text we have beats a message saying we have none."""
    outcome = interpret(FakeTextOnlyResponse("An answer with no candidate list."))

    assert outcome.status == STATUS_OK
    assert outcome.text == "An answer with no candidate list."
    assert outcome.from_model is True


def test_a_prompt_level_block_reads_as_a_safety_block():
    """No candidate is produced at all; the reason is on prompt_feedback."""
    outcome = interpret(
        FakeResponse([], prompt_feedback=FakeBlockFeedback("BlockReason.SAFETY"))
    )

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.finish_reason == "SAFETY"


def test_an_unspecified_block_reason_is_not_reported_as_a_safety_block():
    outcome = interpret(
        FakeResponse(
            [], prompt_feedback=FakeBlockFeedback("BLOCK_REASON_UNSPECIFIED")
        )
    )

    assert outcome.status == STATUS_UNAVAILABLE


# ─── The contract the route relies on ─────────────────────────────────────


@pytest.mark.parametrize(
    "finish_reason",
    [FINISH_REASON_UNSPECIFIED, FINISH_STOP, FINISH_MAX_TOKENS, FINISH_SAFETY,
     FINISH_RECITATION, FINISH_OTHER, 97, None, "nonsense"],
)
def test_every_outcome_carries_showable_text(finish_reason):
    """The property that lets the route stop composing fallbacks itself."""
    outcome = interpret(FakeResponse([FakeCandidate(finish_reason)]))

    assert isinstance(outcome.text, str)
    assert outcome.text.strip()


def test_interpret_never_raises_on_a_malformed_response():
    class Nothing:
        pass

    outcome = interpret(Nothing())
    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text
