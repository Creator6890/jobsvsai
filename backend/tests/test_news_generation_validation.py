"""Phase 4 Step 4 — the generation validation runner and its audit trail.

Step 5 has to answer whether generated content justifies its cost and editorial effort. That
question is unanswerable after the fact unless the data is captured while generating, so
these tests check the *recording* as carefully as the behaviour: latency, token usage, a
stable failure category, the semantic verdict and its reasoning.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.cli import build_parser
from app.news.generation import GeneratedBrief
from app.news.generation_service import generate_for_candidate, run_generation_batch

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE = "Validation Fixture Lab"
FACTORS = {"capability_advancement": 70, "commercial_deployability": 65,
           "breadth_of_affected_work": 60, "adoption_speed": 55,
           "human_work_reduction_potential": 50}   # -> 62.5, medium


def brief(**overrides) -> GeneratedBrief:
    base = dict(
        is_ai_news=True, ai_relevance_confidence=0.93, relevance_reason="Capability release.",
        headline="A capability shipped", what_happened="A vendor shipped a capability.",
        why_it_matters_for_jobs="Some tasks are affected.",
        tags=["AI Agents"], job_areas=["Software Development"],
        factors=dict(FACTORS), impact_confidence=0.88, impact_reasoning="Reasoning.",
        input_tokens=1500, output_tokens=700,
    )
    return GeneratedBrief(**(base | overrides))


class SlowProvider:
    """Takes measurable time, so latency is a real reading rather than a rounded zero."""

    name, model = "validation-fake", "fake-1"

    def __init__(self, result=None, error: Exception | None = None, delay: float = 0.02) -> None:
        self._result = result if result is not None else brief()
        self._error = error
        self._delay = delay
        self.calls = 0

    def generate_news_brief(self, payload):
        import time

        self.calls += 1
        time.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result


def enable(monkeypatch, generation: str = "true", **overrides) -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "true")
    monkeypatch.setenv("NEWS_GENERATION_ENABLED", generation)
    for key, value in overrides.items():
        monkeypatch.setenv(key.upper(), str(value))
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
            "DELETE FROM news_generation_runs WHERE triggered_by LIKE 'validation%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def candidates():
    """Three candidates, and every pre-existing one parked so selection is deterministic."""
    await _cleanup()
    ids: list[int] = []
    parked: list[int] = []
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(
            text("SELECT id FROM news_ingest_items WHERE status='candidate'")
        )).scalars().all())
        if parked:
            await s.execute(
                text("UPDATE news_ingest_items SET status='new' WHERE id = ANY(:ids)"),
                {"ids": parked})
        src = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES (:n, 'https://val.test/rss.xml', 'https://val.test', 'primary', 1, 'rss', false)
          RETURNING id"""), {"n": SOURCE})).scalar_one()
        for n, score in ((1, 88), (2, 72), (3, 51)):
            ids.append((await s.execute(text("""
              INSERT INTO news_ingest_items (source_id, external_url, canonical_url,
                original_title, original_excerpt, source_published_at, content_hash, status,
                relevance_score, relevance_policy_version, relevance_signals, title_fingerprint)
              VALUES (:src, :url, :url, :title, 'An excerpt.',
                      now() - make_interval(hours => :n), :hash, 'candidate', :score,
                      'news-relevance-v1', '{"aiTerms":["ai agent"]}'::jsonb, :fp)
              RETURNING id"""), {
                "src": src, "url": f"https://val.test/item-{n}",
                "title": f"Validation item {n}", "hash": f"v{n:063d}", "n": n,
                "score": score, "fp": f"validation item {n}"})).scalar_one())
    try:
        yield ids
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(
                    text("UPDATE news_ingest_items SET status='candidate' WHERE id = ANY(:ids)"),
                    {"ids": parked})
        get_settings.cache_clear()


async def _item(item_id: int) -> dict:
    async with SessionFactory() as s:
        return dict((await s.execute(text("""
          SELECT status, is_ai_news, ai_relevance_confidence, ai_relevance_reason,
                 generation_attempts, generation_error, generation_error_kind,
                 generation_latency_ms, generation_input_tokens, generation_output_tokens,
                 generation_model, generation_prompt_version, generation_attempted_at
          FROM news_ingest_items WHERE id = :id"""), {"id": item_id})).mappings().one())


# ------------------------------------------------------------------------------- the CLI


async def test_cli_exposes_generate_with_safe_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["generate"])
    assert args.command == "generate"
    assert args.batch_size is None, "batch size must come from configuration by default"
    assert args.item is None, "the default is the queue, not a hand-picked list"
    assert parser.parse_args(["generate", "--item", "5", "--item", "9"]).item == [5, 9]


# --------------------------------------------------- TEST 1: generation disabled


