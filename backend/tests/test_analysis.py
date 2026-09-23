from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import AnalysisResult
from app.ai.service import AnalysisOutcome
from app.models import Role

from .conftest import create_user, login_headers


def _outcome(*, recommended_profile_id: str | None = None) -> AnalysisOutcome:
    result = AnalysisResult(
        main_backend_skill="Python",
        backend_framework="Django",
        secondary_skills=["PostgreSQL", "Docker"],
        seniority="senior",
        key_requirements=["5+ years Python", "REST APIs"],
        recommended_profile_id=recommended_profile_id,
        confidence=0.87,
        reasoning="Strong match on Python/Django experience.",
    )
    outcome = AnalysisOutcome(result, tokens=321, latency_ms=1500)
    outcome.model = "gpt-4o-mini"
    return outcome


async def _setup_client_with_key_and_profile(
    client: AsyncClient, db_session: AsyncSession, *, email: str
) -> tuple[dict, str]:
    await create_user(db_session, email=email, role=Role.CLIENT)
    headers = await login_headers(client, email=email)
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
    )
    profile_resp = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={"name": "Python profile", "tech_stacks": ["Go"]},
    )
    return headers, profile_resp.json()["id"]


async def test_analyze_requires_api_key(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="noapikey@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="noapikey@example.com")

    resp = await client.post(
        "/api/v1/analyses/analyze",
        headers=headers,
        json={
            "company_name": "Acme",
            "position_name": "Backend Eng",
            "job_description": "Python job",
        },
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_api_key"


async def test_analyze_and_save_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _setup_client_with_key_and_profile(
        client, db_session, email="analyzeflow@example.com"
    )

    with patch(
        "app.analysis.service.analyze_job_description",
        new=AsyncMock(return_value=_outcome(recommended_profile_id=profile_id)),
    ):
        analyze_resp = await client.post(
            "/api/v1/analyses/analyze",
            headers=headers,
            json={
                "company_name": "Acme",
                "position_name": "Backend Eng",
                "job_description": "We need a senior Python/Django engineer.",
                "job_link": "https://example.com/job/1",
            },
        )

    assert analyze_resp.status_code == 200, analyze_resp.text
    body = analyze_resp.json()
    assert body["result"]["recommended_profile_id"] == profile_id
    assert body["duplicate_warning"] is False

    save_resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json={
            "company_name": "Acme",
            "position_name": "Backend Eng",
            "job_description": "We need a senior Python/Django engineer.",
            "job_link": "https://example.com/job/1",
            "selected_profile_id": profile_id,
            "result": body["result"],
            "model": body["model"],
            "prompt_version": body["prompt_version"],
            "tokens": body["tokens"],
            "latency_ms": body["latency_ms"],
        },
    )
    assert save_resp.status_code == 201, save_resp.text
    saved = save_resp.json()
    assert saved["selected_profile_id"] == profile_id
    assert saved["record_status"] == "SKIPPED"

    # Re-analyzing the same JD/job link now surfaces the non-blocking duplicate warning.
    with patch(
        "app.analysis.service.analyze_job_description",
        new=AsyncMock(return_value=_outcome(recommended_profile_id=profile_id)),
    ):
        second_resp = await client.post(
            "/api/v1/analyses/analyze",
            headers=headers,
            json={
                "company_name": "Acme",
                "position_name": "Backend Eng",
                "job_description": "We need a senior Python/Django engineer.",
                "job_link": "https://example.com/job/1",
            },
        )
    assert second_resp.json()["duplicate_warning"] is True

    list_resp = await client.get("/api/v1/analyses", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_bidder_save_forces_own_assigned_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _setup_client_with_key_and_profile(
        client, db_session, email="bidderowner@example.com"
    )
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()

    other_profile_resp = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={"name": "Other profile", "tech_stacks": ["Go"]},
    )
    other_profile_id = other_profile_resp.json()["id"]

    await create_user(
        db_session,
        email="analysisbidder@example.com",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, email="analysisbidder@example.com")

    with patch(
        "app.analysis.service.analyze_job_description",
        new=AsyncMock(return_value=_outcome(recommended_profile_id=other_profile_id)),
    ):
        save_resp = await client.post(
            "/api/v1/analyses",
            headers=bidder_headers,
            json={
                "company_name": "Acme",
                "position_name": "Backend Eng",
                "job_description": "Some JD",
                "selected_profile_id": other_profile_id,
                "result": _outcome(recommended_profile_id=other_profile_id).result.model_dump(),
                "model": "gpt-4o-mini",
                "prompt_version": "jd-analysis-v1",
            },
        )

    assert save_resp.status_code == 201, save_resp.text
    # Bidder tried to save under other_profile_id; service forces their own assigned one.
    assert save_resp.json()["selected_profile_id"] == profile_id


async def test_bidder_sees_only_own_analyses(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _setup_client_with_key_and_profile(
        client, db_session, email="scopeowner@example.com"
    )
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(
        db_session,
        email="scopedbidder@example.com",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, email="scopedbidder@example.com")

    save_payload = {
        "company_name": "Acme",
        "position_name": "Backend Eng",
        "job_description": "Some JD",
        "result": _outcome().result.model_dump(),
        "model": "gpt-4o-mini",
        "prompt_version": "jd-analysis-v1",
    }
    await client.post("/api/v1/analyses", headers=headers, json=save_payload)

    bidder_list = await client.get("/api/v1/analyses", headers=bidder_headers)
    assert bidder_list.json() == []

    client_list = await client.get("/api/v1/analyses", headers=headers)
    assert len(client_list.json()) == 1
