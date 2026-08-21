BEGIN;

INSERT INTO data_sources (name,source_url,version,metadata)
VALUES (
  'JobsVsAI Phase 5 bounded corpus scoring',
  'internal://jobsvsai/phase5-bounded-corpus',
  'phase5-2026-Q3-v1',
  '{"source":"O*NET 30.3","public":false,"production_scoring":false,"bounded":true,"coverage_gate":70,"archetype_scoring":false}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE phase5_candidate_namespaces (
  id BIGSERIAL PRIMARY KEY,
  namespace_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('candidate','retired')),
  source_version TEXT NOT NULL,
  scoring_ready_policy_version TEXT NOT NULL,
  mapping_scope_version TEXT NOT NULL,
  occupation_population_count INTEGER NOT NULL CHECK (occupation_population_count > 0),
  occupation_population_hash CHAR(64) NOT NULL,
  coverage_threshold NUMERIC(6,3) NOT NULL CHECK (coverage_threshold BETWEEN 0 AND 100),
  public_activation_allowed BOOLEAN NOT NULL DEFAULT false CHECK (public_activation_allowed=false),
  production_score_writes_allowed BOOLEAN NOT NULL DEFAULT false CHECK (production_score_writes_allowed=false),
  archetype_scoring_enabled BOOLEAN NOT NULL DEFAULT false CHECK (archetype_scoring_enabled=false),
  exact_policy JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(exact_policy)='object')
);

CREATE TABLE phase5_candidate_occupations (
  id BIGSERIAL PRIMARY KEY,
  namespace_id BIGINT NOT NULL REFERENCES phase5_candidate_namespaces(id),
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code),
  identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id),
  cohort_order INTEGER NOT NULL CHECK (cohort_order > 0),
  title_snapshot TEXT NOT NULL,
  soc_major_group TEXT NOT NULL,
  promotion_profile_snapshot JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (namespace_id,occupation_code),
  UNIQUE (namespace_id,cohort_order),
  CHECK (jsonb_typeof(promotion_profile_snapshot)='object')
);

CREATE TABLE phase5_task_mapping_scope (
  id BIGSERIAL PRIMARY KEY,
  namespace_id BIGINT NOT NULL REFERENCES phase5_candidate_namespaces(id),
  candidate_occupation_id BIGINT NOT NULL REFERENCES phase5_candidate_occupations(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  scope_decision TEXT NOT NULL CHECK (scope_decision IN (
    'reused_exact_task','reused_task_hash','generated','unmapped_insufficient_evidence',
    'unmapped_after_gate','source_weight_ineligible'
  )),
  ai_task_mapping_id BIGINT REFERENCES ai_generated_task_mappings(id),
  source_mapping_task_id BIGINT REFERENCES onet_tasks(task_id),
  mapping_run_id BIGINT REFERENCES ai_generated_task_mapping_runs(id),
  source_weight NUMERIC(14,8),
  selection_rank INTEGER,
  selection_reason TEXT NOT NULL,
  task_statement_hash CHAR(32) NOT NULL,
  dependency_reuse_key CHAR(64) NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (namespace_id,onet_task_id),
  CHECK (jsonb_typeof(evidence)='array'),
  CHECK ((scope_decision IN ('reused_exact_task','reused_task_hash','generated') AND ai_task_mapping_id IS NOT NULL)
      OR (scope_decision NOT IN ('reused_exact_task','reused_task_hash','generated') AND ai_task_mapping_id IS NULL))
);

CREATE TABLE phase5_proxy_snapshots (
  id BIGSERIAL PRIMARY KEY,
  namespace_id BIGINT NOT NULL REFERENCES phase5_candidate_namespaces(id),
  candidate_occupation_id BIGINT NOT NULL REFERENCES phase5_candidate_occupations(id),
  phase4d_proxy_model_version_id BIGINT NOT NULL REFERENCES phase4d_proxy_model_versions(id),
  base_proxy_model_version_id BIGINT NOT NULL REFERENCES phase4b_proxy_model_versions(id),
  physical_presence NUMERIC(7,4) NOT NULL CHECK (physical_presence BETWEEN 0 AND 100),
  environment_variability NUMERIC(7,4) NOT NULL CHECK (environment_variability BETWEEN 0 AND 100),
  accountability NUMERIC(7,4) NOT NULL CHECK (accountability BETWEEN 0 AND 100),
  consequence_severity NUMERIC(7,4) NOT NULL CHECK (consequence_severity BETWEEN 0 AND 100),
  human_dependency NUMERIC(7,4) NOT NULL CHECK (human_dependency BETWEEN 0 AND 100),
  regulation NUMERIC(7,4) NOT NULL CHECK (regulation BETWEEN 0 AND 100),
  adoption_pressure NUMERIC(7,4) NOT NULL CHECK (adoption_pressure BETWEEN 0 AND 100),
  labour_market_resilience NUMERIC(7,4) NOT NULL CHECK (labour_market_resilience BETWEEN 0 AND 100),
  proxy_confidence NUMERIC(7,4) NOT NULL CHECK (proxy_confidence BETWEEN 0 AND 100),
  family_values JSONB NOT NULL,
  component_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  provisional_flags JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (namespace_id,candidate_occupation_id),
  CHECK (jsonb_typeof(family_values)='object'),
  CHECK (jsonb_typeof(component_contributions)='object'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object'),
  CHECK (jsonb_typeof(provisional_flags)='object')
);

CREATE TABLE phase5_anomaly_policy_versions (
  id BIGSERIAL PRIMARY KEY,
  policy_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('candidate','retired')),
  thresholds JSONB NOT NULL,
  checks JSONB NOT NULL,
  implementation_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(thresholds)='object'),
  CHECK (jsonb_typeof(checks)='array')
);

