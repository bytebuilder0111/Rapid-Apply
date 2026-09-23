from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

from .conftest import create_user, login_headers


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str) -> dict:
    await create_user(db_session, email=email, role=Role.ADMIN)
    return await login_headers(client, email=email)


async def test_non_admin_cannot_list_clients(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="c1@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="c1@example.com")

    response = await client.get("/api/v1/admin/clients", headers=headers)

    assert response.status_code == 403


async def test_admin_client_and_bidder_crud_flow(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _admin_headers(client, db_session, "admin1@example.com")

    create_client_resp = await client.post(
        "/api/v1/admin/clients",
        headers=headers,
        json={"email": "newclient@example.com", "name": "New Client", "password": "s3cret-pass"},
    )
    assert create_client_resp.status_code == 201, create_client_resp.text
    client_id = create_client_resp.json()["id"]

    # A profile must exist and belong to the client before a bidder can be assigned to it.
    client_login = await login_headers(
        client, email="newclient@example.com", password="s3cret-pass"
    )
    profile_resp = await client.post(
        "/api/v1/profiles",
        headers=client_login,
        json={
            "name": "Python/Django",
            "tech_stacks": ["Python/Django"],
            "skills": ["Django"],
        },
    )
    assert profile_resp.status_code == 201, profile_resp.text
    profile_id = profile_resp.json()["id"]

    create_bidder_resp = await client.post(
        "/api/v1/admin/bidders",
        headers=headers,
        json={
            "client_id": client_id,
            "email": "bidder1@example.com",
            "name": "Bidder One",
            "password": "s3cret-pass",
            "assigned_profile_id": profile_id,
        },
    )
    assert create_bidder_resp.status_code == 201, create_bidder_resp.text
    bidder_id = create_bidder_resp.json()["id"]
    assert create_bidder_resp.json()["client_id"] == client_id

    list_resp = await client.get(
        "/api/v1/admin/bidders", headers=headers, params={"client_id": client_id}
    )
    assert list_resp.status_code == 200
    assert [b["id"] for b in list_resp.json()] == [bidder_id]

    dashboard_resp = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert dashboard_resp.status_code == 200
    body = dashboard_resp.json()
    assert body["clients"]["total"] >= 1
    assert body["bidders"]["total"] >= 1

    deactivate_resp = await client.post(
        f"/api/v1/admin/bidders/{bidder_id}/deactivate", headers=headers
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    login_after_deactivate = await client.post(
        "/api/v1/auth/login", json={"email": "bidder1@example.com", "password": "s3cret-pass"}
    )
    assert login_after_deactivate.status_code == 401


async def test_bidder_requires_profile_owned_by_same_client(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _admin_headers(client, db_session, "admin2@example.com")

    client_a = await create_user(db_session, email="clienta@example.com", role=Role.CLIENT)
    await create_user(db_session, email="clientb@example.com", role=Role.CLIENT)

    profile_resp = await client.post(
        "/api/v1/profiles",
        headers=await login_headers(client, email="clientb@example.com"),
        json={"name": "Node/NestJS", "tech_stacks": ["Node.js/NestJS"]},
    )
    assert profile_resp.status_code == 201
    other_clients_profile_id = profile_resp.json()["id"]

    resp = await client.post(
        "/api/v1/admin/bidders",
        headers=headers,
        json={
            "client_id": str(client_a.id),
            "email": "crossbidder@example.com",
            "name": "Cross Bidder",
            "password": "s3cret-pass",
            "assigned_profile_id": other_clients_profile_id,
        },
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_profile"


async def test_soft_deleting_client_deactivates_its_bidders(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _admin_headers(client, db_session, "admin3@example.com")

    client_user = await create_user(db_session, email="clientc@example.com", role=Role.CLIENT)
    profile_resp = await client.post(
        "/api/v1/profiles",
        headers=await login_headers(client, email="clientc@example.com"),
        json={"name": "Go", "tech_stacks": ["Go"]},
    )
    profile_id = profile_resp.json()["id"]
    bidder_resp = await client.post(
        "/api/v1/admin/bidders",
        headers=headers,
        json={
            "client_id": str(client_user.id),
            "email": "bidderc@example.com",
            "name": "Bidder C",
            "password": "s3cret-pass",
            "assigned_profile_id": profile_id,
        },
    )
    assert bidder_resp.status_code == 201

    delete_resp = await client.delete(f"/api/v1/admin/clients/{client_user.id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted_at"] is not None

    client_login = await client.post(
        "/api/v1/auth/login", json={"email": "clientc@example.com", "password": "s3cret-pass"}
    )
    assert client_login.status_code == 401

    bidder_login = await client.post(
        "/api/v1/auth/login", json={"email": "bidderc@example.com", "password": "s3cret-pass"}
    )
    assert bidder_login.status_code == 401
