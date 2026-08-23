"""Data access for AI News, and the single publication gate for it.

Mirrors `publication.py`'s discipline for occupations: one predicate decides what the
public may see, and every public read composes it rather than writing its own WHERE. A
second, divergent definition of "published" is how draft content reaches the internet.

Nothing here touches occupations, production snapshots, publications or scoring models.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.impact_policy import POLICY_VERSION, assess, requires_review
from app.news.pipeline import canonicalise_url, content_hash
from app.schemas.news import (
    AdminNewsArticle,
    ArticleSource,
    NewsArticleDetail,
    NewsArticleSummary,
)

# The only definition of publicly visible. `published_at IS NOT NULL` is redundant with the
# table CHECK but stated anyway: a public read should not depend on a constraint elsewhere
# staying correct.
PUBLIC_ARTICLE_PREDICATE = "article.status = 'published' AND article.published_at IS NOT NULL"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class NewsPublicationRefused(ValueError):
    """Publication was attempted on an article that does not satisfy the guard."""


def slugify(value: str) -> str:
    """Deterministic, ASCII, hyphenated. Same shape as occupation slugs."""
    lowered = value.lower().replace("&", " and ")
    return _SLUG_STRIP.sub("-", lowered).strip("-")[:200] or "untitled"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    """Append a counter rather than failing: an editor should not have to invent a slug."""
    candidate = base
    for suffix in range(2, 100):
        exists = (await session.execute(
            text("SELECT 1 FROM news_articles WHERE slug = :slug"), {"slug": candidate}
        )).scalar_one_or_none()
        if exists is None:
            return candidate
        candidate = f"{base}-{suffix}"
    raise ValueError(f"Could not derive a unique slug from {base!r}")


# --------------------------------------------------------------------------- public reads

_PUBLIC_COLUMNS = """
  article.slug, article.headline, article.what_happened,
  article.why_it_matters_for_jobs, article.impact_level, article.published_at
"""


async def _decorate(session: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Attach tags, job areas and sources in three queries rather than N per article."""
    if not rows:
        return []
    slugs = [row["slug"] for row in rows]

    tags: dict[str, list[str]] = {slug: [] for slug in slugs}
    for record in (await session.execute(text("""
      SELECT a.slug, t.tag FROM news_article_tags t
      JOIN news_articles a ON a.id = t.article_id
      WHERE a.slug = ANY(:slugs) ORDER BY t.tag
    """), {"slugs": slugs})).mappings():
        tags[record["slug"]].append(record["tag"])

    areas: dict[str, list[str]] = {slug: [] for slug in slugs}
    for record in (await session.execute(text("""
      SELECT a.slug, j.job_area FROM news_article_job_areas j
      JOIN news_articles a ON a.id = j.article_id
      WHERE a.slug = ANY(:slugs) ORDER BY j.job_area
    """), {"slugs": slugs})).mappings():
        areas[record["slug"]].append(record["job_area"])

    sources: dict[str, list[dict]] = {slug: [] for slug in slugs}
    for record in (await session.execute(text("""
      SELECT a.slug, s.name AS source_name, i.external_url AS source_url,
             i.original_title, i.source_published_at, link.is_primary
      FROM news_article_sources link
      JOIN news_articles a ON a.id = link.article_id
      JOIN news_ingest_items i ON i.id = link.ingest_item_id
      JOIN news_sources s ON s.id = i.source_id
      WHERE a.slug = ANY(:slugs)
      ORDER BY link.is_primary DESC, s.name
    """), {"slugs": slugs})).mappings():
        sources[record["slug"]].append(dict(record))

    return [
        dict(row) | {
            "tags": tags[row["slug"]],
            "job_areas": areas[row["slug"]],
            "sources": sources[row["slug"]],
            "primary_source": next(
                (s for s in sources[row["slug"]] if s["is_primary"]),
                sources[row["slug"]][0] if sources[row["slug"]] else None,
            ),
        }
        for row in rows
    ]


