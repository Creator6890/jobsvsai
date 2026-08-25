"""Phase 3 orchestration against the database, with a fake provider.

No test reaches Gemini. The provider is injected, so every branch — accept, reject, fail,
duplicate, limit — is exercised deterministically.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.generation import SEMANTIC_POLICY_VERSION, GeneratedBrief, ProviderNotConfigured
from app.news.generation_service import (
    decide_status,
    generate_for_candidate,
    run_generation_batch,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

FACTORS = {
    "capability_advancement": 84, "commercial_deployability": 88,
    "breadth_of_affected_work": 71, "adoption_speed": 82,
    "human_work_reduction_potential": 65,
}  # -> 80.2, high


def brief(**overrides) -> GeneratedBrief:
    base = dict(
        is_ai_news=True, ai_relevance_confidence=0.94,
        relevance_reason="Capability release.",
        headline="Lab expands autonomous coding capabilities",
        what_happened="A vendor shipped an agent that completes multi-step coding tasks.",
        why_it_matters_for_jobs="Routine implementation work is directly exposed.",
        tags=["AI Agents", "Coding"], job_areas=["Software Development"],
        factors=dict(FACTORS), impact_confidence=0.91,
        impact_reasoning="Broad deployment surface.",
        input_tokens=1200, output_tokens=340,
    )
    return GeneratedBrief(**(base | overrides))


class FakeProvider:
    name = "fake"
    model = "fake-1"

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


def enable(monkeypatch, **overrides) -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "true")
    monkeypatch.setenv("NEWS_GENERATION_ENABLED", "true")
    for k, v in overrides.items():
        monkeypatch.setenv(k.upper(), str(v))
    get_settings.cache_clear()


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text("""
          DELETE FROM news_articles WHERE id IN (
            SELECT link.article_id FROM news_article_sources link
            JOIN news_ingest_items i ON i.id = link.ingest_item_id
            JOIN news_sources src ON src.id = i.source_id WHERE src.name LIKE 'Gen %')
        """))
        await s.execute(text("""
          DELETE FROM news_ingest_items WHERE source_id IN (
            SELECT id FROM news_sources WHERE name LIKE 'Gen %')
        """))
        await s.execute(text("DELETE FROM news_sources WHERE name LIKE 'Gen %'"))
        await s.execute(text(
            "DELETE FROM news_generation_runs WHERE triggered_by LIKE 'pytest%' "
            "OR triggered_by LIKE 'admin:%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def candidates():
    """Three candidates from one source, highest deterministic score first.

    Any pre-existing candidate is parked as `new` for the duration and restored afterwards.
    Without that, `select_generation_candidates` takes the top of the *whole* queue, so a
    database holding real ingested items — which is exactly what a supervised validation
    leaves behind — would have those items generated against by the test suite. The tests
    must own every row they touch.
    """
    await _cleanup()
    ids: list[int] = []
    parked: list[int] = []
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(text(
            "SELECT id FROM news_ingest_items WHERE status = 'candidate'"
        ))).scalars().all())
        if parked:
            await s.execute(
                text("UPDATE news_ingest_items SET status='new' WHERE id = ANY(:ids)"),
                {"ids": parked},
            )
    async with SessionFactory() as s, s.begin():
        source_id = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES ('Gen Fixture Lab', 'https://gen.test/rss.xml', 'https://gen.test',
                  'primary', 1, 'rss', false)
          RETURNING id
        """))).scalar_one()
        for n, score in ((1, 90), (2, 70), (3, 45)):
            ids.append((await s.execute(text("""
              INSERT INTO news_ingest_items
                (source_id, external_url, canonical_url, original_title, original_excerpt,
                 source_published_at, content_hash, status, relevance_score,
                 relevance_policy_version, relevance_signals, title_fingerprint)
              VALUES (:src, :url, :url, :title, 'An excerpt for generation.',
                      now() - make_interval(hours => :n), :hash, 'candidate', :score,
                      'news-relevance-v1', '{"aiTerms":["ai agent"]}'::jsonb, :fp)
              RETURNING id
            """), {"src": source_id, "url": f"https://gen.test/item-{n}",
                   "title": f"Gen fixture item {n}", "hash": f"{n:064d}",
                   "n": n, "score": score, "fp": f"gen fixture item {n}"})).scalar_one())
    try:
        yield ids
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(
                    text("UPDATE news_ingest_items SET status='candidate' WHERE id = ANY(:ids)"),
                    {"ids": parked},
                )
        get_settings.cache_clear()


