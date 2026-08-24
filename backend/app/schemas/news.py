"""API models for AI News. camelCase on the wire, like every other JobsVsAI schema."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.occupation import ApiModel

ImpactLevel = Literal["low", "medium", "high"]
ArticleStatus = Literal["draft", "review_required", "published", "rejected", "archived"]


class ArticleSource(ApiModel):
    """Attribution for a public page. Carries the link out, never the source body."""

    source_name: str
    source_url: str
    original_title: str
    source_published_at: datetime | None = None
    is_primary: bool = False


IngestStatus = Literal["new", "duplicate", "ignored", "candidate", "processed"]


class IngestItem(ApiModel):
    """An incoming feed candidate. Internal only — there is no public route serving this."""

    id: int
    source_id: int
    source_name: str
    trust_tier: int
    external_url: str
    canonical_url: str
    original_title: str
    original_excerpt: str | None = None
    source_published_at: datetime | None = None
    fetched_at: datetime
    status: IngestStatus
    relevance_score: int | None = None
    relevance_policy_version: str | None = None
    relevance_signals: dict = Field(default_factory=dict)
    feed_categories: list[str] = Field(default_factory=list)
    duplicate_of_ingest_item_id: int | None = None
    near_duplicate_similarity: float | None = None

    # Phase 3 semantic verdict. NULL means not yet assessed, which is distinct from false.
    is_ai_news: bool | None = None
    ai_relevance_confidence: float | None = None
    ai_relevance_reason: str | None = None
    semantic_policy_version: str | None = None
    generation_provider: str | None = None
    generation_model: str | None = None
    generation_prompt_version: str | None = None
    generation_attempted_at: datetime | None = None
    generation_attempts: int = 0
    generation_error: str | None = None
    generation_input_tokens: int | None = None
    generation_output_tokens: int | None = None


class IngestStatusInput(ApiModel):
    """Editorial triage. `processed` is deliberately absent: conversion sets it, not opinion."""

    status: Literal["candidate", "ignored", "new"]


class NewsSitemapEntry(ApiModel):
    """Slug and dates for sitemap generation. Typed so it emits camelCase like the rest."""

    slug: str
    published_at: datetime | None = None
    updated_at: datetime


class NewsArticleSummary(ApiModel):
    """A card in the /news list. No impact_score: internal for V1."""

    slug: str
    headline: str
    what_happened: str
    impact_level: ImpactLevel
    published_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    job_areas: list[str] = Field(default_factory=list)
    primary_source: ArticleSource | None = None


class NewsArticleDetail(NewsArticleSummary):
    why_it_matters_for_jobs: str
    sources: list[ArticleSource] = Field(default_factory=list)


class AdminNewsArticle(ApiModel):
    """The full internal record. Includes everything the public models withhold."""

    id: int
    slug: str
    headline: str
    what_happened: str
    why_it_matters_for_jobs: str
    status: ArticleStatus

    impact_score: float | None = None
    impact_level: ImpactLevel | None = None
    impact_confidence: float | None = None
    impact_reasoning: str | None = None
    impact_policy_version: str | None = None

    capability_advancement: int | None = None
    commercial_deployability: int | None = None
    breadth_of_affected_work: int | None = None
    adoption_speed: int | None = None
    human_work_reduction_potential: int | None = None

    automated_impact_score: float | None = None
    automated_impact_level: ImpactLevel | None = None

    generation_provider: str | None = None
    generation_model: str | None = None
    generation_prompt_version: str | None = None
    generated_at: datetime | None = None

    impact_assessed_at: datetime | None = None
    impact_assessed_by: str | None = None
    impact_overridden_at: datetime | None = None
    impact_overridden_by: str | None = None
    impact_override_reason: str | None = None

    published_at: datetime | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    regenerated_at: datetime | None = None
    regeneration_count: int = 0
    created_at: datetime
    updated_at: datetime

    tags: list[str] = Field(default_factory=list)
    job_areas: list[str] = Field(default_factory=list)
    sources: list[ArticleSource] = Field(default_factory=list)


class ArticleDraftInput(ApiModel):
    """Manual creation and editing. Impact is set separately, never inferred from prose."""

    headline: str = Field(min_length=1, max_length=300)
    what_happened: str = Field(min_length=1)
    why_it_matters_for_jobs: str = Field(min_length=1)
    slug: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)
    job_areas: list[str] = Field(default_factory=list)


class ImpactFactorsInput(ApiModel):
    """The five factors. The level is computed from them, never supplied."""

    capability_advancement: int = Field(ge=0, le=100)
    commercial_deployability: int = Field(ge=0, le=100)
    breadth_of_affected_work: int = Field(ge=0, le=100)
    adoption_speed: int = Field(ge=0, le=100)
    human_work_reduction_potential: int = Field(ge=0, le=100)
    impact_confidence: float = Field(ge=0.0, le=1.0)
    impact_reasoning: str = Field(min_length=1)


class ImpactOverrideInput(ApiModel):
    """An editor replacing the computed level. The automated values are never overwritten."""

    impact_level: ImpactLevel
    impact_reasoning: str | None = None
    reason: str | None = None


class ArchiveInput(ApiModel):
    """Optional context for retiring an article. The actor comes from auth, not the body."""

    reason: str | None = None


class ArticleSourceInput(ApiModel):
    ingest_item_id: int
    is_primary: bool = False


class ManualSourceInput(ApiModel):
    """Register a source by hand, for articles written without the ingestion pipeline."""

    source_name: str = Field(min_length=1, max_length=200)
    site_url: str = Field(min_length=1, max_length=500)
    external_url: str = Field(min_length=1, max_length=1000)
    original_title: str = Field(min_length=1, max_length=500)
    original_excerpt: str | None = None
    source_published_at: datetime | None = None
    source_type: Literal["primary", "secondary"] = "secondary"
    is_primary: bool = True
