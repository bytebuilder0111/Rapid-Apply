from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

from .conftest import create_user, login_headers


async def test_client_cannot_see_another_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="owner@example.com", role=Role.CLIENT)
    await create_user(db_session, email="stranger@example.com", role=Role.CLIENT)

    owner_headers = await login_headers(client, email="owner@example.com")
    stranger_headers = await login_headers(client, email="stranger@example.com")

    create_resp = await client.post(
        "/api/v1/profiles",
        headers=owner_headers,
        json={
            "name": "Java/Spring",
            "tech_stacks": ["Java/Spring"],
            "skills": ["Spring Boot"],
        },
    )
    assert create_resp.status_code == 201
    profile_id = create_resp.json()["id"]

    owner_list = await client.get("/api/v1/profiles", headers=owner_headers)
    assert [p["id"] for p in owner_list.json()] == [profile_id]

    stranger_list = await client.get("/api/v1/profiles", headers=stranger_headers)
    assert stranger_list.json() == []

    stranger_get = await client.get(f"/api/v1/profiles/{profile_id}", headers=stranger_headers)
    assert stranger_get.status_code == 404

    stranger_update = await client.patch(
        f"/api/v1/profiles/{profile_id}", headers=stranger_headers, json={"name": "Hijacked"}
    )
    assert stranger_update.status_code == 404

    stranger_delete = await client.delete(
        f"/api/v1/profiles/{profile_id}", headers=stranger_headers
    )
    assert stranger_delete.status_code == 404


async def test_bidder_sees_only_their_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await create_user(db_session, email="owner2@example.com", role=Role.CLIENT)
    await create_user(db_session, email="owner3@example.com", role=Role.CLIENT)
    await create_user(
        db_session,
        email="bidder-scope@example.com",
        role=Role.BIDDER,
        client_id=owner.id,
    )

    owner_headers = await login_headers(client, email="owner2@example.com")
    other_headers = await login_headers(client, email="owner3@example.com")
    bidder_headers = await login_headers(client, email="bidder-scope@example.com")

    await client.post(
        "/api/v1/profiles",
        headers=owner_headers,
        json={"name": "PHP/Laravel", "tech_stacks": ["PHP/Laravel"]},
    )
    await client.post(
        "/api/v1/profiles",
        headers=other_headers,
        json={"name": "Ruby/Rails", "tech_stacks": ["Ruby/Rails"]},
    )

    bidder_list = await client.get("/api/v1/profiles", headers=bidder_headers)
    assert bidder_list.status_code == 200
    names = {p["name"] for p in bidder_list.json()}
    assert names == {"PHP/Laravel"}

    bidder_create = await client.post(
        "/api/v1/profiles",
        headers=bidder_headers,
        json={"name": "Should Fail", "tech_stacks": ["Go"]},
    )
    assert bidder_create.status_code == 403


async def test_admin_requires_client_id_to_list_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin-profiles@example.com", role=Role.ADMIN)
    headers = await login_headers(client, email="admin-profiles@example.com")

    resp = await client.get("/api/v1/profiles", headers=headers)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "client_id_required"


async def test_profile_rejects_unknown_backend_stack(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="stackcheck@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="stackcheck@example.com")

    resp = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={"name": "Bogus", "tech_stacks": ["COBOL/Mainframe"]},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_tech_stack"


async def test_profile_accepts_multiple_tech_stacks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="multistack@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="multistack@example.com")

    resp = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={"name": "Polyglot", "tech_stacks": ["Python/Django", "Go", "Node.js/NestJS"]},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["tech_stacks"] == ["Python/Django", "Go", "Node.js/NestJS"]


async def test_profile_requires_at_least_one_tech_stack(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="emptystack@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="emptystack@example.com")

    resp = await client.post(
        "/api/v1/profiles", headers=headers, json={"name": "Empty", "tech_stacks": []}
    )

    assert resp.status_code == 422
