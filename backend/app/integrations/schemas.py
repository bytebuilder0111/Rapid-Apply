from pydantic import BaseModel, Field


class OpenAiSettingsOut(BaseModel):
    has_key: bool
    masked_key: str | None
    model: str


class SaveApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)
    model: str | None = None


class GoogleAuthorizeUrlOut(BaseModel):
    authorize_url: str


class GoogleConnectionOut(BaseModel):
    connected: bool
    email: str | None = None
    status: str | None = None
