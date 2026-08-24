"""The ingestion run end to end, plus the admin incoming queue.

The fetcher is injected, so no test opens a socket. Every row created is removed afterwards:
ingest items are ordinary mutable rows and a leak would change what the next run sees in its
near-duplicate window.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.feeds import FeedError, parse_feed
from app.news.ingestion import run_ingestion
from tests.fixtures.feeds import ATOM_VALID, RSS_VALID

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE_A = "Pytest Lab Blog"
SOURCE_B = "Pytest Atom Lab"
SOURCE_BROKEN = "Pytest Broken Feed"


def admin_auth() -> tuple[str, str]:
    return os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too")


class FakeFetcher:
    """Serves fixture documents by feed URL, and fails for the feed that is meant to fail."""

    def __init__(self, documents: dict[str, str]) -> None:
        self.documents = documents
        self.calls: list[str] = []

    def fetch_entries(self, feed_url: str, source_id: int):
        self.calls.append(feed_url)
        document = self.documents.get(feed_url)
        if document is None:
            raise FeedError(f"pytest: no fixture for {feed_url}")
        return parse_feed(source_id, document)


def enable_news(monkeypatch, **overrides) -> None:
    """Settings are lru_cached, so the cache is cleared around every override."""
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "true")
    for key, value in overrides.items():
        monkeypatch.setenv(key.upper(), str(value))
    get_settings.cache_clear()


async def _cleanup() -> None:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          DELETE FROM news_articles WHERE id IN (
            SELECT article_id FROM news_article_sources link
            JOIN news_ingest_items item ON item.id = link.ingest_item_id
            JOIN news_sources source ON source.id = item.source_id
            WHERE source.name LIKE 'Pytest %')
        """))
        await session.execute(text("""
          DELETE FROM news_ingest_items WHERE source_id IN (
            SELECT id FROM news_sources WHERE name LIKE 'Pytest %')
        """))
        await session.execute(text("DELETE FROM news_sources WHERE name LIKE 'Pytest %'"))
        await session.execute(text(
            "DELETE FROM news_ingestion_runs WHERE triggered_by LIKE 'pytest%' "
            "OR triggered_by LIKE 'admin:%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def sources():
    """Three sources: two that parse, one whose feed always fails.

    The nine real sources seeded by migration 030 are disabled for the duration and restored
    afterwards. Without that, a run would attempt them too — the injected fetcher has no
    fixture for a real feed, so they would simply all fail and make every counter assertion
    depend on how many sources happen to be seeded. Disabling them also states the intent
    plainly: no test may reach a live feed.
    """
    await _cleanup()
    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "UPDATE news_sources SET enabled = false WHERE name NOT LIKE 'Pytest %'"
        ))
        for name, url, tier, ai in (
            (SOURCE_A, "https://fixture.test/rss.xml", 1, "primary"),
            (SOURCE_B, "https://fixture.test/atom.xml", 1, "primary"),
            (SOURCE_BROKEN, "https://fixture.test/broken.xml", 2, "secondary"),
        ):
            await session.execute(text("""
              INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                        feed_format, enabled)
              VALUES (:name, :url, 'https://fixture.test', :stype, :tier, 'rss', true)
            """), {"name": name, "url": url, "stype": ai, "tier": tier})
    try:
        yield
    finally:
        await _cleanup()
        async with SessionFactory() as session, session.begin():
            await session.execute(text(
                "UPDATE news_sources SET enabled = true WHERE name NOT LIKE 'Pytest %'"
            ))
        get_settings.cache_clear()


def fetcher() -> FakeFetcher:
    return FakeFetcher({
        "https://fixture.test/rss.xml": RSS_VALID,
        "https://fixture.test/atom.xml": ATOM_VALID,
    })


