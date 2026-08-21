import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import SessionFactory
from tests.conftest import set_activation

pytestmark = pytest.mark.asyncio(loop_scope="session")


def admin_auth() -> tuple[str, str]:
    return os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too")


async def _listed(client: AsyncClient, slug: str) -> dict:
    """Find one occupation in the paginated listing.

    The published corpus is larger than a single page, so scanning `?limit=100` finds only
    the alphabetical head. Callers want a specific occupation, not whatever fits on page one.
    """
    page_size = 500
    for offset in range(0, 5000, page_size):
        page = (await client.get(
            f"/api/v1/occupations?limit={page_size}&offset={offset}")).json()
        for item in page:
            if item["slug"] == slug:
                return item
        if len(page) < page_size:
            break
    raise AssertionError(f"{slug} is not in the public listing")


async def test_public_surfaces_agree_on_the_current_production_snapshot(
    client: AsyncClient, published_occupations
) -> None:
    """List, detail and rankings must resolve to the same snapshot.

    Before Option B these three read `occupation_scores` with `ORDER BY calculated_at DESC`
    and no tiebreak, while other endpoints added `id DESC`; two readers could therefore
    disagree. Currency now comes from one view, so this is a real invariant.
    """
    listed = await _listed(client, "graphic-designer")
    detail = (await client.get("/api/v1/occupations/graphic-designer")).json()
    ranking = (await client.get(
        "/api/v1/rankings?metric=ai_exposure&direction=desc&limit=1000")).json()
    ranked = next(item for item in ranking if item["slug"] == "graphic-designer")

    async with SessionFactory() as session:
        snapshot = (await session.execute(text("""
          SELECT score.ai_exposure::float ai_exposure, score.replacement_risk::float replacement_risk,
                 score.confidence::float confidence, score.weighted_task_coverage::float coverage
          FROM current_production_occupation_scores score
          JOIN canonical_occupation_identities identity ON identity.id = score.identity_id
          JOIN occupations occupation ON occupation.id = identity.jobs_vs_ai_occupation_id
          WHERE occupation.slug = 'graphic-designer'
        """))).mappings().one()

    assert detail["aiExposure"] == listed["aiExposure"] == round(float(ranked["ai_exposure"]))
    assert detail["replacementRisk"] == listed["replacementRisk"] == round(float(ranked["replacement_risk"]))
    assert detail["aiExposure"] == round(snapshot["ai_exposure"])
    assert detail["replacementRisk"] == round(snapshot["replacement_risk"])
    assert detail["confidence"] == pytest.approx(snapshot["confidence"])
    assert detail["weightedTaskCoverage"] == pytest.approx(snapshot["coverage"])


async def test_occupation_payload_carries_engine_provenance(
    client: AsyncClient, published_occupations
) -> None:
    """Numeric confidence, coverage, O*NET task identity and provisional-weight share."""
    detail = (await client.get("/api/v1/occupations/graphic-designer")).json()

    assert isinstance(detail["confidence"], (int, float)) and 0 <= detail["confidence"] <= 100
    assert 0 <= detail["weightedTaskCoverage"] <= 100
    # adoptionPressure (0.15) + labourMarketResilienceResistance (0.10) = 25% of the weight.
    assert detail["provisionalWeightShare"] == pytest.approx(25.0, abs=0.01)
    assert detail["tasks"], "task evidence must come from the promoted derivation"
    assert all(task["onetTaskId"] for task in detail["tasks"])
    assert all({"automationFeasibility", "augmentationPotential"} <= set(task) for task in detail["tasks"])
    assert detail["hardestToAutomateTasks"]
    # Removed on purpose: the engine produces none of these.
    assert "trend" not in detail
    assert "salaryPotential" not in detail
    assert "futureDemand" not in detail


