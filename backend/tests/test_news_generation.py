"""Phase 3: provider contract, response validation, and retry classification.

Pure unit tests. No network, no Gemini SDK import, no database. The provider is exercised
through a fake transport so every failure mode — malformed JSON, bad schema, 429, 5xx,
timeout, safety refusal — is reproducible.
"""

import json

import pytest

from app.news.generation import (
    KNOWN_JOB_AREAS,
    KNOWN_TAGS,
    MAX_JOB_AREAS,
    MAX_TAGS,
    MINIMUM_SEMANTIC_CONFIDENCE,
    PROMPT_VERSION,
    SEMANTIC_POLICY_VERSION,
    GenerationInput,
    InvalidGeneratedBrief,
    NullGenerationProvider,
    ProviderNotConfigured,
    parse_provider_response,
)
from app.news.impact_policy import InvalidImpactFactors, assess
from app.news.prompts import RESPONSE_SCHEMA, build_system_instruction, build_user_content

FACTORS = {
    "capability_advancement": 84, "commercial_deployability": 88,
    "breadth_of_affected_work": 71, "adoption_speed": 82,
    "human_work_reduction_potential": 65,
}
ACCEPTED = {
    "is_ai_news": True, "ai_relevance_confidence": 0.94,
    "relevance_reason": "Commercially deployable coding-agent capability release",
    "headline": "Lab expands autonomous coding capabilities",
    "what_happened": "A vendor shipped an agent that completes multi-step coding tasks.",
    "why_it_matters_for_jobs": "Routine implementation work is the directly exposed task.",
    "tags": ["AI Agents", "Coding"], "job_areas": ["Software Development", "IT Operations"],
    "impact_confidence": 0.91, "impact_reasoning": "Broad deployment surface.", **FACTORS,
}
REJECTED = {
    "is_ai_news": False, "ai_relevance_confidence": 0.88,
    "relevance_reason": "Funding round with no capability change.",
}
PAYLOAD = GenerationInput(
    source_title="Lab ships coding agent", source_excerpt="An agent for multi-step tasks.",
    source_url="https://lab.example.com/a", source_name="Example Lab",
    source_trust_tier=1, relevance_score=80, relevance_signals=["ai agent", "launch"],
)


# ------------------------------------------------------------------------- versioning


def test_versions_are_the_documented_ones() -> None:
    # The two move independently on purpose: v2 widened the semantic scope to admit
    # empirical work evidence, while Step 2 and Step 3 of the prompt were untouched, so
    # articles stay attributable to the same brief-writing instructions.
    assert PROMPT_VERSION == "news-generation-v1"
    assert SEMANTIC_POLICY_VERSION == "news-semantic-relevance-v2"
    assert MINIMUM_SEMANTIC_CONFIDENCE == 0.70


def test_prompt_states_the_rubric_and_forbids_deciding_the_level() -> None:
    """The model supplies evidence; JobsVsAI computes the level."""
    system = build_system_instruction()
    for factor in FACTORS:
        assert factor in system, f"{factor} is not defined in the rubric"
    assert "never assign an impact level or score" in system.lower()
    assert "is_ai_news" in system
    # The schema must not offer the model a field in which to decide publication or level.
    for forbidden in ("impact_level", "impact_score", "status", "published", "source_url"):
        assert forbidden not in RESPONSE_SCHEMA["properties"], forbidden


def test_user_content_sends_only_feed_metadata() -> None:
    content = build_user_content(PAYLOAD)
    assert "Lab ships coding agent" in content
    assert "Example Lab" in content
    # The deterministic score is labelled as permissive, not as a recommendation.
    assert "NOT a recommendation" in content


# ------------------------------------------------------------------------- validation


def test_accepted_response_parses() -> None:
    brief = parse_provider_response(ACCEPTED)
    assert brief.is_ai_news is True
    assert brief.factors == FACTORS
    assert brief.tags == ["AI Agents", "Coding"]
    assert float(assess(brief.factors).score) == 80.2


def test_rejected_response_needs_no_prose() -> None:
    """A rejection carries a verdict and a reason; forcing a brief would waste tokens."""
    brief = parse_provider_response(REJECTED)
    assert brief.is_ai_news is False
    assert brief.relevance_reason.startswith("Funding round")
    assert brief.headline == "" and brief.what_happened == ""


def test_missing_required_fields_are_rejected() -> None:
    for missing in ("is_ai_news", "ai_relevance_confidence", "relevance_reason"):
        payload = {k: v for k, v in ACCEPTED.items() if k != missing}
        with pytest.raises((InvalidGeneratedBrief, InvalidImpactFactors)):
            parse_provider_response(payload)
    for missing in ("headline", "what_happened", "why_it_matters_for_jobs", "impact_reasoning"):
        payload = {k: v for k, v in ACCEPTED.items() if k != missing}
        with pytest.raises(InvalidGeneratedBrief):
            parse_provider_response(payload)


