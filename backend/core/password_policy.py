"""Password rules for account creation and password reset (issue #330).

`RegisterRequest.password` was a bare `str`. `a` was a valid Rhythma
password; so was the empty string, `123456`, and the user's own email
address. `ResetPasswordRequest.new_password` had the same gap, so an account
created with a good password could be *reset* to a one-character one.

Everything about what makes a password acceptable lives here, and both
routes call the same function, so the two paths cannot drift apart — which
is the failure this module mostly exists to prevent. A rule added for
registration but forgotten on reset is worse than no rule, because it looks
enforced.

Design notes:

*No composition requirements.* There is no "must contain an uppercase letter
and a symbol" rule, deliberately. NIST SP 800-63B stopped recommending them
because they push people toward predictable transformations — `Password1!`
satisfies every composition rule anyone has ever written and is on every
cracking list. Length, plus a denylist of the passwords that actually get
tried, is the better trade for an audience typing on phone keyboards.

*Every failed rule is reported at once.* A form that surfaces one problem
per submission is how users converge on the shortest thing that gets past
it.

*The 72-byte ceiling is a real limit, not a stylistic one.* bcrypt hashes
at most 72 bytes and silently ignores the rest, so a longer passphrase is
not the password the user thinks it is. This matters far more here than in
an English-only product: UTF-8 spends three bytes on most Devanagari,
Tamil, Telugu, Kannada and Malayalam characters, so a perfectly reasonable
24-character Hindi passphrase is already over the line. Rejecting it with
an explanation beats accepting it and quietly keeping the first 72 bytes.
"""

from __future__ import annotations

import os
import re
import string
from dataclasses import dataclass
from typing import List, Optional

from core.errors import AppError

#: Floor for password length. NIST SP 800-63B puts the minimum at 8 for
#: user-chosen secrets; this is the same number, overridable upward for a
#: deployment that wants to be stricter.
DEFAULT_MIN_LENGTH = 8

#: bcrypt truncates at 72 *bytes*. Not configurable — it is a property of
#: the hash, not a policy choice.
MAX_PASSWORD_BYTES = 72

#: The shortest run of the user's own identity that counts as "your
#: password contains your email". Two or three characters would fire on
#: ordinary words; four is short enough to catch `sana` in `sana@example.com`.
MIN_IDENTIFIER_FRAGMENT = 4

#: Passwords common enough that a guesser tries them before anything else.
#: Deliberately small and hand-kept rather than a bundled 100k-line list:
#: this is the head of the distribution, where nearly all the value is, and
#: it costs no dependency and no file read at import. A larger list (or a
#: k-anonymity check against a breach corpus) is a reasonable later step.
COMMON_PASSWORDS = frozenset(
    {
        "123456", "123456789", "12345678", "1234567", "1234567890", "12345",
        "password", "password1", "password123", "passw0rd", "p@ssw0rd",
        "qwerty", "qwerty123", "qwertyuiop", "asdfghjkl", "zxcvbnm",
        "111111", "000000", "123123", "654321", "666666", "888888",
        "abc123", "abcd1234", "a1b2c3d4", "letmein", "welcome", "welcome1",
        "iloveyou", "monkey", "dragon", "sunshine", "princess", "football",
        "baseball", "superman", "trustno1", "master", "shadow", "michael",
        "jennifer", "computer", "internet", "samsung", "google", "facebook",
        "whatsapp", "india123", "indian123", "bharat123", "krishna",
        "ganesh", "chennai", "mumbai123", "delhi123", "admin", "admin123",
        "root", "test123", "changeme", "secret", "login", "pass1234",
        "rhythma", "rhythma123", "period123", "health123",
    }
)

#: Sources for "this is just a run along the keyboard/alphabet".
_SEQUENCES = (
    string.ascii_lowercase,
    string.digits,
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)

#: How long a sequential run has to be before it disqualifies a password.
#: Five keeps `abcde` out while leaving ordinary words that happen to
#: contain `rst` alone.
_MAX_SEQUENCE_RUN = 5


def min_length() -> int:
    """Minimum length, overridable via ``PASSWORD_MIN_LENGTH``.

    A configured value below the default is ignored. Making a password
    policy *weaker* by environment variable is not a knob worth having:
    it is far more likely to be a mistake than an intention, and the
    consequence is silent.
    """
    raw = os.getenv("PASSWORD_MIN_LENGTH")
    if raw is None:
        return DEFAULT_MIN_LENGTH
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MIN_LENGTH
    return max(value, DEFAULT_MIN_LENGTH)


@dataclass(frozen=True)
class PasswordFailure:
    """One rule the submitted password broke.

    ``code`` is stable and machine-readable so a client can localize the
    message itself; ``message`` is the English fallback for clients that
    don't.
    """

    code: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


class WeakPasswordError(AppError):
    """422 carrying every rule the password broke, not just the first."""

    status_code = 422
    code = "weak_password"
    message = "That password doesn't meet the requirements."