async def test_public_surfaces_require_an_active_publication(
    client: AsyncClient, published_occupations
) -> None:
    """A production score does not make an occupation public."""
    slug = "cybersecurity-analyst"
    linking_slug = "software-developer"  # seeded 'adjacent' relationship -> cybersecurity-analyst

    assert (await _listed(client, slug))["slug"] == slug
    linked = (await client.get(f"/api/v1/occupations/{linking_slug}")).json()["relatedCareers"]
    assert any(item["slug"] == slug for item in linked), "precondition: the related-career link is visible"

    await set_activation(slug, "review_required")
    try:
        listing = (await client.get("/api/v1/occupations?limit=500")).json()
        listing += (await client.get("/api/v1/occupations?limit=500&offset=500")).json()
        ranking = (await client.get(
            "/api/v1/rankings?metric=ai_exposure&direction=desc&limit=1000")).json()
        search = (await client.get("/api/v1/occupations/search", params={"q": "cybersecurity"})).json()
        detail = await client.get(f"/api/v1/occupations/{slug}")

        assert all(item["slug"] != slug for item in listing)
        assert all(item["slug"] != slug for item in ranking)
        assert all(item["slug"] != slug for item in search)
        assert detail.status_code == 404

        related = (await client.get(f"/api/v1/occupations/{linking_slug}")).json()["relatedCareers"]
        assert all(item["slug"] != slug for item in related)

        admin = await client.get(f"/api/v1/admin/jobs/{slug}/derivation", auth=admin_auth())
        assert admin.status_code == 200, "admin review must still see unpublished occupations"
    finally:
        await set_activation(slug, "public")

    assert (await client.get(f"/api/v1/occupations/{slug}")).status_code == 200


async def test_public_surfaces_require_a_promoted_score(
    client: AsyncClient, published_occupations
) -> None:
    """Rolling the promotion run back empties every public surface, without deleting data."""
    from tests.production_fixtures import build_promotion_run, roll_back_run

    before = (await client.get("/api/v1/occupations?limit=100")).json()
    assert before, "precondition: occupations are visible while a completed run exists"

    await roll_back_run(published_occupations["run_id"], "temporary withdrawal test")
    try:
        # Some demo occupations are also in the approved launch cohort and so carry a
        # snapshot from the real promotion run. Withdrawing this fixture's run must remove
        # exactly the occupations it alone was serving — not every occupation in the
        # database, which would only be true when no other completed run exists.
        async with SessionFactory() as session:
            still_scored = set((await session.execute(text("""
              SELECT occupation.slug
              FROM current_production_occupation_scores score
              JOIN canonical_occupation_identities identity ON identity.id = score.identity_id
              JOIN occupations occupation ON occupation.id = identity.jobs_vs_ai_occupation_id
              WHERE score.identity_id = ANY(:ids)
            """), {"ids": published_occupations["identity_ids"]})).scalars().all())
        fixture_only = set(published_occupations["identities"]) - still_scored

        listing = {item["slug"] for item in (await client.get("/api/v1/occupations?limit=100")).json()}
        rankings = {item["slug"] for item in (await client.get("/api/v1/rankings")).json()}
        assert not (listing & fixture_only), "withdrawn occupations are still listed"
        assert not (rankings & fixture_only), "withdrawn occupations are still ranked"
        assert "graphic-designer" in fixture_only, (
            "precondition: graphic-designer is served only by the fixture run")
        assert (await client.get("/api/v1/occupations/graphic-designer")).status_code == 404
        async with SessionFactory() as session:
            surviving = (await session.execute(text(
                "SELECT count(*) FROM production_occupation_score_snapshots WHERE promotion_run_id=:id"
            ), {"id": published_occupations["run_id"]})).scalar_one()
        assert surviving == len(published_occupations["snapshot_ids"]), "rollback deletes nothing"
    finally:
        # A rolled-back run cannot be revived; restoring service means a new run.
        replacement = await build_promotion_run(key_suffix="restore")
        published_occupations["run_id"] = replacement["run_id"]
        published_occupations["run_key"] = replacement["run_key"]
        published_occupations["snapshot_ids"] = replacement["snapshot_ids"]

    assert (await client.get("/api/v1/occupations?limit=100")).json()


async def test_legacy_admin_derivation_still_reconciles(client: AsyncClient, published_occupations) -> None:
    """The legacy JVS 1.0.3 chain is untouched and still explains itself."""
    response = await client.get("/api/v1/admin/jobs/graphic-designer/derivation", auth=admin_auth())
    assert response.status_code == 200
    derivation = response.json()
    contribution_total = sum(float(factor["contribution"]) for factor in derivation["factors"])
    task_total = sum(float(task["exposureContribution"]) for task in derivation["taskContributions"])
    assert contribution_total == pytest.approx(float(derivation["calculatedTotal"]), abs=.011)
    assert float(derivation["calculatedTotal"]) == pytest.approx(float(derivation["replacementRisk"]), abs=.001)
    assert task_total == pytest.approx(float(derivation["taskExposure"]), abs=.011)


