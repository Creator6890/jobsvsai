BEGIN;

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
  IF dataset_row.status IN ('test_validated','reviewed') AND (dataset_row.reviewed_by IS NULL OR dataset_row.reviewed_at IS NULL OR jsonb_array_length(dataset_row.evidence)=0) THEN
    RAISE EXCEPTION 'Gold dataset % lacks reviewer or evidence provenance',dataset_key;
  END IF;
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

COMMIT;
