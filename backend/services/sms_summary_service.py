"""The cycle summary that goes out by SMS, in the account's own language.

``api/sms.py`` used to build this text itself, from its own cycle-length
calculation::

    if len(logs) >= 2:
        deltas = []
        for i in range(len(logs) - 1):
            ...
        avg_cycle_length = round(sum(deltas) / len(deltas))

    next_period_days = max(avg_cycle_length - cycle_day, 0)

That is the calculation ``services/prediction_service.py`` was written to
replace, still running in a second file (issue #483). It had three
consequences worth naming, because each one is a thing a user saw:

**The SMS could not say a period was late.** ``max(..., 0)`` clamps, so a
user five days overdue was texted "Next period expected in ~0 days" while
the Home screen of the same account — reading ``prediction.isOverdue``
from ``/dashboard`` — correctly said she was five days late. One app,
two answers, and the SMS is the surface reaching users who may have no
other view of their data.

**The deltas were not cycles.** ``get_user_scores()`` returns per-day log
documents; ``upsert_log`` keys them ``{user_id}_{YYYY-MM-DD}``. So
consecutive entries are usually consecutive *days*, and the "average
cycle length" was frequently an average of 1s.
``prediction_service.observed_gaps()`` reduces to distinct start dates
before differencing, which is why it is the thing to call rather than
something to reimplement.

**It was English, to everyone.** The account carries a ``language``, the
assistant validates against a published list of eight, and
``/insights/{id}/observations`` returns translation keys so clients can
render in the user's locale. SMS ignored all of it — including for the
Hindi- and Marathi-speaking users this delivery channel exists for.

This module owns the text and nothing else: it is a pure function of
``(logs, profile, today)``, so it can be tested without Firestore, Twilio
or the wall clock, and ``api/sms.py`` keeps ownership of *who* may send
and *where* it goes (issue #382).

Encoding, and why the budget is not always 160
----------------------------------------------

An SMS is billed by segment, and a segment is not a fixed number of
characters. Text drawn from the GSM-7 alphabet fits 160 per segment;
anything outside it — every Indic script this app ships — forces UCS-2,
where a segment is 70 characters, or 67 once a message is long enough to
be split and needs concatenation headers.

70 characters cannot hold a cycle summary *and* a safety disclaimer in
Devanagari. Since ``menstrual_insights_guidelines.md`` and issue #317
make the disclaimer non-optional, the budget is deliberately two
segments for UCS-2 and one for GSM-7. That is an explicit trade — a
Hindi summary costs twice a English one — rather than the alternative,
which is dropping the disclaimer from exactly the messages whose readers
are least likely to find it elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from services.prediction_service import (
    CONFIDENCE_LOW,
    Prediction,
    SOURCE_DEFAULT,
    predict,
)

# ─── Segment budgets ──────────────────────────────────────────────────────

#: One GSM-7 segment. The ceiling ``api/sms.py`` has always used.
GSM7_SINGLE_SEGMENT = 160

#: One UCS-2 segment. Reachable only by a message short enough not to be
#: split, which a summary plus a disclaimer never is.
UCS2_SINGLE_SEGMENT = 70

#: A concatenated UCS-2 segment. Six of the 70 code units are spent on the
#: user-data header that lets the handset reassemble the parts, leaving 67.
UCS2_CONCATENATED_SEGMENT = 67

#: How many segments a non-Latin summary is allowed. Two, for the reason
#: in the module docstring: one cannot carry the disclaimer.
UCS2_MAX_SEGMENTS = 2

#: The GSM-7 default alphabet. Written out rather than derived so the
#: boundary between "one segment" and "two" is reviewable, and so a stray
#: curly quote in a template is a test failure rather than a silent
#: doubling of the bill.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

#: Characters that exist in GSM-7 only via an escape, so they cost two
#: septets each. Included because a template using a euro sign or square
#: brackets would otherwise be counted short.
GSM7_EXTENDED = set("^{}\\[~]|€")


def is_gsm7(text: str) -> bool:
    """Whether ``text`` can be sent in the GSM-7 default alphabet."""
    return all(char in GSM7_BASIC or char in GSM7_EXTENDED for char in text)


def gsm7_length(text: str) -> int:
    """Length of ``text`` in septets, counting escaped characters twice."""
    return sum(2 if char in GSM7_EXTENDED else 1 for char in text)


def segment_budget(text: str) -> int:
    """The character budget ``text`` is allowed, given its encoding.

    Not a constant, because the encoding is a property of the text: an
    English summary gets 160, a Hindi one gets two UCS-2 segments. See
    the module docstring for why the Hindi case is allowed two.
    """
    if is_gsm7(text):
        return GSM7_SINGLE_SEGMENT
    return UCS2_CONCATENATED_SEGMENT * UCS2_MAX_SEGMENTS


def measured_length(text: str) -> int:
    """``text``'s length in the units its own encoding is billed in."""
    return gsm7_length(text) if is_gsm7(text) else len(text)


