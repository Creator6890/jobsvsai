BEGIN;

WITH source AS (
  INSERT INTO data_sources (name,source_url,version,metadata)
  VALUES ('JobsVsAI Phase 4A scoring pilot','internal://jobsvsai/phase4a-scoring-pilot','2026-Q3-v1',
    '{"scope":"12_occupation_pilot","public":false,"production_scoring":false,"corpus_mapping":false}'::jsonb)
  ON CONFLICT (name) DO NOTHING
  RETURNING id
)
SELECT id FROM source;

CREATE TABLE phase4a_task_formula_versions (
  id BIGSERIAL PRIMARY KEY,
  formula_type TEXT NOT NULL CHECK (formula_type IN ('capability_fit','automation_feasibility','augmentation_potential')),
  formula_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  parameters JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','pilot','retired')),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(parameters)='object')
);

CREATE TABLE phase4a_occupation_formula_versions (
  id BIGSERIAL PRIMARY KEY,
  formula_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  parameters JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','pilot','retired')),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(parameters)='object')
);

CREATE TABLE phase4a_pilot_cohorts (
  id BIGSERIAL PRIMARY KEY,
  cohort_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','mapped','scored','reviewed','blocked')),
  target_occupation_count INTEGER NOT NULL CHECK (target_occupation_count BETWEEN 10 AND 15),
  mapping_run_id BIGINT REFERENCES ai_generated_task_mapping_runs(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  scope_policy JSONB NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(scope_policy)='object')
);

CREATE TABLE phase4a_pilot_occupations (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4a_pilot_cohorts(id),
  requested_name TEXT NOT NULL,
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code),
  cohort_order INTEGER NOT NULL,
  selection_status TEXT NOT NULL CHECK (selection_status IN ('requested','substituted')),
  substitution_reason TEXT,
  readiness_snapshot JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (cohort_id,occupation_code),
  UNIQUE (cohort_id,cohort_order),
  CHECK ((selection_status='requested' AND substitution_reason IS NULL) OR selection_status='substituted'),
  CHECK (jsonb_typeof(readiness_snapshot)='object'),
  CHECK (jsonb_typeof(warnings)='array')
);