CREATE TABLE phase5_calculation_runs (
  id BIGSERIAL PRIMARY KEY,
  namespace_id BIGINT NOT NULL REFERENCES phase5_candidate_namespaces(id),
  run_version TEXT NOT NULL UNIQUE,
  run_kind TEXT NOT NULL CHECK (run_kind IN ('bounded_corpus','deterministic_replay')),
  previous_run_id BIGINT REFERENCES phase5_calculation_runs(id),
  anomaly_policy_version_id BIGINT NOT NULL REFERENCES phase5_anomaly_policy_versions(id),
  mapping_run_id BIGINT REFERENCES ai_generated_task_mapping_runs(id),
  capability_fit_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  automation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  augmentation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  occupation_formula_id BIGINT NOT NULL REFERENCES phase4a_occupation_formula_versions(id),
  frontier_track_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_tracks(id),
  attempted_occupation_count INTEGER NOT NULL CHECK (attempted_occupation_count > 0),
  scored_occupation_count INTEGER NOT NULL CHECK (scored_occupation_count >= 0),
  blocked_occupation_count INTEGER NOT NULL CHECK (blocked_occupation_count >= 0),
  task_assessment_count INTEGER NOT NULL CHECK (task_assessment_count >= 0),
  new_mapping_count INTEGER NOT NULL CHECK (new_mapping_count >= 0),
  reused_exact_mapping_count INTEGER NOT NULL CHECK (reused_exact_mapping_count >= 0),
  reused_hash_mapping_count INTEGER NOT NULL CHECK (reused_hash_mapping_count >= 0),
  external_ai_calls INTEGER NOT NULL DEFAULT 0 CHECK (external_ai_calls >= 0),
  estimated_ai_tokens BIGINT NOT NULL DEFAULT 0 CHECK (estimated_ai_tokens >= 0),
  local_compute_milliseconds BIGINT NOT NULL CHECK (local_compute_milliseconds >= 0),
  archetype_scoring_enabled BOOLEAN NOT NULL DEFAULT false CHECK (archetype_scoring_enabled=false),
  production_score_writes INTEGER NOT NULL DEFAULT 0 CHECK (production_score_writes=0),
  public_activations INTEGER NOT NULL DEFAULT 0 CHECK (public_activations=0),
  dependency_hash CHAR(64) NOT NULL,
  reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('passed','failed')),
  replay_matches_previous BOOLEAN,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (scored_occupation_count + blocked_occupation_count = attempted_occupation_count)
);

