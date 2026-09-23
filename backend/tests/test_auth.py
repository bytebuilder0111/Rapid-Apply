from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_refresh_token
from app.models import RefreshToken

from .conftest import create_user as _create_user


async def test_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client1@example.com")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "client1@example.com", "password": "s3cret-pass"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "client1@example.com"
    assert "refresh_token" in response.cookies


async def test_login_invalid_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client2@example.com")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "client2@example.com", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_deactivated_user_cannot_login(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client3@example.com", is_active=False)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "client3@example.com", "password": "s3cret-pass"}
    )

    assert response.status_code == 401


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client4@example.com")
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "client4@example.com", "password": "s3cret-pass"}
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "client4@example.com"


async def test_refresh_rotates_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client5@example.com")
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "client5@example.com", "password": "s3cret-pass"}
    )
    old_cookie = login_response.cookies.get("refresh_token")

    refresh_response = await client.post("/api/v1/auth/refresh")

    assert refresh_response.status_code == 200
    new_cookie = refresh_response.cookies.get("refresh_token")
    assert new_cookie != old_cookie

    old_hash = hash_refresh_token(old_cookie)
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == old_hash)
    )
    old_row = result.scalar_one()
    assert old_row.revoked is True


async def test_refresh_without_cookie_fails(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="client6@example.com")
    await client.post(
        "/api/v1/auth/login", json={"email": "client6@example.com", "password": "s3cret-pass"}
    )

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401