@pytest.mark.parametrize("bad", [101, 140, -1, "high", None, 12.5, True])
def test_out_of_range_factors_are_rejected_not_clamped(bad) -> None:
    """A model that returns 140 for a 0-100 field misunderstood the question."""
    with pytest.raises(InvalidImpactFactors):
        parse_provider_response(ACCEPTED | {"capability_advancement": bad})


@pytest.mark.parametrize("bad", [1.5, -0.1, "very", None, 2])
def test_out_of_range_confidence_is_rejected(bad) -> None:
    with pytest.raises(InvalidGeneratedBrief):
        parse_provider_response(ACCEPTED | {"ai_relevance_confidence": bad})
    with pytest.raises(InvalidGeneratedBrief):
        parse_provider_response(ACCEPTED | {"impact_confidence": bad})


def test_non_boolean_is_ai_news_is_rejected() -> None:
    for bad in ("true", 1, None, "yes"):
        with pytest.raises(InvalidGeneratedBrief):
            parse_provider_response(ACCEPTED | {"is_ai_news": bad})


def test_overlong_prose_is_rejected() -> None:
    with pytest.raises(InvalidGeneratedBrief):
        parse_provider_response(ACCEPTED | {"what_happened": "word " * 2000})
    with pytest.raises(InvalidGeneratedBrief):
        parse_provider_response(ACCEPTED | {"headline": "x" * 300})


def test_a_volunteered_impact_level_is_ignored() -> None:
    """Only the five factors cross the boundary. The level is never read."""
    brief = parse_provider_response(ACCEPTED | {"impact_level": "high", "impact_score": 99})
    assert not hasattr(brief, "impact_level")
    assert float(assess(brief.factors).score) == 80.2


# ------------------------------------------------------------- controlled vocabularies


def test_unknown_tags_and_job_areas_are_dropped_not_fatal() -> None:
    """An invented tag must not cost an otherwise good brief."""
    brief = parse_provider_response(ACCEPTED | {
        "tags": ["AI Agents", "Totally Invented Tag", "Coding"],
        "job_areas": ["Software Development", "Underwater Basket Weaving"],
    })
    assert brief.tags == ["AI Agents", "Coding"]
    assert brief.job_areas == ["Software Development"]


def test_vocabulary_matching_is_case_insensitive_and_deduplicated() -> None:
    brief = parse_provider_response(ACCEPTED | {
        "tags": ["ai agents", "AI AGENTS", "robotics"],
        "job_areas": ["software development", "Software Development"],
    })
    assert brief.tags == ["AI Agents", "Robotics"]
    assert brief.job_areas == ["Software Development"]


def test_tag_and_job_area_counts_are_capped() -> None:
    brief = parse_provider_response(ACCEPTED | {
        "tags": list(KNOWN_TAGS), "job_areas": list(KNOWN_JOB_AREAS),
    })
    assert len(brief.tags) == MAX_TAGS
    assert len(brief.job_areas) == MAX_JOB_AREAS


def test_non_list_tags_are_rejected() -> None:
    with pytest.raises(InvalidGeneratedBrief):
        parse_provider_response(ACCEPTED | {"tags": "AI Agents"})


# ------------------------------------------------------------------- provider behaviour


class FakeResponse:
    """Shaped like a google-genai GenerateContentResponse."""

    def __init__(self, text: str, usage=None) -> None:
        self.text = text
        self.usage_metadata = usage


class FakeUsage:
    """Gemini 3 bills reasoning tokens separately, so total exceeds prompt + candidates."""

    def __init__(self, prompt: int, candidates: int, thoughts: int = 0) -> None:
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.thoughts_token_count = thoughts
        self.total_token_count = prompt + candidates + thoughts


def build_provider(responses, sleep=lambda _s: None):
    """A GeminiGenerationProvider whose transport is a scripted list.

    Mirrors the stable `client.models.generate_content` surface the provider actually uses.
    """
    from app.news.gemini import GeminiGenerationProvider

    provider = GeminiGenerationProvider(api_key="test-key-not-real", model="test-model",
                                        sleep=sleep)
    calls = {"n": 0}

    class FakeModels:
        def generate_content(self, **kwargs):
            calls["n"] += 1
            item = responses[min(calls["n"] - 1, len(responses) - 1)]
            if isinstance(item, Exception):
                raise item
            return item

    class FakeClient:
        models = FakeModels()

    provider._client = FakeClient()
    return provider, calls


def test_provider_satisfies_the_interface() -> None:
    from app.news.gemini import GeminiGenerationProvider

    provider, _ = build_provider([FakeResponse(json.dumps(ACCEPTED))])
    assert provider.name == "gemini"
    assert provider.model == "test-model"
    assert callable(provider.generate_news_brief)
    assert isinstance(provider, GeminiGenerationProvider)


def test_provider_requires_an_api_key() -> None:
    from app.news.gemini import GeminiGenerationProvider

    for empty in ("", "   ", None):
        with pytest.raises(ProviderNotConfigured):
            GeminiGenerationProvider(api_key=empty)


