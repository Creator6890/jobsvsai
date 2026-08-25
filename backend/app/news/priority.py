"""news-generation-priority-v1 — deterministic ordering for a scarce resource.

This is **not** a second relevance filter, and it must never be confused with one.
`news-relevance-v1` answers a question about the item:

    "Is this plausibly AI news at all?"

This policy answers a question about *us*:

    "How valuable is this candidate to spend one scarce JobsVsAI generation call on?"

The two genuinely differ, and the first production dry run proved it. A datacentre hardware
announcement scored 90 on relevance — the highest of the whole run — because it carried a
dense spread of AI vocabulary. A Stanford study on AI displacing entry-level jobs scored 81.
By relevance both are AI news and the ranking is defensible. By editorial value for a career
intelligence platform the ordering is exactly backwards, and generation is capped at a
handful of calls per day, so ordering is the whole game.

Keeping the layers separate matters more than any individual weight here. Relevance decides
what enters the queue and is deliberately permissive, because a false negative loses a story
forever. Priority decides what leaves the queue first and is deliberately opinionated. Fold
them together and you get a filter that is both too strict to be a safety net and too vague
to be an editor.

## What this deliberately does not do

It does not reject anything. The lowest possible priority is 0, which still leaves an item in
the queue for an operator to pick up by hand. Nothing is hard-deleted, no status changes, and
no public surface exposes any of it — priority is internal triage material.

It reads no occupation, scoring, or publication data. Like every other `news_*` component it
is architecturally isolated from the intelligence engine.

No LLM, no embeddings, no network. The same candidate always produces the same score, so a
queue position stays explicable after the policy moves on.

## The shape of the score

Five substantive families earn points, one small evidence bonus rewards empirical work
research, and four depriority families subtract. Scoring is **presence-based and
title-weighted**, matching `news-relevance-v1` — counting occurrences rewards keyword-stuffed
corporate posts, which is the failure mode this policy exists to correct.

    A  work / labour             present +30   in title +55
    B  automation / agents       present +18   in title +32
    C  capability advancement    present +16   in title +28
    D  commercial deployment     present +10   in title +16
    E  physical automation       present +16   in title +28
       empirical evidence        present  +5   in title  +8
       configured source          flat    +4
       depriority families       present -12   in title -18   (capped at -40 total)
       title-only candidate              -5

The **substance gate** is what stops generic announcement vocabulary from ranking: an item
matching none of A-E is capped at `GENERIC_CEILING`, no matter how much AI language it
carries. "Introducing AI Futures" matches `ai` and `introducing` and nothing substantive, and
that is precisely the item a scarce generation call should not be spent on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.news.relevance import matches, normalise

POLICY_VERSION = "news-generation-priority-v1"

PriorityBand = Literal["HIGH", "MEDIUM", "LOW"]

HIGH_THRESHOLD = 60
MEDIUM_THRESHOLD = 35

# An item with no substantive signal cannot exceed this, however much AI vocabulary it has.
GENERIC_CEILING = 15

# --- A. Work and labour ------------------------------------------------------------------
# The core of the platform. Direct evidence about work, employment and the labour market.
WORK_TERMS: frozenset[str] = frozenset({
    "job", "jobs", "job market", "jobs report", "employment", "unemployment",
    "worker", "workers", "workforce", "workplace", "labor", "labour",
    "labor market", "labour market", "labor force", "labour force",
    "career", "careers", "occupation", "occupations", "profession", "professions",
    "hiring", "hire", "hires", "recruiter", "recruiting", "recruitment",
    "layoff", "layoffs", "redundancy", "redundancies", "job cuts", "headcount",
    "staffing", "entry-level", "junior developer", "graduate hiring",
    "white-collar", "blue-collar", "freelance", "freelancer", "gig work",
    "wage", "wages", "salary", "salaries", "productivity",
    "displacement", "displaced", "reskilling", "upskilling", "retraining",
    "job displacement", "future of work",
    # Occupational roles. An item that names an occupation is about work even when it never
    # says "jobs" — and occupations are what this platform is actually about.
    "developer", "developers", "engineer", "engineers", "engineering team",
    "engineering work", "software engineer", "analyst", "analysts",
    "designer", "designers", "lawyer", "lawyers", "paralegal",
    "accountant", "accountants", "auditor", "journalist", "journalists",
    "translator", "translators", "radiologist", "physician", "nurse", "nurses",
    "teacher", "teachers", "student", "students", "classroom", "tutor",
    "customer support", "call center", "call centre", "support team",
})

# --- B. Automation and agents ------------------------------------------------------------
# Can change how work is done even with no employment language anywhere in the text.
AUTOMATION_TERMS: frozenset[str] = frozenset({
    "automation", "automate", "automates", "automated", "automating",
    "autonomous", "autonomy", "agentic", "ai agent", "ai agents",
    "multi-agent", "agent framework", "autonomous agent", "research agent",
    "computer use", "tool use", "task execution", "end-to-end task",
    "workflow", "workflows", "workflow automation", "orchestration",
    "self-driving", "driverless", "back office", "straight-through",
})

# --- C. Capability advancement -----------------------------------------------------------
# Substantive capability movement. Deliberately excludes bare "ai", "model", "announced" and
# "introducing", which carry no information about whether anything actually advanced.
CAPABILITY_TERMS: frozenset[str] = frozenset({
    "frontier model", "frontier models", "model release", "new model",
    "reasoning", "reasoning model", "chain of thought",
    "multimodal", "long context", "long-context", "context window",
    "code generation", "coding", "code completion", "software engineering",
    "swe-bench", "benchmark", "benchmarks", "state of the art", "outperforms",
    "fine-tuning", "distillation", "open-weight", "open weights",
    "capability", "capabilities", "breakthrough", "surpasses", "human-level",
    "planning", "memory", "retrieval", "generalisation", "generalization",
    "codex", "copilot", "code assistant", "software creation", "agent mode",
})

# --- D. Commercial deployment ------------------------------------------------------------
# Real adoption in real organisations, which is how capability reaches actual work.
DEPLOYMENT_TERMS: frozenset[str] = frozenset({
    "enterprise", "enterprises", "deployment", "deployed", "rollout", "rolled out",
    "production use", "in production", "adoption", "adopted", "customers",
    "case study", "integration", "integrates", "integrated into",
    "business process", "operations", "at scale", "pilot programme", "pilot program",
    # Quantified outcomes inside a real organisation. Deliberately excludes "faster" and
    # "efficiency", which are hardware-benchmark vocabulary before they are workplace
    # vocabulary — "efficiency" alone lifted a datacentre power-consumption post into MEDIUM
    # on the production corpus, which is the exact category this policy pushes down.
    "cuts", "reduced", "reduces", "saves", "savings",
    "backlog", "time savings", "teams", "rolled out to",
})

# --- E. Physical automation --------------------------------------------------------------
# Bare "factory" is deliberately absent: "AI factory" is datacentre marketing, not robotics.
PHYSICAL_TERMS: frozenset[str] = frozenset({
    "robot", "robots", "robotic", "robotics", "humanoid", "humanoid robot",
    "factory automation", "smart factory", "warehouse automation", "warehouse robot",
    "assembly line", "manufacturing automation", "industrial automation",
    "autonomous vehicle", "autonomous vehicles", "self-driving car", "robotaxi",
    "drone", "drones", "picking", "fulfilment centre", "fulfillment center",
    "embodied", "embodied ai",
})

# --- Empirical evidence ------------------------------------------------------------------
# A small bonus. Research about work is the platform's native material, and a study is more
# useful to us than an assertion. Kept small so it cannot carry an item on its own.
EVIDENCE_TERMS: frozenset[str] = frozenset({
    "study", "studies", "research", "researchers", "survey", "report",
    "data", "analysis", "economists", "economist", "paper", "findings",
    "evidence", "measured", "experiment",
})

# --- Depriority families -----------------------------------------------------------------
# Compact and explainable rather than exhaustive. Each subtracts; none rejects.

PROMOTIONAL_TERMS: frozenset[str] = frozenset({
    "ads", "advertising", "advertisement", "advertisers", "sponsored", "sponsorship",
    "sponsors", "subscription", "subscriptions", "pricing", "price cut", "discount",
    "free tier", "promotion", "promotional", "sale", "offer", "deal",
    "partnership", "partners with", "collaboration with", "teams up",
    "award", "awards", "conference", "summit", "keynote", "webinar", "event",
    "anniversary", "celebrating", "milestone",
})

CONSUMER_TERMS: frozenset[str] = frozenset({
    "teen", "teens", "teenager", "kids", "children", "parents", "parental",
    "game", "games", "gaming", "gameplay", "gamers", "geforce", "console",
    "music", "playlist", "photo", "photos", "sticker", "stickers", "emoji",
    "wallpaper", "recipe", "recipes", "dinner", "shopping", "travel",
    "holiday", "sports", "fitness", "dating",
})

# Datacentre and silicon marketing. High AI-vocabulary density, minimal work implication.
HARDWARE_TERMS: frozenset[str] = frozenset({
    "gpu", "gpus", "chip", "chips", "silicon", "wafer", "semiconductor",
    "datacenter", "datacentre", "data center", "data centre", "ai factory",
    "rack", "racks", "superchip", "accelerator", "accelerators", "interconnect",
    "nvlink", "hbm", "teraflop", "teraflops", "petaflop", "exaflop",
    "per watt", "throughput", "supercomputer", "cluster", "clusters",
    "full production", "shipping", "form factor", "bandwidth",
})

CORPORATE_TERMS: frozenset[str] = frozenset({
    "funding round", "series a", "series b", "series c", "valuation", "ipo",
    "share price", "shares", "earnings", "quarterly results", "investor",
    "investors", "acquisition", "acquires", "merger", "appoints", "appointed",
    "steps down", "resigns", "board of directors", "chief executive",
})

_DEPRIORITY_FAMILIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("promotional", PROMOTIONAL_TERMS),
    ("consumer", CONSUMER_TERMS),
    ("hardware", HARDWARE_TERMS),
    ("corporate", CORPORATE_TERMS),
)

MAX_PENALTY = 40
TITLE_ONLY_PENALTY = 5


@dataclass(frozen=True)
class PriorityAssessment:
    """One candidate's generation priority, and enough detail to explain its position."""

    score: int
    band: PriorityBand
    policy_version: str
    signals: dict[str, object] = field(default_factory=dict)
    title_only: bool = False

    @property
    def top_signals(self) -> list[str]:
        """The handful of matched terms most worth showing an operator."""
        out: list[str] = []
        for key in ("work", "automation", "capability", "physical", "deployment", "evidence"):
            out.extend(str(t) for t in (self.signals.get(key) or []))
        for key in ("promotional", "consumer", "hardware", "corporate"):
            out.extend(f"-{t}" for t in (self.signals.get(key) or []))
        return out


