"""Phase 4 Step 1 — ingestion and generation are gated independently.

The state that matters is the middle one: ingestion running while generation is off. Under a
single flag that was inexpressible, so enabling feed polling in production also armed the
admin Generate button against a live, billed API key.

These tests prove each case end to end rather than by reading configuration, because the
question is not "is the flag false" but "did a provider get called".
"""

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.session import SessionFactory
from app.news.feeds import parse_feed
from app.news.generation import GeneratedBrief
from app.news.generation_service import generate_for_candidate, run_generation_batch
from app.news.ingestion import run_ingestion
from tests.fixtures.feeds import RSS_VALID

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE = "Flag Fixture Lab"
FEED = "https://flags.test/rss.xml"


class CountingFetcher:
    """Records whether a feed was opened at all."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_entries(self, feed_url: str, source_id: int):
        self.calls.append(feed_url)
        return parse_feed(source_id, RSS_VALID)


class CountingProvider:
    """Records whether the language model was reached at all."""

    name, model = "counting-fake", "fake-1"

    def __init__(self) -> None:
        self.calls = 0

    def generate_news_brief(self, payload):
        self.calls += 1
        return GeneratedBrief(
            is_ai_news=True, ai_relevance_confidence=0.95,
            relevance_reason="Capability release.",
            headline="A capability shipped", what_happened="A vendor shipped something.",
            why_it_matters_for_jobs="Some tasks are affected.",
            tags=["AI Agents"], job_areas=["Software Development"],
            factors={"capability_advancement": 60, "commercial_deployability": 60,
                     "breadth_of_affected_work": 60, "adoption_speed": 60,
                     "human_work_reduction_potential": 60},
            impact_confidence=0.9, impact_reasoning="Reasoning.",
        )


def flags(monkeypatch, *, ingestion=None, generation=None, legacy=None) -> None:
    """Set only the flags a case is about; unset the rest so nothing leaks in."""
    for name in ("NEWS_INGESTION_ENABLED", "NEWS_GENERATION_ENABLED", "NEWS_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    if ingestion is not None:
        monkeypatch.setenv("NEWS_INGESTION_ENABLED", str(ingestion).lower())
    if generation is not None:
        monkeypatch.setenv("NEWS_GENERATION_ENABLED", str(generation).lower())
    if legacy is not None:
        monkeypatch.setenv("NEWS_ENABLED", str(legacy).lower())
    get_settings.cache_clear()


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text("""
          DELETE FROM news_articles WHERE id IN (
            SELECT link.article_id FROM news_article_sources link
            JOIN news_ingest_items i ON i.id = link.ingest_item_id
            JOIN news_sources src ON src.id = i.source_id WHERE src.name = :n)
        """), {"n": SOURCE})
        await s.execute(text(
            "DELETE FROM news_ingest_items WHERE source_id IN "
            "(SELECT id FROM news_sources WHERE name = :n)"), {"n": SOURCE})
        await s.execute(text("DELETE FROM news_sources WHERE name = :n"), {"n": SOURCE})
        await s.execute(text(
            "DELETE FROM news_ingestion_runs WHERE triggered_by LIKE 'flagtest%'"))
        await s.execute(text(
            "DELETE FROM news_generation_runs WHERE triggered_by LIKE 'flagtest%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def flag_source():
    """One enabled source; every other source is parked so runs are deterministic."""
    await _cleanup()
    parked: list[int] = []
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(
            text("SELECT id FROM news_sources WHERE enabled")
        )).scalars().all())
        if parked:
            await s.execute(
                text("UPDATE news_sources SET enabled=false WHERE id = ANY(:ids)"),
                {"ids": parked})
        await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES (:n, :u, 'https://flags.test', 'primary', 1, 'rss', true)
        """), {"n": SOURCE, "u": FEED})
    try:
        yield
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(
                    text("UPDATE news_sources SET enabled=true WHERE id = ANY(:ids)"),
                    {"ids": parked})
        get_settings.cache_clear()


async def _candidate_count() -> int:
    async with SessionFactory() as s:
        return (await s.execute(text("""
          SELECT count(*) FROM news_ingest_items i JOIN news_sources src ON src.id=i.source_id
          WHERE src.name = :n"""), {"n": SOURCE})).scalar_one()


