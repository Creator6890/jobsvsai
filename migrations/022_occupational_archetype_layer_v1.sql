BEGIN;

INSERT INTO data_sources (name,source_url,version,metadata)
VALUES (
  'JobsVsAI Occupational Archetype Layer v1',
  'internal://jobsvsai/occupational-archetype-v1',
  'draft-2026-Q3-v1',
  '{"source":"O*NET 30.3","layer":"additive_scoring_enrichment","public":false,"production_scoring":false,"external_ai_calls":false}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE scoring_enrichment_feature_flags (
  id BIGSERIAL PRIMARY KEY,
  flag_key TEXT NOT NULL UNIQUE,
  layer_version TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT false,
  production_allowed BOOLEAN NOT NULL DEFAULT false CHECK (production_allowed=false),
  configuration JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(configuration)='object')
);

CREATE TABLE occupational_archetype_model_versions (
  id BIGSERIAL PRIMARY KEY,
  model_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','pilot','retired')),
  source_version TEXT NOT NULL,
  algorithm TEXT NOT NULL,
  cluster_count INTEGER NOT NULL CHECK (cluster_count BETWEEN 20 AND 40),
  random_seed INTEGER NOT NULL,
  feature_schema JSONB NOT NULL,
  normalization_policy JSONB NOT NULL,
  discovery_configuration JSONB NOT NULL,
  feature_flag_id BIGINT NOT NULL REFERENCES scoring_enrichment_feature_flags(id),
  source_input_hash CHAR(64) NOT NULL,
  implementation_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(feature_schema)='object'),
  CHECK (jsonb_typeof(normalization_policy)='object'),
  CHECK (jsonb_typeof(discovery_configuration)='object')
);

CREATE TABLE occupational_archetype_definitions (
  id BIGSERIAL PRIMARY KEY,
  model_version_id BIGINT NOT NULL REFERENCES occupational_archetype_model_versions(id),
  archetype_code TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  interpretation_status TEXT NOT NULL CHECK (interpretation_status IN ('candidate','reviewed','rejected')),
  centroid JSONB NOT NULL,
  top_features JSONB NOT NULL,
  representative_occupations JSONB NOT NULL,
  member_count INTEGER NOT NULL CHECK (member_count>0),
  quality_metrics JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_version_id,archetype_code),
  UNIQUE (model_version_id,name),
  CHECK (jsonb_typeof(centroid)='object'),
  CHECK (jsonb_typeof(top_features)='array'),
  CHECK (jsonb_typeof(representative_occupations)='array'),
  CHECK (jsonb_typeof(quality_metrics)='object')
);

CREATE TABLE occupation_archetype_memberships (
  id BIGSERIAL PRIMARY KEY,
  model_version_id BIGINT NOT NULL REFERENCES occupational_archetype_model_versions(id),
  archetype_definition_id BIGINT NOT NULL REFERENCES occupational_archetype_definitions(id),
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code),
  membership_role TEXT NOT NULL CHECK (membership_role IN ('primary','secondary')),
  membership_strength NUMERIC(7,4) NOT NULL CHECK (membership_strength BETWEEN 0 AND 100),
  membership_confidence NUMERIC(7,4) NOT NULL CHECK (membership_confidence BETWEEN 0 AND 100),
  distance_to_centroid NUMERIC(12,8) NOT NULL CHECK (distance_to_centroid>=0),
  distance_rank INTEGER NOT NULL CHECK (distance_rank IN (1,2)),
  feature_completeness NUMERIC(7,4) NOT NULL CHECK (feature_completeness BETWEEN 0 AND 100),
  evidence JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_version_id,occupation_code,membership_role),
  CHECK (jsonb_typeof(evidence)='object')
);

