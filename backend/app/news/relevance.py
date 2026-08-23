"""news-relevance-v1 — the deterministic AI-relevance prefilter.

This is a **prefilter**, not an editorial judgement. Its only question is:

    "Is this plausibly about an AI capability, product, model, agent, robotics or
     automation development worth spending a Phase 3 generation call on?"

It is therefore tuned to be permissive. A false negative silently loses a story forever; a
false positive costs one editor glance in the incoming queue. Those are not symmetric, and
the thresholds reflect it.

No LLM, no embeddings, no network. Same inputs always produce the same score, and the score
is stored with its policy version so a triage decision stays explicable after the policy
moves on.

## Scoring bands (0-100)

    AI-specific terminology              up to +40
    technical / product / capability     up to +25
    automation & work relevance          up to +20
    trusted AI-focused source            up to +15
    negative corporate/finance signals   down-weighted, never absolute

Ambiguous words ("model", "agent", "assistant", "vision") score only with supporting
context, or when the source is itself AI-specific — "Introducing Operator" from OpenAI is a
capability announcement; the same words from a general outlet are not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

POLICY_VERSION = "news-relevance-v1"

RelevanceOutcome = Literal["candidate", "ignored"]

# Explicit, configurable, tested. An item at or above CANDIDATE_THRESHOLD becomes a
# candidate; below it, ignored. The band between the two thresholds is still a candidate but
# is flagged uncertain so the queue can sort confident items first.
CANDIDATE_THRESHOLD = 40
CONFIDENT_THRESHOLD = 60

# --------------------------------------------------------------------------- vocabularies
# Unambiguous AI terminology. Presence is strong evidence on its own.
AI_TERMS: frozenset[str] = frozenset({
    "ai", "a.i.", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "foundation model", "frontier model",
    "generative ai", "genai", "multimodal", "transformer", "neural network",
    "diffusion model", "reinforcement learning", "rlhf", "fine-tuning", "finetuning",
    "inference", "training run", "pretraining", "chatbot", "copilot",
    "computer vision", "speech recognition", "text-to-speech", "speech-to-text",
    "image generation", "video generation", "text-to-video", "text-to-image",
    "code generation", "ai agent", "agentic", "computer use", "tool use",
    "open-weight", "open weights", "open source model", "context window",
    "hallucination", "prompt injection", "robotics", "humanoid robot",
    # Model family names. Absent from the first vocabulary, which was the largest
    # single source of false negatives on live data: a headline naming a model but not
    # the word "model" matched nothing at all.
    "gpt", "chatgpt", "claude", "gemini", "llama", "grok", "qwen", "deepseek",
    "sora", "codex", "copilot", "whisper", "stable diffusion",
    # Morphological variants. Token matching is exact, so "robotic" did not match
    # "robot" and a robotic-factory story was ignored.
    "robotic", "robots",
})

# Capability / product / release language. Evidence that something shipped or was measured.
CAPABILITY_TERMS: frozenset[str] = frozenset({
    "launch", "launches", "launched", "introducing", "announce", "announces", "announced",
    "release", "releases", "released", "available", "general availability", "now live",
    "preview", "beta", "rollout", "ships", "shipping", "unveil", "unveils",
    "benchmark", "benchmarks", "state-of-the-art", "sota", "outperform", "outperforms",
    "capability", "capabilities", "api", "sdk", "developer", "open source", "open-source",
    "research", "paper", "results", "breakthrough", "upgrade", "update", "version",
    "faster", "cheaper", "accuracy", "performance", "evaluation", "eval",
    # Third-person and progressive forms of verbs already present. Real headlines use
    # "introduces"/"expands" as often as "introducing"/"launch".
    "introduces", "expands", "expanding", "powered by", "brings", "adds",
})

# Work / automation relevance. The reason JobsVsAI cares at all.
WORK_TERMS: frozenset[str] = frozenset({
    "automation", "automate", "automates", "automated", "automating", "autonomous",
    "workflow", "workflows",
    "productivity", "worker", "workers", "workforce", "employee", "employees",
    "job", "jobs", "labor", "labour", "task", "tasks", "assistant", "agent", "agents",
    "customer support", "call center", "call centre", "warehouse", "logistics",
    "manufacturing", "self-driving", "driverless", "back office", "white-collar",
    "replace", "replaces", "augment", "augments", "headcount", "staffing",
    "autonomy", "factory", "assembly line", "fulfilment", "fulfillment",
})

# Ambiguous outside an AI context. Need a supporting AI term or an AI-specific source.
AMBIGUOUS_TERMS: frozenset[str] = frozenset({
    "model", "models", "agent", "agents", "assistant", "vision", "training",
    "learning", "neural", "intelligence", "reasoning", "prompt",
})

# Corporate/financial stories with no capability content. Down-weighted, never disqualifying:
# "OpenAI raises $5B to ship GPT-6" is still about a model.
NEGATIVE_TERMS: frozenset[str] = frozenset({
    "raises", "raised", "funding round", "series a", "series b", "series c", "series d",
    "valuation", "ipo", "share price", "stock", "shares", "earnings", "quarterly results",
    "revenue", "acquisition", "acquires", "merger", "invests", "investment",
    "appoints", "appointed", "names new", "steps down", "resigns", "hires",
    "chief executive", "cfo", "cto appointment", "board of directors",
    "office opening", "opens office", "opens new office", "office in",
    "headquarters", "expands its", "sponsorship", "sponsors",
    "award", "awards", "conference", "summit", "keynote", "partnership", "partners with",
    "lawsuit", "sues", "settlement", "regulator", "antitrust", "subpoena",
})

_NON_WORD = re.compile(r"[^a-z0-9\s.-]+")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class RelevanceAssessment:
    score: int
    outcome: RelevanceOutcome
    confident: bool
    policy_version: str
    signals: dict[str, object] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """The ingest status this assessment implies."""
        return "candidate" if self.outcome == "candidate" else "ignored"


def normalise(text: str | None) -> str:
    """Lowercase, strip punctuation that is not part of a term, collapse whitespace."""
    if not text:
        return ""
    lowered = text.lower().replace("&amp;", " ")
    return _WS.sub(" ", _NON_WORD.sub(" ", lowered)).strip()


def _matches(haystack: str, terms: Iterable[str]) -> list[str]:
    """Phrase-aware containment.

    Multi-word terms are matched as phrases; single words are matched on token boundaries,
    so "ai" does not fire inside "said" and "job" does not fire inside "jobs" twice.
    """
    found: list[str] = []
    tokens = set(haystack.split())
    for term in terms:
        if " " in term or "-" in term:
            if term in haystack:
                found.append(term)
        elif term in tokens:
            found.append(term)
        elif _versioned_token_present(term, tokens):
            found.append(term)
    return sorted(found)


def _versioned_token_present(term: str, tokens: set[str]) -> bool:
    """Match a family name carrying a version suffix: gpt-5, llama3, gemini-1.5.

    Real headlines almost never write a model family bare — it is "GPT-5.6", "Claude 4",
    "Llama 3.1". Exact token matching missed every one of them, which is how a live headline
    naming GPT-5.6 matched no AI term at all.

    Only a digit, hyphen or dot may follow, so this stays tight: "ai" matches "ai-powered"
    but not "aid", and "sora" does not match "sorafenib".
    """
    for token in tokens:
        if len(token) > len(term) and token.startswith(term) and token[len(term)] in "-.0123456789":
            return True
    return False


def assess(
    title: str,
    excerpt: str | None = None,
    categories: Iterable[str] | None = None,
    source_trust_tier: int = 3,
    source_is_ai_specific: bool = False,
) -> RelevanceAssessment:
    """Score one feed item 0-100 and decide candidate vs ignored.

    `source_is_ai_specific` is what lets a bare product name from a frontier lab through.
    "Introducing Operator" carries no AI vocabulary at all; from OpenAI it is obviously a
    capability announcement, and from a general outlet it is obviously not enough.
    """
    haystack = " ".join(filter(None, [
        normalise(title), normalise(excerpt), normalise(" ".join(categories or [])),
    ]))
    # The title carries most of the signal; a term appearing only in a boilerplate footer
    # should not count as strongly.
    title_text = normalise(title)

    ai_hits = _matches(haystack, AI_TERMS)
    capability_hits = _matches(haystack, CAPABILITY_TERMS)
    work_hits = _matches(haystack, WORK_TERMS)
    ambiguous_hits = _matches(haystack, AMBIGUOUS_TERMS)
    negative_hits = _matches(haystack, NEGATIVE_TERMS)

    # Scoring is presence-based, not count-based. A real headline — "Introducing GPT-5" —
    # carries one or two vocabulary hits, while a keyword-stuffed corporate post carries
    # many; counting rewarded exactly the wrong text. What matters is whether a category of
    # evidence is present at all, and whether it reached the title.
    ai_in_title = [term for term in ai_hits if term in title_text]
    ambiguous_in_title = [term for term in ambiguous_hits if term in title_text]

    # Ambiguous words only become AI evidence with real AI context or an AI-specific source:
    # "model" in a fashion story is not a signal, "model" on a frontier lab's blog is.
    ambiguous_counts = bool(ambiguous_hits) and (bool(ai_hits) or source_is_ai_specific)

    # --- AI terminology, up to 40
    ai_points = 0
    if ai_hits:
        ai_points = 20
    elif ambiguous_counts:
        ai_points = 12
    if ai_in_title or (ambiguous_counts and ambiguous_in_title):
        ai_points = min(40, ai_points + 20)

    # --- capability / product language, up to 25
    capability_points = 0
    if capability_hits:
        capability_points = 15
        if any(term in title_text for term in capability_hits):
            capability_points = 25

    # --- automation & work relevance, up to 20
    work_points = 0
    if work_hits:
        work_points = 12
        if any(term in title_text for term in work_hits):
            work_points = 20

    # --- source trust, up to 15. An AI-specific first-party source is the strong case:
    # everything it publishes is on-topic by construction.
    if source_is_ai_specific and source_trust_tier <= 1:
        source_points = 15
    elif source_trust_tier <= 1:
        source_points = 10
    elif source_trust_tier == 2:
        source_points = 6
    else:
        source_points = 0

    subtotal = ai_points + capability_points + work_points + source_points

    # --- negative signals. Proportional, capped, and never applied when the item also
    # carries strong AI capability evidence: a funding story that also ships a model is a
    # model story.
    has_strong_capability = bool(ai_in_title) and bool(capability_hits)
    penalty = 0
    if negative_hits and not has_strong_capability:
        penalty = min(30, len(negative_hits) * 12)
        # A purely corporate item with no AI vocabulary at all is penalised hardest.
        if not ai_hits:
            penalty = min(45, penalty + 15)

    score = max(0, min(100, subtotal - penalty))

    # Source floor. A first-party AI lab's own feed is on-topic by construction — almost
    # everything it publishes is a capability, model or research announcement — so an item
    # from one clears the candidate bar even when its wording is opaque. This is what lets
    # "Introducing Operator" through, and it is exactly the case a keyword filter cannot
    # reach. Withheld when negative signals are present, so a funding or appointment post
    # from the same source is not floated by its origin alone.
    # The floor needs *some* positive signal to stand on. Origin alone is not evidence:
    # "Lab opens new office in Dublin" from a frontier lab carries no AI, capability or work
    # vocabulary whatsoever and is not a capability announcement, however trusted the source.
    has_positive_signal = bool(ai_hits or capability_hits or work_hits or ambiguous_counts)
    floored = False
    if (source_is_ai_specific and source_trust_tier <= 1
            and not negative_hits and has_positive_signal
            and score < CANDIDATE_THRESHOLD):
        score = CANDIDATE_THRESHOLD
        floored = True

    outcome: RelevanceOutcome = "candidate" if score >= CANDIDATE_THRESHOLD else "ignored"

    return RelevanceAssessment(
        score=score,
        outcome=outcome,
        confident=score >= CONFIDENT_THRESHOLD,
        policy_version=POLICY_VERSION,
        signals={
            "aiTerms": ai_hits,
            "aiTermsInTitle": ai_in_title,
            "capabilityTerms": capability_hits,
            "workTerms": work_hits,
            "ambiguousTerms": ambiguous_hits,
            "negativeTerms": negative_hits,
            "points": {
                "ai": ai_points, "capability": capability_points,
                "work": work_points, "source": source_points, "penalty": -penalty,
            },
            "sourceFloorApplied": floored,
            "sourceTrustTier": source_trust_tier,
            "sourceIsAiSpecific": source_is_ai_specific,
            "thresholds": {"candidate": CANDIDATE_THRESHOLD, "confident": CONFIDENT_THRESHOLD},
        },
    )
