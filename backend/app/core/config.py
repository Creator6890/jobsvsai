from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "JobsVsAI API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://jobsvsai:change-me@localhost:5432/jobsvsai"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    api_v1_prefix: str = "/api/v1"
    admin_username: str = "admin"
    admin_password: str = "change-me-too"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