async def _statuses() -> dict[str, int]:
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT item.status, count(*) AS total FROM news_ingest_items item
          JOIN news_sources source ON source.id = item.source_id
          WHERE source.name LIKE 'Pytest %' GROUP BY item.status
        """))).mappings().all()
    return {row["status"]: row["total"] for row in rows}


# ------------------------------------------------------------------------------- the run


async def test_disabled_ingestion_is_a_safe_no_op(monkeypatch, sources) -> None:
    """A scheduled job on a disabled system must cost nothing and write nothing."""
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "false")
    get_settings.cache_clear()
    probe = fetcher()

    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by="pytest", fetcher=probe)

    assert result.status == "skipped"
    assert result.skipped_reason == "NEWS_INGESTION_ENABLED is false"
    assert result.run_id is None
    assert probe.calls == [], "a disabled run must not touch a feed"
    assert await _statuses() == {}


async def test_full_run_triages_every_entry(monkeypatch, sources) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)  # fixtures are dated 2026
    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    counters = result.counters
    assert result.status == "completed"
    assert counters.sources_attempted == 3
    assert counters.sources_succeeded == 2
    assert counters.sources_failed == 1

    statuses = await _statuses()
    # The model launch and the agent story are candidates; the CFO appointment is ignored;
    # "GPT-Pytest is now available" restates the launch and is a near duplicate.
    assert statuses.get("candidate", 0) >= 2
    assert statuses.get("ignored", 0) >= 1
    assert statuses.get("duplicate", 0) >= 1


async def test_one_failing_source_does_not_stop_the_others(monkeypatch, sources) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    assert result.counters.sources_failed == 1
    assert result.counters.items_new > 0, "items from healthy feeds must still land"
    assert any(error["source"] == SOURCE_BROKEN for error in result.errors)

    # The failure is recorded against the source, so a persistently broken feed is visible.
    async with SessionFactory() as session:
        row = (await session.execute(text(
            "SELECT last_error, consecutive_failures FROM news_sources WHERE name = :n"
        ), {"n": SOURCE_BROKEN})).mappings().one()
    assert row["last_error"] is not None
    assert row["consecutive_failures"] == 1


async def test_repeat_run_is_idempotent(monkeypatch, sources) -> None:
    """Re-fetching an unchanged feed must add nothing and count the repeats as duplicates."""
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        first = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())
    before = await _statuses()

    async with SessionFactory() as session:
        second = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    assert second.counters.items_new == 0
    assert second.counters.items_exact_duplicate >= first.counters.items_new
    assert await _statuses() == before, "a repeat run must not change stored triage"


async def test_lookback_window_excludes_old_entries(monkeypatch, sources) -> None:
    """The guard against ingesting a feed's entire archive on first run."""
    enable_news(monkeypatch, news_lookback_hours=1)
    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    assert result.counters.items_outside_window > 0
    assert result.counters.items_new == 0


async def test_per_feed_entry_cap_is_applied(monkeypatch, sources) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        result = await run_ingestion(
            session, triggered_by="pytest", fetcher=fetcher(), max_entries_per_feed=1
        )
    # Three RSS entries and one usable Atom entry, capped at one per feed.
    assert result.counters.items_fetched == 2


async def test_run_is_recorded_with_counters(monkeypatch, sources) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        result = await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())
        row = (await session.execute(text(
            "SELECT * FROM news_ingestion_runs WHERE id = :id"
        ), {"id": result.run_id})).mappings().one()

    assert row["status"] == "completed"
    assert row["relevance_policy_version"] == "news-relevance-v1"
    assert row["sources_attempted"] == 3 and row["sources_failed"] == 1
    assert row["completed_at"] is not None and row["duration_ms"] >= 0
    assert len(row["errors"]) == 1


# ----------------------------------------------------------------------- admin + exposure


async def test_incoming_queue_requires_authentication(client: AsyncClient, sources) -> None:
    assert (await client.get("/api/v1/admin/news/incoming")).status_code == 401
    assert (await client.get("/api/v1/admin/news/incoming/counts")).status_code == 401
    assert (await client.post("/api/v1/admin/news/ingest/run")).status_code == 401


async def test_ingest_items_are_never_publicly_visible(
    client: AsyncClient, monkeypatch, sources
) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    items = (await client.get(
        "/api/v1/admin/news/incoming?status=candidate", auth=admin_auth()
    )).json()
    assert items, "expected at least one candidate to test against"

    # Nothing an ingest item carries may appear on any public route.
    public = (await client.get("/api/v1/news?limit=100")).json()
    public_slugs = {article["slug"] for article in public}
    for item in items:
        assert (await client.get(f"/api/v1/news/{item['id']}")).status_code == 404
        assert item["originalTitle"] not in {a["headline"] for a in public}
        assert str(item["id"]) not in public_slugs
    assert (await client.get("/api/v1/news/incoming")).status_code == 404


