BEGIN;

CREATE TABLE task_mapping_gold_review_events (
  id BIGSERIAL PRIMARY KEY,
  gold_item_id BIGINT NOT NULL REFERENCES task_capability_gold_items(id),
  review_round INTEGER NOT NULL CHECK (review_round > 0),
  reviewer_identifier TEXT NOT NULL,
  reviewer_kind TEXT NOT NULL CHECK (reviewer_kind IN ('human','assistant','automated','fixture')),
  reviewer_organization TEXT,
  decision TEXT NOT NULL CHECK (decision IN ('submitted','approved','rejected','abstained')),
  proposed_disposition TEXT CHECK (proposed_disposition IN ('mappable','insufficient_description','ambiguous_scope')),
  capability_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
  environment_constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  adjudication_note TEXT NOT NULL DEFAULT '',
  is_adjudication BOOLEAN NOT NULL DEFAULT false,
  supersedes_review_event_id BIGINT REFERENCES task_mapping_gold_review_events(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(capability_requirements)='array'),
  CHECK (jsonb_typeof(environment_constraints)='array'),
  CHECK (jsonb_typeof(evidence)='array'),
  UNIQUE (gold_item_id,review_round,reviewer_identifier)
);

CREATE TABLE task_mapping_candidate_runs (
  id BIGSERIAL PRIMARY KEY,
  run_version TEXT NOT NULL UNIQUE,
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  benchmark_dataset_id BIGINT NOT NULL REFERENCES task_capability_gold_datasets(id),
  mapper_name TEXT NOT NULL,
  mapper_version TEXT NOT NULL,
  mapper_kind TEXT NOT NULL CHECK (mapper_kind IN ('deterministic_rules','statistical','language_model','hybrid')),
  status TEXT NOT NULL CHECK (status IN ('completed','failed')),
  allowed_input_manifest JSONB NOT NULL,
  prohibited_input_attestation BOOLEAN NOT NULL,
  configuration JSONB NOT NULL,
  source_code_sha256 TEXT NOT NULL,
  input_task_count INTEGER NOT NULL CHECK (input_task_count >= 0),
  output_task_count INTEGER NOT NULL CHECK (output_task_count >= 0),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (output_task_count <= input_task_count)
);

