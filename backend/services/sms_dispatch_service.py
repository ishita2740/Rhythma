"""Deciding who is due a recurring SMS summary, and sending it (issue #532).

All three clients offer to switch on recurring SMS summaries. The web
toggle reads "Enable weekly SMS summaries" and the copy above it promises
"a weekly text summary of your cycle predictions and logging reminders".
``POST /sms/settings`` stored the flag:

    UserService.update_user(user_id, {..., "sms_enabled": settings.enabled})

and ``sms_enabled`` had exactly two readers in the whole repository —
``GET /sms/settings``, reading it back to the screen that set it, and the
privacy export, listing it. There was no scheduler, no background task
and no dispatch path anywhere. ``POST /sms/send-summary`` was the only
code that ever reached Twilio, and only when a user tapped "Send now".

So the flag was write-only. A user in a low-connectivity area — the exact
user the README names for this feature — turned it on, watched it stay on
across restarts because the settings endpoint echoed it back, and waited
for a message no code existed to send.

### Shape of the fix

**Due-ness is a pure function of (user document, now).** :func:`is_due`
takes no clock and no database — it is handed both — so the whole
scheduling rule is testable without freezing time or seeding Firestore,
and so the same rule can be asked about one user (before a manual send)
and about all of them (in a batch) without existing twice.

**No scheduler lives inside the API process.** A thread or an
``APScheduler`` instance inside a web worker fires once per worker, which
on any multi-process deployment means one text per worker per week, and
it fires not at all when the process is asleep. Instead there is one
batch entry point, :func:`dispatch_due`, driven by whatever external cron
the deployment already has — the same reasoning that put refresh and
reset tokens into Firestore in #417 rather than a module-level dict.

**Idempotency is stored, not assumed.** Each successful send stamps
``sms_last_sent_at`` on the user document, and :func:`is_due` reads it.
A cron that double-fires, a retry after a timeout, or two overlapping
batches cannot text anybody twice, because the second pass no longer
considers her due. This is the property that makes the endpoint safe to
call more often than the cadence, which is what any real cron ends up
doing.

**A failure is per-user, never per-batch.** One unreachable number must
not stop the other ninety-nine summaries. Failures are counted, reported
and skipped over; only a user who was actually sent to is stamped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from services import firestore_service as _firestore
from services.firestore_service import UserService
from utils.logger import logger

__all__ = [
    "DEFAULT_BATCH_LIMIT",
    "MAX_BATCH_LIMIT",
    "SMS_SUMMARY_INTERVAL_DAYS",
    "DispatchOutcome",
    "DispatchReport",
    "SKIP_DISABLED",
    "SKIP_NOT_DUE",
    "SKIP_NO_PHONE",
    "as_utc",
    "dispatch_due",
    "due_users",
    "is_due",
    "mark_summary_sent",
    "next_due_at",
    "skip_reason",
]

USERS_COLLECTION = "users"

#: How often a subscribed user is texted. Seven days because that is what
#: every client's copy already promises — the label is the specification,
#: and a cadence that disagreed with it would be the same bug in a new
#: place.
SMS_SUMMARY_INTERVAL_DAYS = 7

#: Field stamped on the user document after a successful send, and read
#: back by :func:`is_due`. Stored as an ISO-8601 string rather than a
#: ``datetime`` so a Firestore round trip cannot hand back a
#: ``DatetimeWithNanoseconds`` that compares oddly against a naive value —
#: :func:`as_utc` normalises either shape on the way in.
LAST_SENT_FIELD = "sms_last_sent_at"

#: Ceiling on one batch. A batch does a Firestore read per user, a scoring
#: pass over her cycle logs, a Twilio call and a write, so the page size
#: multiplies four kinds of work rather than only response bytes. Same
#: reasoning as ``provider_service.MAX_PATIENTS_PAGE``.
MAX_BATCH_LIMIT = 500
DEFAULT_BATCH_LIMIT = 100

#: Why a user in the collection was passed over. Returned rather than
#: logged-and-forgotten so an operator reading the batch response can tell
#: "nobody had it switched on" from "everybody was texted yesterday" —
#: which look identical in a bare ``sent: 0``.
SKIP_DISABLED = "disabled"
SKIP_NO_PHONE = "no_phone"
SKIP_NOT_DUE = "not_due"


def as_utc(value: Any) -> Optional[datetime]:
    """Normalise a stored timestamp to an aware UTC ``datetime``.

    Three shapes reach this: the ISO-8601 string this module writes, a
    ``datetime`` (Firestore returns its own ``DatetimeWithNanoseconds``
    subclass), and ``None`` for a user who has never been sent to.

    A naive ``datetime`` is *assumed* UTC rather than rejected. Everything
    in this codebase that writes a timestamp writes ``datetime.now(timezone.utc)``,
    and refusing a naive value would mean one legacy document could raise
    mid-batch and stop ninety-nine other summaries — a worse failure than
    the assumption.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # `fromisoformat` on Python 3.11 handles the trailing Z; older
        # documents written by other tooling may still carry one.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _destination(user: Dict[str, Any]) -> Optional[str]:
    """The number on this account, read the same way ``GET /sms/settings`` reads it.

    Deliberately delegates to ``api.sms.registered_phone`` rather than
    re-reading the two fields: a user must not be shown one number on the
    settings screen and have her weekly summary sent to another, and two
    copies of that lookup is how that happens.
    """
    from api.sms import registered_phone

    return registered_phone(user)


