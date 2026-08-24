"""Phase 3 orchestration: candidate -> provider -> news-impact-v1 -> draft.

The service depends on `NewsGenerationProvider`, never on Gemini. It owns the decisions the
provider must not make: whether an article is created, what status it gets, and what its
impact level is.

Three rules this module exists to enforce:

  1. **The model never decides publication.** Every article it produces is `draft` or
     `review_required`. There is no code path from here to `published`.
  2. **The model never sets the impact level.** It supplies five factors; `news-impact-v1`
     computes score and level from them.
  3. **One candidate, one article.** An ingest item that already has a linked article is
     skipped, so a retried job or a double-clicked admin button cannot produce duplicates.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.news import impact_policy
from app.news.generation import (
    MINIMUM_SEMANTIC_CONFIDENCE,
    PROMPT_VERSION,
    SEMANTIC_POLICY_VERSION,
    GeneratedBrief,
    GenerationInput,
    NewsGenerationProvider,
    ProviderNotConfigured,
    get_provider,
)
from app.repositories import news as article_repo
from app.repositories import news_ingest as ingest_repo


class DailyLimitReached(RuntimeError):
    """The configured daily generation cap has been hit."""


@dataclass
class GenerationCounters:
    candidates_selected: int = 0
    calls_made: int = 0
    accepted: int = 0
    rejected: int = 0
    failed: int = 0
    skipped_existing: int = 0
    articles_draft: int = 0
    articles_review_required: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


@dataclass
class ItemOutcome:
    ingest_item_id: int
    source_name: str
    original_title: str
    relevance_score: int | None
    outcome: str                      # accepted | rejected | failed | skipped
    is_ai_news: bool | None = None
    ai_relevance_confidence: float | None = None
    relevance_reason: str | None = None
    article_id: int | None = None
    article_status: str | None = None
    impact_score: float | None = None
    impact_level: str | None = None
    impact_confidence: float | None = None
    factors: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    error_kind: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class GenerationRunResult:
    run_id: int | None
    run_key: str
    status: str
    counters: GenerationCounters = field(default_factory=GenerationCounters)
    outcomes: list[ItemOutcome] = field(default_factory=list)
    skipped_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "runId": self.run_id, "runKey": self.run_key, "status": self.status,
            "skippedReason": self.skipped_reason,
            "counters": asdict(self.counters),
            "outcomes": [asdict(o) for o in self.outcomes],
        }


def resolve_provider() -> NewsGenerationProvider:
    """Build the configured provider. Gemini is constructed here and nowhere else."""
    settings = get_settings()
    name = (settings.news_llm_provider or "null").lower()
    if name == "gemini":
        from app.news.gemini import DEFAULT_MODEL, GeminiGenerationProvider

        return GeminiGenerationProvider(
            api_key=settings.news_llm_api_key,
            model=settings.news_llm_model or DEFAULT_MODEL,
            timeout_seconds=float(settings.news_llm_timeout_seconds),
        )
    return get_provider(name)


def decide_status(brief: GeneratedBrief) -> str:
    """Article status from the two confidences. Never `published`.

    Semantic confidence and impact confidence answer different questions — "is this really
    AI news" and "are these factor readings sound" — and either being weak is reason enough
    for a human to look before this goes anywhere.
    """
    if brief.ai_relevance_confidence < MINIMUM_SEMANTIC_CONFIDENCE:
        return "review_required"
    if impact_policy.requires_review(brief.impact_confidence):
        return "review_required"
    return "draft"


async def _todays_call_count(session: AsyncSession) -> int:
    """Generation calls already made today, counted from the items themselves.

    Counting attempts on the items rather than summing run rows means a crashed run cannot
    lose its spend, which is the failure mode that matters for a free tier.
    """
    return (await session.execute(text("""
      SELECT coalesce(sum(generation_attempts), 0) FROM news_ingest_items
      WHERE generation_attempted_at >= date_trunc('day', now())
    """))).scalar_one()


async def generate_for_candidate(
    session: AsyncSession,
    ingest_item_id: int,
    provider: NewsGenerationProvider,
    triggered_by: str = "manual",
) -> ItemOutcome:
    """Process one candidate. Commits its own work so a batch never loses earlier items."""
    # The gate lives here, not only in the batch runner. Every generation path — batch
    # run, admin single-item action, worker job — passes through this function, so checking
    # once here is what makes "generation disabled means no provider call" true rather than
    # merely intended. Checked before the item is even loaded.
    if not get_settings().generation_enabled:
        return ItemOutcome(
            ingest_item_id=ingest_item_id, source_name="", original_title="",
            relevance_score=None, outcome="skipped",
            error="NEWS_GENERATION_ENABLED is false",
        )

    item = await ingest_repo.get_ingest_item(session, ingest_item_id)
    if item is None:
        raise ValueError(f"Ingest item {ingest_item_id} does not exist")

    outcome = ItemOutcome(
        ingest_item_id=item["id"], source_name=item["source_name"],
        original_title=item["original_title"], relevance_score=item["relevance_score"],
        outcome="failed",
    )

    # Idempotency, checked before the call so a duplicate request costs no quota.
    existing = await ingest_repo.article_for_ingest_item(session, ingest_item_id)
    if existing is not None:
        outcome.outcome = "skipped"
        outcome.article_id = existing
        outcome.error = "An article already exists for this candidate"
        return outcome

    signals = item.get("relevance_signals") or {}
    matched = [t for key in ("aiTerms", "capabilityTerms", "workTerms")
               for t in (signals.get(key) or [])]

    payload = GenerationInput(
        source_title=item["original_title"],
        source_excerpt=item["original_excerpt"] or "",
        source_url=item["external_url"],
        source_name=item["source_name"],
        source_trust_tier=item["trust_tier"],
        source_published_at=(
            item["source_published_at"].isoformat() if item["source_published_at"] else None
        ),
        categories=list(item.get("feed_categories") or []),
        relevance_score=item["relevance_score"],
        relevance_signals=matched,
    )

    provider_name = getattr(provider, "name", "unknown")
    provider_model = getattr(provider, "model", "unknown")

    started = time.monotonic()
    try:
        brief = provider.generate_news_brief(payload)
    except Exception as exc:  # noqa: BLE001 - every provider failure is recorded, not raised
        # The candidate stays a candidate so it can be retried; only the attempt is recorded.
        latency_ms = int((time.monotonic() - started) * 1000)
        await ingest_repo.record_generation_failure(
            session, ingest_item_id, provider_name, provider_model, PROMPT_VERSION,
            str(exc)[:400], error_kind=getattr(exc, "kind", "unknown"), latency_ms=latency_ms,
        )
        await session.commit()
        outcome.error = str(exc)[:400]
        outcome.error_kind = getattr(exc, "kind", "unknown")
        outcome.latency_ms = latency_ms
        return outcome
    latency_ms = int((time.monotonic() - started) * 1000)
    outcome.latency_ms = latency_ms
    outcome.input_tokens = brief.input_tokens
    outcome.output_tokens = brief.output_tokens

    outcome.is_ai_news = brief.is_ai_news
    outcome.ai_relevance_confidence = brief.ai_relevance_confidence
    outcome.relevance_reason = brief.relevance_reason

    if not brief.is_ai_news:
        # No article. The verdict, its confidence and its reason are kept on the item — a
        # rejection is the most useful record there is for calibrating the prompt.
        await ingest_repo.record_semantic_rejection(
            session, ingest_item_id, brief, provider_name, provider_model, PROMPT_VERSION,
            latency_ms=latency_ms,
        )
        await session.commit()
        outcome.outcome = "rejected"
        return outcome

    assessment = impact_policy.assess(brief.factors)
    status = decide_status(brief)

    article_id = await article_repo.create_draft(session, {
        "headline": brief.headline,
        "what_happened": brief.what_happened,
        "why_it_matters_for_jobs": brief.why_it_matters_for_jobs,
        "tags": brief.tags,
        "job_areas": brief.job_areas,
    })
    await article_repo.link_ingest_item(session, article_id, ingest_item_id, is_primary=True)
    await article_repo.apply_impact(
        session, article_id,
        factors=brief.factors,
        confidence=brief.impact_confidence,
        reasoning=brief.impact_reasoning,
        assessed_by=f"{provider_name}:{provider_model}",
        provider=provider_name, model=provider_model, prompt_version=PROMPT_VERSION,
    )
    # apply_impact may already have moved the article to review on low impact confidence;
    # this settles the status for the semantic-confidence case too. It never sets published.
    await article_repo.set_status(session, article_id, status)
    await ingest_repo.record_semantic_acceptance(
        session, ingest_item_id, brief, provider_name, provider_model, PROMPT_VERSION,
        latency_ms=latency_ms,
    )
    await session.commit()

    outcome.outcome = "accepted"
    outcome.article_id = article_id
    outcome.article_status = status
    outcome.impact_score = float(assessment.score)
    outcome.impact_level = assessment.level
    outcome.impact_confidence = brief.impact_confidence
    outcome.factors = dict(brief.factors)
    return outcome


async def regenerate_article(
    session: AsyncSession,
    article_id: int,
    provider: NewsGenerationProvider,
    triggered_by: str = "manual",
) -> ItemOutcome:
    """Rewrite an existing article from its source candidate.

    Deliberately updates the existing row rather than creating a second one: the "one
    candidate, one article" rule is what stops a retried job or an impatient click from
    producing duplicates, and regeneration must not become the exception that breaks it.

    A published article is refused. Regenerating in place would silently change what readers
    are already being served, with no review step between the model's new output and the
    public page. Archive or unpublish it first — both are one click, and both make the change
    visible.
    """
    outcome = ItemOutcome(
        ingest_item_id=0, source_name="", original_title="",
        relevance_score=None, outcome="failed",
    )

    if not get_settings().generation_enabled:
        outcome.outcome = "skipped"
        outcome.error = "NEWS_GENERATION_ENABLED is false"
        return outcome

    article = (await session.execute(text(
        "SELECT id, status, headline FROM news_articles WHERE id = :id"
    ), {"id": article_id})).mappings().first()
    if article is None:
        raise ValueError(f"Article {article_id} does not exist")
    if article["status"] == "published":
        outcome.outcome = "skipped"
        outcome.error = (
            "Published articles cannot be regenerated. Archive or unpublish first, so the "
            "change is reviewed before readers see it."
        )
        return outcome

    candidates = await ingest_repo.ingest_items_for_article(session, article_id)
    if not candidates:
        outcome.outcome = "skipped"
        outcome.error = (
            "This article has no source candidate, so there is nothing to regenerate from. "
            "Hand-written articles are edited, not regenerated."
        )
        return outcome

    item = candidates[0]
    outcome.ingest_item_id = item["id"]
    outcome.source_name = item["source_name"]
    outcome.original_title = item["original_title"]
    outcome.relevance_score = item["relevance_score"]

    # The daily cap covers regeneration too: a regenerated brief costs a call like any other,
    # and exempting it would make the ceiling meaningless to anyone clicking the button.
    settings = get_settings()
    already = await _todays_call_count(session)
    if already >= settings.news_daily_generation_limit:
        outcome.outcome = "skipped"
        outcome.error = (
            f"Daily generation limit reached ({already}/{settings.news_daily_generation_limit})"
        )
        return outcome

    signals = item.get("relevance_signals") or {}
    matched = [t for key in ("aiTerms", "capabilityTerms", "workTerms")
               for t in (signals.get(key) or [])]
    payload = GenerationInput(
        source_title=item["original_title"],
        source_excerpt=item["original_excerpt"] or "",
        source_url=item["external_url"],
        source_name=item["source_name"],
        source_trust_tier=item["trust_tier"],
        source_published_at=(
            item["source_published_at"].isoformat() if item["source_published_at"] else None
        ),
        categories=list(item.get("feed_categories") or []),
        relevance_score=item["relevance_score"],
        relevance_signals=matched,
    )

    provider_name = getattr(provider, "name", "unknown")
    provider_model = getattr(provider, "model", "unknown")

    started = time.monotonic()
    try:
        brief = provider.generate_news_brief(payload)
    except Exception as exc:  # noqa: BLE001 - a failed regeneration leaves the article intact
        latency_ms = int((time.monotonic() - started) * 1000)
        await ingest_repo.record_generation_failure(
            session, item["id"], provider_name, provider_model, PROMPT_VERSION,
            str(exc)[:400], error_kind=getattr(exc, "kind", "unknown"), latency_ms=latency_ms,
        )
        await session.commit()
        outcome.error = str(exc)[:400]
        outcome.error_kind = getattr(exc, "kind", "unknown")
        outcome.latency_ms = latency_ms
        return outcome
    latency_ms = int((time.monotonic() - started) * 1000)
    outcome.latency_ms = latency_ms
    outcome.input_tokens = brief.input_tokens
    outcome.output_tokens = brief.output_tokens

    outcome.is_ai_news = brief.is_ai_news
    outcome.ai_relevance_confidence = brief.ai_relevance_confidence
    outcome.relevance_reason = brief.relevance_reason

    if not brief.is_ai_news:
        # The model changed its mind. The existing article is left exactly as it was and the
        # new verdict is reported — deleting an editor's article because a second call
        # disagreed would be the wrong call to make automatically.
        outcome.outcome = "rejected"
        outcome.article_id = article_id
        outcome.error = (
            "The provider now judges this not to be AI news. The article was left unchanged; "
            "archive or reject it if you agree."
        )
        return outcome

    assessment = impact_policy.assess(brief.factors)
    status = decide_status(brief)

    await article_repo.replace_generated_content(session, article_id, {
        "headline": brief.headline,
        "what_happened": brief.what_happened,
        "why_it_matters_for_jobs": brief.why_it_matters_for_jobs,
        "tags": brief.tags,
        "job_areas": brief.job_areas,
    })
    await article_repo.apply_impact(
        session, article_id,
        factors=brief.factors, confidence=brief.impact_confidence,
        reasoning=brief.impact_reasoning,
        assessed_by=f"{provider_name}:{provider_model}",
        provider=provider_name, model=provider_model, prompt_version=PROMPT_VERSION,
    )
    await article_repo.set_status(session, article_id, status)
    await ingest_repo.record_semantic_acceptance(
        session, item["id"], brief, provider_name, provider_model, PROMPT_VERSION,
        latency_ms=latency_ms,
    )
    await session.commit()

    outcome.outcome = "accepted"
    outcome.article_id = article_id
    outcome.article_status = status
    outcome.impact_score = float(assessment.score)
    outcome.impact_level = assessment.level
    outcome.impact_confidence = brief.impact_confidence
    outcome.factors = dict(brief.factors)
    return outcome


async def run_generation_batch(
    session: AsyncSession,
    triggered_by: str = "manual",
    provider: NewsGenerationProvider | None = None,
    batch_size: int | None = None,
    ingest_item_ids: list[int] | None = None,
) -> GenerationRunResult:
    """Generate for a batch of candidates, respecting the daily cap.

    `ingest_item_ids` lets a supervised run name exactly which candidates to process instead
    of taking the top of the queue.
    """
    settings = get_settings()
    run_key = f"news-generate-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"

    if not settings.generation_enabled:
        return GenerationRunResult(
            run_id=None, run_key=run_key, status="skipped",
            skipped_reason="NEWS_GENERATION_ENABLED is false",
        )

    try:
        provider = provider or resolve_provider()
    except ProviderNotConfigured as exc:
        return GenerationRunResult(
            run_id=None, run_key=run_key, status="skipped", skipped_reason=str(exc),
        )

    size = batch_size or settings.news_generation_batch_size
    daily_limit = settings.news_daily_generation_limit
    already = await _todays_call_count(session)
    remaining = max(0, daily_limit - already)
    if remaining == 0:
        return GenerationRunResult(
            run_id=None, run_key=run_key, status="skipped",
            skipped_reason=f"Daily generation limit reached ({already}/{daily_limit})",
        )

    if ingest_item_ids:
        candidates = ingest_item_ids[: min(size, remaining)]
    else:
        candidates = await ingest_repo.select_generation_candidates(
            session, min(size, remaining)
        )

    started = datetime.now(UTC)
    counters = GenerationCounters(candidates_selected=len(candidates))
    outcomes: list[ItemOutcome] = []
    errors: list[dict[str, str]] = []

    run_id = await ingest_repo.start_generation_run(session, {
        "run_key": run_key,
        "provider": getattr(provider, "name", "unknown"),
        "model": getattr(provider, "model", "unknown"),
        "prompt_version": PROMPT_VERSION,
        "impact_policy_version": impact_policy.POLICY_VERSION,
        "semantic_policy_version": SEMANTIC_POLICY_VERSION,
        "batch_size": size, "daily_limit": daily_limit, "triggered_by": triggered_by,
    })
    await session.commit()

    for item_id in candidates:
        outcome = await generate_for_candidate(session, item_id, provider, triggered_by)
        outcomes.append(outcome)
        if outcome.outcome == "skipped":
            counters.skipped_existing += 1
            continue
        counters.calls_made += 1
        if outcome.outcome == "accepted":
            counters.accepted += 1
            if outcome.article_status == "draft":
                counters.articles_draft += 1
            else:
                counters.articles_review_required += 1
        elif outcome.outcome == "rejected":
            counters.rejected += 1
        else:
            counters.failed += 1
            errors.append({"item": str(item_id), "error": (outcome.error or "")[:300]})

    counters.duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    tokens = await ingest_repo.token_totals_for_items(session, candidates)
    counters.input_tokens = tokens["input"]
    counters.output_tokens = tokens["output"]

    await ingest_repo.complete_generation_run(
        session, run_id, asdict(counters), json.dumps(errors),
        "completed" if counters.failed < max(1, counters.calls_made) else "failed",
    )
    await session.commit()

    return GenerationRunResult(
        run_id=run_id, run_key=run_key, status="completed",
        counters=counters, outcomes=outcomes,
    )
