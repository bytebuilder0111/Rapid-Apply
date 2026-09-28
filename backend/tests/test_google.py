from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import google_service
from app.models import Role

from .conftest import create_user, login_headers


async def test_authorize_requires_google_configured(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="googleauth", role=Role.CLIENT)
    headers = await login_headers(client, username="googleauth")

    resp = await client.get("/api/v1/integrations/google/authorize", headers=headers)
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "google_not_configured"


async def test_get_google_connection_disconnected_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="googlestatus", role=Role.CLIENT)
    headers = await login_headers(client, username="googlestatus")

    resp = await client.get("/api/v1/integrations/google", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "email": None, "status": None}


async def test_disconnect_with_no_connection_is_a_noop(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="googledisconnect", role=Role.CLIENT)
    headers = await login_headers(client, username="googledisconnect")

    resp = await client.delete("/api/v1/integrations/google", headers=headers)
    assert resp.status_code == 204


async def test_handle_callback_saves_connection_and_bidder_can_read_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="googlecallback", role=Role.CLIENT)
    headers = await login_headers(client, username="googlecallback")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()

    await create_user(
        db_session,
        username="googlebidder",
        role=Role.BIDDER,
        client_id=me["id"],
    )
    bidder_headers = await login_headers(client, username="googlebidder")

    with (
        patch("app.integrations.google_service.settings.google_client_id", "test-client-id"),
        patch("app.integrations.google_service.settings.google_client_secret", "test-secret"),
        patch(
            "app.integrations.google_service._fetch_token_sync",
            return_value=("refresh-token-abc", "client@gmail.com"),
        ),
    ):
        state = google_service._sign_state(me["id"])
        client_id = await google_service.handle_callback(db_session, code="fake-code", state=state)
        assert str(client_id) == me["id"]

    status_resp = await client.get("/api/v1/integrations/google", headers=headers)
    assert status_resp.json() == {
        "connected": True,
        "email": "client@gmail.com",
        "status": "CONNECTED",
    }

    # A bidder belonging to the same client can see (but not manage) the connection status.
    bidder_status = await client.get("/api/v1/integrations/google", headers=bidder_headers)
    assert bidder_status.json()["connected"] is True

    bidder_forbidden = await client.delete("/api/v1/integrations/google", headers=bidder_headers)
    assert bidder_forbidden.status_code == 403
