BEGIN;

CREATE TABLE task_mapping_evidence_policy_versions (
  id BIGSERIAL PRIMARY KEY,
  policy_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  policy_scope TEXT NOT NULL CHECK (policy_scope IN ('mvp_provisional_scoring','research_validation')),
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  minimum_mapping_confidence NUMERIC(6,3) NOT NULL CHECK (minimum_mapping_confidence BETWEEN 0 AND 100),
  minimum_dimension_confidence NUMERIC(6,3) NOT NULL CHECK (minimum_dimension_confidence BETWEEN 0 AND 100),
  minimum_evidenced_dimension_coverage NUMERIC(6,5) NOT NULL CHECK (minimum_evidenced_dimension_coverage BETWEEN 0 AND 1),
  minimum_rationale_coverage NUMERIC(6,5) NOT NULL CHECK (minimum_rationale_coverage BETWEEN 0 AND 1),
  minimum_capability_dimensions INTEGER NOT NULL CHECK (minimum_capability_dimensions > 0),
  maximum_capability_dimensions INTEGER NOT NULL CHECK (maximum_capability_dimensions > 0),
  allow_ambiguous_scope BOOLEAN NOT NULL DEFAULT false,
  allow_insufficient_description BOOLEAN NOT NULL DEFAULT false,
  require_model_provenance BOOLEAN NOT NULL DEFAULT true,
  require_prompt_provenance BOOLEAN NOT NULL DEFAULT true,
  require_independent_structural_validation BOOLEAN NOT NULL DEFAULT true,
  allowed_scoring_review_states JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  supersedes_policy_version_id BIGINT REFERENCES task_mapping_evidence_policy_versions(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (minimum_capability_dimensions <= maximum_capability_dimensions),
  CHECK (jsonb_typeof(allowed_scoring_review_states)='array')
);

CREATE TABLE ai_generated_task_mapping_runs (
  id BIGSERIAL PRIMARY KEY,
  run_version TEXT NOT NULL UNIQUE,
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  evidence_policy_version_id BIGINT NOT NULL REFERENCES task_mapping_evidence_policy_versions(id),
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  model_version TEXT NOT NULL,
  model_snapshot_date DATE,
  prompt_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  prompt_sha256 TEXT NOT NULL,
  system_prompt_sha256 TEXT,
  inference_configuration JSONB NOT NULL,
  allowed_input_manifest JSONB NOT NULL,
  prohibited_input_attestation BOOLEAN NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('completed','failed')),
  input_task_count INTEGER NOT NULL CHECK (input_task_count >= 0),
  output_task_count INTEGER NOT NULL CHECK (output_task_count >= 0),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (output_task_count <= input_task_count),
  CHECK (jsonb_typeof(inference_configuration)='object'),
  CHECK (jsonb_typeof(allowed_input_manifest)='object')
);