def test_provider_parses_a_valid_structured_response() -> None:
    provider, calls = build_provider([
        FakeResponse(json.dumps(ACCEPTED), usage=FakeUsage(1200, 340, thoughts=90))
    ])
    brief = provider.generate_news_brief(PAYLOAD)
    assert brief.is_ai_news is True
    assert brief.input_tokens == 1200
    # Output is derived from the total so reasoning tokens are counted; reading
    # candidates_token_count alone would understate the bill by the thoughts count.
    assert brief.output_tokens == 430
    assert calls["n"] == 1, "one candidate must cost exactly one call"


def test_rejections_still_record_token_usage() -> None:
    """A rejection costs a call. Dropping its usage understated spend by the larger share
    of traffic, since a permissive prefilter sends more rejections than acceptances."""
    provider, _ = build_provider([
        FakeResponse(json.dumps(REJECTED), usage=FakeUsage(900, 40, thoughts=20))
    ])
    brief = provider.generate_news_brief(PAYLOAD)
    assert brief.is_ai_news is False
    assert brief.input_tokens == 900 and brief.output_tokens == 60


def test_missing_usage_metadata_does_not_fail_generation() -> None:
    provider, _ = build_provider([FakeResponse(json.dumps(ACCEPTED))])
    brief = provider.generate_news_brief(PAYLOAD)
    assert brief.input_tokens is None and brief.output_tokens is None


def test_malformed_json_is_not_retried() -> None:
    """A model that answered badly will answer badly again; retrying burns free quota."""
    from app.news.gemini import GeminiError

    provider, calls = build_provider([FakeResponse("not json at all")])
    with pytest.raises(GeminiError) as caught:
        provider.generate_news_brief(PAYLOAD)
    assert caught.value.retryable is False
    assert calls["n"] == 1


def test_schema_invalid_response_is_not_retried() -> None:
    from app.news.gemini import GeminiError

    provider, calls = build_provider([
        FakeResponse(json.dumps(ACCEPTED | {"capability_advancement": 140}))
    ])
    with pytest.raises(GeminiError) as caught:
        provider.generate_news_brief(PAYLOAD)
    assert caught.value.retryable is False
    assert calls["n"] == 1


def test_empty_response_is_treated_as_a_safety_refusal_and_not_retried() -> None:
    from app.news.gemini import GeminiError

    provider, calls = build_provider([FakeResponse("")])
    with pytest.raises(GeminiError) as caught:
        provider.generate_news_brief(PAYLOAD)
    assert caught.value.retryable is False and calls["n"] == 1


class RateLimited(Exception):
    code = 429


class ServerError(Exception):
    code = 503


class ReadTimeout(Exception):
    pass


class Unauthorized(Exception):
    code = 401


def test_rate_limit_is_retried_then_succeeds() -> None:
    provider, calls = build_provider([RateLimited(), FakeResponse(json.dumps(ACCEPTED))])
    assert provider.generate_news_brief(PAYLOAD).is_ai_news is True
    assert calls["n"] == 2


def test_server_error_is_retried() -> None:
    provider, calls = build_provider([ServerError(), ServerError(),
                                      FakeResponse(json.dumps(ACCEPTED))])
    assert provider.generate_news_brief(PAYLOAD).is_ai_news is True
    assert calls["n"] == 3


def test_timeout_is_retried() -> None:
    provider, calls = build_provider([ReadTimeout(), FakeResponse(json.dumps(REJECTED))])
    assert provider.generate_news_brief(PAYLOAD).is_ai_news is False
    assert calls["n"] == 2


def test_retries_are_bounded() -> None:
    from app.news.gemini import MAX_ATTEMPTS, GeminiError

    provider, calls = build_provider([RateLimited()])
    with pytest.raises(GeminiError):
        provider.generate_news_brief(PAYLOAD)
    assert calls["n"] == MAX_ATTEMPTS, "retries must not be unbounded"


def test_credential_failure_is_not_retried_and_never_echoes_the_key() -> None:
    from app.news.gemini import GeminiError

    provider, calls = build_provider([Unauthorized()])
    with pytest.raises(GeminiError) as caught:
        provider.generate_news_brief(PAYLOAD)
    assert caught.value.retryable is False and calls["n"] == 1
    assert "test-key-not-real" not in str(caught.value)


def test_no_error_message_can_leak_the_api_key() -> None:
    from app.news.gemini import GeminiError

    class Leaky(Exception):
        code = 400

    provider, _ = build_provider([Leaky("failed for key test-key-not-real")])
    with pytest.raises(GeminiError) as caught:
        provider.generate_news_brief(PAYLOAD)
    assert "test-key-not-real" not in str(caught.value), "the key must never reach a message"


def test_null_provider_still_refuses() -> None:
    with pytest.raises(ProviderNotConfigured):
        NullGenerationProvider().generate_news_brief(PAYLOAD)
