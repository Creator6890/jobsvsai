import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.occupation import ScoreDerivation, ScoreFactor, TaskContribution

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    settings = get_settings()
    valid_user = secrets.compare_digest(credentials.username.encode(), settings.admin_username.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    counts = (await session.execute(text("""
      SELECT
        (SELECT count(*) FROM occupations WHERE is_active) occupations,
        (SELECT count(*) FROM tasks) tasks,
        (SELECT count(*) FROM skills) skills,
        (SELECT count(DISTINCT occupation_id) FROM occupation_scores) scored,
        (SELECT count(*) FROM scoring_jobs WHERE status IN ('pending','running')) pending,
        (SELECT count(*) FROM scoring_jobs WHERE status='failed') errors,
        (SELECT count(*) FROM import_runs WHERE status='complete') completed_imports,
        (SELECT count(*) FROM import_runs WHERE status='failed') failed_imports,
        (SELECT max(calculated_at) FROM occupation_scores) latest_recalculation,
        (SELECT count(DISTINCT occupation_id) FROM market_signals) market_occupations
    """))).mappings().one()
    model = (await session.execute(text("""
      SELECT id, version, description, replacement_config, created_at
      FROM scoring_model_versions WHERE is_active ORDER BY created_at DESC LIMIT 1
    """))).mappings().first()
    latest_import = (await session.execute(text("""
      SELECT ir.id, ds.name source, ir.status, ir.records_read, ir.records_written,
             ir.error, ir.started_at, ir.completed_at
      FROM import_runs ir LEFT JOIN data_sources ds ON ds.id=ir.source_id
      ORDER BY coalesce(ir.completed_at, ir.started_at) DESC NULLS LAST, ir.id DESC LIMIT 1
    """))).mappings().first()
    latest_capability = (await session.execute(text("""
      SELECT name, version, capability_level, valid_from
      FROM ai_capabilities ORDER BY valid_from DESC LIMIT 1
    """))).mappings().first()
    occupation_count = int(counts["occupations"] or 0)
    scored = int(counts["scored"] or 0)
    market_occupations = int(counts["market_occupations"] or 0)
    return {
        **dict(counts),
        "score_coverage": round(scored / occupation_count * 100, 1) if occupation_count else 0,
        "market_coverage": round(market_occupations / occupation_count * 100, 1) if occupation_count else 0,
        "active_model": dict(model) if model else None,
        "latest_import": dict(latest_import) if latest_import else None,
        "latest_capability": dict(latest_capability) if latest_capability else None,
    }


@router.get("/scores")
async def scores(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    summary = (await session.execute(text("""
      SELECT count(*) FILTER (WHERE status='pending') queued,
             count(*) FILTER (WHERE status='running') running,
             count(*) FILTER (WHERE status='complete' AND completed_at::date=current_date) completed_today,
             count(*) FILTER (WHERE status='failed') failed
      FROM scoring_jobs
    """))).mappings().one()
    jobs = (await session.execute(text("""
      SELECT sj.id, o.slug occupation_slug, o.title occupation_title, sj.reason,
             sj.dependency_type, sj.status, sj.attempts, sj.error,
             sj.queued_at, sj.started_at, sj.completed_at
      FROM scoring_jobs sj LEFT JOIN occupations o ON o.id=sj.occupation_id
      ORDER BY sj.queued_at DESC LIMIT 25
    """))).mappings().all()
    return {"summary": dict(summary), "jobs": [dict(row) for row in jobs]}


@router.get("/phase4a")
async def phase4a_pilot(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    cohort = (await session.execute(text("""
      SELECT cohort.*,source.name source_name,run.run_version mapping_run_version,
             run.provider_name mapping_provider,run.model_name mapping_model,
             run.prompt_version,run.prohibited_input_attestation,
             run.input_task_count,run.output_task_count,
             count(mapping.id) FILTER (WHERE validation.scoring_eligible) scoring_eligible_mappings,
             count(mapping.id) FILTER (WHERE NOT validation.scoring_eligible) excluded_mappings
      FROM phase4a_pilot_cohorts cohort
      JOIN data_sources source ON source.id=cohort.source_id
      LEFT JOIN ai_generated_task_mapping_runs run ON run.id=cohort.mapping_run_id
      LEFT JOIN ai_generated_task_mappings mapping ON mapping.mapping_run_id=run.id
      LEFT JOIN LATERAL (
        SELECT event.scoring_eligible FROM ai_task_mapping_validation_events event
        WHERE event.ai_task_mapping_id=mapping.id ORDER BY event.created_at DESC,event.id DESC LIMIT 1
      ) validation ON true
      WHERE cohort.cohort_version='phase4a-2026q3-v1'
      GROUP BY cohort.id,source.name,run.id
    """))).mappings().one()
    runs = (await session.execute(text("""
      SELECT calculation.id,calculation.run_version,calculation.run_kind,
             calculation.methodology_phase,
             fit.formula_version capability_fit_formula,
             automation.formula_version automation_formula,
             augmentation.formula_version augmentation_formula,
             occupation.formula_version occupation_formula,
             mapping.run_version mapping_run_version,track.track_code frontier_track,
             calculation.dependency_hash,calculation.new_ai_mapping_calls,
             calculation.reused_mapping_count,calculation.task_assessment_count,
             calculation.occupation_score_count,calculation.reconciliation_status,
             calculation.replay_matches_previous,previous.run_version previous_run_version,
             baseline.run_version baseline_run_version,proxy.model_version proxy_model_version,
             calculation.provenance,calculation.created_at
      FROM phase4a_calculation_runs calculation
      JOIN phase4a_task_formula_versions fit ON fit.id=calculation.capability_fit_formula_id
      JOIN phase4a_task_formula_versions automation ON automation.id=calculation.automation_formula_id
      JOIN phase4a_task_formula_versions augmentation ON augmentation.id=calculation.augmentation_formula_id
      JOIN phase4a_occupation_formula_versions occupation ON occupation.id=calculation.occupation_formula_id
      JOIN ai_generated_task_mapping_runs mapping ON mapping.id=calculation.mapping_run_id
      JOIN frontier_ai_capability_index_tracks track ON track.id=calculation.frontier_track_id
      LEFT JOIN phase4a_calculation_runs previous ON previous.id=calculation.previous_run_id
      LEFT JOIN phase4a_calculation_runs baseline ON baseline.id=calculation.baseline_run_id
      LEFT JOIN phase4b_proxy_model_versions proxy ON proxy.id=calculation.proxy_model_version_id
      ORDER BY calculation.id DESC
    """))).mappings().all()
    latest_run_id = runs[0]["id"] if runs else None
    formulas = (await session.execute(text("""
      SELECT formula_type,formula_version,name,description,parameters,status,provenance,created_at
      FROM phase4a_task_formula_versions ORDER BY id
    """))).mappings().all()
    occupation_formula = (await session.execute(text("""
      SELECT formula_version,name,description,parameters,status,provenance,created_at
      FROM phase4a_occupation_formula_versions ORDER BY id
    """))).mappings().all()
    occupations = (await session.execute(text("""
      SELECT pilot.id pilot_occupation_id,pilot.requested_name,pilot.occupation_code,
             occupation.title source_title,pilot.cohort_order,pilot.selection_status,
             pilot.substitution_reason,pilot.readiness_snapshot,pilot.warnings readiness_warnings,
             score.source_task_count,score.mapped_task_count,score.excluded_task_count,
             score.weighting_eligible_task_count,score.weighted_task_coverage::float,
             score.ai_exposure::float,score.replacement_risk::float,score.confidence::float,
             score.methodology_phase,score.coverage_gate_status,
             score.confidence_penalty::float,score.scale_eligible,
             baseline_score.ai_exposure::float baseline_ai_exposure,
             baseline_score.replacement_risk::float baseline_replacement_risk,
             baseline_score.confidence::float baseline_confidence,
             score.factor_contributions,score.task_contributions,score.exact_inputs,
             score.warnings,score.reconciliation,score.input_hash,
             proxy.adoption_pressure::float,proxy.labour_market_resilience::float,
             proxy.proxy_confidence::float,proxy.domain_values proxy_domain_values,
             proxy.component_contributions proxy_component_contributions,
             proxy.exact_inputs proxy_exact_inputs,proxy.warnings proxy_warnings,
             proxy.reconciliation proxy_reconciliation,proxy.input_hash proxy_input_hash,
             proxy_model.model_version proxy_model_version
      FROM phase4a_pilot_occupations pilot
      JOIN onet_occupations occupation ON occupation.onet_soc_code=pilot.occupation_code
      LEFT JOIN phase4a_occupation_scores score
        ON score.pilot_occupation_id=pilot.id AND score.calculation_run_id=:run_id
      LEFT JOIN phase4a_calculation_runs calculation ON calculation.id=score.calculation_run_id
      LEFT JOIN phase4a_occupation_scores baseline_score
        ON baseline_score.pilot_occupation_id=pilot.id
       AND baseline_score.calculation_run_id=calculation.baseline_run_id
      LEFT JOIN phase4b_occupation_proxy_snapshots proxy ON proxy.id=score.proxy_snapshot_id
      LEFT JOIN phase4b_proxy_model_versions proxy_model ON proxy_model.id=proxy.proxy_model_version_id
      WHERE pilot.cohort_id=:cohort_id ORDER BY pilot.cohort_order
    """), {"run_id": latest_run_id, "cohort_id": cohort["id"]})).mappings().all()
    tasks = (await session.execute(text("""
      SELECT assessment.id,assessment.pilot_occupation_id,assessment.onet_task_id,
             task.statement task_statement,task.importance_score::float,task.frequency_score::float,
             task.weighting_eligible,assessment.ai_capability_fit::float,
             assessment.automation_feasibility::float,assessment.augmentation_potential::float,
             assessment.task_ai_exposure::float,assessment.confidence::float,
             assessment.methodology_phase,assessment.proxy_confidence_penalty::float,
             assessment.capability_contributions,assessment.constraint_contributions,
             assessment.exact_inputs,assessment.warnings,assessment.reconciliation,
             assessment.input_hash,mapping.mapping_confidence::float,mapping.ambiguity_state
      FROM phase4a_task_assessments assessment
      JOIN onet_tasks task ON task.task_id=assessment.onet_task_id
      JOIN ai_generated_task_mappings mapping ON mapping.id=assessment.ai_task_mapping_id
      WHERE assessment.calculation_run_id=:run_id
      ORDER BY assessment.pilot_occupation_id,assessment.task_ai_exposure DESC,assessment.onet_task_id
    """), {"run_id": latest_run_id})).mappings().all() if latest_run_id else []
    excluded_tasks = (await session.execute(text("""
      SELECT pilot.id pilot_occupation_id,task.task_id onet_task_id,task.statement task_statement,
             mapping.ambiguity_state,mapping.mapping_confidence::float,event.failure_reasons,
             event.validation_status,event.review_state
      FROM phase4a_pilot_occupations pilot
      JOIN onet_tasks task ON task.occupation_code=pilot.occupation_code AND task.is_current
      JOIN ai_generated_task_mappings mapping
        ON mapping.onet_task_id=task.task_id AND mapping.mapping_run_id=:mapping_run_id
      JOIN LATERAL (
        SELECT validation.* FROM ai_task_mapping_validation_events validation
        WHERE validation.ai_task_mapping_id=mapping.id
        ORDER BY validation.created_at DESC,validation.id DESC LIMIT 1
      ) event ON true
      WHERE pilot.cohort_id=:cohort_id AND NOT event.scoring_eligible
      ORDER BY pilot.id,task.task_id
    """), {"mapping_run_id": cohort["mapping_run_id"], "cohort_id": cohort["id"]})).mappings().all()
    frontier_evidence = (await session.execute(text("""
      SELECT evidence.id,definition.slug capability_slug,definition.name capability_name,
             entry.capability_score::float,entry.confidence capability_confidence,
             evidence.source_tier,evidence.source_type,evidence.provider_name,evidence.model_name,
             evidence.model_version,evidence.evidence_date,evidence.benchmark_name,
             evidence.reported_result,evidence.source_reference,evidence.rationale,
             evidence.confidence::float,evidence.provenance
      FROM frontier_ai_capability_evidence_records evidence
      JOIN ai_capability_definitions definition ON definition.id=evidence.capability_definition_id
      JOIN frontier_ai_capability_index_entries entry
        ON entry.capability_definition_id=evidence.capability_definition_id
       AND entry.track_id=evidence.track_id
      JOIN frontier_ai_capability_index_tracks track ON track.id=evidence.track_id
      WHERE track.track_code='commercially_deployable'
      ORDER BY definition.slug,evidence.id
    """))).mappings().all()
    proxy_models = (await session.execute(text("""
      SELECT model.id,model.model_version,model.name,model.description,model.parameters,
             model.status,model.provenance,source.name source_name,model.created_at
      FROM phase4b_proxy_model_versions model
      JOIN data_sources source ON source.id=model.source_id ORDER BY model.id
    """))).mappings().all()
    diagnostics = (await session.execute(text("""
      SELECT diagnostic.metric_scope,diagnostic.metric_name,diagnostic.baseline_summary,
             diagnostic.calibrated_summary,diagnostic.delta_summary,diagnostic.reconciliation,
             baseline.run_version baseline_run_version,
             calibration.run_version calibration_run_version,
             diagnostic.provenance,diagnostic.created_at
      FROM phase4b_distribution_diagnostics diagnostic
      JOIN phase4a_calculation_runs baseline ON baseline.id=diagnostic.baseline_run_id
      JOIN phase4a_calculation_runs calibration ON calibration.id=diagnostic.calibration_run_id
      WHERE diagnostic.calibration_run_id=(
        SELECT max(latest.calibration_run_id) FROM phase4b_distribution_diagnostics latest
      )
      ORDER BY diagnostic.metric_scope,diagnostic.metric_name
    """))).mappings().all()
    isolation = (await session.execute(text("""
      SELECT
        (SELECT count(*) FROM occupation_scores) production_occupation_score_rows,
        (SELECT count(*) FROM task_ai_scores) legacy_task_score_rows,
        (SELECT count(*) FROM frontier_ai_capability_index_entries entry
          JOIN frontier_ai_capability_index_tracks track ON track.id=entry.track_id
          WHERE track.track_code='technical_frontier') technical_frontier_values,
        (SELECT count(*) FROM phase4a_occupation_scores) pilot_score_rows,
        (SELECT count(*) FROM phase4a_task_assessments) pilot_task_assessment_rows
    """))).mappings().one()
    return {
        "cohort": dict(cohort),
        "runs": [dict(row) for row in runs],
        "task_formulas": [dict(row) for row in formulas],
        "occupation_formulas": [dict(row) for row in occupation_formula],
        "occupations": [dict(row) for row in occupations],
        "tasks": [dict(row) for row in tasks],
        "excluded_tasks": [dict(row) for row in excluded_tasks],
        "frontier_evidence": [dict(row) for row in frontier_evidence],
        "proxy_models": [dict(row) for row in proxy_models],
        "diagnostics": [dict(row) for row in diagnostics],
        "isolation": dict(isolation),
    }


@router.get("/phase4c")
async def phase4c_validation(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    cohort = (await session.execute(text("""
      SELECT cohort.*,source.name source_name,mapping.run_version new_mapping_run_version,
             mapping.input_task_count new_mapping_rows,mapping.output_task_count new_mapping_outputs,
             mapping.prohibited_input_attestation,mapping.inference_configuration,
             (SELECT count(*) FROM phase4c_validation_occupations occupation
               WHERE occupation.cohort_id=cohort.id AND occupation.cohort_role='retained_phase4a') retained_occupations,
             (SELECT count(*) FROM phase4c_validation_occupations occupation
               WHERE occupation.cohort_id=cohort.id AND occupation.cohort_role='added_validation') added_occupations,
             (SELECT count(*) FROM phase4c_task_mapping_scope scope
               WHERE scope.cohort_id=cohort.id) source_tasks,
             (SELECT count(*) FROM phase4c_task_mapping_scope scope
               WHERE scope.cohort_id=cohort.id AND scope.scope_decision='reused') reused_mappings,
             (SELECT count(*) FROM phase4c_task_mapping_scope scope
               WHERE scope.cohort_id=cohort.id AND scope.scope_decision='generated') generated_eligible_mappings,
             (SELECT count(*) FROM phase4c_task_mapping_scope scope
               WHERE scope.cohort_id=cohort.id AND scope.scope_decision='unmapped_insufficient_evidence') insufficient_mapping_attempts,
             (SELECT count(*) FROM phase4c_task_mapping_scope scope
               WHERE scope.cohort_id=cohort.id AND scope.scope_decision='unmapped_after_gate') unmapped_after_gate
      FROM phase4c_validation_cohorts cohort
      JOIN data_sources source ON source.id=cohort.source_id
      LEFT JOIN ai_generated_task_mapping_runs mapping ON mapping.id=cohort.new_mapping_run_id
      WHERE cohort.cohort_version='phase4c-2026q3-v1'
    """))).mappings().one()
    runs = (await session.execute(text("""
      SELECT run.id,run.run_version,run.run_kind,run.mapping_scope_hash,run.dependency_hash,
             run.new_mapping_count,run.reused_mapping_count,run.external_ai_calls,
             run.task_assessment_count,run.occupation_score_count,run.reconciliation_status,
             run.replay_matches_previous,previous.run_version previous_run_version,
             fit.formula_version capability_fit_formula,
             automation.formula_version automation_formula,
             augmentation.formula_version augmentation_formula,
             occupation.formula_version occupation_formula,proxy.model_version proxy_model_version,
             track.track_code frontier_track,run.provenance,run.created_at
      FROM phase4c_calculation_runs run
      JOIN phase4a_task_formula_versions fit ON fit.id=run.capability_fit_formula_id
      JOIN phase4a_task_formula_versions automation ON automation.id=run.automation_formula_id
      JOIN phase4a_task_formula_versions augmentation ON augmentation.id=run.augmentation_formula_id
      JOIN phase4a_occupation_formula_versions occupation ON occupation.id=run.occupation_formula_id
      JOIN phase4b_proxy_model_versions proxy ON proxy.id=run.proxy_model_version_id
      JOIN frontier_ai_capability_index_tracks track ON track.id=run.frontier_track_id
      LEFT JOIN phase4c_calculation_runs previous ON previous.id=run.previous_run_id
      ORDER BY run.id DESC
    """))).mappings().all()
    latest_run_id = runs[0]["id"] if runs else None
    occupations = (await session.execute(text("""
      WITH scope_counts AS (
        SELECT validation_occupation_id,
               count(*) source_tasks,
               count(*) FILTER (WHERE scope_decision='reused') reused,
               count(*) FILTER (WHERE scope_decision='generated') generated,
               count(*) FILTER (WHERE scope_decision='unmapped_insufficient_evidence') insufficient,
               count(*) FILTER (WHERE scope_decision='unmapped_after_gate') after_gate
        FROM phase4c_task_mapping_scope GROUP BY validation_occupation_id
      )
      SELECT validation.id validation_occupation_id,validation.occupation_code,
             source_occupation.title,validation.cohort_order,validation.cohort_role,
             validation.stress_dimensions,validation.selection_rationale,
             validation.expected_proxy_behavior,validation.readiness_snapshot,
             scope.source_tasks,scope.reused,scope.generated,scope.insufficient,scope.after_gate,
             score.source_task_count,score.mapped_task_count,score.excluded_task_count,
             score.weighting_eligible_task_count,score.weighted_task_coverage::float,
             score.ai_exposure::float,score.replacement_risk::float,score.confidence::float,
             score.coverage_gate_status,score.confidence_penalty::float,score.scale_eligible,
             score.factor_contributions,score.warnings score_warnings,score.reconciliation score_reconciliation,
             proxy.adoption_pressure::float,proxy.labour_market_resilience::float,
             proxy.proxy_confidence::float,proxy.domain_values,proxy.component_contributions,
             proxy.exact_inputs proxy_exact_inputs,proxy.warnings proxy_warnings,
             proxy.reconciliation proxy_reconciliation,proxy.input_hash proxy_input_hash,
             model.model_version proxy_model_version
      FROM phase4c_validation_occupations validation
      JOIN onet_occupations source_occupation
        ON source_occupation.onet_soc_code=validation.occupation_code AND source_occupation.is_current
      LEFT JOIN scope_counts scope ON scope.validation_occupation_id=validation.id
      LEFT JOIN phase4c_occupation_scores score
        ON score.validation_occupation_id=validation.id AND score.calculation_run_id=:run_id
      LEFT JOIN phase4c_proxy_snapshots proxy ON proxy.validation_occupation_id=validation.id
      LEFT JOIN phase4b_proxy_model_versions model ON model.id=proxy.proxy_model_version_id
      WHERE validation.cohort_id=:cohort_id ORDER BY validation.cohort_order
    """), {"run_id": latest_run_id, "cohort_id": cohort["id"]})).mappings().all()
    pairwise_results = (await session.execute(text("""
      SELECT expectation.id expectation_id,expectation.expectation_version,
             expectation.proxy_metric,higher.occupation_code higher_occupation_code,
             higher_source.title higher_occupation_title,
             lower.occupation_code lower_occupation_code,lower_source.title lower_occupation_title,
             expectation.minimum_delta::float,expectation.rationale,expectation.evidence,
             result.higher_value::float,result.lower_value::float,result.observed_delta::float,
             result.passed,result.severity,result.finding,result.reconciliation
      FROM phase4c_proxy_pairwise_expectations expectation
      JOIN phase4c_validation_occupations higher ON higher.id=expectation.higher_occupation_id
      JOIN onet_occupations higher_source
        ON higher_source.onet_soc_code=higher.occupation_code AND higher_source.is_current
      JOIN phase4c_validation_occupations lower ON lower.id=expectation.lower_occupation_id
      JOIN onet_occupations lower_source
        ON lower_source.onet_soc_code=lower.occupation_code AND lower_source.is_current
      LEFT JOIN phase4c_proxy_validation_results result
        ON result.expectation_id=expectation.id AND result.calculation_run_id=:run_id
      WHERE expectation.cohort_id=:cohort_id
      ORDER BY result.passed,result.severity,expectation.proxy_metric,expectation.id
    """), {"run_id": latest_run_id, "cohort_id": cohort["id"]})).mappings().all()
    isolation = (await session.execute(text("""
      SELECT (SELECT count(*) FROM occupation_scores) production_occupation_score_rows,
             (SELECT count(*) FROM task_ai_scores) production_task_score_rows,
             (SELECT count(*) FROM phase4c_occupation_scores) phase4c_score_rows,
             (SELECT count(*) FROM phase4c_task_assessments) phase4c_task_assessment_rows,
             (SELECT count(*) FROM phase4c_calculation_runs WHERE external_ai_calls<>0) runs_with_ai_calls
    """))).mappings().one()

    def metric_value(row: dict[str, object], metric: str) -> float:
        if metric == "adoption-pressure":
            return float(row["adoption_pressure"])
        if metric == "labour-market-resilience":
            return float(row["labour_market_resilience"])
        return float(row["domain_values"][metric]["value"])

    def absolute_pass(value: float, expectation: str) -> bool:
        if expectation == "high":
            return value >= 60
        if expectation == "low":
            return value <= 40
        if expectation == "medium":
            return 35 <= value <= 65
        if expectation == "medium-high":
            return value >= 50
        return False

    absolute_results = []
    for raw_row in occupations:
        row = dict(raw_row)
        for metric, expectation in row["expected_proxy_behavior"].items():
            if metric == "expectation":
                continue
            value = metric_value(row, metric)
            absolute_results.append({
                "occupation_code": row["occupation_code"],
                "occupation_title": row["title"],
                "proxy_metric": metric,
                "expected_band": expectation,
                "observed_value": value,
                "passed": absolute_pass(value, expectation),
                "threshold_policy": "high>=60; low<=40; medium=35..65; medium-high>=50",
            })
    return {
        "cohort": dict(cohort),
        "runs": [dict(row) for row in runs],
        "occupations": [dict(row) for row in occupations],
        "pairwise_results": [dict(row) for row in pairwise_results],
        "absolute_results": absolute_results,
        "isolation": dict(isolation),
    }


@router.get("/archetypes")
async def occupational_archetypes(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Read-only inspection of the disabled Occupational Archetype v1 pilot."""
    flag = (await session.execute(text("""
      SELECT flag_key,layer_version,enabled,production_allowed,configuration,provenance,created_at
      FROM scoring_enrichment_feature_flags
      WHERE flag_key='occupational_archetype_layer'
    """))).mappings().one()
    model = (await session.execute(text("""
      SELECT id,model_version,name,description,status,source_version,algorithm,cluster_count,
             random_seed,feature_schema,normalization_policy,discovery_configuration,
             source_input_hash,implementation_hash,provenance,created_at
      FROM occupational_archetype_model_versions ORDER BY id DESC LIMIT 1
    """))).mappings().one_or_none()
    if model is None:
        return {"feature_flag": dict(flag), "model": None, "archetypes": [], "runs": [],
                "occupations": [], "validations": [], "isolation": {}}
    archetypes = (await session.execute(text("""
      SELECT definition.id,definition.archetype_code,definition.name,definition.description,
             definition.interpretation_status,definition.member_count,definition.top_features,
             definition.representative_occupations,definition.quality_metrics,
             count(DISTINCT membership.id) FILTER (WHERE membership.membership_role='secondary') secondary_memberships,
             jsonb_object_agg(baseline.structural_dimension,jsonb_build_object(
               'value',baseline.baseline_value::float,'confidence',baseline.confidence::float,
               'supporting_occupations',baseline.supporting_occupation_count,
               'dispersion',baseline.source_dispersion::float,'formula',baseline.formula_version
             ) ORDER BY baseline.structural_dimension) baselines
      FROM occupational_archetype_definitions definition
      JOIN archetype_structural_baselines baseline ON baseline.archetype_definition_id=definition.id
      LEFT JOIN occupation_archetype_memberships membership
        ON membership.archetype_definition_id=definition.id
      WHERE definition.model_version_id=:model_id
      GROUP BY definition.id ORDER BY definition.archetype_code
    """), {"model_id": model["id"]})).mappings().all()
    runs = (await session.execute(text("""
      SELECT run.id,run.run_version,run.run_kind,run.occupation_count,run.task_assessment_count,
             run.external_ai_calls,run.regenerated_mapping_count,run.dependency_hash,
             run.reconciliation_status,run.replay_matches_previous,run.provenance,run.created_at,
             baseline.run_version baseline_run_version,previous.run_version previous_run_version
      FROM archetype_phase4c_validation_runs run
      JOIN phase4c_calculation_runs baseline ON baseline.id=run.baseline_phase4c_run_id
      LEFT JOIN archetype_phase4c_validation_runs previous ON previous.id=run.previous_run_id
      WHERE run.model_version_id=:model_id ORDER BY run.id DESC
    """), {"model_id": model["id"]})).mappings().all()
    latest_run_id = runs[0]["id"] if runs else None
    occupations = (await session.execute(text("""
      WITH memberships AS (
        SELECT membership.occupation_code,
               max(definition.archetype_code) FILTER (WHERE membership.membership_role='primary') primary_code,
               max(definition.name) FILTER (WHERE membership.membership_role='primary') primary_name,
               max(membership.membership_strength::float) FILTER (WHERE membership.membership_role='primary') primary_strength,
               max(membership.membership_confidence::float) FILTER (WHERE membership.membership_role='primary') primary_confidence,
               max(definition.archetype_code) FILTER (WHERE membership.membership_role='secondary') secondary_code
        FROM occupation_archetype_memberships membership
        JOIN occupational_archetype_definitions definition ON definition.id=membership.archetype_definition_id
        WHERE membership.model_version_id=:model_id GROUP BY membership.occupation_code
      ), adjustment AS (
        SELECT validation_occupation_id,
               jsonb_object_agg(structural_dimension,jsonb_build_object(
                 'baseline',archetype_baseline::float,'source_evidence',occupation_source_evidence::float,
                 'evidence_confidence',evidence_confidence::float,'prior_weight',prior_weight::float,
                 'adjustment',occupation_adjustment::float,'result',resulting_proxy::float,
                 'result_confidence',resulting_confidence::float,'formula',formula_version,
                 'warnings',warnings,'reconciliation',reconciliation
               ) ORDER BY structural_dimension) adjustments
        FROM occupation_archetype_proxy_adjustments
        WHERE model_version_id=:model_id GROUP BY validation_occupation_id
      )
      SELECT validation.occupation_code,source.title,validation.expected_proxy_behavior,
             membership.primary_code,membership.primary_name,membership.primary_strength,
             membership.primary_confidence,membership.secondary_code,adjustment.adjustments,
             score.ai_exposure::float,score.replacement_risk::float,score.confidence::float,
             score.weighted_task_coverage::float,score.coverage_gate_status,score.scale_eligible,
             score.ai_exposure_delta::float,score.replacement_risk_delta::float,
             score.confidence_delta::float,score.factor_contributions,score.warnings,score.reconciliation
      FROM phase4c_validation_occupations validation
      JOIN onet_occupations source
        ON source.onet_soc_code=validation.occupation_code AND source.is_current
      JOIN memberships membership ON membership.occupation_code=validation.occupation_code
      LEFT JOIN adjustment ON adjustment.validation_occupation_id=validation.id
      LEFT JOIN archetype_phase4c_occupation_scores score
        ON score.validation_occupation_id=validation.id AND score.validation_run_id=:run_id
      WHERE validation.cohort_id=(SELECT id FROM phase4c_validation_cohorts
                                  WHERE cohort_version='phase4c-2026q3-v1')
      ORDER BY validation.cohort_order
    """), {"model_id": model["id"], "run_id": latest_run_id})).mappings().all()
    validations = (await session.execute(text("""
      SELECT validation_type,validation_key,structural_dimension,baseline_outcome,
             archetype_outcome,baseline_value,archetype_value,improved,regressed,finding,reconciliation
      FROM archetype_proxy_validation_results WHERE validation_run_id=:run_id
      ORDER BY validation_type,archetype_outcome,validation_key
    """), {"run_id": latest_run_id})).mappings().all() if latest_run_id else []
    isolation = (await session.execute(text("""
      SELECT (SELECT count(*) FROM occupation_scores) production_occupation_score_rows,
             (SELECT count(*) FROM task_ai_scores) production_task_score_rows,
             (SELECT count(*) FROM archetype_phase4c_occupation_scores) pilot_score_rows,
             (SELECT count(*) FROM archetype_phase4c_task_assessments) pilot_task_rows,
             (SELECT count(*) FROM archetype_phase4c_validation_runs WHERE external_ai_calls<>0) runs_with_ai_calls,
             (SELECT count(*) FROM archetype_phase4c_validation_runs WHERE regenerated_mapping_count<>0) runs_with_regenerated_mappings
    """))).mappings().one()
    return {
        "feature_flag": dict(flag), "model": dict(model),
        "archetypes": [dict(row) for row in archetypes], "runs": [dict(row) for row in runs],
        "occupations": [dict(row) for row in occupations],
        "validations": [dict(row) for row in validations], "isolation": dict(isolation),
    }


@router.get("/phase4d")
async def phase4d_direct_proxies(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Read-only Phase 4D formula, source, score and validation inspector."""
    models = (await session.execute(text("""
      SELECT id,model_version,name,description,status,source_version,reconstructed_families,
             formula_parameters,missing_data_policy,implementation_hash,provenance,created_at
      FROM phase4d_proxy_model_versions ORDER BY id DESC
    """))).mappings().all()
    if not models:
        return {"models": [], "runs": [], "occupations": [], "validations": [],
                "summary": {}, "isolation": {}}
    model = models[0]
    runs = (await session.execute(text("""
      SELECT run.id,run.run_version,run.run_kind,run.occupation_count,run.task_assessment_count,
             run.external_ai_calls,run.regenerated_mapping_count,run.archetype_scoring_enabled,
             run.production_score_writes,run.dependency_hash,run.reconciliation_status,
             run.replay_matches_previous,run.provenance,run.created_at,
             previous.run_version previous_run_version,baseline.run_version baseline_run_version
      FROM phase4d_calculation_runs run
      JOIN phase4c_calculation_runs baseline ON baseline.id=run.baseline_phase4c_run_id
      LEFT JOIN phase4d_calculation_runs previous ON previous.id=run.previous_run_id
      WHERE run.proxy_model_version_id=:model_id ORDER BY run.id DESC
    """), {"model_id": model["id"]})).mappings().all()
    latest_run_id = runs[0]["id"] if runs else None
    occupations = (await session.execute(text("""
      SELECT validation.occupation_code,source.title,snapshot.id proxy_snapshot_id,
             snapshot.physical_presence::float,snapshot.environment_variability::float,
             snapshot.accountability::float,snapshot.consequence_severity::float,
             snapshot.proxy_confidence::float,snapshot.family_values,snapshot.exact_inputs proxy_exact_inputs,
             snapshot.warnings proxy_warnings,snapshot.reconciliation proxy_reconciliation,
             snapshot.input_hash proxy_input_hash,
             score.ai_exposure::float,score.replacement_risk::float,score.confidence::float,
             score.weighted_task_coverage::float,score.coverage_gate_status,score.scale_eligible,
             score.ai_exposure_delta::float,score.replacement_risk_delta::float,
             score.confidence_delta::float,score.factor_contributions,score.warnings score_warnings,
             score.reconciliation score_reconciliation
      FROM phase4c_validation_occupations validation
      JOIN onet_occupations source
        ON source.onet_soc_code=validation.occupation_code AND source.is_current
      JOIN phase4d_proxy_snapshots snapshot
        ON snapshot.validation_occupation_id=validation.id AND snapshot.proxy_model_version_id=:model_id
      LEFT JOIN phase4d_occupation_scores score
        ON score.validation_occupation_id=validation.id AND score.calculation_run_id=:run_id
      WHERE validation.cohort_id=(SELECT id FROM phase4c_validation_cohorts
                                  WHERE cohort_version='phase4c-2026q3-v1')
      ORDER BY validation.cohort_order
    """), {"model_id": model["id"], "run_id": latest_run_id})).mappings().all()
    validations = (await session.execute(text("""
      SELECT validation_type,validation_key,proxy_family,baseline_outcome,phase4d_outcome,
             baseline_value,phase4d_value,improved,regressed,finding,reconciliation
      FROM phase4d_proxy_validation_results WHERE calculation_run_id=:run_id
      ORDER BY validation_type,phase4d_outcome,validation_key
    """), {"run_id": latest_run_id})).mappings().all() if latest_run_id else []
    summary = (await session.execute(text("""
      WITH validation AS (
        SELECT * FROM phase4d_proxy_validation_results WHERE calculation_run_id=:run_id
      ), score AS (
        SELECT * FROM phase4d_occupation_scores WHERE calculation_run_id=:run_id
      )
      SELECT (SELECT count(*) FROM validation WHERE validation_type='absolute_band'
              AND baseline_outcome='failure') baseline_absolute_failures,
             (SELECT count(*) FROM validation WHERE validation_type='absolute_band'
              AND phase4d_outcome='failure') phase4d_absolute_failures,
             (SELECT count(*) FROM validation WHERE validation_type='pairwise'
              AND phase4d_outcome='pass') pairwise_passes,
             (SELECT count(*) FROM validation WHERE validation_type='pairwise'
              AND phase4d_outcome='warning') pairwise_warnings,
             (SELECT count(*) FROM validation WHERE validation_type='pairwise'
              AND phase4d_outcome='failure') pairwise_reversals,
             (SELECT count(*) FROM validation WHERE improved) improvements,
             (SELECT count(*) FROM validation WHERE regressed) regressions,
             (SELECT count(*) FROM score WHERE scale_eligible) scale_eligible,
             (SELECT count(*) FROM score WHERE NOT scale_eligible) coverage_blocked,
             (SELECT avg(ai_exposure_delta)::float FROM score) mean_ai_exposure_delta,
             (SELECT avg(replacement_risk_delta)::float FROM score) mean_replacement_risk_delta,
             (SELECT avg(confidence_delta)::float FROM score) mean_confidence_delta
    """), {"run_id": latest_run_id})).mappings().one() if latest_run_id else {}
    isolation = (await session.execute(text("""
      SELECT (SELECT count(*) FROM occupation_scores) production_occupation_score_rows,
             (SELECT count(*) FROM task_ai_scores) production_task_score_rows,
             (SELECT count(*) FROM phase4d_occupation_scores) phase4d_score_rows,
             (SELECT count(*) FROM phase4d_task_assessments) phase4d_task_rows,
             (SELECT count(*) FROM phase4d_calculation_runs WHERE external_ai_calls<>0) runs_with_ai_calls,
             (SELECT count(*) FROM phase4d_calculation_runs WHERE regenerated_mapping_count<>0) runs_with_regenerated_mappings,
             (SELECT count(*) FROM phase4d_calculation_runs WHERE production_score_writes<>0) runs_with_production_writes,
             (SELECT enabled FROM scoring_enrichment_feature_flags
              WHERE flag_key='occupational_archetype_layer') archetype_layer_enabled
    """))).mappings().one()
    return {"models": [dict(row) for row in models], "runs": [dict(row) for row in runs],
            "occupations": [dict(row) for row in occupations],
            "validations": [dict(row) for row in validations], "summary": dict(summary),
            "isolation": dict(isolation)}


@router.get("/phase5")
async def phase5_bounded_corpus(
    candidate_status: str | None = Query(None, pattern="^(scored|blocked)$"),
    exposure_min: float | None = Query(None, ge=0, le=100),
    exposure_max: float | None = Query(None, ge=0, le=100),
    replacement_min: float | None = Query(None, ge=0, le=100),
    replacement_max: float | None = Query(None, ge=0, le=100),
    confidence_min: float | None = Query(None, ge=0, le=100),
    coverage_min: float | None = Query(None, ge=0, le=100),
    soc: str | None = Query(None, max_length=16),
    warning: str | None = Query(None, max_length=80),
    provisional_sensitive: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Filterable read-only Phase 5 candidate corpus inspector."""
    latest = (await session.execute(text("""
      SELECT run.*,namespace.namespace_version,namespace.occupation_population_hash,
             policy.policy_version anomaly_policy_version,previous.run_version previous_run_version
      FROM phase5_calculation_runs run
      JOIN phase5_candidate_namespaces namespace ON namespace.id=run.namespace_id
      JOIN phase5_anomaly_policy_versions policy ON policy.id=run.anomaly_policy_version_id
      LEFT JOIN phase5_calculation_runs previous ON previous.id=run.previous_run_id
      ORDER BY run.id DESC LIMIT 1
    """))).mappings().first()
    if latest is None:
        return {"runs": [], "report": None, "occupations": [], "anomalies": [],
                "total_filtered": 0, "isolation": {}}
    runs = (await session.execute(text("""
      SELECT run.id,run.run_version,run.run_kind,run.attempted_occupation_count,
             run.scored_occupation_count,run.blocked_occupation_count,run.task_assessment_count,
             run.new_mapping_count,run.reused_exact_mapping_count,run.reused_hash_mapping_count,
             run.external_ai_calls,run.estimated_ai_tokens,run.local_compute_milliseconds,
             run.production_score_writes,run.public_activations,run.archetype_scoring_enabled,
             run.dependency_hash,run.reconciliation_status,run.replay_matches_previous,
             previous.run_version previous_run_version,run.created_at
      FROM phase5_calculation_runs run
      LEFT JOIN phase5_calculation_runs previous ON previous.id=run.previous_run_id
      WHERE run.namespace_id=:namespace_id ORDER BY run.id DESC
    """), {"namespace_id": latest["namespace_id"]})).mappings().all()
    report = (await session.execute(text("""
      SELECT report_version,corpus_summary,distributions,percentiles,correlation,extremes,
             soc_outliers,provisional_impact,anomaly_summary,mapping_reuse_summary,
             recommended_launch_cohort,exact_reconciliation,input_hash,created_at
      FROM phase5_corpus_reports WHERE calculation_run_id=:run_id
    """), {"run_id": latest["id"]})).mappings().one()

    clauses = ["score.calculation_run_id=:run_id"]
    parameters: dict[str, object] = {"run_id": latest["id"], "limit": limit, "offset": offset}
    if candidate_status == "scored":
        clauses.append("score.candidate_status='review_ready'")
    elif candidate_status == "blocked":
        clauses.append("score.candidate_status='blocked'")
    for name, column, value, operator in (
        ("exposure_min", "score.ai_exposure", exposure_min, ">="),
        ("exposure_max", "score.ai_exposure", exposure_max, "<="),
        ("replacement_min", "score.replacement_risk", replacement_min, ">="),
        ("replacement_max", "score.replacement_risk", replacement_max, "<="),
        ("confidence_min", "score.confidence", confidence_min, ">="),
        ("coverage_min", "score.weighted_task_coverage", coverage_min, ">="),
    ):
        if value is not None:
            clauses.append(f"{column}{operator}:{name}")
            parameters[name] = value
    if soc:
        clauses.append("candidate.occupation_code ILIKE :soc")
        parameters["soc"] = f"{soc.strip()}%"
    if warning:
        clauses.append("""(score.warnings::text ILIKE :warning OR EXISTS (
          SELECT 1 FROM phase5_anomaly_findings finding
          WHERE finding.calculation_run_id=score.calculation_run_id
            AND finding.candidate_occupation_id=score.candidate_occupation_id
            AND finding.anomaly_type ILIKE :warning))""")
        parameters["warning"] = f"%{warning.strip()}%"
    if provisional_sensitive is True:
        clauses.append("(score.provisional_sensitivity->>'maximumAbsoluteScoreImpact')::numeric>=3")
    elif provisional_sensitive is False:
        clauses.append("(score.provisional_sensitivity->>'maximumAbsoluteScoreImpact')::numeric<3")
    where_sql = " AND ".join(clauses)
    total_filtered = (await session.execute(text(f"""
      SELECT count(*) FROM phase5_occupation_scores score
      JOIN phase5_candidate_occupations candidate ON candidate.id=score.candidate_occupation_id
      WHERE {where_sql}
    """), parameters)).scalar_one()
    occupations = (await session.execute(text(f"""
      WITH anomaly AS (
        SELECT candidate_occupation_id,count(*) anomaly_count,
               array_agg(DISTINCT anomaly_type ORDER BY anomaly_type) anomaly_types,
               array_agg(DISTINCT severity ORDER BY severity) anomaly_severities
        FROM phase5_anomaly_findings WHERE calculation_run_id=:run_id
        GROUP BY candidate_occupation_id
      )
      SELECT candidate.id candidate_occupation_id,candidate.occupation_code,candidate.title_snapshot title,
             candidate.soc_major_group,score.calculation_status,score.ai_exposure::float,
             score.replacement_risk::float,score.confidence::float,
             score.weighted_task_coverage::float,score.source_task_count,score.eligible_task_count,
             score.excluded_task_count,score.weighting_eligible_task_count,
             score.coverage_gate_status,score.confidence_gate_status,score.candidate_status,
             score.public_activation_eligible,score.top_exposure_tasks,score.top_automation_constraints,
             score.augmentation_heavy_tasks,score.structural_proxy_inputs,score.provisional_sensitivity,
             score.factor_contributions,score.task_contributions,score.exact_inputs,score.warnings,
             score.blocking_reasons,score.reconciliation,score.input_hash,
             proxy.physical_presence::float,proxy.environment_variability::float,
             proxy.accountability::float,proxy.consequence_severity::float,
             proxy.human_dependency::float,proxy.regulation::float,proxy.adoption_pressure::float,
             proxy.labour_market_resilience::float,proxy.proxy_confidence::float,
             proxy.family_values,proxy.component_contributions proxy_component_contributions,
             proxy.exact_inputs proxy_exact_inputs,proxy.warnings proxy_warnings,
             proxy.reconciliation proxy_reconciliation,proxy.provisional_flags,proxy.input_hash proxy_input_hash,
             coalesce(anomaly.anomaly_count,0) anomaly_count,
             coalesce(anomaly.anomaly_types,ARRAY[]::text[]) anomaly_types,
             coalesce(anomaly.anomaly_severities,ARRAY[]::text[]) anomaly_severities
      FROM phase5_occupation_scores score
      JOIN phase5_candidate_occupations candidate ON candidate.id=score.candidate_occupation_id
      JOIN phase5_proxy_snapshots proxy ON proxy.id=score.proxy_snapshot_id
      LEFT JOIN anomaly ON anomaly.candidate_occupation_id=candidate.id
      WHERE {where_sql}
      ORDER BY score.candidate_status DESC,score.confidence DESC,candidate.occupation_code
      LIMIT :limit OFFSET :offset
    """), parameters)).mappings().all()
    anomalies = (await session.execute(text("""
      SELECT finding.id,finding.anomaly_type,finding.severity,finding.metric_values,
             finding.threshold_values,finding.explanation,finding.review_status,
             candidate.occupation_code,candidate.title_snapshot title
      FROM phase5_anomaly_findings finding
      LEFT JOIN phase5_candidate_occupations candidate ON candidate.id=finding.candidate_occupation_id
      WHERE finding.calculation_run_id=:run_id
      ORDER BY CASE finding.severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
               finding.anomaly_type,candidate.occupation_code NULLS FIRST LIMIT 200
    """), {"run_id": latest["id"]})).mappings().all()
    isolation = (await session.execute(text("""
      SELECT (SELECT count(*) FROM occupation_scores) production_occupation_score_rows,
             (SELECT count(*) FROM task_ai_scores) production_task_score_rows,
             (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_occupation_rows,
             (SELECT count(*) FROM phase5_calculation_runs WHERE production_score_writes<>0) runs_with_production_writes,
             (SELECT count(*) FROM phase5_calculation_runs WHERE public_activations<>0) runs_with_public_activations,
             (SELECT enabled FROM scoring_enrichment_feature_flags
              WHERE flag_key='occupational_archetype_layer') archetype_layer_enabled
    """))).mappings().one()
    return {
        "namespace": {"namespace_version": latest["namespace_version"],
                      "occupation_population_hash": latest["occupation_population_hash"],
                      "anomaly_policy_version": latest["anomaly_policy_version"]},
        "runs": [dict(row) for row in runs], "report": dict(report),
        "occupations": [dict(row) for row in occupations],
        "anomalies": [dict(row) for row in anomalies], "total_filtered": total_filtered,
        "filters": {"candidate_status": candidate_status, "exposure_min": exposure_min,
                    "exposure_max": exposure_max, "replacement_min": replacement_min,
                    "replacement_max": replacement_max, "confidence_min": confidence_min,
                    "coverage_min": coverage_min, "soc": soc, "warning": warning,
                    "provisional_sensitive": provisional_sensitive, "limit": limit, "offset": offset},
        "isolation": dict(isolation),
    }


@router.get("/imports")
async def imports(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    summary = (await session.execute(text("""
      SELECT count(*) FILTER (WHERE status='pending') pending,
             count(*) FILTER (WHERE status='running') running,
             count(*) FILTER (WHERE status='complete') complete,
             (SELECT count(*) FROM import_runs failed_run
              WHERE failed_run.status='failed' AND failed_run.id > COALESCE(
                (SELECT max(complete_run.id) FROM import_runs complete_run WHERE complete_run.status='complete'), 0
              )) failed
      FROM import_runs
    """))).mappings().one()
    runs = (await session.execute(text("""
      SELECT ir.id, ds.name source, ds.version source_version, ir.status,
             ir.records_read, ir.records_written, ir.error,
             ir.started_at, ir.completed_at, ir.metadata
      FROM import_runs ir LEFT JOIN data_sources ds ON ds.id=ir.source_id
      ORDER BY coalesce(ir.completed_at, ir.started_at) DESC NULLS LAST, ir.id DESC LIMIT 25
    """))).mappings().all()
    onet_coverage = (await session.execute(text("""
      SELECT
        (SELECT max(source_version) FROM onet_occupations WHERE is_current) source_version,
        (SELECT count(*) FROM onet_occupations WHERE is_current) occupations,
        (SELECT count(*) FROM onet_occupations WHERE is_current AND jobs_vs_ai_occupation_id IS NOT NULL) product_links,
        (SELECT count(*) FROM onet_alternate_titles WHERE is_current) alternate_titles,
        (SELECT count(*) FROM source_occupation_titles WHERE is_current) source_titles,
        (SELECT count(*) FROM onet_scales WHERE is_current) scales,
        (SELECT count(*) FROM source_taxonomies WHERE is_current) source_taxonomies,
        (SELECT count(*) FROM source_taxonomy_nodes WHERE is_current) source_taxonomy_nodes,
        (SELECT count(*) FROM source_occupation_taxonomy_memberships WHERE is_current) taxonomy_memberships,
        (SELECT count(*) FROM source_occupation_successions WHERE is_current) succession_mappings,
        (SELECT count(*) FROM onet_tasks WHERE is_current) tasks,
        (SELECT count(*) FROM onet_task_ratings WHERE is_current) task_ratings,
        (SELECT count(*) FROM onet_element_ratings WHERE is_current AND element_type='skill') skill_ratings,
        (SELECT count(*) FROM onet_element_ratings WHERE is_current AND element_type='ability') ability_ratings,
        (SELECT count(*) FROM onet_element_ratings WHERE is_current AND element_type='work_activity') work_activity_ratings,
        (SELECT count(*) FROM onet_element_ratings WHERE is_current AND element_type='work_context') work_context_ratings,
        (SELECT count(*) FROM onet_related_occupations WHERE is_current) related_occupations,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND importance_score IS NULL) tasks_missing_importance,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND frequency_score IS NULL) tasks_missing_frequency,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND weighting_eligible) weighting_eligible_tasks,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND NOT weighting_eligible) weighting_ineligible_tasks,
        (SELECT count(*) FROM onet_occupation_domain_coverage WHERE coverage_status IN ('partial','missing')) incomplete_domain_rows,
        (SELECT count(*) FROM onet_occupations occupation WHERE occupation.is_current AND NOT EXISTS (
          SELECT 1 FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current
        )) occupations_without_tasks,
        (SELECT count(*) FROM onet_task_ratings rating LEFT JOIN onet_tasks task ON task.task_id=rating.task_id
          WHERE rating.is_current AND task.task_id IS NULL) orphan_task_ratings,
        (SELECT count(*) FROM onet_element_ratings rating LEFT JOIN onet_elements element
          ON element.element_type=rating.element_type AND element.element_id=rating.element_id
          WHERE rating.is_current AND element.element_id IS NULL) orphan_element_ratings,
        (SELECT count(*) FROM onet_task_ratings rating LEFT JOIN onet_scales scale USING (scale_id)
          WHERE rating.is_current AND scale.scale_id IS NULL) orphan_task_scales,
        (SELECT count(*) FROM onet_element_ratings rating LEFT JOIN onet_scales scale USING (scale_id)
          WHERE rating.is_current AND scale.scale_id IS NULL) orphan_element_scales,
        (SELECT count(*) FROM source_occupation_successions WHERE allocation_weight IS NOT NULL) succession_weights,
        (SELECT count(*) FROM source_record_versions record
          JOIN data_sources source ON source.id=record.source_id
          WHERE record.is_current AND source.name LIKE 'O*NET Database %') current_source_records
    """))).mappings().one()
    missing_skills = (await session.execute(text("""
      SELECT occupation.onet_soc_code, occupation.title
      FROM onet_occupations occupation
      WHERE occupation.is_current AND NOT EXISTS (
        SELECT 1 FROM onet_element_ratings rating
        WHERE rating.occupation_code=occupation.onet_soc_code
          AND rating.element_type='skill' AND rating.is_current
      )
      ORDER BY occupation.onet_soc_code
    """))).mappings().all()
    incomplete_domains = (await session.execute(text("""
      SELECT coverage.occupation_code onet_soc_code, occupation.title, coverage.domain,
             coverage.coverage_status, coverage.entity_count, coverage.rating_count, coverage.issues
      FROM onet_occupation_domain_coverage coverage
      JOIN onet_occupations occupation ON occupation.onet_soc_code=coverage.occupation_code
      WHERE coverage.coverage_status IN ('partial','missing')
      ORDER BY coverage.occupation_code, coverage.domain
      LIMIT 100
    """))).mappings().all()
    incomplete_domain_summary = (await session.execute(text("""
      SELECT domain, coverage_status, count(*) occupations
      FROM onet_occupation_domain_coverage
      WHERE coverage_status IN ('partial','missing')
      GROUP BY domain, coverage_status ORDER BY domain, coverage_status
    """))).mappings().all()
    promotion_matrix = (await session.execute(text(
        "SELECT * FROM occupation_promotion_matrix"
    ))).mappings().one()
    lifecycle_states = (await session.execute(text("""
      SELECT lifecycle_state, count(*) occupations
      FROM occupation_promotion_profiles
      GROUP BY lifecycle_state ORDER BY lifecycle_state
    """))).mappings().all()
    identity_resolutions = (await session.execute(text("""
      SELECT resolution_type, review_status, count(*) mappings
      FROM occupation_identity_resolutions WHERE is_current
      GROUP BY resolution_type, review_status ORDER BY resolution_type, review_status
    """))).mappings().all()
    latest_onet_run = (await session.execute(text("""
      SELECT id, status, records_read, records_written, completed_at, metadata
      FROM import_runs WHERE (scope LIKE 'subset:%' OR scope='full') AND source_version IS NOT NULL
      ORDER BY id DESC LIMIT 1
    """))).mappings().first()
    coverage = dict(onet_coverage)
    coverage["missing_skill_occupations"] = [dict(row) for row in missing_skills]
    coverage["incomplete_domains"] = [dict(row) for row in incomplete_domains]
    coverage["incomplete_domain_summary"] = [dict(row) for row in incomplete_domain_summary]
    coverage["promotion_matrix"] = dict(promotion_matrix)
    coverage["lifecycle_states"] = [dict(row) for row in lifecycle_states]
    coverage["identity_resolutions"] = [dict(row) for row in identity_resolutions]
    coverage["latest_run"] = dict(latest_onet_run) if latest_onet_run else None
    coverage["relationship_checks_pass"] = all(int(coverage[key] or 0) == 0 for key in (
        "orphan_task_ratings", "orphan_element_ratings",
        "orphan_task_scales", "orphan_element_scales", "succession_weights",
    ))
    return {"summary": dict(summary), "runs": [dict(row) for row in runs], "onet_coverage": coverage}


@router.get("/system")
async def system_health(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    database_ok = bool((await session.execute(text("SELECT 1"))).scalar_one())
    settings = get_settings()
    redis_ok = False
    redis = Redis.from_url(settings.redis_url)
    try:
        redis_ok = bool(await redis.ping())
    finally:
        await redis.aclose()
    score_store = (await session.execute(text("""
      SELECT count(DISTINCT occupation_id) profession_pages,
             count(*) score_snapshots,
             max(calculated_at) latest_score
      FROM occupation_scores
    """))).mappings().one()
    return {
        "services": {"public_api": True, "postgresql": database_ok, "redis_queue": redis_ok},
        "score_store": dict(score_store),
        "environment": settings.environment,
    }


@router.get("/ai-enrichment")
async def ai_enrichment(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    taxonomies = (await session.execute(text("""
      SELECT taxonomy.id, taxonomy.version, taxonomy.name, taxonomy.description,
             taxonomy.status, taxonomy.methodology_version, taxonomy.created_at,
             count(definition.id) definitions
      FROM ai_capability_taxonomy_versions taxonomy
      LEFT JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy.id
      GROUP BY taxonomy.id ORDER BY taxonomy.created_at DESC
    """))).mappings().all()
    capabilities = (await session.execute(text("""
      SELECT definition.id, taxonomy.version taxonomy_version, definition.slug,
             definition.name, definition.description, definition.capability_category,
             definition.definition_version, definition.evidence, definition.provenance,
             definition.created_at
      FROM ai_capability_definitions definition
      JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=definition.taxonomy_version_id
      ORDER BY definition.capability_category, definition.name
    """))).mappings().all()
    mapping_sets = (await session.execute(text("""
      SELECT mapping_set.id, mapping_set.onet_task_id, task.occupation_code,
             occupation.title occupation_title, task.statement task_statement,
             taxonomy.version taxonomy_version, mapping_set.mapping_set_version,
             mapping_set.mapping_method, mapping_set.mapping_method_version,
             mapping_set.review_state, mapping_set.is_test_fixture,
             round(sum(mapping.weight),7) weight_total,
             jsonb_agg(jsonb_build_object(
               'capabilitySlug',definition.slug,'capabilityName',definition.name,
               'weight',mapping.weight,'requiredCapabilityLevel',mapping.required_capability_level,
               'confidence',mapping.confidence,'rationale',mapping.rationale,
               'evidence',mapping.evidence
             ) ORDER BY mapping.weight DESC) mappings
      FROM task_capability_mapping_sets mapping_set
      JOIN onet_tasks task ON task.task_id=mapping_set.onet_task_id
      JOIN onet_occupations occupation ON occupation.onet_soc_code=task.occupation_code
      JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=mapping_set.taxonomy_version_id
      JOIN task_capability_requirement_mappings mapping ON mapping.mapping_set_id=mapping_set.id
      JOIN ai_capability_definitions definition ON definition.id=mapping.capability_definition_id
      GROUP BY mapping_set.id,task.task_id,occupation.title,taxonomy.version
      ORDER BY mapping_set.onet_task_id
    """))).mappings().all()
    environment_taxonomies = (await session.execute(text("""
      SELECT taxonomy.id,taxonomy.version,taxonomy.name,taxonomy.description,taxonomy.status,
             taxonomy.methodology_version,count(definition.id) definitions
      FROM task_environment_taxonomy_versions taxonomy
      LEFT JOIN task_environment_constraint_definitions definition
        ON definition.environment_taxonomy_version_id=taxonomy.id
      GROUP BY taxonomy.id ORDER BY taxonomy.created_at DESC
    """))).mappings().all()
    constraints = (await session.execute(text("""
      SELECT definition.id,taxonomy.version taxonomy_version,definition.slug,
             definition.name,definition.description,definition.constraint_category,
             definition.value_semantics,definition.definition_version,
             count(mapping.id) test_mappings
      FROM task_environment_constraint_definitions definition
      JOIN task_environment_taxonomy_versions taxonomy
        ON taxonomy.id=definition.environment_taxonomy_version_id
      LEFT JOIN task_environment_constraint_mappings mapping
        ON mapping.constraint_definition_id=definition.id
      GROUP BY definition.id,taxonomy.version
      ORDER BY definition.constraint_category,definition.name
    """))).mappings().all()
    constraint_mappings = (await session.execute(text("""
      SELECT mapping.id,mapping.onet_task_id,task.occupation_code,
             left(task.statement,180) task_statement,definition.slug constraint_slug,
             definition.name constraint_name,mapping.constraint_level::float,
             mapping.confidence::float,mapping.mapping_version,mapping.mapping_method,
             mapping.mapping_method_version,mapping.review_state,mapping.is_test_fixture,
             mapping.evidence,mapping.provenance
      FROM task_environment_constraint_mappings mapping
      JOIN task_environment_constraint_definitions definition ON definition.id=mapping.constraint_definition_id
      JOIN onet_tasks task ON task.task_id=mapping.onet_task_id
      ORDER BY mapping.onet_task_id,definition.name
    """))).mappings().all()
    snapshots = (await session.execute(text("""
      SELECT snapshot.id,taxonomy.version taxonomy_version,snapshot.snapshot_version,
             snapshot.provider_name,snapshot.model_name,snapshot.model_version,
             snapshot.benchmark_method,snapshot.benchmark_method_version,
             snapshot.observed_at,snapshot.review_state,snapshot.expected_capability_count,
             snapshot.is_test_fixture,count(score.id) scores,snapshot.evidence,snapshot.provenance
      FROM ai_capability_benchmark_snapshots snapshot
      JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=snapshot.taxonomy_version_id
      LEFT JOIN ai_capability_benchmark_scores score ON score.snapshot_id=snapshot.id
      GROUP BY snapshot.id,taxonomy.version ORDER BY snapshot.observed_at DESC
    """))).mappings().all()
    assessments = (await session.execute(text("""
      SELECT assessment.id,assessment.onet_task_id,task.occupation_code,
             left(task.statement,180) task_statement,taxonomy.version taxonomy_version,
             assessment.assessment_version,assessment.ai_capability_fit::float,
             assessment.automation_feasibility::float,assessment.augmentation_potential::float,
             assessment.confidence::float,assessment.assessment_method,
             assessment.assessment_method_version,assessment.review_state,
             assessment.is_test_fixture,assessment.input_versions
      FROM task_ai_enrichment_assessments assessment
      JOIN onet_tasks task ON task.task_id=assessment.onet_task_id
      JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=assessment.taxonomy_version_id
      ORDER BY assessment.created_at DESC LIMIT 100
    """))).mappings().all()
    rubrics = (await session.execute(text("""
      SELECT rubric.id,rubric.version,rubric.name,rubric.description,rubric.status,
             capability.version capability_taxonomy_version,
             environment.version environment_taxonomy_version,
             rubric.minimum_meaningful_weight::float,
             rubric.dominant_weight_threshold::float,
             rubric.maximum_capabilities_per_task,
             rubric.minimum_meaningful_requirement_level::float,
             rubric.minimum_meaningful_constraint_level::float,
             rubric.ambiguity_confidence_ceiling::float,
             rubric.normalization_tolerance::float,rubric.documentation_path,
             rubric.decision_rules,rubric.provenance,rubric.created_at
      FROM task_mapping_rubric_versions rubric
      JOIN ai_capability_taxonomy_versions capability ON capability.id=rubric.capability_taxonomy_version_id
      JOIN task_environment_taxonomy_versions environment ON environment.id=rubric.environment_taxonomy_version_id
      ORDER BY rubric.created_at DESC
    """))).mappings().all()
    capability_anchors = (await session.execute(text("""
      SELECT definition.slug,definition.name,
             jsonb_agg(jsonb_build_object(
               'value',anchor.anchor_value,'label',anchor.anchor_label,
               'description',anchor.description,'evidenceRule',anchor.observable_evidence_rule
             ) ORDER BY anchor.anchor_value) anchors
      FROM capability_requirement_scale_anchors anchor
      JOIN ai_capability_definitions definition ON definition.id=anchor.capability_definition_id
      JOIN task_mapping_rubric_versions rubric ON rubric.id=anchor.rubric_version_id
      WHERE rubric.version='jvs-task-capability-rubric-v1'
      GROUP BY definition.id ORDER BY definition.capability_category,definition.name
    """))).mappings().all()
    constraint_anchors = (await session.execute(text("""
      SELECT definition.slug,definition.name,
             jsonb_agg(jsonb_build_object(
               'value',anchor.anchor_value,'label',anchor.anchor_label,
               'description',anchor.description,'evidenceRule',anchor.observable_evidence_rule
             ) ORDER BY anchor.anchor_value) anchors
      FROM environment_constraint_scale_anchors anchor
      JOIN task_environment_constraint_definitions definition ON definition.id=anchor.constraint_definition_id
      JOIN task_mapping_rubric_versions rubric ON rubric.id=anchor.rubric_version_id
      WHERE rubric.version='jvs-task-capability-rubric-v1'
      GROUP BY definition.id ORDER BY definition.constraint_category,definition.name
    """))).mappings().all()
    confidence_states = (await session.execute(text("""
      SELECT state.code,state.name,state.minimum_confidence::float,state.maximum_confidence::float,
             state.definition,state.review_rule
      FROM mapping_confidence_states state
      JOIN task_mapping_rubric_versions rubric ON rubric.id=state.rubric_version_id
      WHERE rubric.version='jvs-task-capability-rubric-v1'
      ORDER BY state.minimum_confidence
    """))).mappings().all()
    gold_datasets = (await session.execute(text("""
      SELECT dataset.id,dataset.dataset_version,dataset.name,dataset.description,dataset.status,
             dataset.expected_task_count,dataset.is_test_fixture,dataset.created_by,
             dataset.reviewed_by,dataset.reviewed_at,dataset.provenance,
             count(item.id) items,
             count(item.id) FILTER (WHERE item.disposition='mappable') mappable_items,
             count(item.id) FILTER (WHERE item.disposition='insufficient_description') insufficient_items,
             count(item.id) FILTER (WHERE item.disposition='ambiguous_scope') ambiguous_items
      FROM task_capability_gold_datasets dataset
      LEFT JOIN task_capability_gold_items item ON item.gold_dataset_id=dataset.id
      GROUP BY dataset.id ORDER BY dataset.created_at DESC
    """))).mappings().all()
    gold_items = (await session.execute(text("""
      SELECT item.id,item.onet_task_id,task.occupation_code,task.statement task_statement,
             item.disposition,item.disposition_rationale,item.task_statement_hash,
             item.reviewer_provenance,item.reviewed_at,
             capability_summary.capability_requirements,
             constraint_summary.environment_constraints,
             capability_summary.capability_weight_total
      FROM task_capability_gold_items item
      JOIN onet_tasks task ON task.task_id=item.onet_task_id
      JOIN task_capability_gold_datasets dataset ON dataset.id=item.gold_dataset_id
      JOIN LATERAL (
        SELECT count(*) capability_requirements,coalesce(round(sum(weight),7),0) capability_weight_total
        FROM gold_task_capability_requirements WHERE gold_item_id=item.id
      ) capability_summary ON true
      JOIN LATERAL (
        SELECT count(*) environment_constraints
        FROM gold_task_environment_constraints WHERE gold_item_id=item.id
      ) constraint_summary ON true
      WHERE dataset.dataset_version='gold-v1-representative-test'
      ORDER BY item.onet_task_id
    """))).mappings().all()
    gold_comparisons = (await session.execute(text("""
      SELECT candidate.id candidate_mapping_set_id,item.onet_task_id,
             compare_task_mapping_to_gold(candidate.id,dataset.id) report
      FROM task_capability_gold_datasets dataset
      JOIN task_capability_gold_items item ON item.gold_dataset_id=dataset.id AND item.disposition='mappable'
      JOIN LATERAL (
        SELECT mapping_set.id
        FROM task_capability_mapping_sets mapping_set
        WHERE mapping_set.onet_task_id=item.onet_task_id AND mapping_set.is_test_fixture
        ORDER BY mapping_set.created_at DESC,mapping_set.id DESC LIMIT 1
      ) candidate ON true
      WHERE dataset.dataset_version='gold-v1-representative-test'
      ORDER BY item.onet_task_id
    """))).mappings().all()
    rubric_validation = (await session.execute(text(
        "SELECT * FROM task_mapping_rubric_validation"
    ))).mappings().all()
    mapper_benchmarks = (await session.execute(text("""
      SELECT * FROM task_mapper_benchmark_validation ORDER BY gold_dataset_id DESC
    """))).mappings().all()
    candidate_runs = (await session.execute(text("""
      SELECT candidate.id,candidate.run_version,candidate.mapper_name,candidate.mapper_version,
             candidate.mapper_kind,candidate.status,candidate.prohibited_input_attestation,
             candidate.allowed_input_manifest,candidate.configuration,candidate.input_task_count,
             candidate.output_task_count,candidate.provenance,candidate.created_at,
             validation.mappable_tasks,validation.ambiguous_tasks,validation.insufficient_tasks,
             validation.invalid_tasks,
             verification.id verification_run_id,verification.verification_version,
             verification.status verification_status,verification.summary verification_summary,
             evaluation.id evaluation_run_id,evaluation.evaluation_version,evaluation.status evaluation_status,
             evaluation.metrics evaluation_metrics,evaluation.gate_results
      FROM task_mapping_candidate_runs candidate
      CROSS JOIN LATERAL candidate_run_validation(candidate.id) validation
      LEFT JOIN LATERAL (
        SELECT * FROM task_mapping_verification_runs
        WHERE candidate_run_id=candidate.id ORDER BY created_at DESC,id DESC LIMIT 1
      ) verification ON true
      LEFT JOIN LATERAL (
        SELECT * FROM task_mapper_evaluation_runs
        WHERE candidate_run_id=candidate.id ORDER BY created_at DESC,id DESC LIMIT 1
      ) evaluation ON true
      ORDER BY candidate.created_at DESC
    """))).mappings().all()
    acceptance_gates = (await session.execute(text("""
      SELECT id,gate_version,name,status,minimum_human_reviewed_tasks,minimum_occupations,
             minimum_capability_set_agreement::float,maximum_mean_weight_deviation::float,
             maximum_mean_requirement_level_deviation::float,maximum_mean_constraint_deviation::float,
             minimum_confidence_agreement::float,maximum_extra_dimension_rate::float,
             maximum_missing_dimension_rate::float,maximum_false_inference_rate::float,
             require_independent_verification,provenance,created_at
      FROM mapper_acceptance_gate_configs ORDER BY created_at DESC
    """))).mappings().all()
    mvp_evidence_policies = (await session.execute(text("""
      SELECT validation.*,policy.name,policy.description,
             policy.minimum_rationale_coverage::float,
             policy.minimum_capability_dimensions,policy.maximum_capability_dimensions,
             policy.allow_ambiguous_scope,policy.allow_insufficient_description,
             policy.require_model_provenance,policy.require_prompt_provenance,
             policy.require_independent_structural_validation,
             policy.allowed_scoring_review_states,policy.provenance,policy.created_at
      FROM mvp_mapping_policy_validation validation
      JOIN task_mapping_evidence_policy_versions policy ON policy.id=validation.policy_id
      ORDER BY policy.created_at DESC
    """))).mappings().all()
    frontier_indexes = (await session.execute(text("""
      SELECT validation.*,index_version.name,index_version.description,
             taxonomy.version taxonomy_version,index_version.methodology_version,
             index_version.score_scale_min::float,index_version.score_scale_max::float,
             index_version.as_of_date,index_version.provenance,index_version.created_at
      FROM frontier_ai_capability_index_validation validation
      JOIN frontier_ai_capability_index_versions index_version ON index_version.id=validation.index_version_id
      JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=index_version.taxonomy_version_id
      ORDER BY index_version.created_at DESC
    """))).mappings().all()
    frontier_tracks = (await session.execute(text("""
      SELECT track.id,track.index_version_id,index_version.index_version,track.track_code,
             track.name,track.description,track.status,track.expected_capability_count,
             track.assessment_date,track.methodology_notes,track.provenance,track.created_at,
             count(DISTINCT entry.id) capability_values,
             count(DISTINCT evidence.id) evidence_records
      FROM frontier_ai_capability_index_tracks track
      JOIN frontier_ai_capability_index_versions index_version ON index_version.id=track.index_version_id
      LEFT JOIN frontier_ai_capability_index_entries entry ON entry.track_id=track.id
      LEFT JOIN frontier_ai_capability_evidence_records evidence ON evidence.track_id=track.id
      GROUP BY track.id,index_version.index_version
      ORDER BY track.index_version_id DESC,track.track_code
    """))).mappings().all()
    frontier_entries = (await session.execute(text("""
      SELECT entry.id,index_version.index_version,track.track_code,track.name track_name,
             definition.slug capability_slug,definition.name capability_name,
             definition.capability_category,entry.capability_score::float,
             entry.confidence::float,entry.assessment_status,entry.assessment_date,
             entry.source_type,entry.provider_name,entry.model_name,entry.model_version,
             entry.observed_at,entry.rationale,entry.benchmark_evidence,entry.provenance,
             coalesce(jsonb_agg(jsonb_build_object(
               'id',evidence.id,'sourceTier',evidence.source_tier,
               'sourceType',evidence.source_type,'providerName',evidence.provider_name,
               'modelName',evidence.model_name,'modelVersion',evidence.model_version,
               'evidenceDate',evidence.evidence_date,'benchmarkName',evidence.benchmark_name,
               'reportedResult',evidence.reported_result,'sourceReference',evidence.source_reference,
               'rationale',evidence.rationale,'confidence',evidence.confidence::float,
               'evidencePayload',evidence.evidence_payload,'provenance',evidence.provenance
             ) ORDER BY evidence.evidence_date DESC,evidence.id DESC)
             FILTER (WHERE evidence.id IS NOT NULL),'[]'::jsonb) evidence_records
      FROM frontier_ai_capability_index_entries entry
      JOIN frontier_ai_capability_index_versions index_version ON index_version.id=entry.index_version_id
      JOIN frontier_ai_capability_index_tracks track ON track.id=entry.track_id
      JOIN ai_capability_definitions definition ON definition.id=entry.capability_definition_id
      LEFT JOIN frontier_ai_capability_evidence_records evidence
        ON evidence.index_version_id=entry.index_version_id AND evidence.track_id=entry.track_id
       AND evidence.capability_definition_id=entry.capability_definition_id
      GROUP BY entry.id,index_version.index_version,track.track_code,track.name,
               definition.slug,definition.name,definition.capability_category
      ORDER BY track.track_code,entry.capability_score DESC,definition.name
    """))).mappings().all()
    validation = (await session.execute(text(
        "SELECT * FROM ai_enrichment_validation"
    ))).mappings().one()
    return {
        "taxonomies": [dict(row) for row in taxonomies],
        "capabilities": [dict(row) for row in capabilities],
        "mapping_sets": [dict(row) for row in mapping_sets],
        "environment_taxonomies": [dict(row) for row in environment_taxonomies],
        "constraints": [dict(row) for row in constraints],
        "constraint_mappings": [dict(row) for row in constraint_mappings],
        "snapshots": [dict(row) for row in snapshots],
        "assessments": [dict(row) for row in assessments],
        "rubrics": [dict(row) for row in rubrics],
        "capability_anchors": [dict(row) for row in capability_anchors],
        "constraint_anchors": [dict(row) for row in constraint_anchors],
        "confidence_states": [dict(row) for row in confidence_states],
        "gold_datasets": [dict(row) for row in gold_datasets],
        "gold_items": [dict(row) for row in gold_items],
        "gold_comparisons": [dict(row) for row in gold_comparisons],
        "rubric_validation": [dict(row) for row in rubric_validation],
        "mapper_benchmarks": [dict(row) for row in mapper_benchmarks],
        "candidate_runs": [dict(row) for row in candidate_runs],
        "acceptance_gates": [dict(row) for row in acceptance_gates],
        "mvp_evidence_policies": [dict(row) for row in mvp_evidence_policies],
        "frontier_indexes": [dict(row) for row in frontier_indexes],
        "frontier_tracks": [dict(row) for row in frontier_tracks],
        "frontier_entries": [dict(row) for row in frontier_entries],
        "validation": dict(validation),
    }


@router.get("/jobs/{slug}/derivation", response_model=ScoreDerivation, response_model_by_alias=True)
async def score_derivation(slug: str, session: AsyncSession = Depends(get_session)) -> ScoreDerivation:
    row = (await session.execute(text("""
      SELECT score.id score_id, occupation.slug occupation_slug, occupation.title occupation_title,
             score.ai_exposure::float ai_exposure, score.replacement_risk::float replacement_risk,
             score.confidence, score.trend, score.task_exposure::float task_exposure,
             score.ai_capability_proximity::float ai_capability_proximity,
             model.version model_version, score.calculated_at,
             derivation.calculated_total::float calculated_total,
             derivation.input_versions, derivation.factors, derivation.task_contributions
      FROM occupations occupation
      JOIN LATERAL (
        SELECT * FROM occupation_scores WHERE occupation_id=occupation.id
        ORDER BY calculated_at DESC, id DESC LIMIT 1
      ) score ON true
      JOIN scoring_model_versions model ON model.id=score.model_version_id
      JOIN score_derivations derivation ON derivation.score_id=score.id
      WHERE occupation.slug=:slug
    """), {"slug": slug})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Score derivation not found")
    data = dict(row)
    data["factors"] = [ScoreFactor(**factor) for factor in data["factors"]]
    data["task_contributions"] = [TaskContribution(**task) for task in data["task_contributions"]]
    return ScoreDerivation(**data)


# ---------------------------------------------------------------------------
# Production score inspector — read-only.
#
# The production store has no other window onto it. Everything below is SELECT-only: this
# inspector can neither promote, approve nor activate. Approval eligibility is *reported*
# here and decided elsewhere.
# ---------------------------------------------------------------------------
@router.get("/production-scores")
async def production_scores(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    runs = (await session.execute(text("""
      SELECT run.id, run.run_key, run.source_kind, run.status, run.is_test_fixture,
             run.promotion_policy_version, run.occupation_count,
             model.version AS scoring_model_version, model.methodology_family,
             run.created_at, run.completed_at, run.rolled_back_at, run.rolled_back_reason,
             run.input_version_bundle, run.selection_policy, run.reconciliation,
             source_run.run_version AS source_calculation_run,
             (SELECT count(*) FROM production_occupation_score_snapshots snapshot
               WHERE snapshot.promotion_run_id = run.id) AS snapshot_count
      FROM production_promotion_runs run
      JOIN scoring_model_versions model ON model.id = run.scoring_model_version_id
      LEFT JOIN phase5_calculation_runs source_run ON source_run.id = run.source_calculation_run_id
      ORDER BY run.created_at DESC, run.id DESC
    """))).mappings().all()

    # Only the current snapshot per identity: an inspector that lists superseded snapshots
    # alongside live ones invites reading the wrong number.
    snapshots = (await session.execute(text("""
      SELECT score.id AS snapshot_id, score.identity_id, score.run_key,
             occupation.slug, coalesce(occupation.title, publication.canonical_public_title) AS title,
             score.ai_exposure::float ai_exposure, score.replacement_risk::float replacement_risk,
             score.confidence::float confidence,
             score.weighted_task_coverage::float weighted_task_coverage,
             score.scoring_eligibility, score.publishable,
             score.coverage_gate_status, score.confidence_gate_status,
             jsonb_array_length(score.warnings) AS warning_count,
             score.calculated_at, score.promoted_at,
             publication.activation_status,
             publication.approved_score_snapshot_id,
             consistency.consistency_state,
             -- Approval eligibility is reported, never applied. A snapshot is eligible when
             -- it is publishable, currently live, and has an editorial page to attach to.
             (score.publishable
              AND occupation.id IS NOT NULL
              AND coalesce(consistency.consistency_state, 'no_approved_snapshot') <> 'approved_snapshot_withdrawn'
             ) AS approval_eligible,
             score.occupation_id IS NULL AS missing_editorial_record
      FROM current_production_occupation_scores score
      LEFT JOIN occupations occupation ON occupation.id = score.occupation_id
      LEFT JOIN occupation_publications publication
             ON publication.identity_id = score.identity_id
            AND publication.locale = 'en' AND publication.source_geography = 'US'
      LEFT JOIN publication_snapshot_consistency consistency
             ON consistency.identity_id = score.identity_id
            AND consistency.locale = 'en' AND consistency.source_geography = 'US'
      ORDER BY score.replacement_risk DESC NULLS LAST, score.identity_id
      LIMIT 1000
    """))).mappings().all()

    consistency_counts = (await session.execute(text("""
      SELECT consistency_state, count(*) AS total
      FROM publication_snapshot_consistency
      GROUP BY consistency_state ORDER BY consistency_state
    """))).mappings().all()

    totals = (await session.execute(text("""
      SELECT (SELECT count(*) FROM production_promotion_runs) promotion_runs,
             (SELECT count(*) FROM production_promotion_runs WHERE status='completed') completed_runs,
             (SELECT count(*) FROM production_occupation_score_snapshots) snapshots,
             (SELECT count(*) FROM current_production_occupation_scores) current_snapshots,
             (SELECT count(*) FROM current_production_occupation_scores WHERE publishable) publishable,
             (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_occupations,
             (SELECT count(*) FROM production_occupation_score_snapshots
               WHERE source_candidate_score_id IS NOT NULL) promoted_from_candidates,
             (SELECT version FROM scoring_model_versions WHERE is_active) active_scoring_model
    """))).mappings().one()

    triage = (await session.execute(text("""
      SELECT run.id, run.run_key, run.policy_version, run.candidates_assessed,
             run.launch_cohort_size, run.excluded_count, run.cohort_selection,
             run.severity_totals, run.exclusion_reasons, run.created_at
      FROM phase6_launch_triage_runs run
      ORDER BY run.created_at DESC, run.id DESC LIMIT 5
    """))).mappings().all()

    return {
        "totals": dict(totals),
        "promotion_runs": [dict(row) for row in runs],
        "current_snapshots": [dict(row) for row in snapshots],
        "consistency_counts": [dict(row) for row in consistency_counts],
        "triage_runs": [dict(row) for row in triage],
    }


@router.get("/production-scores/{snapshot_id}")
async def production_score_detail(
    snapshot_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    snapshot = (await session.execute(text("""
      SELECT snapshot.*, run.run_key, run.status AS promotion_run_status,
             run.source_kind, run.is_test_fixture, run.promotion_policy_version,
             model.version AS scoring_model_version, model.methodology_family,
             occupation.slug, occupation.title,
             publication.activation_status, publication.approved_score_snapshot_id,
             consistency.consistency_state
      FROM production_occupation_score_snapshots snapshot
      JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
      JOIN scoring_model_versions model ON model.id = snapshot.scoring_model_version_id
      LEFT JOIN occupations occupation ON occupation.id = snapshot.occupation_id
      LEFT JOIN occupation_publications publication
             ON publication.identity_id = snapshot.identity_id
            AND publication.locale='en' AND publication.source_geography='US'
      LEFT JOIN publication_snapshot_consistency consistency
             ON consistency.identity_id = snapshot.identity_id
            AND consistency.locale='en' AND consistency.source_geography='US'
      WHERE snapshot.id = :snapshot_id
    """), {"snapshot_id": snapshot_id})).mappings().first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Production score snapshot not found")

    factors = (await session.execute(text("""
      SELECT factor_key, factor_label, value::float value, source_proxy_value::float source_proxy_value,
             transformation, weight::float weight, weighted_contribution::float weighted_contribution,
             is_provisional_proxy, proxy_model_version, placeholder, display_order
      FROM production_score_factor_contributions
      WHERE snapshot_id = :snapshot_id ORDER BY display_order
    """), {"snapshot_id": snapshot_id})).mappings().all()

    tasks = (await session.execute(text("""
      SELECT onet_task_id, onet_soc_code, task_statement,
             ai_capability_fit::float ai_capability_fit,
             automation_feasibility::float automation_feasibility,
             augmentation_potential::float augmentation_potential,
             task_ai_exposure::float task_ai_exposure, task_confidence::float task_confidence,
             source_importance::float source_importance, source_frequency::float source_frequency,
             normalized_covered_weight::float normalized_covered_weight,
             exposure_contribution::float exposure_contribution, weighting_eligible
      FROM production_score_task_contributions
      WHERE snapshot_id = :snapshot_id
      ORDER BY exposure_contribution DESC, onet_task_id
    """), {"snapshot_id": snapshot_id})).mappings().all()

    # The candidate this snapshot was promoted from, so the two can be compared directly.
    # NULL for an architecture fixture, which is exactly what should be visible.
    candidate = None
    if snapshot["source_candidate_score_id"]:
        candidate = (await session.execute(text("""
          SELECT candidate_score.id, candidate.occupation_code, candidate.title_snapshot AS title,
                 candidate_score.ai_exposure::float ai_exposure,
                 candidate_score.replacement_risk::float replacement_risk,
                 candidate_score.confidence::float confidence,
                 candidate_score.weighted_task_coverage::float weighted_task_coverage,
                 candidate_score.candidate_status, candidate_score.coverage_gate_status,
                 candidate_score.confidence_gate_status, candidate_score.warnings,
                 candidate_score.provisional_sensitivity, candidate_score.input_hash,
                 run.run_version AS calculation_run
          FROM phase5_occupation_scores candidate_score
          JOIN phase5_candidate_occupations candidate
            ON candidate.id = candidate_score.candidate_occupation_id
          JOIN phase5_calculation_runs run ON run.id = candidate_score.calculation_run_id
          WHERE candidate_score.id = :candidate_id
        """), {"candidate_id": snapshot["source_candidate_score_id"]})).mappings().first()

    data = dict(snapshot)
    reconciliation = {
        "factorContributionTotal": round(sum(float(item["weighted_contribution"]) for item in factors), 4),
        "replacementRisk": float(data["replacement_risk"]),
        "taskContributionTotal": round(sum(float(item["exposure_contribution"]) for item in tasks), 4),
        "aiExposure": float(data["ai_exposure"]),
    }
    reconciliation["factorsReconcile"] = (
        abs(reconciliation["factorContributionTotal"] - reconciliation["replacementRisk"]) <= 0.01)
    reconciliation["tasksReconcile"] = (
        abs(reconciliation["taskContributionTotal"] - reconciliation["aiExposure"]) <= 0.01)

    return {
        "snapshot": data,
        "candidate": dict(candidate) if candidate else None,
        "factor_contributions": [dict(row) for row in factors],
        "task_contributions": [dict(row) for row in tasks],
        "recomputed_reconciliation": reconciliation,
        "provisional_weight_share": round(
            sum(float(item["weight"]) for item in factors if item["is_provisional_proxy"]) * 100, 4),
    }
