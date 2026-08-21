"""Guarantees of the Option B production score store.

These tests exercise the store directly rather than through the API: immutability,
deterministic currency, rollback, and publication/snapshot consistency. The API-level
behaviour lives in test_integration.py.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionFactory
from tests.production_fixtures import (
    FACTOR_WEIGHTS,
    build_promotion_run,
    roll_back_run,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def extra_run():
    """A second, independent completed run used by the currency tests."""
    run = await build_promotion_run(key_suffix="currency")
    yield run
    await roll_back_run(run["run_id"], "test teardown")


async def test_snapshots_reject_update_and_delete(published_occupations) -> None:
    snapshot_id = published_occupations["snapshot_ids"][0]
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            async with session.begin():
                await session.execute(
                    text("UPDATE production_occupation_score_snapshots SET ai_exposure=1 WHERE id=:id"),
                    {"id": snapshot_id},
                )
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            async with session.begin():
                await session.execute(
                    text("DELETE FROM production_occupation_score_snapshots WHERE id=:id"),
                    {"id": snapshot_id},
                )


async def test_derivation_rows_reject_update_and_delete(published_occupations) -> None:
    snapshot_id = published_occupations["snapshot_ids"][0]
    for table, mutation in [
        ("production_score_factor_contributions", "UPDATE {t} SET weight=0 WHERE snapshot_id=:id"),
        ("production_score_factor_contributions", "DELETE FROM {t} WHERE snapshot_id=:id"),
        ("production_score_task_contributions", "UPDATE {t} SET task_ai_exposure=0 WHERE snapshot_id=:id"),
        ("production_score_task_contributions", "DELETE FROM {t} WHERE snapshot_id=:id"),
    ]:
        async with SessionFactory() as session:
            with pytest.raises(DBAPIError, match="append-only"):
                async with session.begin():
                    await session.execute(text(mutation.format(t=table)), {"id": snapshot_id})


async def test_promotion_run_definition_is_frozen_but_status_may_move(published_occupations) -> None:
    run_id = published_occupations["run_id"]
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            async with session.begin():
                await session.execute(
                    text("UPDATE production_promotion_runs SET input_hash=:h WHERE id=:id"),
                    {"h": "f" * 64, "id": run_id},
                )
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            async with session.begin():
                await session.execute(
                    text("DELETE FROM production_promotion_runs WHERE id=:id"), {"id": run_id}
                )
    # Status bookkeeping is the one thing that may change, and it is what rollback uses.
    async with SessionFactory() as session, session.begin():
        await session.execute(
            text("UPDATE production_promotion_runs SET occupation_count=occupation_count WHERE id=:id"),
            {"id": run_id},
        )


async def test_publishable_requires_the_validated_gates(published_occupations) -> None:
    """A snapshot cannot claim publishability while a gate is failing."""
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="violates check constraint"):
            async with session.begin():
                await session.execute(text("""
                  INSERT INTO production_occupation_score_snapshots (
                    promotion_run_id,identity_id,scoring_model_version_id,ai_exposure,replacement_risk,
                    confidence,weighted_task_coverage,source_task_count,eligible_task_count,
                    excluded_task_count,weighting_eligible_task_count,coverage_gate_status,
                    confidence_gate_status,scoring_eligibility,publishable,frontier_index_version,
                    frontier_track,structural_proxy_model_version,base_proxy_model_version,
                    occupation_formula_version,task_formula_versions,capability_taxonomy_version,
                    mapping_rubric_version,evidence_policy_version,calculated_at,exact_inputs,
                    provisional_sensitivity,reconciliation,input_hash,source_id,created_by)
                  SELECT run.id, snapshot.identity_id, run.scoring_model_version_id, 50, 50,
                         55, 60, 1, 1, 0, 1, 'below_threshold', 'passed', 'blocked', true,
                         'x','y','z','w','v','{}','a','b','c', now(), '{}', '{}', '{}',
                         :hash, run.source_id, 'test'
                  FROM production_promotion_runs run
                  JOIN production_occupation_score_snapshots snapshot ON snapshot.id = :snapshot_id
                  WHERE run.id = :run_id
                """), {"hash": "e" * 64, "snapshot_id": published_occupations["snapshot_ids"][0],
                       "run_id": published_occupations["run_id"]})


async def test_currency_is_deterministic_and_follows_the_newest_completed_run(
    published_occupations, extra_run
) -> None:
    """Two completed runs: the view must resolve every identity to the newer one, once.

    Scoped to this fixture's identities. The real approved promotion also serves identities
    of its own, and its presence is not what this test is about.
    """
    async with SessionFactory() as session:
        all_rows = (await session.execute(text("""
          SELECT current_score.identity_id
          FROM current_production_occupation_scores current_score
        """))).scalars().all()
        rows = (await session.execute(text("""
          SELECT current_score.identity_id, current_score.id AS snapshot_id, current_score.run_key
          FROM current_production_occupation_scores current_score
          WHERE current_score.identity_id = ANY(:ids)
          ORDER BY current_score.identity_id
        """), {"ids": published_occupations["identity_ids"]})).mappings().all()

    assert len(all_rows) == len(set(all_rows)), "the view must yield one row per identity"
    identity_ids = [row["identity_id"] for row in rows]
    assert len(identity_ids) == len(set(identity_ids))
    assert {row["run_key"] for row in rows} == {extra_run["run_key"]}, (
        "currency must come from the newest completed run"
    )


async def test_rollback_restores_the_previous_run_without_touching_snapshots(
    published_occupations, extra_run
) -> None:
    async with SessionFactory() as session:
        before = (await session.execute(
            text("SELECT count(*) FROM production_occupation_score_snapshots")
        )).scalar_one()

    await roll_back_run(extra_run["run_id"], "test rollback")

    async with SessionFactory() as session:
        rows = (await session.execute(text(
            "SELECT DISTINCT run_key FROM current_production_occupation_scores "
            "WHERE identity_id = ANY(:ids)"
        ), {"ids": published_occupations["identity_ids"]})).scalars().all()
        after = (await session.execute(
            text("SELECT count(*) FROM production_occupation_score_snapshots")
        )).scalar_one()
        withdrawn = (await session.execute(text(
            "SELECT status FROM production_promotion_runs WHERE id=:id"
        ), {"id": extra_run["run_id"]})).scalar_one()

    assert rows == [published_occupations["run_key"]], "currency falls back to the earlier run"
    assert after == before, "rollback must not delete or rewrite any snapshot"
    assert withdrawn == "rolled_back"

    # Re-completing is not possible: settled runs cannot return to in_progress, and the
    # rollback is recorded permanently. A correction is a new run.
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="cannot return to in_progress"):
            async with session.begin():
                await session.execute(text(
                    "UPDATE production_promotion_runs SET status='in_progress' WHERE id=:id"
                ), {"id": extra_run["run_id"]})


async def test_factor_contributions_reconcile_to_replacement_risk(published_occupations) -> None:
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT snapshot.id, snapshot.replacement_risk::float AS replacement_risk,
                 sum(factor.weighted_contribution)::float AS contribution_total,
                 sum(factor.weight)::float AS weight_total,
                 count(*) AS factor_count
          FROM production_occupation_score_snapshots snapshot
          JOIN production_score_factor_contributions factor ON factor.snapshot_id = snapshot.id
          WHERE snapshot.promotion_run_id = :run_id
          GROUP BY snapshot.id, snapshot.replacement_risk
        """), {"run_id": published_occupations["run_id"]})).mappings().all()

    assert rows
    for row in rows:
        assert row["factor_count"] == len(FACTOR_WEIGHTS)
        assert row["weight_total"] == pytest.approx(1.0, abs=1e-6)
        assert row["contribution_total"] == pytest.approx(row["replacement_risk"], abs=0.01)


