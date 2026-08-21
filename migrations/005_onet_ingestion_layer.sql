BEGIN;

ALTER TABLE import_runs
  ADD COLUMN IF NOT EXISTS run_key TEXT,
  ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'full',
  ADD COLUMN IF NOT EXISTS source_version TEXT,
  ADD COLUMN IF NOT EXISTS manifest JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS import_runs_run_key_idx ON import_runs(run_key);

CREATE TABLE IF NOT EXISTS source_record_versions (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  first_seen_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  last_seen_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  dataset_name TEXT NOT NULL,
  natural_key TEXT NOT NULL,
  source_version TEXT NOT NULL,
  source_uri TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  payload JSONB NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_at TIMESTAMPTZ,
  UNIQUE (source_id, dataset_name, natural_key, row_hash)
);
CREATE UNIQUE INDEX IF NOT EXISTS source_record_versions_current_idx
  ON source_record_versions(source_id, dataset_name, natural_key) WHERE is_current;
CREATE INDEX IF NOT EXISTS source_record_versions_lookup_idx
  ON source_record_versions(dataset_name, natural_key, source_version);

CREATE TABLE IF NOT EXISTS onet_occupations (
  onet_soc_code TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  jobs_vs_ai_occupation_id BIGINT REFERENCES occupations(id) ON DELETE SET NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS onet_occupations_product_link_idx
  ON onet_occupations(jobs_vs_ai_occupation_id) WHERE jobs_vs_ai_occupation_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS onet_alternate_titles (
  id BIGSERIAL PRIMARY KEY,
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  job_title TEXT NOT NULL,
  short_title TEXT NOT NULL DEFAULT '',
  title_sources TEXT NOT NULL DEFAULT '',
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (occupation_code, job_title, short_title)
);
CREATE INDEX IF NOT EXISTS onet_alternate_titles_occupation_idx
  ON onet_alternate_titles(occupation_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS onet_tasks (
  task_id BIGINT PRIMARY KEY,
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  statement TEXT NOT NULL,
  task_type TEXT,
  incumbents_responding INTEGER,
  observed_date TEXT,
  domain_source TEXT,
  importance_score NUMERIC(7,4),
  frequency_score NUMERIC(7,4),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS onet_tasks_occupation_idx ON onet_tasks(occupation_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS onet_task_ratings (
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  task_id BIGINT NOT NULL REFERENCES onet_tasks(task_id) ON DELETE CASCADE,
  scale_id TEXT NOT NULL,
  scale_name TEXT NOT NULL,
  category INTEGER NOT NULL DEFAULT -1,
  data_value NUMERIC,
  normalized_value NUMERIC(7,4),
  sample_size INTEGER,
  standard_error NUMERIC,
  lower_ci NUMERIC,
  upper_ci NUMERIC,
  recommend_suppress BOOLEAN NOT NULL DEFAULT false,
  observed_date TEXT,
  domain_source TEXT,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (occupation_code, task_id, scale_id, category)
);
CREATE INDEX IF NOT EXISTS onet_task_ratings_task_idx ON onet_task_ratings(task_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS onet_elements (
  element_type TEXT NOT NULL CHECK (element_type IN ('skill','ability','work_activity','work_context')),
  element_id TEXT NOT NULL,
  element_name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (element_type, element_id)
);

CREATE TABLE IF NOT EXISTS onet_element_ratings (
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  element_type TEXT NOT NULL,
  element_id TEXT NOT NULL,
  scale_id TEXT NOT NULL,
  scale_name TEXT NOT NULL,
  category INTEGER NOT NULL DEFAULT -1,
  data_value NUMERIC,
  normalized_value NUMERIC(7,4),
  sample_size INTEGER,
  standard_error NUMERIC,
  lower_ci NUMERIC,
  upper_ci NUMERIC,
  recommend_suppress BOOLEAN NOT NULL DEFAULT false,
  not_relevant BOOLEAN,
  observed_date TEXT,
  domain_source TEXT,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (occupation_code, element_type, element_id, scale_id, category),
  FOREIGN KEY (element_type, element_id) REFERENCES onet_elements(element_type, element_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS onet_element_ratings_occupation_idx
  ON onet_element_ratings(occupation_code, element_type) WHERE is_current;

CREATE TABLE IF NOT EXISTS onet_work_context_categories (
  element_id TEXT NOT NULL,
  scale_id TEXT NOT NULL,
  category INTEGER NOT NULL,
  element_name TEXT NOT NULL,
  scale_name TEXT NOT NULL,
  category_description TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY (element_id, scale_id, category)
);

CREATE TABLE IF NOT EXISTS onet_related_occupations (
  occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  related_occupation_code TEXT NOT NULL,
  related_title TEXT NOT NULL,
  relatedness_tier TEXT NOT NULL,
  relatedness_rank INTEGER NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (occupation_code, related_occupation_code, relatedness_tier, relatedness_rank)
);
CREATE INDEX IF NOT EXISTS onet_related_occupations_source_idx
  ON onet_related_occupations(occupation_code) WHERE is_current;

COMMIT;