CREATE TABLE phase4a_calculation_runs (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4a_pilot_cohorts(id),
  run_version TEXT NOT NULL UNIQUE,
  run_kind TEXT NOT NULL CHECK (run_kind IN ('initial','deterministic_replay','formula_only_recompute')),
  capability_fit_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  automation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  augmentation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  occupation_formula_id BIGINT NOT NULL REFERENCES phase4a_occupation_formula_versions(id),
  mapping_run_id BIGINT NOT NULL REFERENCES ai_generated_task_mapping_runs(id),
  frontier_track_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_tracks(id),
  dependency_hash CHAR(64) NOT NULL,
  previous_run_id BIGINT REFERENCES phase4a_calculation_runs(id),
  new_ai_mapping_calls INTEGER NOT NULL DEFAULT 0 CHECK (new_ai_mapping_calls>=0),
  reused_mapping_count INTEGER NOT NULL DEFAULT 0 CHECK (reused_mapping_count>=0),
  task_assessment_count INTEGER NOT NULL DEFAULT 0 CHECK (task_assessment_count>=0),
  occupation_score_count INTEGER NOT NULL DEFAULT 0 CHECK (occupation_score_count>=0),
  reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('pending','passed','failed')),
  replay_matches_previous BOOLEAN,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE phase4a_task_assessments (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4a_calculation_runs(id),
  pilot_occupation_id BIGINT NOT NULL REFERENCES phase4a_pilot_occupations(id),
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  assessment_version TEXT NOT NULL,
  ai_capability_fit NUMERIC(7,4) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(7,4) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(7,4) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  task_ai_exposure NUMERIC(7,4) NOT NULL CHECK (task_ai_exposure BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
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
  UNIQUE (calculation_run_id,ai_task_mapping_id),
  CHECK (jsonb_typeof(capability_contributions)='array'),
  CHECK (jsonb_typeof(constraint_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4a_occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4a_calculation_runs(id),
  pilot_occupation_id BIGINT NOT NULL REFERENCES phase4a_pilot_occupations(id),
  score_version TEXT NOT NULL,
  source_task_count INTEGER NOT NULL CHECK (source_task_count>=0),
  mapped_task_count INTEGER NOT NULL CHECK (mapped_task_count>=0),
  excluded_task_count INTEGER NOT NULL CHECK (excluded_task_count>=0),
  weighting_eligible_task_count INTEGER NOT NULL CHECK (weighting_eligible_task_count>=0),
  weighted_task_coverage NUMERIC(7,4) NOT NULL CHECK (weighted_task_coverage BETWEEN 0 AND 100),
  ai_exposure NUMERIC(7,4) NOT NULL CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(7,4) NOT NULL CHECK (replacement_risk BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
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
  UNIQUE (calculation_run_id,pilot_occupation_id),
  CHECK (mapped_task_count+excluded_task_count=source_task_count),
  CHECK (jsonb_typeof(factor_contributions)='array'),
  CHECK (jsonb_typeof(task_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4A scoring pilot')
INSERT INTO phase4a_task_formula_versions (formula_type,formula_version,name,description,parameters,status,source_id,provenance,created_by)
SELECT item.formula_type,item.formula_version,item.name,item.description,item.parameters,'pilot',source.id,
  '{"phase":"4A","public":false,"production_scoring":false}'::jsonb,'system:migration-018'
FROM source CROSS JOIN (VALUES
  ('capability_fit','task-capability-fit-v1','Task Capability Fit v1',
   'Weighted geometric capability matching with an explicit critical-capability bottleneck cap.',
   '{"shortfallExponent":1.35,"geometricFloor":1,"criticalWeightThreshold":0.35,"criticalSecondaryWeightThreshold":0.20,"criticalRequiredLevelThreshold":70,"bottleneckMatchThreshold":75,"bottleneckHeadroom":10}'::jsonb),
  ('automation_feasibility','automation-feasibility-v1','Automation Feasibility v1',
   'Capability fit blended with environment-constraint resistance and capped by critical physical, human, legal, or safety constraints.',
   '{"capabilityFitWeight":0.65,"constraintResistanceWeight":0.35,"criticalConstraintThreshold":70,"constraintWeights":{"physical-presence":0.16,"fine-motor-control":0.16,"mobility":0.14,"real-world-sensing":0.12,"synchronous-human-interaction":0.10,"legal-accountability":0.10,"safety-criticality":0.12,"data-access":0.04,"tool-access":0.03,"workflow-integration":0.03},"bottleneckCapStrength":{"physical-presence":0.80,"fine-motor-control":0.85,"mobility":0.85,"real-world-sensing":0.65,"synchronous-human-interaction":0.55,"legal-accountability":0.65,"safety-criticality":0.90},"proxyWarnings":{"environment_variability":"real-world-sensing is an incomplete proxy","regulation_and_accountability":"legal-accountability","consequence_severity":"safety-criticality","real_time_requirements":"synchronous-human-interaction is an incomplete proxy","privacy_sensitivity":"data-access is an incomplete proxy"}}'::jsonb),
  ('augmentation_potential','augmentation-potential-v1','Augmentation Potential v1',
   'Capability fit blended with the human-complement opportunity left when full automation is constrained.',
   '{"capabilityFitWeight":0.70,"humanComplementWeight":0.30}'::jsonb)
) AS item(formula_type,formula_version,name,description,parameters);

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4A scoring pilot')
INSERT INTO phase4a_occupation_formula_versions (formula_version,name,description,parameters,status,source_id,provenance,created_by)
SELECT 'phase4a-occupation-score-v1','Phase 4A occupation score v1',
  'Source-weighted pilot aggregation with explicit neutral placeholders for unavailable adoption and labour-market inputs.',
  '{"taskExposureWeights":{"aiCapabilityFit":0.60,"automationFeasibility":0.25,"augmentationPotential":0.15},"replacementWeights":{"taskAutomationExposure":0.45,"aiCapabilityProximity":0.15,"humanDependencyResistance":0.15,"physicalDependencyResistance":0.10,"adoptionPressure":0.10,"labourMarketResilienceResistance":0.05},"humanDependencyWeights":{"synchronous-human-interaction":0.60,"legal-accountability":0.40},"physicalDependencyWeights":{"physical-presence":0.25,"fine-motor-control":0.25,"mobility":0.20,"real-world-sensing":0.15,"safety-criticality":0.15},"adoptionPressureDefault":50,"labourMarketResilienceDefault":50,"placeholderPolicy":"explicit_neutral_with_warning","taskWeight":"importance_score_x_frequency_score","confidenceWeights":{"weightedCoverage":0.50,"mappingConfidence":0.25,"frontierConfidence":0.15,"sourceCompleteness":0.10}}'::jsonb,
  'pilot',source.id,'{"phase":"4A","public":false,"production_score_namespace":false}'::jsonb,'system:migration-018'
FROM source;

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4A scoring pilot')
INSERT INTO phase4a_pilot_cohorts (cohort_version,name,description,status,target_occupation_count,source_id,scope_policy,provenance,created_by)
SELECT 'phase4a-2026q3-v1','Phase 4A end-to-end scoring pilot',
  'Twelve-occupation private cohort for validating mapping, task scoring, occupation scoring, explainability and deterministic replay.',
  'draft',12,source.id,
  '{"allowedOccupationCodes":["15-1252.00","27-1024.00","13-2011.00","23-1011.00","29-1171.00","25-2031.00","47-2111.00","49-3023.00","11-2022.00","15-2041.00","27-4021.00","35-2014.00"],"bulkMappingAllowed":false,"publicActivationAllowed":false,"productionScoreWritesAllowed":false}'::jsonb,
  '{"phase":"4A","data_scientist_substitution":"Statisticians because Data Scientists had zero weighting-eligible tasks"}'::jsonb,
  'system:migration-018'
FROM source;

WITH context AS (
  SELECT cohort.id cohort_id,source.id source_id
  FROM phase4a_pilot_cohorts cohort
  JOIN data_sources source ON source.name='JobsVsAI Phase 4A scoring pilot'
  WHERE cohort.cohort_version='phase4a-2026q3-v1'
), selection(requested_name,occupation_code,cohort_order,selection_status,substitution_reason) AS (VALUES
  ('Software Developer','15-1252.00',1,'requested',NULL),
  ('Graphic Designer','27-1024.00',2,'requested',NULL),
  ('Accountant','13-2011.00',3,'requested',NULL),
  ('Lawyer','23-1011.00',4,'requested',NULL),
  ('Nurse Practitioner','29-1171.00',5,'requested',NULL),
  ('Teacher','25-2031.00',6,'requested',NULL),
  ('Electrician','47-2111.00',7,'requested',NULL),
  ('Automotive Mechanic','49-3023.00',8,'requested',NULL),
  ('Sales Manager','11-2022.00',9,'requested',NULL),
  ('Data Scientist','15-2041.00',10,'substituted','Data Scientists had 16 source tasks but zero weighting-eligible tasks; Statisticians preserves quantitative work without imputing task weights.'),
  ('Photographer','27-4021.00',11,'requested',NULL),
  ('Cook','35-2014.00',12,'requested',NULL)
)
INSERT INTO phase4a_pilot_occupations (
  cohort_id,requested_name,occupation_code,cohort_order,selection_status,substitution_reason,
  readiness_snapshot,warnings,source_id,created_by
)
SELECT context.cohort_id,selection.requested_name,selection.occupation_code,selection.cohort_order,
  selection.selection_status,selection.substitution_reason,
  jsonb_build_object('sourceTitle',occupation.title,'lifecycleState',profile.lifecycle_state,
    'scoringEligible',profile.scoring_eligible,'sourceTasks',count(task.task_id),
    'weightingEligibleTasks',count(task.task_id) FILTER (WHERE task.weighting_eligible),
    'sourceVersion',max(task.source_version)),
  CASE WHEN profile.scoring_eligible THEN '[]'::jsonb
    ELSE jsonb_build_array(jsonb_build_object('code','promotion_not_scoring_ready','lifecycleState',profile.lifecycle_state,'pilotOnly',true)) END,
  context.source_id,'system:migration-018'
FROM context JOIN selection ON true
JOIN onet_occupations occupation ON occupation.onet_soc_code=selection.occupation_code
LEFT JOIN occupation_promotion_profiles profile ON profile.source_occupation_code=selection.occupation_code
LEFT JOIN onet_tasks task ON task.occupation_code=selection.occupation_code AND task.is_current
GROUP BY context.cohort_id,context.source_id,selection.requested_name,selection.occupation_code,
  selection.cohort_order,selection.selection_status,selection.substitution_reason,occupation.title,
  profile.lifecycle_state,profile.scoring_eligible;

CREATE TRIGGER phase4a_task_formulas_append_only BEFORE UPDATE OR DELETE ON phase4a_task_formula_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4a_occupation_formulas_append_only BEFORE UPDATE OR DELETE ON phase4a_occupation_formula_versions FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4a_pilot_occupations_append_only BEFORE UPDATE OR DELETE ON phase4a_pilot_occupations FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4a_calculation_runs_append_only BEFORE UPDATE OR DELETE ON phase4a_calculation_runs FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4a_task_assessments_append_only BEFORE UPDATE OR DELETE ON phase4a_task_assessments FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4a_occupation_scores_append_only BEFORE UPDATE OR DELETE ON phase4a_occupation_scores FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