#: Truncation markers, one per encoding.
#:
#: U+2026 HORIZONTAL ELLIPSIS is not in the GSM-7 alphabet. Appending it
#: to an otherwise-GSM-7 message re-encodes the *entire* message as
#: UCS-2, cutting the segment from 160 characters to 70 — so the act of
#: trimming a message to fit one segment is what pushes it to three. The
#: ASCII form costs one septet per dot and keeps the message where it was.
GSM7_ELLIPSIS = "..."
UCS2_ELLIPSIS = "…"


def ellipsis_for(text: str) -> str:
    """The truncation marker that does not change ``text``'s encoding."""
    return GSM7_ELLIPSIS if is_gsm7(text) else UCS2_ELLIPSIS


def fit_to_budget(text: str) -> str:
    """Trim ``text`` to its own segment budget without cutting a word.

    The predecessor did ``summary[:160]``, which can slice through a
    number — "in ~12 days" becoming "in ~1" is not a shorter summary, it
    is a different and wrong one, and a cycle figure is exactly what
    lands near a boundary. Cutting at the last whole word and marking the
    cut is honest about having dropped something.

    The budget and the marker are both taken from the *input*, before any
    trimming. Deriving them from the output instead is a trap worth
    naming: the marker decides the encoding, the encoding decides the
    budget, so a GSM-7 message trimmed with a U+2026 becomes a UCS-2
    message measured against a 134-character budget it has just been cut
    to 159 characters for.

    In practice this never fires for any template here. It exists so that
    if the wording is changed later, the failure is a visibly shortened
    message rather than a mangled number.
    """
    budget = segment_budget(text)
    if measured_length(text) <= budget:
        return text

    marker = ellipsis_for(text)
    room = budget - measured_length(marker)

    clipped = text[:room]
    if " " in clipped:
        clipped = clipped[: clipped.rindex(" ")]
    return clipped.rstrip(" .,।") + marker


# ─── Message templates ────────────────────────────────────────────────────
#
# One entry per situation the prediction can be in, per language. Keyed
# rather than assembled from fragments because word order is not shared
# across these languages — a summary built by concatenating "Day", the
# number and "of your cycle" is an English sentence with translated
# pieces, which is worse than English.
#
# ``{day}``, ``{length}``, ``{days}`` are the only placeholders. Every
# template is checked against them by the test suite, so a missing brace
# in a language nobody on the team reads is a failing test rather than a
# KeyError in production at send time.


@dataclass(frozen=True)
class SummaryTemplates:
    """The five sentences one language needs, plus its disclaimer."""

    #: Period is late. The case the clamped arithmetic could not express.
    overdue: str
    #: Predicted date is today.
    due_today: str
    #: Predicted date is ahead.
    upcoming: str
    #: A prediction exists but rests on no logged history at all, so the
    #: number is a population default rather than a measurement. Said
    #: differently on purpose — see ``_situation_for``.
    unmeasured: str
    #: Nothing to anchor on. No date is invented.
    no_anchor: str
    #: Appended when it fits whole. Never appended in part.
    disclaimer: str


