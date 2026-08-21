BEGIN;

CREATE TABLE task_mapping_rubric_versions (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','review','active','retired')),
  capability_taxonomy_version_id BIGINT NOT NULL REFERENCES ai_capability_taxonomy_versions(id),
  environment_taxonomy_version_id BIGINT NOT NULL REFERENCES task_environment_taxonomy_versions(id),
  minimum_meaningful_weight NUMERIC(8,7) NOT NULL CHECK (minimum_meaningful_weight > 0 AND minimum_meaningful_weight <= 1),
  dominant_weight_threshold NUMERIC(8,7) NOT NULL CHECK (dominant_weight_threshold > 0 AND dominant_weight_threshold <= 1),
  maximum_capabilities_per_task INTEGER NOT NULL CHECK (maximum_capabilities_per_task > 0),
  minimum_meaningful_requirement_level NUMERIC(6,3) NOT NULL CHECK (minimum_meaningful_requirement_level BETWEEN 0 AND 100),
  minimum_meaningful_constraint_level NUMERIC(6,3) NOT NULL CHECK (minimum_meaningful_constraint_level BETWEEN 0 AND 100),
  ambiguity_confidence_ceiling NUMERIC(6,3) NOT NULL CHECK (ambiguity_confidence_ceiling BETWEEN 0 AND 100),
  normalization_tolerance NUMERIC(10,9) NOT NULL CHECK (normalization_tolerance > 0 AND normalization_tolerance < 1),
  documentation_path TEXT NOT NULL,
  decision_rules JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  supersedes_rubric_version_id BIGINT REFERENCES task_mapping_rubric_versions(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (minimum_meaningful_weight <= dominant_weight_threshold)
);

CREATE TABLE capability_requirement_scale_anchors (
  id BIGSERIAL PRIMARY KEY,
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  anchor_value INTEGER NOT NULL CHECK (anchor_value IN (0,25,50,75,100)),
  anchor_label TEXT NOT NULL,
  description TEXT NOT NULL,
  observable_evidence_rule TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rubric_version_id,capability_definition_id,anchor_value)
);

CREATE TABLE environment_constraint_scale_anchors (
  id BIGSERIAL PRIMARY KEY,
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  constraint_definition_id BIGINT NOT NULL REFERENCES task_environment_constraint_definitions(id),
  anchor_value INTEGER NOT NULL CHECK (anchor_value IN (0,25,50,75,100)),
  anchor_label TEXT NOT NULL,
  description TEXT NOT NULL,
  observable_evidence_rule TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rubric_version_id,constraint_definition_id,anchor_value)
);

CREATE TABLE mapping_confidence_states (
  id BIGSERIAL PRIMARY KEY,
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  minimum_confidence NUMERIC(6,3) NOT NULL CHECK (minimum_confidence BETWEEN 0 AND 100),
  maximum_confidence NUMERIC(6,3) NOT NULL CHECK (maximum_confidence BETWEEN 0 AND 100),
  definition TEXT NOT NULL,
  review_rule TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (minimum_confidence <= maximum_confidence),
  UNIQUE (rubric_version_id,code),
  UNIQUE (rubric_version_id,id)
);

CREATE TABLE task_capability_gold_datasets (
  id BIGSERIAL PRIMARY KEY,
  rubric_version_id BIGINT NOT NULL REFERENCES task_mapping_rubric_versions(id),
  dataset_version TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','test_validated','reviewed','retired')),
  expected_task_count INTEGER NOT NULL CHECK (expected_task_count >= 0),
  supersedes_dataset_id BIGINT REFERENCES task_capability_gold_datasets(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_test_fixture BOOLEAN NOT NULL DEFAULT true,
  created_by TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rubric_version_id,dataset_version)
);