# ------------------------------------------------------------------------ status routing


@pytest.mark.asyncio(loop_scope="session")
async def test_status_routing_never_yields_published() -> None:
    assert decide_status(brief()) == "draft"
    # Weak semantic confidence -> a human looks first.
    assert decide_status(brief(ai_relevance_confidence=0.55)) == "review_required"
    # Weak impact confidence -> same, via the Phase 1 rule.
    assert decide_status(brief(impact_confidence=0.5)) == "review_required"
    for b in (brief(), brief(ai_relevance_confidence=0.1), brief(impact_confidence=0.0)):
        assert decide_status(b) in {"draft", "review_required"}


async def test_confident_acceptance_creates_a_draft(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    provider = FakeProvider()
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], provider)

    assert outcome.outcome == "accepted"
    assert outcome.article_status == "draft"
    # The deterministic policy computed the level; the model never supplied one.
    assert outcome.impact_score == 80.2 and outcome.impact_level == "high"
    assert provider.calls == 1, "one candidate must cost exactly one call"


async def test_low_impact_confidence_routes_to_review(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], FakeProvider(brief(impact_confidence=0.5))
        )
    assert outcome.article_status == "review_required"


async def test_low_semantic_confidence_routes_to_review(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], FakeProvider(brief(ai_relevance_confidence=0.55))
        )
    assert outcome.article_status == "review_required"


async def test_rejection_creates_no_article_and_keeps_the_verdict(
    monkeypatch, candidates
) -> None:
    enable(monkeypatch)
    rejection = GeneratedBrief(
        is_ai_news=False, ai_relevance_confidence=0.88,
        relevance_reason="Funding round with no capability change.",
    )
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], FakeProvider(rejection))
        row = (await s.execute(text("""
          SELECT status, is_ai_news, ai_relevance_confidence, ai_relevance_reason,
                 semantic_policy_version, generation_provider,
                 (SELECT count(*) FROM news_article_sources l WHERE l.ingest_item_id = :id) links
          FROM news_ingest_items WHERE id = :id
        """), {"id": candidates[0]})).mappings().one()

    assert outcome.outcome == "rejected" and outcome.article_id is None
    assert row["links"] == 0, "a rejected candidate must produce no article"
    assert row["status"] == "ignored"
    # Rejection provenance is the most useful record for calibrating the prompt.
    assert row["is_ai_news"] is False
    assert float(row["ai_relevance_confidence"]) == 0.88
    assert row["ai_relevance_reason"].startswith("Funding round")
    assert row["semantic_policy_version"] == SEMANTIC_POLICY_VERSION


# ------------------------------------------------- the three semantic routing paths
#
# One test per path, named for the outcome, so a regression in routing is legible from the
# failure line alone rather than from a parametrised case id.


