BEGIN;

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

COMMIT;
