import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.duplicates import Entry
from app.analysis.models import Analysis, RecordStatus
from app.db import SessionLocal
from app.errors import AppError
from app.integrations import google_service
from app.models import Role, User
from app.profiles.models import Profile
from app.resume_types.models import ResumeType
from app.sheets.models import SheetConfig
from app.sheets.schemas import SaveSheetConfigRequest, SheetConfigOut, SpreadsheetOut
from app.sheets.writer import SheetsWriter


def _google_error(exc: HttpError) -> dict:
    try:
        return json.loads(exc.content).get("error", {})
    except (ValueError, AttributeError):
        return {}


def _http_error_message(exc: HttpError) -> str:
    status = getattr(exc.resp, "status", None)
    error = _google_error(exc)
    reasons = {d.get("reason") for d in error.get("details", []) if isinstance(d, dict)}
    if "SERVICE_DISABLED" in reasons or "has not been used in project" in error.get("message", ""):
        # e.g. "Google Drive API has not been used in project ... or it is disabled."
        return error["message"].split(" Enable it by visiting")[0] + (
            " Enable it in Google Cloud Console > APIs & Services > Library, then retry."
        )
    if status == 403:
        return "Access denied. Share the sheet with the connected Google account."
    if status == 404:
        return "Spreadsheet or tab not found."
    return f"Google Sheets error (status {status})."


def _scope_missing(exc: HttpError) -> bool:
    body = exc.content.decode(errors="ignore") if isinstance(exc.content, bytes) else ""
    return "insufficient" in body.lower() and "scope" in body.lower()


async def _call_google[T](db: AsyncSession, client_id: UUID, fn: Callable[[SheetsWriter], T]) -> T:
    """Runs a (blocking) SheetsWriter method with the client's Google connection, turning
    Google failures into readable errors. Expired/revoked grants and connections made before
    the Drive permission existed mark the connection NEEDS_RECONNECT, which shows the banner."""
    refresh_token = await google_service.get_decrypted_refresh_token(db, client_id)
    writer = SheetsWriter(refresh_token)
    try:
        return await asyncio.to_thread(fn, writer)
    except RefreshError as exc:
        await google_service.mark_needs_reconnect(db, client_id)
        raise AppError(
            "google_needs_reconnect", "Google connection needs to be reconnected", 400
        ) from exc
    except HttpError as exc:
        if _scope_missing(exc):
            await google_service.mark_needs_reconnect(db, client_id)
            raise AppError(
                "google_needs_reconnect",
                "Reconnect Google under Integrations to allow listing your spreadsheets.",
                400,
            ) from exc
        raise AppError("sheet_access_failed", _http_error_message(exc), 400) from exc


def _out(profile: Profile | None, profile_id: UUID, row: SheetConfig | None) -> SheetConfigOut:
    active = row is not None and row.enabled
    return SheetConfigOut(
        profile_id=profile_id,
        profile_name=profile.name if profile else "",
        enabled=active,
        spreadsheet_id=row.spreadsheet_id if active else None,
        spreadsheet_name=row.spreadsheet_name if active else None,
        sheet_name=row.sheet_name if active else None,
    )


def _config_query(client_id: UUID, profile_id: UUID, user_id: UUID | None):
    stmt = select(SheetConfig).where(
        SheetConfig.client_id == client_id, SheetConfig.profile_id == profile_id
    )
    return stmt.where(
        SheetConfig.user_id.is_(None) if user_id is None else SheetConfig.user_id == user_id
    )


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
    return [_out(p, p.id, by_profile.get(p.id)) for p in profiles]


def _bidder_profile_id(user: User) -> UUID:
    if user.assigned_profile_id is None:
        raise AppError("no_assigned_profile", "You have no assigned profile yet", 400)
    return user.assigned_profile_id


async def get_bidder_config(db: AsyncSession, *, client_id: UUID, user: User) -> SheetConfigOut:
    profile_id = _bidder_profile_id(user)
    profile = await db.get(Profile, profile_id)
    row = (await db.execute(_config_query(client_id, profile_id, user.id))).scalar_one_or_none()
    return _out(profile, profile_id, row)


async def _save(
    db: AsyncSession,
    *,
    client_id: UUID,
    profile: Profile | None,
    profile_id: UUID,
    user_id: UUID | None,
    payload: SaveSheetConfigRequest,
) -> SheetConfigOut:
    title, tabs = await _call_google(
        db, client_id, lambda w: w.get_spreadsheet(payload.spreadsheet_id)
    )
    if payload.sheet_name not in tabs:
        raise AppError("tab_not_found", f"'{payload.sheet_name}' isn't a tab in {title}.", 400)
    # Writing the header (only if the tab is empty) doubles as the write-access check.
    await _call_google(
        db, client_id, lambda w: w.ensure_header(payload.spreadsheet_id, payload.sheet_name)
    )

    row = (await db.execute(_config_query(client_id, profile_id, user_id))).scalar_one_or_none()
    if row is None:
        row = SheetConfig(client_id=client_id, profile_id=profile_id, user_id=user_id)
        db.add(row)
    row.enabled = True
    row.spreadsheet_id = payload.spreadsheet_id
    row.spreadsheet_name = title
    row.sheet_name = payload.sheet_name
    await db.commit()
    return _out(profile, profile_id, row)


