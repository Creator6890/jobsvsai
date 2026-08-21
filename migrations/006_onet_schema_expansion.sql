BEGIN;

ALTER TABLE source_record_versions
  ADD COLUMN IF NOT EXISTS dataset_version TEXT;

UPDATE source_record_versions
SET dataset_version = source_version
WHERE dataset_version IS NULL;

ALTER TABLE source_record_versions
  ALTER COLUMN dataset_version SET NOT NULL;

COMMENT ON TABLE occupation_categories IS
  'JobsVsAI editorial taxonomy. Source taxonomies such as SOC and O*NET-SOC are stored separately in source_taxonomies.';

CREATE TABLE IF NOT EXISTS onet_scales (
  scale_id TEXT PRIMARY KEY,
  scale_name TEXT NOT NULL,
  minimum NUMERIC,
  maximum NUMERIC,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE onet_task_ratings
  ADD CONSTRAINT onet_task_ratings_scale_fk
  FOREIGN KEY (scale_id) REFERENCES onet_scales(scale_id) NOT VALID;

ALTER TABLE onet_element_ratings
  ADD CONSTRAINT onet_element_ratings_scale_fk
  FOREIGN KEY (scale_id) REFERENCES onet_scales(scale_id) NOT VALID;

CREATE TABLE IF NOT EXISTS source_taxonomies (
  id BIGSERIAL PRIMARY KEY,
  taxonomy_code TEXT NOT NULL,
  name TEXT NOT NULL,
  taxonomy_kind TEXT NOT NULL CHECK (taxonomy_kind IN ('occupation','category')),
  taxonomy_version TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  source_uri TEXT NOT NULL,
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (taxonomy_code, taxonomy_version)
);

CREATE TABLE IF NOT EXISTS source_taxonomy_nodes (
  id BIGSERIAL PRIMARY KEY,
  taxonomy_id BIGINT NOT NULL REFERENCES source_taxonomies(id) ON DELETE CASCADE,
  external_code TEXT NOT NULL,
  parent_external_code TEXT,
  node_type TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  hierarchy_level INTEGER,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (taxonomy_id, external_code)
);

CREATE INDEX IF NOT EXISTS source_taxonomy_nodes_parent_idx
  ON source_taxonomy_nodes(taxonomy_id, parent_external_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS source_occupation_taxonomy_memberships (
  taxonomy_id BIGINT NOT NULL REFERENCES source_taxonomies(id) ON DELETE CASCADE,
  node_id BIGINT NOT NULL REFERENCES source_taxonomy_nodes(id) ON DELETE CASCADE,
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  relation_type TEXT NOT NULL DEFAULT 'primary',
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (taxonomy_id, node_id, occupation_code, relation_type)
);

CREATE TABLE IF NOT EXISTS source_occupation_titles (
  id BIGSERIAL PRIMARY KEY,
  taxonomy_id BIGINT NOT NULL REFERENCES source_taxonomies(id) ON DELETE CASCADE,
  occupation_code TEXT NOT NULL,
  title TEXT NOT NULL,
  title_type TEXT NOT NULL CHECK (title_type IN ('preferred','alternate','short','reported')),
  locale TEXT NOT NULL DEFAULT 'en-US',
  source_title_type TEXT,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (taxonomy_id, occupation_code, title, title_type, locale)
);

CREATE INDEX IF NOT EXISTS source_occupation_titles_lookup_idx
  ON source_occupation_titles(taxonomy_id, occupation_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS source_occupation_successions (
  id BIGSERIAL PRIMARY KEY,
  predecessor_taxonomy_id BIGINT NOT NULL REFERENCES source_taxonomies(id),
  predecessor_code TEXT NOT NULL,
  predecessor_title TEXT NOT NULL,
  successor_taxonomy_id BIGINT NOT NULL REFERENCES source_taxonomies(id),
  successor_code TEXT NOT NULL,
  successor_title TEXT NOT NULL,
  mapping_type TEXT NOT NULL CHECK (mapping_type IN ('unchanged','renamed','recoded','split','merge','complex')),
  allocation_weight NUMERIC CHECK (allocation_weight IS NULL OR allocation_weight BETWEEN 0 AND 1),
  effective_version TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (predecessor_taxonomy_id, predecessor_code, successor_taxonomy_id, successor_code)
);

ALTER TABLE onet_tasks
  ADD COLUMN IF NOT EXISTS rating_status TEXT NOT NULL DEFAULT 'missing_both'
    CHECK (rating_status IN ('complete','missing_importance','missing_frequency','missing_both')),
  ADD COLUMN IF NOT EXISTS weighting_eligible BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS rating_policy_version TEXT NOT NULL DEFAULT 'onet-task-rating-v1',
  ADD COLUMN IF NOT EXISTS missing_rating_fields TEXT[] NOT NULL DEFAULT ARRAY['importance','frequency']::TEXT[];

COMMENT ON COLUMN onet_tasks.weighting_eligible IS
  'False unless both source importance and source frequency are available. Missing values are never imputed.';

ALTER TABLE onet_related_occupations
  ADD COLUMN IF NOT EXISTS relation_namespace TEXT NOT NULL DEFAULT 'onet_relatedness'
    CHECK (relation_namespace = 'onet_relatedness');

COMMENT ON TABLE onet_related_occupations IS
  'Source-authored O*NET related occupations only; not JobsVsAI skill similarity or career-transition recommendations.';

CREATE TABLE IF NOT EXISTS onet_occupation_domain_coverage (
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  domain TEXT NOT NULL CHECK (domain IN (
    'titles','tasks','task_ratings','skills','abilities','work_activities','work_context',
    'related_occupations','source_taxonomy','soc_succession'
  )),
  entity_count INTEGER NOT NULL DEFAULT 0 CHECK (entity_count >= 0),
  rating_count INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
  coverage_status TEXT NOT NULL CHECK (coverage_status IN ('complete','partial','missing','present','not_applicable')),
  issues JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_version TEXT NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (occupation_code, domain)
);

COMMIT;
