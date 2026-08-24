"""Phase 4 Step 6 — the controlled automation layer.

The scripts are the scheduled entry points, so they are tested as scripts: their exit codes
are what cron reads, and a guard that fails open would be invisible in a Python-only test.

Nothing here installs cron, and nothing here calls a provider.
"""

import os
import pathlib
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.generation import GeneratedBrief
from app.news.generation_service import generate_for_candidate, run_generation_batch

pytestmark = pytest.mark.asyncio(loop_scope="session")

# /app in the container (tests live at /app/tests); the repo root when run from a checkout.
REPO = pathlib.Path("/app") if pathlib.Path("/app/scripts").is_dir() \
    else pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
SOURCE = "Automation Fixture Lab"
FACTORS = {"capability_advancement": 60, "commercial_deployability": 60,
           "breadth_of_affected_work": 60, "adoption_speed": 60,
           "human_work_reduction_potential": 60}


def brief(**overrides) -> GeneratedBrief:
    base = dict(
        is_ai_news=True, ai_relevance_confidence=0.95, relevance_reason="Capability release.",
        headline="Automation fixture headline",
        what_happened="A vendor shipped a capability.",
        why_it_matters_for_jobs="Some tasks are affected.",
        tags=["AI Agents"], job_areas=["Software Development"],
        factors=dict(FACTORS), impact_confidence=0.9, impact_reasoning="Reasoning.",
        input_tokens=1000, output_tokens=500,
    )
    return GeneratedBrief(**(base | overrides))


class CountingProvider:
    name, model = "automation-fake", "fake-1"

    def __init__(self, result=None) -> None:
        self._result = result if result is not None else brief()
        self.calls = 0

    def generate_news_brief(self, payload):
        self.calls += 1
        return self._result


