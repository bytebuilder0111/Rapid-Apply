from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jd_analyzer"
    jwt_secret: str = "change-me-in-production"
    encryption_key: str = ""
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme"
    default_ai_model: str = "gpt-4o-mini"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"


settings = Settings()
