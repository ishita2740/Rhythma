"""Reading what the model actually did, instead of guessing from a string.

``api/assistant.py`` decided whether Gemini had refused on safety grounds
by stringifying the candidate's ``finish_reason`` and matching on it::

    finish_reason = str(getattr(first_candidate, "finish_reason", ""))
    if "SAFETY" in finish_reason or finish_reason == "2":
        reply = "I cannot process this request as it triggered safety guidelines. ..."

``2`` is ``MAX_TOKENS``. ``SAFETY`` is ``3``. The two halves of that
condition also disagree with each other about what ``str()`` returns —
the substring test only works if it returns the enum *name*, the equality
test only works if it returns the *number* — so on any given SDK version
one of them is dead code.

What the user saw as a result:

* A long answer, generated successfully and then cut off at the token
  ceiling, was thrown away and replaced with "your question triggered
  safety guidelines". On an app whose own README describes an audience
  facing "deep social stigma [that] discourages open conversations about
  reproductive health", telling a woman that asking about her own body
  tripped a filter is the worst available way to be wrong. It is also not
  rare: no output ceiling was set, the system prompt asks for explanation,
  and Devanagari, Tamil and Malayalam cost far more tokens per character
  than English — so the users most likely to be accused are the ones using
  the app in their own language.

* A genuine safety block, when ``str()`` yielded ``3``, matched neither
  half, fell through to ``response.text``, which raises on a blocked
  candidate, and surfaced as the generic "I couldn't generate a response".

* ``RECITATION`` and ``OTHER`` were never distinguished from either.

This module is the reading, kept away from the route so it can be tested
without a model call — which is the other half of the bug, since
``test_assistant_safety.py`` asserted against an inline *copy* of the
route's logic and would have passed no matter what the route did.

Three rules it follows:

**Truncation returns the text.** A shortened answer is worth far more to
the reader than a refusal, so ``MAX_TOKENS`` yields whatever was
generated, marked as shortened, and only falls back to a message when
there is genuinely no text to show.

**A safety message never blames the reader.** The wording says the
assistant will not answer, not that the question was improper.

**Every non-STOP reason is named in the log.** Whoever debugs this next
should be able to tell a recitation block from a quota stop without
reproducing it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# ─── The enum, as the API defines it ──────────────────────────────────────
#
# https://ai.google.dev/api/generate-content#FinishReason. Mirrored as
# plain ints rather than imported from the SDK: the SDK hands these back
# as a proto enum, a bare int or a name depending on version and on
# whether the response was built by the client or by a test double, and
# this module's whole job is to be indifferent to which.

FINISH_REASON_UNSPECIFIED = 0
FINISH_STOP = 1
FINISH_MAX_TOKENS = 2
FINISH_SAFETY = 3
FINISH_RECITATION = 4
FINISH_OTHER = 5

FINISH_REASON_NAMES = {
    FINISH_REASON_UNSPECIFIED: "FINISH_REASON_UNSPECIFIED",
    FINISH_STOP: "STOP",
    FINISH_MAX_TOKENS: "MAX_TOKENS",
    FINISH_SAFETY: "SAFETY",
    FINISH_RECITATION: "RECITATION",
    FINISH_OTHER: "OTHER",
}

#: Name → value, so a candidate carrying ``"SAFETY"`` or
#: ``FinishReason.SAFETY`` resolves the same as one carrying ``3``.
FINISH_REASON_VALUES = {name: value for value, name in FINISH_REASON_NAMES.items()}

# ─── What the caller gets back ────────────────────────────────────────────

#: The answer is usable. ``text`` holds it.
STATUS_OK = "ok"
#: The answer is usable but was cut short at the token ceiling.
STATUS_TRUNCATED = "truncated"
#: The model declined. ``text`` is the message to show instead.
STATUS_BLOCKED_SAFETY = "blocked_safety"
#: The model stopped because the answer reproduced protected material.
STATUS_BLOCKED_RECITATION = "blocked_recitation"
#: Anything else that left us without an answer.
STATUS_UNAVAILABLE = "unavailable"

#: Statuses that carry a real answer from the model rather than a message
#: composed here. Exported so the route does not have to re-list them.
ANSWER_STATUSES = frozenset({STATUS_OK, STATUS_TRUNCATED})


# ─── User-facing messages ─────────────────────────────────────────────────
#
# Deliberately plain, and deliberately about the assistant rather than
# about the person asking. "I can't answer that one" is a statement about
# a limitation here; "your request triggered safety guidelines" is an
# accusation, and it was being made most often to people whose question
# was entirely ordinary.

MESSAGE_SAFETY = (
    "I'm not able to answer that one. It's not a judgement on your question — "
    "there are topics I'm set up to leave to a doctor. Please speak to a "
    "healthcare professional about this."
)

MESSAGE_RECITATION = (
    "I couldn't answer that one in my own words. Please try asking it a "
    "different way, or speak to a healthcare professional."
)

MESSAGE_UNAVAILABLE = (
    "I'm sorry, I couldn't produce an answer just now. Please try asking "
    "again, or speak to a healthcare professional."
)

MESSAGE_EMPTY = "I'm sorry, I couldn't produce an answer just now. Please try again."

#: Appended to a truncated answer so the reader knows the sentence ended
#: because of a limit and not because the assistant had nothing more to
#: say. Kept to one short line — this is added to an answer that is
#: already at the length ceiling.
TRUNCATION_NOTE = "… (this answer was shortened — ask me to continue if you'd like the rest.)"


@dataclass(frozen=True)
class ModelOutcome:
    """What came back, in terms the route can act on.

    ``text`` is always something showable. That is the point of the type:
    the route should never have to decide what to say when the model
    didn't say anything, because that decision is exactly where the
    original bug lived.
    """

    status: str
    text: str
    #: The reason as the API names it, for the log. ``None`` when the
    #: response carried no candidate at all.
    finish_reason: Optional[str] = None
    #: True when the answer is the model's own words rather than a message
    #: composed in this module.
    from_model: bool = False

    @property
    def was_shortened(self) -> bool:
        return self.status == STATUS_TRUNCATED

    @property
    def is_answer(self) -> bool:
        return self.status in ANSWER_STATUSES


def finish_reason_value(raw: Any) -> Optional[int]:
    """Normalize whatever the SDK put on the candidate into an int.

    Tolerated, because all four have been observed depending on SDK
    version, transport and test double:

    * ``3`` — a bare int.
    * ``FinishReason.SAFETY`` — a proto enum, which is int-like and whose
      ``str()`` is the qualified name.
    * ``"SAFETY"`` — the name as a plain string.
    * ``"3"`` — the number as a plain string.

    Returns ``None`` for anything unrecognized, which the caller treats as
    "we don't know", not as "fine".
    """
    if raw is None:
        return None

    # Proto enums are ``IntEnum``-like, so this catches both them and bare
    # ints — and it has to come before the string handling, since an enum's
    # ``str()`` is the qualified name.
    if isinstance(raw, bool):
        # ``bool`` is an ``int`` subclass and would otherwise read as 0/1,
        # i.e. as a valid STOP. Nothing should ever put a bool here, which
        # is exactly why it must not be silently misread as success.
        return None
    if isinstance(raw, int):
        return int(raw)

    text = str(raw).strip()
    if not text:
        return None

    if text.isdigit():
        return int(text)

    # ``FinishReason.SAFETY`` and ``StopReason.SAFETY`` both reduce to the
    # trailing name; a bare ``SAFETY`` is unaffected.
    name = text.rsplit(".", 1)[-1].upper()
    return FINISH_REASON_VALUES.get(name)


def finish_reason_name(value: Optional[int]) -> Optional[str]:
    """The API's own name for a value, or a readable stand-in."""
    if value is None:
        return None
    return FINISH_REASON_NAMES.get(value, f"UNKNOWN_{value}")