async def test_path_1_high_confidence_ai_article_becomes_draft(monkeypatch, candidates) -> None:
    """Confident on both axes: no human needed before an editor picks it up normally."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0],
            FakeProvider(brief(ai_relevance_confidence=0.95, impact_confidence=0.91)),
        )
        row = (await s.execute(text(
            "SELECT status, is_ai_news, ai_relevance_confidence FROM news_ingest_items WHERE id=:id"
        ), {"id": candidates[0]})).mappings().one()

    assert outcome.outcome == "accepted"
    assert outcome.article_status == "draft"
    assert row["status"] == "processed"
    assert row["is_ai_news"] is True


async def test_path_2_non_ai_article_is_rejected_with_no_article(
    monkeypatch, candidates
) -> None:
    """Rejected outright. No article exists to review, and the verdict is retained."""
    enable(monkeypatch)
    rejection = GeneratedBrief(
        is_ai_news=False, ai_relevance_confidence=0.95,
        relevance_reason="Advertising rollout, not a capability change.",
    )
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], FakeProvider(rejection))
        row = (await s.execute(text("""
          SELECT status, is_ai_news, ai_relevance_reason,
                 (SELECT count(*) FROM news_article_sources l WHERE l.ingest_item_id=:id) links
          FROM news_ingest_items WHERE id = :id
        """), {"id": candidates[0]})).mappings().one()

    assert outcome.outcome == "rejected"
    assert outcome.article_id is None
    assert row["links"] == 0
    assert row["status"] == "ignored"
    assert row["is_ai_news"] is False
    assert "Advertising rollout" in row["ai_relevance_reason"]


async def test_path_3_ambiguous_article_becomes_review_required(
    monkeypatch, candidates
) -> None:
    """Accepted, but the model was not sure it was AI news. A human decides.

    This is the path the supervised live run never exercised - every real verdict came back
    at 0.95 - so it is pinned here rather than assumed.
    """
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0],
            # Below MINIMUM_SEMANTIC_CONFIDENCE (0.70) but confident about the factors, so
            # only the semantic axis is what routes it to review.
            FakeProvider(brief(ai_relevance_confidence=0.62, impact_confidence=0.95)),
        )
    assert outcome.outcome == "accepted"
    assert outcome.article_status == "review_required"
    assert outcome.ai_relevance_confidence == 0.62


async def test_semantic_confidence_boundary_is_exact(monkeypatch, candidates) -> None:
    """0.70 is inclusive: at the threshold the article is a draft, just below it is review."""
    from app.news.generation import MINIMUM_SEMANTIC_CONFIDENCE

    assert MINIMUM_SEMANTIC_CONFIDENCE == 0.70
    assert decide_status(brief(ai_relevance_confidence=0.70)) == "draft"
    assert decide_status(brief(ai_relevance_confidence=0.699)) == "review_required"


async def test_either_confidence_alone_forces_review(monkeypatch, candidates) -> None:
    """The two confidences answer different questions; either being weak is enough."""
    # Semantic weak, impact strong.
    assert decide_status(brief(ai_relevance_confidence=0.4, impact_confidence=0.99)) == "review_required"
    # Impact weak, semantic strong.
    assert decide_status(brief(ai_relevance_confidence=0.99, impact_confidence=0.4)) == "review_required"
    # Both weak.
    assert decide_status(brief(ai_relevance_confidence=0.4, impact_confidence=0.4)) == "review_required"


async def test_auto_publish_stays_false_and_is_never_consulted_to_publish(
    monkeypatch, candidates
) -> None:
    """Even with NEWS_AUTO_PUBLISH forced true, generation cannot publish.

    The setting exists as a declaration of intent, not as a switch generation reads. Nothing
    in the generation path branches on it, which is what this asserts.
    """
    enable(monkeypatch, news_auto_publish="true")
    assert get_settings().news_auto_publish is True

    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], FakeProvider())
        status = (await s.execute(text("SELECT status FROM news_articles WHERE id=:id"),
                                  {"id": outcome.article_id})).scalar_one()
    assert status == "draft", "generation must never publish, whatever the flag says"
    assert outcome.article_status != "published"
    get_settings.cache_clear()


async def test_safe_production_defaults(monkeypatch) -> None:
    """Sized from the live run, where the free tier stalled at roughly three calls."""
    # Every NEWS_* override is removed so this reads the code defaults, not whatever the
    # developer's environment happens to set. Without the delenv the assertions would pass or
    # fail depending on a local .env, which is not what "default" means.
    for name in ("NEWS_DAILY_GENERATION_LIMIT", "NEWS_GENERATION_BATCH_SIZE",
                 "NEWS_AUTO_PUBLISH", "NEWS_ENABLED", "NEWS_INGESTION_ENABLED",
                 "NEWS_GENERATION_ENABLED", "NEWS_LLM_PROVIDER",
                 "NEWS_LLM_API_KEY", "NEWS_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.news_daily_generation_limit == 5
    assert settings.news_generation_batch_size == 2
    # Generation is off, unattended publishing is off, and no provider is wired by default.
    assert settings.news_auto_publish is False
    assert settings.ingestion_enabled is False
    assert settings.generation_enabled is False
    assert settings.news_llm_provider == "null"
    get_settings.cache_clear()


# --------------------------------------------------------------------------- provenance


async def test_provenance_is_persisted_on_the_article(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], FakeProvider())
        row = (await s.execute(text("""
          SELECT generation_provider, generation_model, generation_prompt_version,
                 generated_at, impact_policy_version, impact_confidence, impact_reasoning,
                 automated_impact_score, automated_impact_level, status,
                 (SELECT count(*) FROM news_article_sources l WHERE l.article_id = a.id) sources
          FROM news_articles a WHERE a.id = :id
        """), {"id": outcome.article_id})).mappings().one()

    assert row["generation_provider"] == "fake"
    assert row["generation_model"] == "fake-1"
    assert row["generation_prompt_version"] == "news-generation-v1"
    assert row["generated_at"] is not None
    assert row["impact_policy_version"] == "news-impact-v1"
    assert float(row["automated_impact_score"]) == 80.2
    assert row["automated_impact_level"] == "high"
    assert row["sources"] == 1, "the source candidate must stay linked"
    assert row["status"] != "published"


# -------------------------------------------------------------------------- idempotency


async def test_a_candidate_cannot_generate_two_articles(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    provider = FakeProvider()
    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidates[0], provider)
        second = await generate_for_candidate(s, candidates[0], provider)

    assert first.outcome == "accepted"
    assert second.outcome == "skipped"
    assert second.article_id == first.article_id
    # The duplicate request must not have reached the provider at all.
    assert provider.calls == 1, "a duplicate request must cost no quota"


async def test_batch_skips_already_generated_candidates(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    provider = FakeProvider()
    async with SessionFactory() as s:
        await generate_for_candidate(s, candidates[0], provider)
        result = await run_generation_batch(
            s, triggered_by="pytest", provider=provider, batch_size=5
        )
    # The generated item is no longer selectable, so the batch picks the other two.
    assert candidates[0] not in [o.ingest_item_id for o in result.outcomes]


async def test_batch_selects_highest_deterministic_score_first(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        result = await run_generation_batch(
            s, triggered_by="pytest", provider=FakeProvider(), batch_size=2
        )
    scores = [o.relevance_score for o in result.outcomes]
    assert scores == sorted(scores, reverse=True) and scores[0] == 90


# ------------------------------------------------------------------------------- limits


async def test_batch_size_is_respected(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    provider = FakeProvider()
    async with SessionFactory() as s:
        result = await run_generation_batch(
            s, triggered_by="pytest", provider=provider, batch_size=1
        )
    assert result.counters.candidates_selected == 1 and provider.calls == 1


async def test_daily_limit_stops_generation(monkeypatch, candidates) -> None:
    """The free-tier guard: past the cap the batch stops cleanly rather than calling.

    The cap is deliberately global for the day — it counts every generation attempt, not
    just this run's — so the limit is set relative to whatever has already been attempted
    today. Hard-coding 1 would make the test pass only on a database with no prior attempts.
    """
    from app.news.generation_service import _todays_call_count

    async with SessionFactory() as s:
        already = await _todays_call_count(s)

    enable(monkeypatch, news_daily_generation_limit=already + 1)
    provider = FakeProvider()
    async with SessionFactory() as s:
        first = await run_generation_batch(
            s, triggered_by="pytest", provider=provider, batch_size=5
        )
        second = await run_generation_batch(
            s, triggered_by="pytest", provider=provider, batch_size=5
        )
    assert first.counters.calls_made == 1, "the run must stop at the remaining allowance"
    assert second.status == "skipped"
    assert "Daily generation limit reached" in (second.skipped_reason or "")
    assert provider.calls == 1, "no call may be made once the cap is reached"


async def test_disabled_news_makes_generation_a_no_op(monkeypatch, candidates) -> None:
    monkeypatch.setenv("NEWS_GENERATION_ENABLED", "false")
    get_settings.cache_clear()
    provider = FakeProvider()
    async with SessionFactory() as s:
        result = await run_generation_batch(s, triggered_by="pytest", provider=provider)
    assert result.status == "skipped" and provider.calls == 0


async def test_missing_provider_config_fails_safely(monkeypatch, candidates) -> None:
    """An unconfigured provider must skip, not raise into the caller."""
    enable(monkeypatch, news_llm_provider="gemini", news_llm_api_key="")
    async with SessionFactory() as s:
        result = await run_generation_batch(s, triggered_by="pytest")
    assert result.status == "skipped"
    assert "NEWS_LLM_API_KEY" in (result.skipped_reason or "")


# ------------------------------------------------------------------------------ failure


async def test_generation_failure_leaves_the_candidate_retryable(
    monkeypatch, candidates
) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], FakeProvider(error=RuntimeError("provider exploded"))
        )
        row = (await s.execute(text("""
          SELECT status, is_ai_news, generation_attempts, generation_error
          FROM news_ingest_items WHERE id = :id
        """), {"id": candidates[0]})).mappings().one()

    assert outcome.outcome == "failed"
    # Still a candidate, so a later run picks it up again.
    assert row["status"] == "candidate"
    assert row["is_ai_news"] is None, "no verdict was reached, so none is recorded"
    assert row["generation_attempts"] == 1
    assert row["generation_error"] is not None


# ------------------------------------------------------------------------ public safety


@pytest.mark.parametrize("confidence", [0.94, 0.55])
async def test_generated_articles_are_never_publicly_visible(
    client: AsyncClient, monkeypatch, candidates, confidence: float
) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], FakeProvider(brief(ai_relevance_confidence=confidence))
        )
        slug = (await s.execute(text("SELECT slug FROM news_articles WHERE id = :id"),
                                {"id": outcome.article_id})).scalar_one()

    assert outcome.article_status in {"draft", "review_required"}
    assert (await client.get(f"/api/v1/news/{slug}")).status_code == 404
    assert slug not in [a["slug"] for a in (await client.get("/api/v1/news?limit=100")).json()]
    assert slug not in [e["slug"] for e in (await client.get("/api/v1/news/sitemap")).json()]


async def test_generation_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/admin/news/generation/batch")).status_code == 401
    assert (await client.get("/api/v1/admin/news/generation/status")).status_code == 401
    assert (await client.post("/api/v1/admin/news/incoming/1/generate")).status_code == 401


async def test_generation_status_never_exposes_the_key(
    client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setenv("NEWS_LLM_API_KEY", "super-secret-value")
    get_settings.cache_clear()
    body = (await client.get("/api/v1/admin/news/generation/status", auth=admin_auth())).json()
    assert body["apiKeyConfigured"] is True
    assert "super-secret-value" not in str(body), "the key must never be serialised"
    assert body["autoPublish"] is False
    get_settings.cache_clear()


async def test_generation_never_touches_occupation_scoring(monkeypatch, candidates) -> None:
    async def snapshot() -> dict:
        async with SessionFactory() as s:
            return dict((await s.execute(text("""
              SELECT (SELECT count(*) FROM occupation_scores) legacy,
                     (SELECT count(*) FROM production_occupation_score_snapshots) snapshots,
                     (SELECT count(*) FROM occupation_publications
                        WHERE activation_status='public') public_occupations,
                     (SELECT version FROM scoring_model_versions WHERE is_active) model
            """))).mappings().one())

    before = await snapshot()
    enable(monkeypatch)
    async with SessionFactory() as s:
        await run_generation_batch(s, triggered_by="pytest", provider=FakeProvider())
    assert await snapshot() == before
