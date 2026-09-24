from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role
from app.sheets.service import extract_spreadsheet_id

from .conftest import create_user, login_headers


def test_extract_spreadsheet_id_from_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/1AbC-XyZ_123/edit#gid=0"
    assert extract_spreadsheet_id(url) == "1AbC-XyZ_123"


def test_extract_spreadsheet_id_passthrough() -> None:
    assert extract_spreadsheet_id("1AbC-XyZ_123") == "1AbC-XyZ_123"


async def _client_with_profile(
    client: AsyncClient, db_session: AsyncSession, *, email: str
) -> tuple[dict, str]:
    await create_user(db_session, email=email, role=Role.CLIENT)
    headers = await login_headers(client, email=email)
    profile_resp = await client.post("/api/v1/profiles", headers=headers, json={"name": "P1"})
    return headers, profile_resp.json()["id"]


async def test_client_sheet_config_crud(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_profile(
        client, db_session, email="sheetconfig@example.com"
    )

    list_resp = await client.get("/api/v1/sheet-configs", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json() == [
        {
            "profile_id": profile_id,
            "profile_name": "P1",
            "enabled": False,
            "spreadsheet_id": None,
            "sheet_name": None,
        }
    ]

    save_resp = await client.put(
        f"/api/v1/sheet-configs/{profile_id}",
        headers=headers,
        json={
            "enabled": True,
            "spreadsheet": "https://docs.google.com/spreadsheets/d/sheet123/edit",
            "sheet_name": "Sheet1",
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    body = save_resp.json()
    assert body["enabled"] is True
    assert body["spreadsheet_id"] == "sheet123"
    assert body["sheet_name"] == "Sheet1"


async def test_bidder_cannot_configure_other_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(
        client, db_session, email="bidderconfigowner@example.com"
    )
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(
        db_session,
        email="bidderconfiguser@example.com",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, email="bidderconfiguser@example.com")

    other_resp = await client.post("/api/v1/profiles", headers=headers, json={"name": "P2"})
    other_profile_id = other_resp.json()["id"]

    forbidden = await client.put(
        f"/api/v1/sheet-configs/{other_profile_id}",
        headers=bidder_headers,
        json={"enabled": True, "spreadsheet": "abc", "sheet_name": "Sheet1"},
    )
    assert forbidden.status_code == 403

    allowed = await client.put(
        f"/api/v1/sheet-configs/{profile_id}",
        headers=bidder_headers,
        json={"enabled": True, "spreadsheet": "abc", "sheet_name": "Sheet1"},
    )
    assert allowed.status_code == 200, allowed.text

    mine = await client.get("/api/v1/sheet-configs", headers=bidder_headers)
    assert mine.json() == [
        {
            "profile_id": profile_id,
            "profile_name": "P1",
            "enabled": True,
            "spreadsheet_id": "abc",
            "sheet_name": "Sheet1",
        }
    ]


async def test_list_tabs_and_test_write_use_writer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, _ = await _client_with_profile(client, db_session, email="tabsclient@example.com")

    fake_row = MagicMock()
    fake_row.status = None
    with patch(
        "app.sheets.service.google_service.get_decrypted_refresh_token",
        new=AsyncMock(return_value="fake-refresh-token"),
    ):
        with patch("app.sheets.service.SheetsWriter") as writer_cls:
            writer_cls.return_value.list_tabs.return_value = ["Sheet1", "Sheet2"]
            tabs_resp = await client.get(
                "/api/v1/sheet-configs/tabs", headers=headers, params={"spreadsheet": "sheet123"}
            )
        assert tabs_resp.status_code == 200
        assert tabs_resp.json() == {"tabs": ["Sheet1", "Sheet2"]}

        with patch("app.sheets.service.SheetsWriter") as writer_cls:
            test_resp = await client.post(
                "/api/v1/sheet-configs/test",
                headers=headers,
                json={"spreadsheet": "sheet123", "sheet_name": "Sheet1"},
            )
        assert test_resp.status_code == 204
        writer_cls.return_value.ensure_header.assert_called_once_with("sheet123", "Sheet1")


async def test_analysis_save_records_to_sheet_in_background(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(
        client, db_session, email="recordflow@example.com"
    )
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
    )
    await client.put(
        f"/api/v1/sheet-configs/{profile_id}",
        headers=headers,
        json={"enabled": True, "spreadsheet": "sheet123", "sheet_name": "Sheet1"},
    )

    payload = {
        "company_name": "Acme",
        "position_name": "Backend Eng",
        "job_description": "Some JD",
        "selected_profile_id": profile_id,
        "result": {
            "main_backend_skill": "Python",
            "backend_framework": "Django",
            "secondary_skills": [],
            "seniority": "senior",
            "key_requirements": [],
            "recommended_profile_id": profile_id,
            "confidence": 0.9,
            "reasoning": "Match",
        },
        "model": "gpt-4o-mini",
        "prompt_version": "jd-analysis-v1",
    }

    with patch(
        "app.sheets.service.google_service.get_decrypted_refresh_token",
        new=AsyncMock(return_value="fake-refresh-token"),
    ):
        with patch("app.sheets.service.SheetsWriter") as writer_cls:
            save_resp = await client.post("/api/v1/analyses", headers=headers, json=payload)

    assert save_resp.status_code == 201, save_resp.text
    # The response is built before the background task runs, so it still reads PENDING.
    assert save_resp.json()["record_status"] == "PENDING"
    analysis_id = save_resp.json()["id"]
    writer_cls.return_value.append_row.assert_called_once()

    final = await client.get(f"/api/v1/analyses/{analysis_id}", headers=headers)
    assert final.json()["record_status"] == "SUCCESS"


async def test_retry_requires_failed_status(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_profile(
        client, db_session, email="retryflow@example.com"
    )
    save_resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json={
            "company_name": "Acme",
            "position_name": "Backend Eng",
            "job_description": "Some JD",
            "result": {
                "main_backend_skill": "Python",
                "backend_framework": None,
                "secondary_skills": [],
                "seniority": "unknown",
                "key_requirements": [],
                "recommended_profile_id": None,
                "confidence": 0.5,
                "reasoning": "N/A",
            },
            "model": "gpt-4o-mini",
            "prompt_version": "jd-analysis-v1",
        },
    )
    analysis_id = save_resp.json()["id"]
    assert save_resp.json()["record_status"] == "SKIPPED"

    retry_resp = await client.post(f"/api/v1/analyses/{analysis_id}/retry", headers=headers)
    assert retry_resp.status_code == 400
    assert retry_resp.json()["error"]["code"] == "not_retryable"