async def test_legacy_occupation_scores_are_untouched(published_occupations) -> None:
    """Nothing in this phase writes to the legacy chain."""
    async with SessionFactory() as session:
        counts = (await session.execute(text("""
          SELECT (SELECT count(*) FROM occupation_scores) occupation_scores,
                 (SELECT count(*) FROM task_ai_scores) task_ai_scores,
                 (SELECT count(*) FROM scoring_model_versions WHERE is_active) active_models,
                 (SELECT version FROM scoring_model_versions WHERE is_active) active_version
        """))).mappings().one()
    assert counts["occupation_scores"] >= 9
    assert counts["active_models"] == 1
    assert counts["active_version"] == "JVS 1.0.3", "the production model must not have been flipped"


async def test_only_the_approved_cohort_was_promoted(published_occupations) -> None:
    """Real promotion is limited to the one approved run, and to its approved cohort.

    Supersedes the earlier "nothing has been promoted" guard, which encoded a standing
    constraint that was lifted when the 507-occupation Phase 6 cohort was approved. The
    protection that still matters is unchanged: no promotion may appear that is neither an
    architecture fixture nor the approved run, nothing outside the approved cohort may be
    promoted, and nothing may go public without a snapshot.
    """
    approved_run_key = "phase6-promotion-2026q3-v1"
    approved_source_run = "phase5b-coverage-completion-2026q3-v1"
    approved_triage = "phase6-triage-postcoverage-2026q3-v1"

    async with SessionFactory() as session:
        unexpected_runs = (await session.execute(text("""
          SELECT run.run_key FROM production_promotion_runs run
          WHERE run.source_kind <> 'architecture_test_fixture'
            AND run.is_test_fixture IS NOT TRUE
            AND run.run_key <> :approved
        """), {"approved": approved_run_key})).scalars().all()

        promoted_from_wrong_source = (await session.execute(text("""
          SELECT count(*) FROM production_occupation_score_snapshots snapshot
          JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
          LEFT JOIN phase5_calculation_runs source ON source.id = run.source_calculation_run_id
          WHERE run.run_key = :approved AND source.run_version IS DISTINCT FROM :source_run
        """), {"approved": approved_run_key, "source_run": approved_source_run})).scalar_one()

        outside_cohort = (await session.execute(text("""
          SELECT count(*) FROM production_occupation_score_snapshots snapshot
          JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
          JOIN phase5_occupation_scores candidate ON candidate.id = snapshot.source_candidate_score_id
          JOIN phase5_candidate_occupations occupation
            ON occupation.id = candidate.candidate_occupation_id
          WHERE run.run_key = :approved
            AND occupation.occupation_code NOT IN (
              SELECT result.occupation_code FROM phase6_launch_triage_results result
              JOIN phase6_launch_triage_runs triage ON triage.id = result.triage_run_id
              WHERE triage.run_key = :triage AND result.launch_eligible)
        """), {"approved": approved_run_key, "triage": approved_triage})).scalar_one()

        legacy_model_snapshots = (await session.execute(text("""
          SELECT count(*) FROM production_occupation_score_snapshots snapshot
          JOIN scoring_model_versions model ON model.id = snapshot.scoring_model_version_id
          WHERE model.methodology_family <> 'jobsvsai-engine-v2'
        """))).scalar_one()

        activated_without_snapshot = (await session.execute(text(
            "SELECT count(*) FROM occupation_publications WHERE activation_status='public' "
            "AND identity_id NOT IN (SELECT identity_id FROM production_occupation_score_snapshots)"
        ))).scalar_one()

    assert unexpected_runs == [], f"unapproved promotion runs exist: {unexpected_runs}"
    assert promoted_from_wrong_source == 0
    assert outside_cohort == 0, "a snapshot was promoted for an occupation outside the cohort"
    assert legacy_model_snapshots == 0
    assert activated_without_snapshot == 0


async def test_search_no_match_and_partial_alias(client: AsyncClient, published_occupations) -> None:
    no_match = await client.get("/api/v1/occupations/search", params={"q": "zzzz-not-a-career"})
    alias = await client.get("/api/v1/occupations/search", params={"q": "soft eng"})
    assert no_match.status_code == 200
    assert no_match.json() == []
    assert alias.status_code == 200
    assert alias.json()[0]["slug"] == "software-developer"


