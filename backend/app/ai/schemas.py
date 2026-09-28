from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal["intern", "junior", "mid", "senior", "lead", "unknown"]
RoleType = Literal["backend", "fullstack", "mobile", "frontend", "data", "devops", "other"]
WorkArrangement = Literal["remote", "hybrid", "onsite", "unknown"]
# Where a remote role may be worked from: "us" (US, or regions that include it such as
# North America), "worldwide", "non_us" (only other countries/regions), or "unknown".
RemoteLocation = Literal["us", "worldwide", "non_us", "unknown"]


class ResumeSummary(BaseModel):
    summary: str
    key_skills: list[str]


class AnalysisResult(BaseModel):
    """Stored as-is (JSONB) on each analysis. New fields default to None so analyses saved
    by earlier prompt versions still validate."""

    jd_summary: str | None = None
    role_type: RoleType | None = None
    work_arrangement: WorkArrangement | None = None
    remote_location: RemoteLocation | None = None
    relocation_required: bool | None = None
    # Short quote of the JD's location wording, e.g. "Remote (US)" or "Hybrid, 3 days in NYC".
    location_note: str | None = None
    # Set when the job is skipped for seniority or location rules (see app/ai/evidence.py).
    skip_reason: str | None = None
    # Languages/frameworks the JD explicitly names, verified against the JD text in
    # app/ai/service.py. None on analyses saved before this field existed.
    jd_core_stack: list[str] | None = None
    main_backend_skill: str
    backend_framework: str | None = None
    secondary_skills: list[str] = Field(default_factory=list)
    seniority: Seniority
    key_requirements: list[str] = Field(default_factory=list)
    # The best-fitting resume type's id, or None for a "Dismatched JD".
    recommended_resume_type_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class ResumeCheck(BaseModel):
    resume_id: str
    matching_technologies: list[str]
    same_role: bool
    fit: float = Field(ge=0, le=1)
    note: str


class AnalysisResponse(BaseModel):
    """What OpenAI must return. Structured output is generated in field order, so the model
    reads the JD first, then writes a check for every resume. It doesn't pick the winner:
    app/ai/evidence.py does, from these checks plus text evidence."""

    jd_summary: str
    role_type: RoleType
    work_arrangement: WorkArrangement
    remote_location: RemoteLocation
    relocation_required: bool
    location_note: str
    jd_core_stack: list[str]
    main_backend_skill: str
    backend_framework: str | None
    secondary_skills: list[str]
    seniority: Seniority
    key_requirements: list[str]
    resume_checks: list[ResumeCheck]