def candidate_text(candidate: Any) -> str:
    """The text on one candidate, reading the parts directly.

    ``response.text`` is a convenience accessor that *raises* when the
    candidate was blocked or truncated in some SDK versions, which is why
    the route could never get at the text of a truncated answer. Walking
    ``content.parts`` gets the same string without the accessor's
    opinions about whether we are allowed to have it.
    """
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []

    chunks = []
    for part in parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            chunks.append(text)

    return "".join(chunks).strip()


def response_text(response: Any) -> str:
    """Best-effort text for a whole response, candidates first.

    Tries the candidates' parts before ``response.text`` because the parts
    are readable in cases where the accessor throws, and falls back to the
    accessor for the doubles and SDK shapes that only implement that.
    """
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        text = candidate_text(candidate)
        if text:
            return text

    try:
        text = getattr(response, "text", None)
    except Exception:
        # The accessor raising *is* the normal case for a blocked or
        # truncated candidate. It is information, not an error.
        return ""

    return text.strip() if isinstance(text, str) else ""


def interpret(response: Any) -> ModelOutcome:
    """Turn a Gemini response into an outcome the route can render.

    The one function the route calls. Every branch returns a
    :class:`ModelOutcome` with showable ``text``; none of them raises.
    """
    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        # No candidate at all — usually a prompt-level block, where the
        # reason lives on ``prompt_feedback`` rather than on a candidate.
        blocked = _prompt_block_reason(response)
        if blocked:
            return ModelOutcome(
                status=STATUS_BLOCKED_SAFETY,
                text=MESSAGE_SAFETY,
                finish_reason=blocked,
            )

        # A response carrying text but no candidate list. The live SDK
        # always populates candidates, but a plain ``.text`` response is a
        # shape worth honouring rather than discarding: text we have is
        # always better for the reader than a message saying we have none.
        text = response_text(response)
        if text:
            return ModelOutcome(
                status=STATUS_OK, text=text, finish_reason=None, from_model=True
            )

        return ModelOutcome(
            status=STATUS_UNAVAILABLE,
            text=MESSAGE_UNAVAILABLE,
            finish_reason=None,
        )

    candidate = candidates[0]
    value = finish_reason_value(getattr(candidate, "finish_reason", None))
    name = finish_reason_name(value)
    text = candidate_text(candidate) or response_text(response)

    if value == FINISH_SAFETY:
        return ModelOutcome(
            status=STATUS_BLOCKED_SAFETY, text=MESSAGE_SAFETY, finish_reason=name
        )

    if value == FINISH_RECITATION:
        return ModelOutcome(
            status=STATUS_BLOCKED_RECITATION,
            text=MESSAGE_RECITATION,
            finish_reason=name,
        )

    if value == FINISH_MAX_TOKENS:
        # The whole point of the fix: a truncated answer is still an
        # answer. Only when nothing was generated at all does this become
        # a failure the user has to be told about.
        if text:
            return ModelOutcome(
                status=STATUS_TRUNCATED,
                text=f"{text} {TRUNCATION_NOTE}",
                finish_reason=name,
                from_model=True,
            )
        return ModelOutcome(
            status=STATUS_UNAVAILABLE, text=MESSAGE_UNAVAILABLE, finish_reason=name
        )

    # STOP, UNSPECIFIED, OTHER and anything a future API version adds. A
    # reason we do not recognize is not itself a problem as long as there
    # is text; it is only a problem when there is not.
    if text:
        return ModelOutcome(
            status=STATUS_OK, text=text, finish_reason=name, from_model=True
        )

    return ModelOutcome(
        status=STATUS_UNAVAILABLE, text=MESSAGE_EMPTY, finish_reason=name
    )


def _prompt_block_reason(response: Any) -> Optional[str]:
    """The ``prompt_feedback.block_reason``, when the prompt itself was refused.

    A prompt-level block produces a response with *no* candidates, so it
    never reaches the candidate branch above. Reported as a safety block
    because that is what it is from the reader's side.
    """
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is None:
        return None

    raw = getattr(feedback, "block_reason", None)
    if raw is None:
        return None

    text = str(raw).strip()
    if not text or text.upper().endswith("UNSPECIFIED"):
        return None

    return text.rsplit(".", 1)[-1].upper()
