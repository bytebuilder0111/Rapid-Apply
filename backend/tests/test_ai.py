from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.ai.prompts import build_user_prompt
from app.ai.schemas import AnalysisResponse, AnalysisResult, ResumeCheck, ResumeSummary
from app.ai.service import analyze_job_description, summarize_resume
from app.analysis.models import RecordStatus
from app.analysis.schemas import AnalysisOut
from app.errors import AppError

PROFILES = [
    {
        "id": "p1",
        "name": "Python Backend",
        "summary": "Senior backend engineer, Python/Django APIs.",
        "skills": ["Python", "Django"],
    },
    {
        "id": "p2",
        "name": "iOS",
        "summary": "Mobile engineer building iOS apps in Swift.",
        "skills": ["Swift", "SwiftUI"],
    },
]


PYTHON_JD = "Backend developer building Python APIs."


def _fake_openai(*parsed_results) -> MagicMock:
    """An AsyncOpenAI stand-in whose parse() returns each given parsed value in turn."""
    completions = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=p))],
            usage=SimpleNamespace(total_tokens=100),
        )
        for p in parsed_results
    ]
    client = MagicMock()
    client.chat.completions.parse = AsyncMock(side_effect=completions)
    return MagicMock(return_value=client)


def _check(pid: str, *, same_role: bool, fit: float) -> ResumeCheck:
    return ResumeCheck(
        profile_id=pid, matching_technologies=[], same_role=same_role, fit=fit, note=f"{pid} note."
    )


def _response(**overrides) -> AnalysisResponse:
    base = {
        "jd_summary": "Senior backend role building Python APIs.",
        "role_type": "backend",
        "jd_core_stack": ["Python"],
        "main_backend_skill": "Python",
        "backend_framework": None,
        "secondary_skills": [],
        "seniority": "senior",
        "key_requirements": [],
        "resume_checks": [
            _check("p1", same_role=True, fit=0.9),
            _check("p2", same_role=False, fit=0.1),
        ],
    }
    return AnalysisResponse(**(base | overrides))


def test_prompt_lists_each_resume_summary_and_skills() -> None:
    prompt = build_user_prompt("JD text", PROFILES)
    assert "- id=p1 name='Python Backend'" in prompt
    assert "summary: Mobile engineer building iOS apps in Swift." in prompt
    assert "key_skills: Swift, SwiftUI" in prompt
    assert prompt.endswith("Job description:\nJD text")


def test_response_schema_is_valid_for_openai_and_summarizes_first() -> None:
    schema = to_strict_json_schema(AnalysisResponse)
    props = list(schema["properties"])
    assert props[:3] == ["jd_summary", "role_type", "jd_core_stack"]
    assert props[-1] == "resume_checks"
    assert set(props) <= set(schema["required"])
    to_strict_json_schema(ResumeSummary)


async def test_summarize_resume_trims_skills_to_eight() -> None:
    parsed = ResumeSummary(summary=" Backend dev. ", key_skills=[f"s{i}" for i in range(12)])
    with patch("app.ai.service.AsyncOpenAI", _fake_openai(parsed)):
        result = await summarize_resume(api_key="k", model="gpt-4o-mini", resume_text="cv")
    assert result.summary == "Backend dev."
    assert result.key_skills == [f"s{i}" for i in range(8)]


async def test_summarize_resume_retries_once_then_errors() -> None:
    with patch("app.ai.service.AsyncOpenAI", _fake_openai(None, None)):
        with pytest.raises(AppError) as exc:
            await summarize_resume(api_key="k", model="gpt-4o-mini", resume_text="cv")
    assert exc.value.code == "invalid_ai_response"


async def test_analyze_retries_when_a_resume_was_skipped() -> None:
    skipped = _response(resume_checks=[_check("p2", same_role=False, fit=0.1)])
    fake = _fake_openai(skipped, _response())
    with patch("app.ai.service.AsyncOpenAI", fake):
        outcome = await analyze_job_description(
            api_key="k", model="gpt-4o-mini", job_description=PYTHON_JD, profiles=PROFILES
        )
    assert outcome.result.recommended_profile_id == "p1"
    assert outcome.result.confidence == 0.9
    assert outcome.result.jd_summary == "Senior backend role building Python APIs."
    assert fake.return_value.chat.completions.parse.await_count == 2


async def test_analyze_allows_dismatched_jd() -> None:
    all_other_roles = _response(
        resume_checks=[
            _check("p1", same_role=False, fit=0.2),
            _check("p2", same_role=False, fit=0.1),
        ]
    )
    with patch("app.ai.service.AsyncOpenAI", _fake_openai(all_other_roles)):
        outcome = await analyze_job_description(
            api_key="k", model="gpt-4o-mini", job_description=PYTHON_JD, profiles=PROFILES
        )
    assert outcome.result.recommended_profile_id is None


def test_old_saved_result_omits_new_fields() -> None:
    def out(result: dict) -> dict:
        return AnalysisOut(
            id=uuid4(),
            client_id=uuid4(),
            created_by=uuid4(),
            created_by_name="x",
            company_name="c",
            position_name="p",
            job_description="jd",
            job_link=None,
            recommended_profile_id=None,
            selected_profile_id=None,
            result=result,
            model="m",
            prompt_version="v",
            tokens=None,
            latency_ms=None,
            record_status=RecordStatus.SKIPPED,
            record_attempts=0,
            record_error=None,
            created_at=datetime.now(UTC),
        ).model_dump(mode="json")["result"]

    old_row = AnalysisResult(
        main_backend_skill="Java", seniority="senior", confidence=0.7, reasoning="r"
    ).model_dump(exclude={"jd_summary", "role_type"})
    assert "jd_summary" not in out(old_row)
    new_row = AnalysisResult(
        jd_summary="Summary.",
        main_backend_skill="Java",
        seniority="senior",
        confidence=0.7,
        reasoning="r",
    ).model_dump()
    assert out(new_row)["jd_summary"] == "Summary."