async def test_disabled_generation_never_calls_the_provider(monkeypatch, candidates) -> None:
    enable(monkeypatch, generation="false")
    provider = SlowProvider()

    async with SessionFactory() as s:
        batch = await run_generation_batch(s, triggered_by="validation", provider=provider)
        single = await generate_for_candidate(s, candidates[0], provider)

    assert provider.calls == 0, "a disabled pipeline must not reach the model"
    assert batch.status == "skipped"
    assert single.outcome == "skipped"
    # Nothing was recorded against the candidate either.
    row = await _item(candidates[0])
    assert row["generation_attempts"] == 0
    assert row["generation_latency_ms"] is None


# ------------------------------------------------------ TEST 2: candidate becomes a draft


async def test_enabled_generation_turns_a_candidate_into_a_draft(
    monkeypatch, candidates
) -> None:
    enable(monkeypatch)
    provider = SlowProvider()

    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], provider)

    assert provider.calls == 1
    assert outcome.outcome == "accepted"
    assert outcome.article_id is not None
    assert outcome.article_status == "draft"
    assert outcome.impact_score == 62.5 and outcome.impact_level == "medium"
    row = await _item(candidates[0])
    assert row["status"] == "processed" and row["is_ai_news"] is True


# ------------------------------------------------------- TEST 3: nothing auto-publishes


async def test_generated_articles_are_never_published(monkeypatch, candidates) -> None:
    """Even with NEWS_AUTO_PUBLISH forced true. The service has no path to `published`."""
    enable(monkeypatch, news_auto_publish="true")
    assert get_settings().news_auto_publish is True

    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], SlowProvider())
        status = (await s.execute(text("SELECT status FROM news_articles WHERE id=:id"),
                                  {"id": outcome.article_id})).scalar_one()
        published = (await s.execute(text(
            "SELECT count(*) FROM news_articles WHERE status='published'"))).scalar_one()

    assert status in ("draft", "review_required") and status != "published"
    assert published == 0
    get_settings.cache_clear()


# ----------------------------------------------------- TEST 4: failure stays recoverable


async def test_a_failed_call_leaves_the_candidate_recoverable(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], SlowProvider(error=RuntimeError("provider exploded")))

    assert outcome.outcome == "failed"
    row = await _item(candidates[0])
    # Still a candidate, so the next run picks it up.
    assert row["status"] == "candidate"
    # No verdict was reached, so none is recorded: an unassessed item is not the same as one
    # the model declined, and conflating them would corrupt Step 5's acceptance rate.
    assert row["is_ai_news"] is None
    assert row["generation_attempts"] == 1
    assert row["generation_error"] is not None


async def test_a_second_attempt_after_failure_succeeds(monkeypatch, candidates) -> None:
    """Recoverable means recoverable, not merely un-deleted."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        await generate_for_candidate(s, candidates[0],
                                     SlowProvider(error=RuntimeError("transient")))
        retry = await generate_for_candidate(s, candidates[0], SlowProvider())

    assert retry.outcome == "accepted"
    row = await _item(candidates[0])
    assert row["generation_attempts"] == 2, "both attempts are counted"
    assert row["generation_error"] is None, "success clears the previous failure"
    assert row["generation_error_kind"] is None


# ------------------------------------------------------------ TEST 5: one candidate, one article


async def test_a_candidate_cannot_produce_two_articles(monkeypatch, candidates) -> None:
    enable(monkeypatch)
    provider = SlowProvider()

    async with SessionFactory() as s:
        first = await generate_for_candidate(s, candidates[0], provider)
        second = await generate_for_candidate(s, candidates[0], provider)
        links = (await s.execute(text(
            "SELECT count(*) FROM news_article_sources WHERE ingest_item_id = :id"
        ), {"id": candidates[0]})).scalar_one()

    assert second.outcome == "skipped"
    assert second.article_id == first.article_id
    assert links == 1
    assert provider.calls == 1, "the duplicate request must cost no quota"


# ------------------------------------------------------------------------- audit capture


async def test_latency_and_tokens_are_recorded_on_success(monkeypatch, candidates) -> None:
    """Step 5 cannot compute cost per article after the fact if this is not captured now."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], SlowProvider(delay=0.05))

    assert outcome.latency_ms is not None and outcome.latency_ms >= 40
    assert outcome.input_tokens == 1500 and outcome.output_tokens == 700

    row = await _item(candidates[0])
    assert row["generation_latency_ms"] >= 40
    assert row["generation_input_tokens"] == 1500
    assert row["generation_output_tokens"] == 700
    assert row["generation_model"] == "fake-1"
    assert row["generation_prompt_version"] == "news-generation-v1"
    assert row["generation_attempted_at"] is not None


