import json
import os

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="session")


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@postgres:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_phase5_namespace_freezes_878_scoring_ready_occupations() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        namespace = await connection.fetchrow(
            "SELECT * FROM phase5_candidate_namespaces WHERE namespace_version='phase5-candidate-2026q3-v1'"
        )
        assert namespace["occupation_population_count"] == 878
        assert namespace["coverage_threshold"] == 70
        assert namespace["public_activation_allowed"] is False
        assert namespace["production_score_writes_allowed"] is False
        assert namespace["archetype_scoring_enabled"] is False
        assert await connection.fetchval(
            "SELECT count(*) FROM phase5_candidate_occupations WHERE namespace_id=$1", namespace["id"]
        ) == 878
        assert await connection.fetchval(
            """SELECT count(*) FROM phase5_candidate_occupations candidate
               JOIN occupation_promotion_profiles profile
                 ON profile.source_occupation_code=candidate.occupation_code
               WHERE candidate.namespace_id=$1 AND NOT profile.scoring_eligible""", namespace["id"]
        ) == 0
    finally:
        await connection.close()


async def test_phase5_mapping_scope_reuses_dependencies_and_never_invents_missing_evidence() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        namespace_id = await connection.fetchval(
            "SELECT id FROM phase5_candidate_namespaces WHERE namespace_version='phase5-candidate-2026q3-v1'"
        )
        counts = await connection.fetchrow("""
          SELECT count(*) total,
                 count(*) FILTER (WHERE scope_decision='generated') generated,
                 count(*) FILTER (WHERE scope_decision='reused_exact_task') reused_exact,
                 count(*) FILTER (WHERE scope_decision='reused_task_hash') reused_hash,
                 count(*) FILTER (WHERE scope_decision='unmapped_insufficient_evidence') insufficient,
                 count(*) FILTER (WHERE scope_decision='unmapped_after_gate') after_gate,
                 count(*) FILTER (WHERE scope_decision='source_weight_ineligible') weight_ineligible,
                 count(*) FILTER (WHERE scope_decision IN ('unmapped_insufficient_evidence',
                   'unmapped_after_gate','source_weight_ineligible') AND ai_task_mapping_id IS NOT NULL)
                   invented_mapping_links
          FROM phase5_task_mapping_scope WHERE namespace_id=$1
        """, namespace_id)
        assert dict(counts) == {
            "total": 17843, "generated": 10253, "reused_exact": 393, "reused_hash": 169,
            "insufficient": 2264, "after_gate": 4559, "weight_ineligible": 205,
            "invented_mapping_links": 0,
        }
        run = await connection.fetchrow(
            "SELECT * FROM ai_generated_task_mapping_runs WHERE run_version='phase5-bounded-mapper-v1-2026q3'"
        )
        config = decoded(run["inference_configuration"])
        provenance = decoded(run["provenance"])
        assert run["output_task_count"] == 10253
        assert run["prohibited_input_attestation"] is True
        assert config["runtimeExternalModelCalls"] == 0
        assert config["estimatedAiTokens"] == 0
        assert provenance["scoreBlind"] is True
    finally:
        await connection.close()


async def test_phase5_proxies_scores_gates_and_replay_reconcile_exactly() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        namespace_id = await connection.fetchval(
            "SELECT id FROM phase5_candidate_namespaces WHERE namespace_version='phase5-candidate-2026q3-v1'"
        )
        proxies = await connection.fetch(
            "SELECT * FROM phase5_proxy_snapshots WHERE namespace_id=$1", namespace_id
        )
        assert len(proxies) == 878
        assert all(decoded(row["reconciliation"])["passed"] for row in proxies)
        assert all(set(decoded(row["provisional_flags"])) == {
            "regulation", "adoption-pressure", "labour-market-resilience"
        } for row in proxies)
        assert all(decoded(row["exact_inputs"])["missingDataPolicy"].endswith("never invent or impute")
                   for row in proxies)

        # Scoped to the Phase 5 namespace. Later phases (5B coverage completion) reuse the
        # same anomaly policy, so policy alone no longer identifies this run pair.
        runs = await connection.fetch("""
          SELECT run.* FROM phase5_calculation_runs run
          JOIN phase5_anomaly_policy_versions policy ON policy.id=run.anomaly_policy_version_id
          JOIN phase5_candidate_namespaces namespace ON namespace.id=run.namespace_id
          WHERE policy.policy_version='phase5-corpus-anomaly-policy-v2'
            AND namespace.namespace_version='phase5-candidate-2026q3-v1'
          ORDER BY run.id
        """)
        assert [row["run_kind"] for row in runs] == ["bounded_corpus", "deterministic_replay"]
        assert runs[-1]["replay_matches_previous"] is True
        assert all(row["attempted_occupation_count"] == 878 for row in runs)
        assert all(row["scored_occupation_count"] == 744 for row in runs)
        assert all(row["blocked_occupation_count"] == 134 for row in runs)
        assert all(row["task_assessment_count"] == 10815 for row in runs)
        assert all(row["external_ai_calls"] == 0 and row["estimated_ai_tokens"] == 0 for row in runs)
        assert all(row["production_score_writes"] == 0 and row["public_activations"] == 0 for row in runs)
        replay_id = runs[-1]["id"]
        score_counts = await connection.fetchrow("""
          SELECT count(*) scores,
                 count(*) FILTER (WHERE candidate_status='review_ready') ready,
                 count(*) FILTER (WHERE candidate_status='blocked') blocked,
                 count(*) FILTER (WHERE weighted_task_coverage<70 AND candidate_status<>'blocked') gate_violations,
                 count(*) FILTER (WHERE public_activation_eligible) public_eligible,
                 count(*) FILTER (WHERE NOT (ai_exposure BETWEEN 0 AND 100)
                   OR NOT (replacement_risk BETWEEN 0 AND 100)
                   OR NOT (confidence BETWEEN 0 AND 100)) range_violations,
                 count(*) FILTER (WHERE NOT (reconciliation->>'passed')::boolean) reconciliation_failures
          FROM phase5_occupation_scores WHERE calculation_run_id=$1
        """, replay_id)
        assert dict(score_counts) == {
            "scores": 878, "ready": 744, "blocked": 134, "gate_violations": 0,
            "public_eligible": 0, "range_violations": 0, "reconciliation_failures": 0,
        }
        assert await connection.fetchval(
            "SELECT count(*) FROM phase5_task_assessments WHERE calculation_run_id=$1 AND NOT (reconciliation->>'passed')::boolean",
            replay_id,
        ) == 0
    finally:
        await connection.close()


