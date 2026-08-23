"""news-impact-v1: the deterministic Jobs Impact policy.

Pure unit tests — no database, no provider, no network. The policy is the one part of the
news system that must never drift, because a published level is only defensible if the same
five factors always produce it.
"""

import pytest

from app.news.generation import (
    GenerationInput,
    InvalidGeneratedBrief,
    NullGenerationProvider,
    ProviderNotConfigured,
    parse_provider_response,
)
from app.news.impact_policy import (
    FACTOR_WEIGHTS,
    POLICY_VERSION,
    InvalidImpactFactors,
    assess,
    classify,
    requires_review,
)
from app.news.pipeline import canonicalise_url, content_hash

FACTORS = {
    "capability_advancement": 80,
    "commercial_deployability": 70,
    "breadth_of_affected_work": 60,
    "adoption_speed": 50,
    "human_work_reduction_potential": 40,
}


def test_policy_version_and_weights_are_the_documented_ones() -> None:
    assert POLICY_VERSION == "news-impact-v1"
    assert {k: float(v) for k, v in FACTOR_WEIGHTS.items()} == {
        "capability_advancement": 0.30,
        "commercial_deployability": 0.25,
        "breadth_of_affected_work": 0.20,
        "adoption_speed": 0.15,
        "human_work_reduction_potential": 0.10,
    }
    assert sum(FACTOR_WEIGHTS.values()) == 1


def test_weighted_calculation_matches_the_published_formula() -> None:
    # 80*.30 + 70*.25 + 60*.20 + 50*.15 + 40*.10 = 24 + 17.5 + 12 + 7.5 + 4 = 65
    result = assess(FACTORS)
    assert float(result.score) == 65.0
    assert result.level == "medium"
    assert result.policy_version == "news-impact-v1"
    assert result.factors == FACTORS


def test_all_zero_and_all_hundred_are_the_extremes() -> None:
    assert float(assess(dict.fromkeys(FACTOR_WEIGHTS, 0)).score) == 0.0
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 0)).level == "low"
    assert float(assess(dict.fromkeys(FACTOR_WEIGHTS, 100)).score) == 100.0
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 100)).level == "high"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "low"), (34, "low"),           # 34 is the inclusive upper edge of low
        # The bands are specified as 0-34 / 35-69 / 70-100, and scores carry two decimals,
        # so 34.01-34.99 falls in the gap between the written bands. The rule applied is
        # the literal one: low is score <= 34, so anything above 34 is already medium.
        (34.01, "medium"), (34.5, "medium"), (34.99, "medium"),
        (35, "medium"), (69, "medium"), (69.99, "medium"),
        (70, "high"), (100, "high"),       # 70 is the inclusive lower edge of high
    ],
)
def test_exact_classification_boundaries(score: float, expected: str) -> None:
    assert classify(score) == expected


def test_uniform_factor_values_land_on_each_boundary_exactly() -> None:
    # Weights sum to 1, so a uniform value scores exactly that value. This pins the
    # boundaries through the real entry point, not just through classify().
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 34)).level == "low"
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 35)).level == "medium"
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 69)).level == "medium"
    assert assess(dict.fromkeys(FACTOR_WEIGHTS, 70)).level == "high"


def test_rounding_is_half_up_to_two_decimals() -> None:
    # 81*.30 + 81*.25 + 81*.20 + 81*.15 + 82*.10 = 81.1
    factors = FACTORS | {
        "capability_advancement": 81, "commercial_deployability": 81,
        "breadth_of_affected_work": 81, "adoption_speed": 81,
        "human_work_reduction_potential": 82,
    }
    assert float(assess(factors).score) == 81.10


def test_assessment_is_deterministic() -> None:
    assert assess(FACTORS).score == assess(FACTORS).score


@pytest.mark.parametrize("bad", [-1, 101, 1000, "high", None, 12.5, True])
def test_out_of_range_or_non_integer_factors_are_rejected(bad: object) -> None:
    with pytest.raises(InvalidImpactFactors):
        assess(FACTORS | {"capability_advancement": bad})


