BEGIN;

-- Migration 020 defined the added-selection CTE but omitted its INSERT clause in
-- the first applied local database. This idempotent correction preserves that
-- history while making both upgraded and fresh databases converge.
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
  'system:migration-021'
FROM context JOIN selection ON true
JOIN onet_occupations occupation ON occupation.onet_soc_code=selection.occupation_code AND occupation.is_current
LEFT JOIN onet_tasks task ON task.occupation_code=selection.occupation_code AND task.is_current
GROUP BY context.cohort_id,context.source_id,selection.occupation_code,selection.cohort_order,
  selection.stress_dimensions,selection.selection_rationale,selection.expected_proxy_behavior,occupation.title
ON CONFLICT (cohort_id,occupation_code) DO NOTHING;

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
  context.source_id,'{"phase":"4C","definedBeforeProxyEvaluation":true}'::jsonb,'system:migration-021'
FROM context JOIN expectation ON true
JOIN phase4c_validation_occupations higher
  ON higher.cohort_id=context.cohort_id AND higher.occupation_code=expectation.higher_code
JOIN phase4c_validation_occupations lower
  ON lower.cohort_id=context.cohort_id AND lower.occupation_code=expectation.lower_code
ON CONFLICT (cohort_id,proxy_metric,higher_occupation_id,lower_occupation_id) DO NOTHING;

COMMIT;