async def test_phase5_corpus_report_has_healthy_distributions_and_unactivated_launch_cohort() -> None:
    connection = await asyncpg.connect(database_url())
    try:
        run_id = await connection.fetchval(
            "SELECT id FROM phase5_calculation_runs WHERE run_version='phase5-bounded-corpus-replay-v2-2026q3'"
        )
        report = await connection.fetchrow(
            "SELECT * FROM phase5_corpus_reports WHERE calculation_run_id=$1", run_id
        )
        summary = decoded(report["corpus_summary"])
        distributions = decoded(report["distributions"])
        anomalies = decoded(report["anomaly_summary"])
        launch = decoded(report["recommended_launch_cohort"])
        reconciliation = decoded(report["exact_reconciliation"])
        assert summary["scoringReadyOccupationsAttempted"] == 878
        assert summary["reviewReadyOccupations"] == 744
        assert summary["coverageBlockedOccupations"] == 134
        assert distributions["aiExposure"]["standardDeviation"] >= 5
        assert distributions["replacementRisk"]["standardDeviation"] >= 5
        assert 0 <= distributions["aiExposure"]["minimum"] < distributions["aiExposure"]["maximum"] <= 100
        assert 0 <= distributions["replacementRisk"]["minimum"] < distributions["replacementRisk"]["maximum"] <= 100
        assert anomalies["bySeverity"].get("error", 0) == 0
        assert launch["recommendedCount"] == 400
        assert len(launch["occupations"]) == 400
        assert launch["activated"] is False
        assert reconciliation["deterministicReplay"] is True
        assert reconciliation["passed"] is True
    finally:
        await connection.close()


async def test_admin_phase5_exposes_filters_full_provenance_and_isolation() -> None:
    auth = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-me-too"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/phase5?candidate_status=blocked&limit=10", auth=auth)
        sensitive = await client.get("/api/v1/admin/phase5?provisional_sensitive=true&limit=5", auth=auth)
        impossible = await client.get(
            "/api/v1/admin/phase5?candidate_status=blocked&coverage_min=70&limit=5", auth=auth
        )
    assert response.status_code == sensitive.status_code == impossible.status_code == 200
    data = response.json()
    assert data["runs"][0]["replay_matches_previous"] is True
    assert data["report"]["recommended_launch_cohort"]["recommendedCount"] == 400
    assert data["total_filtered"] == 134
    assert all(row["candidate_status"] == "blocked" for row in data["occupations"])
    assert all(row["public_activation_eligible"] is False for row in data["occupations"])
    assert all(row["structural_proxy_inputs"]["phase4dProxyModel"] ==
               "phase4d-direct-structural-proxy-v2" for row in data["occupations"])
    assert all(row["reconciliation"]["passed"] for row in data["occupations"])
    assert sensitive.json()["total_filtered"] == 106
    assert impossible.json()["total_filtered"] == 0
    # `public_occupation_rows` is an ambient count, not a Phase 5 property: the session-scoped
    # `published_occupations` fixture activates pages while it is alive, so pinning it to 0
    # makes this assertion depend on test ordering. The panel must report the truth, and the
    # Phase 5 guarantee — that Phase 5 itself activated nothing — is
    # `runs_with_public_activations`, which stays pinned.
    connection = await asyncpg.connect(database_url())
    try:
        public_rows = await connection.fetchval(
            "SELECT count(*) FROM occupation_publications WHERE activation_status='public'"
        )
    finally:
        await connection.close()
    assert data["isolation"] == {
        "production_occupation_score_rows": 11,
        "production_task_score_rows": 23,
        "public_occupation_rows": public_rows,
        "runs_with_production_writes": 0,
        "runs_with_public_activations": 0,
        "archetype_layer_enabled": False,
    }