def _identifier_fragments(email: Optional[str], username: Optional[str]) -> List[str]:
    """Pieces of the user's own identity a password shouldn't contain.

    From `sana.k@example.com` this yields `sana.k`, `sana`, `k` (dropped —
    too short) and `example`. The domain is included because
    `example2026` is exactly the kind of password someone signing up on a
    company address picks.
    """
    fragments: List[str] = []

    if username:
        fragments.append(username)

    if email and "@" in email:
        local, _, domain = email.partition("@")
        fragments.append(local)
        fragments.extend(re.split(r"[._\-+]", local))
        # Only the registrable-ish part: `example` from `example.com`, not
        # `com`, which would fire on any password containing "com".
        domain_parts = domain.split(".")
        if domain_parts:
            fragments.append(domain_parts[0])
    elif email:
        fragments.append(email)

    return [f.lower() for f in fragments if len(f) >= MIN_IDENTIFIER_FRAGMENT]


def _has_long_sequence(password: str) -> bool:
    """True if the password contains a run along a keyboard row or the alphabet."""
    lowered = password.lower()
    for source in _SEQUENCES:
        reverse = source[::-1]
        for start in range(len(source) - _MAX_SEQUENCE_RUN + 1):
            if source[start : start + _MAX_SEQUENCE_RUN] in lowered:
                return True
            if reverse[start : start + _MAX_SEQUENCE_RUN] in lowered:
                return True
    return False


def validate_password(
    password: str,
    *,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> List[PasswordFailure]:
    """Return every rule ``password`` breaks. Empty list means acceptable.

    Never raises and never logs the password. Callers that want an HTTP
    error should use :func:`enforce_password_policy`.
    """
    failures: List[PasswordFailure] = []
    required = min_length()

    if password is None or password == "":
        # Returned alone: every other rule would fire too, and eight
        # complaints about an empty box is noise, not help.
        return [
            PasswordFailure(
                code="password_required",
                message="Please enter a password.",
            )
        ]

    if password.strip() == "":
        return [
            PasswordFailure(
                code="password_blank",
                message="A password cannot be only spaces.",
            )
        ]

    if len(password) < required:
        failures.append(
            PasswordFailure(
                code="too_short",
                message=f"Use at least {required} characters.",
            )
        )

    byte_length = len(password.encode("utf-8"))
    if byte_length > MAX_PASSWORD_BYTES:
        failures.append(
            PasswordFailure(
                code="too_long",
                message=(
                    f"That password is too long to be stored safely "
                    f"({byte_length} bytes; the limit is {MAX_PASSWORD_BYTES}). "
                    "Please shorten it."
                ),
            )
        )

    if password.lower() in COMMON_PASSWORDS:
        failures.append(
            PasswordFailure(
                code="too_common",
                message="That password is one of the most commonly used ones. Please pick another.",
            )
        )

    lowered = password.lower()
    for fragment in _identifier_fragments(email, username):
        if fragment in lowered:
            failures.append(
                PasswordFailure(
                    code="contains_identifier",
                    message="Your password shouldn't contain your email address or username.",
                )
            )
            break

    if len(set(password)) < 4 and len(password) >= 4:
        failures.append(
            PasswordFailure(
                code="not_varied_enough",
                message="Use a few more different characters — this one repeats too much.",
            )
        )

    if _has_long_sequence(password):
        failures.append(
            PasswordFailure(
                code="sequential",
                message="Avoid runs like 12345 or qwerty — they're the first thing guessed.",
            )
        )

    return failures


def enforce_password_policy(
    password: str,
    *,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> None:
    """Raise :class:`WeakPasswordError` if ``password`` breaks any rule.

    The raised error carries *all* failures in ``details`` so a form can
    show them together.
    """
    failures = validate_password(password, email=email, username=username)
    if not failures:
        return

    raise WeakPasswordError(
        details=[failure.to_dict() for failure in failures],
    )


def requirements() -> dict:
    """The policy, described for a client to render before submission.

    Served by ``GET /auth/password-requirements`` so the rules a user is
    shown come from the same place as the rules she is judged against,
    rather than being retyped in each client and going stale.
    """
    return {
        "minLength": min_length(),
        "maxBytes": MAX_PASSWORD_BYTES,
        "rules": [
            {
                "code": "too_short",
                "message": f"At least {min_length()} characters.",
            },
            {
                "code": "too_long",
                "message": (
                    f"No longer than {MAX_PASSWORD_BYTES} bytes — note that "
                    "letters in Indian-language scripts take about three "
                    "bytes each."
                ),
            },
            {
                "code": "too_common",
                "message": "Not one of the most commonly used passwords.",
            },
            {
                "code": "contains_identifier",
                "message": "Doesn't contain your email address or username.",
            },
            {
                "code": "not_varied_enough",
                "message": "More than a few repeated characters.",
            },
            {
                "code": "sequential",
                "message": "No long runs like 12345 or qwerty.",
            },
        ],
    }
