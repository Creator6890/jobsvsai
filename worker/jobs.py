import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import text

from app.db.session import SessionFactory
from scoring import (
    ReplacementInputs,
    ScoringModel,
    calculate_exposure,
    calculate_replacement_derivation,
)
from scoring.exposure import TaskScore

# The legacy recalculation path is retained ONLY to keep the JVS 1.0.3 demo chain
# reproducible. It computes legacy arithmetic over hand-authored occupation columns and has
# nothing to do with the Phase 4B/4D/5 engine.
#
# Three things it must never do, in ascending order of how bad they would be:
#   1. run legacy arithmetic under a v2 model identity — it would silently mislabel legacy
#      numbers as engine scores the moment the active model is flipped;
#   2. write production_occupation_score_snapshots — the production store is append-only and
#      fed exclusively by promotion runs;
#   3. alter Phase 5 candidate data — every phase5_* table is append-only (migration 024).
#
# All three are enforced by the database (migration 026 triggers for 1, migration 025 and 024
# append-only triggers for 2 and 3). The check below fails fast with a legible message rather
# than waiting for a trigger to raise mid-transaction, and documents the contract at the one
# place a future change would break it.
LEGACY_COMPATIBLE_METHODOLOGY_FAMILY = "legacy-jvs-1"


class LegacyWorkerDisabled(RuntimeError):
    """Raised when the active scoring model is not legacy JVS 1.x arithmetic."""


def recalculate_occupation(occupation_id: int, reason: str) -> dict[str, object]:
    """RQ entrypoint. It runs the async database work outside the HTTP process."""
    return asyncio.run(_recalculate_occupation(occupation_id, reason))


