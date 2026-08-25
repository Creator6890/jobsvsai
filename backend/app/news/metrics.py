"""Derived AI News metrics: economics, reliability and editorial usefulness.

Three layers, kept separate on purpose:

    repositories/news_metrics.py   SQL only — counts, sums, percentiles
    app/news/metrics.py            this module — every derived value
    app/news/cli.py                formatting only

Derivations lived in the CLI before this module existed, which meant a rate could not be
tested without capturing stdout, and a second consumer (a JSON export, an admin page) would
have had to reimplement them.

## The honesty rule

A rate computed over two observations is arithmetic, not evidence. Every derived block
reports the sample it rests on, and projections — cost per 100 articles, monthly spend —
are withheld entirely below `MIN_ECONOMIC_SAMPLE` rather than returned with a caveat that a
dashboard would drop. Raw sums are always reported: those are facts regardless of n.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories import news_metrics as repo

# Below this many successful generations, cost-per-article and anything extrapolated from it
# is noise. Chosen as the point where one outlier stops dominating the mean, not from theory.
MIN_ECONOMIC_SAMPLE = 5

# Publishing volumes to project monthly spend against, matching the product target of 2-3
# stories a day plus headroom.
PROJECTION_VOLUMES = (1, 2, 3, 5)

INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class TokenCost:
    """A cost figure and the price that produced it."""

    input_tokens: int
    output_tokens: int
    input_cost: float | None
    output_cost: float | None
    total: float | None
    priced: bool


def _rate(numerator: float, denominator: float) -> float | None:
    """A proportion, or None when there is nothing to divide by.

    None rather than 0.0: "no attempts" and "nothing succeeded" are different facts, and a
    zero would let a dashboard render a reassuring 0% failure rate for a pipeline that has
    never run.
    """
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    price_per_1m_input: float | None = None,
    price_per_1m_output: float | None = None,
) -> TokenCost:
    """Token spend, and a currency figure only when both prices are supplied.

    Pure and separately testable. Half a price is not a price: with only one side supplied
    the total would silently omit the other, so both are required or neither is used.
    """
    priced = price_per_1m_input is not None and price_per_1m_output is not None
    if not priced:
        return TokenCost(input_tokens, output_tokens, None, None, None, False)
    input_cost = round(input_tokens / 1_000_000 * price_per_1m_input, 6)
    output_cost = round(output_tokens / 1_000_000 * price_per_1m_output, 6)
    return TokenCost(
        input_tokens, output_tokens, input_cost, output_cost,
        round(input_cost + output_cost, 6), True,
    )


def derive_reliability(generation: dict, ingestion: dict, failures: list[dict]) -> dict:
    """Is the pipeline reliable?"""
    attempts = int(generation.get("attempts") or 0)
    items_attempted = int(generation.get("items_attempted") or 0)
    by_kind = {row["kind"]: int(row["total"]) for row in failures}

    return {
        "ingestionFetchAttempts": int(ingestion.get("fetch_attempts") or 0),
        "ingestionFetchSuccesses": int(ingestion.get("fetch_successes") or 0),
        "ingestionSuccessRate": _rate(
            int(ingestion.get("fetch_successes") or 0),
            int(ingestion.get("fetch_attempts") or 0),
        ),
        "generationAttempts": attempts,
        "generationSuccessRate": _rate(
            int(generation.get("accepted") or 0) + int(generation.get("rejected") or 0),
            attempts,
        ),
        # A rejection is a successful call: the model answered. Only `failed` means the call
        # itself did not complete, and conflating the two would make a working filter look
        # like an outage.
        "providerFailureRate": _rate(int(generation.get("failed") or 0), attempts),
        "timeoutRate": _rate(by_kind.get("timeout", 0), attempts),
        # Calls beyond the first per item. sum(attempts) counts calls; items_attempted counts
        # distinct candidates, so the difference is exactly the retries.
        "retryRate": _rate(max(0, attempts - items_attempted), attempts),
        "failuresByKind": by_kind,
        "latencyMeanMs": generation.get("latency_mean"),
        "latencyP50Ms": generation.get("latency_p50"),
        "latencyP95Ms": generation.get("latency_p95"),
        "latencyMaxMs": generation.get("latency_max"),
    }


def derive_economics(generation: dict, settings: Any) -> dict:
    """Is AI News economically viable?"""
    attempts = int(generation.get("attempts") or 0)
    accepted = int(generation.get("accepted") or 0)
    input_tokens = int(generation.get("input_tokens") or 0)
    output_tokens = int(generation.get("output_tokens") or 0)
    total_tokens = input_tokens + output_tokens

    cost = compute_cost(
        input_tokens, output_tokens,
        settings.news_llm_cost_per_1m_input, settings.news_llm_cost_per_1m_output,
    )

    economics: dict[str, Any] = {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "priced": cost.priced,
        "estimatedSpend": cost.total,
        "sampleSize": accepted,
        "minimumSampleForProjection": MIN_ECONOMIC_SAMPLE,
        # Per-attempt figures are honest at any n: they describe what was actually spent.
        "tokensPerAttempt": round(total_tokens / attempts, 1) if attempts else None,
        "costPerAttempt": round(cost.total / attempts, 6) if cost.priced and attempts else None,
    }

    if accepted < MIN_ECONOMIC_SAMPLE:
        # Withheld, not caveated. A dashboard renders numbers and drops footnotes, so a
        # figure that must not be trusted should not be returned at all.
        economics["status"] = INSUFFICIENT
        economics["tokensPerArticle"] = None
        economics["costPerArticle"] = None
        economics["costPer100Articles"] = None
        economics["monthlyProjections"] = None
        return economics

    economics["status"] = "ok"
    tokens_per_article = round(total_tokens / accepted, 1)
    economics["tokensPerArticle"] = tokens_per_article

    if not cost.priced:
        economics["costPerArticle"] = None
        economics["costPer100Articles"] = None
        economics["monthlyProjections"] = None
        return economics

    cost_per_article = round(cost.total / accepted, 6)
    economics["costPerArticle"] = cost_per_article
    economics["costPer100Articles"] = round(cost_per_article * 100, 4)
    # Projections use cost per *accepted* article, so they already carry the cost of the
    # rejections and failures it took to get there.
    economics["monthlyProjections"] = {
        f"{volume}_per_day": round(cost_per_article * volume * 30, 4)
        for volume in PROJECTION_VOLUMES
    }
    return economics


def derive_editorial(quality: dict, candidates: dict, generation: dict) -> dict:
    """Is generated content useful?

    Every figure here is a proxy. Nothing has been validated against whether a story
    mattered to a reader; these describe what editors did with the output.
    """
    accepted = int(generation.get("accepted") or 0)
    rejected = int(generation.get("rejected") or 0)
    assessed = accepted + rejected
    articles = int(quality.get("articles") or 0)
    published = int(quality.get("published") or 0)
    editorially_resolved = published + int(quality.get("rejected") or 0) \
        + int(quality.get("archived") or 0)

    return {
        "candidatesCreated": int(candidates.get("candidate") or 0)
        + int(candidates.get("processed") or 0),
        "candidatesIgnored": int(candidates.get("ignored") or 0),
        "candidatesDuplicate": int(candidates.get("duplicate") or 0),
        "candidatesGenerated": assessed,
        "articlesCreated": articles,
        "draft": int(quality.get("draft") or 0),
        "reviewRequired": int(quality.get("review_required") or 0),
        "published": published,
        "rejected": int(quality.get("rejected") or 0),
        "archived": int(quality.get("archived") or 0),
        "regeneratedArticles": int(quality.get("regenerated") or 0),
        "regenerations": int(quality.get("regenerations") or 0),
        "impactOverrides": int(quality.get("overridden") or 0),
        # The model's own filter: of the candidates it assessed, how many it judged AI news.
        "semanticAcceptanceRate": _rate(accepted, assessed),
        # The editor's verdict, over articles an editor has actually resolved. Articles still
        # sitting in draft or review are excluded — they are undecided, not rejected.
        "editorialAcceptanceRate": _rate(published, editorially_resolved),
        "editoriallyResolved": editorially_resolved,
        "regenerationRate": _rate(int(quality.get("regenerated") or 0), articles),
        "avgImpactScore": quality.get("avg_impact_score"),
        "avgImpactConfidence": quality.get("avg_impact_confidence"),
        "avgSemanticConfidence": quality.get("avg_semantic_confidence"),
        "impactDistribution": {
            "low": int(quality.get("impact_low") or 0),
            "medium": int(quality.get("impact_medium") or 0),
            "high": int(quality.get("impact_high") or 0),
        },
    }


async def collect(session: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Everything, raw and derived, in one structured result."""
    settings = get_settings()
    raw = await repo.collect(session, days)

    economics = derive_economics(raw["generation"], settings)
    reliability = derive_reliability(raw["generation"], raw["ingestion"], raw["failures"])
    editorial = derive_editorial(raw["quality"], raw["candidates"], raw["generation"])

    has_any_activity = bool(
        int(raw["ingestion"].get("runs") or 0) or int(raw["generation"].get("attempts") or 0)
    )

    return {
        "windowDays": days,
        "status": "ok" if has_any_activity else INSUFFICIENT,
        "sources": raw["sources"],
        "candidates": raw["candidates"],
        "ingestion": raw["ingestion"],
        "generation": raw["generation"],
        "cost": economics,
        "reliability": reliability,
        "quality": editorial,
        "failures": raw["failures"],
    }
