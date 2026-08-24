"""Phase 4 Step 3 — archive, restore and regenerate.

Two properties carry most of the weight:

  * archiving is not rejecting — it preserves `published_at`, because an article that was
    published genuinely was, and erasing that falsifies the record;
  * regenerating rewrites in place — the "one candidate, one article" rule must not acquire
    an exception.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.generation import GeneratedBrief
from app.news.generation_service import generate_for_candidate, regenerate_article
from app.repositories import news as repo

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE = "Editorial Fixture Lab"
FACTORS = {"capability_advancement": 60, "commercial_deployability": 60,
           "breadth_of_affected_work": 60, "adoption_speed": 60,
           "human_work_reduction_potential": 60}   # -> 60.0, medium


def brief(**overrides) -> GeneratedBrief:
    base = dict(
        is_ai_news=True, ai_relevance_confidence=0.95, relevance_reason="Capability release.",
        headline="First generated headline",
        what_happened="A vendor shipped a capability.",
        why_it_matters_for_jobs="Some tasks are affected.",
        tags=["AI Agents"], job_areas=["Software Development"],
        factors=dict(FACTORS), impact_confidence=0.9, impact_reasoning="Reasoning.",
    )
    return GeneratedBrief(**(base | overrides))


class FakeProvider:
    name, model = "editorial-fake", "fake-1"

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self._result = result if result is not None else brief()
        self._error = error
        self.calls = 0

    def generate_news_brief(self, payload):
        self.calls += 1
        if self._error:
            raise self._error
        return self._result


def admin_auth() -> tuple[str, str]:
    return os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too")


def enable(monkeypatch, generation: str = "true") -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "true")
    monkeypatch.setenv("NEWS_GENERATION_ENABLED", generation)
    get_settings.cache_clear()


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text("""
          DELETE FROM news_articles WHERE id IN (
            SELECT link.article_id FROM news_article_sources link
            JOIN news_ingest_items i ON i.id = link.ingest_item_id
            JOIN news_sources src ON src.id = i.source_id WHERE src.name = :n)
        """), {"n": SOURCE})
        await s.execute(text("DELETE FROM news_articles WHERE headline LIKE 'Editorial fixture%'"))
        await s.execute(text(
            "DELETE FROM news_ingest_items WHERE source_id IN "
            "(SELECT id FROM news_sources WHERE name = :n)"), {"n": SOURCE})
        await s.execute(text("DELETE FROM news_sources WHERE name = :n"), {"n": SOURCE})


@pytest_asyncio.fixture(loop_scope="session")
async def candidate():
    """One ingest candidate ready to generate from."""
    await _cleanup()
    async with SessionFactory() as s, s.begin():
        src = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES (:n, 'https://ed.test/rss.xml', 'https://ed.test', 'primary', 1, 'rss', false)
          RETURNING id"""), {"n": SOURCE})).scalar_one()
        item = (await s.execute(text("""
          INSERT INTO news_ingest_items (source_id, external_url, canonical_url,
            original_title, original_excerpt, source_published_at, content_hash, status,
            relevance_score, relevance_policy_version, relevance_signals, title_fingerprint)
          VALUES (:src, 'https://ed.test/a', 'https://ed.test/a', 'Editorial source title',
            'An excerpt.', now(),
            'ed00000000000000000000000000000000000000000000000000000000000000',
            'candidate', 80, 'news-relevance-v1', '{"aiTerms":["ai agent"]}'::jsonb,
            'editorial source title')
          RETURNING id"""), {"src": src})).scalar_one()
    try:
        yield item
    finally:
        await _cleanup()
        get_settings.cache_clear()


async def _article_row(article_id: int) -> dict:
    async with SessionFactory() as s:
        return dict((await s.execute(text("""
          SELECT status, published_at, archived_at, archived_by, archive_reason,
                 regenerated_at, regeneration_count, headline, impact_overridden_at
          FROM news_articles WHERE id = :id"""), {"id": article_id})).mappings().one())


# ------------------------------------------------------------------------------- archive


