"""One definition of "are these two addresses the same person?" (issue #380).

An email address is the primary identity key on this API: it is what
``users`` documents are looked up by, what a password-reset token is
filed under, and what the per-account rate-limit bucket is derived from.
It also arrives from a form, typed by a human, on a phone keyboard that
capitalises the first letter of a field by default.

``Doc@Clinic.in``, ``doc@clinic.in`` and ``DOC@CLINIC.IN ``  are one
person typing one address. Without a single point that says so, they
become three accounts holding three separate cycle histories, and the one
she reaches depends on how her keyboard felt that morning.

``core/auth_router.py`` already had a ``normalize_email`` with that
docstring, and nothing in that module called it — ``api/provider.py`` was
its only caller, so the provider flow normalised and the patient flow did
not. That asymmetry is the bug this module exists to make impossible: it
lives below both of them, has no imports, and is what
``services/firestore_service.py`` uses too, which ``core/auth_router.py``
could never be (it imports the service, so the service cannot import it
back).

Deliberately *not* done here:

**No local-part case folding beyond ``lower()``, and no dot-stripping or
``+tag`` removal.** Gmail treats ``s.ana+news@gmail.com`` and
``sana@gmail.com`` as one mailbox; RFC 5321 says the local part is the
destination server's business and nobody else's. A provider-specific
rule applied globally would refuse two genuinely different addresses on
hosts that are case- or dot-sensitive, and refusing a legitimate sign-up
is a worse failure than accepting a duplicate. Case folding is the one
transformation every mainstream provider agrees on.

**No validation.** ``EmailStr`` on the request models already decides
whether a string is an address. This decides what an address is *called*
once it is one.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["normalize_email", "same_email"]


def normalize_email(email: Optional[str]) -> str:
    """The canonical form of ``email``: stripped and lower-cased.

    Returns ``""`` for ``None`` or a blank string rather than raising —
    every caller here is either about to look the result up (where a miss
    is the correct answer) or about to store it alongside a value
    ``EmailStr`` has already validated.
    """
    return (email or "").strip().lower()


def same_email(left: Optional[str], right: Optional[str]) -> bool:
    """Whether two addresses identify the same account.

    A named function rather than ``a.lower() == b.lower()`` at each call
    site, so the comparison cannot drift from the normalisation used to
    write the value in the first place.
    """
    normalized = normalize_email(left)
    return bool(normalized) and normalized == normalize_email(right)
