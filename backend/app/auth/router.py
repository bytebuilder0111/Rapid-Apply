from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import session_cache
from app.auth.schemas import AccessTokenResponse, LoginRequest
from app.auth.service import (
    create_access_token,
    decode_session_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.db import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.models import RefreshToken, User
from app.users.schemas import UserOut

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
# Path="/" (not scoped to /api/v1/auth) so Next.js middleware can see the cookie
# on every route to gate access; the value itself is still httpOnly and only
# ever read by the /auth/refresh and /auth/logout handlers below.
REFRESH_COOKIE_PATH = "/"


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        expires=expires_at,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    result = await db.execute(
        select(User).where(func.lower(User.username) == payload.username.strip().lower())
    )
    user = result.scalar_one_or_none()
    valid_password = user is not None and verify_password(payload.password, user.password_hash)
    is_usable = user is not None and user.is_active and user.deleted_at is None
    if not is_usable or not valid_password:
        raise AppError("invalid_credentials", "Invalid username or password", 401)

    access_token = create_access_token(user)
    token, token_hash, expires_at = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    _set_refresh_cookie(response, token, expires_at)
    return AccessTokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise AppError("unauthorized", "Missing refresh token", 401)

    token_hash = hash_refresh_token(token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if stored is None or stored.revoked or stored.expires_at < now:
        raise AppError("unauthorized", "Invalid or expired refresh token", 401)

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AppError("unauthorized", "Invalid or expired refresh token", 401)

    stored.revoked = True
    new_token, new_hash, new_expires_at = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=new_expires_at))
    await db.commit()

    _set_refresh_cookie(response, new_token, new_expires_at)
    access_token = create_access_token(user)
    return AccessTokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        token_hash = hash_refresh_token(token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()
        if stored is not None:
            stored.revoked = True
            await db.commit()

    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"status": "ok"}


@router.get("/session", status_code=204)
async def session(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """The check every open tab makes each minute: 204 while the session is on, 401 once it
    ended (signed out by an admin, password reset, deactivated). Answered from memory, and it
    accepts an expired access token, so an idle tab neither queries the database nor renews
    its token; real requests still do both."""
    if credentials is None:
        raise AppError("unauthorized", "Not authenticated", 401)
    claims = decode_session_token(credentials.credentials)
    user_id = UUID(claims["sub"])
    state = session_cache.get(user_id)
    if state is None:
        user = await db.get(User, user_id)
        usable = user is not None and user.is_active and user.deleted_at is None
        state = (usable, user.session_version if user else -1)
        session_cache.put(user_id, usable=state[0], session_version=state[1])
    usable, version = state
    if not usable or claims.get("sv", 0) != version:
        raise AppError("session_ended", "Your session has ended. Please sign in again.", 401)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