async def test_ignore_and_restore_a_candidate(client: AsyncClient, monkeypatch, sources) -> None:
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    item = (await client.get(
        "/api/v1/admin/news/incoming?status=candidate", auth=admin_auth()
    )).json()[0]

    ignored = (await client.post(
        f"/api/v1/admin/news/incoming/{item['id']}/status",
        json={"status": "ignored"}, auth=admin_auth(),
    )).json()
    assert ignored["status"] == "ignored"

    restored = (await client.post(
        f"/api/v1/admin/news/incoming/{item['id']}/status",
        json={"status": "candidate"}, auth=admin_auth(),
    )).json()
    assert restored["status"] == "candidate"


async def test_processed_cannot_be_set_by_triage(client: AsyncClient, monkeypatch, sources) -> None:
    """`processed` means converted into an article, never an editorial opinion."""
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())
    item = (await client.get(
        "/api/v1/admin/news/incoming?status=candidate", auth=admin_auth()
    )).json()[0]

    response = await client.post(
        f"/api/v1/admin/news/incoming/{item['id']}/status",
        json={"status": "processed"}, auth=admin_auth(),
    )
    assert response.status_code == 422


async def test_draft_from_candidate_preserves_provenance(
    client: AsyncClient, monkeypatch, sources
) -> None:
    """Conversion carries the source across and writes no prose."""
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())

    item = (await client.get(
        "/api/v1/admin/news/incoming?status=candidate", auth=admin_auth()
    )).json()[0]

    draft = (await client.post(
        f"/api/v1/admin/news/incoming/{item['id']}/draft", auth=admin_auth()
    )).json()

    assert draft["status"] == "draft"
    # Phase 2 writes no prose and no impact: both are the editor's job.
    assert draft["whatHappened"] == ""
    assert draft["whyItMattersForJobs"] == ""
    assert draft["impactLevel"] is None
    assert draft["impactScore"] is None
    assert draft["generationProvider"] is None

    # Provenance survived the conversion.
    assert draft["sources"], "the candidate's source must be attached to the draft"
    assert draft["sources"][0]["sourceUrl"] == item["externalUrl"]
    assert draft["sources"][0]["originalTitle"] == item["originalTitle"]
    assert draft["sources"][0]["isPrimary"] is True

    # The candidate is now processed, and the unpublished draft stays invisible publicly.
    after = (await client.get(
        f"/api/v1/admin/news/incoming/{item['id']}", auth=admin_auth()
    )).json()
    assert after["status"] == "processed"
    assert (await client.get(f"/api/v1/news/{draft['slug']}")).status_code == 404


async def test_manual_trigger_reports_skipped_when_disabled(
    client: AsyncClient, monkeypatch, sources
) -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "false")
    get_settings.cache_clear()
    body = (await client.post("/api/v1/admin/news/ingest/run", auth=admin_auth())).json()
    assert body["status"] == "skipped"


async def test_ingestion_never_touches_occupation_scoring(monkeypatch, sources) -> None:
    """The Phase 1 separation guarantee, re-asserted for the Phase 2 pipeline."""
    async def snapshot() -> dict:
        async with SessionFactory() as session:
            return dict((await session.execute(text("""
              SELECT (SELECT count(*) FROM occupation_scores) legacy,
                     (SELECT count(*) FROM production_occupation_score_snapshots) snapshots,
                     (SELECT count(*) FROM occupation_publications
                        WHERE activation_status='public') public_occupations,
                     (SELECT count(*) FROM production_promotion_runs) runs,
                     (SELECT version FROM scoring_model_versions WHERE is_active) model
            """))).mappings().one())

    before = await snapshot()
    enable_news(monkeypatch, news_lookback_hours=87600)
    async with SessionFactory() as session:
        await run_ingestion(session, triggered_by="pytest", fetcher=fetcher())
    assert await snapshot() == before
