from pydantic import BaseModel, Field


class OpenAiSettingsOut(BaseModel):
    has_key: bool
    masked_key: str | None
    model: str


class SaveApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)
    model: str | None = None