# ------------------------------------------------------------------------------ defaults


async def test_both_pipelines_default_to_disabled(monkeypatch) -> None:
    """A fresh environment inherits nothing. Enabling either is deliberate."""
    flags(monkeypatch)
    settings = get_settings()
    assert settings.ingestion_enabled is False
    assert settings.generation_enabled is False
    assert settings.news_auto_publish is False
    assert settings.uses_legacy_news_flag is False


# ------------------------------------------------ CASE 1: ingestion disabled


async def test_case1_ingestion_disabled_runs_nothing(monkeypatch, flag_source) -> None:
    """No job executes, no feed is opened, no candidate is created, no run row is written."""
    flags(monkeypatch, ingestion=False, generation=False)
    fetcher = CountingFetcher()

    async with SessionFactory() as s:
        result = await run_ingestion(s, triggered_by="flagtest", fetcher=fetcher)
        runs = (await s.execute(text(
            "SELECT count(*) FROM news_ingestion_runs WHERE triggered_by LIKE 'flagtest%'"
        ))).scalar_one()

    assert result.status == "skipped"
    assert result.skipped_reason == "NEWS_INGESTION_ENABLED is false"
    assert result.run_id is None
    assert fetcher.calls == [], "a disabled pipeline must not open a feed"
    assert await _candidate_count() == 0
    assert runs == 0, "a skipped run must not write a run row"


async def test_case1_the_gate_the_enqueue_helpers_consult_is_closed(monkeypatch) -> None:
    """`worker.news_jobs.enqueue_ingestion` returns None on this condition.

    The worker package is not on the backend test image's path — the Dockerfile copies app,
    tests, scoring, ingestion and enrichment, but not worker — so the gate it reads is
    asserted here rather than mounting a second package for one call.
    """
    flags(monkeypatch, ingestion=False)
    assert get_settings().ingestion_enabled is False


# ------------------------------- CASE 2: ingestion on, generation off (the important one)


async def test_case2_candidates_are_created_but_nothing_is_generated(
    monkeypatch, flag_source
) -> None:
    """The state a single flag could not express.

    Fetch, normalise, deduplicate and store all run. No provider call is made and no article
    exists afterwards.
    """
    flags(monkeypatch, ingestion=True, generation=False)
    fetcher = CountingFetcher()
    provider = CountingProvider()

    async with SessionFactory() as s:
        ingest = await run_ingestion(
            s, triggered_by="flagtest", fetcher=fetcher, lookback_hours=87600
        )

    assert ingest.status == "completed"
    assert fetcher.calls == [FEED], "the feed must have been fetched"
    assert ingest.counters.items_new > 0, "candidates must be stored"
    assert await _candidate_count() > 0

    # Now prove the generation half is genuinely closed, through both entry points.
    async with SessionFactory() as s:
        item_id = (await s.execute(text("""
          SELECT i.id FROM news_ingest_items i JOIN news_sources src ON src.id=i.source_id
          WHERE src.name=:n AND i.status='candidate' LIMIT 1"""), {"n": SOURCE})).scalar_one()

        single = await generate_for_candidate(s, item_id, provider)
        batch = await run_generation_batch(s, triggered_by="flagtest", provider=provider)

        articles = (await s.execute(text("""
          SELECT count(*) FROM news_article_sources link
          JOIN news_ingest_items i ON i.id = link.ingest_item_id
          JOIN news_sources src ON src.id = i.source_id WHERE src.name = :n
        """), {"n": SOURCE})).scalar_one()

    assert provider.calls == 0, "generation disabled means the model is never reached"
    assert single.outcome == "skipped"
    assert "NEWS_GENERATION_ENABLED is false" in (single.error or "")
    assert batch.status == "skipped"
    assert batch.skipped_reason == "NEWS_GENERATION_ENABLED is false"
    assert articles == 0, "no article may exist while generation is disabled"


