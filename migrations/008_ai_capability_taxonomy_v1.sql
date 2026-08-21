BEGIN;

CREATE TABLE ai_capability_taxonomy_versions (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  scale_min NUMERIC(6,3) NOT NULL DEFAULT 0,
  scale_max NUMERIC(6,3) NOT NULL DEFAULT 100,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  methodology_version TEXT NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (scale_min < scale_max)
);

CREATE TABLE ai_capability_definitions (
  id BIGSERIAL PRIMARY KEY,
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  capability_category TEXT NOT NULL,
  definition_version INTEGER NOT NULL DEFAULT 1 CHECK (definition_version > 0),
  parent_definition_id BIGINT REFERENCES ai_capability_definitions(id),
  supersedes_definition_id BIGINT REFERENCES ai_capability_definitions(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (taxonomy_version_id, slug, definition_version)
);

CREATE TABLE task_capability_mapping_sets (
  id BIGSERIAL PRIMARY KEY,
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id) ON DELETE CASCADE,
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  mapping_set_version TEXT NOT NULL,
  mapping_method TEXT NOT NULL CHECK (mapping_method IN ('human_expert','rule_assisted','model_assisted','architecture_test_fixture')),
  mapping_method_version TEXT NOT NULL,
  review_state TEXT NOT NULL CHECK (review_state IN ('draft','test_validated','pending_review','reviewed','rejected','retired')),
  supersedes_mapping_set_id BIGINT REFERENCES task_capability_mapping_sets(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_test_fixture BOOLEAN NOT NULL DEFAULT false,
  created_by TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (onet_task_id, taxonomy_version_id, mapping_set_version)
);

CREATE TABLE task_capability_requirement_mappings (
  id BIGSERIAL PRIMARY KEY,
  mapping_set_id BIGINT NOT NULL REFERENCES task_capability_mapping_sets(id) ON DELETE CASCADE,
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  weight NUMERIC(8,7) NOT NULL CHECK (weight > 0 AND weight <= 1),
  required_capability_level NUMERIC(6,3) NOT NULL CHECK (required_capability_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  rationale TEXT NOT NULL DEFAULT '',
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (mapping_set_id, capability_definition_id)
);

CREATE TABLE task_environment_taxonomy_versions (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  methodology_version TEXT NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_environment_constraint_definitions (
  id BIGSERIAL PRIMARY KEY,
  environment_taxonomy_version_id BIGINT NOT NULL REFERENCES task_environment_taxonomy_versions(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  constraint_category TEXT NOT NULL,
  value_semantics TEXT NOT NULL,
  definition_version INTEGER NOT NULL DEFAULT 1 CHECK (definition_version > 0),
  supersedes_definition_id BIGINT REFERENCES task_environment_constraint_definitions(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (environment_taxonomy_version_id, slug, definition_version)
);

CREATE TABLE task_environment_constraint_mappings (
  id BIGSERIAL PRIMARY KEY,
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id) ON DELETE CASCADE,
  constraint_definition_id BIGINT NOT NULL REFERENCES task_environment_constraint_definitions(id),
  mapping_version TEXT NOT NULL,
  constraint_level NUMERIC(6,3) NOT NULL CHECK (constraint_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  mapping_method TEXT NOT NULL CHECK (mapping_method IN ('human_expert','rule_assisted','model_assisted','architecture_test_fixture')),
  mapping_method_version TEXT NOT NULL,
  review_state TEXT NOT NULL CHECK (review_state IN ('draft','test_validated','pending_review','reviewed','rejected','retired')),
  supersedes_mapping_id BIGINT REFERENCES task_environment_constraint_mappings(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_test_fixture BOOLEAN NOT NULL DEFAULT false,
  created_by TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (onet_task_id, constraint_definition_id, mapping_version)
);

CREATE TABLE ai_capability_benchmark_snapshots (
  id BIGSERIAL PRIMARY KEY,
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  snapshot_version TEXT NOT NULL,
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  model_version TEXT NOT NULL,
  benchmark_method TEXT NOT NULL,
  benchmark_method_version TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  published_at TIMESTAMPTZ,
  retrieved_at TIMESTAMPTZ,
  expected_capability_count INTEGER NOT NULL CHECK (expected_capability_count >= 0),
  review_state TEXT NOT NULL CHECK (review_state IN ('draft','test_validated','pending_review','reviewed','rejected','retired')),
  supersedes_snapshot_id BIGINT REFERENCES ai_capability_benchmark_snapshots(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_test_fixture BOOLEAN NOT NULL DEFAULT false,
  created_by TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (taxonomy_version_id, provider_name, model_name, model_version, snapshot_version)
);

CREATE TABLE ai_capability_benchmark_scores (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES ai_capability_benchmark_snapshots(id) ON DELETE CASCADE,
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  capability_level NUMERIC(6,3) NOT NULL CHECK (capability_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  sample_size INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
  standard_error NUMERIC CHECK (standard_error IS NULL OR standard_error >= 0),
  lower_ci NUMERIC(6,3) CHECK (lower_ci IS NULL OR lower_ci BETWEEN 0 AND 100),
  upper_ci NUMERIC(6,3) CHECK (upper_ci IS NULL OR upper_ci BETWEEN 0 AND 100),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (lower_ci IS NULL OR upper_ci IS NULL OR lower_ci <= upper_ci),
  UNIQUE (snapshot_id, capability_definition_id)
);

CREATE TABLE task_ai_enrichment_assessments (
  id BIGSERIAL PRIMARY KEY,
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id) ON DELETE CASCADE,
  taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  capability_mapping_set_id BIGINT REFERENCES task_capability_mapping_sets(id),
  benchmark_snapshot_id BIGINT REFERENCES ai_capability_benchmark_snapshots(id),
  assessment_version TEXT NOT NULL,
  ai_capability_fit NUMERIC(6,3) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(6,3) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(6,3) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  assessment_method TEXT NOT NULL,
  assessment_method_version TEXT NOT NULL,
  review_state TEXT NOT NULL CHECK (review_state IN ('draft','test_validated','pending_review','reviewed','rejected','retired')),
  supersedes_assessment_id BIGINT REFERENCES task_ai_enrichment_assessments(id),
  input_versions JSONB NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  is_test_fixture BOOLEAN NOT NULL DEFAULT false,
  created_by TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (onet_task_id, taxonomy_version_id, assessment_version)
);

CREATE OR REPLACE FUNCTION validate_task_capability_mapping_set(set_id BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  set_row task_capability_mapping_sets%ROWTYPE;
  total NUMERIC;
  mapping_count INTEGER;
  invalid_versions INTEGER;
BEGIN
  SELECT * INTO set_row FROM task_capability_mapping_sets WHERE id=set_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown task capability mapping set %', set_id; END IF;
  IF (SELECT status FROM ai_capability_taxonomy_versions WHERE id=set_row.taxonomy_version_id)='retired' THEN
    RAISE EXCEPTION 'Mapping set % references retired taxonomy', set_id;
  END IF;
  SELECT count(*), coalesce(sum(weight),0), count(*) FILTER (
    WHERE definition.taxonomy_version_id<>set_row.taxonomy_version_id
  ) INTO mapping_count,total,invalid_versions
  FROM task_capability_requirement_mappings mapping
  JOIN ai_capability_definitions definition ON definition.id=mapping.capability_definition_id
  WHERE mapping.mapping_set_id=set_id;
  IF invalid_versions>0 THEN RAISE EXCEPTION 'Mapping set % mixes taxonomy versions', set_id; END IF;
  IF set_row.review_state IN ('test_validated','reviewed') AND (mapping_count=0 OR abs(total-1)>0.000001) THEN
    RAISE EXCEPTION 'Mapping set % weights must sum to 1; got %', set_id, total;
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION validate_benchmark_snapshot(snapshot_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  snapshot_row ai_capability_benchmark_snapshots%ROWTYPE;
  actual_count INTEGER;
  invalid_versions INTEGER;
BEGIN
  SELECT * INTO snapshot_row FROM ai_capability_benchmark_snapshots WHERE id=snapshot_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown benchmark snapshot %', snapshot_key; END IF;
  SELECT count(*), count(*) FILTER (
    WHERE definition.taxonomy_version_id<>snapshot_row.taxonomy_version_id
  ) INTO actual_count,invalid_versions
  FROM ai_capability_benchmark_scores score
  JOIN ai_capability_definitions definition ON definition.id=score.capability_definition_id
  WHERE score.snapshot_id=snapshot_key;
  IF invalid_versions>0 THEN RAISE EXCEPTION 'Benchmark snapshot % mixes taxonomy versions', snapshot_key; END IF;
  IF snapshot_row.review_state IN ('test_validated','reviewed') AND actual_count<>snapshot_row.expected_capability_count THEN
    RAISE EXCEPTION 'Benchmark snapshot % expected % scores, found %', snapshot_key, snapshot_row.expected_capability_count, actual_count;
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION enforce_task_capability_mapping_set()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  PERFORM validate_task_capability_mapping_set(NEW.mapping_set_id);
  RETURN NEW;
END $$;

CREATE CONSTRAINT TRIGGER task_capability_mapping_rows_reconcile
AFTER INSERT ON task_capability_requirement_mappings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_task_capability_mapping_set();

CREATE OR REPLACE FUNCTION enforce_mapping_set_row()
RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_capability_mapping_set(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER task_capability_mapping_sets_reconcile
AFTER INSERT ON task_capability_mapping_sets
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_mapping_set_row();

CREATE OR REPLACE FUNCTION enforce_benchmark_snapshot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  PERFORM validate_benchmark_snapshot(NEW.snapshot_id);
  RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER benchmark_scores_reconcile
AFTER INSERT ON ai_capability_benchmark_scores
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_benchmark_snapshot();

CREATE OR REPLACE FUNCTION enforce_benchmark_snapshot_row()
RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_benchmark_snapshot(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER benchmark_snapshots_reconcile
AFTER INSERT ON ai_capability_benchmark_snapshots
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_benchmark_snapshot_row();

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI AI Capability Taxonomy','internal://jobsvsai/ai-capability-taxonomy','v1',
    '{"owner":"JobsVsAI","layer":"private_enrichment","production_scoring":false}'::jsonb)
  ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,metadata=EXCLUDED.metadata
  RETURNING id
)
INSERT INTO ai_capability_taxonomy_versions (
  version,name,description,status,source_id,methodology_version,provenance,created_by
)
SELECT 'jvs-ai-cap-v1','JobsVsAI AI Capability Taxonomy v1',
  'Draft capability requirements taxonomy. Definitions only; no benchmark or production score values.',
  'draft',id,'ai-capability-methodology-v1',
  '{"seed":"architecture_definition_only","not_for_production_scoring":true}'::jsonb,'system:migration-008'
FROM source;

INSERT INTO ai_capability_definitions (
  taxonomy_version_id,slug,name,description,capability_category,source_id,evidence,provenance,created_by
)
SELECT taxonomy.id,item.slug,item.name,item.description,item.category,taxonomy.source_id,
  '[]'::jsonb,'{"seed":"taxonomy_v1_definition"}'::jsonb,'system:migration-008'
FROM ai_capability_taxonomy_versions taxonomy
CROSS JOIN (VALUES
  ('language-comprehension','Language comprehension','Understand and interpret written or spoken language and instructions.','cognitive'),
  ('language-generation','Language generation','Produce coherent written or spoken language for a specified purpose.','generative'),
  ('information-retrieval','Information retrieval','Locate, select, and synthesize relevant information from available sources.','cognitive'),
  ('quantitative-reasoning','Quantitative reasoning','Apply mathematical, statistical, and quantitative reasoning.','cognitive'),
  ('general-reasoning','General reasoning and problem-solving','Analyze unfamiliar situations, infer relationships, and solve problems.','cognitive'),
  ('software-code-generation','Software and code generation','Create, modify, debug, or explain software and machine-readable instructions.','digital-action'),
  ('visual-understanding','Visual understanding','Interpret images, diagrams, spatial layouts, and visual evidence.','perception'),
  ('visual-content-generation','Visual and content generation','Create or transform images, layouts, graphics, and multimodal content.','generative'),
  ('planning-workflow-execution','Planning and workflow execution','Sequence goals, coordinate steps, and monitor multi-step work.','agentic'),
  ('tool-computer-operation','Tool and computer operation','Operate software interfaces, tools, and digital systems to complete actions.','digital-action'),
  ('interpersonal-social-interaction','Interpersonal and social interaction','Interpret social context and communicate appropriately with people.','human-interaction'),
  ('persuasion-negotiation','Persuasion and negotiation','Influence, negotiate, resolve objections, and align stakeholders.','human-interaction'),
  ('physical-perception','Physical perception','Sense and interpret real-world physical conditions beyond supplied digital inputs.','embodied'),
  ('fine-physical-manipulation','Fine physical manipulation','Perform precise physical handling and dexterous manipulation.','embodied'),
  ('mobility-real-world-operation','Mobility and real-world operation','Navigate and act safely in changing physical environments.','embodied')
) AS item(slug,name,description,category)
WHERE taxonomy.version='jvs-ai-cap-v1';

INSERT INTO task_environment_taxonomy_versions (
  version,name,description,status,source_id,methodology_version,provenance,created_by
)
SELECT 'jvs-task-env-v1','JobsVsAI Task Environment Constraints v1',
  'Draft constraints that separate capability fit from real-world automation feasibility.',
  'draft',source_id,'task-environment-methodology-v1',
  '{"seed":"architecture_definition_only","not_for_production_scoring":true}'::jsonb,'system:migration-008'
FROM ai_capability_taxonomy_versions WHERE version='jvs-ai-cap-v1';

INSERT INTO task_environment_constraint_definitions (
  environment_taxonomy_version_id,slug,name,description,constraint_category,value_semantics,
  source_id,provenance,created_by
)
SELECT taxonomy.id,item.slug,item.name,item.description,item.category,
  '0 means no material constraint; 100 means the constraint strongly limits end-to-end automation.',
  taxonomy.source_id,'{"seed":"constraint_v1_definition"}'::jsonb,'system:migration-008'
FROM task_environment_taxonomy_versions taxonomy
CROSS JOIN (VALUES
  ('physical-presence','Physical presence','Requires a person or machine to be physically present.','embodiment'),
  ('fine-motor-control','Fine motor control','Requires precise dexterous physical manipulation.','embodiment'),
  ('mobility','Mobility','Requires navigation through a changing real-world environment.','embodiment'),
  ('real-world-sensing','Real-world sensing','Depends on physical sensing not fully represented in digital inputs.','embodiment'),
  ('synchronous-human-interaction','Synchronous human interaction','Requires live reciprocal interaction, trust, or social adaptation.','human'),
  ('legal-accountability','Legal accountability','Requires a legally accountable human decision-maker or signatory.','governance'),
  ('safety-criticality','Safety criticality','Errors can create serious health, safety, or physical consequences.','risk'),
  ('tool-access','Tool access','Requires controlled access to tools, software, equipment, or credentials.','integration'),
  ('data-access','Data access','Depends on unavailable, restricted, or privacy-sensitive data.','integration'),
  ('workflow-integration','Workflow integration','Requires coordination across systems, actors, and organizational processes.','integration')
) AS item(slug,name,description,category)
WHERE taxonomy.version='jvs-task-env-v1';

DO $$
DECLARE
  taxonomy_id BIGINT;
  source_key BIGINT;
  set_key BIGINT;
  test_task BIGINT;
BEGIN
  SELECT id,source_id INTO taxonomy_id,source_key FROM ai_capability_taxonomy_versions WHERE version='jvs-ai-cap-v1';
  FOREACH test_task IN ARRAY ARRAY[299::bigint,21662::bigint,18382::bigint] LOOP
    IF EXISTS (SELECT 1 FROM onet_tasks WHERE task_id=test_task AND is_current) THEN
      INSERT INTO task_capability_mapping_sets (
        onet_task_id,taxonomy_version_id,mapping_set_version,mapping_method,
        mapping_method_version,review_state,source_id,evidence,provenance,is_test_fixture,created_by
      ) VALUES (test_task,taxonomy_id,'architecture-test-v1','architecture_test_fixture',
        'fixture-rules-v1','test_validated',source_key,
        '[{"type":"architecture_test_fixture","not_for_scoring":true}]'::jsonb,
        '{"purpose":"schema_validation_only"}'::jsonb,true,'system:migration-008') RETURNING id INTO set_key;

      IF test_task=299 THEN
        INSERT INTO task_capability_requirement_mappings (mapping_set_id,capability_definition_id,weight,required_capability_level,confidence,rationale,evidence,provenance,source_id,created_by)
        SELECT set_key,definition.id,item.weight,item.level,70,'Architecture test fixture only','[{"not_for_scoring":true}]'::jsonb,'{"fixture":true}'::jsonb,source_key,'system:migration-008'
        FROM (VALUES ('visual-content-generation',0.45::numeric,75::numeric),('planning-workflow-execution',0.20,55),('visual-understanding',0.15,60),('general-reasoning',0.20,60)) item(slug,weight,level)
        JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy_id AND definition.slug=item.slug;
      ELSIF test_task=21662 THEN
        INSERT INTO task_capability_requirement_mappings (mapping_set_id,capability_definition_id,weight,required_capability_level,confidence,rationale,evidence,provenance,source_id,created_by)
        SELECT set_key,definition.id,item.weight,item.level,70,'Architecture test fixture only','[{"not_for_scoring":true}]'::jsonb,'{"fixture":true}'::jsonb,source_key,'system:migration-008'
        FROM (VALUES ('language-comprehension',0.25::numeric,65::numeric),('quantitative-reasoning',0.15,55),('general-reasoning',0.35,75),('planning-workflow-execution',0.25,65)) item(slug,weight,level)
        JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy_id AND definition.slug=item.slug;
      ELSE
        INSERT INTO task_capability_requirement_mappings (mapping_set_id,capability_definition_id,weight,required_capability_level,confidence,rationale,evidence,provenance,source_id,created_by)
        SELECT set_key,definition.id,item.weight,item.level,65,'Architecture test fixture only','[{"not_for_scoring":true}]'::jsonb,'{"fixture":true}'::jsonb,source_key,'system:migration-008'
        FROM (VALUES ('language-comprehension',0.20::numeric,70::numeric),('general-reasoning',0.35,85),('information-retrieval',0.15,65),('visual-understanding',0.15,65),('interpersonal-social-interaction',0.15,70)) item(slug,weight,level)
        JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=taxonomy_id AND definition.slug=item.slug;
      END IF;
    END IF;
  END LOOP;
END $$;

INSERT INTO task_environment_constraint_mappings (
  onet_task_id,constraint_definition_id,mapping_version,constraint_level,confidence,
  mapping_method,mapping_method_version,review_state,source_id,evidence,provenance,
  is_test_fixture,created_by
)
SELECT fixture.task_id,definition.id,'architecture-test-v1',fixture.level,65,
  'architecture_test_fixture','fixture-rules-v1','test_validated',taxonomy.source_id,
  '[{"type":"architecture_test_fixture","not_for_scoring":true}]'::jsonb,
  '{"purpose":"schema_validation_only"}'::jsonb,true,'system:migration-008'
FROM task_environment_taxonomy_versions taxonomy
JOIN (VALUES
  (299::bigint,'synchronous-human-interaction',25::numeric),(299::bigint,'tool-access',35::numeric),
  (21662::bigint,'workflow-integration',55::numeric),(21662::bigint,'data-access',45::numeric),
  (18382::bigint,'legal-accountability',90::numeric),(18382::bigint,'safety-criticality',95::numeric),
  (18382::bigint,'synchronous-human-interaction',75::numeric)
) fixture(task_id,slug,level) ON EXISTS (SELECT 1 FROM onet_tasks WHERE task_id=fixture.task_id AND is_current)
JOIN task_environment_constraint_definitions definition
  ON definition.environment_taxonomy_version_id=taxonomy.id AND definition.slug=fixture.slug
WHERE taxonomy.version='jvs-task-env-v1';

CREATE OR REPLACE VIEW ai_enrichment_validation AS
SELECT
  (SELECT count(*) FROM task_capability_mapping_sets mapping_set
    WHERE mapping_set.review_state IN ('test_validated','reviewed') AND NOT validate_task_capability_mapping_set(mapping_set.id)) invalid_mapping_sets,
  (SELECT count(*) FROM ai_capability_benchmark_snapshots snapshot
    WHERE snapshot.review_state IN ('test_validated','reviewed') AND NOT validate_benchmark_snapshot(snapshot.id)) invalid_snapshots,
  (SELECT count(*) FROM task_ai_enrichment_assessments) task_assessments,
  (SELECT count(*) FROM ai_capability_benchmark_scores) benchmark_scores,
  (SELECT count(*) FROM occupation_scores) production_score_rows,
  (SELECT count(*) FROM task_ai_scores) legacy_task_ai_score_rows;

CREATE OR REPLACE FUNCTION prevent_ai_enrichment_history_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only; create a new version using supersedes_*', TG_TABLE_NAME;
END $$;

CREATE TRIGGER capability_definitions_append_only BEFORE UPDATE OR DELETE ON ai_capability_definitions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER capability_mapping_sets_append_only BEFORE UPDATE OR DELETE ON task_capability_mapping_sets FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER capability_mappings_append_only BEFORE UPDATE OR DELETE ON task_capability_requirement_mappings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER constraint_definitions_append_only BEFORE UPDATE OR DELETE ON task_environment_constraint_definitions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER constraint_mappings_append_only BEFORE UPDATE OR DELETE ON task_environment_constraint_mappings FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER benchmark_snapshots_append_only BEFORE UPDATE OR DELETE ON ai_capability_benchmark_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER benchmark_scores_append_only BEFORE UPDATE OR DELETE ON ai_capability_benchmark_scores FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER task_assessments_append_only BEFORE UPDATE OR DELETE ON task_ai_enrichment_assessments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
