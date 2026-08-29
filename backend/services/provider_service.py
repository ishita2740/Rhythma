"""Consent management and provider-side data access (issue #267).

The provider dashboard exists so a healthcare professional can see only
the cycle/health data a patient has explicitly chosen to share. The
consent record is the gate: a provider endpoint never reads a patient's
data without an active consent document linking that patient to that
provider.

Consents live in their own ``consents`` collection, deliberately outside
the ``users`` document. Keeping them separate means the privacy module's
``USER_DATA_COLLECTIONS`` purge guard stays meaningful — a consent is a
relationship record, not a profile field — and it keeps the set of
collections a deletion cascade must cover explicitly enumerated.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from services import access_log_service
from services.firestore_service import UserService
from services.scoring_service import get_user_scores

CONSENTS_COLLECTION = "consents"

#: Paging bounds for the two provider list endpoints (#406), following the
#: contract #331 set for cycle history and ``access_log_service`` copied.
#:
#: The ceiling matters more on ``/patients`` than on an ordinary list.
#: Building one summary costs a profile read, a scoring pass over that
#: patient's cycle logs, *and* an access-log write, so the page size is a
#: multiplier on three kinds of work rather than only on response bytes.
MAX_PATIENTS_PAGE = 100
DEFAULT_PATIENTS_PAGE = 20

MAX_CONSENTS_PAGE = 100
DEFAULT_CONSENTS_PAGE = 20

#: Profile fields a provider may see once consent is active. Deliberately
#: excludes phone, email, password and any other identity/contact data the
#: patient has not been asked about.
_PROVIDER_VISIBLE_PROFILE_FIELDS = (
    "full_name",
    "age",
    "city",
    "state",
    "cycle_length",
    "period_duration",
    "cycle_regular",
    "last_period",
)


def _db():
    """The live Firestore handle, looked up on every call.

    Same reasoning as ``data_privacy_service._db()``: ``firestore_service.db``
    is reassigned at import time and by the test suite, so a value imported at
    module load could pin this module to a stale client.
    """
    from services.firestore_service import db

    return db


def _consent_doc_id(patient_id: str, provider_id: str) -> str:
    """Deterministic id so a grant is an upsert, not a duplicate."""
    return f"{patient_id}::{provider_id}"


def _sort_key(consent: Dict[str, Any]):
    """Newest first, with a stable tiebreak.

    ``created_at`` is a ``datetime`` on documents this codebase wrote, but
    a Firestore round trip can hand back a string, and an older document
    may not carry the field at all. Comparing those against each other
    raises ``TypeError`` mid-sort, so everything is coerced to a string
    first — ISO-8601 sorts correctly as text, which is the property that
    makes this safe rather than merely convenient.

    The document id is the tiebreak. Two consents created in the same
    instant would otherwise be free to swap places between requests, and a
    page boundary that moves is a row the caller either sees twice or
    never sees at all.
    """
    created = consent.get("created_at")
    if isinstance(created, datetime):
        created = created.isoformat()
    return (str(created or ""), str(consent.get("id") or ""))


def _sorted_consents(consents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A total, stable order — the precondition for paging to mean anything."""
    return sorted(consents, key=_sort_key, reverse=True)


def _provider_display_name(provider_id: str) -> Optional[str]:
    """How to name this provider on the patient's access-history screen.

    Resolved once per request and stamped onto each record rather than
    joined at read time — see ``access_log_service.record``. Falls back
    through the same chain the consent record uses, so the two screens
    name the same clinician the same way.
    """
    provider = UserService.get_user_by_id(provider_id) or {}
    return (
        provider.get("full_name")
        or provider.get("username")
        or provider.get("email")
    )