def next_due_at(user: Dict[str, Any]) -> Optional[datetime]:
    """When this user next becomes due, or ``None`` if she is due now.

    A user who has never been sent to is due immediately — she switched
    the feature on and should not wait a week to find out whether it
    works.
    """
    last_sent = as_utc(user.get(LAST_SENT_FIELD))
    if last_sent is None:
        return None
    return last_sent + timedelta(days=SMS_SUMMARY_INTERVAL_DAYS)


def skip_reason(user: Dict[str, Any], now: datetime) -> Optional[str]:
    """Why this user is not due, or ``None`` when she is.

    Checked in the order an operator would want reported: a user who has
    the feature switched off is *disabled*, not *not due*, even if she
    also has no number saved — the first answer is the one that explains
    the situation.
    """
    if not user.get("sms_enabled"):
        return SKIP_DISABLED

    if not _destination(user):
        # Reachable: `POST /sms/settings` refuses to enable without a
        # number, but a later profile edit can clear `phone`, and a
        # document written before that route validated may hold neither.
        return SKIP_NO_PHONE

    due_at = next_due_at(user)
    if due_at is not None and now < due_at:
        return SKIP_NOT_DUE

    return None


def is_due(user: Dict[str, Any], now: datetime) -> bool:
    """Whether ``user`` should be sent a summary at ``now``.

    Pure: no clock, no database. Both are arguments, so the scheduling
    rule can be exercised across a week of instants in a unit test without
    freezing time or seeding Firestore.
    """
    return skip_reason(user, now) is None


def _stream_users() -> Iterable[Any]:
    """Every user document, mock-client compatible.

    The in-memory mock's ``MockCollectionReference`` does not implement a
    bare ``stream()``, so fall back to walking its store — the same
    fallback ``data_privacy_service._stream_collection`` and
    ``access_log_service._stream_all`` use, and for the same reason: this
    feature has to work in the mock-mode setup ``initialize_firebase()``
    falls back to, or it cannot be developed against.
    """
    collection = _firestore.db.collection(USERS_COLLECTION)

    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            yield from stream()
            return
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return
    for doc_id in list(store.keys()):
        yield collection.document(doc_id)


def _all_users() -> List[Dict[str, Any]]:
    """Every user document as a dict, with its id folded in.

    Ordered by document id. An unordered scan would make ``limit`` mean
    "an arbitrary hundred of them", so a user unlucky in the iteration
    order could be passed over week after week while the batch reported
    a hundred sends every time.
    """
    users: List[Dict[str, Any]] = []
    for doc in _stream_users():
        data = doc.to_dict() or {}
        data["id"] = doc.id
        users.append(data)
    return sorted(users, key=lambda item: str(item.get("id") or ""))


