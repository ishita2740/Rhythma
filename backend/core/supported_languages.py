"""The locale codes the product ships a UI translation for (issue #136).

``UserProfileUpdate.language`` is the account's *UI* locale preference — the
language the app renders in — not the narrower set the AI assistant answers
in (``api.assistant.SUPPORTED_LANGUAGES``) or the set the SMS summary writer
has templates for (``services.sms_summary_service.SUPPORTED_SMS_LANGUAGES``).

Until now that field accepted any string. Every other constrained field on
the model is bounded (``age`` is ``ge=10, le=120``, ``cycle_length`` is
``ge=15, le=60``), but ``language`` was free text, so a direct API call could
store ``"klingon"`` — or a megabyte of it — on the user document, bypassing
the client-side ``LocaleProvider.setLocale()`` restriction and leaving
downstream code to cope with a locale nothing else in the app understands.

**Why the list lives here.** The issue asks for one shared place so the
allowlist cannot drift from the set the app actually ships. The clients each
carry one translation file per code:

* Flutter — ``rhythma_flutter/lib/l10n/app_<code>.arb``
* Web — ``web/src/i18n/locales/<code>.json``

Both ship exactly the codes below. When a new language is added, its file
lands in both clients and its code is added here in the same change, the way
a new ``.arb`` file and its ``supported_languages.dart`` entry go together on
the Flutter side.

Region tags (``en-US``, ``hi-IN``) are reduced to their base language before
the check, because the web client sends ``i18n.language`` and the browser
language detector routinely reports a region tag — the same normalisation
``api.assistant`` applies for the same reason.
"""

from __future__ import annotations

from typing import Any, Optional

#: The canonical set of UI locale codes the app ships a translation for.
#: Kept sorted for a stable error message; membership is what matters.
SUPPORTED_LANGUAGE_CODES = frozenset(
    {
        "as",   # Assamese
        "bn",   # Bengali
        "en",   # English
        "gu",   # Gujarati
        "hi",   # Hindi
        "kn",   # Kannada
        "ks",   # Kashmiri
        "mai",  # Maithili
        "ml",   # Malayalam
        "mr",   # Marathi
        "ne",   # Nepali
        "or",   # Odia
        "pa",   # Punjabi
        "sat",  # Santali
        "sd",   # Sindhi
        "ta",   # Tamil
        "te",   # Telugu
        "ur",   # Urdu
    }
)

#: Longest a submitted value can be before it is refused unparsed. A locale
#: code is a handful of characters; anything longer than a region tag could
#: ever be is not a locale code, and is rejected before any normalisation so
#: a large blob is turned away cheaply.
MAX_LANGUAGE_CHARS = 35


def normalize_language(value: Any) -> Optional[str]:
    """Validate a UI locale preference and return its canonical base code.

    ``None`` passes through: a profile is built up over time, and a request
    that omits ``language`` is not the same as one that sets it to nonsense.
    An empty or whitespace-only string is treated as omission too, since that
    is what a client clearing the field tends to send.

    Accepted, each reduced to its base code:

    * ``en``, ``hi`` — a bare supported code
    * ``en-US``, ``hi_IN`` — a region tag whose base is supported

    Refused, with a message naming the supported set:

    * anything that is not text, or is longer than a locale code could be
    * any code, bare or region-tagged, whose base is not in
      :data:`SUPPORTED_LANGUAGE_CODES`

    Raises ``ValueError``; Pydantic turns that into the standard 422 envelope
    with the field's location attached, so this never needs to know about
    HTTP — the same arrangement ``core/profile_validation`` uses.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(_unsupported_message(value))

    text = value.strip()
    if not text:
        return None

    if len(text) > MAX_LANGUAGE_CHARS:
        raise ValueError(_unsupported_message(value))

    # Reduce a region tag to its base language: ``en-US`` / ``hi_IN`` → the
    # code the app actually keys translations by.
    normalized = text.lower().replace("_", "-").split("-")[0]

    if normalized not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(_unsupported_message(value))

    return normalized


def _unsupported_message(value: Any) -> str:
    supported = ", ".join(sorted(SUPPORTED_LANGUAGE_CODES))
    return (
        f"Unsupported language {value!r}. "
        f"Supported languages: {supported}."
    )


__all__ = [
    "MAX_LANGUAGE_CHARS",
    "SUPPORTED_LANGUAGE_CODES",
    "normalize_language",
]
