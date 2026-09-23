from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal["junior", "mid", "senior", "lead", "unknown"]


class AnalysisResult(BaseModel):
    main_backend_skill: str
    backend_framework: str | None = None
    secondary_skills: list[str] = Field(default_factory=list)
    seniority: Seniority
    key_requirements: list[str] = Field(default_factory=list)
    recommended_profile_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reasoning: str
