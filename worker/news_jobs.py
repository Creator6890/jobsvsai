"""RQ job for scheduled AI News ingestion.

Uses the existing Redis/RQ worker. No new scheduler, no Celery, no second process type — the
cadence is supplied by whatever enqueues this (an RQ scheduler, a cron entry calling
`enqueue_ingestion`, or an admin button), and `NEWS_FETCH_INTERVAL_MINUTES` is read here
rather than compiled into the job so changing it is configuration.

The job is deliberately safe to fire on a disabled system: with `NEWS_ENABLED=false` it
returns a `skipped` result without opening a feed connection or writing a run row.
"""

from __future__ import annotations

import asyncio
import os

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.ingestion import run_ingestion


def fetch_news_sources(triggered_by: str = "scheduler") -> dict[str, object]:
    """Entry point for RQ. Synchronous by necessity; RQ jobs are plain callables."""
    return asyncio.run(_run(triggered_by))


async def _run(triggered_by: str) -> dict[str, object]:
    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by=triggered_by)
    return result.as_dict()


def enqueue_ingestion(queue=None, triggered_by: str = "scheduler"):
    """Enqueue one ingestion run. Returns None when news is disabled.

    Kept separate from the job body so a caller can schedule work without importing RQ's
    scheduler, and so the disabled case costs nothing at all.
    """
    settings = get_settings()
    if not settings.news_enabled:
        return None
    if queue is None:
        from redis import Redis
        from rq import Queue

        redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        queue = Queue(os.getenv("QUEUE_NAME", "default"), connection=redis)
    return queue.enqueue(fetch_news_sources, triggered_by)


def fetch_interval_seconds() -> int:
    """The configured cadence, for whatever schedules this."""
    return max(60, get_settings().news_fetch_interval_minutes * 60)


# ---------------------------------------------------------------- Phase 3 generation


def generate_news_candidates(triggered_by: str = "batch",
                             ingest_item_ids: list[int] | None = None) -> dict[str, object]:
    """RQ job: generate briefs for a batch of candidates.

    Deliberately not scheduled. It is enqueued by an admin action or run by hand; deciding
    the production cadence is a later phase's job, and an unattended generator on a free
    tier is exactly what the daily cap exists to survive.
    """
    return asyncio.run(_generate(triggered_by, ingest_item_ids))


async def _generate(triggered_by: str, ingest_item_ids: list[int] | None) -> dict[str, object]:
    from app.news.generation_service import run_generation_batch

    async with SessionFactory() as session:
        result = await run_generation_batch(
            session, triggered_by=triggered_by, ingest_item_ids=ingest_item_ids
        )
    return result.as_dict()


def enqueue_generation(queue=None, triggered_by: str = "batch",
                       ingest_item_ids: list[int] | None = None):
    """Enqueue one generation batch. Returns None when news is disabled."""
    settings = get_settings()
    if not settings.news_enabled:
        return None
    if queue is None:
        from redis import Redis
        from rq import Queue

        redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        queue = Queue(os.getenv("QUEUE_NAME", "default"), connection=redis)
    return queue.enqueue(generate_news_candidates, triggered_by, ingest_item_ids)
