"""Read-only aggregates over what the pipeline already records.

Nothing here writes, and nothing here captures anything new: Step 4 put latency, token
counts and a stable failure category on every generation attempt precisely so these numbers
could be derived afterwards rather than re-instrumented.

Cost is reported in **tokens by default**. A currency figure appears only when the operator
supplies a price, because inventing a rate would produce a number that looks authoritative
and is not.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ingestion_summary(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    row = (await session.execute(text("""
      SELECT
        count(*)                                            AS runs,
        coalesce(sum(items_fetched), 0)                     AS fetched,
        coalesce(sum(items_new), 0)                         AS stored,
        coalesce(sum(items_candidate), 0)                   AS candidates,
        coalesce(sum(items_ignored), 0)                     AS ignored,
        coalesce(sum(items_exact_duplicate), 0)             AS exact_duplicates,
        coalesce(sum(items_near_duplicate), 0)              AS near_duplicates,
        coalesce(sum(items_outside_window), 0)              AS outside_window,
        coalesce(sum(sources_attempted), 0)                 AS fetch_attempts,
        coalesce(sum(sources_succeeded), 0)                 AS fetch_successes,
        coalesce(sum(sources_failed), 0)                    AS source_failures,
        max(started_at)                                     AS last_run
      FROM news_ingestion_runs
      WHERE started_at >= now() - make_interval(days => :days)
    """), {"days": days})).mappings().one()
    return dict(row)


async def generation_summary(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Attempt-level truth, read from the items rather than the run rows.

    A crashed run leaves its counters unwritten but its attempts recorded, so counting from
    the items is the figure that cannot silently under-report spend.
    """
    row = (await session.execute(text("""
      SELECT
        coalesce(sum(generation_attempts), 0)                        AS attempts,
        count(*) FILTER (WHERE is_ai_news IS TRUE)                   AS accepted,
        count(*) FILTER (WHERE is_ai_news IS FALSE)                  AS rejected,
        count(*) FILTER (WHERE generation_error IS NOT NULL)         AS failed,
        coalesce(sum(generation_input_tokens), 0)                    AS input_tokens,
        coalesce(sum(generation_output_tokens), 0)                   AS output_tokens,
        percentile_disc(0.5) WITHIN GROUP (ORDER BY generation_latency_ms)
          FILTER (WHERE generation_latency_ms IS NOT NULL)           AS latency_p50,
        percentile_disc(0.95) WITHIN GROUP (ORDER BY generation_latency_ms)
          FILTER (WHERE generation_latency_ms IS NOT NULL)           AS latency_p95,
        max(generation_latency_ms)                                   AS latency_max,
        round(avg(generation_latency_ms))                            AS latency_mean,
        count(*) FILTER (WHERE generation_attempted_at IS NOT NULL)  AS items_attempted,
        max(generation_attempted_at)                                 AS last_attempt
      FROM news_ingest_items
      WHERE generation_attempted_at >= now() - make_interval(days => :days)
    """), {"days": days})).mappings().one()
    return dict(row)


async def failure_breakdown(session: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    """Grouped by the stable category, not by parsing the message."""
    return [dict(r) for r in (await session.execute(text("""
      SELECT generation_error_kind AS kind, count(*) AS total,
             max(generation_attempted_at) AS last_seen
      FROM news_ingest_items
      WHERE generation_error_kind IS NOT NULL
        AND generation_attempted_at >= now() - make_interval(days => :days)
      GROUP BY generation_error_kind ORDER BY total DESC
    """), {"days": days})).mappings().all()]


async def quality_summary(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Quality proxies. These are confidence and impact readings, not measured outcomes.

    Nothing here has been validated against whether a story mattered; they describe how the
    model rated its own work and how the deterministic policy scored it.
    """
    row = (await session.execute(text("""
      SELECT
        count(*)                                                  AS articles,
        count(*) FILTER (WHERE status = 'draft')                  AS draft,
        count(*) FILTER (WHERE status = 'review_required')        AS review_required,
        count(*) FILTER (WHERE status = 'published')              AS published,
        count(*) FILTER (WHERE status = 'rejected')               AS rejected,
        count(*) FILTER (WHERE status = 'archived')               AS archived,
        count(*) FILTER (WHERE regeneration_count > 0)            AS regenerated,
        coalesce(sum(regeneration_count), 0)                      AS regenerations,
        count(*) FILTER (WHERE impact_overridden_at IS NOT NULL)  AS overridden,
        round(avg(impact_score), 2)                               AS avg_impact_score,
        round(avg(impact_confidence), 3)                          AS avg_impact_confidence,
        count(*) FILTER (WHERE impact_level = 'low')              AS impact_low,
        count(*) FILTER (WHERE impact_level = 'medium')           AS impact_medium,
        count(*) FILTER (WHERE impact_level = 'high')             AS impact_high
      FROM news_articles
      WHERE created_at >= now() - make_interval(days => :days)
    """), {"days": days})).mappings().one()

    semantic = (await session.execute(text("""
      SELECT round(avg(ai_relevance_confidence), 3) AS avg_semantic_confidence,
             min(ai_relevance_confidence)           AS min_semantic_confidence
      FROM news_ingest_items
      WHERE is_ai_news IS NOT NULL
        AND generation_attempted_at >= now() - make_interval(days => :days)
    """), {"days": days})).mappings().one()
    return dict(row) | dict(semantic)


async def source_count(session: AsyncSession) -> dict[str, Any]:
    """Configured feeds. Not windowed — configuration is current, not historical."""
    row = (await session.execute(text("""
      SELECT count(*) AS configured,
             count(*) FILTER (WHERE enabled) AS enabled,
             count(*) FILTER (WHERE consecutive_failures > 0) AS failing
      FROM news_sources
    """))).mappings().one()
    return dict(row)


async def candidate_counts(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Current queue state, by status. Complements the per-run ingestion counters."""
    rows = (await session.execute(text("""
      SELECT status, count(*) AS total FROM news_ingest_items
      WHERE fetched_at >= now() - make_interval(days => :days)
      GROUP BY status
    """), {"days": days})).mappings().all()
    counts = {"new": 0, "candidate": 0, "ignored": 0, "duplicate": 0, "processed": 0}
    return counts | {r["status"]: r["total"] for r in rows}


async def collect(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    return {
        "windowDays": days,
        "sources": await source_count(session),
        "candidates": await candidate_counts(session, days),
        "ingestion": await ingestion_summary(session, days),
        "generation": await generation_summary(session, days),
        "failures": await failure_breakdown(session, days),
        "quality": await quality_summary(session, days),
    }
