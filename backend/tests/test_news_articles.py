"""AI News: publication guard, public isolation, admin workflow and override auditing.

Every article these tests create is cleaned up. Unlike the occupation store, the news
tables are ordinary mutable rows with no append-only trigger, so a fixture that leaks
articles would change what /news renders for the next run.

These tests also assert the architectural separation: exercising the whole news workflow
must leave occupation scoring, publication state and the active model untouched.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import SessionFactory

pytestmark = pytest.mark.asyncio(loop_scope="session")

FACTORS = {
    "capabilityAdvancement": 80,
    "commercialDeployability": 70,
    "breadthOfAffectedWork": 60,
    "adoptionSpeed": 50,
    "humanWorkReductionPotential": 40,
}
CONFIDENT = FACTORS | {"impactConfidence": 0.91, "impactReasoning": "Broad deployment surface."}
UNCERTAIN = FACTORS | {"impactConfidence": 0.55, "impactReasoning": "Thin sourcing."}

DRAFT = {
    "headline": "Pytest fixture: agent ships for expense workflows",
    "whatHappened": "A vendor released an agent aimed at expense reporting.",
    "whyItMattersForJobs": "Routine finance administration is the directly exposed work.",
    "tags": ["agents", "finance"],
    "jobAreas": ["Finance", "Administration"],
}
SOURCE = {
    "sourceName": "Pytest Wire",
    "siteUrl": "https://pytest.example.com",
    "externalUrl": "https://pytest.example.com/agents-expenses?utm_source=rss",
    "originalTitle": "Vendor ships expense agent",
    "isPrimary": True,
}


def admin_auth() -> tuple[str, str]:
    return os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too")


async def _delete_article(article_id: int) -> None:
    """Remove an article and anything left orphaned by its removal.

    Order matters: news_article_sources references news_ingest_items, so the article goes
    first (cascading the link rows away) and only then can an ingest item be removed. The
    ingest row is shared — attach_manual_source upserts on canonical_url — so it is deleted
    only once no other article still points at it.
    """
    async with SessionFactory() as session, session.begin():
        await session.execute(text("DELETE FROM news_articles WHERE id = :id"), {"id": article_id})
        await session.execute(text("""
          DELETE FROM news_ingest_items item
          WHERE item.source_id IN (SELECT id FROM news_sources WHERE name = :name)
            AND NOT EXISTS (
              SELECT 1 FROM news_article_sources link WHERE link.ingest_item_id = item.id)
        """), {"name": SOURCE["sourceName"]})
        await session.execute(text("""
          DELETE FROM news_sources source
          WHERE source.name = :name
            AND NOT EXISTS (
              SELECT 1 FROM news_ingest_items i WHERE i.source_id = source.id)
        """), {"name": SOURCE["sourceName"]})


@pytest_asyncio.fixture(loop_scope="session")
async def article(client: AsyncClient):
    """A draft with a source attached. Torn down whatever the test does to it."""
    created = (await client.post("/api/v1/admin/news", json=DRAFT, auth=admin_auth())).json()
    await client.post(f"/api/v1/admin/news/{created['id']}/source", json=SOURCE, auth=admin_auth())
    try:
        yield created
    finally:
        await _delete_article(created["id"])


# ------------------------------------------------------------------- admin create / edit


async def test_admin_can_create_a_draft_without_any_generation_record(client: AsyncClient) -> None:
    response = await client.post("/api/v1/admin/news", json=DRAFT, auth=admin_auth())
    assert response.status_code == 201
    body = response.json()
    try:
        assert body["status"] == "draft"
        assert body["slug"].startswith("pytest-fixture-agent-ships")
        assert body["generationProvider"] is None, "a hand-written brief has no provider"
        assert sorted(body["tags"]) == ["agents", "finance"]
        assert sorted(body["jobAreas"]) == ["Administration", "Finance"]
        assert body["impactLevel"] is None, "impact is set deliberately, never inferred"
    finally:
        await _delete_article(body["id"])


async def test_admin_can_update_a_draft(client: AsyncClient, article) -> None:
    updated = DRAFT | {"headline": "Pytest fixture: revised headline", "tags": ["revised"]}
    response = await client.post(
        f"/api/v1/admin/news/{article['id']}", json=updated, auth=admin_auth()
    )
    assert response.status_code == 200
    assert response.json()["headline"] == "Pytest fixture: revised headline"
    assert response.json()["tags"] == ["revised"]


async def test_slug_collisions_get_a_suffix_rather_than_failing(client: AsyncClient, article) -> None:
    duplicate = (await client.post("/api/v1/admin/news", json=DRAFT, auth=admin_auth())).json()
    try:
        # Both derive from the same headline, so both share the base slug; the second gets a
        # numeric suffix. Comparing against the base rather than against the first article's
        # slug keeps this true when an earlier run already claimed the unsuffixed form.
        base = "pytest-fixture-agent-ships-for-expense-workflows"
        assert duplicate["slug"] != article["slug"]
        assert article["slug"].startswith(base) and duplicate["slug"].startswith(base)
    finally:
        await _delete_article(duplicate["id"])


async def test_admin_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/news")).status_code == 401
    assert (await client.post("/api/v1/admin/news", json=DRAFT)).status_code == 401


# ------------------------------------------------------------------------------- impact


async def test_impact_is_computed_from_factors_not_supplied(client: AsyncClient, article) -> None:
    response = await client.post(
        f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["impactScore"] == 65.0
    assert body["impactLevel"] == "medium"
    assert body["impactPolicyVersion"] == "news-impact-v1"
    assert body["automatedImpactScore"] == 65.0
    assert body["automatedImpactLevel"] == "medium"
    assert body["impactAssessedBy"].startswith("admin:")
    assert body["status"] == "draft", "confident assessment leaves the article publishable"


async def test_low_confidence_forces_review_required(client: AsyncClient, article) -> None:
    response = await client.post(
        f"/api/v1/admin/news/{article['id']}/impact", json=UNCERTAIN, auth=admin_auth()
    )
    assert response.json()["status"] == "review_required"


async def test_impact_rejects_out_of_range_factors(client: AsyncClient, article) -> None:
    bad = CONFIDENT | {"capabilityAdvancement": 140}
    response = await client.post(
        f"/api/v1/admin/news/{article['id']}/impact", json=bad, auth=admin_auth()
    )
    assert response.status_code == 422


async def test_override_preserves_the_automated_assessment(client: AsyncClient, article) -> None:
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    response = await client.post(
        f"/api/v1/admin/news/{article['id']}/impact/override",
        json={"impactLevel": "high", "reason": "Editor judged the deployment surface wider."},
        auth=admin_auth(),
    )
    body = response.json()
    assert body["impactLevel"] == "high", "editorial value wins"
    assert body["automatedImpactLevel"] == "medium", "automated level is preserved"
    assert body["automatedImpactScore"] == 65.0, "automated score is preserved"
    assert body["impactScore"] == 65.0, "the computed score is not rewritten by an override"
    assert body["impactOverriddenAt"] is not None
    assert body["impactOverriddenBy"].startswith("admin:")
    assert body["impactOverrideReason"].startswith("Editor judged")


# -------------------------------------------------------------------- publication guard


async def test_publication_requires_impact(client: AsyncClient, article) -> None:
    response = await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    assert response.status_code == 422
    assert "Impact level is required" in response.json()["detail"]


@pytest.mark.parametrize(
    ("column", "blocker"),
    [
        ("headline", "Headline is required"),
        ("what_happened", "What happened is required"),
        ("why_it_matters_for_jobs", "Why it matters for jobs is required"),
    ],
)
async def test_publication_requires_each_content_field(
    client: AsyncClient, article, column: str, blocker: str
) -> None:
    """The guard checks the three prose fields independently.

    The API schema enforces min_length=1, so a draft cannot be created empty through it.
    That is the right behaviour but it means the guard's own content checks would never be
    exercised from the outside. Blanking the column directly is how this reaches them, and
    it is also the realistic failure: a bad backfill or a future generation path writing
    whitespace, not a request that got past validation.
    """
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    async with SessionFactory() as session, session.begin():
        await session.execute(
            text(f"UPDATE news_articles SET {column} = '   ' WHERE id = :id"),
            {"id": article["id"]},
        )

    check = (await client.get(
        f"/api/v1/admin/news/{article['id']}/publication-check", auth=admin_auth()
    )).json()
    assert check["publishable"] is False
    assert blocker in check["blockers"]

    response = await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    assert response.status_code == 422
    assert blocker in response.json()["detail"]


async def test_rejecting_an_article_moves_it_out_of_the_queue(client: AsyncClient, article) -> None:
    response = await client.post(f"/api/v1/admin/news/{article['id']}/reject", auth=admin_auth())
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    # A rejected article cannot be published without being reopened first.
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    refused = await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    assert refused.status_code == 422
    assert "Rejected articles cannot be published" in refused.json()["detail"]


async def test_publish_refusal_leaves_the_article_unchanged(client: AsyncClient, article) -> None:
    """A refused publish must not half-apply: no status change, no published_at."""
    before = (await client.get(f"/api/v1/admin/news/{article['id']}", auth=admin_auth())).json()
    assert (await client.post(
        f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth()
    )).status_code == 422
    after = (await client.get(f"/api/v1/admin/news/{article['id']}", auth=admin_auth())).json()
    assert after["status"] == before["status"]
    assert after["publishedAt"] is None


async def test_publication_requires_a_source(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/admin/news", json=DRAFT, auth=admin_auth())).json()
    try:
        await client.post(f"/api/v1/admin/news/{created['id']}/impact", json=CONFIDENT, auth=admin_auth())
        response = await client.post(f"/api/v1/admin/news/{created['id']}/publish", auth=admin_auth())
        assert response.status_code == 422
        assert "At least one source is required" in response.json()["detail"]
    finally:
        await _delete_article(created["id"])


async def test_publication_check_reports_every_blocker_at_once(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/admin/news", json=DRAFT, auth=admin_auth())).json()
    try:
        body = (await client.get(
            f"/api/v1/admin/news/{created['id']}/publication-check", auth=admin_auth()
        )).json()
        assert body["publishable"] is False
        assert "At least one source is required" in body["blockers"]
        assert "Impact level is required" in body["blockers"]
    finally:
        await _delete_article(created["id"])


async def test_publish_succeeds_once_every_requirement_is_met(client: AsyncClient, article) -> None:
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    check = (await client.get(
        f"/api/v1/admin/news/{article['id']}/publication-check", auth=admin_auth()
    )).json()
    assert check["publishable"] is True and check["blockers"] == []

    response = await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["publishedAt"] is not None


# ------------------------------------------------------------------ public API isolation


@pytest.mark.parametrize("status_name", ["draft", "review_required", "rejected"])
async def test_unpublished_articles_never_reach_the_public_api(
    client: AsyncClient, article, status_name: str
) -> None:
    """Draft, review_required and rejected are all indistinguishable from missing."""
    if status_name == "review_required":
        await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=UNCERTAIN, auth=admin_auth())
    elif status_name == "rejected":
        await client.post(f"/api/v1/admin/news/{article['id']}/reject", auth=admin_auth())

    assert (await client.get(f"/api/v1/news/{article['slug']}")).status_code == 404
    listed = (await client.get("/api/v1/news?limit=100")).json()
    assert article["slug"] not in [item["slug"] for item in listed]
    sitemap = (await client.get("/api/v1/news/sitemap")).json()
    assert article["slug"] not in [item["slug"] for item in sitemap]


async def test_published_article_is_public_and_withholds_the_internal_score(
    client: AsyncClient, article
) -> None:
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())

    detail = (await client.get(f"/api/v1/news/{article['slug']}")).json()
    assert detail["headline"] == DRAFT["headline"]
    assert detail["whyItMattersForJobs"] == DRAFT["whyItMattersForJobs"]
    assert detail["impactLevel"] == "medium"
    # V1: the numeric score is internal. Its absence from the public contract is the point.
    assert "impactScore" not in detail
    assert "impactConfidence" not in detail
    assert "impactReasoning" not in detail

    assert detail["primarySource"]["sourceUrl"].startswith("https://pytest.example.com")
    assert detail["primarySource"]["originalTitle"] == SOURCE["originalTitle"]
    assert sorted(detail["jobAreas"]) == ["Administration", "Finance"]


async def test_public_list_filters_by_impact_level(client: AsyncClient, article) -> None:
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())

    medium = (await client.get("/api/v1/news?impact=medium&limit=100")).json()
    assert article["slug"] in [item["slug"] for item in medium]
    high = (await client.get("/api/v1/news?impact=high&limit=100")).json()
    assert article["slug"] not in [item["slug"] for item in high]
    assert (await client.get("/api/v1/news?impact=enormous")).status_code == 422


async def test_sitemap_contains_published_and_excludes_unpublished(
    client: AsyncClient, article
) -> None:
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    assert article["slug"] in [i["slug"] for i in (await client.get("/api/v1/news/sitemap")).json()]

    await client.post(f"/api/v1/admin/news/{article['id']}/unpublish", auth=admin_auth())
    assert article["slug"] not in [i["slug"] for i in (await client.get("/api/v1/news/sitemap")).json()]


# ------------------------------------------------------------ separation from scoring


async def test_the_news_workflow_never_touches_occupation_scoring(
    client: AsyncClient, article
) -> None:
    """The architectural rule, asserted rather than assumed.

    Runs a full publish cycle and checks that occupation scoring, publication state and the
    active model are all exactly where they started.
    """
    async def snapshot() -> dict:
        async with SessionFactory() as session:
            return dict((await session.execute(text("""
              SELECT (SELECT count(*) FROM occupation_scores) legacy_scores,
                     (SELECT count(*) FROM production_occupation_score_snapshots) snapshots,
                     (SELECT count(*) FROM occupation_publications
                        WHERE activation_status='public') public_occupations,
                     (SELECT count(*) FROM production_promotion_runs) promotion_runs,
                     (SELECT version FROM scoring_model_versions WHERE is_active) active_model
            """))).mappings().one())

    before = await snapshot()
    await client.post(f"/api/v1/admin/news/{article['id']}/impact", json=CONFIDENT, auth=admin_auth())
    await client.post(f"/api/v1/admin/news/{article['id']}/publish", auth=admin_auth())
    await client.post(
        f"/api/v1/admin/news/{article['id']}/impact/override",
        json={"impactLevel": "high"}, auth=admin_auth(),
    )
    assert await snapshot() == before


async def test_job_areas_are_editorial_text_not_occupation_links() -> None:
    """The schema must not grow a foreign key from news into the occupation graph."""
    async with SessionFactory() as session:
        references = (await session.execute(text("""
          SELECT count(*) FROM information_schema.table_constraints tc
          JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
          WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name LIKE 'news_%'
            AND ccu.table_name IN ('occupations', 'canonical_occupation_identities',
                                   'occupation_publications',
                                   'production_occupation_score_snapshots',
                                   'scoring_model_versions')
        """))).scalar_one()
    assert references == 0, "news tables must not reference occupation or scoring tables"
