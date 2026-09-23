import asyncio
import re
from uuid import UUID

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Analysis, RecordStatus
from app.db import SessionLocal
from app.errors import AppError
from app.integrations import google_service
from app.models import Role, User
from app.profiles.models import Profile
from app.sheets.models import SheetConfig
from app.sheets.schemas import SaveSheetConfigRequest, SheetConfigOut
from app.sheets.writer import SheetsWriter

_URL_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def extract_spreadsheet_id(value: str) -> str:
    match = _URL_ID_RE.search(value)
    return match.group(1) if match else value.strip()


def _http_error_message(exc: HttpError) -> str:
    status = getattr(exc.resp, "status", None)
    if status == 403:
        return "Access denied. Share the sheet with the connected Google account."
    if status == 404:
        return "Spreadsheet or tab not found."
    return f"Google Sheets error (status {status})."


async def list_configs_for_client(db: AsyncSession, client_id: UUID) -> list[SheetConfigOut]:
    profiles = (
        (
            await db.execute(
                select(Profile).where(Profile.client_id == client_id, Profile.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    configs = (
        (
            await db.execute(
                select(SheetConfig).where(
                    SheetConfig.client_id == client_id, SheetConfig.user_id.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    by_profile = {c.profile_id: c for c in configs}
    return [
        SheetConfigOut(
            profile_id=p.id,
            profile_name=p.name,
            enabled=by_profile[p.id].enabled if p.id in by_profile else False,
            spreadsheet_id=by_profile[p.id].spreadsheet_id if p.id in by_profile else None,
            sheet_name=by_profile[p.id].sheet_name if p.id in by_profile else None,
        )
        for p in profiles
    ]


async def get_bidder_config(db: AsyncSession, *, client_id: UUID, user: User) -> SheetConfigOut:
    if user.assigned_profile_id is None:
        raise AppError("no_assigned_profile", "You have no assigned profile yet", 400)
    profile = await db.get(Profile, user.assigned_profile_id)
    row = (
        await db.execute(
            select(SheetConfig).where(
                SheetConfig.client_id == client_id,
                SheetConfig.profile_id == user.assigned_profile_id,
                SheetConfig.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    return SheetConfigOut(
        profile_id=user.assigned_profile_id,
        profile_name=profile.name if profile else "",
        enabled=row.enabled if row else False,
        spreadsheet_id=row.spreadsheet_id if row else None,
        sheet_name=row.sheet_name if row else None,
    )


async def _upsert(
    db: AsyncSession,
    *,
    client_id: UUID,
    profile_id: UUID,
    user_id: UUID | None,
    payload: SaveSheetConfigRequest,
    profile_name: str,
) -> SheetConfigOut:
    spreadsheet_id = extract_spreadsheet_id(payload.spreadsheet) if payload.spreadsheet else None
    stmt = select(SheetConfig).where(
        SheetConfig.client_id == client_id, SheetConfig.profile_id == profile_id
    )
    stmt = stmt.where(
        SheetConfig.user_id.is_(None) if user_id is None else SheetConfig.user_id == user_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = SheetConfig(client_id=client_id, profile_id=profile_id, user_id=user_id)
        db.add(row)
    row.enabled = payload.enabled
    row.spreadsheet_id = spreadsheet_id
    row.sheet_name = payload.sheet_name
    await db.commit()
    return SheetConfigOut(
        profile_id=profile_id,
        profile_name=profile_name,
        enabled=row.enabled,
        spreadsheet_id=row.spreadsheet_id,
        sheet_name=row.sheet_name,
    )


async def save_client_config(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID, payload: SaveSheetConfigRequest
) -> SheetConfigOut:
    profile = await db.get(Profile, profile_id)
    if profile is None or profile.client_id != client_id:
        raise AppError("not_found", "Profile not found", 404)
    return await _upsert(
        db,
        client_id=client_id,
        profile_id=profile_id,
        user_id=None,
        payload=payload,
        profile_name=profile.name,
    )


async def save_bidder_config(
    db: AsyncSession, *, client_id: UUID, user: User, payload: SaveSheetConfigRequest
) -> SheetConfigOut:
    if user.assigned_profile_id is None:
        raise AppError("no_assigned_profile", "You have no assigned profile yet", 400)
    profile = await db.get(Profile, user.assigned_profile_id)
    return await _upsert(
        db,
        client_id=client_id,
        profile_id=user.assigned_profile_id,
        user_id=user.id,
        payload=payload,
        profile_name=profile.name if profile else "",
    )


async def list_tabs(db: AsyncSession, *, client_id: UUID, spreadsheet: str) -> list[str]:
    spreadsheet_id = extract_spreadsheet_id(spreadsheet)
    refresh_token = await google_service.get_decrypted_refresh_token(db, client_id)
    writer = SheetsWriter(refresh_token)
    try:
        return await asyncio.to_thread(writer.list_tabs, spreadsheet_id)
    except RefreshError as exc:
        await google_service.mark_needs_reconnect(db, client_id)
        raise AppError(
            "google_needs_reconnect", "Google connection needs to be reconnected", 400
        ) from exc
    except HttpError as exc:
        raise AppError("sheet_access_failed", _http_error_message(exc), 400) from exc


async def test_write(
    db: AsyncSession, *, client_id: UUID, spreadsheet: str, sheet_name: str
) -> None:
    spreadsheet_id = extract_spreadsheet_id(spreadsheet)
    refresh_token = await google_service.get_decrypted_refresh_token(db, client_id)
    writer = SheetsWriter(refresh_token)
    try:
        await asyncio.to_thread(writer.ensure_header, spreadsheet_id, sheet_name)
    except RefreshError as exc:
        await google_service.mark_needs_reconnect(db, client_id)
        raise AppError(
            "google_needs_reconnect", "Google connection needs to be reconnected", 400
        ) from exc
    except HttpError as exc:
        raise AppError("sheet_access_failed", _http_error_message(exc), 400) from exc


async def resolve_config(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID | None, user: User
) -> SheetConfig | None:
    """CLIENT rows always use the profile-level config. A BIDDER uses their own enabled
    personal config for their assigned profile if set, else falls back to the same
    profile-level config — see docs/SPEC.md's Config section."""
    if profile_id is None:
        return None
    if user.role == Role.BIDDER:
        personal = (
            await db.execute(
                select(SheetConfig).where(
                    SheetConfig.client_id == client_id,
                    SheetConfig.profile_id == profile_id,
                    SheetConfig.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if personal is not None and personal.enabled:
            return personal
    return (
        await db.execute(
            select(SheetConfig).where(
                SheetConfig.client_id == client_id,
                SheetConfig.profile_id == profile_id,
                SheetConfig.user_id.is_(None),
            )
        )
    ).scalar_one_or_none()


def _is_eligible(config: SheetConfig | None) -> bool:
    return bool(config and config.enabled and config.spreadsheet_id and config.sheet_name)


async def initial_record_status(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID | None, user: User
) -> RecordStatus:
    config = await resolve_config(db, client_id=client_id, profile_id=profile_id, user=user)
    return RecordStatus.PENDING if _is_eligible(config) else RecordStatus.SKIPPED


def _build_row(analysis: Analysis, profile_name: str, recorded_by: str) -> list[str]:
    result = analysis.result
    return [
        analysis.created_at.isoformat(),
        analysis.company_name,
        analysis.position_name,
        analysis.job_link or "",
        result.get("main_backend_skill", ""),
        result.get("backend_framework") or "",
        ", ".join(result.get("secondary_skills", [])),
        result.get("seniority", ""),
        profile_name,
        recorded_by,
        str(result.get("confidence", "")),
    ]


async def record_analysis(analysis_id: UUID) -> None:
    """Writes one analysis row to its resolved sheet. Idempotent: no-ops once SUCCESS,
    per docs/SPEC.md's "never write the same analysis to the same sheet twice"."""
    async with SessionLocal() as db:
        analysis = await db.get(Analysis, analysis_id)
        if analysis is None or analysis.record_status == RecordStatus.SUCCESS:
            return

        creator = await db.get(User, analysis.created_by)
        config = (
            await resolve_config(
                db,
                client_id=analysis.client_id,
                profile_id=analysis.selected_profile_id,
                user=creator,
            )
            if creator is not None
            else None
        )
        if not _is_eligible(config):
            analysis.record_status = RecordStatus.SKIPPED
            await db.commit()
            return
        assert config is not None

        profile = await db.get(Profile, analysis.selected_profile_id)
        analysis.record_attempts += 1
        try:
            refresh_token = await google_service.get_decrypted_refresh_token(db, analysis.client_id)
            writer = SheetsWriter(refresh_token)
            row = _build_row(
                analysis, profile.name if profile else "", creator.name if creator else ""
            )
            await asyncio.to_thread(writer.ensure_header, config.spreadsheet_id, config.sheet_name)
            await asyncio.to_thread(
                writer.append_row, config.spreadsheet_id, config.sheet_name, row
            )
            analysis.record_status = RecordStatus.SUCCESS
            analysis.record_error = None
        except RefreshError:
            await google_service.mark_needs_reconnect(db, analysis.client_id)
            analysis.record_status = RecordStatus.FAILED
            analysis.record_error = "Google connection needs to be reconnected"
        except HttpError as exc:
            analysis.record_status = RecordStatus.FAILED
            analysis.record_error = _http_error_message(exc)
        except AppError as exc:
            analysis.record_status = RecordStatus.FAILED
            analysis.record_error = exc.message
        await db.commit()