CREATE TABLE ai_generated_task_mappings (
  id BIGSERIAL PRIMARY KEY,
  mapping_run_id BIGINT NOT NULL REFERENCES ai_generated_task_mapping_runs(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  mapping_version TEXT NOT NULL,
  task_statement_hash TEXT NOT NULL,
  ambiguity_state TEXT NOT NULL CHECK (ambiguity_state IN ('none','ambiguous_scope','insufficient_description')),
  mapping_confidence NUMERIC(6,3) NOT NULL CHECK (mapping_confidence BETWEEN 0 AND 100),
  initial_validation_status TEXT NOT NULL CHECK (initial_validation_status IN ('pending','self_checked')),
  initial_review_state TEXT NOT NULL CHECK (initial_review_state IN ('unreviewed','ai_self_checked','pending_human_review','human_reviewed','rejected')),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  supersedes_mapping_id BIGINT REFERENCES ai_generated_task_mappings(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (mapping_run_id,onet_task_id,mapping_version),
  CHECK (jsonb_typeof(evidence)='array')
);

CREATE TABLE ai_generated_task_capability_requirements (
  id BIGSERIAL PRIMARY KEY,
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  weight NUMERIC(8,7) NOT NULL CHECK (weight > 0 AND weight <= 1),
  required_capability_level NUMERIC(6,3) NOT NULL CHECK (required_capability_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ai_task_mapping_id,capability_definition_id),
  CHECK (jsonb_typeof(evidence)='array')
);

CREATE TABLE ai_generated_task_environment_constraints (
  id BIGSERIAL PRIMARY KEY,
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  constraint_definition_id BIGINT NOT NULL REFERENCES task_environment_constraint_definitions(id),
  constraint_level NUMERIC(6,3) NOT NULL CHECK (constraint_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ai_task_mapping_id,constraint_definition_id),
  CHECK (jsonb_typeof(evidence)='array')
);

CREATE TABLE ai_task_mapping_validation_events (
  id BIGSERIAL PRIMARY KEY,
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  evidence_policy_version_id BIGINT NOT NULL REFERENCES task_mapping_evidence_policy_versions(id),
  validation_version TEXT NOT NULL,
  validator_name TEXT NOT NULL,
  validator_version TEXT NOT NULL,
  structural_validation_passed BOOLEAN NOT NULL,
  confidence_threshold_passed BOOLEAN NOT NULL,
  evidence_coverage_passed BOOLEAN NOT NULL,
  ambiguity_policy_passed BOOLEAN NOT NULL,
  provenance_validation_passed BOOLEAN NOT NULL,
  validation_status TEXT NOT NULL CHECK (validation_status IN ('passed','failed')),
  review_state TEXT NOT NULL CHECK (review_state IN ('unreviewed','ai_self_checked','ai_validated','pending_human_review','human_reviewed','rejected')),
  scoring_eligible BOOLEAN NOT NULL DEFAULT false,
  capability_dimension_count INTEGER NOT NULL CHECK (capability_dimension_count >= 0),
  constraint_dimension_count INTEGER NOT NULL CHECK (constraint_dimension_count >= 0),
  normalized_weight_total NUMERIC(9,7) NOT NULL,
  evidenced_dimension_coverage NUMERIC(6,5) NOT NULL CHECK (evidenced_dimension_coverage BETWEEN 0 AND 1),
  rationale_coverage NUMERIC(6,5) NOT NULL CHECK (rationale_coverage BETWEEN 0 AND 1),
  gate_results JSONB NOT NULL,
  failure_reasons JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ai_task_mapping_id,evidence_policy_version_id,validation_version),
  CHECK (jsonb_typeof(gate_results)='object'),
  CHECK (jsonb_typeof(failure_reasons)='array'),
  CHECK (NOT scoring_eligible OR validation_status='passed')
);

CREATE TABLE frontier_ai_capability_index_versions (
  id BIGSERIAL PRIMARY KEY,
  index_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  methodology_version TEXT NOT NULL,
  score_scale_min NUMERIC(6,3) NOT NULL DEFAULT 0,
  score_scale_max NUMERIC(6,3) NOT NULL DEFAULT 100,
  expected_capability_count INTEGER NOT NULL CHECK (expected_capability_count >= 0),
  as_of_date DATE,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  supersedes_index_version_id BIGINT REFERENCES frontier_ai_capability_index_versions(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (score_scale_min < score_scale_max)
);

CREATE TABLE frontier_ai_capability_index_entries (
  id BIGSERIAL PRIMARY KEY,
  index_version_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_versions(id),
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  capability_score NUMERIC(6,3) NOT NULL CHECK (capability_score BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  source_type TEXT NOT NULL CHECK (source_type IN ('provider_benchmark','independent_benchmark','research_paper','third_party_evaluation','internal_evaluation','expert_synthesis')),
  provider_name TEXT,
  model_name TEXT,
  model_version TEXT,
  observed_at DATE NOT NULL,
  rationale TEXT NOT NULL,
  benchmark_evidence JSONB NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (index_version_id,capability_definition_id),
  CHECK (jsonb_typeof(benchmark_evidence)='array'),
  CHECK (jsonb_array_length(benchmark_evidence)>0)
);

CREATE TABLE frontier_ai_capability_evidence_records (
  id BIGSERIAL PRIMARY KEY,
  index_version_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_versions(id),
  capability_definition_id BIGINT REFERENCES ai_capability_definitions(id),
  source_type TEXT NOT NULL CHECK (source_type IN ('provider_benchmark','independent_benchmark','research_paper','third_party_evaluation','internal_evaluation','expert_synthesis')),
  provider_name TEXT,
  model_name TEXT,
  model_version TEXT,
  evidence_date DATE NOT NULL,
  title TEXT NOT NULL,
  source_uri TEXT,
  evidence_payload JSONB NOT NULL,
  rationale TEXT NOT NULL,
  confidence NUMERIC(6,3) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 100),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(evidence_payload)='object')
);

CREATE OR REPLACE FUNCTION validate_ai_generated_task_mapping(
  mapping_key BIGINT,policy_key BIGINT,validation_key TEXT,validator_key TEXT,validator_version_key TEXT,actor TEXT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
  mapping_row ai_generated_task_mappings%ROWTYPE;
  run_row ai_generated_task_mapping_runs%ROWTYPE;
  policy_row task_mapping_evidence_policy_versions%ROWTYPE;
  rubric_row task_mapping_rubric_versions%ROWTYPE;
  capability_count INTEGER;
  constraint_count INTEGER;
  invalid_capabilities INTEGER;
  invalid_constraints INTEGER;
  weight_total NUMERIC;
  evidenced_count INTEGER;
  rationale_count INTEGER;
  total_dimensions INTEGER;
  evidence_coverage NUMERIC;
  rationale_coverage_value NUMERIC;
  structural_pass BOOLEAN;
  confidence_pass BOOLEAN;
  evidence_pass BOOLEAN;
  ambiguity_pass BOOLEAN;
  provenance_pass BOOLEAN;
  overall_pass BOOLEAN;
  event_id BIGINT;
  gates JSONB;
  failures JSONB := '[]'::jsonb;
BEGIN
  SELECT * INTO mapping_row FROM ai_generated_task_mappings WHERE id=mapping_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown AI task mapping %',mapping_key; END IF;
  SELECT * INTO run_row FROM ai_generated_task_mapping_runs WHERE id=mapping_row.mapping_run_id;
  SELECT * INTO policy_row FROM task_mapping_evidence_policy_versions WHERE id=policy_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown evidence policy %',policy_key; END IF;
  SELECT * INTO rubric_row FROM task_mapping_rubric_versions WHERE id=run_row.rubric_version_id;

  SELECT count(*),coalesce(sum(requirement.weight),0),
    count(*) FILTER (WHERE definition.taxonomy_version_id<>run_row.taxonomy_version_id
      OR requirement.weight<rubric_row.minimum_meaningful_weight
      OR requirement.required_capability_level<rubric_row.minimum_meaningful_requirement_level),
    count(*) FILTER (WHERE jsonb_array_length(requirement.evidence)>0),
    count(*) FILTER (WHERE length(trim(requirement.rationale))>0)
  INTO capability_count,weight_total,invalid_capabilities,evidenced_count,rationale_count
  FROM ai_generated_task_capability_requirements requirement
  JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
  WHERE requirement.ai_task_mapping_id=mapping_key;

  SELECT count(*),
    count(*) FILTER (WHERE definition.environment_taxonomy_version_id<>rubric_row.environment_taxonomy_version_id
      OR constraint_mapping.constraint_level<rubric_row.minimum_meaningful_constraint_level),
    evidenced_count + count(*) FILTER (WHERE jsonb_array_length(constraint_mapping.evidence)>0),
    rationale_count + count(*) FILTER (WHERE length(trim(constraint_mapping.rationale))>0)
  INTO constraint_count,invalid_constraints,evidenced_count,rationale_count
  FROM ai_generated_task_environment_constraints constraint_mapping
  JOIN task_environment_constraint_definitions definition ON definition.id=constraint_mapping.constraint_definition_id
  WHERE constraint_mapping.ai_task_mapping_id=mapping_key;

  total_dimensions := capability_count + constraint_count;
  evidence_coverage := CASE WHEN total_dimensions=0 THEN 0 ELSE evidenced_count::numeric/total_dimensions END;
  rationale_coverage_value := CASE WHEN total_dimensions=0 THEN 0 ELSE rationale_count::numeric/total_dimensions END;
  structural_pass := run_row.taxonomy_version_id=policy_row.taxonomy_version_id
    AND run_row.rubric_version_id=policy_row.rubric_version_id
    AND run_row.evidence_policy_version_id=policy_row.id
    AND mapping_row.task_statement_hash=(SELECT md5(statement) FROM onet_tasks WHERE task_id=mapping_row.onet_task_id)
    AND capability_count BETWEEN policy_row.minimum_capability_dimensions AND policy_row.maximum_capability_dimensions
    AND abs(weight_total-1)<=rubric_row.normalization_tolerance
    AND invalid_capabilities=0 AND invalid_constraints=0;
  confidence_pass := mapping_row.mapping_confidence>=policy_row.minimum_mapping_confidence
    AND NOT EXISTS (SELECT 1 FROM ai_generated_task_capability_requirements WHERE ai_task_mapping_id=mapping_key AND confidence<policy_row.minimum_dimension_confidence)
    AND NOT EXISTS (SELECT 1 FROM ai_generated_task_environment_constraints WHERE ai_task_mapping_id=mapping_key AND confidence<policy_row.minimum_dimension_confidence);
  evidence_pass := evidence_coverage>=policy_row.minimum_evidenced_dimension_coverage
    AND rationale_coverage_value>=policy_row.minimum_rationale_coverage;
  ambiguity_pass := (mapping_row.ambiguity_state='none')
    OR (mapping_row.ambiguity_state='ambiguous_scope' AND policy_row.allow_ambiguous_scope)
    OR (mapping_row.ambiguity_state='insufficient_description' AND policy_row.allow_insufficient_description);
  provenance_pass := (NOT policy_row.require_model_provenance OR (length(trim(run_row.provider_name))>0 AND length(trim(run_row.model_name))>0 AND length(trim(run_row.model_version))>0))
    AND (NOT policy_row.require_prompt_provenance OR (length(trim(run_row.prompt_name))>0 AND length(trim(run_row.prompt_version))>0 AND length(trim(run_row.prompt_sha256))=64))
    AND run_row.prohibited_input_attestation;
  overall_pass := policy_row.status='active' AND structural_pass AND confidence_pass AND evidence_pass AND ambiguity_pass AND provenance_pass;

  gates := jsonb_build_object(
    'activePolicy',policy_row.status='active','structuralValidation',structural_pass,
    'confidenceThreshold',confidence_pass,'evidenceCoverage',evidence_pass,
    'ambiguityPolicy',ambiguity_pass,'modelAndPromptProvenance',provenance_pass,
    'humanGoldRequired',false
  );
  IF policy_row.status<>'active' THEN failures:=failures||'"policy_not_active"'::jsonb; END IF;
  IF NOT structural_pass THEN failures:=failures||'"structural_validation_failed"'::jsonb; END IF;
  IF NOT confidence_pass THEN failures:=failures||'"confidence_threshold_failed"'::jsonb; END IF;
  IF NOT evidence_pass THEN failures:=failures||'"evidence_coverage_failed"'::jsonb; END IF;
  IF NOT ambiguity_pass THEN failures:=failures||'"ambiguity_policy_failed"'::jsonb; END IF;
  IF NOT provenance_pass THEN failures:=failures||'"provenance_validation_failed"'::jsonb; END IF;

  INSERT INTO ai_task_mapping_validation_events (
    ai_task_mapping_id,evidence_policy_version_id,validation_version,validator_name,validator_version,
    structural_validation_passed,confidence_threshold_passed,evidence_coverage_passed,
    ambiguity_policy_passed,provenance_validation_passed,validation_status,review_state,
    scoring_eligible,capability_dimension_count,constraint_dimension_count,normalized_weight_total,
    evidenced_dimension_coverage,rationale_coverage,gate_results,failure_reasons,source_id,provenance,created_by
  ) VALUES (
    mapping_key,policy_key,validation_key,validator_key,validator_version_key,
    structural_pass,confidence_pass,evidence_pass,ambiguity_pass,provenance_pass,
    CASE WHEN overall_pass THEN 'passed' ELSE 'failed' END,
    CASE WHEN overall_pass THEN 'ai_validated' ELSE mapping_row.initial_review_state END,
    overall_pass,capability_count,constraint_count,weight_total,evidence_coverage,rationale_coverage_value,
    gates,failures,run_row.source_id,
    jsonb_build_object('deterministic',true,'human_review_required',false,'mvp_provisional',true),actor
  ) RETURNING id INTO event_id;
  RETURN event_id;
END $$;

CREATE OR REPLACE FUNCTION validate_frontier_ai_capability_index(index_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  index_row frontier_ai_capability_index_versions%ROWTYPE;
  entry_count INTEGER;
  invalid_entries INTEGER;
BEGIN
  SELECT * INTO index_row FROM frontier_ai_capability_index_versions WHERE id=index_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown Frontier AI Capability Index version %',index_key; END IF;
  SELECT count(*),count(*) FILTER (WHERE definition.taxonomy_version_id<>index_row.taxonomy_version_id)
  INTO entry_count,invalid_entries
  FROM frontier_ai_capability_index_entries entry
  JOIN ai_capability_definitions definition ON definition.id=entry.capability_definition_id
  WHERE entry.index_version_id=index_key;
  IF invalid_entries>0 THEN RAISE EXCEPTION 'Frontier index % mixes taxonomy versions',index_key; END IF;
  IF index_row.status IN ('review','active') AND entry_count<>index_row.expected_capability_count THEN
    RAISE EXCEPTION 'Frontier index % expected % capability values, found %',index_key,index_row.expected_capability_count,entry_count;
  END IF;
  RETURN true;
END $$;

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI MVP Evidence Mapping Policy','internal://jobsvsai/mvp-evidence-mapping-policy','v1',
    '{"owner":"JobsVsAI","scope":"mvp_provisional_scoring","human_gold_required":false,"production_score_recalculation":false}'::jsonb)
  ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,metadata=EXCLUDED.metadata
  RETURNING id
)
INSERT INTO task_mapping_evidence_policy_versions (
  policy_version,name,description,status,policy_scope,taxonomy_version_id,rubric_version_id,
  minimum_mapping_confidence,minimum_dimension_confidence,minimum_evidenced_dimension_coverage,
  minimum_rationale_coverage,minimum_capability_dimensions,maximum_capability_dimensions,
  allow_ambiguous_scope,allow_insufficient_description,require_model_provenance,
  require_prompt_provenance,require_independent_structural_validation,allowed_scoring_review_states,
  source_id,provenance,created_by
)
SELECT 'mvp-evidence-policy-v1','JobsVsAI MVP Evidence-Based Mapping Policy v1',
  'Allows provisional scoring eligibility from structurally valid, sufficiently confident and evidenced AI mappings without mandatory human-gold coverage.',
  'active','mvp_provisional_scoring',rubric.capability_taxonomy_version_id,rubric.id,
  70,60,1.0,1.0,1,rubric.maximum_capabilities_per_task,false,false,true,true,true,
  '["ai_validated","human_reviewed"]'::jsonb,source.id,
  '{"replaces_human_gold_as_mvp_gate":true,"preserves_research_gold_infrastructure":true,"does_not_activate_mappings":true}'::jsonb,
  'system:migration-015'
FROM source JOIN task_mapping_rubric_versions rubric ON rubric.version='jvs-task-capability-rubric-v1';

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI Frontier AI Capability Index','internal://jobsvsai/frontier-ai-capability-index','v1',
    '{"owner":"JobsVsAI","layer":"frontier_capability_evidence","production_scoring":false,"values_assigned":false}'::jsonb)
  ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,metadata=EXCLUDED.metadata
  RETURNING id
)
INSERT INTO frontier_ai_capability_index_versions (
  index_version,name,description,status,taxonomy_version_id,methodology_version,
  expected_capability_count,source_id,provenance,created_by
)
SELECT 'frontier-ai-index-v1','JobsVsAI Frontier AI Capability Index v1',
  'Draft evidence model for dated frontier capability estimates. No capability values are assigned in this phase.',
  'draft',taxonomy.id,'frontier-ai-index-methodology-v1',15,source.id,
  '{"definitions_only":true,"values_assigned":false,"not_for_production_scoring":true}'::jsonb,
  'system:migration-015'
