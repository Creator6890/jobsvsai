"""Phase 4 Step 5 — cost, reliability and editorial metrics.

The derivations are tested as pure functions rather than through stdout, which is the point
of moving them out of the CLI: a rate that can only be checked by capturing printed output
is a rate nobody checks.

The honesty rules get as much attention as the arithmetic. A projection built on two
observations, or a zero that reads as "nothing failed" when it means "nothing ran", is worse
than no number at all.
"""

import json
import os
import pathlib
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news import metrics as service
from app.news.metrics import (
    INSUFFICIENT,
    MIN_ECONOMIC_SAMPLE,
    compute_cost,
    derive_economics,
    derive_editorial,
    derive_reliability,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

SOURCE = "Metrics Fixture Lab"


class Priced:
    """Minimal settings stand-in, so cost maths is tested without touching configuration."""

    def __init__(self, inp: float | None = None, out: float | None = None) -> None:
        self.news_llm_cost_per_1m_input = inp
        self.news_llm_cost_per_1m_output = out


# ------------------------------------------------------------------- TEST 3: cost maths


async def test_cost_calculation_is_correct() -> None:
    """1,000 input at $0.30/M and 500 output at $2.50/M."""
    cost = compute_cost(1000, 500, price_per_1m_input=0.30, price_per_1m_output=2.50)
    assert cost.priced is True
    assert cost.input_cost == pytest.approx(0.0003)    # 1000/1e6 * 0.30
    assert cost.output_cost == pytest.approx(0.00125)  # 500/1e6 * 2.50
    assert cost.total == pytest.approx(0.00155)


async def test_cost_is_withheld_unless_both_prices_are_given() -> None:
    """Half a price is not a price: the total would silently omit one side."""
    for inp, out in ((0.30, None), (None, 2.50), (None, None)):
        cost = compute_cost(1000, 500, inp, out)
        assert cost.priced is False
        assert cost.total is None
        # Token counts are facts and are always reported.
        assert cost.input_tokens == 1000 and cost.output_tokens == 500


async def test_zero_tokens_costs_zero_not_none() -> None:
    cost = compute_cost(0, 0, 0.30, 2.50)
    assert cost.priced is True and cost.total == 0.0


# ------------------------------------------------------- economics and the sample rule


def _generation(**overrides) -> dict:
    base = {"attempts": 10, "accepted": 6, "rejected": 3, "failed": 1,
            "input_tokens": 12000, "output_tokens": 6000, "items_attempted": 9,
            "latency_mean": 900, "latency_p50": 850, "latency_p95": 2000, "latency_max": 2400}
    return base | overrides


async def test_economics_projects_only_above_the_minimum_sample() -> None:
    economics = derive_economics(_generation(accepted=6), Priced(0.30, 2.50))
    assert economics["status"] == "ok"
    assert economics["tokensPerArticle"] == pytest.approx(3000.0)   # 18000 / 6
    assert economics["costPerArticle"] is not None
    assert economics["costPer100Articles"] == pytest.approx(economics["costPerArticle"] * 100)
    # Projections carry the cost of the rejections and failures it took to get there.
    assert economics["monthlyProjections"]["3_per_day"] == pytest.approx(
        economics["costPerArticle"] * 3 * 30
    )


async def test_projections_are_withheld_not_caveated_below_the_sample() -> None:
    """A dashboard renders numbers and drops footnotes."""
    economics = derive_economics(_generation(accepted=1), Priced(0.30, 2.50))
    assert economics["status"] == INSUFFICIENT
    assert economics["sampleSize"] == 1
    assert economics["minimumSampleForProjection"] == MIN_ECONOMIC_SAMPLE
    for withheld in ("tokensPerArticle", "costPerArticle", "costPer100Articles",
                     "monthlyProjections"):
        assert economics[withheld] is None, f"{withheld} must not be estimated from n=1"
    # Per-attempt figures describe what was actually spent, so they survive.
    assert economics["tokensPerAttempt"] is not None
    assert economics["costPerAttempt"] is not None
    assert economics["totalTokens"] == 18000


async def test_unpriced_economics_still_reports_tokens() -> None:
    economics = derive_economics(_generation(), Priced())
    assert economics["priced"] is False
    assert economics["estimatedSpend"] is None
    assert economics["costPerArticle"] is None
    assert economics["tokensPerArticle"] == pytest.approx(3000.0), "tokens are still facts"


# ------------------------------------------------- TEST 4: reliability and percentiles


async def test_latency_percentiles_are_passed_through_unrounded() -> None:
    reliability = derive_reliability(
        _generation(latency_mean=900, latency_p50=850, latency_p95=2000, latency_max=2400),
        {"fetch_attempts": 9, "fetch_successes": 9}, [],
    )
    assert reliability["latencyMeanMs"] == 900
    assert reliability["latencyP50Ms"] == 850
    assert reliability["latencyP95Ms"] == 2000
    assert reliability["latencyMaxMs"] == 2400


async def test_reliability_rates_are_computed_from_the_right_denominators() -> None:
    reliability = derive_reliability(
        _generation(attempts=10, accepted=6, rejected=3, failed=1, items_attempted=9),
        {"fetch_attempts": 10, "fetch_successes": 8},
        [{"kind": "timeout", "total": 1}],
    )
    assert reliability["ingestionSuccessRate"] == pytest.approx(0.8)
    # A rejection is a successful call: the model answered.
    assert reliability["generationSuccessRate"] == pytest.approx(0.9)
    assert reliability["providerFailureRate"] == pytest.approx(0.1)
    assert reliability["timeoutRate"] == pytest.approx(0.1)
    # 10 calls across 9 distinct items means exactly one retry.
    assert reliability["retryRate"] == pytest.approx(0.1)


async def test_a_rejection_is_not_counted_as_a_failure() -> None:
    """Conflating them would make a working semantic filter look like an outage."""
    reliability = derive_reliability(
        _generation(attempts=10, accepted=2, rejected=8, failed=0, items_attempted=10),
        {"fetch_attempts": 1, "fetch_successes": 1}, [],
    )
    assert reliability["generationSuccessRate"] == pytest.approx(1.0)
    assert reliability["providerFailureRate"] == pytest.approx(0.0)


async def test_rates_are_none_not_zero_when_nothing_ran() -> None:
    """A 0% failure rate for a pipeline that never ran is a reassuring lie."""
    reliability = derive_reliability(
        {"attempts": 0, "accepted": 0, "rejected": 0, "failed": 0, "items_attempted": 0},
        {"fetch_attempts": 0, "fetch_successes": 0}, [],
    )
    assert reliability["generationSuccessRate"] is None
    assert reliability["providerFailureRate"] is None
    assert reliability["ingestionSuccessRate"] is None
    assert reliability["retryRate"] is None


# ------------------------------------------------------------------- editorial usefulness


async def test_editorial_acceptance_excludes_undecided_articles() -> None:
    """Draft and review_required are undecided, not rejected."""
    quality = {"articles": 10, "draft": 3, "review_required": 2, "published": 3,
               "rejected": 1, "archived": 1, "regenerated": 2, "regenerations": 3,
               "overridden": 1, "avg_impact_score": 61.0, "avg_impact_confidence": 0.85,
               "avg_semantic_confidence": 0.92, "impact_low": 2, "impact_medium": 5,
               "impact_high": 3}
    editorial = derive_editorial(quality, {"candidate": 4, "processed": 6, "ignored": 9,
                                           "duplicate": 2}, _generation())
    # 3 published of 5 resolved (3 published + 1 rejected + 1 archived), not of 10 created.
    assert editorial["editoriallyResolved"] == 5
    assert editorial["editorialAcceptanceRate"] == pytest.approx(0.6)
    # _rate rounds to 4dp, so compare at that precision rather than to full float.
    assert editorial["semanticAcceptanceRate"] == pytest.approx(6 / 9, abs=1e-4)
    assert editorial["regenerationRate"] == pytest.approx(0.2)
    assert editorial["candidatesCreated"] == 10


async def test_editorial_rates_are_none_before_anything_is_resolved() -> None:
    quality = {"articles": 2, "draft": 2, "review_required": 0, "published": 0,
               "rejected": 0, "archived": 0, "regenerated": 0, "regenerations": 0,
               "overridden": 0}
    editorial = derive_editorial(quality, {}, {"accepted": 0, "rejected": 0})
    assert editorial["editorialAcceptanceRate"] is None
    assert editorial["semanticAcceptanceRate"] is None


# ------------------------------------------- TEST 5: empty database handled gracefully


@pytest_asyncio.fixture(loop_scope="session")
async def quiet_window():
    """A window with no activity, achieved by asking for a zero-length one."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_empty_database_does_not_crash_and_says_so(quiet_window) -> None:
    async with SessionFactory() as session:
        data = await service.collect(session, days=1)

    assert isinstance(data, dict)
    assert data["status"] in ("ok", INSUFFICIENT)
    # Structure is always present, so a consumer never has to guard for missing keys.
    for key in ("sources", "candidates", "ingestion", "generation", "cost",
                "reliability", "quality", "failures"):
        assert key in data
    assert data["cost"]["totalTokens"] >= 0
    # Nothing is invented in the absence of data.
    if data["cost"]["status"] == INSUFFICIENT:
        assert data["cost"]["costPerArticle"] is None
        assert data["cost"]["monthlyProjections"] is None


async def test_collect_reports_insufficient_when_nothing_has_run() -> None:
    """Distinguishes "quiet" from "broken" for whoever reads the report."""
    async with SessionFactory() as session:
        totals = (await session.execute(text("""
          SELECT (SELECT count(*) FROM news_ingestion_runs) runs,
                 (SELECT coalesce(sum(generation_attempts), 0) FROM news_ingest_items) attempts
        """))).mappings().one()
        data = await service.collect(session, days=30)

    if not totals["runs"] and not totals["attempts"]:
        assert data["status"] == INSUFFICIENT


# --------------------------------------------------- TESTS 1 & 2: the command itself


REPO = pathlib.Path("/app") if pathlib.Path("/app/app").is_dir() \
    else pathlib.Path(__file__).resolve().parent.parent


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "app.news.cli", "metrics", *args],
        cwd=str(REPO), env=os.environ.copy(), capture_output=True, text=True, timeout=120,
    )


async def test_metrics_command_executes_successfully() -> None:
    result = run_cli("--days", "7")
    assert result.returncode == 0, result.stderr[-600:]
    for section in ("INGESTION", "CANDIDATES", "GENERATION", "TOKENS", "COST",
                    "EDITORIAL", "QUALITY"):
        assert section in result.stdout, f"missing section {section}"


async def test_json_output_is_valid_and_carries_the_required_keys() -> None:
    result = run_cli("--days", "7", "--json")
    assert result.returncode == 0, result.stderr[-600:]
    data = json.loads(result.stdout)
    for key in ("generation", "cost", "quality"):
        assert key in data, f"JSON export must expose {key!r}"
    assert isinstance(data["cost"], dict) and isinstance(data["quality"], dict)


async def test_json_and_human_output_come_from_the_same_derivations() -> None:
    """They cannot drift: the CLI formats, it does not compute."""
    source = (REPO / "app" / "news" / "cli.py").read_text()
    block = source[source.index("async def cmd_metrics("):source.index("def build_parser(")]
    for arithmetic in ("100 *", "/ accepted", "/ attempts", "* 30"):
        assert arithmetic not in block, (
            f"cmd_metrics must not compute {arithmetic!r}; derivation belongs in metrics.py"
        )


async def test_metrics_never_touches_occupation_scoring() -> None:
    async def snapshot() -> dict:
        async with SessionFactory() as s:
            return dict((await s.execute(text("""
              SELECT (SELECT count(*) FROM occupation_scores) legacy,
                     (SELECT count(*) FROM occupation_publications
                        WHERE activation_status='public') public_occupations,
                     (SELECT version FROM scoring_model_versions WHERE is_active) model
            """))).mappings().one())

    before = await snapshot()
    async with SessionFactory() as session:
        await service.collect(session, days=30)
    assert await snapshot() == before