async def test_case2_the_two_gates_are_independent(monkeypatch) -> None:
    """Ingestion open, generation closed — the state the single flag could not express."""
    flags(monkeypatch, ingestion=True, generation=False)
    settings = get_settings()
    assert settings.ingestion_enabled is True
    assert settings.generation_enabled is False
    # And the reverse, to prove neither is derived from the other.
    flags(monkeypatch, ingestion=False, generation=True)
    settings = get_settings()
    assert settings.ingestion_enabled is False
    assert settings.generation_enabled is True


# --------------------------------------------------- CASE 3: generation enabled


async def test_case3_generation_runs_when_enabled(monkeypatch, flag_source) -> None:
    flags(monkeypatch, ingestion=True, generation=True)
    provider = CountingProvider()

    async with SessionFactory() as s:
        await run_ingestion(s, triggered_by="flagtest", fetcher=CountingFetcher(),
                            lookback_hours=87600)
        item_id = (await s.execute(text("""
          SELECT i.id FROM news_ingest_items i JOIN news_sources src ON src.id=i.source_id
          WHERE src.name=:n AND i.status='candidate' LIMIT 1"""), {"n": SOURCE})).scalar_one()
        outcome = await generate_for_candidate(s, item_id, provider)

    assert provider.calls == 1
    assert outcome.outcome == "accepted"
    assert outcome.article_status in {"draft", "review_required"}


# ------------------------------------------------- CASE 4: auto publish stays off


async def test_case4_nothing_publishes_automatically(monkeypatch, flag_source) -> None:
    """Even with both pipelines on and NEWS_AUTO_PUBLISH forced true."""
    flags(monkeypatch, ingestion=True, generation=True)
    monkeypatch.setenv("NEWS_AUTO_PUBLISH", "true")
    get_settings.cache_clear()
    assert get_settings().news_auto_publish is True

    async with SessionFactory() as s:
        await run_ingestion(s, triggered_by="flagtest", fetcher=CountingFetcher(),
                            lookback_hours=87600)
        item_id = (await s.execute(text("""
          SELECT i.id FROM news_ingest_items i JOIN news_sources src ON src.id=i.source_id
          WHERE src.name=:n AND i.status='candidate' LIMIT 1"""), {"n": SOURCE})).scalar_one()
        outcome = await generate_for_candidate(s, item_id, CountingProvider())
        published = (await s.execute(text("""
          SELECT count(*) FROM news_articles WHERE status = 'published'
        """))).scalar_one()

    assert outcome.article_status != "published"
    assert published == 0
    get_settings.cache_clear()


# ------------------------------------------------------ legacy compatibility


async def test_legacy_flag_still_drives_both_pipelines(monkeypatch) -> None:
    """An environment that only sets NEWS_ENABLED keeps behaving exactly as it did.

    Failing closed here would have been a silent behaviour change for anyone already running
    with NEWS_ENABLED=true, which is the one thing the migration must not do.
    """
    flags(monkeypatch, legacy=True)
    settings = get_settings()
    assert settings.ingestion_enabled is True
    assert settings.generation_enabled is True
    assert settings.uses_legacy_news_flag is True

    flags(monkeypatch, legacy=False)
    settings = get_settings()
    assert settings.ingestion_enabled is False
    assert settings.generation_enabled is False


async def test_explicit_flags_override_the_legacy_one(monkeypatch) -> None:
    """The split flags win, so an operator can narrow a legacy environment without
    first removing the old variable."""
    flags(monkeypatch, ingestion=True, generation=False, legacy=True)
    settings = get_settings()
    assert settings.ingestion_enabled is True
    assert settings.generation_enabled is False, "explicit generation=false must win"

    flags(monkeypatch, ingestion=False, legacy=True)
    settings = get_settings()
    assert settings.ingestion_enabled is False, "explicit ingestion=false must win"
    assert settings.generation_enabled is True, "generation still falls back to the legacy flag"


async def test_unset_legacy_flag_is_not_treated_as_false_by_accident(monkeypatch) -> None:
    """`None` and `False` are different: only the Optional type keeps 'explicitly set'
    distinguishable from 'left at default'."""
    flags(monkeypatch)
    assert get_settings().news_enabled is None
    assert get_settings().uses_legacy_news_flag is False
