from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

from .conftest import create_user, login_headers


async def test_client_cannot_see_another_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="owner", role=Role.CLIENT)
    await create_user(db_session, username="stranger", role=Role.CLIENT)

    owner_headers = await login_headers(client, username="owner")
    stranger_headers = await login_headers(client, username="stranger")

    create_resp = await client.post(
        "/api/v1/profiles", headers=owner_headers, json={"name": "Java/Spring"}
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
    owner = await create_user(db_session, username="owner2", role=Role.CLIENT)
    await create_user(db_session, username="owner3", role=Role.CLIENT)
    await create_user(
        db_session,
        username="bidder-scope",
        role=Role.BIDDER,
        client_id=owner.id,
    )

    owner_headers = await login_headers(client, username="owner2")
    other_headers = await login_headers(client, username="owner3")
    bidder_headers = await login_headers(client, username="bidder-scope")

    await client.post("/api/v1/profiles", headers=owner_headers, json={"name": "PHP/Laravel"})
    await client.post("/api/v1/profiles", headers=other_headers, json={"name": "Ruby/Rails"})

    bidder_list = await client.get("/api/v1/profiles", headers=bidder_headers)
    assert bidder_list.status_code == 200
    names = {p["name"] for p in bidder_list.json()}
    assert names == {"PHP/Laravel"}

    bidder_create = await client.post(
        "/api/v1/profiles", headers=bidder_headers, json={"name": "Should Fail"}
    )
    assert bidder_create.status_code == 403


async def test_admin_without_client_id_lists_every_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, username="admin-profiles", role=Role.ADMIN)
    for name in ("profowner1", "profowner2"):
        await create_user(db_session, username=name, role=Role.CLIENT)
        await client.post(
            "/api/v1/profiles",
            headers=await login_headers(client, username=name),
            json={"name": f"{name} person"},
        )
    headers = await login_headers(client, username="admin-profiles")

    resp = await client.get("/api/v1/profiles", headers=headers)

    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert {"profowner1 person", "profowner2 person"} <= names