async def test_archiving_preserves_published_at_where_rejecting_clears_it(
    client: AsyncClient, monkeypatch, candidate
) -> None:
    """The distinction the new status exists to carry."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidate, FakeProvider())
    article_id = outcome.article_id

    await client.post(f"/api/v1/admin/news/{article_id}/publish", auth=admin_auth())
    published = await _article_row(article_id)
    assert published["status"] == "published" and published["published_at"] is not None

    archived = (await client.post(
        f"/api/v1/admin/news/{article_id}/archive",
        json={"reason": "Superseded by a later release"}, auth=admin_auth(),
    )).json()

    assert archived["status"] == "archived"
    row = await _article_row(article_id)
    assert row["published_at"] is not None, (
        "archiving must keep the record that this was published; rejecting is the action "
        "that treats an item as something that should never have gone out"
    )
    assert row["archived_at"] is not None
    assert row["archived_by"].startswith("admin:")
    assert row["archive_reason"] == "Superseded by a later release"


async def test_archived_article_leaves_the_public_site_immediately(
    client: AsyncClient, monkeypatch, candidate
) -> None:
    """No separate unpublish: the reader predicate admits only `published`."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidate, FakeProvider())
    article_id = outcome.article_id
    slug = (await client.get(f"/api/v1/admin/news/{article_id}", auth=admin_auth())).json()["slug"]

    await client.post(f"/api/v1/admin/news/{article_id}/publish", auth=admin_auth())
    assert (await client.get(f"/api/v1/news/{slug}")).status_code == 200

    await client.post(f"/api/v1/admin/news/{article_id}/archive", auth=admin_auth())
    assert (await client.get(f"/api/v1/news/{slug}")).status_code == 404
    assert slug not in [a["slug"] for a in (await client.get("/api/v1/news?limit=100")).json()]
    assert slug not in [e["slug"] for e in (await client.get("/api/v1/news/sitemap")).json()]


async def test_restore_returns_to_review_never_straight_to_public(
    client: AsyncClient, monkeypatch, candidate
) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidate, FakeProvider())
    article_id = outcome.article_id

    await client.post(f"/api/v1/admin/news/{article_id}/publish", auth=admin_auth())
    await client.post(f"/api/v1/admin/news/{article_id}/archive", auth=admin_auth())
    restored = (await client.post(
        f"/api/v1/admin/news/{article_id}/restore", auth=admin_auth())).json()

    assert restored["status"] == "review_required", (
        "time has passed; an article worth un-retiring is worth a second look"
    )
    row = await _article_row(article_id)
    assert row["archived_at"] is None and row["archived_by"] is None


async def test_set_status_refuses_to_archive_without_an_actor(monkeypatch, candidate) -> None:
    """A helper taking only a status string cannot record who archived it."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidate, FakeProvider())
        with pytest.raises(repo.NewsPublicationRefused):
            await repo.set_status(s, outcome.article_id, "archived")
        await s.rollback()


async def test_archive_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/admin/news/1/archive")).status_code == 401
    assert (await client.post("/api/v1/admin/news/1/restore")).status_code == 401
    assert (await client.post("/api/v1/admin/news/1/regenerate")).status_code == 401


# ---------------------------------------------------------------------------- regenerate


async def test_regeneration_rewrites_in_place_and_creates_no_second_article(
    monkeypatch, candidate
) -> None:
    """"One candidate, one article" must not acquire an exception."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
        second = await regenerate_article(
            s, first.article_id,
            FakeProvider(brief(headline="Second generated headline",
                               what_happened="A revised account.")),
        )
        total = (await s.execute(text("""
          SELECT count(*) FROM news_article_sources WHERE ingest_item_id = :id
        """), {"id": candidate})).scalar_one()

    assert second.outcome == "accepted"
    assert second.article_id == first.article_id, "it must update, not create"
    assert total == 1, "the candidate must still map to exactly one article"

    row = await _article_row(first.article_id)
    assert row["headline"] == "Second generated headline"
    assert row["regeneration_count"] == 1
    assert row["regenerated_at"] is not None


