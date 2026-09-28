from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jd_analyzer"
    jwt_secret: str = "change-me-in-production"
    encryption_key: str = ""
    admin_username: str = "Admin"
    admin_password: str = "changeme"
    default_ai_model: str = "gpt-4o-mini"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        # Deployed = the frontend is served over https from a real host.
        return self.frontend_url.startswith("https://") and "localhost" not in self.frontend_url

    def check_production_secrets(self) -> None:
        """Refuses to run a deployed API on development defaults."""
        if not self.is_production:
            return
        problems = []
        if self.jwt_secret == "change-me-in-production" or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random string of 32+ characters")
        if not self.encryption_key:
            problems.append("ENCRYPTION_KEY is missing")
        if problems:
            raise RuntimeError("Unsafe production config: " + "; ".join(problems))


settings = Settings()
settings.check_production_secrets()
