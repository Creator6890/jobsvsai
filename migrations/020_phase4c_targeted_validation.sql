BEGIN;

INSERT INTO data_sources (name,source_url,version,metadata)
VALUES (
  'JobsVsAI Phase 4C targeted validation',
  'internal://jobsvsai/phase4c-targeted-validation',
  '2026-Q3-v1',
  '{"scope":"25_occupation_targeted_validation","public":false,"production_scoring":false,"corpus_mapping":false,"maximum_added_occupations":15}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE phase4c_validation_cohorts (
  id BIGSERIAL PRIMARY KEY,
  cohort_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','mapped','scored','validated','blocked')),
  retained_cohort_id BIGINT NOT NULL REFERENCES phase4a_pilot_cohorts(id),
  added_occupation_count INTEGER NOT NULL CHECK (added_occupation_count BETWEEN 10 AND 15),
  total_occupation_count INTEGER NOT NULL CHECK (total_occupation_count BETWEEN 22 AND 27),
  minimum_weighted_coverage NUMERIC(7,4) NOT NULL DEFAULT 70
    CHECK (minimum_weighted_coverage=70),
  new_mapping_run_id BIGINT REFERENCES ai_generated_task_mapping_runs(id),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  scope_policy JSONB NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(scope_policy)='object')
);

CREATE TABLE phase4c_validation_occupations (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4c_validation_cohorts(id),
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code),
  cohort_order INTEGER NOT NULL,
  cohort_role TEXT NOT NULL CHECK (cohort_role IN ('retained_phase4a','added_validation')),
  stress_dimensions TEXT[] NOT NULL,
  selection_rationale TEXT NOT NULL,
  expected_proxy_behavior JSONB NOT NULL,
  readiness_snapshot JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (cohort_id,occupation_code),
  UNIQUE (cohort_id,cohort_order),
  CHECK (cardinality(stress_dimensions)>0),
  CHECK (jsonb_typeof(expected_proxy_behavior)='object'),
  CHECK (jsonb_typeof(readiness_snapshot)='object'),
  CHECK (jsonb_typeof(warnings)='array')
);

