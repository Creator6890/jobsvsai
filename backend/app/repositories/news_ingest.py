"""Data access for ingest items, sources and ingestion runs.

Separate from `repositories/news.py`, which owns articles and the publication gate. Ingest
items are internal triage material and are never publicly readable: there is no public
predicate here because there is no public read path to gate.
"""

from __future__ import annotations

import json

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.news import priority

# Sources whose own subject matter is AI. Used by the relevance prefilter to let an opaque
# first-party headline ("Introducing Operator") through. Matched on the source name, so
# adding a source stays an INSERT rather than a code change; an unlisted source simply does
# not get the boost.
AI_SPECIFIC_SOURCES: frozenset[str] = frozenset({
    "openai", "google deepmind", "google ai", "anthropic", "meta ai",
    "microsoft research", "nvidia", "mistral ai", "hugging face",
})


def source_is_ai_specific(name: str) -> bool:
    return (name or "").strip().lower() in AI_SPECIFIC_SOURCES


async def list_enabled_sources(session: AsyncSession) -> list[dict[str, Any]]:
    """Sources with a feed, most trusted first."""
    return [dict(row) for row in (await session.execute(text("""
      SELECT id, name, feed_url, site_url, source_type, trust_tier, feed_format,
             consecutive_failures, last_success_at
      FROM news_sources
      WHERE enabled AND feed_url IS NOT NULL
      ORDER BY trust_tier, name
    """))).mappings().all()]


async def recent_fingerprints(
    session: AsyncSession, window_hours: int
) -> list[tuple[int, str]]:
    """Items inside the near-duplicate window, as (id, fingerprint).

    Excludes items already marked duplicate: chaining a duplicate onto a duplicate would
    build a similarity drift chain where the last item resembles the first not at all.
    """
    rows = (await session.execute(text("""
      SELECT id, title_fingerprint FROM news_ingest_items
      WHERE title_fingerprint IS NOT NULL
        AND status <> 'duplicate'
        AND fetched_at >= now() - make_interval(hours => :hours)
      ORDER BY fetched_at DESC
      LIMIT 500
    """), {"hours": window_hours})).mappings().all()
    return [(row["id"], row["title_fingerprint"]) for row in rows]


async def find_existing(
    session: AsyncSession, canonical_url: str, source_id: int, content_hash: str
) -> int | None:
    """Exact-duplicate probe on both schema-enforced axes."""
    return (await session.execute(text("""
      SELECT id FROM news_ingest_items
      WHERE canonical_url = :canonical_url
         OR (source_id = :source_id AND content_hash = :content_hash)
      LIMIT 1
    """), {
        "canonical_url": canonical_url, "source_id": source_id, "content_hash": content_hash,
    })).scalar_one_or_none()


async def insert_item(session: AsyncSession, item: Mapping[str, Any]) -> int | None:
    """Insert one ingest item.

    ON CONFLICT DO NOTHING on both unique axes: a concurrent run, or a feed that repeats an
    entry mid-document, must not fail the whole batch. A None return means "already known",
    which the caller counts as an exact duplicate.
    """
    return (await session.execute(text("""
      INSERT INTO news_ingest_items
        (source_id, external_url, canonical_url, original_title, original_excerpt,
         source_published_at, content_hash, status, relevance_score,
         relevance_policy_version, relevance_signals, feed_categories,
         title_fingerprint, duplicate_of_ingest_item_id, near_duplicate_similarity)
      VALUES
        (:source_id, :external_url, :canonical_url, :original_title, :original_excerpt,
         :source_published_at, :content_hash, :status, :relevance_score,
         :relevance_policy_version, CAST(:relevance_signals AS jsonb),
         CAST(:feed_categories AS jsonb),
         :title_fingerprint, :duplicate_of_ingest_item_id, :near_duplicate_similarity)
      ON CONFLICT DO NOTHING
      RETURNING id
    """), item)).scalar_one_or_none()


async def record_source_result(
    session: AsyncSession, source_id: int, error: str | None
) -> None:
    """Update per-source health. Conservative backoff state lives here, not in the fetcher."""
    await session.execute(text("""
      UPDATE news_sources SET
        last_fetched_at = now(),
        last_success_at = CASE WHEN CAST(:error AS TEXT) IS NULL THEN now() ELSE last_success_at END,
        last_error = CAST(:error AS TEXT),
        consecutive_failures = CASE WHEN CAST(:error AS TEXT) IS NULL
                                    THEN 0 ELSE consecutive_failures + 1 END,
        updated_at = now()
      WHERE id = :id
    """), {"id": source_id, "error": error})