CREATE TABLE task_capability_gold_items (
  id BIGSERIAL PRIMARY KEY,
  gold_dataset_id BIGINT NOT NULL REFERENCES task_capability_gold_datasets(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  disposition TEXT NOT NULL CHECK (disposition IN ('mappable','insufficient_description','ambiguous_scope')),
  task_statement_hash TEXT NOT NULL,
  disposition_rationale TEXT NOT NULL,
  reviewer_provenance JSONB NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  reviewed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (gold_dataset_id,onet_task_id)
);

CREATE TABLE gold_task_capability_requirements (
  id BIGSERIAL PRIMARY KEY,
  gold_item_id BIGINT NOT NULL REFERENCES task_capability_gold_items(id),
  capability_definition_id BIGINT NOT NULL REFERENCES ai_capability_definitions(id),
  weight NUMERIC(8,7) NOT NULL CHECK (weight > 0 AND weight <= 1),
  required_capability_level NUMERIC(6,3) NOT NULL CHECK (required_capability_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  confidence_state_id BIGINT NOT NULL REFERENCES mapping_confidence_states(id),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (gold_item_id,capability_definition_id)
);

CREATE TABLE gold_task_environment_constraints (
  id BIGSERIAL PRIMARY KEY,
  gold_item_id BIGINT NOT NULL REFERENCES task_capability_gold_items(id),
  constraint_definition_id BIGINT NOT NULL REFERENCES task_environment_constraint_definitions(id),
  constraint_level NUMERIC(6,3) NOT NULL CHECK (constraint_level BETWEEN 0 AND 100),
  confidence NUMERIC(6,3) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  confidence_state_id BIGINT NOT NULL REFERENCES mapping_confidence_states(id),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (gold_item_id,constraint_definition_id)
);

CREATE OR REPLACE FUNCTION validate_task_mapping_rubric(rubric_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  rubric_row task_mapping_rubric_versions%ROWTYPE;
  capability_count INTEGER;
  capability_anchor_count INTEGER;
  invalid_capability_anchor_sets INTEGER;
  constraint_count INTEGER;
  constraint_anchor_count INTEGER;
  invalid_constraint_anchor_sets INTEGER;
  confidence_state_count INTEGER;
BEGIN
  SELECT * INTO rubric_row FROM task_mapping_rubric_versions WHERE id=rubric_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown mapping rubric %',rubric_key; END IF;
  IF (SELECT status FROM ai_capability_taxonomy_versions WHERE id=rubric_row.capability_taxonomy_version_id)='retired'
    OR (SELECT status FROM task_environment_taxonomy_versions WHERE id=rubric_row.environment_taxonomy_version_id)='retired' THEN
    RAISE EXCEPTION 'Rubric % references a retired taxonomy',rubric_key;
  END IF;
  SELECT count(*) INTO capability_count FROM ai_capability_definitions
    WHERE taxonomy_version_id=rubric_row.capability_taxonomy_version_id;
  SELECT count(*) INTO capability_anchor_count FROM capability_requirement_scale_anchors
    WHERE rubric_version_id=rubric_key;
  SELECT count(*) INTO invalid_capability_anchor_sets FROM (
    SELECT capability_definition_id
    FROM capability_requirement_scale_anchors WHERE rubric_version_id=rubric_key
    GROUP BY capability_definition_id
    HAVING array_agg(anchor_value ORDER BY anchor_value)<>ARRAY[0,25,50,75,100]
  ) invalid;
  SELECT count(*) INTO constraint_count FROM task_environment_constraint_definitions
    WHERE environment_taxonomy_version_id=rubric_row.environment_taxonomy_version_id;
  SELECT count(*) INTO constraint_anchor_count FROM environment_constraint_scale_anchors
    WHERE rubric_version_id=rubric_key;
  SELECT count(*) INTO invalid_constraint_anchor_sets FROM (
    SELECT constraint_definition_id
    FROM environment_constraint_scale_anchors WHERE rubric_version_id=rubric_key
    GROUP BY constraint_definition_id
    HAVING array_agg(anchor_value ORDER BY anchor_value)<>ARRAY[0,25,50,75,100]
  ) invalid;
  SELECT count(*) INTO confidence_state_count FROM mapping_confidence_states WHERE rubric_version_id=rubric_key;
  IF rubric_row.status IN ('review','active') AND (
    capability_count<>15 OR capability_anchor_count<>capability_count*5 OR invalid_capability_anchor_sets>0
    OR constraint_count<>10 OR constraint_anchor_count<>constraint_count*5 OR invalid_constraint_anchor_sets>0
    OR confidence_state_count<>5
  ) THEN RAISE EXCEPTION 'Rubric % scale anchors or confidence states do not reconcile',rubric_key; END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION validate_task_capability_gold_dataset(dataset_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  dataset_row task_capability_gold_datasets%ROWTYPE;
  rubric_row task_mapping_rubric_versions%ROWTYPE;
  actual_items INTEGER;
  invalid_items INTEGER;
BEGIN
  SELECT * INTO dataset_row FROM task_capability_gold_datasets WHERE id=dataset_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown gold dataset %',dataset_key; END IF;
  SELECT * INTO rubric_row FROM task_mapping_rubric_versions WHERE id=dataset_row.rubric_version_id;
  SELECT count(*) INTO actual_items FROM task_capability_gold_items WHERE gold_dataset_id=dataset_key;
  SELECT count(*) INTO invalid_items
  FROM task_capability_gold_items item
  LEFT JOIN LATERAL (
    SELECT count(*) capability_count,coalesce(sum(requirement.weight),0) total_weight,
      count(*) FILTER (WHERE requirement.weight<rubric_row.minimum_meaningful_weight
        OR requirement.required_capability_level<rubric_row.minimum_meaningful_requirement_level) threshold_errors,
      count(*) FILTER (WHERE capability.taxonomy_version_id<>rubric_row.capability_taxonomy_version_id) version_errors,
      count(*) FILTER (WHERE requirement.confidence<state.minimum_confidence
        OR requirement.confidence>state.maximum_confidence
        OR state.rubric_version_id<>dataset_row.rubric_version_id) confidence_errors
    FROM gold_task_capability_requirements requirement
    JOIN ai_capability_definitions capability ON capability.id=requirement.capability_definition_id
    JOIN mapping_confidence_states state ON state.id=requirement.confidence_state_id
    WHERE requirement.gold_item_id=item.id
  ) capability_summary ON true
  LEFT JOIN LATERAL (
    SELECT count(*) constraint_count,
      count(*) FILTER (WHERE constraint_mapping.constraint_level<rubric_row.minimum_meaningful_constraint_level) threshold_errors,
      count(*) FILTER (WHERE definition.environment_taxonomy_version_id<>rubric_row.environment_taxonomy_version_id) version_errors,
      count(*) FILTER (WHERE constraint_mapping.confidence<state.minimum_confidence
        OR constraint_mapping.confidence>state.maximum_confidence
        OR state.rubric_version_id<>dataset_row.rubric_version_id) confidence_errors
    FROM gold_task_environment_constraints constraint_mapping
    JOIN task_environment_constraint_definitions definition ON definition.id=constraint_mapping.constraint_definition_id
    JOIN mapping_confidence_states state ON state.id=constraint_mapping.confidence_state_id
    WHERE constraint_mapping.gold_item_id=item.id
  ) constraint_summary ON true
  WHERE item.gold_dataset_id=dataset_key AND (
    jsonb_typeof(item.reviewer_provenance)<>'array'
    OR jsonb_array_length(item.reviewer_provenance)<2
    OR (item.disposition='mappable' AND (
      capability_summary.capability_count=0
      OR abs(capability_summary.total_weight-1)>rubric_row.normalization_tolerance
      OR capability_summary.capability_count>rubric_row.maximum_capabilities_per_task))
    OR (item.disposition<>'mappable' AND (
      capability_summary.capability_count>0 OR constraint_summary.constraint_count>0))
    OR capability_summary.threshold_errors>0 OR capability_summary.version_errors>0
    OR capability_summary.confidence_errors>0 OR constraint_summary.threshold_errors>0 OR constraint_summary.version_errors>0
    OR constraint_summary.confidence_errors>0
  );
  IF dataset_row.status IN ('test_validated','reviewed') AND actual_items<>dataset_row.expected_task_count THEN
    RAISE EXCEPTION 'Gold dataset % expected % tasks, found %',dataset_key,dataset_row.expected_task_count,actual_items;
  END IF;
  IF dataset_row.status IN ('test_validated','reviewed') AND invalid_items>0 THEN
    RAISE EXCEPTION 'Gold dataset % has % invalid task items',dataset_key,invalid_items;
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION compare_task_mapping_to_gold(candidate_mapping_set_key BIGINT,gold_dataset_key BIGINT)
RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
  candidate task_capability_mapping_sets%ROWTYPE;
  dataset task_capability_gold_datasets%ROWTYPE;
  rubric task_mapping_rubric_versions%ROWTYPE;
  gold_item task_capability_gold_items%ROWTYPE;
  capability_report JSONB;
  constraint_report JSONB;
  summary JSONB;
BEGIN
  SELECT * INTO candidate FROM task_capability_mapping_sets WHERE id=candidate_mapping_set_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown candidate mapping set %',candidate_mapping_set_key; END IF;
  SELECT * INTO dataset FROM task_capability_gold_datasets WHERE id=gold_dataset_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown gold dataset %',gold_dataset_key; END IF;
  SELECT * INTO rubric FROM task_mapping_rubric_versions WHERE id=dataset.rubric_version_id;
  IF candidate.taxonomy_version_id<>rubric.capability_taxonomy_version_id THEN
    RAISE EXCEPTION 'Candidate taxonomy does not match gold rubric taxonomy';
  END IF;
  SELECT * INTO gold_item FROM task_capability_gold_items
    WHERE gold_dataset_id=gold_dataset_key AND onet_task_id=candidate.onet_task_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'No gold item for candidate task %',candidate.onet_task_id; END IF;
  IF gold_item.disposition<>'mappable' THEN RAISE EXCEPTION 'Gold item for task % is %, not mappable',candidate.onet_task_id,gold_item.disposition; END IF;

  WITH candidate_rows AS (
    SELECT capability_definition_id,weight,required_capability_level,confidence
    FROM task_capability_requirement_mappings WHERE mapping_set_id=candidate_mapping_set_key
  ),gold_rows AS (
    SELECT requirement.capability_definition_id,requirement.weight,requirement.required_capability_level,
      requirement.confidence,state.code confidence_state
    FROM gold_task_capability_requirements requirement
    JOIN mapping_confidence_states state ON state.id=requirement.confidence_state_id
    WHERE requirement.gold_item_id=gold_item.id
  ),deviations AS (
    SELECT definition.slug,definition.name,
      coalesce(candidate_rows.weight,0) candidate_weight,coalesce(gold_rows.weight,0) gold_weight,
      abs(coalesce(candidate_rows.weight,0)-coalesce(gold_rows.weight,0)) weight_deviation,
      candidate_rows.required_capability_level candidate_level,gold_rows.required_capability_level gold_level,
      CASE WHEN candidate_rows.required_capability_level IS NULL OR gold_rows.required_capability_level IS NULL THEN NULL ELSE abs(candidate_rows.required_capability_level-gold_rows.required_capability_level) END level_deviation,
      candidate_rows.confidence candidate_confidence,gold_rows.confidence gold_confidence,
      CASE WHEN candidate_rows.confidence IS NULL OR gold_rows.confidence IS NULL THEN NULL ELSE abs(candidate_rows.confidence-gold_rows.confidence) END confidence_deviation,
      gold_rows.confidence_state gold_confidence_state,
      CASE WHEN candidate_rows.capability_definition_id IS NULL THEN 'missing' WHEN gold_rows.capability_definition_id IS NULL THEN 'extra' ELSE 'matched' END presence
    FROM candidate_rows FULL JOIN gold_rows USING (capability_definition_id)
    JOIN ai_capability_definitions definition ON definition.id=coalesce(candidate_rows.capability_definition_id,gold_rows.capability_definition_id)
  )
  SELECT coalesce(jsonb_agg(to_jsonb(deviations) ORDER BY weight_deviation DESC,slug),'[]'::jsonb) INTO capability_report FROM deviations;

  WITH latest_candidate AS (
    SELECT DISTINCT ON (mapping.constraint_definition_id)
      mapping.constraint_definition_id,mapping.constraint_level,mapping.confidence
    FROM task_environment_constraint_mappings mapping
    JOIN task_environment_constraint_definitions definition ON definition.id=mapping.constraint_definition_id
    WHERE mapping.onet_task_id=candidate.onet_task_id
      AND definition.environment_taxonomy_version_id=rubric.environment_taxonomy_version_id
      AND mapping.review_state NOT IN ('rejected','retired')
    ORDER BY mapping.constraint_definition_id,mapping.created_at DESC,mapping.id DESC
  ),gold_rows AS (
    SELECT constraint_mapping.constraint_definition_id,constraint_mapping.constraint_level,
      constraint_mapping.confidence,state.code confidence_state
    FROM gold_task_environment_constraints constraint_mapping
    JOIN mapping_confidence_states state ON state.id=constraint_mapping.confidence_state_id
    WHERE constraint_mapping.gold_item_id=gold_item.id
  ),deviations AS (
    SELECT definition.slug,definition.name,
      coalesce(latest_candidate.constraint_level,0) candidate_level,coalesce(gold_rows.constraint_level,0) gold_level,
      abs(coalesce(latest_candidate.constraint_level,0)-coalesce(gold_rows.constraint_level,0)) level_deviation,
      latest_candidate.confidence candidate_confidence,gold_rows.confidence gold_confidence,
      CASE WHEN latest_candidate.confidence IS NULL OR gold_rows.confidence IS NULL THEN NULL ELSE abs(latest_candidate.confidence-gold_rows.confidence) END confidence_deviation,
      gold_rows.confidence_state gold_confidence_state,
      CASE WHEN latest_candidate.constraint_definition_id IS NULL THEN 'missing' WHEN gold_rows.constraint_definition_id IS NULL THEN 'extra' ELSE 'matched' END presence
    FROM latest_candidate FULL JOIN gold_rows USING (constraint_definition_id)
    JOIN task_environment_constraint_definitions definition ON definition.id=coalesce(latest_candidate.constraint_definition_id,gold_rows.constraint_definition_id)
  )
  SELECT coalesce(jsonb_agg(to_jsonb(deviations) ORDER BY level_deviation DESC,slug),'[]'::jsonb) INTO constraint_report FROM deviations;

  WITH cap AS (SELECT * FROM jsonb_to_recordset(capability_report) AS x(weight_deviation NUMERIC,level_deviation NUMERIC,confidence_deviation NUMERIC,presence TEXT)),
  env AS (SELECT * FROM jsonb_to_recordset(constraint_report) AS x(level_deviation NUMERIC,confidence_deviation NUMERIC,presence TEXT)),
  candidate_stats AS (SELECT count(*) capability_count,coalesce(sum(weight),0) weight_total,count(*) FILTER (WHERE weight<rubric.minimum_meaningful_weight OR required_capability_level<rubric.minimum_meaningful_requirement_level) threshold_violations FROM task_capability_requirement_mappings WHERE mapping_set_id=candidate_mapping_set_key)
  SELECT jsonb_build_object(
    'meanAbsoluteWeightDeviation',coalesce(round(avg(cap.weight_deviation),7),0),
    'meanAbsoluteLevelDeviation',coalesce(round(avg(cap.level_deviation),3),0),
    'meanAbsoluteCapabilityConfidenceDeviation',coalesce(round(avg(cap.confidence_deviation),3),0),
    'meanAbsoluteConstraintDeviation',(SELECT coalesce(round(avg(env.level_deviation),3),0) FROM env),
    'meanAbsoluteConstraintConfidenceDeviation',(SELECT coalesce(round(avg(env.confidence_deviation),3),0) FROM env),
    'missingCapabilities',count(*) FILTER (WHERE cap.presence='missing'),
    'extraCapabilities',count(*) FILTER (WHERE cap.presence='extra'),
    'candidateWeightTotal',(SELECT weight_total FROM candidate_stats),
    'thresholdViolations',(SELECT threshold_violations FROM candidate_stats),
    'maximumCapabilityCountExceeded',(SELECT capability_count>rubric.maximum_capabilities_per_task FROM candidate_stats)
  ) INTO summary FROM cap;

  RETURN jsonb_build_object(
    'rubricVersion',rubric.version,'goldDatasetVersion',dataset.dataset_version,
    'candidateMappingSetId',candidate.id,'onetTaskId',candidate.onet_task_id,
    'capabilityDeviations',capability_report,'constraintDeviations',constraint_report,'summary',summary
  );
END $$;

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI Task-to-Capability Mapping Rubric','internal://jobsvsai/task-capability-rubric','v1',
    '{"owner":"JobsVsAI","layer":"validation_infrastructure","production_scoring":false}'::jsonb)
  ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,metadata=EXCLUDED.metadata
  RETURNING id
)
INSERT INTO task_mapping_rubric_versions (
  version,name,description,status,capability_taxonomy_version_id,environment_taxonomy_version_id,
  minimum_meaningful_weight,dominant_weight_threshold,maximum_capabilities_per_task,
  minimum_meaningful_requirement_level,minimum_meaningful_constraint_level,ambiguity_confidence_ceiling,normalization_tolerance,
  documentation_path,decision_rules,source_id,provenance,created_by
)
SELECT 'jvs-task-capability-rubric-v1','JobsVsAI Task-to-Capability Mapping Rubric v1',
  'Draft annotation and validation rubric; it does not generate mappings or feed production scoring.',
  'review',capability.id,environment.id,0.05,0.40,6,10,10,49,0.000001,
  'enrichment/TASK_TO_CAPABILITY_MAPPING_RUBRIC_V1.md',
  '{"weighting":{"normalize_to":1,"minimum_meaningful_weight":0.05,"dominant_threshold":0.40,"maximum_dimensions":6},"description_policy":{"insufficient":"record disposition; create no requirement or constraint values","ambiguous":"record disposition or cap confidence at 49; do not infer missing context"},"interpolation":"interpolate between adjacent 0/25/50/75/100 anchors only when task evidence supports it"}'::jsonb,
  source.id,'{"seed":"rubric_definition_and_test_gold_only","not_for_production_scoring":true}'::jsonb,'system:migration-010'
FROM source
JOIN ai_capability_taxonomy_versions capability ON capability.version='jvs-ai-cap-v1'
JOIN task_environment_taxonomy_versions environment ON environment.version='jvs-task-env-v1';

INSERT INTO mapping_confidence_states (rubric_version_id,code,name,minimum_confidence,maximum_confidence,definition,review_rule,source_id,provenance,created_by)
SELECT rubric.id,state.code,state.name,state.minimum,state.maximum,state.definition,state.review_rule,rubric.source_id,
  '{"seed":"rubric_v1_confidence_state"}'::jsonb,'system:migration-010'
FROM task_mapping_rubric_versions rubric
CROSS JOIN (VALUES
  ('insufficient_evidence','Insufficient evidence',0,24,'The statement does not support a defensible value.','Do not include in a reviewed mapping; use an insufficient or ambiguous disposition.'),
  ('low','Low',25,49,'A plausible interpretation depends on material assumptions.','Require a second reviewer and record the assumption; ambiguous task-level evidence cannot exceed 49.'),
  ('moderate','Moderate',50,74,'The statement supports the mapping, with limited uncertainty about scope or level.','Second-reviewer confirmation is required for gold data.'),
  ('high','High',75,89,'The requirement or constraint is explicit and its level is well supported.','Document the task phrase supporting the anchor selection.'),
  ('expert_consensus','Expert consensus',90,100,'Multiple qualified reviewers independently agree and evidence is explicit.','Requires independent annotations and adjudication provenance.')
) state(code,name,minimum,maximum,definition,review_rule)
WHERE rubric.version='jvs-task-capability-rubric-v1';

WITH dimensions(slug,a0,a25,a50,a75,a100) AS (VALUES
  ('language-comprehension','No language input must be understood.','Understand short, explicit instructions or labels.','Interpret ordinary multi-sentence material with context.','Resolve technical, nuanced, or cross-document meaning.','Expert interpretation of highly ambiguous or consequential language defines success.'),
  ('language-generation','No language output is required.','Produce short factual phrases or fixed-format text.','Draft coherent routine communication or structured prose.','Create nuanced, audience-specific, high-quality language.','Original, expert, highly consequential language production defines the task.'),
  ('information-retrieval','No external information must be located.','Find a known fact in a clearly identified source.','Search and select among several ordinary sources.','Synthesize incomplete or conflicting evidence across sources.','Open-ended evidence discovery and authoritative synthesis define success.'),
  ('quantitative-reasoning','No quantitative reasoning is required.','Apply direct arithmetic or a stated formula.','Select and apply standard quantitative methods.','Model complex relationships or uncertain quantitative evidence.','Novel, expert quantitative reasoning with high consequence defines success.'),
  ('general-reasoning','No inference or problem solving is required.','Follow a direct rule for a familiar case.','Choose among standard approaches using multiple facts.','Solve unfamiliar, multi-factor problems with trade-offs.','Novel strategic reasoning under deep uncertainty defines success.'),
  ('software-code-generation','No software or machine-readable instruction creation is required.','Modify a small known snippet or configuration.','Implement or debug a bounded component using standard patterns.','Design and integrate complex software across components.','Novel architecture or safety-critical software engineering defines success.'),
  ('visual-understanding','No visual evidence must be interpreted.','Recognize obvious objects, labels, or simple diagrams.','Interpret ordinary layouts, images, or visual relationships.','Analyze subtle, technical, or incomplete visual evidence.','Expert visual diagnosis under ambiguity or consequence defines success.'),
  ('visual-content-generation','No visual content must be created.','Make simple template-based edits or assets.','Create coherent routine layouts or visual content.','Develop original, audience-specific, polished visual systems.','Novel art direction or expert visual creation defines success.'),
  ('planning-workflow-execution','No sequencing or monitoring is required.','Follow a short fixed sequence.','Plan and monitor a bounded multi-step workflow.','Coordinate dependencies, exceptions, and multiple actors.','Long-horizon adaptive orchestration under uncertainty defines success.'),
  ('tool-computer-operation','No tool or software interaction is required.','Use one familiar tool for a direct action.','Operate several standard functions or connected tools.','Handle complex toolchains, exceptions, permissions, or integrations.','Expert operation of dynamic, high-consequence systems defines success.'),
  ('interpersonal-social-interaction','No interaction or social interpretation is required.','Exchange routine factual information.','Adapt ordinary communication to another person.','Manage emotion, trust, conflict, or sensitive social context.','Deep relational judgment in highly consequential interaction defines success.'),
  ('persuasion-negotiation','No influence or negotiation is required.','Present a simple recommendation with known rationale.','Address routine objections and align ordinary preferences.','Negotiate conflicting interests or persuade skeptical stakeholders.','High-stakes, multi-party influence strategy defines success.'),
  ('physical-perception','No real-world physical sensing is required.','Observe an obvious condition through a direct sensor or view.','Interpret ordinary multi-sensory physical conditions.','Detect subtle, changing, or partially observable physical states.','Expert physical diagnosis in uncontrolled conditions defines success.'),
  ('fine-physical-manipulation','No precise physical manipulation is required.','Perform a simple coarse or repeatable movement.','Handle ordinary objects with controlled dexterity.','Execute precise, variable, delicate manipulation.','Exceptional dexterity with safety-critical precision defines success.'),
  ('mobility-real-world-operation','No navigation or real-world movement is required.','Move through a fixed, controlled route.','Navigate an ordinary environment with limited variation.','Adapt movement to dynamic people, obstacles, or terrain.','Autonomous operation in highly unpredictable environments defines success.')
),anchors(value,label,evidence_rule) AS (VALUES
  (0,'Not required','The capability is explicitly irrelevant or absent from successful task completion.'),
  (25,'Basic','The capability supports a simple sub-step and is directly evidenced by the statement.'),
  (50,'Working','The capability is material to routine successful completion and is directly evidenced.'),
  (75,'Advanced','The capability is a primary complex requirement with clear task-language evidence.'),
  (100,'Defining','The task cannot be successfully performed without exceptional capability; evidence must be explicit and consequential.')
)
INSERT INTO capability_requirement_scale_anchors (rubric_version_id,capability_definition_id,anchor_value,anchor_label,description,observable_evidence_rule,source_id,provenance,created_by)
SELECT rubric.id,definition.id,anchors.value,anchors.label,
  CASE anchors.value WHEN 0 THEN dimensions.a0 WHEN 25 THEN dimensions.a25 WHEN 50 THEN dimensions.a50 WHEN 75 THEN dimensions.a75 ELSE dimensions.a100 END,
  anchors.evidence_rule,rubric.source_id,'{"seed":"rubric_v1_capability_anchor"}'::jsonb,'system:migration-010'
FROM task_mapping_rubric_versions rubric
JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=rubric.capability_taxonomy_version_id
JOIN dimensions ON dimensions.slug=definition.slug CROSS JOIN anchors
WHERE rubric.version='jvs-task-capability-rubric-v1';

WITH dimensions(slug,a0,a25,a50,a75,a100) AS (VALUES
  ('physical-presence','No physical presence is needed.','Occasional presence supports setup or verification.','Presence is regularly needed for material steps.','Most execution depends on presence at the work site.','Continuous on-site presence is inseparable from the task.'),
  ('fine-motor-control','No dexterous manipulation is needed.','Simple repeatable handling is needed.','Controlled manipulation of ordinary objects is material.','Precise or variable dexterity strongly constrains execution.','Exceptional or safety-critical dexterity is indispensable.'),
  ('mobility','No real-world movement is needed.','Movement follows a fixed controlled path.','Routine navigation through ordinary spaces is needed.','Dynamic obstacles or varied terrain strongly constrain execution.','Unpredictable real-world mobility is indispensable.'),
  ('real-world-sensing','No physical sensing beyond supplied data is needed.','A simple direct observation is occasionally needed.','Routine physical observations materially inform execution.','Subtle or changing physical signals strongly constrain execution.','Continuous expert sensing in uncontrolled conditions is indispensable.'),
  ('synchronous-human-interaction','No live interaction is needed.','Brief scripted interaction is useful.','Routine reciprocal interaction is material.','Trust, emotion, or rapid social adaptation strongly constrains execution.','Deep live human relationship and judgment are inseparable from success.'),
  ('legal-accountability','No human legal accountability is attached.','A human acknowledgement or routine approval is needed.','A responsible human must review or authorize material output.','Licensed or legally accountable judgment strongly constrains execution.','The law requires an accountable human decision-maker for the core act.'),
  ('safety-criticality','Errors have negligible safety consequences.','Errors can cause minor, readily reversible harm.','Errors can cause material but controlled safety consequences.','Errors can cause serious injury or irreversible harm.','Immediate life-critical consequences dominate the task.'),
  ('tool-access','No restricted tool, system, or credential access is needed.','One readily available tool or permission is needed.','Several controlled tools or credentials are material.','Complex permissions, equipment, or integrations strongly constrain execution.','Exclusive, highly restricted access is indispensable.'),
  ('data-access','No unavailable or sensitive data is needed.','Limited ordinary data access is needed.','Restricted, private, or distributed data is material.','Highly sensitive or difficult-to-obtain data strongly constrains execution.','Exclusive real-time data access is indispensable.'),
  ('workflow-integration','No coordination with external workflow is needed.','A simple handoff or single-system step is needed.','Several systems or actors must coordinate.','Exception-heavy cross-system coordination strongly constrains execution.','Organization-wide adaptive integration is inseparable from success.')
),anchors(value,label,evidence_rule) AS (VALUES
  (0,'No material constraint','The task statement provides no evidence that this constraint limits completion.'),
  (25,'Limited constraint','A bounded, occasional constraint is explicit but does not dominate execution.'),
  (50,'Material constraint','The constraint regularly affects how the task can be completed.'),
  (75,'Strong constraint','The constraint blocks or reshapes most end-to-end execution.'),
  (100,'Binding constraint','The constraint is inseparable from the core task and prevents remote or autonomous completion without equivalent real-world capacity.')
)
INSERT INTO environment_constraint_scale_anchors (rubric_version_id,constraint_definition_id,anchor_value,anchor_label,description,observable_evidence_rule,source_id,provenance,created_by)
SELECT rubric.id,definition.id,anchors.value,anchors.label,
  CASE anchors.value WHEN 0 THEN dimensions.a0 WHEN 25 THEN dimensions.a25 WHEN 50 THEN dimensions.a50 WHEN 75 THEN dimensions.a75 ELSE dimensions.a100 END,
  anchors.evidence_rule,rubric.source_id,'{"seed":"rubric_v1_constraint_anchor"}'::jsonb,'system:migration-010'
FROM task_mapping_rubric_versions rubric
JOIN task_environment_constraint_definitions definition ON definition.environment_taxonomy_version_id=rubric.environment_taxonomy_version_id
JOIN dimensions ON dimensions.slug=definition.slug CROSS JOIN anchors
WHERE rubric.version='jvs-task-capability-rubric-v1';

INSERT INTO task_capability_gold_datasets (rubric_version_id,dataset_version,name,description,status,expected_task_count,source_id,evidence,provenance,is_test_fixture,created_by,reviewed_by,reviewed_at)
SELECT rubric.id,'gold-v1-representative-test','Rubric v1 representative gold set',
  'Small manually curated architecture-validation set. Fixture reviewer identities are not production annotations.',
  'test_validated',4,rubric.source_id,'[{"kind":"rubric_validation_fixture"}]'::jsonb,
  '{"manual_curation":true,"fixture_reviewer_identities":true,"not_for_training_or_scoring":true}'::jsonb,true,
  'fixture:rubric-curator','fixture:rubric-reviewer-a + fixture:rubric-reviewer-b',TIMESTAMPTZ '2026-08-20 00:00:00+00'
FROM task_mapping_rubric_versions rubric
WHERE rubric.version='jvs-task-capability-rubric-v1'
  AND (SELECT count(*) FROM onet_tasks WHERE task_id IN (299,18382,21662,21668))=4
  AND (SELECT count(DISTINCT onet_task_id) FROM task_capability_mapping_sets
       WHERE onet_task_id IN (299,18382,21662) AND is_test_fixture)=3;

INSERT INTO task_capability_gold_items (gold_dataset_id,onet_task_id,disposition,task_statement_hash,disposition_rationale,reviewer_provenance,evidence,provenance,created_by,reviewed_at)
SELECT dataset.id,task.task_id,item.disposition,md5(task.statement),item.rationale,
  '[{"reviewer":"fixture:rubric-reviewer-a","role":"primary","identity":"test-only"},{"reviewer":"fixture:rubric-reviewer-b","role":"adjudicator","identity":"test-only"}]'::jsonb,
  jsonb_build_array(jsonb_build_object('task_statement',task.statement,'source','O*NET 30.3')),
  '{"manual_fixture":true,"not_for_training_or_scoring":true}'::jsonb,'fixture:rubric-curator',TIMESTAMPTZ '2026-08-20 00:00:00+00'
FROM task_capability_gold_datasets dataset
JOIN (VALUES
  (299::bigint,'mappable','The statement specifies design output, governing concepts, and knowledge context.'),
  (18382::bigint,'mappable','The statement specifies evidence inputs, an interpretive action, and a diagnostic outcome.'),
  (21662::bigint,'mappable','The statement specifies analysis inputs and feasibility criteria.'),
  (21668::bigint,'ambiguous_scope','“Determine system performance standards” does not specify the system, evidence, authority, or complexity; assigning levels would require invented context.')
) item(task_id,disposition,rationale) ON true
JOIN onet_tasks task ON task.task_id=item.task_id
WHERE dataset.dataset_version='gold-v1-representative-test';

INSERT INTO gold_task_capability_requirements (gold_item_id,capability_definition_id,weight,required_capability_level,confidence,confidence_state_id,rationale,evidence,provenance,source_id,created_by)
SELECT gold_item.id,mapping.capability_definition_id,mapping.weight,mapping.required_capability_level,mapping.confidence,state.id,
  mapping.rationale,mapping.evidence,'{"copied_from_architecture_fixture_then_manually_adjudicated":true}'::jsonb,dataset.source_id,'fixture:rubric-curator'
FROM task_capability_gold_items gold_item
JOIN task_capability_gold_datasets dataset ON dataset.id=gold_item.gold_dataset_id
JOIN task_mapping_rubric_versions rubric ON rubric.id=dataset.rubric_version_id
JOIN task_capability_mapping_sets mapping_set ON mapping_set.onet_task_id=gold_item.onet_task_id AND mapping_set.taxonomy_version_id=rubric.capability_taxonomy_version_id AND mapping_set.is_test_fixture
JOIN task_capability_requirement_mappings mapping ON mapping.mapping_set_id=mapping_set.id
JOIN mapping_confidence_states state ON state.rubric_version_id=rubric.id AND mapping.confidence BETWEEN state.minimum_confidence AND state.maximum_confidence
WHERE dataset.dataset_version='gold-v1-representative-test' AND gold_item.disposition='mappable';

INSERT INTO gold_task_environment_constraints (gold_item_id,constraint_definition_id,constraint_level,confidence,confidence_state_id,rationale,evidence,provenance,source_id,created_by)
SELECT gold_item.id,mapping.constraint_definition_id,mapping.constraint_level,mapping.confidence,state.id,
  'Gold fixture preserves the manually adjudicated architecture constraint value.',mapping.evidence,
  '{"copied_from_architecture_fixture_then_manually_adjudicated":true}'::jsonb,dataset.source_id,'fixture:rubric-curator'
FROM task_capability_gold_items gold_item
JOIN task_capability_gold_datasets dataset ON dataset.id=gold_item.gold_dataset_id
JOIN task_mapping_rubric_versions rubric ON rubric.id=dataset.rubric_version_id
JOIN task_environment_constraint_mappings mapping ON mapping.onet_task_id=gold_item.onet_task_id AND mapping.is_test_fixture
JOIN task_environment_constraint_definitions definition ON definition.id=mapping.constraint_definition_id AND definition.environment_taxonomy_version_id=rubric.environment_taxonomy_version_id
JOIN mapping_confidence_states state ON state.rubric_version_id=rubric.id AND mapping.confidence BETWEEN state.minimum_confidence AND state.maximum_confidence
WHERE dataset.dataset_version='gold-v1-representative-test' AND gold_item.disposition='mappable';

CREATE OR REPLACE FUNCTION enforce_rubric_row() RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_mapping_rubric(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER rubric_versions_reconcile AFTER INSERT ON task_mapping_rubric_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_rubric_row();
CREATE OR REPLACE FUNCTION enforce_rubric_child() RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_mapping_rubric(NEW.rubric_version_id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER capability_anchors_reconcile AFTER INSERT ON capability_requirement_scale_anchors DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_rubric_child();
CREATE CONSTRAINT TRIGGER constraint_anchors_reconcile AFTER INSERT ON environment_constraint_scale_anchors DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_rubric_child();
CREATE CONSTRAINT TRIGGER confidence_states_reconcile AFTER INSERT ON mapping_confidence_states DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_rubric_child();
CREATE OR REPLACE FUNCTION enforce_gold_dataset_row() RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_capability_gold_dataset(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER gold_datasets_reconcile AFTER INSERT ON task_capability_gold_datasets DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_gold_dataset_row();
CREATE OR REPLACE FUNCTION enforce_gold_item() RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_capability_gold_dataset(NEW.gold_dataset_id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER gold_items_reconcile AFTER INSERT ON task_capability_gold_items DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_gold_item();
CREATE OR REPLACE FUNCTION enforce_gold_requirement() RETURNS TRIGGER LANGUAGE plpgsql AS $$ DECLARE dataset_key BIGINT; BEGIN SELECT gold_dataset_id INTO dataset_key FROM task_capability_gold_items WHERE id=NEW.gold_item_id; PERFORM validate_task_capability_gold_dataset(dataset_key); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER gold_capabilities_reconcile AFTER INSERT ON gold_task_capability_requirements DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_gold_requirement();
CREATE CONSTRAINT TRIGGER gold_constraints_reconcile AFTER INSERT ON gold_task_environment_constraints DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_gold_requirement();

CREATE TRIGGER rubric_versions_append_only BEFORE UPDATE OR DELETE ON task_mapping_rubric_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER capability_anchors_append_only BEFORE UPDATE OR DELETE ON capability_requirement_scale_anchors FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER constraint_anchors_append_only BEFORE UPDATE OR DELETE ON environment_constraint_scale_anchors FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER confidence_states_append_only BEFORE UPDATE OR DELETE ON mapping_confidence_states FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER gold_datasets_append_only BEFORE UPDATE OR DELETE ON task_capability_gold_datasets FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER gold_items_append_only BEFORE UPDATE OR DELETE ON task_capability_gold_items FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER gold_capabilities_append_only BEFORE UPDATE OR DELETE ON gold_task_capability_requirements FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER gold_constraints_append_only BEFORE UPDATE OR DELETE ON gold_task_environment_constraints FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

CREATE OR REPLACE VIEW task_mapping_rubric_validation AS
SELECT rubric.id rubric_id,rubric.version,rubric.status,
  (SELECT count(*) FROM capability_requirement_scale_anchors WHERE rubric_version_id=rubric.id) capability_anchors,
  (SELECT count(*) FROM environment_constraint_scale_anchors WHERE rubric_version_id=rubric.id) constraint_anchors,
  (SELECT count(*) FROM mapping_confidence_states WHERE rubric_version_id=rubric.id) confidence_states,
  (SELECT count(*) FROM task_capability_gold_datasets WHERE rubric_version_id=rubric.id) gold_datasets,
  (SELECT count(*) FROM task_capability_gold_items item JOIN task_capability_gold_datasets dataset ON dataset.id=item.gold_dataset_id WHERE dataset.rubric_version_id=rubric.id) gold_items,
  (SELECT count(*) FROM task_capability_gold_datasets dataset WHERE dataset.rubric_version_id=rubric.id AND NOT validate_task_capability_gold_dataset(dataset.id)) invalid_gold_datasets,
  validate_task_mapping_rubric(rubric.id) rubric_valid
FROM task_mapping_rubric_versions rubric;

COMMIT;