CREATE TABLE phase5_task_assessments (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase5_calculation_runs(id),
  candidate_occupation_id BIGINT NOT NULL REFERENCES phase5_candidate_occupations(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  ai_capability_fit NUMERIC(7,4) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(7,4) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(7,4) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  task_ai_exposure NUMERIC(7,4) NOT NULL CHECK (task_ai_exposure BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  source_weight NUMERIC(14,8) NOT NULL CHECK (source_weight >= 0),
  capability_contributions JSONB NOT NULL,
  constraint_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,onet_task_id),
  CHECK (jsonb_typeof(capability_contributions)='array'),
  CHECK (jsonb_typeof(constraint_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase5_occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase5_calculation_runs(id),
  candidate_occupation_id BIGINT NOT NULL REFERENCES phase5_candidate_occupations(id),
  proxy_snapshot_id BIGINT NOT NULL REFERENCES phase5_proxy_snapshots(id),
  calculation_status TEXT NOT NULL CHECK (calculation_status IN ('scored','blocked_no_usable_evidence')),
  ai_exposure NUMERIC(7,4) CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(7,4) CHECK (replacement_risk BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  weighted_task_coverage NUMERIC(7,4) NOT NULL CHECK (weighted_task_coverage BETWEEN 0 AND 100),
  source_task_count INTEGER NOT NULL CHECK (source_task_count >= 0),
  eligible_task_count INTEGER NOT NULL CHECK (eligible_task_count >= 0),
  excluded_task_count INTEGER NOT NULL CHECK (excluded_task_count >= 0),
  weighting_eligible_task_count INTEGER NOT NULL CHECK (weighting_eligible_task_count >= 0),
  coverage_gate_status TEXT NOT NULL CHECK (coverage_gate_status IN ('passed','below_threshold','no_usable_evidence')),
  confidence_gate_status TEXT NOT NULL CHECK (confidence_gate_status IN ('passed','below_threshold')),
  candidate_status TEXT NOT NULL CHECK (candidate_status IN ('review_ready','blocked')),
  public_activation_eligible BOOLEAN NOT NULL DEFAULT false CHECK (public_activation_eligible=false),
  top_exposure_tasks JSONB NOT NULL,
  top_automation_constraints JSONB NOT NULL,
  augmentation_heavy_tasks JSONB NOT NULL,
  structural_proxy_inputs JSONB NOT NULL,
  provisional_sensitivity JSONB NOT NULL,
  factor_contributions JSONB NOT NULL,
  task_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  blocking_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,candidate_occupation_id),
  CHECK (jsonb_typeof(top_exposure_tasks)='array'),
  CHECK (jsonb_typeof(top_automation_constraints)='array'),
  CHECK (jsonb_typeof(augmentation_heavy_tasks)='array'),
  CHECK (jsonb_typeof(structural_proxy_inputs)='object'),
  CHECK (jsonb_typeof(provisional_sensitivity)='object'),
  CHECK (jsonb_typeof(factor_contributions)='array'),
  CHECK (jsonb_typeof(task_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(blocking_reasons)='array'),
  CHECK (jsonb_typeof(reconciliation)='object'),
  CHECK ((calculation_status='scored' AND ai_exposure IS NOT NULL AND replacement_risk IS NOT NULL)
      OR (calculation_status='blocked_no_usable_evidence' AND ai_exposure IS NULL AND replacement_risk IS NULL)),
  CHECK (candidate_status='blocked' OR (coverage_gate_status='passed' AND confidence_gate_status='passed'))
);

CREATE TABLE phase5_anomaly_findings (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase5_calculation_runs(id),
  candidate_occupation_id BIGINT REFERENCES phase5_candidate_occupations(id),
  anomaly_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
  metric_values JSONB NOT NULL,
  threshold_values JSONB NOT NULL,
  explanation TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'flagged' CHECK (review_status IN ('flagged','reviewed','dismissed','confirmed')),
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(metric_values)='object'),
  CHECK (jsonb_typeof(threshold_values)='object')
);

CREATE TABLE phase5_corpus_reports (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL UNIQUE REFERENCES phase5_calculation_runs(id),
  report_version TEXT NOT NULL,
  corpus_summary JSONB NOT NULL,
  distributions JSONB NOT NULL,
  percentiles JSONB NOT NULL,
  correlation JSONB NOT NULL,
  extremes JSONB NOT NULL,
  soc_outliers JSONB NOT NULL,
  provisional_impact JSONB NOT NULL,
  anomaly_summary JSONB NOT NULL,
  mapping_reuse_summary JSONB NOT NULL,
  recommended_launch_cohort JSONB NOT NULL,
  exact_reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(corpus_summary)='object'),
  CHECK (jsonb_typeof(distributions)='object'),
  CHECK (jsonb_typeof(percentiles)='object'),
  CHECK (jsonb_typeof(correlation)='object'),
  CHECK (jsonb_typeof(extremes)='object'),
  CHECK (jsonb_typeof(soc_outliers)='array'),
  CHECK (jsonb_typeof(provisional_impact)='object'),
  CHECK (jsonb_typeof(anomaly_summary)='object'),
  CHECK (jsonb_typeof(mapping_reuse_summary)='object'),
  CHECK (jsonb_typeof(recommended_launch_cohort)='object'),
  CHECK (jsonb_typeof(exact_reconciliation)='object')
);

CREATE INDEX phase5_scores_filter_idx ON phase5_occupation_scores
  (calculation_run_id,candidate_status,weighted_task_coverage,confidence,ai_exposure,replacement_risk);
CREATE INDEX phase5_scope_decision_idx ON phase5_task_mapping_scope (namespace_id,scope_decision);
CREATE INDEX phase5_anomalies_filter_idx ON phase5_anomaly_findings (calculation_run_id,severity,anomaly_type);

CREATE TRIGGER phase5_namespaces_append_only BEFORE UPDATE OR DELETE ON phase5_candidate_namespaces FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_occupations_append_only BEFORE UPDATE OR DELETE ON phase5_candidate_occupations FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_mapping_scope_append_only BEFORE UPDATE OR DELETE ON phase5_task_mapping_scope FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_proxy_snapshots_append_only BEFORE UPDATE OR DELETE ON phase5_proxy_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_anomaly_policies_append_only BEFORE UPDATE OR DELETE ON phase5_anomaly_policy_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_runs_append_only BEFORE UPDATE OR DELETE ON phase5_calculation_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_task_assessments_append_only BEFORE UPDATE OR DELETE ON phase5_task_assessments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_occupation_scores_append_only BEFORE UPDATE OR DELETE ON phase5_occupation_scores FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_anomalies_append_only BEFORE UPDATE OR DELETE ON phase5_anomaly_findings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase5_reports_append_only BEFORE UPDATE OR DELETE ON phase5_corpus_reports FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
