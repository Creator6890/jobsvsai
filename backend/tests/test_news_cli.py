"""Phase 4 Step 2 — the operator CLI and the dry-run ingestion path.

The property that matters most: a dry run must reach the same decisions a real run would,
and write nothing. A preview that disagreed with the run it previews would be worse than no
preview at all.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news.cli import build_parser
from app.news.feeds import parse_feed
from app.news.ingestion import run_ingestion
from tests.fixtures.feeds import RSS_VALID

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE = "CLI Fixture Lab"
FEED = "https://cli.test/rss.xml"
WIDE = 87600  # the fixtures are dated, so the window must not exclude them


class FixtureFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_entries(self, feed_url: str, source_id: int):
        self.calls.append(feed_url)
        return parse_feed(source_id, RSS_VALID)


def enable_ingestion(monkeypatch, generation: str = "false") -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "true")
    monkeypatch.setenv("NEWS_GENERATION_ENABLED", generation)
    get_settings.cache_clear()


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text(
            "DELETE FROM news_ingest_items WHERE source_id IN "
            "(SELECT id FROM news_sources WHERE name = :n)"), {"n": SOURCE})
        await s.execute(text("DELETE FROM news_sources WHERE name = :n"), {"n": SOURCE})
        await s.execute(text(
            "DELETE FROM news_ingestion_runs WHERE triggered_by LIKE 'clitest%'"))


@pytest_asyncio.fixture(loop_scope="session")
async def cli_source():
    await _cleanup()
    parked: list[int] = []
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(
            text("SELECT id FROM news_sources WHERE enabled"))).scalars().all())
        if parked:
            await s.execute(text("UPDATE news_sources SET enabled=false WHERE id = ANY(:ids)"),
                            {"ids": parked})
        await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES (:n, :u, 'https://cli.test', 'primary', 1, 'rss', true)
        """), {"n": SOURCE, "u": FEED})
    try:
        yield
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(text("UPDATE news_sources SET enabled=true WHERE id = ANY(:ids)"),
                                {"ids": parked})
        get_settings.cache_clear()


async def _counts() -> dict[str, int]:
    async with SessionFactory() as s:
        row = (await s.execute(text("""
          SELECT (SELECT count(*) FROM news_ingest_items i JOIN news_sources src
                    ON src.id=i.source_id WHERE src.name=:n) items,
                 (SELECT count(*) FROM news_ingestion_runs
                    WHERE triggered_by LIKE 'clitest%') runs
        """), {"n": SOURCE})).mappings().one()
    return dict(row)


# ------------------------------------------------------------------------ argument parsing


async def test_parser_exposes_the_documented_commands() -> None:
    parser = build_parser()
    for argv in (["ingest", "--dry-run"], ["candidates"], ["sources"], ["runs"]):
        assert parser.parse_args(argv).command == argv[0]
    assert parser.parse_args(["ingest", "--dry-run"]).dry_run is True
    assert parser.parse_args(["ingest"]).dry_run is False, "live must be the explicit default"
    assert parser.parse_args(["ingest", "--lookback", "168"]).lookback == 168


async def test_cli_cannot_publish() -> None:
    """The CLI can generate (Step 4 added that) but has no path to publication.

    Asserted on the module's own source: the guarantee is the absence of a capability, and a
    behavioural test could only show it went unused today. `generation_service` is imported
    inside the one command that needs it, so ingestion commands still cannot reach a
    provider merely by being in the same module.
    """
    import pathlib

    source_text = (pathlib.Path(__file__).parent.parent / "app" / "news" / "cli.py").read_text()
    module_imports = "\n".join(line for line in source_text.splitlines()
                               if line.startswith(("import ", "from ")))
    assert "generation_service" not in module_imports, (
        "generation must stay a local import inside cmd_generate"
    )
    # `repositories.news` is the module that owns publish() and set_status(). The CLI reads
    # from news_ingest and news_metrics only, so the publication path is not merely unused
    # here — it is unreachable.
    assert "repositories import news\n" not in source_text
    assert "repositories.news " not in source_text
    # And no call site exists. Checked as calls rather than as substrings: the metrics
    # command legitimately *reports* a count of published articles, and a naive string
    # search cannot tell that apart from publishing one.
    for forbidden_call in ("publish(", "set_status(", "archive(", "create_draft("):
        assert forbidden_call not in source_text, f"CLI must not call {forbidden_call}"


# ---------------------------------------------------------------------------- the dry run


