"""Provider-neutral news generation.

Phase 2 will plug a real provider (likely Gemini's free tier) in behind
`NewsGenerationProvider`. Nothing above this interface knows which provider ran: the API,
the repository and the impact policy all consume `GeneratedBrief`, never a provider
response. Swapping providers is a registry entry, not a redesign.

The provider returns prose and factor readings. It does NOT return an impact level, a
score, a slug, a source URL or a publication decision — those are computed or supplied by
JobsVsAI. A model that invents a source URL has fabricated a citation, so the interface
gives it no field in which to do so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.news.impact_policy import FACTOR_WEIGHTS, InvalidImpactFactors

# Bumped whenever the prompt changes shape, so a stored article records which prompt wrote
# it and regressions are attributable.
PROMPT_VERSION = "news-generation-v1"

# The semantic relevance contract, versioned separately from the prompt because its decision
# rules can tighten without the brief-writing instructions changing.
SEMANTIC_POLICY_VERSION = "news-semantic-relevance-v1"

# Below this, an accepted item still becomes an article but lands in review rather than
# draft: the model said yes without much conviction, and a human should look.
MINIMUM_SEMANTIC_CONFIDENCE = 0.70

# Controlled vocabularies. A model left to invent tags produces dozens of near-synonyms and
# a taxonomy nobody can filter on, so anything outside these lists is dropped rather than
# stored.
KNOWN_TAGS: tuple[str, ...] = (
    "AI Agents", "LLMs", "Robotics", "Coding", "Multimodal AI", "Computer Use",
    "AI Infrastructure", "Image Generation", "Video Generation", "Voice AI",
    "Automation", "Open Source AI", "AI Safety", "Benchmarks", "Enterprise AI",
)
MAX_TAGS = 5
MAX_JOB_AREAS = 6

# The editorial vocabulary for affected work. Free text, deliberately not SOC codes.
KNOWN_JOB_AREAS: tuple[str, ...] = (
    "Software Development", "Design", "Marketing", "Administration", "Finance",
    "Legal", "Healthcare", "Manufacturing", "Transportation", "Education",
    "Customer Support", "Research", "Media", "Sales", "IT Operations",
)

# Case-insensitive lookup so a model returning "ai agents" or "LLMS" still lands on the
# canonical spelling instead of being discarded on a capitalisation difference.
_TAG_LOOKUP = {tag.lower(): tag for tag in KNOWN_TAGS}
_JOB_AREA_LOOKUP = {area.lower(): area for area in KNOWN_JOB_AREAS}


@dataclass(frozen=True)
class GenerationInput:
    """What a provider is given. Feed metadata only — never a fetched article body.

    Everything here already exists on the ingest item from Phase 2. Nothing else from the
    database is sent: the model needs the story, not our schema.
    """

    source_title: str
    source_excerpt: str
    source_url: str
    source_name: str
    source_trust_tier: int = 3
    source_published_at: str | None = None
    categories: list[str] = field(default_factory=list)
    relevance_score: int | None = None
    relevance_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedBrief:
    """A validated provider response, before news-impact-v1 runs over the factors.

    Carries the semantic verdict as well as the brief. When `is_ai_news` is false the prose
    fields are permitted to be empty — the model was asked to judge first and write second,
    and making it write a brief for something it just rejected wastes tokens on text nobody
    will read.
    """

    is_ai_news: bool
    ai_relevance_confidence: float
    relevance_reason: str
    headline: str = ""
    what_happened: str = ""
    why_it_matters_for_jobs: str = ""
    tags: list[str] = field(default_factory=list)
    job_areas: list[str] = field(default_factory=list)
    factors: dict[str, int] = field(default_factory=dict)
    impact_confidence: float = 0.0
    impact_reasoning: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None


class NewsGenerationProvider(Protocol):
    """One structured call: brief and factor readings together, to keep tokens low."""

    name: str
    model: str

    def generate_news_brief(self, payload: GenerationInput) -> GeneratedBrief: ...


class ProviderNotConfigured(RuntimeError):
    """Raised when generation is attempted with no provider wired up."""


class InvalidGeneratedBrief(ValueError):
    """A provider response failed validation. Never coerced, never partially accepted."""


# Length ceilings. A model that returns an essay has misunderstood the brief, and storing it
# would put unbounded text on a page designed around a short summary.
MAX_HEADLINE_CHARS = 200
MAX_PROSE_CHARS = 1500
MAX_REASON_CHARS = 800


def _clean_text(raw: object, field_name: str, limit: int, required: bool = True) -> str:
    if raw is None or not isinstance(raw, str) or not raw.strip():
        if required:
            raise InvalidGeneratedBrief(f"{field_name} must be a non-empty string")
        return ""
    value = " ".join(raw.split())
    if len(value) > limit:
        raise InvalidGeneratedBrief(
            f"{field_name} is {len(value)} chars, over the {limit} limit"
        )
    return value


def _unit_interval(raw: object, field_name: str) -> float:
    if isinstance(raw, bool) or raw is None:
        raise InvalidGeneratedBrief(f"{field_name} must be a number between 0.0 and 1.0")
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise InvalidGeneratedBrief(
            f"{field_name} must be a number between 0.0 and 1.0"
        ) from exc
    if not (0.0 <= value <= 1.0):
        raise InvalidGeneratedBrief(f"{field_name} must be within 0.0-1.0, got {raw!r}")
    return value


def _controlled_list(
    raw: object, field_name: str, lookup: dict[str, str], cap: int
) -> list[str]:
    """Map to the controlled vocabulary, dropping anything unrecognised.

    Dropping rather than failing is deliberate: an otherwise good brief should not be lost
    because the model invented one extra tag. Values are matched case-insensitively and
    deduplicated, preserving the model's ordering so its first choice survives the cap.
    """
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise InvalidGeneratedBrief(f"{field_name} must be a list")
    picked: dict[str, None] = {}
    for item in raw:
        if not isinstance(item, str):
            continue
        canonical = lookup.get(item.strip().lower())
        if canonical:
            picked.setdefault(canonical, None)
    return list(picked)[:cap]


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_provider_response(raw: dict[str, object]) -> GeneratedBrief:
    """Validate a provider's JSON into a GeneratedBrief.

    Shared by every provider so validation cannot drift between them, and so a malformed
    response fails here rather than reaching the database. Nothing is silently coerced: an
    out-of-range factor is an error, not a value to clamp, because a model that returned 140
    for a 0-100 field has misunderstood the question and its other answers are suspect too.

    The impact *level* is deliberately not read even if a provider volunteers one. Only the
    five factors cross this boundary; news-impact-v1 decides the level.
    """
    if not isinstance(raw, dict):
        raise InvalidGeneratedBrief("Provider response must be a JSON object")

    is_ai_news = raw.get("is_ai_news")
    if not isinstance(is_ai_news, bool):
        raise InvalidGeneratedBrief("is_ai_news must be a boolean")

    confidence = _unit_interval(raw.get("ai_relevance_confidence"), "ai_relevance_confidence")
    reason = _clean_text(raw.get("relevance_reason"), "relevance_reason", MAX_REASON_CHARS)

    if not is_ai_news:
        # A rejection needs a verdict and a reason and nothing else. Requiring a brief here
        # would force the model to write copy for a story it just declined.
        #
        # Token usage still carries: a rejection costs a call like any other, and dropping
        # it here would understate recorded spend by exactly the rejections — which, on a
        # permissive prefilter, is the larger share of the traffic.
        return GeneratedBrief(
            is_ai_news=False, ai_relevance_confidence=confidence, relevance_reason=reason,
            input_tokens=_int_or_none(raw.get("_input_tokens")),
            output_tokens=_int_or_none(raw.get("_output_tokens")),
        )

    factors: dict[str, int] = {}
    for name in FACTOR_WEIGHTS:
        value = raw.get(name)
        if isinstance(value, bool) or value is None:
            raise InvalidImpactFactors(f"{name} is required and must be a number 0-100")
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise InvalidImpactFactors(f"{name} must be a number 0-100, got {value!r}") from exc
        if number != int(number):
            raise InvalidImpactFactors(f"{name} must be a whole number, got {value!r}")
        if not (0 <= number <= 100):
            raise InvalidImpactFactors(f"{name} must be within 0-100, got {value!r}")
        factors[name] = int(number)

    return GeneratedBrief(
        is_ai_news=True,
        ai_relevance_confidence=confidence,
        relevance_reason=reason,
        headline=_clean_text(raw.get("headline"), "headline", MAX_HEADLINE_CHARS),
        what_happened=_clean_text(raw.get("what_happened"), "what_happened", MAX_PROSE_CHARS),
        why_it_matters_for_jobs=_clean_text(
            raw.get("why_it_matters_for_jobs"), "why_it_matters_for_jobs", MAX_PROSE_CHARS
        ),
        tags=_controlled_list(raw.get("tags"), "tags", _TAG_LOOKUP, MAX_TAGS),
        job_areas=_controlled_list(
            raw.get("job_areas"), "job_areas", _JOB_AREA_LOOKUP, MAX_JOB_AREAS
        ),
        factors=factors,
        impact_confidence=_unit_interval(raw.get("impact_confidence"), "impact_confidence"),
        impact_reasoning=_clean_text(
            raw.get("impact_reasoning"), "impact_reasoning", MAX_REASON_CHARS
        ),
        input_tokens=_int_or_none(raw.get("_input_tokens")),
        output_tokens=_int_or_none(raw.get("_output_tokens")),
    )


class NullGenerationProvider:
    """The provider used until a real one is configured.

    It refuses rather than returning placeholder prose: a stub that invented a brief would
    put machine-written filler into an editorial queue that cannot tell it apart from a
    real generation. Manual article creation does not go through here.
    """

    name = "null"
    model = "none"

    def generate_news_brief(self, payload: GenerationInput) -> GeneratedBrief:
        raise ProviderNotConfigured(
            "No news generation provider is configured. Set NEWS_LLM_PROVIDER and its "
            "credentials, or create the article manually in the admin console."
        )


_PROVIDERS: dict[str, type] = {"null": NullGenerationProvider}


def register_provider(name: str, provider: type) -> None:
    """Phase 2 hook: a Gemini client registers itself here and nothing else changes."""
    _PROVIDERS[name] = provider


def get_provider(name: str | None) -> NewsGenerationProvider:
    provider = _PROVIDERS.get((name or "null").lower())
    if provider is None:
        raise ProviderNotConfigured(f"Unknown news generation provider: {name!r}")
    return provider()  # type: ignore[return-value]
