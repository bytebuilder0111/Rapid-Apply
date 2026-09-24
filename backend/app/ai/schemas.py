from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal["junior", "mid", "senior", "lead", "unknown"]
RoleType = Literal["backend", "fullstack", "mobile", "frontend", "data", "devops", "other"]


class ResumeSummary(BaseModel):
    summary: str
    key_skills: list[str]


class AnalysisResult(BaseModel):
    """Stored as-is (JSONB) on each analysis. New fields default to None so analyses saved
    by earlier prompt versions still validate."""

    jd_summary: str | None = None
    role_type: RoleType | None = None
    main_backend_skill: str
    backend_framework: str | None = None
    secondary_skills: list[str] = Field(default_factory=list)
    seniority: Seniority
    key_requirements: list[str] = Field(default_factory=list)
    # The best-fitting resume (profile) id, or None for a "Dismatched JD".
    recommended_profile_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class AnalysisResponse(AnalysisResult):
    """What OpenAI must return. Structured output is generated in field order, so the model
    writes the JD summary and decides the role type before it picks a resume."""

    jd_summary: str
    role_type: RoleType
