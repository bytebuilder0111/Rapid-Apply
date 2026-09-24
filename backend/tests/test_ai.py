import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from app.ai.prompts import allowed_stacks_from, build_user_prompt
from app.ai.schemas import AnalysisResult, response_model_for
from app.ai.service import reconcile_with_stack

PROFILES = [
    {"id": "p1", "name": "Python dev", "tech_stacks": ["Python/Django", "Go"]},
    {"id": "p2", "name": "Node dev", "tech_stacks": ["Node.js/NestJS", "Go"]},
]


def _result(**overrides) -> AnalysisResult:
    base = {
        "main_tech_stack": "Node.js/NestJS",
        "main_backend_skill": "Node.js",
        "seniority": "senior",
        "recommended_profile_id": "p2",
        "confidence": 0.8,
        "reasoning": "r",
    }
    return AnalysisResult(**(base | overrides))


def test_allowed_stacks_are_deduplicated_in_order() -> None:
    assert allowed_stacks_from(PROFILES) == ["Python/Django", "Go", "Node.js/NestJS"]


def test_prompt_lists_allowed_stacks() -> None:
    prompt = build_user_prompt("JD text", PROFILES)
    assert "Allowed tech stacks:\n- Python/Django\n- Go\n- Node.js/NestJS" in prompt


def test_response_model_restricts_stack_to_profile_list() -> None:
    model = response_model_for(["Python/Django", "Go"])
    base = _result().model_dump()

    assert model.model_validate(base | {"main_tech_stack": "Go"}).main_tech_stack == "Go"
    assert model.model_validate(base | {"main_tech_stack": None}).main_tech_stack is None
    with pytest.raises(ValidationError):
        model.model_validate(base | {"main_tech_stack": "Rust"})


def test_response_model_is_valid_openai_strict_schema() -> None:
    schema = to_strict_json_schema(response_model_for(["Python/Django", "Go"]))
    stack_schema = schema["properties"]["main_tech_stack"]
    enums = [opt.get("enum") for opt in stack_schema.get("anyOf", [stack_schema])]
    assert ["Python/Django", "Go"] in enums
    assert "main_tech_stack" in schema["required"]


def test_response_model_without_profiles_forces_null_stack() -> None:
    schema = to_strict_json_schema(response_model_for([]))
    assert schema["properties"]["main_tech_stack"]["type"] == "null"


def test_old_saved_result_omits_main_tech_stack() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.analysis.models import RecordStatus
    from app.analysis.schemas import AnalysisOut

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

    old_row = _result().model_dump(exclude={"main_tech_stack"})
    assert "main_tech_stack" not in out(old_row)
    assert out(_result(main_tech_stack=None).model_dump())["main_tech_stack"] is None


def test_reconcile_keeps_consistent_recommendation() -> None:
    result = _result()
    assert reconcile_with_stack(result, PROFILES).recommended_profile_id == "p2"


def test_reconcile_swaps_profile_that_lacks_the_stack() -> None:
    result = _result(recommended_profile_id="p1")
    assert reconcile_with_stack(result, PROFILES).recommended_profile_id == "p2"


def test_reconcile_leaves_null_stack_alone() -> None:
    result = _result(main_tech_stack=None, recommended_profile_id="p1")
    assert reconcile_with_stack(result, PROFILES).recommended_profile_id == "p1"