async def test_rejections_record_their_reasoning_and_cost(monkeypatch, candidates) -> None:
    """A rejection costs a call, and its reasoning is the input to prompt calibration."""
    enable(monkeypatch)
    rejection = GeneratedBrief(
        is_ai_news=False, ai_relevance_confidence=0.91,
        relevance_reason="Funding round with no capability change.",
        input_tokens=900, output_tokens=60,
    )
    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], SlowProvider(rejection))

    assert outcome.outcome == "rejected"
    row = await _item(candidates[0])
    assert row["is_ai_news"] is False
    assert float(row["ai_relevance_confidence"]) == 0.91
    assert "Funding round" in row["ai_relevance_reason"]
    assert row["generation_input_tokens"] == 900
    assert row["generation_latency_ms"] is not None


@pytest.mark.parametrize(
    ("status_code", "expected_kind"),
    [(429, "rate_limited"), (503, "server_error"), (401, "credentials"), (400, "provider_error")],
)
async def test_failures_are_categorised_for_grouping(
    monkeypatch, candidates, status_code: int, expected_kind: str
) -> None:
    """Step 5 groups model failures. Parsing an error message would work until it changed."""
    from app.news.gemini import GeminiGenerationProvider

    enable(monkeypatch)

    class Failing(Exception):
        code = status_code

    classified = GeminiGenerationProvider._classify(Failing())
    assert classified.kind == expected_kind

    async with SessionFactory() as s:
        outcome = await generate_for_candidate(s, candidates[0], SlowProvider(error=classified))

    assert outcome.error_kind == expected_kind
    assert (await _item(candidates[0]))["generation_error_kind"] == expected_kind


async def test_error_kind_and_message_always_appear_together(
    monkeypatch, candidates
) -> None:
    """A category without a message is unactionable; a message without one is ungroupable."""
    enable(monkeypatch)
    async with SessionFactory() as s:
        await generate_for_candidate(s, candidates[0], SlowProvider(error=RuntimeError("boom")))
    row = await _item(candidates[0])
    assert (row["generation_error"] is None) == (row["generation_error_kind"] is None)


# ------------------------------------------------------------------- batch-level metrics


async def test_batch_records_the_rates_step5_needs(monkeypatch, candidates) -> None:
    """One accepted, one rejected, one failed — every counter should reflect it."""
    enable(monkeypatch, news_generation_batch_size=3)

    accept = SlowProvider()
    reject = SlowProvider(GeneratedBrief(
        is_ai_news=False, ai_relevance_confidence=0.9, relevance_reason="Not AI news.",
        input_tokens=800, output_tokens=40))
    fail = SlowProvider(error=RuntimeError("provider exploded"))

    async with SessionFactory() as s:
        await generate_for_candidate(s, candidates[0], accept)
        await generate_for_candidate(s, candidates[1], reject)
        await generate_for_candidate(s, candidates[2], fail)

        totals = (await s.execute(text("""
          SELECT count(*) FILTER (WHERE is_ai_news IS TRUE)  accepted,
                 count(*) FILTER (WHERE is_ai_news IS FALSE) rejected,
                 count(*) FILTER (WHERE generation_error IS NOT NULL) failed,
                 coalesce(sum(generation_input_tokens), 0)  input_tokens,
                 coalesce(sum(generation_output_tokens), 0) output_tokens,
                 count(*) FILTER (WHERE generation_latency_ms IS NOT NULL) timed
          FROM news_ingest_items i JOIN news_sources s2 ON s2.id = i.source_id
          WHERE s2.name = :n"""), {"n": SOURCE})).mappings().one()

    assert totals["accepted"] == 1 and totals["rejected"] == 1 and totals["failed"] == 1
    # Accepted and rejected both cost tokens; the failure recorded none but was still timed.
    assert totals["input_tokens"] == 2300
    assert totals["timed"] == 3, "every attempt must carry a latency reading"


async def test_batch_respects_the_daily_cap_and_records_the_run(
    monkeypatch, candidates
) -> None:
    from app.news.generation_service import _todays_call_count

    async with SessionFactory() as s:
        already = await _todays_call_count(s)
    enable(monkeypatch, news_daily_generation_limit=already + 1,
           news_generation_batch_size=3)
    provider = SlowProvider()

    async with SessionFactory() as s:
        result = await run_generation_batch(s, triggered_by="validation", provider=provider)
        run = (await s.execute(text("""
          SELECT calls_made, accepted, input_tokens, output_tokens, batch_size, daily_limit
          FROM news_generation_runs WHERE id = :id"""), {"id": result.run_id})).mappings().one()

    assert provider.calls == 1, "the cap must bound the batch"
    assert run["calls_made"] == 1 and run["accepted"] == 1
    assert run["input_tokens"] == 1500 and run["output_tokens"] == 700
    assert run["daily_limit"] == already + 1


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
        await run_generation_batch(s, triggered_by="validation", provider=SlowProvider())
    assert await snapshot() == before
