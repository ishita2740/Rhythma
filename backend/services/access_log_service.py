"""A record of when a provider read a patient's data (issue #350).

The provider dashboard from #267 got the hard part right: no read of a
patient's data happens without an active consent document. What was
missing is the other half of the same contract — a patient could see *who
had permission*, and never *whether anyone used it*.

The consent was checked and then discarded:

    consent = ConsentService.active_consent(patient_id, provider_id)
    if not consent:
        raise HTTPException(403, ...)
    ...
    return {"patient": profile, "cycleLogs": history, ...}

So after a clinician opened a patient's full history — every logged
period, symptom, mood, stress and sleep entry — the only trace was the
HTTP access line in ``core/middleware.py``: operator-only, retained on
whatever schedule the log sink uses, and never shown to the patient.

Three decisions worth stating.

**This records that data was viewed, not the data itself.** No request
bodies, no field-level detail, no IP addresses. A privacy feature whose
implementation is a second copy of the health data has not helped anyone,
and an access log is exactly the kind of collection that quietly grows
into one.

**It is written in the service, not the route.** Any future endpoint that
reads patient data through ``ProviderService`` is recorded by
construction. A decorator on the two current routes would be quietly
bypassed by the third one somebody adds.

**A failed write must never break the read.** A clinician seeing a 500
because an audit record could not be saved is a worse outcome than the
missing record, and it would make the audit trail a new way for the
dashboard to fail. Failures are logged and swallowed — deliberately, and
:func:`record` is the only place that swallowing happens.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import logger

ACCESS_LOG_COLLECTION = "access_log"

#: The kinds of read that get recorded. Kept as an explicit vocabulary
#: rather than free text so the patient-facing screen can translate them,
#: and so a new call site has to make a deliberate choice about what it is
#: describing.
VIEW_PATIENT_LIST = "patient_list"
VIEW_PATIENT_DETAIL = "patient_detail"

VIEW_TYPES = (VIEW_PATIENT_LIST, VIEW_PATIENT_DETAIL)

#: Ceiling on one page of access history, mirroring the cycle-history
#: bound from #331 — a patient with a long history should not be able to
#: ask for all of it in one response.
MAX_ACCESS_LOG_PAGE = 100
DEFAULT_ACCESS_LOG_PAGE = 20


def _db():
    """The live Firestore handle, looked up on every call.

    Same reasoning as ``data_privacy_service._db()`` and
    ``provider_service._db()``: ``firestore_service.db`` is reassigned at
    import time and by the test suite, so a value imported at module load
    could pin this module to a stale client.
    """
    from services.firestore_service import db

    return db


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _stream_all() -> List[Any]:
    """Every document in the collection, mock-client compatible.

    The in-memory mock's ``MockCollectionReference`` implements ``where``
    but not a bare ``stream()``, so a plain ``collection.stream()`` raises
    ``AttributeError`` under the local mock-mode setup
    ``firestore_service.initialize_firebase()`` falls back to. Same
    fallback as ``data_privacy_service._stream_collection``, and the same
    reason: this feature has to work in mock mode or it cannot be
    developed against.
    """
    collection = _db().collection(ACCESS_LOG_COLLECTION)

    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            return list(stream())
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return []
    return [collection.document(doc_id) for doc_id in list(store.keys())]


def record(
    *,
    provider_id: str,
    patient_id: str,
    view: str,
    consent_id: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> None:
    """Append one access record. Never raises.

    ``provider_name`` is denormalised onto the record on purpose. The
    patient-facing screen has to render "who looked at my data", and
    resolving a provider id per row would be one user lookup per entry —
    but more importantly, a provider who later closes her account would
    leave the patient with an unresolvable id where a name used to be.
    The record is a statement about a moment, so it keeps the name as it
    was at that moment.
    """
    if view not in VIEW_TYPES:
        # A typo'd view type would produce records the patient-facing
        # screen cannot label. Loud in the log, still not an exception.
        logger.warning(f"Ignoring access record with unknown view type {view!r}")
        return

    try:
        _db().collection(ACCESS_LOG_COLLECTION).add(
            {
                "provider_id": provider_id,
                "patient_id": patient_id,
                "provider_name": provider_name,
                "view": view,
                "consent_id": consent_id,
                "accessed_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:
        # Deliberately swallowed. See the module docstring: a clinician
        # seeing a 500 because an audit write failed is worse than the
        # missing record, and would make this feature a new way for the
        # dashboard to break.
        logger.warning(f"Could not record provider access: {exc}")


def _entries_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    """Every access record for one patient, newest first.

    Sorted in Python rather than with ``order_by`` on the query. The
    collection is filtered by ``patient_id`` first, so this sorts one
    patient's own records — tens, not thousands — and it avoids requiring
    a composite index for a feature whose whole point is that it works
    from the moment it ships.
    """
    entries: List[Dict[str, Any]] = []
    for doc in _stream_all():
        data = doc.to_dict() or {}
        if data.get("patient_id") != patient_id:
            continue
        data["id"] = doc.id
        entries.append(data)

    entries.sort(key=lambda entry: str(entry.get("accessed_at") or ""), reverse=True)
    return entries


def list_for_patient(
    patient_id: str,
    *,
    limit: int = DEFAULT_ACCESS_LOG_PAGE,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], bool]:
    """One page of a patient's access history, plus whether more exists.

    Returns ``(entries, has_more)``. ``has_more`` comes from slicing one
    past the page rather than from a count, matching the paging contract
    ``CycleService.get_logs_page`` established in #331.
    """
    entries = _entries_for_patient(patient_id)
    window = entries[offset : offset + limit + 1]
    has_more = len(window) > limit

    page = [
        {
            "id": entry.get("id"),
            "providerId": entry.get("provider_id"),
            "providerName": entry.get("provider_name"),
            "view": entry.get("view"),
            "consentId": entry.get("consent_id"),
            "accessedAt": _serialize(entry.get("accessed_at")),
        }
        for entry in window[:limit]
    ]
    return page, has_more


def summary_for_patient(patient_id: str) -> Dict[str, Dict[str, Any]]:
    """Per-provider access totals, keyed by provider id.

    Folded into the existing ``GET /provider/consents`` response so the
    Sharing screen can show "last viewed" beside each provider without a
    second round trip. A sharing list that says "Dr. Sharma — shared since
    12 March" is materially different from one that says "...last viewed
    your records 2 days ago, 4 times in total", and the second is the one
    a patient can actually act on.
    """
    summary: Dict[str, Dict[str, Any]] = {}
    for entry in _entries_for_patient(patient_id):
        provider_id = entry.get("provider_id")
        if not provider_id:
            continue
        accessed_at = _serialize(entry.get("accessed_at"))
        existing = summary.get(provider_id)
        if existing is None:
            summary[provider_id] = {"viewCount": 1, "lastAccessedAt": accessed_at}
            continue
        existing["viewCount"] += 1
        # Entries arrive newest-first, so the first one seen for a
        # provider is already the latest. Compared rather than assumed so
        # a record written with a clock skew cannot make "last viewed"
        # jump backwards.
        if accessed_at and str(accessed_at) > str(existing["lastAccessedAt"] or ""):
            existing["lastAccessedAt"] = accessed_at
    return summary


def count_for_patient(patient_id: str) -> int:
    """How many access records exist, for the privacy data inventory."""
    return len(_entries_for_patient(patient_id))


def doc_ids_for_user(user_id: str) -> List[str]:
    """Every access record touching this user, on either side.

    Used by the deletion cascade. Both sides matter: a patient's records
    are hers, and a *provider* closing her account should not leave rows
    naming her in other people's access histories.
    """
    ids: List[str] = []
    for doc in _stream_all():
        data = doc.to_dict() or {}
        if data.get("patient_id") == user_id or data.get("provider_id") == user_id:
            ids.append(doc.id)
    return ids
