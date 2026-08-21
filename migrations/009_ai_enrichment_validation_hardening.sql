BEGIN;

CREATE OR REPLACE FUNCTION validate_task_environment_constraint_mapping(mapping_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  taxonomy_status TEXT;
BEGIN
  SELECT taxonomy.status INTO taxonomy_status
  FROM task_environment_constraint_mappings mapping
  JOIN task_environment_constraint_definitions definition ON definition.id=mapping.constraint_definition_id
  JOIN task_environment_taxonomy_versions taxonomy ON taxonomy.id=definition.environment_taxonomy_version_id
  WHERE mapping.id=mapping_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown environment constraint mapping %', mapping_key; END IF;
  IF taxonomy_status='retired' THEN RAISE EXCEPTION 'Constraint mapping % references retired taxonomy', mapping_key; END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION validate_task_ai_enrichment_assessment(assessment_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  assessment_row task_ai_enrichment_assessments%ROWTYPE;
  mapping_taxonomy BIGINT;
  snapshot_taxonomy BIGINT;
  taxonomy_status TEXT;
BEGIN
  SELECT * INTO assessment_row FROM task_ai_enrichment_assessments WHERE id=assessment_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown task enrichment assessment %', assessment_key; END IF;
  SELECT status INTO taxonomy_status FROM ai_capability_taxonomy_versions WHERE id=assessment_row.taxonomy_version_id;
  IF taxonomy_status='retired' THEN RAISE EXCEPTION 'Assessment % references retired taxonomy', assessment_key; END IF;
  IF assessment_row.capability_mapping_set_id IS NOT NULL THEN
    SELECT taxonomy_version_id INTO mapping_taxonomy FROM task_capability_mapping_sets WHERE id=assessment_row.capability_mapping_set_id;
    IF mapping_taxonomy<>assessment_row.taxonomy_version_id THEN
      RAISE EXCEPTION 'Assessment % mapping set taxonomy mismatch', assessment_key;
    END IF;
  END IF;
  IF assessment_row.benchmark_snapshot_id IS NOT NULL THEN
    SELECT taxonomy_version_id INTO snapshot_taxonomy FROM ai_capability_benchmark_snapshots WHERE id=assessment_row.benchmark_snapshot_id;
    IF snapshot_taxonomy<>assessment_row.taxonomy_version_id THEN
      RAISE EXCEPTION 'Assessment % benchmark taxonomy mismatch', assessment_key;
    END IF;
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION enforce_environment_constraint_mapping()
RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_environment_constraint_mapping(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER environment_constraint_mapping_version_valid
AFTER INSERT ON task_environment_constraint_mappings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_environment_constraint_mapping();

CREATE OR REPLACE FUNCTION enforce_task_ai_enrichment_assessment()
RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN PERFORM validate_task_ai_enrichment_assessment(NEW.id); RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER task_ai_assessment_versions_reconcile
AFTER INSERT ON task_ai_enrichment_assessments
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_task_ai_enrichment_assessment();

DROP VIEW ai_enrichment_validation;
CREATE VIEW ai_enrichment_validation AS
SELECT
  (SELECT count(*) FROM task_capability_mapping_sets mapping_set
    WHERE mapping_set.review_state IN ('test_validated','reviewed')
      AND abs((SELECT coalesce(sum(weight),0) FROM task_capability_requirement_mappings mapping WHERE mapping.mapping_set_id=mapping_set.id)-1)>0.000001
  ) invalid_mapping_sets,
  (SELECT count(*) FROM ai_capability_benchmark_snapshots snapshot
    WHERE snapshot.review_state IN ('test_validated','reviewed')
      AND snapshot.expected_capability_count<>(SELECT count(*) FROM ai_capability_benchmark_scores score WHERE score.snapshot_id=snapshot.id)
  ) invalid_snapshots,
  (SELECT count(*) FROM task_environment_constraint_mappings mapping
    JOIN task_environment_constraint_definitions definition ON definition.id=mapping.constraint_definition_id
    JOIN task_environment_taxonomy_versions taxonomy ON taxonomy.id=definition.environment_taxonomy_version_id
    WHERE taxonomy.status='retired'
  ) invalid_constraint_mappings,
  (SELECT count(*) FROM task_ai_enrichment_assessments assessment
    LEFT JOIN task_capability_mapping_sets mapping_set ON mapping_set.id=assessment.capability_mapping_set_id
    LEFT JOIN ai_capability_benchmark_snapshots snapshot ON snapshot.id=assessment.benchmark_snapshot_id
    WHERE (mapping_set.id IS NOT NULL AND mapping_set.taxonomy_version_id<>assessment.taxonomy_version_id)
       OR (snapshot.id IS NOT NULL AND snapshot.taxonomy_version_id<>assessment.taxonomy_version_id)
  ) invalid_assessments,
  (SELECT count(*) FROM task_ai_enrichment_assessments) task_assessments,
  (SELECT count(*) FROM ai_capability_benchmark_scores) benchmark_scores,
  (SELECT count(*) FROM occupation_scores) production_score_rows,
  (SELECT count(*) FROM task_ai_scores) legacy_task_ai_score_rows;

COMMIT;
