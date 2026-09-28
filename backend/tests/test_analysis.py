from unittest.mock import AsyncMock, patch
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import AnalysisResult
from app.ai.service import AnalysisOutcome
from app.models import Role
from app.resume_types.models import ResumeType

from .conftest import create_user, login_headers


def _outcome(*, recommended: str | None = None) -> AnalysisOutcome:
    result = AnalysisResult(
        main_backend_skill="Python",
        backend_framework="Django",
        secondary_skills=["PostgreSQL", "Docker"],
        seniority="senior",
        key_requirements=["5+ years Python", "REST APIs"],
        recommended_resume_type_id=recommended,
        confidence=0.87,
        reasoning="Strong match on Python/Django experience.",
    )
    outcome = AnalysisOutcome(result, tokens=321, latency_ms=1500)
    outcome.model = "gpt-4o-mini"
    return outcome


async def _add_resume_type(
    client: AsyncClient, db_session: AsyncSession, headers: dict, profile_id: str, name: str
) -> str:
    resp = await client.post(
        "/api/v1/resume-types", headers=headers, json={"profile_id": profile_id, "name": name}
    )
    rt_id = resp.json()["id"]
    # Stands in for an uploaded resume (upload itself is covered in test_resume_types.py).
    await db_session.execute(
        update(ResumeType)
        .where(ResumeType.id == UUID(rt_id))
        .values(resume_summary=f"Senior {name} backend engineer.", skills=[name])
    )
    await db_session.commit()
    return rt_id


async def _setup(
    client: AsyncClient, db_session: AsyncSession, *, email: str
) -> tuple[dict, str, str]:
    """(headers, profile_id, resume_type_id): a client with a key, a profile and one resume."""
    await create_user(db_session, email=email, role=Role.CLIENT)
    headers = await login_headers(client, email=email)
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
    )
    profile_id = (
        await client.post("/api/v1/profiles", headers=headers, json={"name": "Jane Doe"})
    ).json()["id"]
    rt_id = await _add_resume_type(client, db_session, headers, profile_id, "Python")
    return headers, profile_id, rt_id


def _jd(profile_id: str | None = None, **extra) -> dict:
    body = {
        "company_name": "Acme",
        "position_name": "Eng",
        "job_description": "A Python JD",
        "job_link": "https://acme.example/jobs/1",
    }
    if profile_id:
        body["profile_id"] = profile_id
    return body | extra


async def test_analyze_requires_an_uploaded_resume(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="noresume@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="noresume@example.com")
    await client.put(
        "/api/v1/integrations/openai",
        headers=headers,
        json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
    )
    profile_id = (
        await client.post("/api/v1/profiles", headers=headers, json={"name": "Empty"})
    ).json()["id"]
    await client.post(
        "/api/v1/resume-types", headers=headers, json={"profile_id": profile_id, "name": "Go"}
    )

    analyze = AsyncMock()
    with patch("app.analysis.service.analyze_job_description", new=analyze):
        resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=_jd(profile_id))

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_resumes"
    analyze.assert_not_called()


async def test_client_must_choose_a_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, _, _ = await _setup(client, db_session, email="noprofilechoice@example.com")
    resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=_jd())
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "profile_required"


async def test_analyze_compares_only_the_chosen_profiles_resumes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id, rt_id = await _setup(client, db_session, email="summaryctx@example.com")
    other = (await client.post("/api/v1/profiles", headers=headers, json={"name": "Other"})).json()[
        "id"
    ]
    await _add_resume_type(client, db_session, headers, other, "Go")

    analyze = AsyncMock(return_value=_outcome(recommended=rt_id))
    with patch("app.analysis.service.analyze_job_description", new=analyze):
        resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=_jd(profile_id))

    assert resp.status_code == 200, resp.text
    assert analyze.call_args.kwargs["resumes"] == [
        {
            "id": rt_id,
            "name": "Python",
            "summary": "Senior Python backend engineer.",
            "skills": ["Python"],
        }
    ]


async def test_analyze_requires_api_key(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, email="noapikey@example.com", role=Role.CLIENT)
    headers = await login_headers(client, email="noapikey@example.com")
    resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=_jd())
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_api_key"