CREATE TABLE candidate_task_mappings (
  id BIGSERIAL PRIMARY KEY,
  candidate_run_id BIGINT NOT NULL REFERENCES task_mapping_candidate_runs(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  task_statement_hash TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK (disposition IN ('mappable','insufficient_description','ambiguous_scope')),
  disposition_confidence NUMERIC(6,3) NOT NULL CHECK (disposition_confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (candidate_run_id,onet_task_id)
);

CREATE TABLE candidate_task_capability_requirements (
  id BIGSERIAL PRIMARY KEY,
  candidate_task_mapping_id BIGINT NOT NULL REFERENCES candidate_task_mappings(id),
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  weight NUMERIC(8,7) NOT NULL CHECK (weight > 0 AND weight <= 1),
  required_capability_level NUMERIC(6,3) NOT NULL CHECK (required_capability_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (candidate_task_mapping_id,capability_definition_id)
);

CREATE TABLE candidate_task_environment_constraints (
  id BIGSERIAL PRIMARY KEY,
  candidate_task_mapping_id BIGINT NOT NULL REFERENCES candidate_task_mappings(id),
  constraint_definition_id BIGINT NOT NULL REFERENCES task_environment_constraint_definitions(id),
  constraint_level NUMERIC(6,3) NOT NULL CHECK (constraint_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (candidate_task_mapping_id,constraint_definition_id)
);

CREATE TABLE task_mapping_verification_runs (
  id BIGSERIAL PRIMARY KEY,
  candidate_run_id BIGINT NOT NULL REFERENCES task_mapping_candidate_runs(id),
  verification_version TEXT NOT NULL,
  verifier_name TEXT NOT NULL,
  verifier_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('passed','failed')),
  independent_implementation_attestation BOOLEAN NOT NULL,
  allowed_input_manifest JSONB NOT NULL,
  checks_performed JSONB NOT NULL,
  summary JSONB NOT NULL,
  source_code_sha256 TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (candidate_run_id,verification_version)
);

CREATE TABLE task_mapping_verification_findings (
  id BIGSERIAL PRIMARY KEY,
  verification_run_id BIGINT NOT NULL REFERENCES task_mapping_verification_runs(id),
  candidate_task_mapping_id BIGINT REFERENCES candidate_task_mappings(id),
  severity TEXT NOT NULL CHECK (severity IN ('error','warning','info')),
  finding_code TEXT NOT NULL,
  message TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mapper_acceptance_gate_configs (
  id BIGSERIAL PRIMARY KEY,
  gate_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  minimum_human_reviewed_tasks INTEGER NOT NULL CHECK (minimum_human_reviewed_tasks >= 0),
  minimum_occupations INTEGER NOT NULL CHECK (minimum_occupations >= 0),
  minimum_capability_set_agreement NUMERIC(6,5) NOT NULL CHECK (minimum_capability_set_agreement BETWEEN 0 AND 1),
  maximum_mean_weight_deviation NUMERIC(8,7) NOT NULL CHECK (maximum_mean_weight_deviation BETWEEN 0 AND 1),
  maximum_mean_requirement_level_deviation NUMERIC(6,3) NOT NULL CHECK (maximum_mean_requirement_level_deviation BETWEEN 0 AND 100),
  maximum_mean_constraint_deviation NUMERIC(6,3) NOT NULL CHECK (maximum_mean_constraint_deviation BETWEEN 0 AND 100),
  minimum_confidence_agreement NUMERIC(6,5) NOT NULL CHECK (minimum_confidence_agreement BETWEEN 0 AND 1),
  maximum_extra_dimension_rate NUMERIC(6,5) NOT NULL CHECK (maximum_extra_dimension_rate BETWEEN 0 AND 1),
  maximum_missing_dimension_rate NUMERIC(6,5) NOT NULL CHECK (maximum_missing_dimension_rate BETWEEN 0 AND 1),
  maximum_false_inference_rate NUMERIC(6,5) NOT NULL CHECK (maximum_false_inference_rate BETWEEN 0 AND 1),
  require_independent_verification BOOLEAN NOT NULL DEFAULT true,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  supersedes_gate_config_id BIGINT REFERENCES mapper_acceptance_gate_configs(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_mapper_evaluation_runs (
  id BIGSERIAL PRIMARY KEY,
  evaluation_version TEXT NOT NULL UNIQUE,
  candidate_run_id BIGINT NOT NULL REFERENCES task_mapping_candidate_runs(id),
  gold_dataset_id BIGINT NOT NULL REFERENCES task_capability_gold_datasets(id),
  gate_config_id BIGINT NOT NULL REFERENCES mapper_acceptance_gate_configs(id),
  verification_run_id BIGINT REFERENCES task_mapping_verification_runs(id),
  status TEXT NOT NULL CHECK (status IN ('passed','failed','ineligible')),
  evaluated_task_count INTEGER NOT NULL CHECK (evaluated_task_count >= 0),
  human_reviewed_task_count INTEGER NOT NULL CHECK (human_reviewed_task_count >= 0),
  occupation_count INTEGER NOT NULL CHECK (occupation_count >= 0),
  metrics JSONB NOT NULL,
  gate_results JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VIEW task_mapping_blind_inputs AS
SELECT task.task_id onet_task_id,task.occupation_code,task.statement task_statement,
       md5(task.statement) task_statement_hash
FROM onet_tasks task;

CREATE OR REPLACE FUNCTION validate_candidate_mapping(candidate_mapping_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  candidate candidate_task_mappings%ROWTYPE;
  rubric_row task_mapping_rubric_versions%ROWTYPE;
  requirement_count INTEGER;
  constraint_count INTEGER;
  total_weight NUMERIC;
  invalid_requirements INTEGER;
  invalid_constraints INTEGER;
BEGIN
  SELECT * INTO candidate FROM candidate_task_mappings WHERE id=candidate_mapping_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown candidate task mapping %',candidate_mapping_key; END IF;
  SELECT rubric.* INTO rubric_row
  FROM task_mapping_candidate_runs run
  JOIN task_mapping_rubric_versions rubric ON rubric.id=run.rubric_version_id
  WHERE run.id=candidate.candidate_run_id;
  SELECT count(*),coalesce(sum(requirement.weight),0),count(*) FILTER (
    WHERE requirement.weight<rubric_row.minimum_meaningful_weight
      OR requirement.required_capability_level<rubric_row.minimum_meaningful_requirement_level
      OR definition.taxonomy_version_id<>rubric_row.capability_taxonomy_version_id
  ) INTO requirement_count,total_weight,invalid_requirements
  FROM candidate_task_capability_requirements requirement
  JOIN ai_capability_definitions definition ON definition.id=requirement.capability_definition_id
  WHERE requirement.candidate_task_mapping_id=candidate_mapping_key;
  SELECT count(*),count(*) FILTER (
    WHERE constraint_mapping.constraint_level<rubric_row.minimum_meaningful_constraint_level
      OR definition.environment_taxonomy_version_id<>rubric_row.environment_taxonomy_version_id
  ) INTO constraint_count,invalid_constraints
  FROM candidate_task_environment_constraints constraint_mapping
  JOIN task_environment_constraint_definitions definition ON definition.id=constraint_mapping.constraint_definition_id
  WHERE constraint_mapping.candidate_task_mapping_id=candidate_mapping_key;
  IF candidate.disposition='mappable' AND (
    requirement_count=0 OR requirement_count>rubric_row.maximum_capabilities_per_task
    OR abs(total_weight-1)>rubric_row.normalization_tolerance OR invalid_requirements>0 OR invalid_constraints>0
  ) THEN RAISE EXCEPTION 'Candidate mapping % does not satisfy rubric structure',candidate_mapping_key; END IF;
  IF candidate.disposition<>'mappable' AND (requirement_count>0 OR constraint_count>0) THEN
    RAISE EXCEPTION 'Candidate mapping % creates false inference for % task',candidate_mapping_key,candidate.disposition;
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION candidate_run_validation(candidate_run_key BIGINT)
RETURNS TABLE(total_tasks BIGINT,mappable_tasks BIGINT,ambiguous_tasks BIGINT,insufficient_tasks BIGINT,invalid_tasks BIGINT) LANGUAGE SQL AS $$
  SELECT count(*),
    count(*) FILTER (WHERE disposition='mappable'),
    count(*) FILTER (WHERE disposition='ambiguous_scope'),
    count(*) FILTER (WHERE disposition='insufficient_description'),
    count(*) FILTER (WHERE NOT validate_candidate_mapping(id))
  FROM candidate_task_mappings WHERE candidate_run_id=candidate_run_key
$$;

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI Draft Task Mapper','internal://jobsvsai/draft-task-mapper','v1',
    '{"owner":"JobsVsAI","allowed_inputs":["onet_task_statement","draft_taxonomy","mapping_rubric"],"prohibited_inputs":["ai_capability_scores","automation_outcomes","occupation_scores"],"production_scoring":false}'::jsonb)
  ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,metadata=EXCLUDED.metadata
  RETURNING id
)
INSERT INTO mapper_acceptance_gate_configs (
  gate_version,name,status,minimum_human_reviewed_tasks,minimum_occupations,
  minimum_capability_set_agreement,maximum_mean_weight_deviation,
  maximum_mean_requirement_level_deviation,maximum_mean_constraint_deviation,
  minimum_confidence_agreement,maximum_extra_dimension_rate,maximum_missing_dimension_rate,
  maximum_false_inference_rate,require_independent_verification,source_id,provenance,created_by
)
SELECT 'mapper-acceptance-gates-v1','JobsVsAI mapper acceptance gates v1','review',150,25,
  0.80,0.08,10,10,0.75,0.10,0.10,0.02,true,id,
  '{"configurable":true,"not_an_activation_gate":true,"requires_real_human_reviews":true}'::jsonb,
  'system:migration-013' FROM source;

WITH rubric AS (
  SELECT * FROM task_mapping_rubric_versions WHERE version='jvs-task-capability-rubric-v1'
),source AS (
  SELECT id FROM data_sources WHERE name='JobsVsAI Task-to-Capability Mapping Rubric'
)
INSERT INTO task_capability_gold_datasets (
  rubric_version_id,dataset_version,name,description,status,expected_task_count,supersedes_dataset_id,
  source_id,evidence,provenance,is_test_fixture,created_by
)
SELECT rubric.id,'gold-v1-175-pending-human-review','Gold benchmark v1 — 175-task review frame',
  'Representative 175-task, 28-occupation frame. Automated stratification and dispositions are triage only; human mapping and adjudication are pending.',
  'draft',175,(SELECT id FROM task_capability_gold_datasets WHERE dataset_version='gold-v1-representative-test'),
  source.id,'[{"kind":"stratified_benchmark_selection","occupations":28,"tasks":175}]'::jsonb,
  '{"human_review_status":"pending","automated_triage_is_not_gold":true,"activation_allowed":false}'::jsonb,
  false,'system:benchmark-selector-v1'
FROM rubric,source
WHERE (SELECT count(*) FROM onet_tasks)>0;

WITH selected_occupations(occupation_code,target_count) AS (VALUES
  ('11-9121.01',7),('13-1161.01',7),('15-1252.00',7),('17-2031.00',7),('19-2042.00',7),('21-1012.00',7),('23-1011.00',7),
  ('25-2057.00',6),('27-1024.00',6),('27-2012.00',6),('29-1171.00',6),('29-2056.00',6),('31-1131.00',6),('33-2011.00',6),
  ('35-2021.00',6),('37-1012.00',6),('39-9041.00',6),('41-4011.00',6),('43-4121.00',6),('45-3031.00',6),('47-2031.00',6),
  ('49-3011.00',6),('51-4031.00',6),('53-5021.00',6),('15-1241.00',6),('29-9099.01',6),('41-9022.00',6),('43-5011.01',6)
),ranked AS (
  SELECT task.task_id,task.occupation_code,task.statement,occupation.target_count,
    row_number() OVER (PARTITION BY task.occupation_code ORDER BY
      CASE WHEN task.task_id IN (299,18382,21662,21668) THEN 0
           WHEN length(task.statement)<=25 THEN 1
           WHEN length(task.statement)<=60 THEN 2
           ELSE 3 END,
      CASE WHEN length(task.statement)>60 THEN -length(task.statement) ELSE length(task.statement) END,
      md5(task.task_id::text||'gold-v1-175')) selection_rank
  FROM onet_tasks task JOIN selected_occupations occupation ON occupation.occupation_code=task.occupation_code
),selected AS (
  SELECT * FROM ranked WHERE selection_rank<=target_count
),dataset AS (
  SELECT * FROM task_capability_gold_datasets WHERE dataset_version='gold-v1-175-pending-human-review'
)
INSERT INTO task_capability_gold_items (
  gold_dataset_id,onet_task_id,disposition,task_statement_hash,disposition_rationale,
  reviewer_provenance,evidence,provenance,created_by,reviewed_at
)
SELECT dataset.id,selected.task_id,
  CASE WHEN selected.task_id=21668 THEN 'ambiguous_scope'
       WHEN length(selected.statement)<=25 OR array_length(regexp_split_to_array(trim(selected.statement),'\s+'),1)<=3 THEN 'insufficient_description'
       WHEN length(selected.statement)<=60 THEN 'ambiguous_scope'
       ELSE 'mappable' END,
  md5(selected.statement),
  'Automated review-stratum suggestion only; a human reviewer must confirm or replace this disposition without inferring unstated context.',
  '[{"reviewer":"system:benchmark-selector-v1","role":"triage","reviewer_kind":"automated","human_review_pending":true}]'::jsonb,
  jsonb_build_array(jsonb_build_object('task_statement',selected.statement,'selection_rank',selected.selection_rank,'selection_method','length-stratified-v1')),
  '{"automated_triage":true,"not_human_reviewed":true,"not_gold_eligible":true}'::jsonb,
  'system:benchmark-selector-v1',TIMESTAMPTZ '2026-08-20 00:00:00+00'
FROM selected,dataset;

INSERT INTO task_mapping_gold_review_events (
  gold_item_id,review_round,reviewer_identifier,reviewer_kind,decision,proposed_disposition,
  evidence,adjudication_note,provenance
)
SELECT item.id,1,'system:benchmark-selector-v1','automated','submitted',item.disposition,
  item.evidence,'Automated triage only. Independent human annotations and adjudication are required.',
  '{"counts_as_human_review":false,"counts_as_gold":false}'::jsonb
FROM task_capability_gold_items item
JOIN task_capability_gold_datasets dataset ON dataset.id=item.gold_dataset_id
WHERE dataset.dataset_version='gold-v1-175-pending-human-review';

CREATE TRIGGER gold_review_events_append_only BEFORE UPDATE OR DELETE ON task_mapping_gold_review_events FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER candidate_runs_append_only BEFORE UPDATE OR DELETE ON task_mapping_candidate_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER candidate_mappings_append_only BEFORE UPDATE OR DELETE ON candidate_task_mappings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER candidate_requirements_append_only BEFORE UPDATE OR DELETE ON candidate_task_capability_requirements FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER candidate_constraints_append_only BEFORE UPDATE OR DELETE ON candidate_task_environment_constraints FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER verification_runs_append_only BEFORE UPDATE OR DELETE ON task_mapping_verification_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER verification_findings_append_only BEFORE UPDATE OR DELETE ON task_mapping_verification_findings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER acceptance_gates_append_only BEFORE UPDATE OR DELETE ON mapper_acceptance_gate_configs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER evaluation_runs_append_only BEFORE UPDATE OR DELETE ON task_mapper_evaluation_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

CREATE OR REPLACE VIEW task_mapper_benchmark_validation AS
SELECT dataset.id gold_dataset_id,dataset.dataset_version,dataset.status,
  count(DISTINCT item.id) tasks,count(DISTINCT task.occupation_code) occupations,
  count(DISTINCT item.id) FILTER (WHERE item.disposition='mappable') mappable_tasks,
  count(DISTINCT item.id) FILTER (WHERE item.disposition='ambiguous_scope') ambiguous_tasks,
  count(DISTINCT item.id) FILTER (WHERE item.disposition='insufficient_description') insufficient_tasks,
  count(DISTINCT item.id) FILTER (WHERE EXISTS (
    SELECT 1 FROM task_mapping_gold_review_events review
    WHERE review.gold_item_id=item.id AND review.reviewer_kind='human' AND review.decision IN ('submitted','approved')
  )) human_reviewed_tasks,
  count(DISTINCT item.id) FILTER (WHERE (
    SELECT count(DISTINCT review.reviewer_identifier) FROM task_mapping_gold_review_events review
    WHERE review.gold_item_id=item.id AND review.reviewer_kind='human' AND review.decision IN ('submitted','approved')
  )>=2) independently_human_reviewed_tasks,
  count(DISTINCT item.id) FILTER (WHERE EXISTS (
    SELECT 1 FROM task_mapping_gold_review_events review
    WHERE review.gold_item_id=item.id AND review.reviewer_kind='human' AND review.is_adjudication
  )) adjudicated_tasks
FROM task_capability_gold_datasets dataset
JOIN task_capability_gold_items item ON item.gold_dataset_id=dataset.id
JOIN onet_tasks task ON task.task_id=item.onet_task_id
GROUP BY dataset.id;

COMMIT;