def due_users(
    now: datetime,
    *,
    limit: int = DEFAULT_BATCH_LIMIT,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """The users due a summary at ``now``, plus a tally of who was passed over.

    Returns ``(due, skipped_counts)``. The tally is by :data:`SKIP_DISABLED` /
    :data:`SKIP_NO_PHONE` / :data:`SKIP_NOT_DUE`, and it counts *every*
    non-due user, not just those inside ``limit`` — a caller needs to know
    the shape of the whole collection to tell "nobody is subscribed" from
    "the batch size is too small".
    """
    bounded = max(1, min(int(limit), MAX_BATCH_LIMIT))

    due: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {SKIP_DISABLED: 0, SKIP_NO_PHONE: 0, SKIP_NOT_DUE: 0}

    for user in _all_users():
        reason = skip_reason(user, now)
        if reason is not None:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        if len(due) < bounded:
            due.append(user)

    return due, skipped


def mark_summary_sent(user_id: str, sent_at: datetime) -> None:
    """Stamp the send, so the next pass does not repeat it.

    Written *after* Twilio accepts the message, never before. Stamping
    first would mean a failed send silently consumed the user's week: she
    would be marked as having been told, and would not be due again for
    seven days.
    """
    UserService.update_user(
        user_id, {LAST_SENT_FIELD: as_utc(sent_at).isoformat()}
    )


@dataclass(frozen=True)
class DispatchOutcome:
    """What happened for one user in a batch.

    ``user_id`` and not the phone number: this object ends up in a
    response body and in the log, and a batch report is not a place to
    accumulate a list of women's phone numbers.
    """

    user_id: str
    status: str
    detail: Optional[str] = None


@dataclass
class DispatchReport:
    """The result of one batch, in the shape an operator needs to read it."""

    sent: int = 0
    failed: int = 0
    skipped: Dict[str, int] = field(default_factory=dict)
    outcomes: List[DispatchOutcome] = field(default_factory=list)
    ran_at: Optional[str] = None

    @property
    def considered(self) -> int:
        return self.sent + self.failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ranAt": self.ran_at,
            "sent": self.sent,
            "failed": self.failed,
            "skipped": dict(self.skipped),
            "intervalDays": SMS_SUMMARY_INTERVAL_DAYS,
            "outcomes": [
                {
                    "userId": outcome.user_id,
                    "status": outcome.status,
                    "detail": outcome.detail,
                }
                for outcome in self.outcomes
            ],
        }


def dispatch_due(
    *,
    now: Optional[datetime] = None,
    limit: int = DEFAULT_BATCH_LIMIT,
    send: Optional[Callable[[str, str], Any]] = None,
    build_body: Optional[Callable[[str], str]] = None,
) -> DispatchReport:
    """Send one batch of due summaries and report what happened.

    ``send`` and ``build_body`` are injectable so the batch can be tested
    without Twilio and without a live Gemini/Firestore round trip. They
    default to the same two functions ``POST /sms/send-summary`` uses, so
    the scheduled message and the on-demand one are the same message —
    a divergence there is precisely the bug #483 describes on the other
    side of this feature.

    Every user is attempted independently. One unreachable number, one
    Twilio outage on a single request, one malformed document: each is
    caught, counted, reported, and does not touch the ninety-nine
    summaries behind it.
    """
    if send is None or build_body is None:
        from api.sms import generate_cycle_sms_summary, send_sms

        send = send or send_sms
        build_body = build_body or generate_cycle_sms_summary

    moment = as_utc(now) or datetime.now(timezone.utc)
    due, skipped = due_users(moment, limit=limit)

    report = DispatchReport(skipped=skipped, ran_at=moment.isoformat())

    for user in due:
        user_id = str(user.get("id") or "")
        destination = _destination(user)

        try:
            body = build_body(user_id)
            send(destination, body)
        except Exception as exc:
            # Deliberately swallowed per user. The alternative is that the
            # first bad number ends the batch, which turns one user's
            # problem into everybody's missing summary.
            report.failed += 1
            report.outcomes.append(
                DispatchOutcome(user_id=user_id, status="failed", detail=str(exc))
            )
            logger.warning(f"Scheduled SMS summary failed for {user_id}: {exc}")
            continue

        try:
            mark_summary_sent(user_id, moment)
        except Exception as exc:
            # The text has already gone out. Report it as sent — because it
            # was — but say loudly that the stamp did not land, since an
            # unstamped user will be texted again on the next run.
            report.sent += 1
            report.outcomes.append(
                DispatchOutcome(
                    user_id=user_id,
                    status="sent_unstamped",
                    detail=f"sent, but {LAST_SENT_FIELD} was not written: {exc}",
                )
            )
            logger.error(
                f"Scheduled SMS summary sent to {user_id} but {LAST_SENT_FIELD} "
                f"was not written: {exc}"
            )
            continue

        report.sent += 1
        report.outcomes.append(DispatchOutcome(user_id=user_id, status="sent"))

    return report
