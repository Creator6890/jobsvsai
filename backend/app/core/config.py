from functools import lru_cache

from pydantic import field_validator
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

    # --- AI News. Ingestion and generation are controlled SEPARATELY.
    #
    # A single NEWS_ENABLED flag could not express the state Phase 4 needs: ingestion running
    # in production while generation stays off. Under one flag, turning ingestion on also
    # armed the admin Generate button against a live, billed API key.
    #
    # Both default to disabled. Enabling either is a deliberate operational act, not
    # something a fresh environment inherits.
    #
    # `news_enabled` is the LEGACY variable, retained only so an environment that still sets
    # it keeps behaving exactly as it did. Precedence, resolved by the properties below:
    #   1. an explicitly set new flag wins
    #   2. otherwise NEWS_ENABLED applies to both, preserving old behaviour exactly
    #   3. otherwise disabled
    # Optional types are what make "explicitly set" distinguishable from "left at default";
    # a plain `bool = False` could not tell the two apart.
    news_ingestion_enabled: bool | None = None
    news_generation_enabled: bool | None = None
    news_enabled: bool | None = None
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
    # Sized from the supervised live run of 2026-08-24, where the free tier sustained
    # roughly three calls before returning 429 and kept doing so after a 90s backoff. The
    # earlier 10/5 defaults were above what the tier actually delivered. Target volume is
    # 2-3 published stories a day, so a batch of 2 with a daily ceiling of 5 leaves room for
    # rejections without inviting a quota wall.
    news_daily_generation_limit: int = 5
    news_generation_batch_size: int = 2
    # Aliases for the same two limits under the operational names used in the automation
    # docs. Deliberately aliases, not new settings: two names for one cap is confusing, but
    # two independent settings for one cap is a bug waiting to happen — someone raises one
    # and the other silently still binds. The canonical fields above are what the code
    # reads; these only override them when explicitly set.
    news_max_generations_per_run: int | None = None
    news_max_generations_per_day: int | None = None
    news_llm_timeout_seconds: int = 90
    # Optional. Left unset by default so `metrics` reports tokens only — deriving a currency
    # figure from a guessed rate produces a number that looks authoritative and is not.
    news_llm_cost_per_1m_input: float | None = None
    news_llm_cost_per_1m_output: float | None = None
    # Must stay false. Generation produces draft or review_required, never published.
    news_auto_publish: bool = False

    # Every optional NEWS_* field, because compose passes each one as `${VAR:-}` and an
    # absent variable therefore arrives as an empty string rather than as an absent key.
    @field_validator("news_ingestion_enabled", "news_generation_enabled", "news_enabled",
                     "news_max_generations_per_run", "news_max_generations_per_day",
                     "news_llm_cost_per_1m_input", "news_llm_cost_per_1m_output",
                     mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        """Treat an empty string as "not set".

        Docker Compose interpolates an absent variable to an empty string — `${NEWS_ENABLED:-}`
        yields `NEWS_ENABLED=""`, not an absent key — and pydantic cannot parse that as a
        boolean. Without this the API refuses to start whenever the deprecated variable is
        merely passed through unset, which is the normal case.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def generations_per_run(self) -> int:
        """Candidates per generation run. NEWS_MAX_GENERATIONS_PER_RUN wins if set."""
        if self.news_max_generations_per_run is not None:
            return self.news_max_generations_per_run
        return self.news_generation_batch_size

    @property
    def generations_per_day(self) -> int:
        """Provider calls per day, counted across every run. Alias wins if set."""
        if self.news_max_generations_per_day is not None:
            return self.news_max_generations_per_day
        return self.news_daily_generation_limit

    @property
    def ingestion_enabled(self) -> bool:
        """Whether feed ingestion may run. Never read `news_enabled` directly."""
        if self.news_ingestion_enabled is not None:
            return self.news_ingestion_enabled
        return bool(self.news_enabled)

    @property
    def generation_enabled(self) -> bool:
        """Whether the language-model generation pipeline may run.

        Independent of ingestion: candidates can accumulate for review with no provider call
        ever being made, which is the state controlled production validation requires.
        """
        if self.news_generation_enabled is not None:
            return self.news_generation_enabled
        return bool(self.news_enabled)

    @property
    def uses_legacy_news_flag(self) -> bool:
        """True when behaviour is coming from NEWS_ENABLED rather than the split flags.

        Surfaced to admin so an operator can see that a deprecated variable is still in play
        rather than discovering it when the fallback is eventually removed.
        """
        return self.news_enabled is not None and (
            self.news_ingestion_enabled is None or self.news_generation_enabled is None
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
