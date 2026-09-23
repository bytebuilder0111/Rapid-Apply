from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.schemas import AnalysisResult
from app.analysis.models import RecordStatus


class AnalyzeRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1)
    job_link: str | None = None


class AnalyzeResponse(BaseModel):
    result: AnalysisResult
    model: str
    prompt_version: str
    tokens: int | None
    latency_ms: int
    duplicate_warning: bool
    duplicate_reason: str | None = None


class SaveAnalysisRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1)
    job_link: str | None = None
    selected_profile_id: UUID | None = None
    result: AnalysisResult
    model: str
    prompt_version: str
    tokens: int | None = None
    latency_ms: int | None = None


class AnalysisOut(BaseModel):
    id: UUID
    client_id: UUID
    created_by: UUID
    created_by_name: str
    company_name: str
    position_name: str
    job_description: str
    job_link: str | None
    recommended_profile_id: UUID | None
    selected_profile_id: UUID | None
    result: AnalysisResult
    model: str
    prompt_version: str
    tokens: int | None
    latency_ms: int | None
    record_status: RecordStatus
    record_attempts: int
    record_error: str | None
    created_at: datetime