async def test_career_finder_still_runs_on_the_legacy_path(
    client: AsyncClient, published_occupations
) -> None:
    """Excluded from launch navigation, but functional internally and still gated."""
    payload = {
        "currentOccupationSlug": "graphic-designer",
        "experienceYears": 4,
        "skills": ["Visual communication", "Client communication", "Creative problem solving"],
        "education": "bachelors",
        "country": "India",
        "salaryExpectation": "same_or_higher",
        "retrainingTolerance": "few_months",
    }
    response = await client.post("/api/v1/careers/recommendations", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["recommendations"]
    assert all(item["estimatedMonthsMax"] <= 6 for item in result["recommendations"])
    required_components = {
        "skillFit", "aiResilience", "futureDemand", "locationDemand",
        "salaryFit", "retrainingFit", "educationReadiness", "experienceReadiness",
    }
    assert required_components <= set(result["recommendations"][0]["scoreComponents"])


async def test_admin_ai_enrichment_inspector_is_draft_and_score_neutral(client: AsyncClient, published_occupations) -> None:
    response = await client.get("/api/v1/admin/ai-enrichment", auth=admin_auth())
    assert response.status_code == 200
    data = response.json()
    assert data["taxonomies"][0]["version"] == "jvs-ai-cap-v1"
    assert data["taxonomies"][0]["status"] == "draft"
    assert len(data["capabilities"]) == 15
    assert len(data["mapping_sets"]) == 3
    assert all(item["is_test_fixture"] for item in data["mapping_sets"])
    assert all(float(item["weight_total"]) == pytest.approx(1) for item in data["mapping_sets"])
    assert len(data["constraints"]) == 10
    assert data["snapshots"] == []
    assert data["assessments"] == []
    assert data["validation"]["benchmark_scores"] == 0
    assert data["validation"]["task_assessments"] == 0
    assert data["rubrics"][0]["version"] == "jvs-task-capability-rubric-v1"
    assert data["rubrics"][0]["status"] == "review"
    assert len(data["capability_anchors"]) == 15
    assert all(len(item["anchors"]) == 5 for item in data["capability_anchors"])
    assert len(data["constraint_anchors"]) == 10
    assert len(data["confidence_states"]) == 5
    architecture_gold = next(item for item in data["gold_datasets"] if item["dataset_version"] == "gold-v1-representative-test")
    assert architecture_gold["items"] == 4
    assert len(data["gold_comparisons"]) == 3
    assert all(float(item["report"]["summary"]["meanAbsoluteWeightDeviation"]) == 0 for item in data["gold_comparisons"])
    benchmark = next(item for item in data["mapper_benchmarks"] if item["dataset_version"] == "gold-v1-175-pending-human-review")
    assert benchmark["tasks"] == 175 and benchmark["occupations"] == 28
    assert benchmark["human_reviewed_tasks"] == 0
    assert data["candidate_runs"][0]["output_task_count"] == 175
    assert data["candidate_runs"][0]["verification_status"] == "passed"
    assert data["candidate_runs"][0]["evaluation_status"] == "ineligible"
    assert data["acceptance_gates"][0]["minimum_human_reviewed_tasks"] == 150
    assert data["mvp_evidence_policies"][0]["policy_version"] == "mvp-evidence-policy-v1"
    assert data["mvp_evidence_policies"][0]["human_gold_required"] is False
    # +2,347 since Phase 5B coverage completion; the point of this test is that the
    # inspector stays draft and score-neutral, which the assertions around this one check.
    assert data["mvp_evidence_policies"][0]["scoring_eligible_mappings"] == 13007
    assert data["frontier_indexes"][0]["index_version"] == "frontier-ai-index-v1"
    assert data["frontier_indexes"][0]["capability_values"] == 15
    assert data["frontier_indexes"][0]["commercially_deployable_values"] == 15
    assert data["frontier_indexes"][0]["technical_frontier_values"] == 0
    assert len(data["frontier_tracks"]) == 2
    assert len(data["frontier_entries"]) == 15
    assert all(item["assessment_status"] == "provisional" for item in data["frontier_entries"])
    assert all(item["evidence_records"] for item in data["frontier_entries"])
