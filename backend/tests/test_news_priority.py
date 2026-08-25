"""news-generation-priority-v1 — the ordering policy for a scarce generation budget.

The fixtures below are real headlines and real feed summaries from the first controlled
production dry run of 2026-08-25, kept as regression cases because they are the exact items
that exposed the problem: relevance ranked datacentre hardware marketing above a study on AI
displacing entry-level workers. Only short factual metadata is reproduced — a headline and a
one-line paraphrase of the summary — which is what the policy actually reads.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.db.session import SessionFactory
from app.news import priority
from app.repositories.news_ingest import select_generation_candidates

# --- real production dry-run cases --------------------------------------------------------

STANFORD_JOBS = (
    "AI is hitting entry-level jobs hardest, Stanford study finds",
    "A Stanford study of payroll data finds employment for young workers in AI-exposed "
    "occupations has declined.",
    2,
)
NVIDIA_HARDWARE = (
    "With Groq 3 LPX in Full Production, NVIDIA Extends Vera Rubin Platform",
    "The rack-scale platform delivers agentic AI inference throughput for AI factories, "
    "with new GPUs and interconnect.",
    1,
)
GENERIC_ANNOUNCEMENT = (
    "Introducing AI Futures",
    "We are introducing AI Futures, a new initiative.",
    1,
)
CHATGPT_ADS = (
    "ChatGPT Ads expands across Europe",
    "Advertising in ChatGPT is expanding to more European markets.",
    1,
)
GAMING = (
    "Bring the Fire: Play Games on GeForce NOW With New Firefox Support",
    "Stream games on GeForce NOW in the browser.",
    1,
)
FRONTIER_AGENT = (
    "Introducing GPT-5.6 with computer use and long context",
    "The new frontier model operates a browser end-to-end, with improved reasoning and "
    "coding capability.",
    1,
)
ROBOTICS = (
    "Humanoid robot begins warehouse automation pilot",
    "The humanoid robot is deployed for picking in a logistics facility.",
    1,
)


def score(case: tuple[str, str | None, int]) -> priority.PriorityAssessment:
    title, excerpt, tier = case
    return priority.assess(title, excerpt, None, tier)


# --- 1. labour evidence ranks strongly ----------------------------------------------------


def test_labour_market_study_ranks_high() -> None:
    result = score(STANFORD_JOBS)
    assert result.band == "HIGH"
    assert result.score >= priority.HIGH_THRESHOLD
    assert "jobs" in result.signals["work"]


# --- 2. the inversion this policy exists to fix -------------------------------------------


def test_datacentre_marketing_does_not_outrank_labour_research() -> None:
    """The exact production inversion: relevance scored these 90 and 81 respectively."""
    hardware = score(NVIDIA_HARDWARE)
    labour = score(STANFORD_JOBS)
    assert hardware.score < labour.score
    assert hardware.band == "LOW"
    # It is deprioritised for what it is, not merely absent from the positive families.
    assert "hardware" in hardware.signals


def test_power_efficiency_marketing_stays_low() -> None:
    """A regression from calibration: "efficiency" briefly lifted this into MEDIUM.

    "Up to 30x More Work Per Watt" is a datacentre power-consumption claim. The words "work"
    and "efficiency" read as workplace vocabulary and are not — which is why "efficiency" is
    deliberately absent from the deployment family.
    """
    result = priority.assess(
        "Up to 30x More Work Per Watt: NVIDIA Vera Rubin NVL72 Sets Records",
        "Rack-scale agentic AI agent inference with data throughput for AI factories.",
        None, 1,
    )
    assert result.band == "LOW"


def test_ai_factory_is_hardware_marketing_not_physical_automation() -> None:
    """"AI factory" is datacentre branding; bare "factory" must not imply robotics."""
    result = score(NVIDIA_HARDWARE)
    assert not result.signals.get("physical")


def test_applied_productivity_evidence_ranks_high() -> None:
    """A real customer story about AI compressing engineering work.

    This scored 4 before calibration and was ranked 21st of 33 — the worst false negative of
    the first recalibration, because the policy knew "jobs" but not the occupational roles
    the platform is actually built around.
    """
    result = priority.assess(
        "Asana cleared 5 years of engineering work in 2 weeks with Codex",
        "The engineering team used Codex to clear a backlog, improving productivity.",
        None, 1,
    )
    assert result.band == "HIGH"
    assert "engineering work" in result.signals["work"]


# --- 3. capability without employment language --------------------------------------------


def test_frontier_agent_release_ranks_high_without_the_word_jobs() -> None:
    result = score(FRONTIER_AGENT)
    title, excerpt, _ = FRONTIER_AGENT
    assert "job" not in f"{title} {excerpt}".lower()
    assert result.band == "HIGH"


def test_physical_automation_ranks_high() -> None:
    assert score(ROBOTICS).band == "HIGH"


# --- 4, 5. promotional and consumer content -----------------------------------------------


def test_advertising_announcement_is_deprioritised() -> None:
    result = score(CHATGPT_ADS)
    assert result.band == "LOW"
    assert "promotional" in result.signals


def test_gaming_content_stays_low() -> None:
    result = score(GAMING)
    assert result.band == "LOW"
    assert "consumer" in result.signals


# --- 6. the substance gate ----------------------------------------------------------------


def test_generic_ai_announcement_cannot_reach_high_priority() -> None:
    """"AI" plus "introducing" is vocabulary, not substance."""
    result = score(GENERIC_ANNOUNCEMENT)
    assert result.score <= priority.GENERIC_CEILING
    assert result.band == "LOW"
    assert result.signals.get("substantive") is not True


def test_substance_gate_caps_even_a_trusted_source() -> None:
    result = priority.assess("Introducing something new", "An announcement.", None, 1)
    assert result.score <= priority.GENERIC_CEILING


# --- 7. determinism -----------------------------------------------------------------------


def test_scoring_is_deterministic() -> None:
    for case in (STANFORD_JOBS, NVIDIA_HARDWARE, FRONTIER_AGENT, GAMING):
        first = score(case)
        for _ in range(5):
            repeat = score(case)
            assert repeat.score == first.score
            assert repeat.band == first.band
            assert repeat.signals == first.signals


def test_presence_based_not_count_based() -> None:
    """Repeating a term must not buy more points — the keyword-stuffing failure mode."""
    once = priority.assess("Automation of workflows", "Automation.", None, 1)
    many = priority.assess(
        "Automation of workflows",
        "Automation automation automation workflows workflows automation.", None, 1,
    )
    assert once.score == many.score


# --- source treatment ---------------------------------------------------------------------


def test_source_tier_cannot_invert_editorial_value() -> None:
    """A tier-1 vendor post must not outrank tier-2 labour research on tier alone."""
    vendor_tier1 = priority.assess(*CHATGPT_ADS[:2], None, 1)
    research_tier2 = priority.assess(*STANFORD_JOBS[:2], None, 2)
    assert research_tier2.score > vendor_tier1.score


def test_source_tier_does_not_separate_tier_one_from_tier_two() -> None:
    title, excerpt, _ = STANFORD_JOBS
    assert priority.assess(title, excerpt, None, 1).score == \
        priority.assess(title, excerpt, None, 2).score


# --- missing excerpts ---------------------------------------------------------------------


def test_title_only_is_flagged_and_penalised_but_not_rejected() -> None:
    """Hugging Face supplies no summary at all; four of its items were candidates."""
    title, excerpt, tier = FRONTIER_AGENT
    with_excerpt = priority.assess(title, excerpt, None, tier)
    title_only = priority.assess(title, None, None, tier)
    assert title_only.title_only is True
    assert title_only.score < with_excerpt.score
    # A nudge, not a burial: a major release on a bare headline still ranks.
    assert with_excerpt.score - title_only.score == priority.TITLE_ONLY_PENALTY
    assert title_only.score > 0


def test_title_only_penalty_cannot_drive_a_score_negative() -> None:
    result = priority.assess("Ads", None, None, 3)
    assert result.score == 0


# --- 9. architectural isolation -----------------------------------------------------------


def test_priority_policy_imports_no_data_access() -> None:
    """Isolation asserted on imports, not on prose.

    A word-search would be worthless here: the policy legitimately scores the term
    "occupations" as work vocabulary. What matters is that it cannot reach a database, a
    model, or the intelligence engine at all — so the check is on what it imports.
    """
    import ast

    tree = ast.parse(open(priority.__file__, encoding="utf-8").read())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert imported == {"__future__", "dataclasses", "typing", "app.news.relevance"}, (
        f"priority policy must stay a pure lexical policy; imports were {sorted(imported)}")


def test_priority_policy_issues_no_sql() -> None:
    body = open(priority.__file__, encoding="utf-8").read().upper()
    for statement in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "JOIN "):
        assert statement not in body, f"priority policy contains SQL: {statement.strip()}"


# --- 8. generation selection uses priority ordering ---------------------------------------


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text(
            "DELETE FROM news_ingest_items WHERE canonical_url LIKE 'https://prio.test/%'"))
        await s.execute(text("DELETE FROM news_sources WHERE name = 'Priority Fixture Lab'"))


@pytest_asyncio.fixture(loop_scope="session")
async def priority_queue() -> list[tuple[int, str]]:
    """Two candidates whose relevance ordering is the reverse of their priority ordering.

    The high-relevance row is the datacentre case (relevance 90, low priority); the
    low-relevance row is the labour study (relevance 81, high priority). Under the previous
    `ORDER BY relevance_score DESC` the hardware item was selected first.
    """
    await _cleanup()
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(text(
            "SELECT id FROM news_ingest_items WHERE status = 'candidate'"
        ))).scalars().all())
        if parked:
            await s.execute(
                text("UPDATE news_ingest_items SET status='new' WHERE id = ANY(:ids)"),
                {"ids": parked})

    rows: list[tuple[int, str]] = []
    async with SessionFactory() as s, s.begin():
        source_id = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES ('Priority Fixture Lab', 'https://prio.test/rss.xml', 'https://prio.test',
                  'primary', 1, 'rss', false)
          RETURNING id
        """))).scalar_one()
        for n, (title, excerpt, _tier), relevance_score, label in (
            (1, NVIDIA_HARDWARE, 90, "hardware"),
            (2, STANFORD_JOBS, 81, "labour"),
        ):
            item_id = (await s.execute(text("""
              INSERT INTO news_ingest_items
                (source_id, external_url, canonical_url, original_title, original_excerpt,
                 source_published_at, content_hash, status, relevance_score,
                 relevance_policy_version, relevance_signals, title_fingerprint)
              VALUES (:src, :url, :url, :title, :excerpt,
                      now() - make_interval(hours => :n), :hash, 'candidate', :score,
                      'news-relevance-v1', '{"aiTerms":["ai"]}'::jsonb, :fp)
              RETURNING id
            """), {"src": source_id, "url": f"https://prio.test/item-{n}",
                   "title": title, "excerpt": excerpt, "hash": f"{n:064d}",
                   "n": n, "score": relevance_score, "fp": f"prio fixture {n}"})).scalar_one()
            rows.append((item_id, label))
    try:
        yield rows
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(
                    text("UPDATE news_ingest_items SET status='candidate' WHERE id = ANY(:ids)"),
                    {"ids": parked})


@pytest.mark.asyncio(loop_scope="session")
async def test_generation_selection_orders_by_priority_not_relevance(
    priority_queue: list[tuple[int, str]],
) -> None:
    by_label = {label: item_id for item_id, label in priority_queue}
    async with SessionFactory() as session:
        selected = await select_generation_candidates(session, limit=2)

    assert selected[0] == by_label["labour"], (
        "the labour study must be generated first despite its lower relevance score")
    assert selected[1] == by_label["hardware"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generation_selection_respects_the_limit(
    priority_queue: list[tuple[int, str]],
) -> None:
    by_label = {label: item_id for item_id, label in priority_queue}
    async with SessionFactory() as session:
        selected = await select_generation_candidates(session, limit=1)
    assert selected == [by_label["labour"]]