FROM source JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.version='jvs-ai-cap-v1';

CREATE TRIGGER evidence_policies_append_only BEFORE UPDATE OR DELETE ON task_mapping_evidence_policy_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER ai_mapping_runs_append_only BEFORE UPDATE OR DELETE ON ai_generated_task_mapping_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER ai_mappings_append_only BEFORE UPDATE OR DELETE ON ai_generated_task_mappings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER ai_mapping_requirements_append_only BEFORE UPDATE OR DELETE ON ai_generated_task_capability_requirements FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER ai_mapping_constraints_append_only BEFORE UPDATE OR DELETE ON ai_generated_task_environment_constraints FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER ai_mapping_validation_append_only BEFORE UPDATE OR DELETE ON ai_task_mapping_validation_events FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER frontier_index_versions_append_only BEFORE UPDATE OR DELETE ON frontier_ai_capability_index_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER frontier_index_entries_append_only BEFORE UPDATE OR DELETE ON frontier_ai_capability_index_entries FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER frontier_index_evidence_append_only BEFORE UPDATE OR DELETE ON frontier_ai_capability_evidence_records FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

CREATE OR REPLACE VIEW mvp_mapping_policy_validation AS
SELECT policy.id policy_id,policy.policy_version,policy.status,policy.policy_scope,
  policy.minimum_mapping_confidence,policy.minimum_dimension_confidence,
  policy.minimum_evidenced_dimension_coverage,policy.minimum_rationale_coverage,
  count(DISTINCT run.id) ai_mapping_runs,count(DISTINCT mapping.id) ai_task_mappings,
  count(DISTINCT validation.id) validation_events,
  count(DISTINCT validation.ai_task_mapping_id) FILTER (WHERE validation.scoring_eligible) scoring_eligible_mappings,
  count(DISTINCT validation.ai_task_mapping_id) FILTER (WHERE validation.validation_status='failed') failed_mappings,
  false human_gold_required
FROM task_mapping_evidence_policy_versions policy
LEFT JOIN ai_generated_task_mapping_runs run ON run.evidence_policy_version_id=policy.id
LEFT JOIN ai_generated_task_mappings mapping ON mapping.mapping_run_id=run.id
LEFT JOIN ai_task_mapping_validation_events validation ON validation.ai_task_mapping_id=mapping.id AND validation.evidence_policy_version_id=policy.id
GROUP BY policy.id;

CREATE OR REPLACE VIEW frontier_ai_capability_index_validation AS
SELECT index_version.id index_version_id,index_version.index_version,index_version.status,
  index_version.expected_capability_count,count(DISTINCT entry.id) capability_values,
  count(DISTINCT evidence.id) evidence_records,
  validate_frontier_ai_capability_index(index_version.id) index_valid
FROM frontier_ai_capability_index_versions index_version
LEFT JOIN frontier_ai_capability_index_entries entry ON entry.index_version_id=index_version.id
LEFT JOIN frontier_ai_capability_evidence_records evidence ON evidence.index_version_id=index_version.id
GROUP BY index_version.id;

COMMIT;