async def _recalculate_occupation(occupation_id: int, reason: str) -> dict[str, object]:
    async with SessionFactory() as session, session.begin():
        baseline = (await session.execute(text("""
          SELECT o.id, latest.human_dependency, latest.physical_dependency,
                 latest.adoption_pressure, latest.market_resilience,
                 latest.confidence, latest.trend, latest.salary_potential,
                 latest.future_demand, latest.input_versions
          FROM occupations o
          JOIN occupation_scores latest ON latest.id = (SELECT id FROM occupation_scores WHERE occupation_id=o.id ORDER BY calculated_at DESC LIMIT 1)
          WHERE o.id=:occupation_id
        """), {"occupation_id": occupation_id})).mappings().one()
        model_row = (await session.execute(text("""
          SELECT id, version, replacement_config, methodology_family
          FROM scoring_model_versions WHERE is_active ORDER BY created_at DESC LIMIT 1
        """))).mappings().one()
        if model_row["methodology_family"] != LEGACY_COMPATIBLE_METHODOLOGY_FAMILY:
            raise LegacyWorkerDisabled(
                f"The active scoring model {model_row['version']!r} belongs to methodology "
                f"family {model_row['methodology_family']!r}. This worker computes legacy "
                "JVS 1.x arithmetic and must not stamp it with an engine model. Engine scores "
                "are produced by the Phase 5 pipeline and reach production through a promotion "
                "run, never through this path."
            )
        task_rows = (await session.execute(text("""
          SELECT task.id task_id, task.name task, task_score.exposure::float exposure,
                 occupation_task.importance::float importance,
                 coalesce(occupation_task.frequency, 100)::float frequency,
                 coalesce(capability.capability_level, 0)::float capability_level
          FROM occupation_tasks occupation_task
          JOIN tasks task ON task.id=occupation_task.task_id
          JOIN LATERAL (
            SELECT exposure, capability_id FROM task_ai_scores
            WHERE task_id=task.id ORDER BY calculated_at DESC LIMIT 1
          ) task_score ON true
          LEFT JOIN ai_capabilities capability ON capability.id=task_score.capability_id
          WHERE occupation_task.occupation_id=:occupation_id
          ORDER BY occupation_task.importance DESC, task.name
        """), {"occupation_id": occupation_id})).mappings().all()
        if not task_rows:
            raise ValueError(f"Occupation {occupation_id} has no scored tasks")

        task_scores = [TaskScore(row["exposure"], row["importance"], row["frequency"]) for row in task_rows]
        task_exposure = calculate_exposure(task_scores)
        total_weight = sum(row["importance"] * row["frequency"] for row in task_rows)
        capability_proximity = round(sum(
            row["capability_level"] * row["importance"] * row["frequency"] for row in task_rows
        ) / total_weight, 2)
        model = ScoringModel(
            version=model_row["version"],
            replacement_weights={key: float(value) for key, value in model_row["replacement_config"].items()},
        )
        derivation = calculate_replacement_derivation(ReplacementInputs(
            task_exposure=task_exposure,
            ai_capability_proximity=capability_proximity,
            human_dependency=float(baseline["human_dependency"]),
            physical_dependency=float(baseline["physical_dependency"]),
            adoption_pressure=float(baseline["adoption_pressure"]),
            market_resilience=float(baseline["market_resilience"]),
        ), model)
        task_contributions = [{
            "taskId": row["task_id"],
            "task": row["task"],
            "exposure": row["exposure"],
            "importance": row["importance"],
            "frequency": row["frequency"],
            "normalizedWeight": round(row["importance"] * row["frequency"] / total_weight, 6),
            "exposureContribution": round(row["exposure"] * row["importance"] * row["frequency"] / total_weight, 4),
        } for row in task_rows]
        score_id = (await session.execute(text("""
          INSERT INTO occupation_scores (
            occupation_id, model_version_id, ai_exposure, replacement_risk, confidence, trend,
            human_dependency, physical_dependency, adoption_pressure, market_resilience,
            salary_potential, future_demand, input_versions, task_exposure, ai_capability_proximity
          )
          VALUES (
            :occupation_id, :model_version_id, :task_exposure, :replacement, :confidence, :trend,
            :human_dependency, :physical_dependency, :adoption_pressure, :market_resilience,
            :salary_potential, :future_demand,
            CAST(:input_versions AS jsonb) || jsonb_build_object('reason', CAST(:reason AS TEXT)),
            :task_exposure, :ai_capability_proximity
          )
          RETURNING id
        """), {
            "occupation_id": occupation_id,
            "model_version_id": model_row["id"],
            "task_exposure": task_exposure,
            "replacement": derivation.total,
            "confidence": baseline["confidence"],
            "trend": baseline["trend"],
            "human_dependency": baseline["human_dependency"],
            "physical_dependency": baseline["physical_dependency"],
            "adoption_pressure": baseline["adoption_pressure"],
            "market_resilience": baseline["market_resilience"],
            "salary_potential": baseline["salary_potential"],
            "future_demand": baseline["future_demand"],
            "ai_capability_proximity": capability_proximity,
            "input_versions": json.dumps(baseline["input_versions"]),
            "reason": reason,
        })).scalar_one()
        await session.execute(text("""
          INSERT INTO score_derivations (
            score_id, occupation_id, model_version_id, calculated_total,
            factors, task_contributions, input_versions
          ) VALUES (
            :score_id, :occupation_id, :model_version_id, :total,
            CAST(:factors AS jsonb), CAST(:task_contributions AS jsonb), CAST(:input_versions AS jsonb)
          )
        """), {
            "score_id": score_id,
            "occupation_id": occupation_id,
            "model_version_id": model_row["id"],
            "total": derivation.total,
            "factors": json.dumps([asdict(factor) for factor in derivation.factors]),
            "task_contributions": json.dumps(task_contributions),
            "input_versions": json.dumps(baseline["input_versions"]),
        })
        await session.execute(text("""
          INSERT INTO score_history (occupation_id, model_version_id, ai_exposure, replacement_risk, snapshot_at, source_score_id)
          SELECT occupation_id, model_version_id, ai_exposure, replacement_risk, calculated_at, id FROM occupation_scores WHERE id=:score_id
        """), {"score_id": score_id})
        await session.execute(text("UPDATE scoring_jobs SET status='complete', completed_at=now() WHERE occupation_id=:occupation_id AND status='running'"), {"occupation_id": occupation_id})
        return {
            "occupation_id": occupation_id,
            "score_id": score_id,
            "replacement_risk": derivation.total,
            "reason": reason,
            "calculated_at": datetime.now(UTC).isoformat(),
        }


def enqueue_affected_occupations(dependency_type: str, dependency_id: int) -> int:
    return asyncio.run(_enqueue_affected(dependency_type, dependency_id))


async def _enqueue_affected(dependency_type: str, dependency_id: int) -> int:
    async with SessionFactory() as session, session.begin():
        result = await session.execute(text("""
          INSERT INTO scoring_jobs (occupation_id, reason, dependency_type, dependency_id)
          SELECT DISTINCT ot.occupation_id, 'dependency_changed', :dependency_type, :dependency_id
          FROM occupation_tasks ot
          WHERE (:dependency_type = 'task' AND ot.task_id = :dependency_id)
             OR (:dependency_type = 'capability' AND EXISTS (SELECT 1 FROM task_ai_scores tas WHERE tas.task_id=ot.task_id AND tas.capability_id=:dependency_id))
          RETURNING id
        """), {"dependency_type": dependency_type, "dependency_id": dependency_id})
        return len(result.fetchall())
