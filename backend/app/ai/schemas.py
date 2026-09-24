from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

Seniority = Literal["junior", "mid", "senior", "lead", "unknown"]


class AnalysisResult(BaseModel):
    # One of the client's profile tech stacks (exact string), or None if none fit the JD.
    # Defaults to None so analyses saved before this field existed still validate.
    main_tech_stack: str | None = None
    main_backend_skill: str
    backend_framework: str | None = None
    secondary_skills: list[str] = Field(default_factory=list)
    seniority: Seniority
    key_requirements: list[str] = Field(default_factory=list)
    recommended_profile_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reasoning: str


def response_model_for(allowed_stacks: list[str]) -> type[AnalysisResult]:
    """AnalysisResult with main_tech_stack narrowed to an enum of allowed_stacks, so OpenAI's
    structured output can only ever pick a stack that exists in the client's profiles."""
    stack_type: Any = Literal[tuple(allowed_stacks)] | None if allowed_stacks else None
    return create_model(
        "AnalysisResponse",
        __base__=AnalysisResult,
        main_tech_stack=(stack_type, ...),
    )
