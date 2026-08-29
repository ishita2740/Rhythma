"""Data portability and account erasure endpoints.

Every route here operates strictly on ``current_user["id"]``. None of them
takes a user id from the path — an endpoint that hands out a full health
export or destroys an account is the last place an IDOR should be
possible, so the opportunity to get the authorization check wrong is
removed rather than guarded.

See ``services/data_privacy_service.py`` for the cascade itself and for
why the previous deletion path was incomplete.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from core.auth import COOKIE_NAME, REFRESH_COOKIE_NAME, get_current_user
from services.data_privacy_service import (
    DELETION_TOKEN_TTL_SECONDS,
    EXPORT_SCHEMA_VERSION,
    account_exists,
    build_cycle_logs_csv,
    build_data_summary,
    build_export_bundle,
    delete_account,
    deletion_record_for,
    export_filename,
    issue_deletion_token,
    verify_deletion_token,
)
from utils.logger import logger

router = APIRouter(tags=["Privacy"])


# ─── Response models ──────────────────────────────────────────────────────


class DataCategory(BaseModel):
    key: str
    label: str
    recordCount: int
    storedFields: List[str] = Field(default_factory=list)
    collection: str
    earliestEntry: Optional[str] = None
    latestEntry: Optional[str] = None
    retentionNote: str


class DataSummaryResponse(BaseModel):
    userId: str
    generatedAt: str
    categories: List[DataCategory]
    totalRecords: int


class DeletionRequestResponse(BaseModel):
    """Step one of deletion: what will happen, and the token to confirm it."""

    confirmationToken: str = Field(
        ...,
        description=(
            "Single-use token. Send it back to POST /privacy/delete-account "
            "to actually delete. Expires shortly."
        ),
    )
    expiresInSeconds: int
    impact: DataSummaryResponse
    warning: str


class DeletionResultResponse(BaseModel):
    status: str
    deletedCounts: Dict[str, int]
    totalDeleted: int
    deletedAt: str
    message: str


class DeletionStatusResponse(BaseModel):
    accountExists: bool
    deletedAt: Optional[str] = None
    deletedCounts: Optional[Dict[str, int]] = None


class DeleteAccountRequest(BaseModel):
    confirmationToken: Optional[str] = Field(
        None,
        description=(
            "Omit to receive a token and an impact preview. Send the token "
            "back to perform the deletion."
        ),
    )


DELETION_WARNING = (
    "This permanently deletes your cycle logs, symptoms, notes, profile and "
    "assistant conversation. It cannot be undone. Export your data first if "
    "you want to keep a copy."
)


# ─── Routes ───────────────────────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=DataSummaryResponse,
    summary="What data is stored about you",
    description=(
        "Returns an inventory of everything Rhythma stores for the "
        "authenticated user — per category: how many records, which fields, "
        "the date range, and the retention note. Values themselves are not "
        "included; use /privacy/export for those. This is what a Settings "
        "screen should show before offering Export or Delete."
    ),
)
async def get_data_summary(current_user: dict = Depends(get_current_user)):
    return build_data_summary(current_user["id"])


@router.get(
    "/export",
    summary="Download all of your data",
    description=(
        "Returns a complete, machine-readable export of everything stored "
        "for the authenticated user. `format=json` (default) is the "
        "canonical bundle, versioned by `schema_version`, covering profile, "
        "cycle logs, assistant conversation and SMS settings. `format=csv` "
        "returns a flattened cycle-log table for spreadsheets and for import "
        "into other trackers. The password hash is deliberately excluded."
    ),
    responses={
        200: {
            "content": {"application/json": {}, "text/csv": {}},
            "description": "The export bundle as a file download.",
        }
    },
)
async def export_user_data(
    format: str = Query(
        "json",
        pattern="^(json|csv)$",
        description="json for the full bundle, csv for cycle logs only.",
    ),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    # Logged without any of the exported content: knowing an export
    # happened is operationally useful, knowing what was in it is not.
    logger.bind(export_format=format).info("User data export requested")

    if format == "csv":
        return PlainTextResponse(
            content=build_cycle_logs_csv(user_id),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{export_filename(user_id, "csv")}"'
                ),
                # An export is per-user and never cacheable by a shared proxy.
                "Cache-Control": "no-store",
            },
        )

    return JSONResponse(
        content=build_export_bundle(user_id),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export_filename(user_id, "json")}"'
            ),
            "Cache-Control": "no-store",
            "X-Export-Schema-Version": EXPORT_SCHEMA_VERSION,
        },
    )


@router.post(
    "/delete-account",
    summary="Delete your account and all stored data",
    description=(
        "Two-step by design. Called without `confirmationToken`, it returns "
        "a short-lived single-use token together with an impact preview "
        "(exactly how many records will be destroyed) and responds 202. "
        "Called again with that token, it performs the cascade delete across "
        "every collection, revokes all refresh tokens, clears the auth "
        "cookies, and returns the per-collection deleted counts. "
        "Irreversible."
    ),
    responses={
        200: {"model": DeletionResultResponse},
        202: {"model": DeletionRequestResponse},
    },
)
async def delete_account_endpoint(
    payload: DeleteAccountRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    if not payload.confirmationToken:
        token, ttl = issue_deletion_token(user_id)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "confirmationToken": token,
                "expiresInSeconds": ttl,
                "impact": build_data_summary(user_id),
                "warning": DELETION_WARNING,
            },
        )

    if not verify_deletion_token(user_id, payload.confirmationToken):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": (
                    "That confirmation token is invalid, already used, or has "
                    "expired. Request a new one and confirm again."
                )
            },
        )

    result = delete_account(user_id)

    body = {
        "status": "success",
        "deletedCounts": result["deletedCounts"],
        "totalDeleted": result["totalDeleted"],
        "deletedAt": result["deletedAt"],
        "message": "Your account and all associated data have been deleted.",
    }
    deletion_response = JSONResponse(status_code=status.HTTP_200_OK, content=body)
    _clear_auth_cookies(deletion_response)
    return deletion_response


@router.get(
    "/deletion-status",
    response_model=DeletionStatusResponse,
    summary="Confirm an account deletion completed",
    description=(
        "Reports whether the account still exists and, if it was deleted, "
        "when and how many records were removed. Reads the audit record, "
        "which stores only a hashed user id and counts — never personal data."
    ),
)
async def deletion_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    record = deletion_record_for(user_id)
    return {
        "accountExists": account_exists(user_id),
        "deletedAt": record.get("deleted_at") if record else None,
        "deletedCounts": record.get("deleted_counts") if record else None,
    }


def _clear_auth_cookies(response: Response) -> None:
    """Drop the session cookies, the way /auth/logout does.

    Without this a web client keeps sending a cookie for an account that
    no longer exists, and every subsequent request 401s in a way that
    looks like a bug rather than a completed deletion.
    """
    import os

    domain = os.getenv("COOKIE_DOMAIN") or None
    for cookie in (COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(key=cookie, path="/", domain=domain)