async def start_run(session: AsyncSession, run: Mapping[str, Any]) -> int:
    return (await session.execute(text("""
      INSERT INTO news_ingestion_runs
        (run_key, relevance_policy_version, lookback_hours, max_entries_per_feed, triggered_by)
      VALUES (:run_key, :relevance_policy_version, :lookback_hours, :max_entries_per_feed, :triggered_by)
      RETURNING id
    """), run)).scalar_one()


async def complete_run(
    session: AsyncSession, run_id: int, counters: Mapping[str, Any], errors: str, status: str
) -> None:
    await session.execute(text("""
      UPDATE news_ingestion_runs SET
        status = :status,
        sources_attempted = :sources_attempted, sources_succeeded = :sources_succeeded,
        sources_failed = :sources_failed,
        items_fetched = :items_fetched, items_new = :items_new,
        items_exact_duplicate = :items_exact_duplicate,
        items_near_duplicate = :items_near_duplicate,
        items_ignored = :items_ignored, items_candidate = :items_candidate,
        items_outside_window = :items_outside_window,
        errors = CAST(:errors AS jsonb),
        completed_at = now(),
        duration_ms = :duration_ms
      WHERE id = :id
    """), {"id": run_id, "status": status, "errors": errors, **counters})


# ------------------------------------------------------------------------- admin queries

INGEST_COLUMNS = """
  item.id, item.source_id, source.name AS source_name, source.trust_tier,
  item.external_url, item.canonical_url, item.original_title, item.original_excerpt,
  item.source_published_at, item.fetched_at, item.status,
  item.relevance_score, item.relevance_policy_version, item.relevance_signals,
  item.feed_categories, item.duplicate_of_ingest_item_id, item.near_duplicate_similarity,
  item.is_ai_news, item.ai_relevance_confidence, item.ai_relevance_reason,
  item.semantic_policy_version, item.generation_provider, item.generation_model,
  item.generation_prompt_version, item.generation_attempted_at, item.generation_attempts,
  item.generation_error, item.generation_input_tokens, item.generation_output_tokens
"""


