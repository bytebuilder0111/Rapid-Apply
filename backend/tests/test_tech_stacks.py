from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

from .conftest import create_user, login_headers


async def test_any_authenticated_user_can_list_active_stacks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="reader@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="reader@example.com")

    resp = await client.get("/api/v1/tech-stacks", headers=headers)

    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "Python/Django" in names


async def test_non_admin_cannot_manage_tech_stacks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="notadmin@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="notadmin@example.com")

    resp = await client.post("/api/v1/admin/tech-stacks", headers=headers, json={"name": "Rust"})

    assert resp.status_code == 403


async def test_admin_can_create_deactivate_and_delete_tech_stack(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="stackadmin@example.com", role=Role.ADMIN)
    headers = await login_headers(client, email="stackadmin@example.com")

    create_resp = await client.post(
        "/api/v1/admin/tech-stacks", headers=headers, json={"name": "Rust/Actix"}
    )
    assert create_resp.status_code == 201, create_resp.text
    stack_id = create_resp.json()["id"]

    # newly created stacks are immediately usable for profiles
    await create_user(db_session, email="rustclient@example.com", role=Role.CLIENT)
    client_headers = await login_headers(client, email="rustclient@example.com")
    profile_resp = await client.post(
        "/api/v1/profiles",
        headers=client_headers,
        json={"name": "Rust profile", "tech_stacks": ["Rust/Actix"]},
    )
    assert profile_resp.status_code == 201, profile_resp.text

    deactivate_resp = await client.patch(
        f"/api/v1/admin/tech-stacks/{stack_id}", headers=headers, json={"is_active": False}
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    # deactivated stacks can no longer be used for new profiles
    rejected_resp = await client.post(
        "/api/v1/profiles",
        headers=client_headers,
        json={"name": "Should fail", "tech_stacks": ["Rust/Actix"]},
    )
    assert rejected_resp.status_code == 400
    assert rejected_resp.json()["error"]["code"] == "invalid_tech_stack"

    # deactivated stacks no longer show up in the public active list
    active_resp = await client.get("/api/v1/tech-stacks", headers=client_headers)
    assert "Rust/Actix" not in {s["name"] for s in active_resp.json()}

    delete_resp = await client.delete(f"/api/v1/admin/tech-stacks/{stack_id}", headers=headers)
    assert delete_resp.status_code == 204


async def test_admin_cannot_create_duplicate_tech_stack_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="dupadmin@example.com", role=Role.ADMIN)
    headers = await login_headers(client, email="dupadmin@example.com")

    resp = await client.post(
        "/api/v1/admin/tech-stacks", headers=headers, json={"name": "Python/Django"}
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "name_taken"