TEMPLATES: Dict[str, SummaryTemplates] = {
    "en": SummaryTemplates(
        overdue="Rhythma: day {day} of your cycle. Your period is {days} days late.",
        due_today="Rhythma: day {day} of your cycle. Your period is expected today.",
        upcoming="Rhythma Summary: Cycle Day {day}/{length}. Next period expected in ~{days} days.",
        unmeasured="Rhythma: day {day} of your cycle. Log a few periods for a prediction based on your own cycles.",
        no_anchor="Rhythma: no period logged yet. Log your last period to get a prediction.",
        disclaimer=" Estimate only, not medical/contraceptive advice.",
    ),
    "hi": SummaryTemplates(
        overdue="रिदमा: चक्र का दिन {day}। मासिक धर्म {days} दिन देर से है।",
        due_today="रिदमा: चक्र का दिन {day}। मासिक धर्म आज अपेक्षित है।",
        upcoming="रिदमा: चक्र का दिन {day}/{length}। अगला मासिक ~{days} दिन में।",
        unmeasured="रिदमा: चक्र का दिन {day}। अपने चक्र के अनुमान के लिए कुछ मासिक दर्ज करें।",
        no_anchor="रिदमा: अभी कोई मासिक दर्ज नहीं है। अनुमान के लिए पिछला मासिक दर्ज करें।",
        disclaimer=" केवल अनुमान, चिकित्सा या गर्भनिरोधक सलाह नहीं।",
    ),
    "mr": SummaryTemplates(
        overdue="रिदमा: चक्राचा दिवस {day}। पाळी {days} दिवस उशिरा आहे।",
        due_today="रिदमा: चक्राचा दिवस {day}। पाळी आज अपेक्षित आहे।",
        upcoming="रिदमा: चक्राचा दिवस {day}/{length}। पुढील पाळी ~{days} दिवसांत।",
        unmeasured="रिदमा: चक्राचा दिवस {day}। स्वतःच्या अंदाजासाठी काही पाळ्या नोंदवा।",
        no_anchor="रिदमा: अद्याप पाळी नोंदलेली नाही। अंदाजासाठी मागील पाळी नोंदवा।",
        disclaimer=" फक्त अंदाज, वैद्यकीय किंवा गर्भनिरोधक सल्ला नाही।",
    ),
    "ta": SummaryTemplates(
        overdue="ரித்மா: சுழற்சி நாள் {day}. மாதவிடாய் {days} நாள் தாமதம்.",
        due_today="ரித்மா: சுழற்சி நாள் {day}. மாதவிடாய் இன்று எதிர்பார்க்கப்படுகிறது.",
        upcoming="ரித்மா: சுழற்சி நாள் {day}/{length}. அடுத்த மாதவிடாய் ~{days} நாளில்.",
        unmeasured="ரித்மா: சுழற்சி நாள் {day}. உங்கள் சொந்த கணிப்புக்கு சில மாதவிடாய்களைப் பதிவு செய்யவும்.",
        no_anchor="ரித்மா: இதுவரை மாதவிடாய் பதிவு இல்லை. கணிப்புக்கு கடைசி மாதவிடாயைப் பதிவு செய்யவும்.",
        disclaimer=" மதிப்பீடு மட்டுமே, மருத்துவ ஆலோசனை அல்ல.",
    ),
    "te": SummaryTemplates(
        overdue="రిథ్మా: చక్ర దినం {day}. రుతుస్రావం {days} రోజులు ఆలస్యం.",
        due_today="రిథ్మా: చక్ర దినం {day}. రుతుస్రావం ఈరోజు ఆశించబడుతోంది.",
        upcoming="రిథ్మా: చక్ర దినం {day}/{length}. తదుపరి రుతుస్రావం ~{days} రోజుల్లో.",
        unmeasured="రిథ్మా: చక్ర దినం {day}. మీ సొంత అంచనా కోసం కొన్ని రుతుస్రావాలు నమోదు చేయండి.",
        no_anchor="రిథ్మా: ఇంకా రుతుస్రావం నమోదు కాలేదు. అంచనా కోసం చివరిది నమోదు చేయండి.",
        disclaimer=" అంచనా మాత్రమే, వైద్య సలహా కాదు.",
    ),
    "kn": SummaryTemplates(
        overdue="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ಮುಟ್ಟು {days} ದಿನ ತಡವಾಗಿದೆ.",
        due_today="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ಮುಟ್ಟು ಇಂದು ನಿರೀಕ್ಷಿತ.",
        upcoming="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}/{length}. ಮುಂದಿನ ಮುಟ್ಟು ~{days} ದಿನಗಳಲ್ಲಿ.",
        unmeasured="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ನಿಮ್ಮದೇ ಅಂದಾಜಿಗಾಗಿ ಕೆಲವು ಮುಟ್ಟುಗಳನ್ನು ದಾಖಲಿಸಿ.",
        no_anchor="ರಿದ್ಮಾ: ಇನ್ನೂ ಮುಟ್ಟು ದಾಖಲಾಗಿಲ್ಲ. ಅಂದಾಜಿಗಾಗಿ ಕೊನೆಯದನ್ನು ದಾಖಲಿಸಿ.",
        disclaimer=" ಅಂದಾಜು ಮಾತ್ರ, ವೈದ್ಯಕೀಯ ಸಲಹೆಯಲ್ಲ.",
    ),
    "ml": SummaryTemplates(
        overdue="റിഥ്മ: ചക്ര ദിനം {day}. ആർത്തവം {days} ദിവസം വൈകി.",
        due_today="റിഥ്മ: ചക്ര ദിനം {day}. ആർത്തവം ഇന്ന് പ്രതീക്ഷിക്കുന്നു.",
        upcoming="റിഥ്മ: ചക്ര ദിനം {day}/{length}. അടുത്ത ആർത്തവം ~{days} ദിവസത്തിൽ.",
        unmeasured="റിഥ്മ: ചക്ര ദിനം {day}. സ്വന്തം പ്രവചനത്തിനായി കുറച്ച് ആർത്തവങ്ങൾ രേഖപ്പെടുത്തുക.",
        no_anchor="റിഥ്മ: ആർത്തവം രേഖപ്പെടുത്തിയിട്ടില്ല. പ്രവചനത്തിനായി അവസാനത്തേത് രേഖപ്പെടുത്തുക.",
        disclaimer=" കണക്കാക്കൽ മാത്രം, വൈദ്യോപദേശമല്ല.",
    ),
    "gu": SummaryTemplates(
        overdue="રિધ્મા: ચક્રનો દિવસ {day}. માસિક {days} દિવસ મોડું છે.",
        due_today="રિધ્મા: ચક્રનો દિવસ {day}. માસિક આજે અપેક્ષિત છે.",
        upcoming="રિધ્મા: ચક્રનો દિવસ {day}/{length}. આગામી માસિક ~{days} દિવસમાં.",
        unmeasured="રિધ્મા: ચક્રનો દિવસ {day}. તમારા પોતાના અંદાજ માટે થોડા માસિક નોંધો.",
        no_anchor="રિધ્મા: હજુ કોઈ માસિક નોંધાયું નથી. અંદાજ માટે છેલ્લું નોંધો.",
        disclaimer=" માત્ર અંદાજ, તબીબી સલાહ નથી.",
    ),
}