async def list_public_articles(
    session: AsyncSession,
    impact_level: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[NewsArticleSummary]:
    rows = (await session.execute(text(f"""
      SELECT {_PUBLIC_COLUMNS}
      FROM news_articles article
      WHERE {PUBLIC_ARTICLE_PREDICATE}
        AND (CAST(:impact_level AS TEXT) IS NULL
             OR article.impact_level = CAST(:impact_level AS TEXT))
      ORDER BY article.published_at DESC, article.id DESC
      LIMIT :limit OFFSET :offset
    """), {"impact_level": impact_level, "limit": limit, "offset": offset})).mappings().all()
    return [NewsArticleSummary(**row) for row in await _decorate(session, rows)]


async def get_public_article(session: AsyncSession, slug: str) -> NewsArticleDetail | None:
    rows = (await session.execute(text(f"""
      SELECT {_PUBLIC_COLUMNS}
      FROM news_articles article
      WHERE {PUBLIC_ARTICLE_PREDICATE} AND article.slug = :slug
    """), {"slug": slug})).mappings().all()
    decorated = await _decorate(session, rows)
    return NewsArticleDetail(**decorated[0]) if decorated else None


async def list_public_slugs(session: AsyncSession) -> list[dict]:
    """For the sitemap. Published only, by construction."""
    return [dict(row) for row in (await session.execute(text(f"""
      SELECT article.slug, article.published_at, article.updated_at
      FROM news_articles article
      WHERE {PUBLIC_ARTICLE_PREDICATE}
      ORDER BY article.published_at DESC
    """))).mappings().all()]


# ---------------------------------------------------------------------------- admin reads

_ADMIN_COLUMNS = """
  article.id, article.slug, article.headline, article.what_happened,
  article.why_it_matters_for_jobs, article.status,
  article.impact_score, article.impact_level, article.impact_confidence,
  article.impact_reasoning, article.impact_policy_version,
  article.capability_advancement, article.commercial_deployability,
  article.breadth_of_affected_work, article.adoption_speed,
  article.human_work_reduction_potential,
  article.automated_impact_score, article.automated_impact_level,
  article.generation_provider, article.generation_model,
  article.generation_prompt_version, article.generated_at,
  article.impact_assessed_at, article.impact_assessed_by,
  article.impact_overridden_at, article.impact_overridden_by,
  article.impact_override_reason,
  article.published_at, article.created_at, article.updated_at
"""


async def list_admin_articles(
    session: AsyncSession, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[AdminNewsArticle]:
    rows = (await session.execute(text(f"""
      SELECT {_ADMIN_COLUMNS} FROM news_articles article
      WHERE (CAST(:status AS TEXT) IS NULL
             OR article.status = CAST(:status AS TEXT))
      ORDER BY article.created_at DESC, article.id DESC
      LIMIT :limit OFFSET :offset
    """), {"status": status, "limit": limit, "offset": offset})).mappings().all()
    return [AdminNewsArticle(**row) for row in await _decorate(session, rows)]


async def get_admin_article(session: AsyncSession, article_id: int) -> AdminNewsArticle | None:
    rows = (await session.execute(text(f"""
      SELECT {_ADMIN_COLUMNS} FROM news_articles article WHERE article.id = :id
    """), {"id": article_id})).mappings().all()
    decorated = await _decorate(session, rows)
    return AdminNewsArticle(**decorated[0]) if decorated else None


async def admin_status_counts(session: AsyncSession) -> dict[str, int]:
    rows = (await session.execute(
        text("SELECT status, count(*) AS total FROM news_articles GROUP BY status")
    )).mappings().all()
    counts = {"draft": 0, "review_required": 0, "published": 0, "rejected": 0}
    return counts | {row["status"]: row["total"] for row in rows}


# --------------------------------------------------------------------------- admin writes


async def create_draft(session: AsyncSession, payload: Mapping[str, Any]) -> int:
    slug = await _unique_slug(session, slugify(payload.get("slug") or payload["headline"]))
    article_id = (await session.execute(text("""
      INSERT INTO news_articles (slug, headline, what_happened, why_it_matters_for_jobs, status)
      VALUES (:slug, :headline, :what_happened, :why, 'draft')
      RETURNING id
    """), {
        "slug": slug, "headline": payload["headline"].strip(),
        "what_happened": payload["what_happened"].strip(),
        "why": payload["why_it_matters_for_jobs"].strip(),
    })).scalar_one()
    await replace_tags(session, article_id, payload.get("tags") or [])
    await replace_job_areas(session, article_id, payload.get("job_areas") or [])
    return article_id


async def update_draft(session: AsyncSession, article_id: int, payload: Mapping[str, Any]) -> None:
    await session.execute(text("""
      UPDATE news_articles
      SET headline = :headline, what_happened = :what_happened,
          why_it_matters_for_jobs = :why, updated_at = now()
      WHERE id = :id
    """), {
        "id": article_id, "headline": payload["headline"].strip(),
        "what_happened": payload["what_happened"].strip(),
        "why": payload["why_it_matters_for_jobs"].strip(),
    })
    await replace_tags(session, article_id, payload.get("tags") or [])
    await replace_job_areas(session, article_id, payload.get("job_areas") or [])


async def replace_tags(session: AsyncSession, article_id: int, tags: Sequence[str]) -> None:
    await session.execute(
        text("DELETE FROM news_article_tags WHERE article_id = :id"), {"id": article_id}
    )
    for tag in {t.strip() for t in tags if t and t.strip()}:
        await session.execute(text(
            "INSERT INTO news_article_tags (article_id, tag) VALUES (:id, :tag)"
        ), {"id": article_id, "tag": tag})


async def replace_job_areas(session: AsyncSession, article_id: int, areas: Sequence[str]) -> None:
    await session.execute(
        text("DELETE FROM news_article_job_areas WHERE article_id = :id"), {"id": article_id}
    )
    for area in {a.strip() for a in areas if a and a.strip()}:
        await session.execute(text(
            "INSERT INTO news_article_job_areas (article_id, job_area) VALUES (:id, :area)"
        ), {"id": article_id, "area": area})


async def attach_manual_source(
    session: AsyncSession, article_id: int, payload: Mapping[str, Any]
) -> int:
    """Register a source for a hand-written article.

    Creates the news_sources row on demand and stores the third-party title/excerpt in
    news_ingest_items, keeping source material in the same place the automated pipeline
    will put it. The article's own columns stay JobsVsAI-written.
    """
    source_id = (await session.execute(text("""
      INSERT INTO news_sources (name, site_url, source_type)
      VALUES (:name, :site_url, :source_type)
      ON CONFLICT (name) DO UPDATE SET updated_at = now()
      RETURNING id
    """), {
        "name": payload["source_name"].strip(),
        "site_url": payload["site_url"].strip(),
        "source_type": payload.get("source_type", "secondary"),
    })).scalar_one()

    canonical = canonicalise_url(payload["external_url"])
    hashed = content_hash(payload["original_title"], payload.get("original_excerpt"), source_id)
    item_id = (await session.execute(text("""
      INSERT INTO news_ingest_items
        (source_id, external_url, canonical_url, original_title, original_excerpt,
         source_published_at, content_hash, status)
      VALUES (:source_id, :external_url, :canonical_url, :title, :excerpt,
              :published_at, :hash, 'processed')
      ON CONFLICT (canonical_url) DO UPDATE SET updated_at = now()
      RETURNING id
    """), {
        "source_id": source_id, "external_url": payload["external_url"].strip(),
        "canonical_url": canonical, "title": payload["original_title"].strip(),
        "excerpt": payload.get("original_excerpt"),
        "published_at": payload.get("source_published_at"), "hash": hashed,
    })).scalar_one()

    if payload.get("is_primary", True):
        await session.execute(text(
            "UPDATE news_article_sources SET is_primary = false WHERE article_id = :id"
        ), {"id": article_id})
    await session.execute(text("""
      INSERT INTO news_article_sources (article_id, ingest_item_id, is_primary)
      VALUES (:article_id, :item_id, :is_primary)
      ON CONFLICT (article_id, ingest_item_id) DO UPDATE SET is_primary = EXCLUDED.is_primary
    """), {
        "article_id": article_id, "item_id": item_id,
        "is_primary": bool(payload.get("is_primary", True)),
    })
    return item_id


async def link_ingest_item(
    session: AsyncSession, article_id: int, ingest_item_id: int, is_primary: bool = True
) -> None:
    """Attach an already-ingested item to an article as its source.

    The Phase 2 counterpart to attach_manual_source: the source material already exists in
    news_ingest_items because the pipeline put it there, so provenance is preserved by
    reference rather than re-typed by an editor.
    """
    if is_primary:
        await session.execute(text(
            "UPDATE news_article_sources SET is_primary = false WHERE article_id = :id"
        ), {"id": article_id})
    await session.execute(text("""
      INSERT INTO news_article_sources (article_id, ingest_item_id, is_primary)
      VALUES (:article_id, :item_id, :is_primary)
      ON CONFLICT (article_id, ingest_item_id) DO UPDATE SET is_primary = EXCLUDED.is_primary
    """), {"article_id": article_id, "item_id": ingest_item_id, "is_primary": is_primary})


async def apply_impact(
    session: AsyncSession,
    article_id: int,
    factors: Mapping[str, Any],
    confidence: float,
    reasoning: str,
    assessed_by: str,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    """Run news-impact-v1 and store the result as BOTH the automated and current values.

    Recording the automated pair here is what makes a later override auditable: the machine
    reading is written once, at assessment time, and an override never touches it.

    Low confidence moves the article to review_required rather than leaving it a draft, so
    it surfaces in the editorial queue instead of sitting unnoticed.
    """
    assessment = assess(factors)
    needs_review = requires_review(confidence)

    await session.execute(text("""
      UPDATE news_articles SET
        impact_score = :score, impact_level = :level,
        automated_impact_score = :score, automated_impact_level = :level,
        impact_confidence = :confidence, impact_reasoning = :reasoning,
        impact_policy_version = :policy,
        capability_advancement = :capability_advancement,
        commercial_deployability = :commercial_deployability,
        breadth_of_affected_work = :breadth_of_affected_work,
        adoption_speed = :adoption_speed,
        human_work_reduction_potential = :human_work_reduction_potential,
        impact_assessed_at = now(), impact_assessed_by = :assessed_by,
        generation_provider = COALESCE(:provider, generation_provider),
        generation_model = COALESCE(:model, generation_model),
        generation_prompt_version = COALESCE(:prompt_version, generation_prompt_version),
        generated_at = CASE WHEN :provider IS NULL THEN generated_at ELSE now() END,
        status = CASE
          WHEN status IN ('published','rejected') THEN status
          WHEN :needs_review THEN 'review_required'
          ELSE status END,
        updated_at = now()
      WHERE id = :id
    """), {
        "id": article_id, "score": assessment.score, "level": assessment.level,
        "confidence": confidence, "reasoning": reasoning, "policy": POLICY_VERSION,
        "assessed_by": assessed_by, "needs_review": needs_review,
        "provider": provider, "model": model, "prompt_version": prompt_version,
        **assessment.factors,
    })
    return {
        "impact_score": float(assessment.score),
        "impact_level": assessment.level,
        "impact_policy_version": POLICY_VERSION,
        "requires_review": needs_review,
    }


async def override_impact(
    session: AsyncSession,
    article_id: int,
    level: str,
    overridden_by: str,
    reasoning: str | None = None,
    reason: str | None = None,
) -> None:
    """Replace the editorial level, preserving the automated pair.

    automated_impact_score/level are never written here. If no automated assessment exists,
    the current values are promoted into those columns first, so "what the machine said"
    is always populated once an override has happened — the CHECK constraint requires it.
    """
    await session.execute(text("""
      UPDATE news_articles SET
        automated_impact_score = COALESCE(automated_impact_score, impact_score),
        automated_impact_level = COALESCE(automated_impact_level, impact_level, :level),
        impact_level = :level,
        impact_reasoning = COALESCE(:reasoning, impact_reasoning),
        impact_overridden_at = now(),
        impact_overridden_by = :overridden_by,
        impact_override_reason = :reason,
        updated_at = now()
      WHERE id = :id
    """), {
        "id": article_id, "level": level, "reasoning": reasoning,
        "overridden_by": overridden_by, "reason": reason,
    })


async def publication_blockers(session: AsyncSession, article_id: int) -> list[str]:
    """Every reason this article may not go public. Empty list means publishable.

    Returns all blockers rather than the first, so an editor fixes one article once instead
    of discovering problems one refusal at a time.
    """
    row = (await session.execute(text("""
      SELECT a.headline, a.what_happened, a.why_it_matters_for_jobs,
             a.impact_level, a.impact_score, a.impact_policy_version, a.status,
             (SELECT count(*) FROM news_article_sources s WHERE s.article_id = a.id) AS sources
      FROM news_articles a WHERE a.id = :id
    """), {"id": article_id})).mappings().first()
    if row is None:
        return ["Article does not exist"]

    blockers: list[str] = []
    if not (row["headline"] or "").strip():
        blockers.append("Headline is required")
    if not (row["what_happened"] or "").strip():
        blockers.append("What happened is required")
    if not (row["why_it_matters_for_jobs"] or "").strip():
        blockers.append("Why it matters for jobs is required")
    if row["impact_level"] is None:
        blockers.append("Impact level is required")
    if row["impact_score"] is None:
        blockers.append("Impact score is required")
    if row["impact_policy_version"] is None:
        blockers.append("Impact policy version is required")
    if not row["sources"]:
        blockers.append("At least one source is required")
    if row["status"] == "rejected":
        blockers.append("Rejected articles cannot be published without reopening them")
    return blockers


async def publish(session: AsyncSession, article_id: int) -> None:
    """Publish, or refuse with every reason. The only path to status='published'."""
    blockers = await publication_blockers(session, article_id)
    if blockers:
        raise NewsPublicationRefused("; ".join(blockers))
    await session.execute(text("""
      UPDATE news_articles
      SET status = 'published', published_at = COALESCE(published_at, now()), updated_at = now()
      WHERE id = :id
    """), {"id": article_id})


async def set_status(session: AsyncSession, article_id: int, status: str) -> None:
    """Move between non-public statuses. Publication has its own guarded path."""
    if status == "published":
        raise NewsPublicationRefused("Use publish() so the publication guard runs")
    await session.execute(text("""
      UPDATE news_articles
      SET status = :status,
          published_at = CASE WHEN :status = 'rejected' THEN NULL ELSE published_at END,
          updated_at = now()
      WHERE id = :id
    """), {"id": article_id, "status": status})