async def list_ingest_items(
    session: AsyncSession,
    status: str | None = None,
    source_id: int | None = None,
    since_hours: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = (await session.execute(text(f"""
      SELECT {INGEST_COLUMNS}
      FROM news_ingest_items item
      JOIN news_sources source ON source.id = item.source_id
      WHERE (CAST(:status AS TEXT) IS NULL OR item.status = CAST(:status AS TEXT))
        AND (CAST(:source_id AS BIGINT) IS NULL OR item.source_id = CAST(:source_id AS BIGINT))
        AND (CAST(:since_hours AS INTEGER) IS NULL
             OR item.fetched_at >= now() - make_interval(hours => CAST(:since_hours AS INTEGER)))
      ORDER BY item.relevance_score DESC NULLS LAST, item.source_published_at DESC NULLS LAST,
               item.id DESC
      LIMIT :limit OFFSET :offset
    """), {
        "status": status, "source_id": source_id, "since_hours": since_hours,
        "limit": limit, "offset": offset,
    })).mappings().all()
    return [dict(row) for row in rows]


async def get_ingest_item(session: AsyncSession, item_id: int) -> dict[str, Any] | None:
    row = (await session.execute(text(f"""
      SELECT {INGEST_COLUMNS}
      FROM news_ingest_items item
      JOIN news_sources source ON source.id = item.source_id
      WHERE item.id = :id
    """), {"id": item_id})).mappings().first()
    return dict(row) if row else None


async def ingest_status_counts(session: AsyncSession) -> dict[str, int]:
    rows = (await session.execute(
        text("SELECT status, count(*) AS total FROM news_ingest_items GROUP BY status")
    )).mappings().all()
    counts = {"new": 0, "candidate": 0, "ignored": 0, "duplicate": 0, "processed": 0}
    return counts | {row["status"]: row["total"] for row in rows}


async def set_ingest_status(session: AsyncSession, item_id: int, status: str) -> None:
    """Editorial triage. `processed` is reserved for Phase 3 conversion and is not settable
    here: an item becomes processed by being turned into an article, not by an opinion."""
    if status not in {"candidate", "ignored", "new"}:
        raise ValueError(f"Status {status!r} is not settable from admin triage")
    await session.execute(text("""
      UPDATE news_ingest_items
      SET status = :status,
          duplicate_of_ingest_item_id = NULL,
          updated_at = now()
      WHERE id = :id
    """), {"id": item_id, "status": status})


async def mark_processed(session: AsyncSession, item_id: int) -> None:
    """The one path to `processed`: the item has been converted into an article."""
    await session.execute(text("""
      UPDATE news_ingest_items SET status = 'processed', updated_at = now() WHERE id = :id
    """), {"id": item_id})


# ------------------------------------------------------------------- Phase 3 generation


async def article_for_ingest_item(session: AsyncSession, item_id: int) -> int | None:
    """The article already generated from this candidate, if any.

    The idempotency check. Consulted before any provider call so a repeated request costs
    no quota, and backed by the (article_id, ingest_item_id) primary key on the link table
    so a genuine race still cannot create two links to one article.
    """
    return (await session.execute(text("""
      SELECT article_id FROM news_article_sources WHERE ingest_item_id = :id LIMIT 1
    """), {"id": item_id})).scalar_one_or_none()


async def ingest_items_for_article(session: AsyncSession, article_id: int) -> list[dict[str, Any]]:
    """The source candidates behind an article, primary first.

    What makes editorial review possible: the reviewer can read the model's brief beside the
    feed material it was written from, and see the semantic verdict that let it through.
    Without this the editor is asked to trust generated prose with no way to check it.
    """
    rows = (await session.execute(text(f"""
      SELECT {INGEST_COLUMNS}
      FROM news_article_sources link
      JOIN news_ingest_items item ON item.id = link.ingest_item_id
      JOIN news_sources source ON source.id = item.source_id
      WHERE link.article_id = :id
      ORDER BY link.is_primary DESC, item.id
    """), {"id": article_id})).mappings().all()
    return [dict(row) for row in rows]


async def select_generation_candidates(session: AsyncSession, limit: int) -> list[int]:
    """Unassessed candidates, highest JobsVsAI generation priority first.

    Excludes anything already assessed, already converted, or already linked to an article,
    so a repeated batch never reprocesses the same item.

    Ordering is by `news-generation-priority-v1`, not by relevance score. Relevance decides
    what enters the queue; priority decides what leaves it first, and the two disagree often
    enough to matter — the first production dry run put datacentre hardware marketing above a
    labour-market study on relevance alone. Generation is capped at a handful of calls a day,
    so the order is the entire practical difference.

    Priority is derived here rather than stored. It is a pure function of fields the row
    already carries, so persisting it would add a column that could only ever disagree with
    the policy, and every policy revision would need a backfill to stay truthful. The
    eligible queue is bounded by the per-run candidate ceiling, so ranking in Python costs
    nothing that matters.
    """
    rows = (await session.execute(text("""
      SELECT item.id, item.original_title, item.original_excerpt, item.feed_categories,
             item.relevance_score, item.source_published_at, source.trust_tier
      FROM news_ingest_items item
      JOIN news_sources source ON source.id = item.source_id
      WHERE item.status = 'candidate'
        AND item.is_ai_news IS NULL
        AND NOT EXISTS (
          SELECT 1 FROM news_article_sources link WHERE link.ingest_item_id = item.id)
    """))).mappings().all()

    ranked = sorted(
        ((priority.assess(
            title=row["original_title"],
            excerpt=row["original_excerpt"],
            categories=_categories(row["feed_categories"]),
            source_trust_tier=row["trust_tier"] or 3,
        ), row) for row in rows),
        key=lambda pair: (
            -pair[0].score,
            -(pair[1]["relevance_score"] or 0),
            -(pair[1]["source_published_at"].timestamp()
              if pair[1]["source_published_at"] else 0),
            -pair[1]["id"],
        ),
    )
    return [row["id"] for _, row in ranked[:limit]]


def _categories(raw: Any) -> list[str]:
    """`feed_categories` is stored as JSON text; tolerate null and malformed values."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


async def record_semantic_acceptance(
    session: AsyncSession, item_id: int, brief, provider: str, model: str,
    prompt_version: str, latency_ms: int | None = None,
) -> None:
    """Accepted: the item is now `processed`, and the verdict is kept alongside it."""
    await session.execute(text("""
      UPDATE news_ingest_items SET
        status = 'processed',
        is_ai_news = true,
        ai_relevance_confidence = :confidence,
        ai_relevance_reason = :reason,
        semantic_policy_version = :policy,
        generation_provider = :provider, generation_model = :model,
        generation_prompt_version = :prompt_version,
        generation_attempted_at = now(),
        generation_attempts = generation_attempts + 1,
        generation_error = NULL,
        generation_error_kind = NULL,
        generation_latency_ms = :latency_ms,
        generation_input_tokens = :input_tokens,
        generation_output_tokens = :output_tokens,
        updated_at = now()
      WHERE id = :id
    """), _semantic_params(item_id, brief, provider, model, prompt_version, latency_ms))


async def record_semantic_rejection(
    session: AsyncSession, item_id: int, brief, provider: str, model: str,
    prompt_version: str, latency_ms: int | None = None,
) -> None:
    """Rejected: no article, and the item becomes `ignored`.

    The verdict, its confidence and its stated reason are retained. A rejection with its
    reasoning is the most useful single record for calibrating the prompt later, so it is
    kept rather than discarded with the candidate.
    """
    await session.execute(text("""
      UPDATE news_ingest_items SET
        status = 'ignored',
        is_ai_news = false,
        ai_relevance_confidence = :confidence,
        ai_relevance_reason = :reason,
        semantic_policy_version = :policy,
        generation_provider = :provider, generation_model = :model,
        generation_prompt_version = :prompt_version,
        generation_attempted_at = now(),
        generation_attempts = generation_attempts + 1,
        generation_error = NULL,
        generation_error_kind = NULL,
        generation_latency_ms = :latency_ms,
        generation_input_tokens = :input_tokens,
        generation_output_tokens = :output_tokens,
        updated_at = now()
      WHERE id = :id
    """), _semantic_params(item_id, brief, provider, model, prompt_version, latency_ms))


def _semantic_params(item_id, brief, provider, model, prompt_version, latency_ms=None) -> dict:
    from app.news.generation import SEMANTIC_POLICY_VERSION

    return {
        "id": item_id,
        "confidence": brief.ai_relevance_confidence,
        "reason": brief.relevance_reason,
        "policy": SEMANTIC_POLICY_VERSION,
        "provider": provider, "model": model, "prompt_version": prompt_version,
        "input_tokens": brief.input_tokens, "output_tokens": brief.output_tokens,
        "latency_ms": latency_ms,
    }


async def record_generation_failure(
    session: AsyncSession, item_id: int, provider: str, model: str,
    prompt_version: str, error: str, error_kind: str = "unknown",
    latency_ms: int | None = None,
) -> None:
    """A failed attempt. The item keeps its `candidate` status so it stays retryable.

    Only the attempt counter, the reason and its category move; the semantic columns stay
    NULL because no verdict was reached — an unassessed item is not the same as one the model
    declined, and conflating them would corrupt the acceptance rate Step 5 needs.
    """
    await session.execute(text("""
      UPDATE news_ingest_items SET
        generation_provider = :provider, generation_model = :model,
        generation_prompt_version = :prompt_version,
        generation_attempted_at = now(),
        generation_attempts = generation_attempts + 1,
        generation_error = :error,
        generation_error_kind = :error_kind,
        generation_latency_ms = :latency_ms,
        updated_at = now()
      WHERE id = :id
    """), {"id": item_id, "provider": provider, "model": model,
           "prompt_version": prompt_version, "error": error,
           "error_kind": error_kind, "latency_ms": latency_ms})


async def token_totals_for_items(session: AsyncSession, item_ids: list[int]) -> dict[str, int]:
    if not item_ids:
        return {"input": 0, "output": 0}
    row = (await session.execute(text("""
      SELECT coalesce(sum(generation_input_tokens), 0) AS input_tokens,
             coalesce(sum(generation_output_tokens), 0) AS output_tokens
      FROM news_ingest_items WHERE id = ANY(:ids)
    """), {"ids": item_ids})).mappings().one()
    return {"input": int(row["input_tokens"]), "output": int(row["output_tokens"])}


async def start_generation_run(session: AsyncSession, run: Mapping[str, Any]) -> int:
    return (await session.execute(text("""
      INSERT INTO news_generation_runs
        (run_key, provider, model, prompt_version, impact_policy_version,
         semantic_policy_version, batch_size, daily_limit, triggered_by)
      VALUES (:run_key, :provider, :model, :prompt_version, :impact_policy_version,
              :semantic_policy_version, :batch_size, :daily_limit, :triggered_by)
      RETURNING id
    """), run)).scalar_one()


async def complete_generation_run(
    session: AsyncSession, run_id: int, counters: Mapping[str, Any], errors: str, status: str
) -> None:
    await session.execute(text("""
      UPDATE news_generation_runs SET
        status = :status,
        candidates_selected = :candidates_selected, calls_made = :calls_made,
        accepted = :accepted, rejected = :rejected, failed = :failed,
        skipped_existing = :skipped_existing,
        articles_draft = :articles_draft,
        articles_review_required = :articles_review_required,
        input_tokens = :input_tokens, output_tokens = :output_tokens,
        errors = CAST(:errors AS jsonb),
        completed_at = now(), duration_ms = :duration_ms
      WHERE id = :id
    """), {"id": run_id, "status": status, "errors": errors, **counters})


async def latest_generation_runs(session: AsyncSession, limit: int = 5) -> list[dict[str, Any]]:
    return [dict(r) for r in (await session.execute(text(
        "SELECT * FROM news_generation_runs ORDER BY started_at DESC LIMIT :limit"
    ), {"limit": limit})).mappings().all()]


async def latest_runs(session: AsyncSession, limit: int = 10) -> list[dict[str, Any]]:
    return [dict(row) for row in (await session.execute(text("""
      SELECT * FROM news_ingestion_runs ORDER BY started_at DESC LIMIT :limit
    """), {"limit": limit})).mappings().all()]
