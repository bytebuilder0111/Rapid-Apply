from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Role

from .conftest import create_user, login_headers


async def test_non_client_cannot_access_integrations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="bidder-int", role=Role.BIDDER)
    headers = await login_headers(client, username="bidder-int")

    resp = await client.get("/api/v1/integrations/openai", headers=headers)

    assert resp.status_code == 403


async def test_no_key_configured_by_default(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="freshclient", role=Role.CLIENT)
    headers = await login_headers(client, username="freshclient")

    resp = await client.get("/api/v1/integrations/openai", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_key"] is False
    assert body["masked_key"] is None


async def test_save_mask_and_delete_key(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="keyclient", role=Role.CLIENT)
    headers = await login_headers(client, username="keyclient")

    save_resp = await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-1234567890abcdWXYZ", "model": "gpt-4o-mini"},
    )
    assert save_resp.status_code == 200, save_resp.text
    body = save_resp.json()
    assert body["has_key"] is True
    assert body["model"] == "gpt-4o-mini"
    assert body["masked_key"] == "sk-...WXYZ"
    assert "1234567890" not in body["masked_key"]

    get_resp = await client.get("/api/v1/integrations/openai", headers=headers)
    assert get_resp.json()["masked_key"] == "sk-...WXYZ"

    delete_resp = await client.delete("/api/v1/integrations/openai", headers=headers)
    assert delete_resp.status_code == 204

    after_delete = await client.get("/api/v1/integrations/openai", headers=headers)
    assert after_delete.json()["has_key"] is False


async def test_test_key_requires_saved_key(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="notestkey", role=Role.CLIENT)
    headers = await login_headers(client, username="notestkey")

    resp = await client.post("/api/v1/integrations/openai/test", headers=headers)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_api_key"


async def test_test_key_success_calls_openai_with_saved_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="testkeyok", role=Role.CLIENT)
    headers = await login_headers(client, username="testkeyok")
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-realkeyvalue1234", "model": "gpt-4o-mini"},
    )

    with patch("app.integrations.router.test_api_key", new_callable=AsyncMock) as mocked:
        resp = await client.post("/api/v1/integrations/openai/test", headers=headers)

    assert resp.status_code == 204
    mocked.assert_awaited_once_with("sk-realkeyvalue1234", "gpt-4o-mini")


async def test_test_key_surfaces_invalid_key_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="testkeybad", role=Role.CLIENT)
    headers = await login_headers(client, username="testkeybad")
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-badkey", "model": "gpt-4o-mini"},
    )

    with patch("app.integrations.router.test_api_key", new_callable=AsyncMock) as mocked:
        mocked.side_effect = AppError("invalid_api_key", "That OpenAI API key was rejected", 400)
        resp = await client.post("/api/v1/integrations/openai/test", headers=headers)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_api_key"
