"""Test fixtures that build a production score store the way a promotion would.

The real promotion transaction will read persisted Phase 5 candidate rows. A fresh test
database has none, so these fixtures derive equivalent values from the legacy demo rows and
mark the resulting run `architecture_test_fixture` — the same convention migration 008 uses
for its seeded mapping sets. Nothing here promotes real candidate data.

The arithmetic mirrors `phase4b-occupation-score-v2-calibration` so that the reconciliation
assertions are meaningful rather than tautological: replacement risk is the weighted sum of
the six factor rows, and AI Exposure is the covered-weight-normalised sum of the task rows.
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import text

from app.db.session import SessionFactory

# phase4b-occupation-score-v2-calibration, migration 019.
FACTOR_WEIGHTS: dict[str, float] = {
    "taskAutomationExposure": 0.35,
    "aiCapabilityProximity": 0.10,
    "humanDependencyResistance": 0.15,
    "physicalDependencyResistance": 0.15,
    "adoptionPressure": 0.15,
    "labourMarketResilienceResistance": 0.10,
}
FACTOR_LABELS = {
    "taskAutomationExposure": "Task automation exposure",
    "aiCapabilityProximity": "AI capability proximity",
    "humanDependencyResistance": "Human dependency resistance",
    "physicalDependencyResistance": "Physical dependency resistance",
    "adoptionPressure": "Adoption pressure",
    "labourMarketResilienceResistance": "Labour-market resilience resistance",
}
PROVISIONAL_FACTORS = {"adoptionPressure", "labourMarketResilienceResistance"}
PROVISIONAL_MODEL = "phase4b-occupation-proxy-v1"
INVERSE_FACTORS = {
    "humanDependencyResistance",
    "physicalDependencyResistance",
    "labourMarketResilienceResistance",
}

VERSION_BUNDLE = {
    "frontierIndexVersion": "frontier-ai-index-v1",
    "frontierTrack": "commercially_deployable",
    "structuralProxyModelVersion": "phase4d-direct-structural-proxy-v2",
    "baseProxyModelVersion": "phase4b-occupation-proxy-v1",
    "occupationFormulaVersion": "phase4b-occupation-score-v2-calibration",
    "capabilityTaxonomyVersion": "jvs-ai-cap-v1",
    "mappingRubricVersion": "jvs-task-capability-rubric-v1",
    "evidencePolicyVersion": "mvp-evidence-policy-v1",
    "taskFormulaVersions": {
        "capabilityFit": "task-capability-fit-v2-calibration",
        "automationFeasibility": "automation-feasibility-v2-calibration",
        "augmentationPotential": "augmentation-potential-v2-calibration",
    },
}


def _hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


async def ensure_identities() -> dict[str, int]:
    """Give every scored demo occupation a canonical identity. Returns slug -> identity id."""
    async with SessionFactory() as session, session.begin():
        occupations = (await session.execute(text("""
          SELECT o.id, o.slug, o.title FROM occupations o
          WHERE EXISTS (SELECT 1 FROM occupation_scores s WHERE s.occupation_id = o.id)
          ORDER BY o.id
        """))).mappings().all()
        identities: dict[str, int] = {}
        for occupation in occupations:
            identity_id = (await session.execute(
                text("SELECT id FROM canonical_occupation_identities WHERE jobs_vs_ai_occupation_id=:id"),
                {"id": occupation["id"]},
            )).scalar_one_or_none()
            if identity_id is None:
                identity_id = (await session.execute(text("""
                  INSERT INTO canonical_occupation_identities
                    (identity_key,jobs_vs_ai_occupation_id,identity_origin,created_by_policy,source_version)
                  VALUES (:key,:id,'existing_editorial','pytest-production-fixture','test')
                  RETURNING id
                """), {"key": f"pytest:{occupation['slug']}", "id": occupation["id"]})).scalar_one()
            identities[occupation["slug"]] = identity_id
        return identities


async def build_promotion_run(key_suffix: str = "base") -> dict[str, Any]:
    """Create one completed promotion run covering every scored demo occupation."""
    run_key = f"pytest-promotion-{key_suffix}-{uuid.uuid4().hex[:12]}"
    identities = await ensure_identities()

    async with SessionFactory() as session, session.begin():
        source_id = (await session.execute(
            text("SELECT id FROM data_sources ORDER BY id LIMIT 1")
        )).scalar_one()
        # The engine model, NOT the active one. Migration 026 registered it inactive and the
        # production store refuses anything outside the `jobsvsai-engine-v2` family, so a
        # fixture cannot accidentally label legacy arithmetic as engine intelligence.
        model_id = (await session.execute(text(
            "SELECT id FROM scoring_model_versions WHERE methodology_family='jobsvsai-engine-v2' "
            "ORDER BY created_at DESC LIMIT 1"
        ))).scalar_one()

        run_id = (await session.execute(text("""
          INSERT INTO production_promotion_runs (
            run_key,source_kind,scoring_model_version_id,promotion_policy_version,status,
            is_test_fixture,input_version_bundle,selection_policy,input_hash,source_id,created_by)
          VALUES (:run_key,'architecture_test_fixture',:model,'pytest-fixture-v1','in_progress',
            true,CAST(:bundle AS jsonb),CAST(:policy AS jsonb),:hash,:source,'system:pytest')
          RETURNING id
        """), {
            "run_key": run_key, "model": model_id, "bundle": json.dumps(VERSION_BUNDLE),
            "policy": json.dumps({"rule": "all scored demo occupations", "fixture": True}),
            "hash": _hash({"run": run_key}), "source": source_id,
        })).scalar_one()

        rows = (await session.execute(text("""
          SELECT o.id AS occupation_id, o.slug,
                 score.ai_exposure::float ai_exposure,
                 score.task_exposure::float task_exposure,
                 score.ai_capability_proximity::float ai_capability_proximity,
                 score.human_dependency::float human_dependency,
                 score.physical_dependency::float physical_dependency,
                 score.adoption_pressure::float adoption_pressure,
                 score.market_resilience::float market_resilience
          FROM occupations o
          JOIN LATERAL (
            SELECT * FROM occupation_scores WHERE occupation_id=o.id
            ORDER BY calculated_at DESC, id DESC LIMIT 1
          ) score ON true
          ORDER BY o.id
        """))).mappings().all()

        snapshot_ids: list[int] = []
        by_identity: dict[int, int] = {}
        for row in rows:
            factor_values = {
                "taskAutomationExposure": row["task_exposure"],
                "aiCapabilityProximity": row["ai_capability_proximity"],
                "humanDependencyResistance": 100.0 - row["human_dependency"],
                "physicalDependencyResistance": 100.0 - row["physical_dependency"],
                "adoptionPressure": row["adoption_pressure"],
                "labourMarketResilienceResistance": 100.0 - row["market_resilience"],
            }
            contributions = {
                key: round(FACTOR_WEIGHTS[key] * value, 4) for key, value in factor_values.items()
            }
            replacement_risk = round(sum(contributions.values()), 4)

            task_rows = (await session.execute(text("""
              SELECT t.id AS task_id, t.name,
                     ot.importance::float importance,
                     coalesce(ot.frequency, 100)::float frequency,
                     coalesce(latest.exposure, 0)::float exposure
              FROM occupation_tasks ot
              JOIN tasks t ON t.id = ot.task_id
              LEFT JOIN LATERAL (
                SELECT exposure FROM task_ai_scores WHERE task_id=t.id
                ORDER BY calculated_at DESC, id DESC LIMIT 1
              ) latest ON true
              WHERE ot.occupation_id=:occupation_id
              ORDER BY t.id
            """), {"occupation_id": row["occupation_id"]})).mappings().all()
            if not task_rows:
                continue

            total_weight = sum(task["importance"] * task["frequency"] for task in task_rows)
            task_payload = []
            for task in task_rows:
                normalized = (task["importance"] * task["frequency"]) / total_weight
                task_payload.append({
                    "onet_task_id": task["task_id"],
                    "statement": task["name"],
                    "exposure": task["exposure"],
                    "importance": task["importance"],
                    "frequency": task["frequency"],
                    "normalized": round(normalized, 6),
                    "contribution": round(normalized * task["exposure"], 4),
                })
            # AI Exposure is the sum of persisted contributions, so the reconciliation
            # assertions test the data rather than restating a constant.
            ai_exposure = round(sum(item["contribution"] for item in task_payload), 4)

            snapshot_id = (await session.execute(text("""
              INSERT INTO production_occupation_score_snapshots (
                promotion_run_id,identity_id,occupation_id,scoring_model_version_id,
                ai_exposure,replacement_risk,augmentation_potential,confidence,weighted_task_coverage,
                source_task_count,eligible_task_count,excluded_task_count,weighting_eligible_task_count,
                coverage_gate_status,confidence_gate_status,scoring_eligibility,publishable,
                frontier_index_version,frontier_track,structural_proxy_model_version,
                base_proxy_model_version,occupation_formula_version,task_formula_versions,
                capability_taxonomy_version,mapping_rubric_version,evidence_policy_version,
                calculated_at,exact_inputs,provisional_sensitivity,warnings,reconciliation,
                input_hash,source_id,provenance,created_by)
              VALUES (
                :run,:identity,:occupation,:model,
                :ai_exposure,:replacement_risk,NULL,:confidence,:coverage,
                :task_count,:task_count,0,:task_count,
                'passed','passed','production_ready',true,
                :frontier_version,:frontier_track,:structural_version,
                :base_version,:occupation_formula,CAST(:task_formulas AS jsonb),
                :taxonomy,:rubric,:policy,
                now(),CAST(:exact AS jsonb),CAST(:sensitivity AS jsonb),'[]'::jsonb,
                CAST(:reconciliation AS jsonb),:hash,:source,CAST(:provenance AS jsonb),'system:pytest')
              RETURNING id
            """), {
                "run": run_id, "identity": identities[row["slug"]],
                "occupation": row["occupation_id"], "model": model_id,
                "ai_exposure": ai_exposure, "replacement_risk": replacement_risk,
                "confidence": 76.4, "coverage": 71.61, "task_count": len(task_payload),
                "frontier_version": VERSION_BUNDLE["frontierIndexVersion"],
                "frontier_track": VERSION_BUNDLE["frontierTrack"],
                "structural_version": VERSION_BUNDLE["structuralProxyModelVersion"],
                "base_version": VERSION_BUNDLE["baseProxyModelVersion"],
                "occupation_formula": VERSION_BUNDLE["occupationFormulaVersion"],
                "task_formulas": json.dumps(VERSION_BUNDLE["taskFormulaVersions"]),
                "taxonomy": VERSION_BUNDLE["capabilityTaxonomyVersion"],
                "rubric": VERSION_BUNDLE["mappingRubricVersion"],
                "policy": VERSION_BUNDLE["evidencePolicyVersion"],
                "exact": json.dumps({"factors": factor_values}),
                "sensitivity": json.dumps({
                    "method": "one-at-a-time deterministic neutral-50 counterfactual",
                    "maximumAbsoluteScoreImpact": 0.0, "fixture": True}),
                "reconciliation": json.dumps({
                    "replacementContributionTotal": replacement_risk,
                    "exposureContributionTotal": ai_exposure, "passed": True}),
                "hash": _hash({"slug": row["slug"], "factors": factor_values}),
                "source": source_id,
                "provenance": json.dumps({"fixture": True, "promoted": False}),
            })).scalar_one()
            snapshot_ids.append(snapshot_id)
            by_identity[identities[row["slug"]]] = snapshot_id

            for order, (key, value) in enumerate(factor_values.items(), start=1):
                await session.execute(text("""
                  INSERT INTO production_score_factor_contributions (
                    snapshot_id,factor_key,factor_label,value,source_proxy_value,transformation,
                    weight,weighted_contribution,is_provisional_proxy,proxy_model_version,
                    placeholder,display_order)
                  VALUES (:snapshot,:key,:label,:value,:source_value,:transformation,
                    :weight,:contribution,:provisional,:proxy_version,false,:order)
                """), {
                    "snapshot": snapshot_id, "key": key, "label": FACTOR_LABELS[key],
                    "value": round(value, 4),
                    "source_value": round(100.0 - value, 4) if key in INVERSE_FACTORS else round(value, 4),
                    "transformation": "inverse: 100 - raw" if key in INVERSE_FACTORS else "identity",
                    "weight": FACTOR_WEIGHTS[key], "contribution": contributions[key],
                    "provisional": key in PROVISIONAL_FACTORS,
                    "proxy_version": PROVISIONAL_MODEL if key in PROVISIONAL_FACTORS else None,
                    "order": order,
                })

            for task in task_payload:
                await session.execute(text("""
                  INSERT INTO production_score_task_contributions (
                    snapshot_id,onet_task_id,onet_soc_code,task_statement,task_statement_hash,
                    ai_capability_fit,automation_feasibility,augmentation_potential,task_ai_exposure,
                    task_confidence,source_importance,source_frequency,source_weight,
                    normalized_covered_weight,exposure_contribution,weighting_eligible)
                  VALUES (:snapshot,:task_id,:soc,:statement,:statement_hash,
                    :fit,:automation,:augmentation,:exposure,
                    74.26,:importance,:frequency,:weight,
                    :normalized,:contribution,true)
                """), {
                    "snapshot": snapshot_id, "task_id": task["onet_task_id"],
                    "soc": f"00-0000.{row['occupation_id']:02d}", "statement": task["statement"],
                    "statement_hash": _hash(task["statement"])[:32],
                    "fit": min(100.0, task["exposure"] + 5),
                    "automation": task["exposure"],
                    "augmentation": min(100.0, task["exposure"] * 0.8 + 10),
                    "exposure": task["exposure"], "importance": task["importance"],
                    "frequency": task["frequency"],
                    "weight": task["importance"] * task["frequency"],
                    "normalized": task["normalized"], "contribution": task["contribution"],
                })

        await session.execute(text("""
          UPDATE production_promotion_runs
          SET status='completed', completed_at=now(), occupation_count=:count,
              reconciliation=CAST(:reconciliation AS jsonb)
          WHERE id=:id
        """), {"count": len(snapshot_ids), "id": run_id,
               "reconciliation": json.dumps({"snapshots": len(snapshot_ids), "passed": True})})

    await ensure_related_occupations(identities)
    return {
        "run_id": run_id,
        "run_key": run_key,
        "snapshot_ids": snapshot_ids,
        "identity_ids": list(identities.values()),
        "identities": identities,
        "by_identity": by_identity,
    }


async def ensure_related_occupations(identities: dict[str, int]) -> int | None:
    """Stage one O*NET-shaped related-occupation link between two demo occupations.

    The public reader takes related occupations from `public_occupation_related_occupations`,
    which the real content pipeline populates for the launch cohort only. The demo
    occupations these tests use sit outside that cohort, so the link they rely on has to be
    staged here. Rows go in their own content run: the reader resolves the newest run *per
    occupation*, so this cannot hide the real cohort's relations.
    """
    source_slug, target_slug = "software-developer", "cybersecurity-analyst"
    if source_slug not in identities or target_slug not in identities:
        return None

    async with SessionFactory() as session, session.begin():
        # Reuse an earlier fixture run only if it is still the newest run *for this source
        # occupation*. The reader resolves relations from `max(content_run_id)` per
        # occupation, so a later real content run covering this identity silently shadows an
        # older fixture row — the link would exist in the table and be invisible to the API.
        # Checking mere existence was enough while content runs only ever covered the launch
        # cohort; it stopped being enough once a run covered the whole corpus.
        existing = (await session.execute(text("""
          SELECT related.content_run_id
          FROM public_occupation_related_occupations related
          JOIN LATERAL (
            SELECT max(newer.content_run_id) AS newest
            FROM public_occupation_related_occupations newer
            WHERE newer.identity_id = related.identity_id
          ) latest ON latest.newest = related.content_run_id
          WHERE related.identity_id = :source AND related.related_identity_id = :target
          LIMIT 1
        """), {"source": identities[source_slug], "target": identities[target_slug]})).scalar()
        if existing is not None:
            return existing

        source_id = (await session.execute(
            text("SELECT id FROM data_sources ORDER BY id LIMIT 1"))).scalar_one()
        target_code = (await session.execute(text(
            "SELECT current_source_code FROM canonical_occupation_identities WHERE id=:id"
        ), {"id": identities[target_slug]})).scalar_one()
        run_id = (await session.execute(text("""
          INSERT INTO public_occupation_content_runs (
            run_key, content_policy_version, verdict_template_version, onet_source_version,
            occupation_count, complete_count, incomplete_count, input_hash, source_id,
            provenance, created_by)
          VALUES (:key,'pytest-related-fixture','pytest-related-fixture','O*NET 30.3',
                  0,0,0,:hash,:source,'{"fixture": true}'::jsonb,'pytest')
          RETURNING id
        """), {"key": f"pytest-related-{uuid.uuid4().hex[:12]}",
               "hash": uuid.uuid4().hex + uuid.uuid4().hex, "source": source_id})).scalar_one()
        await session.execute(text("""
          INSERT INTO public_occupation_related_occupations (
            content_run_id, identity_id, related_identity_id, related_onet_soc_code,
            relatedness_tier, relatedness_rank)
          VALUES (:run,:source,:target,:code,'Primary-Short',1)
        """), {"run": run_id, "source": identities[source_slug],
               "target": identities[target_slug], "code": target_code})
    return run_id


async def roll_back_run(run_id: int, reason: str) -> None:
    """Roll a promotion run back. Idempotent, and it never touches a snapshot row."""
    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          UPDATE production_promotion_runs
          SET status='rolled_back', rolled_back_at=now(),
              rolled_back_by='system:pytest', rolled_back_reason=:reason
          WHERE id=:id AND status <> 'rolled_back'
        """), {"id": run_id, "reason": reason})