CREATE TABLE phase4c_task_mapping_scope (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4c_validation_cohorts(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  scope_decision TEXT NOT NULL CHECK (scope_decision IN (
    'reused','generated','unmapped_after_gate','unmapped_insufficient_evidence','source_weight_ineligible'
  )),
  ai_task_mapping_id BIGINT REFERENCES ai_generated_task_mappings(id),
  mapping_run_id BIGINT REFERENCES ai_generated_task_mapping_runs(id),
  source_weight NUMERIC(14,8),
  selection_rank INTEGER,
  selection_reason TEXT NOT NULL,
  evidence JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (cohort_id,onet_task_id),
  CHECK (jsonb_typeof(evidence)='array'),
  CHECK ((scope_decision IN ('reused','generated','unmapped_insufficient_evidence') AND ai_task_mapping_id IS NOT NULL)
      OR (scope_decision IN ('unmapped_after_gate','source_weight_ineligible') AND ai_task_mapping_id IS NULL))
);

CREATE TABLE phase4c_proxy_snapshots (
  id BIGSERIAL PRIMARY KEY,
  proxy_model_version_id BIGINT NOT NULL REFERENCES phase4b_proxy_model_versions(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  adoption_pressure NUMERIC(7,4) NOT NULL CHECK (adoption_pressure BETWEEN 0 AND 100),
  labour_market_resilience NUMERIC(7,4) NOT NULL CHECK (labour_market_resilience BETWEEN 0 AND 100),
  proxy_confidence NUMERIC(7,4) NOT NULL CHECK (proxy_confidence BETWEEN 0 AND 100),
  domain_values JSONB NOT NULL,
  component_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (proxy_model_version_id,validation_occupation_id),
  CHECK (jsonb_typeof(domain_values)='object'),
  CHECK (jsonb_typeof(component_contributions)='object'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4c_calculation_runs (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4c_validation_cohorts(id),
  run_version TEXT NOT NULL UNIQUE,
  run_kind TEXT NOT NULL CHECK (run_kind IN ('targeted_validation','deterministic_replay')),
  capability_fit_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  automation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  augmentation_formula_id BIGINT NOT NULL REFERENCES phase4a_task_formula_versions(id),
  occupation_formula_id BIGINT NOT NULL REFERENCES phase4a_occupation_formula_versions(id),
  frontier_track_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_tracks(id),
  proxy_model_version_id BIGINT NOT NULL REFERENCES phase4b_proxy_model_versions(id),
  mapping_scope_hash CHAR(64) NOT NULL,
  dependency_hash CHAR(64) NOT NULL,
  previous_run_id BIGINT REFERENCES phase4c_calculation_runs(id),
  new_mapping_count INTEGER NOT NULL CHECK (new_mapping_count>=0),
  reused_mapping_count INTEGER NOT NULL CHECK (reused_mapping_count>=0),
  external_ai_calls INTEGER NOT NULL DEFAULT 0 CHECK (external_ai_calls=0),
  task_assessment_count INTEGER NOT NULL CHECK (task_assessment_count>=0),
  occupation_score_count INTEGER NOT NULL CHECK (occupation_score_count=25),
  reconciliation_status TEXT NOT NULL CHECK (reconciliation_status IN ('pending','passed','failed')),
  replay_matches_previous BOOLEAN,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE phase4c_task_assessments (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4c_calculation_runs(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  ai_task_mapping_id BIGINT NOT NULL REFERENCES ai_generated_task_mappings(id),
  onet_task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id),
  assessment_version TEXT NOT NULL,
  ai_capability_fit NUMERIC(7,4) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(7,4) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(7,4) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  task_ai_exposure NUMERIC(7,4) NOT NULL CHECK (task_ai_exposure BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  proxy_confidence_penalty NUMERIC(7,4) NOT NULL CHECK (proxy_confidence_penalty BETWEEN 0 AND 100),
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

CREATE TABLE phase4c_occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4c_calculation_runs(id),
  validation_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  score_version TEXT NOT NULL,
  source_task_count INTEGER NOT NULL CHECK (source_task_count>=0),
  mapped_task_count INTEGER NOT NULL CHECK (mapped_task_count>=0),
  excluded_task_count INTEGER NOT NULL CHECK (excluded_task_count>=0),
  weighting_eligible_task_count INTEGER NOT NULL CHECK (weighting_eligible_task_count>=0),
  weighted_task_coverage NUMERIC(7,4) NOT NULL CHECK (weighted_task_coverage BETWEEN 0 AND 100),
  ai_exposure NUMERIC(7,4) NOT NULL CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(7,4) NOT NULL CHECK (replacement_risk BETWEEN 0 AND 100),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  coverage_gate_status TEXT NOT NULL CHECK (coverage_gate_status IN ('passed','below_threshold')),
  confidence_penalty NUMERIC(7,4) NOT NULL CHECK (confidence_penalty BETWEEN 0 AND 100),
  scale_eligible BOOLEAN NOT NULL,
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
  CHECK (mapped_task_count+excluded_task_count=source_task_count),
  CHECK (jsonb_typeof(factor_contributions)='array'),
  CHECK (jsonb_typeof(task_contributions)='array'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

CREATE TABLE phase4c_proxy_pairwise_expectations (
  id BIGSERIAL PRIMARY KEY,
  cohort_id BIGINT NOT NULL REFERENCES phase4c_validation_cohorts(id),
  expectation_version TEXT NOT NULL,
  proxy_metric TEXT NOT NULL CHECK (proxy_metric IN (
    'physical-presence','environment-variability','human-dependency','regulation',
    'accountability','consequence-severity','adoption-pressure','labour-market-resilience'
  )),
  higher_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  lower_occupation_id BIGINT NOT NULL REFERENCES phase4c_validation_occupations(id),
  minimum_delta NUMERIC(7,4) NOT NULL CHECK (minimum_delta BETWEEN 0 AND 100),
  rationale TEXT NOT NULL,
  evidence JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (cohort_id,proxy_metric,higher_occupation_id,lower_occupation_id),
  CHECK (higher_occupation_id<>lower_occupation_id),
  CHECK (jsonb_typeof(evidence)='array')
);

CREATE TABLE phase4c_proxy_validation_results (
  id BIGSERIAL PRIMARY KEY,
  calculation_run_id BIGINT NOT NULL REFERENCES phase4c_calculation_runs(id),
  expectation_id BIGINT NOT NULL REFERENCES phase4c_proxy_pairwise_expectations(id),
  higher_value NUMERIC(7,4) NOT NULL CHECK (higher_value BETWEEN 0 AND 100),
  lower_value NUMERIC(7,4) NOT NULL CHECK (lower_value BETWEEN 0 AND 100),
  observed_delta NUMERIC(8,4) NOT NULL CHECK (observed_delta BETWEEN -100 AND 100),
  passed BOOLEAN NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('pass','warning','failure')),
  finding TEXT NOT NULL,
  reconciliation JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calculation_run_id,expectation_id),
  CHECK (jsonb_typeof(reconciliation)='object')
);

WITH context AS (
  SELECT source.id source_id,retained.id retained_cohort_id
  FROM data_sources source
  JOIN phase4a_pilot_cohorts retained ON retained.cohort_version='phase4a-2026q3-v1'
  WHERE source.name='JobsVsAI Phase 4C targeted validation'
)
INSERT INTO phase4c_validation_cohorts (
  cohort_version,name,description,status,retained_cohort_id,added_occupation_count,
  total_occupation_count,minimum_weighted_coverage,source_id,scope_policy,provenance,created_by
)
SELECT 'phase4c-2026q3-v1','Phase 4C targeted proxy validation cohort',
  'The unchanged Phase 4A twelve plus thirteen deliberately diverse occupations selected to stress physical dependency, human interaction, regulation, accountability, adoption pressure and structural labour resilience.',
  'draft',retained_cohort_id,13,25,70,source_id,
  '{"retainedOccupationCount":12,"addedOccupationCount":13,"maximumAddedOccupations":15,"fullCorpusScoringAllowed":false,"publicActivationAllowed":false,"productionScoreWritesAllowed":false,"mappingPolicy":"reuse_phase4a_else_minimum_highest_source_weight_until_70_percent_eligible_coverage","coverageGate":70,"missingEvidencePolicy":"never_invent_never_impute"}'::jsonb,
  '{"phase":"4C","targetedValidationOnly":true,"selectionWasDefinedBeforeProxyEvaluation":true}'::jsonb,
  'system:migration-020'
FROM context;

WITH context AS (
  SELECT cohort.id cohort_id,source.id source_id
  FROM phase4c_validation_cohorts cohort
  JOIN data_sources source ON source.name='JobsVsAI Phase 4C targeted validation'
  WHERE cohort.cohort_version='phase4c-2026q3-v1'
)
INSERT INTO phase4c_validation_occupations (
  cohort_id,occupation_code,cohort_order,cohort_role,stress_dimensions,selection_rationale,
  expected_proxy_behavior,readiness_snapshot,warnings,source_id,provenance,created_by
)
SELECT context.cohort_id,pilot.occupation_code,pilot.cohort_order,'retained_phase4a',
  ARRAY['continuity','phase4b-comparison'],
  'Retained unchanged from the Phase 4A cohort to test numerical continuity and previously observed coverage/proxy behavior.',
  '{"expectation":"numerically_equal_to_phase4b_under_unchanged_inputs"}'::jsonb,
  pilot.readiness_snapshot,pilot.warnings,context.source_id,
  jsonb_build_object('phase','4C','retainedPilotOccupationId',pilot.id),
  'system:migration-020'
FROM context
JOIN phase4a_pilot_cohorts retained ON retained.cohort_version='phase4a-2026q3-v1'
JOIN phase4a_pilot_occupations pilot ON pilot.cohort_id=retained.id;

WITH context AS (
  SELECT cohort.id cohort_id,source.id source_id
  FROM phase4c_validation_cohorts cohort
  JOIN data_sources source ON source.name='JobsVsAI Phase 4C targeted validation'
  WHERE cohort.cohort_version='phase4c-2026q3-v1'
), selection(occupation_code,cohort_order,stress_dimensions,selection_rationale,expected_proxy_behavior) AS (VALUES
  ('11-1021.00',13,ARRAY['human-dependency','accountability','adoption-pressure'],'Management work tests high coordination/accountability with substantial information and computer work.','{"human-dependency":"high","accountability":"high","adoption-pressure":"medium-high"}'::jsonb),
  ('13-2052.00',14,ARRAY['human-dependency','regulation','adoption-pressure'],'Financial advice tests regulated knowledge work with direct client dependence and digital information processing.','{"human-dependency":"high","regulation":"high","adoption-pressure":"high"}'::jsonb),
  ('15-1212.00',15,ARRAY['regulation','accountability','adoption-pressure'],'Information security tests highly digital work with material compliance and accountability demands.','{"physical-presence":"low","adoption-pressure":"high","accountability":"high"}'::jsonb),
  ('17-2051.00',16,ARRAY['physical-presence','environment-variability','regulation','accountability'],'Civil engineering bridges computer-intensive analysis, site variability, standards and consequential decisions.','{"physical-presence":"medium","environment-variability":"medium","accountability":"high"}'::jsonb),
  ('21-1022.00',17,ARRAY['human-dependency','regulation','labour-market-resilience'],'Healthcare social work is a strong human-interaction and regulated-care stress case.','{"human-dependency":"high","regulation":"high","labour-market-resilience":"high"}'::jsonb),
  ('25-2021.00',18,ARRAY['human-dependency','accountability','labour-market-resilience'],'Elementary teaching tests sustained face-to-face dependency and responsibility for children.','{"human-dependency":"high","accountability":"high","labour-market-resilience":"high"}'::jsonb),
  ('27-3042.00',19,ARRAY['adoption-pressure','physical-presence','labour-market-resilience'],'Technical writing supplies a low-physical, high-information counterexample expected to face stronger digital adoption pressure.','{"physical-presence":"low","adoption-pressure":"high","labour-market-resilience":"low"}'::jsonb),
  ('29-1141.00',20,ARRAY['physical-presence','human-dependency','regulation','accountability','consequence-severity','labour-market-resilience'],'Registered nursing combines direct physical care, human dependency, regulation and severe consequences.','{"physical-presence":"high","human-dependency":"high","regulation":"high","accountability":"high","consequence-severity":"high","labour-market-resilience":"high"}'::jsonb),
  ('33-3051.00',21,ARRAY['physical-presence','environment-variability','human-dependency','regulation','accountability','consequence-severity'],'Patrol work is an extreme real-world, variable, regulated and safety-consequential occupation.','{"physical-presence":"high","environment-variability":"high","accountability":"high","consequence-severity":"high"}'::jsonb),
  ('39-5012.00',22,ARRAY['physical-presence','human-dependency','adoption-pressure','labour-market-resilience'],'Hairdressing tests fine physical service delivery, direct interpersonal dependence and low digital substitutability.','{"physical-presence":"high","human-dependency":"high","adoption-pressure":"low","labour-market-resilience":"high"}'::jsonb),
  ('41-2031.00',23,ARRAY['human-dependency','adoption-pressure','labour-market-resilience'],'Retail sales tests interpersonal service alongside meaningful existing workflow automation.','{"human-dependency":"high","adoption-pressure":"medium","labour-market-resilience":"medium"}'::jsonb),
  ('51-4041.00',24,ARRAY['physical-presence','environment-variability','accountability','adoption-pressure'],'Machining tests equipment-bound precision work in a variable physical production environment.','{"physical-presence":"high","environment-variability":"high","adoption-pressure":"medium"}'::jsonb),
  ('53-3032.00',25,ARRAY['physical-presence','environment-variability','accountability','consequence-severity','adoption-pressure'],'Heavy trucking tests mobility, uncontrolled environments, safety accountability and partial workflow automation.','{"physical-presence":"high","environment-variability":"high","accountability":"high","consequence-severity":"high","adoption-pressure":"medium"}'::jsonb)
)
INSERT INTO phase4c_validation_occupations (
  cohort_id,occupation_code,cohort_order,cohort_role,stress_dimensions,selection_rationale,
  expected_proxy_behavior,readiness_snapshot,warnings,source_id,provenance,created_by
)
SELECT context.cohort_id,selection.occupation_code,selection.cohort_order,'added_validation',
  selection.stress_dimensions,selection.selection_rationale,selection.expected_proxy_behavior,
  jsonb_build_object('sourceTitle',occupation.title,'sourceTasks',count(task.task_id),
    'weightingEligibleTasks',count(task.task_id) FILTER (WHERE task.weighting_eligible),
    'sourceVersion',max(task.source_version),'currentContextRatings',(
      SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=selection.occupation_code
        AND rating.is_current AND rating.element_type='work_context'
    ),'currentActivityRatings',(
      SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=selection.occupation_code
        AND rating.is_current AND rating.element_type='work_activity'
    )),
  '[]'::jsonb,context.source_id,
  '{"phase":"4C","selectionBasis":"occupation_semantics_and_source_metadata_not_score_outcomes"}'::jsonb,
  'system:migration-020'
FROM context JOIN selection ON true
JOIN onet_occupations occupation ON occupation.onet_soc_code=selection.occupation_code AND occupation.is_current
LEFT JOIN onet_tasks task ON task.occupation_code=selection.occupation_code AND task.is_current
GROUP BY context.cohort_id,context.source_id,selection.occupation_code,selection.cohort_order,
  selection.stress_dimensions,selection.selection_rationale,selection.expected_proxy_behavior,occupation.title;

WITH context AS (
  SELECT cohort.id cohort_id,source.id source_id
  FROM phase4c_validation_cohorts cohort
  JOIN data_sources source ON source.name='JobsVsAI Phase 4C targeted validation'
  WHERE cohort.cohort_version='phase4c-2026q3-v1'
), expectation(metric,higher_code,lower_code,minimum_delta,rationale) AS (VALUES
  ('physical-presence','51-4041.00','27-3042.00',20.0,'Machining requires materially more physical activity and equipment presence than technical writing.'),
  ('physical-presence','39-5012.00','15-1212.00',20.0,'Hairdressing requires direct manual service delivery while information security is primarily digital.'),
  ('physical-presence','33-3051.00','15-1212.00',15.0,'Patrol work requires materially more real-world physical presence than information security.'),
  ('physical-presence','47-2111.00','15-1252.00',20.0,'Electricians provide the retained physical-versus-digital continuity comparison.'),
  ('environment-variability','53-3032.00','27-3042.00',20.0,'Heavy trucking operates in uncontrolled changing environments unlike technical writing.'),
  ('environment-variability','33-3051.00','15-1212.00',20.0,'Patrol work faces materially more environmental variability than information security.'),
  ('human-dependency','21-1022.00','27-3042.00',20.0,'Healthcare social work depends more directly on live human relationships than technical writing.'),
  ('human-dependency','25-2021.00','51-4041.00',20.0,'Elementary teaching depends more directly on sustained human interaction than machining.'),
  ('human-dependency','29-1141.00','15-1212.00',15.0,'Registered nursing depends more directly on human care interaction than information security.'),
  ('human-dependency','29-1171.00','15-1252.00',15.0,'Nurse practitioners provide the retained care-versus-software continuity comparison.'),
  ('regulation','29-1141.00','39-5012.00',15.0,'Registered nursing should reflect materially stronger regulated-care requirements than hairdressing.'),
  ('regulation','15-1212.00','39-5012.00',10.0,'Information security includes material standards and compliance responsibilities.'),
  ('accountability','33-3051.00','27-3042.00',20.0,'Patrol decisions carry materially greater formal accountability than technical writing.'),
  ('accountability','29-1141.00','41-2031.00',15.0,'Registered nursing carries materially greater decision accountability than retail sales.'),
  ('consequence-severity','33-3051.00','27-3042.00',25.0,'Errors in patrol work can have much more severe real-world consequences than technical writing.'),
  ('consequence-severity','29-1141.00','39-5012.00',20.0,'Nursing errors can have materially more severe consequences than hairdressing errors.'),
  ('consequence-severity','29-1171.00','27-1024.00',20.0,'Nurse practitioners provide the retained clinical-versus-creative continuity comparison.'),
  ('adoption-pressure','15-1212.00','39-5012.00',20.0,'Information security is more digitally mediated and computer-intensive than hairdressing.'),
  ('adoption-pressure','27-3042.00','51-4041.00',15.0,'Technical writing should face stronger near-term digital workflow pressure than machining.'),
  ('adoption-pressure','13-2011.00','35-2014.00',20.0,'Accountants and cooks provide the retained information-versus-physical adoption comparison.'),
  ('labour-market-resilience','39-5012.00','27-3042.00',15.0,'Direct manual and interpersonal delivery should make hairdressing structurally more resilient than technical writing.'),
  ('labour-market-resilience','33-3051.00','15-1212.00',15.0,'Real-world patrol duties should be structurally more resilient than primarily digital information-security work.'),
  ('labour-market-resilience','29-1141.00','15-1212.00',10.0,'Direct clinical care should be structurally more resilient than primarily digital information-security work.'),
  ('labour-market-resilience','47-2111.00','15-1252.00',20.0,'Electricians provide the retained physical-trade-versus-software continuity comparison.')
)
INSERT INTO phase4c_proxy_pairwise_expectations (
  cohort_id,expectation_version,proxy_metric,higher_occupation_id,lower_occupation_id,
  minimum_delta,rationale,evidence,source_id,provenance,created_by
)
SELECT context.cohort_id,'phase4c-directional-expectations-v1',expectation.metric,
  higher.id,lower.id,expectation.minimum_delta,expectation.rationale,
  jsonb_build_array(jsonb_build_object('source','pre_scoring_occupation_selection_rationale',
    'higherOccupationCode',expectation.higher_code,'lowerOccupationCode',expectation.lower_code)),
  context.source_id,'{"phase":"4C","definedBeforeProxyEvaluation":true}'::jsonb,'system:migration-020'
FROM context JOIN expectation ON true
JOIN phase4c_validation_occupations higher
  ON higher.cohort_id=context.cohort_id AND higher.occupation_code=expectation.higher_code
JOIN phase4c_validation_occupations lower
  ON lower.cohort_id=context.cohort_id AND lower.occupation_code=expectation.lower_code;

CREATE TRIGGER phase4c_occupations_append_only
  BEFORE UPDATE OR DELETE ON phase4c_validation_occupations
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_mapping_scope_append_only
  BEFORE UPDATE OR DELETE ON phase4c_task_mapping_scope
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_proxy_snapshots_append_only
  BEFORE UPDATE OR DELETE ON phase4c_proxy_snapshots
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_calculation_runs_append_only
  BEFORE UPDATE OR DELETE ON phase4c_calculation_runs
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_task_assessments_append_only
  BEFORE UPDATE OR DELETE ON phase4c_task_assessments
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_occupation_scores_append_only
  BEFORE UPDATE OR DELETE ON phase4c_occupation_scores
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_expectations_append_only
  BEFORE UPDATE OR DELETE ON phase4c_proxy_pairwise_expectations
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4c_results_append_only
  BEFORE UPDATE OR DELETE ON phase4c_proxy_validation_results
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