def flags(monkeypatch, **overrides) -> None:
    for name in ("NEWS_INGESTION_ENABLED", "NEWS_GENERATION_ENABLED", "NEWS_ENABLED",
                 "NEWS_AUTO_PUBLISH", "NEWS_MAX_GENERATIONS_PER_RUN",
                 "NEWS_MAX_GENERATIONS_PER_DAY"):
        monkeypatch.delenv(name, raising=False)
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
            "DELETE FROM news_generation_runs WHERE triggered_by LIKE 'automation%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def candidates():
    await _cleanup()
    ids: list[int] = []
    parked: list[int] = []
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(
            text("SELECT id FROM news_ingest_items WHERE status='candidate'")
        )).scalars().all())
        if parked:
            await s.execute(text("UPDATE news_ingest_items SET status='new' WHERE id = ANY(:ids)"),
                            {"ids": parked})
        src = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES (:n, 'https://auto.test/rss.xml', 'https://auto.test', 'primary', 1, 'rss', false)
          RETURNING id"""), {"n": SOURCE})).scalar_one()
        for n, score in ((1, 90), (2, 80), (3, 70), (4, 60)):
            ids.append((await s.execute(text("""
              INSERT INTO news_ingest_items (source_id, external_url, canonical_url,
                original_title, original_excerpt, source_published_at, content_hash, status,
                relevance_score, relevance_policy_version, relevance_signals, title_fingerprint)
              VALUES (:src, :url, :url, :title, 'An excerpt.',
                      now() - make_interval(hours => :n), :hash, 'candidate', :score,
                      'news-relevance-v1', '{"aiTerms":["ai agent"]}'::jsonb, :fp)
              RETURNING id"""), {
                "src": src, "url": f"https://auto.test/i{n}", "title": f"Automation item {n}",
                "hash": f"a{n:063d}", "n": n, "score": score,
                "fp": f"automation item {n}"})).scalar_one())
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


def run_script(name: str, **env) -> subprocess.CompletedProcess:
    """Run an automation script with a broken compose file.

    The scripts are exercised for their guards and exit codes, not to drive Docker from
    inside a container. A guard that returns before invoking compose is unaffected by the
    broken file; anything that reaches compose fails, which is exactly the distinction under
    test.
    """
    environment = os.environ | {"COMPOSE_FILES": "-f /nonexistent-compose.yml"} | {
        k: str(v) for k, v in env.items()
    }
    return subprocess.run(
        ["bash", str(SCRIPTS / name)], cwd=str(REPO), env=environment,
        capture_output=True, text=True, timeout=120,
    )


# ------------------------------------------------------------------------------- scripts


async def test_the_three_automation_scripts_exist_and_are_executable() -> None:
    for name in ("news-ingest.sh", "news-generate.sh", "news-metrics.sh"):
        script = SCRIPTS / name
        assert script.is_file(), f"{name} is missing"
        assert os.access(script, os.X_OK), f"{name} is not executable"


async def test_the_cron_example_is_documentation_not_an_installer() -> None:
    example = REPO / "deploy" / "news-cron.example"
    assert example.is_file()
    body = example.read_text()
    # It must not be wired into anything that runs.
    for name in ("news-ingest.sh", "news-generate.sh", "news-metrics.sh"):
        assert name in body, f"{name} should appear in the cron example"
    assert "NEWS_AUTO_PUBLISH=false" in body, "the example must state the publishing rule"
    # Nothing in the repo should install it.
    for script in SCRIPTS.glob("*.sh"):
        text_body = script.read_text()
        assert "crontab" not in text_body, f"{script.name} must not touch crontab"


# ------------------------------------------------------ TEST 1: scheduler disabled


async def test_ingest_script_does_nothing_when_ingestion_is_disabled() -> None:
    result = run_script("news-ingest.sh", NEWS_INGESTION_ENABLED="false")
    assert result.returncode == 0, "a disabled pipeline is a configured state, not a failure"
    assert "nothing to do" in result.stdout
    # It returned before reaching compose, which the broken compose file proves.
    assert "nonexistent-compose" not in result.stderr


async def test_generate_script_does_nothing_when_generation_is_disabled() -> None:
    result = run_script("news-generate.sh", NEWS_GENERATION_ENABLED="false")
    assert result.returncode == 0
    assert "no provider call will be made" in result.stdout


async def test_disabled_generation_never_reaches_the_provider(monkeypatch, candidates) -> None:
    flags(monkeypatch, news_ingestion_enabled="true", news_generation_enabled="false")
    provider = CountingProvider()
    async with SessionFactory() as s:
        batch = await run_generation_batch(s, triggered_by="automation", provider=provider)
    assert batch.status == "skipped"
    assert provider.calls == 0


# ------------------------------------------------------- TEST 2: enabled, within limits


async def test_enabled_generation_runs_within_the_batch_limit(
    monkeypatch, candidates
) -> None:
    flags(monkeypatch, news_ingestion_enabled="true", news_generation_enabled="true",
          news_max_generations_per_run=2, news_max_generations_per_day=50)
    assert get_settings().generations_per_run == 2, "the alias must win when set"
    provider = CountingProvider()

    async with SessionFactory() as s:
        result = await run_generation_batch(s, triggered_by="automation", provider=provider)

    assert result.status == "completed"
    assert provider.calls == 2, "the run must stop at the configured batch size"
    assert result.counters.accepted == 2


# ------------------------------------------------------------- TEST 3: daily cap reached


async def test_daily_cap_blocks_further_generation(monkeypatch, candidates) -> None:
    from app.news.generation_service import _todays_call_count

    async with SessionFactory() as s:
        already = await _todays_call_count(s)

    flags(monkeypatch, news_ingestion_enabled="true", news_generation_enabled="true",
          news_max_generations_per_run=4, news_max_generations_per_day=already + 1)
    provider = CountingProvider()

    async with SessionFactory() as s:
        first = await run_generation_batch(s, triggered_by="automation", provider=provider)
        second = await run_generation_batch(s, triggered_by="automation", provider=provider)

    assert first.counters.calls_made == 1, "the remaining allowance bounds the run"
    assert second.status == "skipped"
    assert "Daily generation limit reached" in (second.skipped_reason or "")
    assert provider.calls == 1, "no call may be made once the cap is reached"


async def test_the_limit_aliases_resolve_to_the_canonical_settings(monkeypatch) -> None:
    """Two names for one cap; never two independent caps."""
    flags(monkeypatch)
    settings = get_settings()
    assert settings.generations_per_run == settings.news_generation_batch_size == 2
    assert settings.generations_per_day == settings.news_daily_generation_limit == 5

    flags(monkeypatch, news_max_generations_per_run=7, news_max_generations_per_day=21)
    settings = get_settings()
    assert settings.generations_per_run == 7
    assert settings.generations_per_day == 21


# ------------------------------------------------------------ TEST 4: no auto publishing


async def test_scheduled_generation_leaves_articles_awaiting_review(
    monkeypatch, candidates
) -> None:
    flags(monkeypatch, news_ingestion_enabled="true", news_generation_enabled="true",
          news_auto_publish="true", news_max_generations_per_run=1)
    assert get_settings().news_auto_publish is True

    async with SessionFactory() as s:
        outcome = await generate_for_candidate(
            s, candidates[0], CountingProvider(brief(impact_confidence=0.5)))
        published = (await s.execute(text(
            "SELECT count(*) FROM news_articles WHERE status='published'"))).scalar_one()

    assert outcome.article_status == "review_required"
    assert published == 0
    get_settings.cache_clear()


async def test_generate_script_refuses_when_auto_publish_is_on() -> None:
    """A safety net ahead of spending, not the enforcement point.

    The service cannot publish regardless; this catches the misconfiguration before a
    provider call rather than after.
    """
    result = run_script("news-generate.sh", NEWS_GENERATION_ENABLED="true",
                        NEWS_AUTO_PUBLISH="true")
    assert result.returncode == 2, "a refusal must be distinguishable from success and failure"
    assert "Refusing to run scheduled generation" in result.stderr
    assert "nonexistent-compose" not in result.stderr, "it must refuse before reaching compose"


# ------------------------------------------------------------ TEST 5: failure exit codes


async def test_a_real_failure_exits_non_zero() -> None:
    """Cron reads the exit code; a guard that failed open would be invisible."""
    result = run_script("news-ingest.sh", NEWS_INGESTION_ENABLED="true")
    assert result.returncode != 0, "a failing run must be visible to cron"
    assert "FAILED" in result.stderr


async def test_metrics_failure_exits_non_zero() -> None:
    result = run_script("news-metrics.sh")
    assert result.returncode != 0
    assert "FAILED" in result.stderr


async def test_scripts_let_the_caller_override_the_env_file() -> None:
    """`set -a; . ./.env` alone lets the file clobber the caller.

    That made a one-off override impossible and, more quietly, made these guards untestable —
    the auto-publish refusal silently did not fire when first written.
    """
    for name in ("news-ingest.sh", "news-generate.sh", "news-metrics.sh"):
        body = (SCRIPTS / name).read_text()
        assert "_keep " in body and "_restore " in body, (
            f"{name} must preserve caller overrides across the .env load"
        )


async def test_automation_never_touches_occupation_scoring(monkeypatch, candidates) -> None:
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
    flags(monkeypatch, news_ingestion_enabled="true", news_generation_enabled="true")
    async with SessionFactory() as s:
        await run_generation_batch(s, triggered_by="automation", provider=CountingProvider())
    assert await snapshot() == before