def _band(score: int) -> PriorityBand:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _family_points(hits: list[str], title_text: str, present: int, in_title: int) -> int:
    """Presence-based, title-weighted. Matching twice is worth no more than matching once."""
    if not hits:
        return 0
    return in_title if any(term in title_text for term in hits) else present


def assess(
    title: str,
    excerpt: str | None = None,
    categories: list[str] | None = None,
    source_trust_tier: int = 3,
) -> PriorityAssessment:
    """Score one candidate 0-100 for generation priority.

    Deterministic and side-effect free. `source_trust_tier` contributes a small flat bonus
    for any configured source and deliberately does **not** separate tier 1 from tier 2 — a
    first-party vendor announcement must never outrank substantive labour research merely
    because the vendor is a frontier lab. Topic is what should decide the ordering, and the
    families above already carry it.
    """
    haystack = " ".join(filter(None, [
        normalise(title), normalise(excerpt), normalise(" ".join(categories or [])),
    ]))
    title_text = normalise(title)

    work = matches(haystack, WORK_TERMS)
    automation = matches(haystack, AUTOMATION_TERMS)
    capability = matches(haystack, CAPABILITY_TERMS)
    deployment = matches(haystack, DEPLOYMENT_TERMS)
    physical = matches(haystack, PHYSICAL_TERMS)
    evidence = matches(haystack, EVIDENCE_TERMS)

    score = 0
    score += _family_points(work, title_text, 30, 55)
    score += _family_points(automation, title_text, 18, 32)
    score += _family_points(capability, title_text, 16, 28)
    score += _family_points(deployment, title_text, 10, 16)
    score += _family_points(physical, title_text, 16, 28)
    score += _family_points(evidence, title_text, 5, 8)

    # Small, and deliberately uniform across configured sources. See the docstring.
    if source_trust_tier <= 2:
        score += 4

    signals: dict[str, object] = {
        "work": work, "automation": automation, "capability": capability,
        "deployment": deployment, "physical": physical, "evidence": evidence,
    }

    penalty = 0
    for name, terms in _DEPRIORITY_FAMILIES:
        hits = matches(haystack, terms)
        if hits:
            signals[name] = hits
            penalty += 18 if any(term in title_text for term in hits) else 12
    penalty = min(MAX_PENALTY, penalty)
    score -= penalty

    # A feed that supplies no summary leaves us judging on a headline alone, and leaves the
    # generator with less to work from. Small on purpose: a major release with a bare title
    # still matters, so this nudges rather than buries. Surfaced to the operator either way.
    title_only = not (excerpt and excerpt.strip())
    if title_only:
        score -= TITLE_ONLY_PENALTY

    has_substance = bool(work or automation or capability or deployment or physical)
    if not has_substance:
        score = min(score, GENERIC_CEILING)

    score = max(0, min(100, score))
    signals["substantive"] = has_substance
    signals["penalty"] = penalty
    if title_only:
        signals["titleOnly"] = True

    return PriorityAssessment(
        score=score, band=_band(score), policy_version=POLICY_VERSION,
        signals={k: v for k, v in signals.items() if v not in ([], False)},
        title_only=title_only,
    )
