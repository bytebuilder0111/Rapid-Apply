from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.ai.schemas import AnalysisResult
from app.analysis.models import RecordStatus


class AnalyzeRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1)
    job_link: str = Field(min_length=1, max_length=2048)
    # Whose resumes to compare against. Required for a client; a bidder always uses their
    # assigned profile, so it's ignored for them.
    profile_id: UUID | None = None


class DuplicateCheckRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    job_link: str = Field(min_length=1, max_length=2048)
    profile_id: UUID | None = None


class DuplicateCheckResponse(BaseModel):
    # Where the job was already applied to, e.g. "row 12 of Bids > Sheet1"; None if it's new.
    duplicate: str | None


class AnalyzeResponse(BaseModel):
    result: AnalysisResult
    model: str
    prompt_version: str
    tokens: int | None
    latency_ms: int


class SaveAnalysisRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1)
    job_link: str = Field(min_length=1, max_length=2048)
    profile_id: UUID | None = None
    selected_resume_type_id: UUID | None = None
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
    profile_id: UUID | None
    recommended_resume_type_id: UUID | None
    selected_resume_type_id: UUID | None
    result: AnalysisResult
    model: str
    prompt_version: str
    tokens: int | None
    latency_ms: int | None
    record_status: RecordStatus
    record_attempts: int
    record_error: str | None
    created_at: datetime

    @field_serializer("result")
    def _serialize_result(self, result: AnalysisResult) -> dict:
        # Rows saved before a field existed (e.g. jd_summary) omit it rather than reporting a
        # default, so the UI can tell an older analysis from a real empty value.
        return result.model_dump(exclude_unset=True)
