from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Move Estimator API"
    environment: str = "development"

    supabase_url: str
    supabase_service_role_key: str

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5-5"

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()