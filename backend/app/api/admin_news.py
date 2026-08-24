"""Admin AI News API.

Reuses `require_admin` from app.api.admin — the same HTTP Basic dependency every other
admin surface uses. No second authentication system.

Unlike the read-only admin console elsewhere, these routes mutate, so each one commits
explicitly and each write path runs through app.repositories.news rather than issuing SQL
of its own. Publication in particular has exactly one entry point, which runs the guard.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import require_admin
from app.core.config import get_settings
from app.db.session import get_session
from app.news.impact_policy import (
    FACTOR_LABELS,
    FACTOR_WEIGHTS,
    MINIMUM_PUBLISH_CONFIDENCE,
    POLICY_VERSION,
)
from app.news import generation, generation_service, ingestion, relevance
from app.repositories import news as repo
from app.repositories import news_ingest as ingest_repo
from app.schemas.news import (
    AdminNewsArticle,
    ArchiveInput,
    IngestItem,
    IngestStatusInput,
    ArticleDraftInput,
    ImpactFactorsInput,
    ImpactOverrideInput,
    ManualSourceInput,
)

# Router-level auth, matching app.api.admin. Individual routes additionally depend on
# require_admin only where they need the username for an audit column.
router = APIRouter(prefix="/admin/news", tags=["admin-news"],
                   dependencies=[Depends(require_admin)])


async def _load_or_404(session: AsyncSession, article_id: int) -> AdminNewsArticle:
    article = await repo.get_admin_article(session, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/policy")
async def impact_policy() -> dict[str, object]:
    """The active policy, so the admin UI never hard-codes weights of its own."""
    return {
        "policyVersion": POLICY_VERSION,
        "minimumPublishConfidence": float(MINIMUM_PUBLISH_CONFIDENCE),
        "factors": [
            {"key": key, "label": FACTOR_LABELS[key], "weight": float(weight)}
            for key, weight in FACTOR_WEIGHTS.items()
        ],
        "thresholds": {"low": "0-34", "medium": "35-69", "high": "70-100"},
    }


@router.get("", response_model=list[AdminNewsArticle], response_model_by_alias=True)
async def list_articles(
    article_status: str | None = Query(
        default=None, alias="status", pattern="^(draft|review_required|published|rejected)$"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AdminNewsArticle]:
    return await repo.list_admin_articles(session, article_status, limit, offset)


@router.get("/counts")
async def status_counts(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    return await repo.admin_status_counts(session)


# --------------------------------------------------------------------- incoming (Phase 2)
#
# Ingest items are internal triage material. There is no public router for them anywhere in
# the application, and no public schema that can serialise one.


@router.get("/incoming", response_model=list[IngestItem], response_model_by_alias=True)
async def list_incoming(
    item_status: str | None = Query(
        default=None, alias="status", pattern="^(new|candidate|ignored|duplicate|processed)$"
    ),
    source_id: int | None = Query(default=None, ge=1),
    since_hours: int | None = Query(default=None, ge=1, le=720),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[IngestItem]:
    rows = await ingest_repo.list_ingest_items(
        session, item_status, source_id, since_hours, limit, offset
    )
    return [IngestItem(**row) for row in rows]


@router.get("/incoming/counts")
async def incoming_counts(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    return {
        "statuses": await ingest_repo.ingest_status_counts(session),
        "relevancePolicyVersion": relevance.POLICY_VERSION,
        "candidateThreshold": relevance.CANDIDATE_THRESHOLD,
        "confidentThreshold": relevance.CONFIDENT_THRESHOLD,
        "runs": await ingest_repo.latest_runs(session, limit=5),
    }


@router.get("/incoming/{item_id}", response_model=IngestItem, response_model_by_alias=True)
async def get_incoming(item_id: int, session: AsyncSession = Depends(get_session)) -> IngestItem:
    row = await ingest_repo.get_ingest_item(session, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    return IngestItem(**row)


@router.post("/incoming/{item_id}/status", response_model=IngestItem,
             response_model_by_alias=True)
async def set_incoming_status(
    item_id: int, payload: IngestStatusInput, session: AsyncSession = Depends(get_session)
) -> IngestItem:
    """Editorial triage: ignore, or restore to candidate.

    `processed` is not settable here — an item becomes processed by being converted into an
    article, never by an opinion about it.
    """
    if await ingest_repo.get_ingest_item(session, item_id) is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    try:
        await ingest_repo.set_ingest_status(session, item_id, payload.status)
    except ValueError as error:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    await session.commit()
    return await get_incoming(item_id, session)


@router.post("/incoming/{item_id}/draft", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def draft_from_incoming(
    item_id: int, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    """Create an empty draft carrying the candidate's provenance.

    Phase 2 explicitly does not write prose. The draft is created with placeholder headline
    text and the source already attached, so the editor supplies the brief and the impact
    assessment by hand. Nothing here generates, scores or publishes.

    The ingest item becomes `processed`: it has been converted, which is the one meaning
    that status carries.
    """
    item = await ingest_repo.get_ingest_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")

    article_id = await repo.create_draft(session, {
        # The source's own title seeds the slug so the draft is findable, and is replaced by
        # the editor's headline. It is never published as JobsVsAI prose.
        "headline": item["original_title"],
        "what_happened": "",
        "why_it_matters_for_jobs": "",
        "tags": [],
        "job_areas": [],
    })
    await repo.link_ingest_item(session, article_id, item_id, is_primary=True)
    await ingest_repo.mark_processed(session, item_id)
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/ingest/run")
async def trigger_ingestion(
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> dict[str, object]:
    """Run ingestion now. Returns `skipped` rather than failing when ingestion is off."""
    result = await ingestion.run_ingestion(session, triggered_by=f"admin:{admin}")
    return result.as_dict()


@router.get("/generation/status")
async def generation_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """What the generator is configured to do, and what it has done lately.

    Reports whether a provider is configured without ever reading the key back: only its
    presence is exposed.
    """
    settings = get_settings()
    return {
        # Reported separately so an operator can see the exact gating state, including
        # whether the deprecated single flag is still supplying it.
        "ingestionEnabled": settings.ingestion_enabled,
        "generationEnabled": settings.generation_enabled,
        "usesLegacyNewsFlag": settings.uses_legacy_news_flag,
        "provider": settings.news_llm_provider,
        "model": settings.news_llm_model or None,
        "apiKeyConfigured": bool(settings.news_llm_api_key),
        "autoPublish": settings.news_auto_publish,
        "dailyLimit": settings.news_daily_generation_limit,
        "batchSize": settings.news_generation_batch_size,
        "promptVersion": generation.PROMPT_VERSION,
        "semanticPolicyVersion": generation.SEMANTIC_POLICY_VERSION,
        "minimumSemanticConfidence": generation.MINIMUM_SEMANTIC_CONFIDENCE,
        "runs": await ingest_repo.latest_generation_runs(session, limit=5),
    }


@router.post("/incoming/{item_id}/generate")
async def generate_from_incoming(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> dict[str, object]:
    """Generate one article from one candidate. The admin's 'Generate with AI' action.

    Returns the outcome rather than raising on a provider failure: a failed generation is a
    normal, retryable state, and the candidate is left untouched so it can be tried again.
    """
    if await ingest_repo.get_ingest_item(session, item_id) is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    settings = get_settings()
    if not settings.generation_enabled:
        return {"status": "skipped", "reason": "NEWS_GENERATION_ENABLED is false"}
    try:
        provider = generation_service.resolve_provider()
    except generation.ProviderNotConfigured as exc:
        return {"status": "skipped", "reason": str(exc)}

    outcome = await generation_service.generate_for_candidate(
        session, item_id, provider, triggered_by=f"admin:{admin}"
    )
    return {"status": outcome.outcome, "outcome": outcome.__dict__}


@router.post("/generation/batch")
async def generate_batch(
    batch_size: int | None = Query(default=None, ge=1, le=25),
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> dict[str, object]:
    """Run one generation batch now. Respects the daily cap and the batch size."""
    result = await generation_service.run_generation_batch(
        session, triggered_by=f"admin:{admin}", batch_size=batch_size
    )
    return result.as_dict()


@router.get("/{article_id}", response_model=AdminNewsArticle, response_model_by_alias=True)
async def get_article(article_id: int, session: AsyncSession = Depends(get_session)) -> AdminNewsArticle:
    return await _load_or_404(session, article_id)


@router.get("/{article_id}/candidates", response_model=list[IngestItem],
            response_model_by_alias=True)
async def article_candidates(
    article_id: int, session: AsyncSession = Depends(get_session)
) -> list[IngestItem]:
    """The source candidates behind an article, with their semantic verdicts.

    Admin-only, like every ingest read. Lets the editor check the generated brief against the
    feed material rather than taking it on trust.
    """
    await _load_or_404(session, article_id)
    rows = await ingest_repo.ingest_items_for_article(session, article_id)
    return [IngestItem(**row) for row in rows]


@router.post("", response_model=AdminNewsArticle, response_model_by_alias=True,
             status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: ArticleDraftInput, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    """Manual creation. No generation record is required — an editor can write a brief."""
    article_id = await repo.create_draft(session, payload.model_dump())
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}", response_model=AdminNewsArticle, response_model_by_alias=True)
async def update_article(
    article_id: int, payload: ArticleDraftInput, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    await _load_or_404(session, article_id)
    await repo.update_draft(session, article_id, payload.model_dump())
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/source", response_model=AdminNewsArticle, response_model_by_alias=True)
async def add_source(
    article_id: int, payload: ManualSourceInput, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    await _load_or_404(session, article_id)
    await repo.attach_manual_source(session, article_id, payload.model_dump())
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/impact", response_model=AdminNewsArticle, response_model_by_alias=True)
async def set_impact(
    article_id: int,
    payload: ImpactFactorsInput,
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> AdminNewsArticle:
    """Supply the five factors; news-impact-v1 computes score and level.

    The caller cannot pass a level. Confidence below the policy minimum moves the article
    to review_required rather than leaving it publishable.
    """
    await _load_or_404(session, article_id)
    await repo.apply_impact(
        session, article_id,
        factors=payload.model_dump(),
        confidence=payload.impact_confidence,
        reasoning=payload.impact_reasoning,
        assessed_by=f"admin:{admin}",
    )
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/impact/override", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def override_impact(
    article_id: int,
    payload: ImpactOverrideInput,
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> AdminNewsArticle:
    """Editorial override. The automated score and level are preserved untouched."""
    await _load_or_404(session, article_id)
    await repo.override_impact(
        session, article_id, payload.impact_level,
        overridden_by=f"admin:{admin}",
        reasoning=payload.impact_reasoning, reason=payload.reason,
    )
    await session.commit()
    return await _load_or_404(session, article_id)


@router.get("/{article_id}/publication-check")
async def publication_check(
    article_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    """What still blocks publication. Lets the editor see the whole list before trying."""
    await _load_or_404(session, article_id)
    blockers = await repo.publication_blockers(session, article_id)
    return {"publishable": not blockers, "blockers": blockers}


@router.post("/{article_id}/publish", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def publish_article(
    article_id: int, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    await _load_or_404(session, article_id)
    try:
        await repo.publish(session, article_id)
    except repo.NewsPublicationRefused as refusal:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(refusal)) from refusal
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/archive", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def archive_article(
    article_id: int,
    payload: ArchiveInput | None = None,
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> AdminNewsArticle:
    """Retire an article. Preserves `published_at`; rejecting does not.

    An archived article is no longer public — the reader predicate admits only `published` —
    so no separate unpublish step is required.
    """
    await _load_or_404(session, article_id)
    await repo.archive(session, article_id, archived_by=f"admin:{admin}",
                       reason=payload.reason if payload else None)
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/restore", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def restore_article(
    article_id: int, session: AsyncSession = Depends(get_session)
) -> AdminNewsArticle:
    """Bring an archived article back to review — never straight back to public."""
    await _load_or_404(session, article_id)
    await repo.restore_from_archive(session, article_id)
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/regenerate")
async def regenerate(
    article_id: int,
    session: AsyncSession = Depends(get_session),
    admin: str = Depends(require_admin),
) -> dict[str, object]:
    """Rewrite the brief from its source candidate, in place.

    Returns the outcome rather than raising on a provider failure: a failed regeneration is a
    normal, retryable state and the existing article is left untouched.
    """
    await _load_or_404(session, article_id)
    settings = get_settings()
    if not settings.generation_enabled:
        return {"status": "skipped", "reason": "NEWS_GENERATION_ENABLED is false"}
    try:
        provider = generation_service.resolve_provider()
    except generation.ProviderNotConfigured as exc:
        return {"status": "skipped", "reason": str(exc)}

    outcome = await generation_service.regenerate_article(
        session, article_id, provider, triggered_by=f"admin:{admin}"
    )
    return {"status": outcome.outcome, "outcome": outcome.__dict__}


@router.post("/{article_id}/reject", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def reject_article(article_id: int, session: AsyncSession = Depends(get_session)) -> AdminNewsArticle:
    await _load_or_404(session, article_id)
    await repo.set_status(session, article_id, "rejected")
    await session.commit()
    return await _load_or_404(session, article_id)


@router.post("/{article_id}/unpublish", response_model=AdminNewsArticle,
             response_model_by_alias=True)
async def unpublish_article(article_id: int, session: AsyncSession = Depends(get_session)) -> AdminNewsArticle:
    """Pull a published article back to review. The reverse of publish, deliberately kept."""
    await _load_or_404(session, article_id)
    await repo.set_status(session, article_id, "review_required")
    await session.commit()
    return await _load_or_404(session, article_id)