#: What an unknown or missing ``language`` falls back to. English rather
#: than "nothing", because a summary in the wrong language is still a
#: summary and a user can act on it; an empty SMS is a wasted send.
DEFAULT_LANGUAGE = "en"

SUPPORTED_SMS_LANGUAGES = frozenset(TEMPLATES)

#: Situations, in the order they are tested. Named so a test can assert on
#: which branch was taken without matching on translated prose.
SITUATION_NO_ANCHOR = "no_anchor"
SITUATION_UNMEASURED = "unmeasured"
SITUATION_OVERDUE = "overdue"
SITUATION_DUE_TODAY = "due_today"
SITUATION_UPCOMING = "upcoming"


def resolve_language(profile: Optional[Dict[str, Any]]) -> str:
    """The language code to write in, from the account's own profile.

    Tolerant of the shapes a stored value actually takes — ``"HI"``,
    ``"hi-IN"``, a stray space — because this field has been writable
    through ``PATCH /auth/me`` for longer than it has been validated
    (issue #136), so old documents hold forms the current validator
    would refuse.
    """
    raw = (profile or {}).get("language")
    if not isinstance(raw, str):
        return DEFAULT_LANGUAGE

    code = raw.strip().lower().replace("_", "-").split("-")[0]
    return code if code in TEMPLATES else DEFAULT_LANGUAGE


def _situation_for(prediction: Prediction) -> str:
    """Which of the five sentences this prediction calls for.

    ``unmeasured`` is separated from ``upcoming`` deliberately. A user
    with no logged cycles still gets a ``next_period_date`` — the
    estimate falls back to her declared cycle length and then to the
    population default — and texting her "next period expected in ~28
    days" presents a population constant as if it were a measurement of
    her. The prediction already records which happened, in
    ``cycle_length.source``, so the text can too.
    """
    if prediction.last_period_start is None or prediction.days_until_next_period is None:
        return SITUATION_NO_ANCHOR

    if (
        prediction.cycle_length.source == SOURCE_DEFAULT
        and prediction.cycle_length.sample_size == 0
        and not prediction.is_overdue
    ):
        return SITUATION_UNMEASURED

    if prediction.is_overdue:
        return SITUATION_OVERDUE
    if prediction.days_until_next_period == 0:
        return SITUATION_DUE_TODAY
    return SITUATION_UPCOMING


