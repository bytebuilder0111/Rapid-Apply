from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role

from .conftest import create_user, login_headers


@contextmanager
def fake_google(*, title: str = "Job Tracker", tabs: list[str] | None = None):
    """Stands in for a connected Google account; yields the SheetsWriter instance mock."""
    with (
        patch(
            "app.sheets.service.google_service.get_decrypted_refresh_token",
            new=AsyncMock(return_value="fake-refresh-token"),
        ),
        patch("app.sheets.service.SheetsWriter") as writer_cls,
    ):
        writer: MagicMock = writer_cls.return_value
        writer.get_spreadsheet.return_value = (title, tabs or ["Sheet1", "Job Log"])
        writer.sheet_context.return_value = (5, "America/Chicago", "en_US")
        writer.recorded_jobs.return_value = [
            (2, ["Turing", "Software Engineer", "https://turing.example/se"])
        ]
        writer.list_spreadsheets.return_value = [
            {"id": "sheet123", "name": "Job Tracker"},
            {"id": "sheet456", "name": "Budget"},
        ]
        yield writer


async def _client_with_profile(
    client: AsyncClient, db_session: AsyncSession, *, username: str
) -> tuple[dict, str]:
    await create_user(db_session, username=username, role=Role.CLIENT)
    headers = await login_headers(client, username=username)
    profile_resp = await client.post("/api/v1/profiles", headers=headers, json={"name": "P1"})
    return headers, profile_resp.json()["id"]


async def _resume_type(client: AsyncClient, headers: dict, profile_id: str) -> str:
    resp = await client.post(
        "/api/v1/resume-types", headers=headers, json={"profile_id": profile_id, "name": "Python"}
    )
    return resp.json()["id"]


def _config(profile_id: str, **overrides) -> dict:
    base = {
        "profile_id": profile_id,
        "profile_name": "P1",
        "enabled": False,
        "spreadsheet_id": None,
        "spreadsheet_name": None,
        "sheet_name": None,
    }
    return base | overrides


