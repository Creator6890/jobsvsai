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

    # --- AI News ingestion (Phase 2). Disabled by default: enabling ingestion is a
    # deliberate operational act, not something a fresh environment inherits.
    news_enabled: bool = False
    news_fetch_interval_minutes: int = 120
    # First-run protection. Feeds carry years of history — the OpenAI feed alone holds well
    # over a thousand entries — so a run only considers entries published inside this
    # window. Without it, the first production run would ingest the entire archive.
    news_lookback_hours: int = 48
    news_max_entries_per_feed: int = 40
    # Ceiling on candidates promoted per run, so an unusually busy day cannot flood the
    # editorial queue. Excess items are still stored, just left as `new` for the next run.
    news_max_candidates_per_run: int = 60
    # Phase 3 knobs, inert until a provider exists. Declared here so configuration does not
    # have to move when one is added.
    news_llm_provider: str = "null"
    news_llm_api_key: str = ""
    news_llm_model: str = ""
    news_daily_generation_limit: int = 10
    news_generation_batch_size: int = 5
    news_llm_timeout_seconds: int = 45
    # Must stay false. Generation produces draft or review_required, never published.
    news_auto_publish: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