async def _clear(
    db: AsyncSession,
    *,
    client_id: UUID,
    profile: Profile | None,
    profile_id: UUID,
    user_id: UUID | None,
) -> SheetConfigOut:
    row = (await db.execute(_config_query(client_id, profile_id, user_id))).scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()
    return _out(profile, profile_id, None)


async def _client_profile(db: AsyncSession, client_id: UUID, profile_id: UUID) -> Profile:
    profile = await db.get(Profile, profile_id)
    if profile is None or profile.client_id != client_id:
        raise AppError("not_found", "Profile not found", 404)
    return profile


async def save_client_config(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID, payload: SaveSheetConfigRequest
) -> SheetConfigOut:
    profile = await _client_profile(db, client_id, profile_id)
    return await _save(
        db,
        client_id=client_id,
        profile=profile,
        profile_id=profile_id,
        user_id=None,
        payload=payload,
    )


async def clear_client_config(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID
) -> SheetConfigOut:
    profile = await _client_profile(db, client_id, profile_id)
    return await _clear(
        db, client_id=client_id, profile=profile, profile_id=profile_id, user_id=None
    )


async def save_bidder_config(
    db: AsyncSession, *, client_id: UUID, user: User, payload: SaveSheetConfigRequest
) -> SheetConfigOut:
    profile_id = _bidder_profile_id(user)
    return await _save(
        db,
        client_id=client_id,
        profile=await db.get(Profile, profile_id),
        profile_id=profile_id,
        user_id=user.id,
        payload=payload,
    )


async def clear_bidder_config(db: AsyncSession, *, client_id: UUID, user: User) -> SheetConfigOut:
    profile_id = _bidder_profile_id(user)
    return await _clear(
        db,
        client_id=client_id,
        profile=await db.get(Profile, profile_id),
        profile_id=profile_id,
        user_id=user.id,
    )


async def list_spreadsheets(db: AsyncSession, *, client_id: UUID) -> list[SpreadsheetOut]:
    files = await _call_google(db, client_id, lambda w: w.list_spreadsheets())
    return [SpreadsheetOut(**f) for f in files]


async def list_tabs(db: AsyncSession, *, client_id: UUID, spreadsheet_id: str) -> list[str]:
    _, tabs = await _call_google(db, client_id, lambda w: w.get_spreadsheet(spreadsheet_id))
    return tabs


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


async def recorded_jobs(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID, user: User
) -> list[Entry]:
    """The jobs already in the sheet this user's analyses for the profile would go to, for the
    duplicate check. Empty when no sheet is set up."""
    config = await resolve_config(db, client_id=client_id, profile_id=profile_id, user=user)
    if not _is_eligible(config):
        return []
    assert config is not None
    rows = await _call_google(
        db, client_id, lambda w: w.recorded_jobs(config.spreadsheet_id, config.sheet_name)
    )
    where = f"{config.spreadsheet_name or 'your sheet'} > {config.sheet_name}"
    return [
        Entry(company=company, position=position, job_link=link, where=f"row {n} of {where}")
        for n, (company, position, link) in rows
    ]


async def initial_record_status(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID | None, user: User
) -> RecordStatus:
    config = await resolve_config(db, client_id=client_id, profile_id=profile_id, user=user)
    return RecordStatus.PENDING if _is_eligible(config) else RecordStatus.SKIPPED


# A Sheets cell holds at most 50,000 characters.
_MAX_CELL_CHARS = 49_000
RECORDED_STATUS = "Applied"


def _text(value: str) -> str:
    """Rows are written with USER_ENTERED; a leading apostrophe keeps text like "=..." or
    "+1..." from being read as a formula or number (Sheets hides the apostrophe)."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def _sheet_date(moment: datetime, time_zone: str, locale: str) -> str:
    """The date as the spreadsheet's owner would type it, in the spreadsheet's time zone:
    "9/4/2026 12:09:33" for US-locale sheets, an unambiguous ISO form otherwise."""
    try:
        local = moment.astimezone(ZoneInfo(time_zone))
    except (ZoneInfoNotFoundError, ValueError):
        local = moment
    if locale == "en_US":
        return f"{local.month}/{local.day}/{local.year} {local:%H:%M:%S}"
    return f"{local:%Y-%m-%d %H:%M:%S}"


def _build_row(
    analysis: Analysis, *, number: int, resume_name: str, time_zone: str, locale: str
) -> list:
    """No | Company Name | Position Name | Job Link | Status | Resume | Date | Job Description"""
    return [
        number,
        _text(analysis.company_name),
        _text(analysis.position_name),
        _text(analysis.job_link or ""),
        RECORDED_STATUS,
        _text(resume_name),
        _sheet_date(analysis.created_at, time_zone, locale),
        _text(analysis.job_description[:_MAX_CELL_CHARS]),
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
                profile_id=analysis.profile_id,
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

        resume_type = (
            await db.get(ResumeType, analysis.selected_resume_type_id)
            if analysis.selected_resume_type_id
            else None
        )
        analysis.record_attempts += 1
        try:
            refresh_token = await google_service.get_decrypted_refresh_token(db, analysis.client_id)
            writer = SheetsWriter(refresh_token)
            # sheet_context also restores the header if the tab was emptied since setup.
            number, time_zone, locale = await asyncio.to_thread(
                writer.sheet_context, config.spreadsheet_id, config.sheet_name
            )
            row = _build_row(
                analysis,
                number=number,
                resume_name=resume_type.name if resume_type else "",
                time_zone=time_zone,
                locale=locale,
            )
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
