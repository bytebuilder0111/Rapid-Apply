from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

Seniority = Literal["junior", "mid", "senior", "lead", "unknown"]
RoleType = Literal["backend", "fullstack", "mobile", "frontend", "data", "devops", "other"]
# Profiles are backend resumes, so only these role types can match a profile stack.
MATCHABLE_ROLE_TYPES = {"backend", "fullstack"}


class AnalysisResult(BaseModel):
    # role_type comes first on purpose: structured output is generated in field order, so
    # the model commits to what kind of role this is before it picks a stack.
    role_type: RoleType | None = None
    # One of the client's profile tech stacks (exact string), or None if none fit the JD.
    # Both default to None so analyses saved before these fields existed still validate.
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
        role_type=(RoleType, ...),
        main_tech_stack=(stack_type, ...),
    )