CREATE TABLE archetype_structural_baselines (
  id BIGSERIAL PRIMARY KEY,
  archetype_definition_id BIGINT NOT NULL REFERENCES occupational_archetype_definitions(id),
  baseline_version TEXT NOT NULL,
  structural_dimension TEXT NOT NULL CHECK (structural_dimension IN (
    'physical-presence','physical-manipulation','mobility-real-world-operation',
    'environment-variability','human-dependency','regulation','accountability',
    'consequence-severity','real-time-interaction','privacy-sensitivity','adoption-pressure'
  )),
  baseline_value NUMERIC(7,4) NOT NULL CHECK (baseline_value BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  supporting_occupation_count INTEGER NOT NULL CHECK (supporting_occupation_count>0),
  source_dispersion NUMERIC(9,4) NOT NULL CHECK (source_dispersion>=0),
  formula_version TEXT NOT NULL,
  exact_inputs JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (archetype_definition_id,baseline_version,structural_dimension),
  CHECK (jsonb_typeof(exact_inputs)='object')
);

CREATE TABLE occupation_archetype_proxy_adjustments (
  id BIGSERIAL PRIMARY KEY,
  model_version_id BIGINT NOT NULL REFERENCES occupational_archetype_model_versions(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  structural_dimension TEXT NOT NULL CHECK (structural_dimension IN (
    'physical-presence','physical-manipulation','mobility-real-world-operation',
    'environment-variability','human-dependency','regulation','accountability',
    'consequence-severity','real-time-interaction','privacy-sensitivity','adoption-pressure'
  )),
  primary_archetype_id BIGINT NOT NULL REFERENCES occupational_archetype_definitions(id),
  secondary_archetype_id BIGINT REFERENCES occupational_archetype_definitions(id),
  archetype_baseline NUMERIC(7,4) NOT NULL CHECK (archetype_baseline BETWEEN 0 AND 100),
  occupation_source_evidence NUMERIC(7,4) CHECK (occupation_source_evidence BETWEEN 0 AND 100),
  evidence_confidence NUMERIC(7,4) NOT NULL CHECK (evidence_confidence BETWEEN 0 AND 100),
  prior_weight NUMERIC(7,6) NOT NULL CHECK (prior_weight BETWEEN 0 AND 1),
  occupation_adjustment NUMERIC(8,4) NOT NULL CHECK (occupation_adjustment BETWEEN -100 AND 100),
  resulting_proxy NUMERIC(7,4) NOT NULL CHECK (resulting_proxy BETWEEN 0 AND 100),
  resulting_confidence NUMERIC(7,4) NOT NULL CHECK (resulting_confidence BETWEEN 0 AND 100),
  formula_version TEXT NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_version_id,validation_occupation_id,structural_dimension),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE archetype_phase4c_validation_runs (
  id BIGSERIAL PRIMARY KEY,
  run_version TEXT NOT NULL UNIQUE,
  run_kind TEXT NOT NULL CHECK (run_kind IN ('archetype_pilot','deterministic_replay')),
  model_version_id BIGINT NOT NULL REFERENCES occupational_archetype_model_versions(id),
  baseline_phase4c_run_id BIGINT NOT NULL REFERENCES phase4c_calculation_runs(id),
  previous_run_id BIGINT REFERENCES archetype_phase4c_validation_runs(id),
  pilot_feature_flag_override BOOLEAN NOT NULL CHECK (pilot_feature_flag_override=true),
  external_ai_calls INTEGER NOT NULL DEFAULT 0 CHECK (external_ai_calls=0),
  regenerated_mapping_count INTEGER NOT NULL DEFAULT 0 CHECK (regenerated_mapping_count=0),
  occupation_count INTEGER NOT NULL CHECK (occupation_count=25),
  task_assessment_count INTEGER NOT NULL CHECK (task_assessment_count>=0),
  dependency_hash CHAR(64) NOT NULL,
  reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('passed','failed')),
  replay_matches_previous BOOLEAN,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE archetype_phase4c_task_assessments (
  id BIGSERIAL PRIMARY KEY,
  validation_run_id BIGINT NOT NULL REFERENCES archetype_phase4c_validation_runs(id),
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
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (validation_run_id,ai_task_mapping_id),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(constraint_contributions)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE archetype_phase4c_occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  validation_run_id BIGINT NOT NULL REFERENCES archetype_phase4c_validation_runs(id),
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
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (validation_run_id,validation_occupation_id),
  CHECK (jsonb_typeof(factor_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE archetype_proxy_validation_results (
  id BIGSERIAL PRIMARY KEY,
  validation_run_id BIGINT NOT NULL REFERENCES archetype_phase4c_validation_runs(id),
  validation_type TEXT NOT NULL CHECK (validation_type IN ('pairwise','absolute_band')),
  validation_key TEXT NOT NULL,
  structural_dimension TEXT NOT NULL,
  baseline_outcome TEXT NOT NULL CHECK (baseline_outcome IN ('pass','warning','failure')),
  archetype_outcome TEXT NOT NULL CHECK (archetype_outcome IN ('pass','warning','failure')),
  baseline_value JSONB NOT NULL,
  archetype_value JSONB NOT NULL,
  improved BOOLEAN NOT NULL,
  regressed BOOLEAN NOT NULL,
  finding TEXT NOT NULL,
  reconciliation JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (validation_run_id,validation_type,validation_key),
  CHECK (NOT (improved AND regressed)),
  CHECK (jsonb_typeof(baseline_value)='object'),
  CHECK (jsonb_typeof(archetype_value)='object'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

WITH source AS (
  SELECT id FROM data_sources WHERE name='JobsVsAI Occupational Archetype Layer v1'
)
INSERT INTO scoring_enrichment_feature_flags (
  flag_key,layer_version,enabled,production_allowed,configuration,source_id,provenance,created_by
)
SELECT 'occupational_archetype_layer','occupational-archetype-v1',false,false,
  '{"default":"disabled","pilotOverrideScope":"phase4c-2026q3-v1","fallback":"unchanged_phase4b_phase4c_pipeline"}'::jsonb,
  source.id,'{"reversible":true,"public":false,"production":false}'::jsonb,'system:migration-022'
FROM source;

CREATE TRIGGER archetype_feature_flags_append_only BEFORE UPDATE OR DELETE ON scoring_enrichment_feature_flags FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_models_append_only BEFORE UPDATE OR DELETE ON occupational_archetype_model_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_definitions_append_only BEFORE UPDATE OR DELETE ON occupational_archetype_definitions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_memberships_append_only BEFORE UPDATE OR DELETE ON occupation_archetype_memberships FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_baselines_append_only BEFORE UPDATE OR DELETE ON archetype_structural_baselines FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_adjustments_append_only BEFORE UPDATE OR DELETE ON occupation_archetype_proxy_adjustments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_validation_runs_append_only BEFORE UPDATE OR DELETE ON archetype_phase4c_validation_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_task_assessments_append_only BEFORE UPDATE OR DELETE ON archetype_phase4c_task_assessments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_occupation_scores_append_only BEFORE UPDATE OR DELETE ON archetype_phase4c_occupation_scores FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER archetype_proxy_results_append_only BEFORE UPDATE OR DELETE ON archetype_proxy_validation_results FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