async def test_task_contributions_reconcile_to_ai_exposure(published_occupations) -> None:
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT snapshot.id, snapshot.ai_exposure::float AS ai_exposure,
                 sum(contribution.exposure_contribution)::float AS exposure_total,
                 sum(contribution.normalized_covered_weight)::float AS weight_total
          FROM production_occupation_score_snapshots snapshot
          JOIN production_score_task_contributions contribution ON contribution.snapshot_id = snapshot.id
          WHERE snapshot.promotion_run_id = :run_id
          GROUP BY snapshot.id, snapshot.ai_exposure
        """), {"run_id": published_occupations["run_id"]})).mappings().all()

    assert rows
    for row in rows:
        assert row["weight_total"] == pytest.approx(1.0, abs=1e-4)
        assert row["exposure_total"] == pytest.approx(row["ai_exposure"], abs=0.01)


async def test_provisional_proxy_provenance_survives_promotion(published_occupations) -> None:
    """The provisional adoption/labour models must stay identifiable and attributable."""
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT factor_key, is_provisional_proxy, proxy_model_version
          FROM production_score_factor_contributions
          WHERE snapshot_id = :id ORDER BY display_order
        """), {"id": published_occupations["snapshot_ids"][0]})).mappings().all()

    provisional = {row["factor_key"] for row in rows if row["is_provisional_proxy"]}
    assert provisional == {"adoptionPressure", "labourMarketResilienceResistance"}
    assert all(row["proxy_model_version"] for row in rows if row["is_provisional_proxy"])
    assert all(row["proxy_model_version"] is None for row in rows if not row["is_provisional_proxy"])


