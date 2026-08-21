BEGIN;

INSERT INTO data_sources (name,source_url,version,metadata)
VALUES (
  'JobsVsAI Phase 4D direct structural proxy reconstruction',
  'internal://jobsvsai/phase4d-direct-structural-proxies',
  'phase4d-2026-Q3-v1',
  '{"source":"O*NET 30.3","cohort":"phase4c-2026q3-v1","public":false,"production_scoring":false,"external_ai_calls":false,"archetype_scoring":false}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE phase4d_proxy_model_versions (
  id BIGSERIAL PRIMARY KEY,
  model_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','pilot','retired')),
  source_version TEXT NOT NULL,
  reconstructed_families JSONB NOT NULL,
  formula_parameters JSONB NOT NULL,
  missing_data_policy JSONB NOT NULL,
  implementation_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(reconstructed_families)='array'),
  CHECK (jsonb_array_length(reconstructed_families)=4),
  CHECK (jsonb_typeof(formula_parameters)='object'),
  CHECK (jsonb_typeof(missing_data_policy)='object')
);

CREATE TABLE phase4d_proxy_snapshots (
  id BIGSERIAL PRIMARY KEY,
  proxy_model_version_id BIGINT NOT NULL REFERENCES phase4d_proxy_model_versions(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  physical_presence NUMERIC(7,4) NOT NULL CHECK (physical_presence BETWEEN 0 AND 100),
  environment_variability NUMERIC(7,4) NOT NULL CHECK (environment_variability BETWEEN 0 AND 100),
  accountability NUMERIC(7,4) NOT NULL CHECK (accountability BETWEEN 0 AND 100),
  consequence_severity NUMERIC(7,4) NOT NULL CHECK (consequence_severity BETWEEN 0 AND 100),
  proxy_confidence NUMERIC(7,4) NOT NULL CHECK (proxy_confidence BETWEEN 0 AND 100),
  family_values JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (proxy_model_version_id,validation_occupation_id),
  CHECK (jsonb_typeof(family_values)='object'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4d_calculation_runs (
  id BIGSERIAL PRIMARY KEY,
  run_version TEXT NOT NULL UNIQUE,
  run_kind TEXT NOT NULL CHECK (run_kind IN ('direct_proxy_recompute','deterministic_replay')),
  proxy_model_version_id BIGINT NOT NULL REFERENCES phase4d_proxy_model_versions(id),
  baseline_phase4c_run_id BIGINT NOT NULL REFERENCES phase4c_calculation_runs(id),
  previous_run_id BIGINT REFERENCES phase4d_calculation_runs(id),
  occupation_count INTEGER NOT NULL CHECK (occupation_count=25),
  task_assessment_count INTEGER NOT NULL CHECK (task_assessment_count>=0),
  external_ai_calls INTEGER NOT NULL DEFAULT 0 CHECK (external_ai_calls=0),
  regenerated_mapping_count INTEGER NOT NULL DEFAULT 0 CHECK (regenerated_mapping_count=0),
  archetype_scoring_enabled BOOLEAN NOT NULL DEFAULT false CHECK (archetype_scoring_enabled=false),
  production_score_writes INTEGER NOT NULL DEFAULT 0 CHECK (production_score_writes=0),
  dependency_hash CHAR(64) NOT NULL,
  reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('passed','failed')),
  replay_matches_previous BOOLEAN,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE phase4d_task_assessments (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4d_calculation_runs(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  ai_capability_fit NUMERIC(7,4) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(7,4) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(7,4) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  task_ai_exposure NUMERIC(7,4) NOT NULL CHECK (task_ai_exposure BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  exact_inputs JSONB NOT NULL,
  constraint_contributions JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,ai_task_mapping_id),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(constraint_contributions)='array'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4d_occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4d_calculation_runs(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  baseline_phase4c_score_id BIGINT NOT NULL REFERENCES phase4c_occupation_scores(id),
  ai_exposure NUMERIC(7,4) NOT NULL CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(7,4) NOT NULL CHECK (replacement_risk BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  weighted_task_coverage NUMERIC(7,4) NOT NULL CHECK (weighted_task_coverage BETWEEN 0 AND 100),
  coverage_gate_status TEXT NOT NULL CHECK (coverage_gate_status IN ('passed','below_threshold')),
  scale_eligible BOOLEAN NOT NULL,
  ai_exposure_delta NUMERIC(8,4) NOT NULL CHECK (ai_exposure_delta BETWEEN -100 AND 100),
  replacement_risk_delta NUMERIC(8,4) NOT NULL CHECK (replacement_risk_delta BETWEEN -100 AND 100),
  confidence_delta NUMERIC(8,4) NOT NULL CHECK (confidence_delta BETWEEN -100 AND 100),
  factor_contributions JSONB NOT NULL,
  task_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,validation_occupation_id),
  CHECK (jsonb_typeof(factor_contributions)='array'),
  CHECK (jsonb_typeof(task_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4d_proxy_validation_results (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4d_calculation_runs(id),
  validation_type TEXT NOT NULL CHECK (validation_type IN ('pairwise','absolute_band')),
  validation_key TEXT NOT NULL,
  proxy_family TEXT NOT NULL,
  baseline_outcome TEXT NOT NULL CHECK (baseline_outcome IN ('pass','warning','failure')),
  phase4d_outcome TEXT NOT NULL CHECK (phase4d_outcome IN ('pass','warning','failure')),
  baseline_value JSONB NOT NULL,
  phase4d_value JSONB NOT NULL,
  improved BOOLEAN NOT NULL,
  regressed BOOLEAN NOT NULL,
  finding TEXT NOT NULL,
  reconciliation JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,validation_type,validation_key),
  CHECK (NOT (improved AND regressed)),
  CHECK (jsonb_typeof(baseline_value)='object'),
  CHECK (jsonb_typeof(phase4d_value)='object'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TRIGGER phase4d_proxy_models_append_only BEFORE UPDATE OR DELETE ON phase4d_proxy_model_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4d_proxy_snapshots_append_only BEFORE UPDATE OR DELETE ON phase4d_proxy_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4d_runs_append_only BEFORE UPDATE OR DELETE ON phase4d_calculation_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4d_task_assessments_append_only BEFORE UPDATE OR DELETE ON phase4d_task_assessments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4d_occupation_scores_append_only BEFORE UPDATE OR DELETE ON phase4d_occupation_scores FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4d_proxy_validation_append_only BEFORE UPDATE OR DELETE ON phase4d_proxy_validation_results FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