class ConsentService:
    """The patient->provider data-sharing store (grant / list / revoke)."""

    @staticmethod
    def grant(patient_id: str, provider_email: str) -> Dict[str, Any]:
        """Open (or re-open) an active consent for ``provider_email``."""
        provider = UserService.get_user_by_email(provider_email)
        if not provider or provider.get("role") != "provider":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No healthcare provider found with that email",
            )
        if provider["id"] == patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot share data with yourself",
            )

        doc_id = _consent_doc_id(patient_id, provider["id"])
        doc_ref = _db().collection(CONSENTS_COLLECTION).document(doc_id)
        existing = doc_ref.get()
        now = datetime.now(timezone.utc)

        consent = {
            "patient_id": patient_id,
            "provider_id": provider["id"],
            "provider_email": provider.get("email"),
            "provider_name": (
                provider.get("full_name")
                or provider.get("username")
                or provider.get("email")
            ),
            "status": "active",
            "created_at": (
                existing.to_dict().get("created_at") if existing.exists else now
            ),
            "updated_at": now,
            "revoked_at": None,
        }
        doc_ref.set(consent)
        consent["id"] = doc_id
        return consent

    @staticmethod
    def list_for_patient(patient_id: str) -> List[Dict[str, Any]]:
        """Every consent a patient has created, including revoked ones.

        Kept unpaged because callers inside the service layer want the
        whole relationship set — ``list_page_for_patient`` is the one the
        HTTP endpoint uses.
        """
        consents: List[Dict[str, Any]] = []
        for doc in (
            _db().collection(CONSENTS_COLLECTION)
            .where("patient_id", "==", patient_id)
            .stream()
        ):
            data = doc.to_dict()
            data["id"] = doc.id
            consents.append(data)
        return _sorted_consents(consents)

    @staticmethod
    def list_page_for_patient(
        patient_id: str,
        *,
        limit: int = DEFAULT_CONSENTS_PAGE,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """One page of a patient's consents, plus whether more exist.

        Returns ``(consents, has_more)``. ``has_more`` comes from slicing
        one past the page rather than from a count query, matching the
        contract ``CycleService.get_logs_page`` set in #331 — paging costs
        no extra round trip.

        Sorted newest-first before slicing. Without an explicit order a
        page boundary is meaningless: Firestore makes no ordering promise
        on an unordered query, so ``offset=20`` could return rows the
        caller already saw at ``offset=0`` and skip others entirely.
        """
        consents = ConsentService.list_for_patient(patient_id)
        window = consents[offset : offset + limit + 1]
        return window[:limit], len(window) > limit

    @staticmethod
    def revoke(patient_id: str, consent_id: str) -> Dict[str, Any]:
        """Revoke a consent. Only its owning patient may do so."""
        doc_ref = _db().collection(CONSENTS_COLLECTION).document(consent_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("patient_id") != patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consent not found",
            )
        now = datetime.now(timezone.utc)
        doc_ref.update({"status": "revoked", "revoked_at": now, "updated_at": now})
        data = doc_ref.get().to_dict()
        data["id"] = consent_id
        return data

    @staticmethod
    def active_consent(
        patient_id: str, provider_id: str
    ) -> Optional[Dict[str, Any]]:
        """The active consent linking this patient to this provider, or None."""
        doc = (
            _db().collection(CONSENTS_COLLECTION)
            .document(_consent_doc_id(patient_id, provider_id))
            .get()
        )
        if not doc.exists or doc.to_dict().get("status") != "active":
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    @staticmethod
    def list_active_for_provider(provider_id: str) -> List[Dict[str, Any]]:
        """All patients who currently share data with this provider."""
        consents: List[Dict[str, Any]] = []
        for doc in (
            _db().collection(CONSENTS_COLLECTION)
            .where("provider_id", "==", provider_id)
            .stream()
        ):
            data = doc.to_dict()
            if data.get("status") != "active":
                continue
            data["id"] = doc.id
            consents.append(data)
        return _sorted_consents(consents)


class ProviderService:
    """Provider-facing reads, all gated on an active consent."""

    @staticmethod
    def patient_summaries(provider_id: str) -> List[Dict[str, Any]]:
        """Every sharing patient. Prefer :meth:`patient_summaries_page`.

        Retained so service-layer callers and existing tests keep working.
        The HTTP endpoint no longer uses it, because the work here grows
        without a ceiling — see the page method for what that costs.
        """
        summaries, _ = ProviderService.patient_summaries_page(
            provider_id, limit=None
        )
        return summaries

    @staticmethod
    def patient_summaries_page(
        provider_id: str,
        *,
        limit: Optional[int] = DEFAULT_PATIENTS_PAGE,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """One page of dashboard cards, plus whether more exist.

        Returns ``(summaries, has_more)``, the same shape
        ``access_log_service.list_for_patient`` returns.

        The slice happens on the *consents* — before the fan-out — and that
        is the whole point of this method rather than a nicety of where the
        code sits. Each summary costs a profile read, a scoring pass over
        that patient's cycle logs, and an access-log write. Fetching every
        consent and slicing the finished summaries would trim the response
        body and leave all three of those running for the entire roster,
        which is the expensive half of #406.

        A consequence worth being deliberate about: the access-log rows
        (#350) are written only for the patients on this page. That is more
        truthful than what it replaces — the provider genuinely did not
        look at page four — and it means a patient's "your data was viewed"
        history stops counting views that never happened.

        ``limit=None`` disables paging, for the whole-roster callers that
        predate this.
        """
        summaries: List[Dict[str, Any]] = []
        provider_name = _provider_display_name(provider_id)

        consents = ConsentService.list_active_for_provider(provider_id)
        if limit is None:
            window, has_more = consents, False
        else:
            window = consents[offset : offset + limit + 1]
            has_more = len(window) > limit
            window = window[:limit]

        for consent in window:
            patient = UserService.get_user_by_id(consent["patient_id"])
            if not patient:
                continue
            scores = get_user_scores(consent["patient_id"])
            access_log_service.record(
                provider_id=provider_id,
                patient_id=consent["patient_id"],
                view=access_log_service.VIEW_PATIENT_LIST,
                consent_id=consent.get("id"),
                provider_name=provider_name,
            )
            summaries.append(
                {
                    "patient_id": consent["patient_id"],
                    "name": (
                        patient.get("full_name")
                        or patient.get("username")
                        or consent["patient_id"]
                    ),
                    "age": patient.get("age"),
                    "city": patient.get("city"),
                    "state": patient.get("state"),
                    "sharedSince": consent["created_at"],
                    "loggedCycleCount": scores["logged_cycle_count"],
                    "analyzedCycleCount": scores["analyzed_cycle_count"],
                    "mhs": scores["mhs"],
                    "cvi": scores["cvi_risk"],
                    "hasEnoughDataForInsights": scores["has_enough_data_for_insights"],
                }
            )
        return summaries, has_more

    @staticmethod
    def patient_detail(provider_id: str, patient_id: str) -> Dict[str, Any]:
        """Full shared view of one patient: profile + scores + cycle history."""
        consent = ConsentService.active_consent(patient_id, provider_id)
        if not consent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have this patient's consent to view their data",
            )

        patient = UserService.get_user_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Recorded after the consent and existence checks and before the
        # data is assembled, so the log holds reads that were actually
        # authorised — a refused 403 is not an access, and logging it here
        # would let a provider without consent write rows into a
        # patient's history simply by requesting her id (issue #350).
        access_log_service.record(
            provider_id=provider_id,
            patient_id=patient_id,
            view=access_log_service.VIEW_PATIENT_DETAIL,
            consent_id=consent.get("id"),
            provider_name=_provider_display_name(provider_id),
        )

        scores = get_user_scores(patient_id)

        history: List[Dict[str, Any]] = []
        for log in scores["logs"]:
            entry = dict(log)
            start = entry.get("start_date")
            entry["start_date"] = (
                start.isoformat() if hasattr(start, "isoformat") else start
            )
            history.append(entry)

        sleep_hours = [
            log.get("sleep_hours")
            for log in scores["logs"]
            if log.get("sleep_hours") is not None
        ]
        avg_sleep = round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else None

        profile = {
            "id": patient_id,
            "name": (
                patient.get("full_name")
                or patient.get("username")
                or patient_id
            ),
            **{field: patient.get(field) for field in _PROVIDER_VISIBLE_PROFILE_FIELDS},
        }

        return {
            "patient": profile,
            "summary": {
                "mhs": scores["mhs"],
                "cvi": scores["cvi_risk"],
                "cvi_raw": scores["cvi"],
                "loggedCycleCount": scores["logged_cycle_count"],
                "analyzedCycleCount": scores["analyzed_cycle_count"],
                "hasEnoughDataForInsights": scores["has_enough_data_for_insights"],
                "avgSleepHours": avg_sleep,
            },
            "cycleLogs": history,
            "consent": {
                "grantedAt": consent["created_at"],
                "status": consent["status"],
            },
        }