async def test_publication_snapshot_consistency_flags_withdrawn_approvals(
    published_occupations, extra_run
) -> None:
    """Approving a page against a run that is later rolled back must be reported."""
    identity_id = published_occupations["identity_ids"][0]
    approved = next(
        snapshot_id for identity, snapshot_id in extra_run["by_identity"].items()
        if identity == identity_id
    )
    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          UPDATE occupation_publications SET approved_score_snapshot_id=:snapshot
          WHERE identity_id=:identity AND locale='en' AND source_geography='US'
        """), {"snapshot": approved, "identity": identity_id})

    async with SessionFactory() as session:
        state = (await session.execute(text("""
          SELECT consistency_state FROM publication_snapshot_consistency
          WHERE identity_id=:id AND locale='en' AND source_geography='US'
        """), {"id": identity_id})).scalar_one()
    assert state == "consistent"

    await roll_back_run(extra_run["run_id"], "consistency test")

    async with SessionFactory() as session:
        state = (await session.execute(text("""
          SELECT consistency_state FROM publication_snapshot_consistency
          WHERE identity_id=:id AND locale='en' AND source_geography='US'
        """), {"id": identity_id})).scalar_one()
    assert state == "approved_snapshot_withdrawn"

    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          UPDATE occupation_publications SET approved_score_snapshot_id=NULL
          WHERE identity_id=:id AND locale='en' AND source_geography='US'
        """), {"id": identity_id})


async def test_v2_model_is_registered_but_not_active(published_occupations) -> None:
    """Migration 026 registers the engine model without flipping production."""
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT version, is_active, methodology_family, replacement_config
          FROM scoring_model_versions ORDER BY id
        """))).mappings().all()

    by_version = {row["version"]: row for row in rows}
    assert by_version["JVS 1.0.3"]["is_active"] is True
    assert by_version["JVS 1.0.3"]["methodology_family"] == "legacy-jvs-1"

    engine = by_version["JVS 2.0.0-phase4b"]
    assert engine["is_active"] is False
    assert engine["methodology_family"] == "jobsvsai-engine-v2"
    # Exactly the weights from phase4b-occupation-score-v2-calibration (migration 019).
    assert engine["replacement_config"] == {
        "taskAutomationExposure": 0.35,
        "aiCapabilityProximity": 0.10,
        "humanDependencyResistance": 0.15,
        "physicalDependencyResistance": 0.15,
        "adoptionPressure": 0.15,
        "labourMarketResilienceResistance": 0.10,
    }
    assert sum(engine["replacement_config"].values()) == pytest.approx(1.0)


async def test_legacy_arithmetic_cannot_be_stamped_with_the_engine_model(published_occupations) -> None:
    """The guard that matters if the active model is ever flipped."""
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="cannot be written under model family"):
            async with session.begin():
                await session.execute(text("""
                  INSERT INTO occupation_scores (
                    occupation_id, model_version_id, ai_exposure, replacement_risk, confidence,
                    trend, human_dependency, physical_dependency, adoption_pressure,
                    market_resilience, salary_potential, future_demand, task_exposure,
                    ai_capability_proximity)
                  SELECT occupation.id, model.id, 50,50,'High','Stable',50,50,50,50,50,50,50,50
                  FROM occupations occupation
                  CROSS JOIN scoring_model_versions model
                  WHERE occupation.slug='graphic-designer'
                    AND model.methodology_family='jobsvsai-engine-v2'
                """))


async def test_production_store_rejects_the_legacy_model(published_occupations) -> None:
    """The mirror guard: engine tables cannot reference legacy arithmetic."""
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="cannot reference model family"):
            async with session.begin():
                await session.execute(text("""
                  INSERT INTO production_promotion_runs (
                    run_key, source_kind, scoring_model_version_id, promotion_policy_version,
                    status, is_test_fixture, input_version_bundle, selection_policy,
                    input_hash, source_id, created_by)
                  SELECT 'legacy-family-probe','architecture_test_fixture', model.id, 'probe',
                         'in_progress', true, '{}'::jsonb, '{}'::jsonb, :hash, source.id, 'test'
                  FROM scoring_model_versions model
                  CROSS JOIN (SELECT id FROM data_sources ORDER BY id LIMIT 1) source
                  WHERE model.methodology_family='legacy-jvs-1'
                """), {"hash": "9" * 64})


async def test_phase5_candidate_data_is_immutable(published_occupations) -> None:
    """The legacy worker — or anything else — cannot alter Phase 5 candidate evidence."""
    async with SessionFactory() as session:
        has_rows = (await session.execute(
            text("SELECT count(*) FROM phase5_calculation_runs")
        )).scalar_one()

    if not has_rows:
        # No corpus in this database; assert the guard exists rather than skipping silently.
        async with SessionFactory() as session:
            triggers = (await session.execute(text("""
              SELECT count(*) FROM pg_trigger
              WHERE tgrelid IN ('phase5_occupation_scores'::regclass,
                                'phase5_calculation_runs'::regclass,
                                'phase5_candidate_occupations'::regclass)
                AND NOT tgisinternal
            """))).scalar_one()
        assert triggers >= 3, "every phase5 table must carry an append-only trigger"
        return

    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            async with session.begin():
                await session.execute(text("UPDATE phase5_calculation_runs SET run_kind='deterministic_replay'"))