def test_missing_factor_is_rejected() -> None:
    incomplete = {k: v for k, v in FACTORS.items() if k != "adoption_speed"}
    with pytest.raises(InvalidImpactFactors):
        assess(incomplete)


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(None, True), (0.0, True), (0.79, True), (0.799, True), (0.80, False), (0.95, False)],
)
def test_confidence_below_the_minimum_forces_review(confidence, expected) -> None:
    assert requires_review(confidence) is expected


# ------------------------------------------------------------------ provider interface


def test_provider_interface_is_mockable_without_network() -> None:
    """A fake provider satisfies the interface with no HTTP client involved."""

    class FakeProvider:
        name = "fake"
        model = "fake-1"

        def generate_news_brief(self, payload):
            return parse_provider_response({
                # Phase 3 added the semantic verdict to the provider contract.
                "is_ai_news": True,
                "ai_relevance_confidence": 0.9,
                "relevance_reason": "Agent capability release for finance workflows.",
                "headline": "Lab ships an agent that files expense reports",
                "what_happened": "A vendor released an agent for expense workflows.",
                "why_it_matters_for_jobs": "Routine finance admin is the directly exposed task.",
                # Tags outside the controlled vocabulary are dropped, not fatal.
                "tags": ["AI Agents", "Automation", "AI Agents"],
                "job_areas": ["Finance", "Administration"],
                "impact_confidence": 0.86,
                "impact_reasoning": "Narrow task, broad deployment surface.",
                **FACTORS,
            })

    brief = FakeProvider().generate_news_brief(
        GenerationInput("t", "e", "https://example.com/a", "Example")
    )
    assert brief.headline.startswith("Lab ships")
    assert brief.tags == ["AI Agents", "Automation"]  # canonicalised and deduplicated
    assert float(assess(brief.factors).score) == 65.0


def test_null_provider_refuses_rather_than_inventing_a_brief() -> None:
    with pytest.raises(ProviderNotConfigured):
        NullGenerationProvider().generate_news_brief(
            GenerationInput("t", "e", "https://example.com/a", "Example")
        )


def test_provider_response_validation_rejects_malformed_payloads() -> None:
    valid = {
        "is_ai_news": True, "ai_relevance_confidence": 0.9, "relevance_reason": "R",
        "headline": "H", "what_happened": "W", "why_it_matters_for_jobs": "Y",
        "impact_confidence": 0.9, "impact_reasoning": "R", **FACTORS,
    }
    assert parse_provider_response(valid).impact_confidence == 0.9
    for bad in [
        {"headline": ""}, {"what_happened": "  "}, {"why_it_matters_for_jobs": None},
        {"impact_confidence": 1.5}, {"impact_confidence": "high"}, {"impact_reasoning": ""},
        {"tags": "finance"}, {"is_ai_news": "yes"}, {"ai_relevance_confidence": 2},
    ]:
        with pytest.raises((InvalidImpactFactors, InvalidGeneratedBrief)):
            parse_provider_response(valid | bad)


def test_canonical_url_strips_tracking_and_normalises_host() -> None:
    assert canonicalise_url("https://WWW.Example.com/a/b/?utm_source=x&id=7#top") == \
        "https://example.com/a/b?id=7"
    # Same article, two shared links -> one canonical identity. Scheme, www and the
    # trailing slash are all normalised away; only tracking parameters are dropped.
    assert canonicalise_url("https://example.com/a?utm_medium=rss") == \
        canonicalise_url("http://www.example.com/a/")
    assert canonicalise_url("http://example.com/a") == "https://example.com/a"


def test_content_hash_ignores_whitespace_and_case() -> None:
    assert content_hash("A  Title", "Body") == content_hash("a title", "body")
    assert content_hash("A", "B") != content_hash("A", "C")
