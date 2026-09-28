"""Google OAuth connect/disconnect flow for a client's Google account.

Credential building for actual Sheets API calls lives in app/sheets/writer.py —
this module only owns the OAuth handshake and the google_connections row.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.integrations.models import GoogleConnection, GoogleConnectionStatus
from app.integrations.schemas import GoogleConnectionOut
from app.integrations.service import decrypt_key, encrypt_key

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/spreadsheets",
    # Names/ids only, so Config can list the account's spreadsheets in a dropdown.
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

_STATE_TTL = timedelta(minutes=10)

logger = logging.getLogger(__name__)

# Google may return the granted scopes in a different form or order than requested (and
# users can untick some). oauthlib treats any difference as an error unless relaxed; the
# granted set is checked explicitly in handle_callback instead.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def _require_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise AppError(
            "google_not_configured",
            "Server is missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET",
            500,
        )


def _sign_state(client_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {"client_id": str(client_id), "typ": "google_oauth_state", "exp": now + _STATE_TTL}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _verify_state(state: str) -> UUID:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("invalid_state", "Google sign-in link expired or is invalid", 400) from exc
    if payload.get("typ") != "google_oauth_state":
        raise AppError("invalid_state", "Google sign-in link expired or is invalid", 400)
    return UUID(payload["client_id"])


def _flow() -> Flow:
    # No PKCE: the authorize redirect and the callback are separate stateless requests, so
    # an auto-generated code_verifier from the first would be missing from the second and
    # Google would reject the code. This is a confidential client (it has a secret), so
    # PKCE isn't required.
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
        autogenerate_code_verifier=False,
    )


def build_authorize_url(client_id: UUID) -> str:
    _require_configured()
    authorize_url, _ = _flow().authorization_url(
        access_type="offline",
        prompt="consent",
        state=_sign_state(client_id),
    )
    return authorize_url


def _fetch_token_sync(code: str) -> tuple[str | None, str, set[str]]:
    flow = _flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    claims = google_id_token.verify_oauth2_token(
        credentials.id_token,
        GoogleAuthRequest(),
        audience=settings.google_client_id,
        clock_skew_in_seconds=30,
    )
    scope = flow.oauth2session.token.get("scope") or []
    granted = set(scope.split() if isinstance(scope, str) else scope)
    return credentials.refresh_token, claims["email"], granted


# Without these the user can't list or write spreadsheets, so connecting is pointless.
_REQUIRED_SCOPES = {
    "https://www.googleapis.com/auth/spreadsheets": (
        "See, edit, create, and delete your Google Sheets"
    ),
    "https://www.googleapis.com/auth/drive.metadata.readonly": (
        "See information about your Google Drive files"
    ),
}


async def handle_callback(db: AsyncSession, *, code: str, state: str) -> UUID:
    """Exchanges the auth code, stores the connection, and returns the client_id
    so the router can redirect back to that client's frontend page."""
    _require_configured()
    client_id = _verify_state(state)
    try:
        refresh_token, email, granted = await asyncio.to_thread(_fetch_token_sync, code)
    except (OAuth2Error, GoogleAuthError, ValueError) as exc:
        logger.warning("Google token exchange failed: %r", exc)
        raise AppError(
            "google_auth_failed", "Google sign-in failed. Please try connecting again.", 400
        ) from exc

    missing = [label for scope, label in _REQUIRED_SCOPES.items() if scope not in granted]
    if missing:
        raise AppError(
            "google_missing_permissions",
            "Google connected, but these permissions were unticked: "
            + "; ".join(missing)
            + ". Connect again and leave every box ticked.",
            400,
        )

    if refresh_token is None:
        # Google only issues a refresh token on first consent for a given client/user pair.
        # prompt=consent forces this, but guard anyway rather than silently losing offline access.
        raise AppError(
            "google_no_refresh_token",
            "Google did not grant offline access. Disconnect any prior grant at "
            "myaccount.google.com/permissions and try connecting again.",
            400,
        )

    result = await db.execute(
        select(GoogleConnection).where(GoogleConnection.client_id == client_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = GoogleConnection(
            client_id=client_id,
            email=email,
            refresh_token_encrypted=encrypt_key(refresh_token),
            status=GoogleConnectionStatus.CONNECTED,
        )
        db.add(row)
    else:
        row.email = email
        row.refresh_token_encrypted = encrypt_key(refresh_token)
        row.status = GoogleConnectionStatus.CONNECTED
    await db.commit()
    return client_id


async def get_connection_row(db: AsyncSession, client_id: UUID) -> GoogleConnection | None:
    result = await db.execute(
        select(GoogleConnection).where(GoogleConnection.client_id == client_id)
    )
    return result.scalar_one_or_none()


async def get_connection_out(db: AsyncSession, client_id: UUID) -> GoogleConnectionOut:
    row = await get_connection_row(db, client_id)
    if row is None:
        return GoogleConnectionOut(connected=False)
    return GoogleConnectionOut(connected=True, email=row.email, status=row.status.value)


async def disconnect(db: AsyncSession, client_id: UUID) -> None:
    row = await get_connection_row(db, client_id)
    if row is not None:
        await db.delete(row)
        await db.commit()


async def get_decrypted_refresh_token(db: AsyncSession, client_id: UUID) -> str:
    row = await get_connection_row(db, client_id)
    if row is None:
        raise AppError("google_not_connected", "No Google account connected for this client", 400)
    if row.status == GoogleConnectionStatus.NEEDS_RECONNECT:
        raise AppError(
            "google_needs_reconnect",
            "Google connection needs to be reconnected",
            400,
        )
    return decrypt_key(row.refresh_token_encrypted)


async def mark_needs_reconnect(db: AsyncSession, client_id: UUID) -> None:
    row = await get_connection_row(db, client_id)
    if row is not None:
        row.status = GoogleConnectionStatus.NEEDS_RECONNECT
        await db.commit()