async def test_regeneration_clears_a_stale_editorial_override(
    client: AsyncClient, monkeypatch, candidate
) -> None:
    """An override was a judgement about prose that no longer exists."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())

    await client.post(f"/api/v1/admin/news/{first.article_id}/impact/override",
                      json={"impactLevel": "high", "reason": "Editor judgement"},
                      auth=admin_auth())
    assert (await _article_row(first.article_id))["impact_overridden_at"] is not None

    async with SessionFactory() as s:
        await regenerate_article(s, first.article_id,
                                 FakeProvider(brief(headline="Rewritten")))

    row = await _article_row(first.article_id)
    assert row["impact_overridden_at"] is None, (
        "carrying an override onto new text would attribute an editor's decision to prose "
        "they never read"
    )


async def test_published_articles_cannot_be_regenerated(
    client: AsyncClient, monkeypatch, candidate
) -> None:
    """Rewriting in place would silently change what readers are already served."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
    await client.post(f"/api/v1/admin/news/{first.article_id}/publish", auth=admin_auth())

    provider = FakeProvider(brief(headline="Should never appear"))
    async with SessionFactory() as s:
        outcome = await regenerate_article(s, first.article_id, provider)

    assert outcome.outcome == "skipped"
    assert "Archive or unpublish first" in (outcome.error or "")
    assert provider.calls == 0, "a refused regeneration must cost no quota"
    assert (await _article_row(first.article_id))["headline"] == "First generated headline"


async def test_regeneration_is_refused_when_generation_is_disabled(
    monkeypatch, candidate
) -> None:
    enable(monkeypatch, generation="true")
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())

    enable(monkeypatch, generation="false")
    provider = FakeProvider()
    async with SessionFactory() as s:
        outcome = await regenerate_article(s, first.article_id, provider)

    assert outcome.outcome == "skipped"
    assert "NEWS_GENERATION_ENABLED is false" in (outcome.error or "")
    assert provider.calls == 0


async def test_regeneration_respects_the_daily_cap(monkeypatch, candidate) -> None:
    """A regenerated brief costs a call like any other."""
    from app.news.generation_service import _todays_call_count

    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
        already = await _todays_call_count(s)

    monkeypatch.setenv("NEWS_DAILY_GENERATION_LIMIT", str(already))
    get_settings.cache_clear()
    provider = FakeProvider()
    async with SessionFactory() as s:
        outcome = await regenerate_article(s, first.article_id, provider)

    assert outcome.outcome == "skipped"
    assert "Daily generation limit reached" in (outcome.error or "")
    assert provider.calls == 0


async def test_a_hand_written_article_cannot_be_regenerated(
    client: AsyncClient, monkeypatch
) -> None:
    """There is no source candidate to regenerate from; those are edited instead."""
    enable(monkeypatch)
    created = (await client.post("/api/v1/admin/news", json={
        "headline": "Editorial fixture: hand written",
        "whatHappened": "Written by an editor.",
        "whyItMattersForJobs": "Explained by an editor.",
    }, auth=admin_auth())).json()
    try:
        provider = FakeProvider()
        async with SessionFactory() as s:
            outcome = await regenerate_article(s, created["id"], provider)
        assert outcome.outcome == "skipped"
        assert "no source candidate" in (outcome.error or "")
        assert provider.calls == 0
    finally:
        async with SessionFactory() as s, s.begin():
            await s.execute(text("DELETE FROM news_articles WHERE id = :id"),
                            {"id": created["id"]})


async def test_a_regeneration_that_now_rejects_leaves_the_article_untouched(
    monkeypatch, candidate
) -> None:
    """Deleting an editor's article because a second call disagreed is not an automatic
    decision to make."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
        outcome = await regenerate_article(s, first.article_id, FakeProvider(
            GeneratedBrief(is_ai_news=False, ai_relevance_confidence=0.9,
                           relevance_reason="On reflection, not AI news."),
        ))

    assert outcome.outcome == "rejected"
    row = await _article_row(first.article_id)
    assert row["headline"] == "First generated headline"
    assert row["status"] != "archived"


async def test_a_failed_regeneration_leaves_the_article_intact(monkeypatch, candidate) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
        outcome = await regenerate_article(
            s, first.article_id, FakeProvider(error=RuntimeError("provider exploded")))

    assert outcome.outcome == "failed"
    row = await _article_row(first.article_id)
    assert row["headline"] == "First generated headline"
    assert row["regeneration_count"] == 0


async def test_regenerated_articles_are_never_published_automatically(
    monkeypatch, candidate
) -> None:
    enable(monkeypatch)
    monkeypatch.setenv("NEWS_AUTO_PUBLISH", "true")
    get_settings.cache_clear()
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidate, FakeProvider())
        outcome = await regenerate_article(
            s, first.article_id, FakeProvider(brief(impact_confidence=0.5)))

    assert outcome.article_status == "review_required"
    assert (await _article_row(first.article_id))["status"] != "published"
    get_settings.cache_clear()
