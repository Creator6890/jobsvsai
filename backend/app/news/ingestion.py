"""The Phase 2 ingestion run.

    feeds -> parse -> lookback window -> exact dedupe -> near dedupe -> relevance -> stored

What it deliberately does **not** do: generate prose, call any model, assign impact factors,
create articles, or publish anything. Its whole job is to leave good candidates in the
incoming queue for a human, and later for Phase 3.

Failure isolation is the design priority. One source returning 500, serving malformed XML or
timing out must cost exactly that source's items, never the run. Every source is therefore
fetched, parsed and recorded independently, and its error is written against the source row
so a persistently broken feed is visible rather than silently empty.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.news import dedupe, relevance
from app.news.feeds import FeedError, HttpFeedFetcher, ParsedEntry
from app.repositories import news_ingest as repo


@dataclass
class RunCounters:
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    items_fetched: int = 0
    items_new: int = 0
    items_exact_duplicate: int = 0
    items_near_duplicate: int = 0
    items_ignored: int = 0
    items_candidate: int = 0
    items_outside_window: int = 0
    duration_ms: int = 0


@dataclass
class RunResult:
    run_id: int | None
    run_key: str
    status: str
    counters: RunCounters = field(default_factory=RunCounters)
    errors: list[dict[str, str]] = field(default_factory=list)
    skipped_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "runId": self.run_id, "runKey": self.run_key, "status": self.status,
            "skippedReason": self.skipped_reason,
            "counters": asdict(self.counters), "errors": self.errors,
        }


def _within_window(entry: ParsedEntry, cutoff: datetime) -> bool:
    """Entries with no usable date are admitted.

    A feed that omits or malforms its dates would otherwise be silently invisible, which is
    a worse failure than occasionally re-examining an old entry — exact dedupe absorbs the
    repeat anyway.
    """
    if entry.source_published_at is None:
        return True
    return entry.source_published_at >= cutoff


async def run_ingestion(
    session: AsyncSession,
    triggered_by: str = "manual",
    fetcher: object | None = None,
    lookback_hours: int | None = None,
    max_entries_per_feed: int | None = None,
) -> RunResult:
    """Fetch every enabled source once and triage what comes back.

    `fetcher` is injectable so tests drive the whole pipeline from fixtures with no network.
    """
    settings = get_settings()
    run_key = f"news-ingest-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"

    if not settings.ingestion_enabled:
        # A disabled scheduler must be a safe no-op, not an error: a recurring job will fire
        # regardless of configuration and should cost nothing when ingestion is off. No feed
        # is opened and no run row is written.
        return RunResult(
            run_id=None, run_key=run_key, status="skipped",
            skipped_reason="NEWS_INGESTION_ENABLED is false",
        )

    lookback = lookback_hours or settings.news_lookback_hours
    per_feed = max_entries_per_feed or settings.news_max_entries_per_feed
    max_candidates = settings.news_max_candidates_per_run
    fetcher = fetcher or HttpFeedFetcher()

    started = datetime.now(UTC)
    cutoff = started - timedelta(hours=lookback)
    counters = RunCounters()
    errors: list[dict[str, str]] = []

    run_id = await repo.start_run(session, {
        "run_key": run_key,
        "relevance_policy_version": relevance.POLICY_VERSION,
        "lookback_hours": lookback,
        "max_entries_per_feed": per_feed,
        "triggered_by": triggered_by,
    })
    await session.commit()

    sources = await repo.list_enabled_sources(session)

    for source in sources:
        counters.sources_attempted += 1
        try:
            entries = fetcher.fetch_entries(source["feed_url"], source["id"])
        except FeedError as error:
            counters.sources_failed += 1
            errors.append({"source": source["name"], "error": str(error)[:400]})
            await repo.record_source_result(session, source["id"], str(error)[:400])
            await session.commit()
            continue
        except Exception as error:  # noqa: BLE001 - an unexpected fault is still one source
            counters.sources_failed += 1
            message = f"{type(error).__name__}: {error}"[:400]
            errors.append({"source": source["name"], "error": message})
            await repo.record_source_result(session, source["id"], message)
            await session.commit()
            continue

        counters.sources_succeeded += 1
        await repo.record_source_result(session, source["id"], None)

        is_ai_specific = repo.source_is_ai_specific(source["name"])

        for entry in entries[:per_feed]:
            counters.items_fetched += 1

            if not _within_window(entry, cutoff):
                counters.items_outside_window += 1
                continue

            # 1. Exact dedupe, on both axes the schema enforces.
            existing = await repo.find_existing(
                session, entry.canonical_url, source["id"], entry.content_hash
            )
            if existing is not None:
                counters.items_exact_duplicate += 1
                continue

            # 2. Near dedupe, against recent non-duplicate items only.
            fingerprint = dedupe.normalise_title(entry.original_title)
            recent = await repo.recent_fingerprints(session, dedupe.DEFAULT_WINDOW_HOURS)
            match = dedupe.find_duplicate(fingerprint, recent)

            if match is not None:
                # The row is kept: cross-source coverage is evidence about the event. It is
                # marked duplicate and points at what it duplicates, and is not scored,
                # because a duplicate is not a separate candidate.
                inserted = await repo.insert_item(session, {
                    "source_id": source["id"],
                    "external_url": entry.external_url,
                    "canonical_url": entry.canonical_url,
                    "original_title": entry.original_title,
                    "original_excerpt": entry.original_excerpt,
                    "source_published_at": entry.source_published_at,
                    "content_hash": entry.content_hash,
                    "status": "duplicate",
                    "relevance_score": None,
                    "relevance_policy_version": None,
                    "relevance_signals": json.dumps({"nearDuplicateOf": match.ingest_item_id}),
                    "feed_categories": json.dumps(entry.categories),
                    "title_fingerprint": fingerprint,
                    "duplicate_of_ingest_item_id": match.ingest_item_id,
                    "near_duplicate_similarity": match.similarity,
                })
                if inserted is None:
                    counters.items_exact_duplicate += 1
                else:
                    counters.items_near_duplicate += 1
                await session.commit()
                continue

            # 3. Relevance prefilter.
            assessment = relevance.assess(
                title=entry.original_title,
                excerpt=entry.original_excerpt,
                categories=entry.categories,
                source_trust_tier=source["trust_tier"],
                source_is_ai_specific=is_ai_specific,
            )
            status = assessment.status
            # Volume control: past the per-run ceiling, a would-be candidate is stored as
            # `new` rather than dropped, so the next run can pick it up without re-fetching.
            if status == "candidate" and counters.items_candidate >= max_candidates:
                status = "new"

            inserted = await repo.insert_item(session, {
                "source_id": source["id"],
                "external_url": entry.external_url,
                "canonical_url": entry.canonical_url,
                "original_title": entry.original_title,
                "original_excerpt": entry.original_excerpt,
                "source_published_at": entry.source_published_at,
                "content_hash": entry.content_hash,
                "status": status,
                "relevance_score": assessment.score,
                "relevance_policy_version": assessment.policy_version,
                "relevance_signals": json.dumps(assessment.signals),
                "feed_categories": json.dumps(entry.categories),
                "title_fingerprint": fingerprint,
                "duplicate_of_ingest_item_id": None,
                "near_duplicate_similarity": None,
            })
            await session.commit()

            if inserted is None:
                # Lost a race, or the feed repeated an entry within one document.
                counters.items_exact_duplicate += 1
                continue

            counters.items_new += 1
            if status == "candidate":
                counters.items_candidate += 1
            elif status == "ignored":
                counters.items_ignored += 1

    counters.duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    await repo.complete_run(
        session, run_id, asdict(counters), json.dumps(errors),
        "completed" if counters.sources_failed < counters.sources_attempted or not sources else "failed",
    )
    await session.commit()

    return RunResult(
        run_id=run_id, run_key=run_key,
        status="completed" if counters.sources_failed < counters.sources_attempted or not sources else "failed",
        counters=counters, errors=errors,
    )
