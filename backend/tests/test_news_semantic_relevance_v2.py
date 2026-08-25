"""news-semantic-relevance-v2 — the semantic gate's scope contract.

v1 defined AI news as a capability or deployment change and nothing else. Applied to the first
production corpus it rejected the Stanford study on AI and entry-level hiring at 0.95
confidence — correctly under its own rules, and uselessly for a career-intelligence product,
because that study is the single most on-topic item the pipeline had found. v2 adds empirical
work evidence as a first-class category without loosening the boundary against opinion.

These tests do **not** call a provider. The semantic verdict is the model's to make; what is
testable here is the contract we hand it — that the criteria say what we think they say — plus
the code paths around the verdict. A fake provider covers the routing.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.db.session import SessionFactory
from app.news import prompts
from app.news.generation import PROMPT_VERSION, SEMANTIC_POLICY_VERSION
from app.repositories.news_ingest import (
    requeue_for_reassessment,
    select_generation_candidates,
)

CRITERIA = prompts.RELEVANCE_CRITERIA.lower()
SYSTEM = prompts.build_system_instruction().lower()


# --- versioning ---------------------------------------------------------------------------


def test_semantic_policy_is_versioned_to_v2() -> None:
    assert SEMANTIC_POLICY_VERSION == "news-semantic-relevance-v2"


def test_prompt_version_is_not_bumped() -> None:
    """Step 2 and Step 3 are unchanged, so articles stay attributable to the same writer.

    The two versions are deliberately separate: the decision rules moved, the brief-writing
    and impact instructions did not.
    """
    assert PROMPT_VERSION == "news-generation-v1"


def test_criteria_are_carried_into_the_system_instruction() -> None:
    assert "step 1" in SYSTEM
    assert "jobsvsai" in SYSTEM


# --- category A: capability, preserved -----------------------------------------------------


@pytest.mark.parametrize("phrase", [
    "new model release",
    "agent, tool-use or computer-use capability",
    "robotics or physical-automation capability",
    "coding-automation release",
    "commercially deployable automation system",
])
def test_capability_acceptance_is_retained(phrase: str) -> None:
    """v2 must not weaken the path v1 already got right."""
    assert phrase in CRITERIA


# --- category B: deployment, preserved -----------------------------------------------------


def test_deployment_acceptance_is_explicit() -> None:
    assert "enterprise deployment or production rollout" in CRITERIA
    assert "doing real work inside an organisation" in CRITERIA


# --- category C: the missing category ------------------------------------------------------


@pytest.mark.parametrize("phrase", [
    "employment, hiring, layoffs, displacement",
    "wages, earnings or entry-level opportunity",
    "task substitution, task augmentation or work compression",
    "productivity, throughput or time saved",
    "workforce structure, staffing patterns or occupational change",
])
def test_empirical_work_evidence_is_a_first_class_category(phrase: str) -> None:
    assert phrase in CRITERIA


def test_evidence_does_not_require_an_announcement() -> None:
    """The exact failure mode of v1: no model shipped, therefore rejected."""
    assert "does not require any new model or deployment to be announced" in CRITERIA
    assert "the evidence itself is" in CRITERIA


def test_the_stanford_case_is_named_as_in_scope() -> None:
    """The production rejection is written into the prompt as a worked example.

    Naming the case that broke v1 is cheaper than hoping the general rule covers it.
    """
    assert "entry-level hiring is squarely in scope" in CRITERIA
    assert "announces no model and ships no product" in CRITERIA


@pytest.mark.parametrize("form", [
    "academic research", "labour-market datasets", "credible surveys",
    "company studies reporting measured outcomes", "independent reporting",
])
def test_acceptable_evidence_forms_are_enumerated(form: str) -> None:
    assert form in CRITERIA


# --- the negative boundary -----------------------------------------------------------------


@pytest.mark.parametrize("phrase", [
    "funding rounds, valuations, ipos",
    "executive appointments, hires, departures",
    "conference attendance, keynotes, sponsorships, awards",
    "advertising or marketing rollouts",
    "generic corporate partnerships",
])
def test_existing_rejections_survive(phrase: str) -> None:
    assert phrase in CRITERIA


@pytest.mark.parametrize("phrase", [
    "opinion columns, essays and think pieces",
    "predictions, forecasts and speculation with no supporting data",
    "broad commentary that ai will change jobs, with nothing measured",
    "ethics or policy debate with no development and no findings",
])
def test_opinion_and_speculation_are_rejected_explicitly(phrase: str) -> None:
    """Widening to evidence must not widen to commentary about the same subject."""
    assert phrase in CRITERIA


def test_work_vocabulary_alone_cannot_confer_relevance() -> None:
    """The failure mode v2 could plausibly introduce, blocked in the prompt itself."""
    assert "does not become relevant merely because it uses the words" in CRITERIA
    assert "jobs, workers, employment, automation or future of work" in CRITERIA


def test_the_gate_demands_something_observed_or_shipped() -> None:
    assert "reports something observed, measured or shipped" in CRITERIA
    assert "if you cannot name what was measured or what was built" in CRITERIA


def test_evidence_and_opinion_are_contrasted_directly() -> None:
    assert "evidence versus opinion" in CRITERIA
    assert "about evidence, not about subject matter" in CRITERIA


# --- source attribution --------------------------------------------------------------------


def test_first_party_evidence_is_relevant_but_not_verified() -> None:
    """Relevance and credibility are different questions; the prompt must not merge them."""
    assert "vendor case study" in CRITERIA
    assert "not a judgement that the claim has been independently verified" in CRITERIA
    assert "the company's report, not as established fact" in CRITERIA


def test_attribution_is_carried_into_the_brief() -> None:
    assert "carry that distinction into" in CRITERIA


# --- isolation ------------------------------------------------------------------------------


def test_prompt_references_no_occupation_or_scoring_data() -> None:
    body = prompts.RELEVANCE_CRITERIA + prompts.SYSTEM_INSTRUCTION
    for forbidden in ("soc_code", "occupation_publications", "scoring_model",
                      "production_occupation", "replacement_risk", "ai exposure"):
        assert forbidden not in body.lower()


def test_generation_gate_and_publication_path_unchanged() -> None:
    """v2 changes what counts as relevant, and must change nothing about safety."""
    import inspect

    from app.news import generation_service

    source = inspect.getsource(generation_service)
    assert source.count(".publish(") == 0
    assert "news_auto_publish" not in source
    assert source.count("generation_enabled") >= 3
    assert '"published"' not in inspect.getsource(generation_service.decide_status)


# --- Step 8: the operator requeue path ------------------------------------------------------


async def _cleanup() -> None:
    async with SessionFactory() as s, s.begin():
        await s.execute(text(
            "DELETE FROM news_ingest_items WHERE canonical_url LIKE 'https://requeue.test/%'"))
        await s.execute(text("DELETE FROM news_sources WHERE name = 'Requeue Fixture Lab'"))


@pytest_asyncio.fixture(loop_scope="session")
async def rejected_item() -> int:
    """One item rejected by v1, exactly as production candidate 25 now stands."""
    await _cleanup()
    async with SessionFactory() as s, s.begin():
        parked = list((await s.execute(text(
            "SELECT id FROM news_ingest_items WHERE status = 'candidate'"))).scalars().all())
        if parked:
            await s.execute(
                text("UPDATE news_ingest_items SET status='new' WHERE id = ANY(:ids)"),
                {"ids": parked})
    async with SessionFactory() as s, s.begin():
        source_id = (await s.execute(text("""
          INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier,
                                    feed_format, enabled)
          VALUES ('Requeue Fixture Lab', 'https://requeue.test/rss.xml',
                  'https://requeue.test', 'secondary', 2, 'rss', false)
          RETURNING id
        """))).scalar_one()
        item_id = (await s.execute(text("""
          INSERT INTO news_ingest_items
            (source_id, external_url, canonical_url, original_title, original_excerpt,
             source_published_at, content_hash, status, relevance_score,
             relevance_policy_version, title_fingerprint,
             is_ai_news, ai_relevance_confidence, ai_relevance_reason,
             semantic_policy_version, generation_attempts, generation_attempted_at)
          VALUES (:src, 'https://requeue.test/item-1', 'https://requeue.test/item-1',
                  'AI is hitting entry-level jobs hardest, study finds',
                  'Young employment in AI-impacted fields down 19%.',
                  now() - interval '1 hour', :hash, 'ignored', 81,
                  'news-relevance-v1', 'requeue fixture 1',
                  false, 0.95, 'An academic study, not a capability development.',
                  'news-semantic-relevance-v1', 1, now())
          RETURNING id
        """), {"src": source_id, "hash": f"{7:064d}"})).scalar_one()
    try:
        yield item_id
    finally:
        await _cleanup()
        if parked:
            async with SessionFactory() as s, s.begin():
                await s.execute(
                    text("UPDATE news_ingest_items SET status='candidate' WHERE id = ANY(:ids)"),
                    {"ids": parked})


@pytest.mark.asyncio(loop_scope="session")
async def test_a_v1_rejection_is_invisible_to_selection(rejected_item: int) -> None:
    """Why a requeue path had to exist at all: status and verdict both exclude it."""
    async with SessionFactory() as s:
        assert rejected_item not in await select_generation_candidates(s, 50)


@pytest.mark.asyncio(loop_scope="session")
async def test_requeue_returns_a_superseded_rejection_to_the_queue(
    rejected_item: int,
) -> None:
    async with SessionFactory() as s:
        result = await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
        await s.commit()
    assert result["ok"] is True
    assert result["superseded"]["policy_version"] == "news-semantic-relevance-v1"
    assert result["superseded"]["is_ai_news"] is False
    async with SessionFactory() as s:
        assert rejected_item in await select_generation_candidates(s, 50)


@pytest.mark.asyncio(loop_scope="session")
async def test_requeue_preserves_the_attempt_count(rejected_item: int) -> None:
    """The spend already happened; erasing it would make the daily cap lie."""
    async with SessionFactory() as s:
        await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
        await s.commit()
    async with SessionFactory() as s:
        attempts = (await s.execute(
            text("SELECT generation_attempts FROM news_ingest_items WHERE id = :id"),
            {"id": rejected_item})).scalar_one()
    assert attempts == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_requeue_refuses_under_the_policy_still_in_force(rejected_item: int) -> None:
    """Guard against re-rolling the same policy and burning free-tier quota."""
    async with SessionFactory() as s:
        first = await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
        await s.commit()
    assert first["ok"] is True

    async with SessionFactory() as s, s.begin():
        await s.execute(text("""
          UPDATE news_ingest_items
          SET is_ai_news = false, ai_relevance_confidence = 0.9,
              semantic_policy_version = :policy, status = 'ignored'
          WHERE id = :id
        """), {"id": rejected_item, "policy": SEMANTIC_POLICY_VERSION})

    async with SessionFactory() as s:
        second = await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
    assert second["ok"] is False
    assert "still the policy in force" in second["reason"]


@pytest.mark.asyncio(loop_scope="session")
async def test_requeue_refuses_an_item_with_no_verdict(rejected_item: int) -> None:
    """Requeueing is only meaningful for an item a policy actually judged.

    Driven by requeueing once, which clears the verdict, then asking again — so the "no
    verdict" state is produced by the code under test rather than found in the database.
    """
    async with SessionFactory() as s:
        first = await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
        await s.commit()
    assert first["ok"] is True

    async with SessionFactory() as s:
        second = await requeue_for_reassessment(s, rejected_item, SEMANTIC_POLICY_VERSION)
    assert second["ok"] is False
    assert "nothing to requeue" in second["reason"]


@pytest.mark.asyncio(loop_scope="session")
async def test_requeue_refuses_an_unknown_item() -> None:
    async with SessionFactory() as s:
        result = await requeue_for_reassessment(s, 99_999_999, SEMANTIC_POLICY_VERSION)
    assert result["ok"] is False
    assert "No ingest item" in result["reason"]


def test_requeue_has_no_bulk_variant() -> None:
    """A bulk reset would rewrite history and spend the daily budget unasked."""
    from app.repositories import news_ingest

    names = [n for n in dir(news_ingest) if "requeue" in n.lower()]
    assert names == ["requeue_for_reassessment"]

    import inspect

    signature = inspect.signature(news_ingest.requeue_for_reassessment)
    assert "item_id" in signature.parameters
    assert not any("ids" in p or "items" in p for p in signature.parameters)