async def test_dry_run_writes_absolutely_nothing(monkeypatch, cli_source) -> None:
    enable_ingestion(monkeypatch)
    before = await _counts()
    fetcher = FixtureFetcher()

    async with SessionFactory() as s:
        result = await run_ingestion(s, triggered_by="clitest", fetcher=fetcher,
                                     lookback_hours=WIDE, dry_run=True)

    assert result.dry_run is True
    assert fetcher.calls == [FEED], "a dry run still fetches — that is the point"
    assert result.counters.items_new > 0, "it must reach real decisions"
    assert await _counts() == before, "no ingest item and no run row may be written"
    assert result.run_id is None


async def test_dry_run_leaves_source_health_untouched(monkeypatch, cli_source) -> None:
    """last_fetched_at and the failure counter are writes too."""
    enable_ingestion(monkeypatch)
    async with SessionFactory() as s:
        await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                            lookback_hours=WIDE, dry_run=True)
        row = (await s.execute(text(
            "SELECT last_fetched_at, consecutive_failures FROM news_sources WHERE name=:n"
        ), {"n": SOURCE})).mappings().one()
    assert row["last_fetched_at"] is None
    assert row["consecutive_failures"] == 0


async def test_dry_run_predicts_what_the_live_run_then_does(monkeypatch, cli_source) -> None:
    """The preview and the run must agree, or the preview is not worth having."""
    enable_ingestion(monkeypatch)
    async with SessionFactory() as s:
        dry = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                  lookback_hours=WIDE, dry_run=True)
        live = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                   lookback_hours=WIDE)

    assert dry.counters.items_fetched == live.counters.items_fetched
    assert dry.counters.items_new == live.counters.items_new
    assert dry.counters.items_candidate == live.counters.items_candidate
    assert dry.counters.items_ignored == live.counters.items_ignored
    assert dry.counters.items_near_duplicate == live.counters.items_near_duplicate

    def shape(result):
        return sorted((d.original_title, d.dedupe, d.status, d.relevance_score)
                      for d in result.decisions)

    assert shape(dry) == shape(live), "the dry run must reach identical decisions"


async def test_decisions_carry_everything_the_operator_needs(monkeypatch, cli_source) -> None:
    """Source, title, URL, published date, relevance score, dedupe result and status."""
    enable_ingestion(monkeypatch)
    async with SessionFactory() as s:
        result = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                     lookback_hours=WIDE, dry_run=True)

    stored = [d for d in result.decisions if d.status in ("candidate", "ignored")]
    assert stored
    for d in stored:
        assert d.source_name == SOURCE
        assert d.original_title and d.external_url.startswith("https://")
        assert d.source_published_at is not None
        assert d.relevance_score is not None
        assert d.dedupe in ("new", "exact_duplicate", "near_duplicate", "outside_window")
        assert d.status in ("candidate", "ignored", "duplicate", "new", "not_stored")

    # The near-duplicate in the fixture is reported with what it duplicates.
    near = [d for d in result.decisions if d.dedupe == "near_duplicate"]
    assert near, "the fixture contains a restatement and it should be detected"
    assert near[0].near_duplicate_similarity is not None


async def test_dry_run_reports_exact_duplicates_against_stored_history(
    monkeypatch, cli_source
) -> None:
    """After a live run, a dry run sees the same entries as already known."""
    enable_ingestion(monkeypatch)
    async with SessionFactory() as s:
        await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                            lookback_hours=WIDE)
        second = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                     lookback_hours=WIDE, dry_run=True)

    assert second.counters.items_new == 0
    assert second.counters.items_exact_duplicate > 0
    assert all(d.dedupe == "exact_duplicate"
               for d in second.decisions if d.status == "not_stored" and d.dedupe != "outside_window")


async def test_dry_run_is_refused_when_ingestion_is_disabled(monkeypatch, cli_source) -> None:
    monkeypatch.setenv("NEWS_INGESTION_ENABLED", "false")
    get_settings.cache_clear()
    fetcher = FixtureFetcher()

    async with SessionFactory() as s:
        result = await run_ingestion(s, triggered_by="clitest", fetcher=fetcher, dry_run=True)

    assert result.status == "skipped"
    assert fetcher.calls == [], "a gated pipeline must not fetch, even as a preview"


async def test_lookback_override_is_honoured(monkeypatch, cli_source) -> None:
    """The flag a first production run depends on: the default window finds nothing."""
    enable_ingestion(monkeypatch)
    async with SessionFactory() as s:
        narrow = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                     lookback_hours=1, dry_run=True)
        wide = await run_ingestion(s, triggered_by="clitest", fetcher=FixtureFetcher(),
                                   lookback_hours=WIDE, dry_run=True)

    assert narrow.counters.items_new == 0
    assert narrow.counters.items_outside_window > 0
    assert wide.counters.items_new > 0
