"""Whether an account may take an email address (issue #531).

``core/email_identity`` answers "are these two strings the same address?".
This module answers the question one layer up: *given that this account
wants to be reachable at this address, is it allowed to be?*

The two are deliberately separate. ``email_identity`` has no imports and
is used by ``services/firestore_service`` itself, so it cannot look
anything up. This module reads the ``users`` collection, so it sits above
the service layer where ``core/auth_router`` and ``api/provider`` both
already are.

### The hole this closes

``POST /auth/register`` refused a duplicate address:

    user = UserService.get_user_by_email(data.email)
    if user:
        raise HTTPException(409, "An account with this email already exists")

``PATCH /auth/profile`` reached the same collection, wrote the same field,
and refused nothing:

    updates = {k: v for k, v in profile_data.model_dump().items() if v is not None}
    UserService.update_user(current_user["id"], updates)

So one authenticated request put a second ``users`` document into the
collection under an address that already identified somebody else.

That matters because email is the identity key for this API, and every
lookup that uses it bottoms out in a single unordered query:

    for user in db.collection("users").where(field, "==", value).limit(1).stream():

``.limit(1)`` over two matching documents returns *whichever one Firestore
hands back first*, and nothing constrains which. So a duplicate does not
create a tidy "two accounts, one address" situation — it creates a coin
flip, re-tossed on every call, inside:

* ``POST /auth/login`` — the victim's correct password stops verifying,
  because the lookup can resolve to the other document.
* ``POST /auth/reset-password`` — the token is verified against the
  *address*, then the account is resolved by the same address, so a
  victim's own reset can write her new password onto the other document.
* ``ConsentService.grant`` — a patient shares her cycle history by typing
  a clinician's address, and the consent binds to ``provider["id"]``.
  A provider-role account holding that address is a valid answer.

The consent gate from #267 is not broken by this and does not need to
change: it is being handed the wrong provider id before it runs.

### Why a helper rather than four lines in the route

A guard written into ``update_profile`` would protect ``update_profile``.
This bug exists precisely because the guard was written into ``register``
and the second write path did not inherit it. Anything that lets an
account choose its own address — a future admin route, a merge flow, a
social sign-in that copies a provider-supplied address onto an existing
account — asks the same question, and should get the same answer from
the same place.

### What is deliberately *not* decided here

**Whether the caller may edit this account at all.** That is
authentication, settled by ``get_current_user`` before anything here
runs. This module takes an account id as a given.

**Whether the string is an address.** ``EmailStr`` on the request model
has already decided that.

**What to do about ``email_verified``.** :func:`classify_email_change`
reports that the address is *new*; resetting the flag and issuing a
verification token is the route's business, because only the route knows
which token namespace and which response shape it is working in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from core.email_identity import normalize_email, same_email
from services.firestore_service import UserService

__all__ = [
    "EMAIL_TAKEN_DETAIL",
    "EmailChange",
    "EmailChangeKind",
    "classify_email_change",
    "enforce_email_available",
]


#: The message a rejected claim carries. Identical to the one
#: ``POST /auth/register`` returns for the same collision, on purpose: a
#: user who has typed an address somebody else holds should read the same
#: sentence whichever screen she typed it on.
EMAIL_TAKEN_DETAIL = "An account with this email already exists"


class EmailChangeKind(str, Enum):
    """What a requested address amounts to for a given account."""

    #: No address was supplied — the caller is not touching the field.
    ABSENT = "absent"

    #: The address the account already has, in some capitalisation.
    #: Writing it is a no-op, and refusing it would be a 409 for a request
    #: that changes nothing.
    UNCHANGED = "unchanged"

    #: A different address that no other account holds.
    AVAILABLE = "available"

    #: A different address that another account already holds.
    TAKEN = "taken"


@dataclass(frozen=True)
class EmailChange:
    """The verdict on one requested address.

    ``normalized`` is the canonical form (see ``email_identity``) and is
    what a caller should write, so the value that was checked and the
    value that is stored cannot differ. It is ``""`` when ``kind`` is
    :attr:`EmailChangeKind.ABSENT`.

    ``holder_id`` is set only for :attr:`EmailChangeKind.TAKEN`, and only
    so a caller can tell "somebody else has it" from "I have it" without
    a second lookup. It is never put in a response: which account holds an
    address is not something an unrelated caller gets to learn.
    """

    kind: EmailChangeKind
    normalized: str
    holder_id: Optional[str] = None

    @property
    def is_new_address(self) -> bool:
        """Whether accepting this would change what address the account has.

        The flag a caller needs to decide whether ``email_verified`` still
        means anything. ``UNCHANGED`` is false here — re-submitting your
        own address in different capitalisation must not un-verify you.
        """
        return self.kind is EmailChangeKind.AVAILABLE


def classify_email_change(
    *,
    user_id: str,
    requested_email: Optional[str],
    current_email: Optional[str] = None,
) -> EmailChange:
    """Decide what ``requested_email`` means for the account ``user_id``.

    ``current_email`` is optional: pass it when the caller has already
    loaded the user document (``PATCH /auth/profile`` has), and this makes
    no read at all for the common no-op case. Omit it and the account is
    fetched here.

    The order of the checks is the point:

    1. **Absent** first, so a request that does not mention the field
       never reads the collection.
    2. **Unchanged** second, compared with ``same_email`` so that
       ``Sana@Example.com`` submitted by the holder of ``sana@example.com``
       is recognised as hers. Checking availability first would find *her
       own document* and report the address taken, which is how a naive
       "is this email used?" guard turns saving your own profile into a
       409.
    3. **Taken** last, and only then. The lookup uses the raw string
       because ``get_user_by_email`` canonicalises internally *and* falls
       back to the string as typed, which is what lets it also find a
       document written before #380 under a different capitalisation. A
       pre-#380 duplicate is still a duplicate.
    """
    if requested_email is None or not str(requested_email).strip():
        return EmailChange(kind=EmailChangeKind.ABSENT, normalized="")

    requested_raw = str(requested_email).strip()
    normalized = normalize_email(requested_raw)

    if current_email is None:
        existing_account = UserService.get_user_by_id(user_id) or {}
        current_email = existing_account.get("email")

    if same_email(current_email, normalized):
        return EmailChange(kind=EmailChangeKind.UNCHANGED, normalized=normalized)

    holder = UserService.get_user_by_email(requested_raw)

    # A holder whose id *is* this account can only happen when the caller
    # passed a stale `current_email` — the document is the authority, so
    # believe it over the argument rather than reporting the account has
    # taken its own address.
    if holder is None or holder.get("id") == user_id:
        return EmailChange(kind=EmailChangeKind.AVAILABLE, normalized=normalized)

    return EmailChange(
        kind=EmailChangeKind.TAKEN,
        normalized=normalized,
        holder_id=holder.get("id"),
    )


def enforce_email_available(
    *,
    user_id: str,
    requested_email: Optional[str],
    current_email: Optional[str] = None,
) -> EmailChange:
    """:func:`classify_email_change`, raising 409 on a collision.

    409 rather than 403 or 422: the address is well-formed and the caller
    is allowed to change her own address — the request conflicts with the
    state of the collection, which is what 409 is for, and it is what
    ``POST /auth/register`` already answers for the identical collision.

    The response says only that the address is taken. It deliberately does
    not say by whom, and the message is byte-identical to registration's,
    so this route is no better an account-enumeration oracle than the one
    that already exists.
    """
    change = classify_email_change(
        user_id=user_id,
        requested_email=requested_email,
        current_email=current_email,
    )

    if change.kind is EmailChangeKind.TAKEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=EMAIL_TAKEN_DETAIL,
        )

    return change


def apply_email_change(
    updates: Dict[str, Any],
    change: EmailChange,
) -> Dict[str, Any]:
    """Fold an accepted ``change`` into a pending ``updates`` payload.

    Returns ``updates`` (mutated) so it can be used inline.

    Three rules, all of them about not letting a flag outrun what has been
    proven:

    * An **absent** address removes ``email`` from the payload entirely,
      so a client that sends ``{"email": null}`` cannot blank the identity
      key by accident.
    * An **unchanged** address is written in canonical form and leaves
      ``email_verified`` alone. Re-saving your profile must not un-verify
      you.
    * A **new** address is written *and* sets ``email_verified`` to
      ``False``. ``POST /auth/register`` starts every account unverified;
      an address arriving through a profile edit has had no more proof of
      control than one arriving through registration, and until #531 it
      inherited the previous address's verified flag — which
      ``POST /auth/login`` then returned to the client as
      ``email_verified: true``.
    """
    if change.kind is EmailChangeKind.ABSENT:
        updates.pop("email", None)
        return updates

    updates["email"] = change.normalized
    if change.is_new_address:
        updates["email_verified"] = False

    return updates