def _render(templates: SummaryTemplates, situation: str, prediction: Prediction) -> str:
    """Fill one template from the prediction. No fallbacks, on purpose.

    Every placeholder used by a template is guaranteed present by
    ``_situation_for`` having already established the branch, so a
    ``KeyError`` here means a template gained a placeholder the situation
    cannot supply — which should be a loud test failure, not a silently
    half-rendered SMS.
    """
    sentence = getattr(templates, situation)
    return sentence.format(
        day=prediction.current_cycle_day,
        length=prediction.cycle_length.days,
        days=(
            prediction.days_overdue
            if situation == SITUATION_OVERDUE
            else prediction.days_until_next_period
        ),
    )


def compose(prediction: Prediction, language: str = DEFAULT_LANGUAGE) -> str:
    """The text to send, disclaimer included when it fits whole.

    The disclaimer is all-or-nothing. Half of "not medical/contraceptive
    advice" says something the whole sentence does not, so it is either
    appended entire or omitted entire — never trimmed into.
    """
    templates = TEMPLATES.get(language, TEMPLATES[DEFAULT_LANGUAGE])
    situation = _situation_for(prediction)
    summary = _render(templates, situation, prediction)

    combined = summary + templates.disclaimer
    if measured_length(combined) <= segment_budget(combined):
        return combined
    return fit_to_budget(summary)


def build_summary(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> str:
    """The SMS body for one user, from her logs and profile.

    Pure: no Firestore, no Twilio, no wall clock unless ``today`` is
    omitted. ``api/sms.py`` supplies all three.
    """
    prediction = predict(logs, profile=profile, today=today)
    return compose(prediction, resolve_language(profile))


def describe(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """``build_summary`` plus the reasoning behind it, for tests and logs.

    Kept separate from ``build_summary`` so the send path stays a
    single-return function, while a test can assert "this took the
    overdue branch" without pattern-matching translated prose, and an
    operator can answer "why did this user get that text?" without
    re-running the prediction by hand.
    """
    prediction = predict(logs, profile=profile, today=today)
    language = resolve_language(profile)
    body = compose(prediction, language)

    return {
        "body": body,
        "language": language,
        "situation": _situation_for(prediction),
        "encoding": "GSM-7" if is_gsm7(body) else "UCS-2",
        "length": measured_length(body),
        "budget": segment_budget(body),
        "confidence": prediction.cycle_length.confidence,
        "estimateSource": prediction.cycle_length.source,
        "isOverdue": prediction.is_overdue,
        "daysOverdue": prediction.days_overdue,
        "daysUntilNextPeriod": prediction.days_until_next_period,
    }


def template_placeholders() -> Dict[str, List[str]]:
    """Every ``{placeholder}`` each situation's English template uses.

    The English entry is the reference every other language is checked
    against, so a translation that drops ``{days}`` — and would therefore
    text someone a sentence with a hole in it — fails a test rather than
    reaching a handset.
    """
    import string

    reference = TEMPLATES[DEFAULT_LANGUAGE]
    return {
        situation: sorted(
            {
                name
                for _, name, _, _ in string.Formatter().parse(getattr(reference, situation))
                if name
            }
        )
        for situation in (
            SITUATION_OVERDUE,
            SITUATION_DUE_TODAY,
            SITUATION_UPCOMING,
            SITUATION_UNMEASURED,
            SITUATION_NO_ANCHOR,
        )
    }


__all__ = [
    "DEFAULT_LANGUAGE",
    "GSM7_ELLIPSIS",
    "GSM7_SINGLE_SEGMENT",
    "UCS2_ELLIPSIS",
    "ellipsis_for",
    "SITUATION_DUE_TODAY",
    "SITUATION_NO_ANCHOR",
    "SITUATION_OVERDUE",
    "SITUATION_UNMEASURED",
    "SITUATION_UPCOMING",
    "SUPPORTED_SMS_LANGUAGES",
    "TEMPLATES",
    "UCS2_CONCATENATED_SEGMENT",
    "UCS2_MAX_SEGMENTS",
    "SummaryTemplates",
    "build_summary",
    "compose",
    "describe",
    "fit_to_budget",
    "gsm7_length",
    "is_gsm7",
    "measured_length",
    "resolve_language",
    "segment_budget",
    "template_placeholders",
]