async def test_analyze_and_save_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id, rt_id = await _setup(client, db_session, email="analyzeflow@example.com")
    jd = _jd(profile_id, job_link="https://example.com/job/1")

    with patch(
        "app.analysis.service.analyze_job_description",
        new=AsyncMock(return_value=_outcome(recommended=rt_id)),
    ):
        analyze_resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=jd)
    assert analyze_resp.status_code == 200, analyze_resp.text
    body = analyze_resp.json()
    assert body["result"]["recommended_resume_type_id"] == rt_id

    save_resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json=jd
        | {
            "selected_resume_type_id": rt_id,
            "result": body["result"],
            "model": body["model"],
            "prompt_version": body["prompt_version"],
            "tokens": body["tokens"],
            "latency_ms": body["latency_ms"],
        },
    )
    assert save_resp.status_code == 201, save_resp.text
    saved = save_resp.json()
    assert saved["profile_id"] == profile_id
    assert saved["selected_resume_type_id"] == rt_id
    assert saved["recommended_resume_type_id"] == rt_id
    assert saved["record_status"] == "SKIPPED"

    # The same job again is blocked before the AI is called, by link or by company + position.
    analyze = AsyncMock(return_value=_outcome(recommended=rt_id))
    with patch("app.analysis.service.analyze_job_description", new=analyze):
        same_link = await client.post(
            "/api/v1/analyses/analyze",
            headers=headers,
            json=jd | {"company_name": "Other", "position_name": "Other"},
        )
        same_title = await client.post(
            "/api/v1/analyses/analyze",
            headers=headers,
            json=jd | {"job_link": "https://acme.example/jobs/999"},
        )
    assert same_link.status_code == 409
    assert same_link.json()["error"]["code"] == "duplicate_job"
    assert same_title.status_code == 409
    analyze.assert_not_called()

    list_resp = await client.get(
        "/api/v1/analyses", headers=headers, params={"profile_id": profile_id}
    )
    assert len(list_resp.json()) == 1


async def test_save_rejects_resume_from_another_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id, _ = await _setup(client, db_session, email="crossresume@example.com")
    other = (await client.post("/api/v1/profiles", headers=headers, json={"name": "Other"})).json()[
        "id"
    ]
    other_rt = await _add_resume_type(client, db_session, headers, other, "Go")

    resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json=_jd(profile_id)
        | {
            "selected_resume_type_id": other_rt,
            "result": _outcome(recommended=other_rt).result.model_dump(),
            "model": "gpt-4o-mini",
            "prompt_version": "v",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_resume_type"


async def test_bidder_always_uses_assigned_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id, rt_id = await _setup(client, db_session, email="bidderowner@example.com")
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()
    other = (await client.post("/api/v1/profiles", headers=headers, json={"name": "Other"})).json()[
        "id"
    ]
    await create_user(
        db_session,
        email="analysisbidder@example.com",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, email="analysisbidder@example.com")

    analyze = AsyncMock(return_value=_outcome(recommended=rt_id))
    with patch("app.analysis.service.analyze_job_description", new=analyze):
        await client.post("/api/v1/analyses/analyze", headers=bidder_headers, json=_jd(other))
    assert [r["id"] for r in analyze.call_args.kwargs["resumes"]] == [rt_id]

    save_resp = await client.post(
        "/api/v1/analyses",
        headers=bidder_headers,
        json=_jd(other)
        | {
            "selected_resume_type_id": rt_id,
            "result": _outcome(recommended=rt_id).result.model_dump(),
            "model": "gpt-4o-mini",
            "prompt_version": "v",
        },
    )
    assert save_resp.status_code == 201, save_resp.text
    # The bidder asked for `other`; the service forces their own assigned profile.
    assert save_resp.json()["profile_id"] == profile_id


async def test_bidder_sees_only_own_analyses(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id, rt_id = await _setup(client, db_session, email="scopeowner@example.com")
    client_row = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(
        db_session,
        email="scopedbidder@example.com",
        role=Role.BIDDER,
        client_id=client_row["id"],
        assigned_profile_id=profile_id,
    )
    bidder_headers = await login_headers(client, email="scopedbidder@example.com")

    await client.post(
        "/api/v1/analyses",
        headers=headers,
        json=_jd(profile_id)
        | {
            "result": _outcome(recommended=rt_id).result.model_dump(),
            "model": "gpt-4o-mini",
            "prompt_version": "v",
        },
    )

    assert (await client.get("/api/v1/analyses", headers=bidder_headers)).json() == []
    assert len((await client.get("/api/v1/analyses", headers=headers)).json()) == 1


async def test_dismatched_jd_cannot_be_saved(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id, _ = await _setup(client, db_session, email="dismatchsave@example.com")
    resp = await client.post(
        "/api/v1/analyses",
        headers=headers,
        json=_jd(profile_id)
        | {"result": _outcome().result.model_dump(), "model": "gpt-4o-mini", "prompt_version": "v"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "dismatched_jd"


async def test_job_link_is_required(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id, _ = await _setup(client, db_session, email="nolink@example.com")
    body = _jd(profile_id)
    del body["job_link"]
    resp = await client.post("/api/v1/analyses/analyze", headers=headers, json=body)
    assert resp.status_code == 422