async def test_save_and_clear_client_sheet_config(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="sheetconfig")
    assert (await client.get("/api/v1/sheet-configs", headers=headers)).json() == [
        _config(profile_id)
    ]

    with fake_google() as writer:
        save_resp = await client.put(
            f"/api/v1/sheet-configs/{profile_id}",
            headers=headers,
            json={"spreadsheet_id": "sheet123", "sheet_name": "Job Log"},
        )
    assert save_resp.status_code == 200, save_resp.text
    saved = _config(
        profile_id,
        enabled=True,
        spreadsheet_id="sheet123",
        spreadsheet_name="Job Tracker",
        sheet_name="Job Log",
    )
    assert save_resp.json() == saved
    # Saving verifies write access by writing the header row (only if the tab is empty).
    writer.ensure_header.assert_called_once_with("sheet123", "Job Log")
    assert (await client.get("/api/v1/sheet-configs", headers=headers)).json() == [saved]

    clear_resp = await client.delete(f"/api/v1/sheet-configs/{profile_id}", headers=headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json() == _config(profile_id)
    assert (await client.get("/api/v1/sheet-configs", headers=headers)).json() == [
        _config(profile_id)
    ]


async def test_save_rejects_a_tab_that_does_not_exist(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="badtab")
    with fake_google(tabs=["Sheet1"]) as writer:
        resp = await client.put(
            f"/api/v1/sheet-configs/{profile_id}",
            headers=headers,
            json={"spreadsheet_id": "sheet123", "sheet_name": "Missing"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "tab_not_found"
    writer.ensure_header.assert_not_called()


async def test_save_requires_google_connection(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="nogoogle")
    resp = await client.put(
        f"/api/v1/sheet-configs/{profile_id}",
        headers=headers,
        json={"spreadsheet_id": "sheet123", "sheet_name": "Sheet1"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "google_not_connected"


async def test_list_spreadsheets_and_tabs(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, _ = await _client_with_profile(client, db_session, username="listsheets")
    with fake_google() as writer:
        sheets = await client.get("/api/v1/sheet-configs/spreadsheets", headers=headers)
        tabs = await client.get(
            "/api/v1/sheet-configs/tabs", headers=headers, params={"spreadsheet_id": "sheet123"}
        )
    assert sheets.json() == [
        {"id": "sheet123", "name": "Job Tracker"},
        {"id": "sheet456", "name": "Budget"},
    ]
    assert tabs.json() == {"tabs": ["Sheet1", "Job Log"]}
    writer.get_spreadsheet.assert_called_once_with("sheet123")


async def test_bidder_can_only_configure_assigned_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(
        client, db_session, username="bidderconfigowner"
    )
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(
        db_session,
        username="bidderconfiguser",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, username="bidderconfiguser")
    other_profile_id = (
        await client.post("/api/v1/profiles", headers=headers, json={"name": "P2"})
    ).json()["id"]
    body = {"spreadsheet_id": "sheet123", "sheet_name": "Sheet1"}

    with fake_google():
        forbidden = await client.put(
            f"/api/v1/sheet-configs/{other_profile_id}", headers=bidder_headers, json=body
        )
        forbidden_clear = await client.delete(
            f"/api/v1/sheet-configs/{other_profile_id}", headers=bidder_headers
        )
        allowed = await client.put(
            f"/api/v1/sheet-configs/{profile_id}", headers=bidder_headers, json=body
        )

    assert forbidden.status_code == 403
    assert forbidden_clear.status_code == 403
    assert allowed.status_code == 200, allowed.text
    mine = await client.get("/api/v1/sheet-configs", headers=bidder_headers)
    assert mine.json() == [
        _config(
            profile_id,
            enabled=True,
            spreadsheet_id="sheet123",
            spreadsheet_name="Job Tracker",
            sheet_name="Sheet1",
        )
    ]
    # The bidder's personal config doesn't change the client's profile-level one.
    client_view = await client.get("/api/v1/sheet-configs", headers=headers)
    assert _config(profile_id) in client_view.json()


async def test_analysis_save_records_to_sheet_in_background(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="recordflow")
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
    )
    with fake_google():
        saved = await client.put(
            f"/api/v1/sheet-configs/{profile_id}",
            headers=headers,
            json={"spreadsheet_id": "sheet123", "sheet_name": "Sheet1"},
        )
    assert saved.status_code == 200, saved.text

    rt_id = await _resume_type(client, headers, profile_id)
    payload = {
        "company_name": "Acme",
        "position_name": "Backend Eng",
        "job_description": "Some JD",
        "job_link": "https://acme.example/jobs/1",
        "profile_id": profile_id,
        "selected_resume_type_id": rt_id,
        "result": {
            "main_backend_skill": "Python",
            "backend_framework": "Django",
            "secondary_skills": [],
            "seniority": "senior",
            "key_requirements": [],
            "recommended_resume_type_id": rt_id,
            "confidence": 0.9,
            "reasoning": "Match",
        },
        "model": "gpt-4o-mini",
        "prompt_version": "jd-analysis-v1",
    }

    with fake_google() as writer:
        save_resp = await client.post("/api/v1/analyses", headers=headers, json=payload)

    assert save_resp.status_code == 201, save_resp.text
    # The response is built before the background task runs, so it still reads PENDING.
    assert save_resp.json()["record_status"] == "PENDING"
    analysis_id = save_resp.json()["id"]
    writer.append_row.assert_called_once()
    spreadsheet_id, tab, row = writer.append_row.call_args.args
    assert (spreadsheet_id, tab) == ("sheet123", "Sheet1")
    assert row[0] == 5 and row[1:3] == ["Acme", "Backend Eng"] and row[4] == "Applied"
    assert row[5] == "Python"

    final = await client.get(f"/api/v1/analyses/{analysis_id}", headers=headers)
    assert final.json()["record_status"] == "SUCCESS"


async def test_retry_requires_failed_status(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="retryflow")
    rt_id = await _resume_type(client, headers, profile_id)
    save_resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json={
            "company_name": "Acme",
            "position_name": "Backend Eng",
            "job_description": "Some JD",
            "job_link": "https://acme.example/jobs/2",
            "profile_id": profile_id,
            "result": {
                "main_backend_skill": "Python",
                "backend_framework": None,
                "secondary_skills": [],
                "seniority": "unknown",
                "key_requirements": [],
                "recommended_resume_type_id": rt_id,
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


async def test_job_already_in_the_sheet_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_profile(client, db_session, username="sheetdup")
    rt_id = await _resume_type(client, headers, profile_id)
    with fake_google():
        await client.put(
            f"/api/v1/sheet-configs/{profile_id}",
            headers=headers,
            json={"spreadsheet_id": "sheet123", "sheet_name": "Sheet1"},
        )
        resp = await client.post(
            "/api/v1/analyses",
            headers=headers,
            json={
                "company_name": "TURING",
                "position_name": "software engineer",
                "job_description": "Some JD",
                "job_link": "https://turing.example/a-new-link",
                "profile_id": profile_id,
                "result": {
                    "main_backend_skill": "Python",
                    "seniority": "senior",
                    "recommended_resume_type_id": rt_id,
                    "confidence": 0.9,
                    "reasoning": "Match",
                },
                "model": "gpt-4o-mini",
                "prompt_version": "v",
            },
        )
    assert resp.status_code == 409
    assert "row 2 of Job Tracker > Sheet1" in resp.json()["error"]["message"]
