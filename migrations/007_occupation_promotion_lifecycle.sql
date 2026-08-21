BEGIN;

ALTER TABLE source_occupation_titles
  DROP CONSTRAINT IF EXISTS source_occupation_titles_title_type_check;
ALTER TABLE source_occupation_titles
  ADD CONSTRAINT source_occupation_titles_title_type_check
  CHECK (title_type IN ('preferred','alternate','short','reported','historical'));
UPDATE source_occupation_titles SET locale='en' WHERE locale='en-US';
ALTER TABLE source_occupation_titles ALTER COLUMN locale SET DEFAULT 'en';

CREATE TABLE IF NOT EXISTS canonical_occupation_identities (
  id BIGSERIAL PRIMARY KEY,
  identity_key TEXT NOT NULL UNIQUE,
  current_source_code TEXT UNIQUE REFERENCES onet_occupations(onet_soc_code) ON DELETE SET NULL,
  jobs_vs_ai_occupation_id BIGINT UNIQUE REFERENCES occupations(id) ON DELETE SET NULL,
  identity_origin TEXT NOT NULL CHECK (identity_origin IN ('source_import','existing_editorial')),
  created_by_policy TEXT NOT NULL,
  source_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS occupation_identity_resolutions (
  id BIGSERIAL PRIMARY KEY,
  succession_id BIGINT REFERENCES source_occupation_successions(id) ON DELETE CASCADE,
  source_taxonomy_id BIGINT REFERENCES source_taxonomies(id),
  source_occupation_code TEXT NOT NULL,
  target_identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id) ON DELETE CASCADE,
  target_occupation_code TEXT NOT NULL REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  resolution_type TEXT NOT NULL CHECK (resolution_type IN (
    'unchanged_continuity','renamed_continuity','recoded_continuity',
    'merge_new_identity','split_new_identity','complex_manual','new_source_identity'
  )),
  automatic_allowed BOOLEAN NOT NULL,
  review_status TEXT NOT NULL CHECK (review_status IN ('auto_resolved','pending','approved','rejected')),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  notes TEXT NOT NULL DEFAULT '',
  allocation_weight NUMERIC CHECK (allocation_weight IS NULL OR allocation_weight BETWEEN 0 AND 1),
  policy_version TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_record_id BIGINT NOT NULL REFERENCES source_record_versions(id),
  source_version TEXT NOT NULL,
  row_hash CHAR(64) NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  UNIQUE NULLS NOT DISTINCT (succession_id, source_occupation_code, target_occupation_code)
);

COMMENT ON COLUMN occupation_identity_resolutions.allocation_weight IS
  'Must remain NULL unless an official source supplies an allocation. JobsVsAI never invents taxonomy succession weights.';

CREATE TABLE IF NOT EXISTS occupation_promotion_profiles (
  identity_id BIGINT PRIMARY KEY REFERENCES canonical_occupation_identities(id) ON DELETE CASCADE,
  source_occupation_code TEXT NOT NULL UNIQUE REFERENCES onet_occupations(onet_soc_code) ON DELETE CASCADE,
  lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN (
    'source_imported','normalized','identity_resolved','scoring_ready','scored',
    'editorially_approved','public'
  )),
  ingestion_eligible BOOLEAN NOT NULL DEFAULT true,
  scoring_eligible BOOLEAN NOT NULL DEFAULT false,
  public_activation_eligible BOOLEAN NOT NULL DEFAULT false,
  lifecycle_policy_version TEXT NOT NULL,
  scoring_policy_version TEXT NOT NULL,
  blocking_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_version TEXT NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS occupation_publications (
  identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id) ON DELETE CASCADE,
  locale TEXT NOT NULL DEFAULT 'en',
  country TEXT,
  canonical_public_title TEXT NOT NULL,
  seo_slug TEXT NOT NULL,
  source_geography TEXT NOT NULL DEFAULT 'US',
  activation_status TEXT NOT NULL CHECK (activation_status IN ('staged','review_required','approved','public','inactive')),
  editorial_review_status TEXT NOT NULL CHECK (editorial_review_status IN ('not_required','pending','approved','rejected')),
  title_source TEXT NOT NULL CHECK (title_source IN ('onet_preferred','jobsvsai_editorial')),
  review_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (identity_id, locale, source_geography),
  UNIQUE (locale, source_geography, seo_slug)
);

CREATE TABLE IF NOT EXISTS occupation_search_aliases (
  id BIGSERIAL PRIMARY KEY,
  identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id) ON DELETE CASCADE,
  source_title_id BIGINT REFERENCES source_occupation_titles(id) ON DELETE SET NULL,
  alias TEXT NOT NULL,
  locale TEXT NOT NULL DEFAULT 'en',
  source_geography TEXT NOT NULL DEFAULT 'US',
  searchable BOOLEAN NOT NULL DEFAULT false,
  activation_status TEXT NOT NULL CHECK (activation_status IN ('staged','approved','active','rejected')),
  editorial_review_status TEXT NOT NULL CHECK (editorial_review_status IN ('not_required','pending','approved','rejected')),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  import_run_id BIGINT NOT NULL REFERENCES import_runs(id),
  source_version TEXT NOT NULL,
  UNIQUE (identity_id, alias, locale, source_geography)
);

CREATE TABLE IF NOT EXISTS occupation_localizations (
  identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id) ON DELETE CASCADE,
  locale TEXT NOT NULL,
  country TEXT NOT NULL,
  public_title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  salary_source_id BIGINT REFERENCES data_sources(id),
  market_source_id BIGINT REFERENCES data_sources(id),
  review_status TEXT NOT NULL CHECK (review_status IN ('draft','pending','approved','rejected')),
  is_public BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (identity_id, locale, country)
);

ALTER TABLE onet_element_ratings
  ADD COLUMN IF NOT EXISTS skill_classification TEXT
    CHECK (skill_classification IS NULL OR skill_classification IN ('essential','transferable'));

COMMENT ON COLUMN onet_element_ratings.skill_classification IS
  'Immutable O*NET source semantic. Future JobsVsAI skill relevance and transition semantics belong in separate derived tables.';

CREATE TABLE IF NOT EXISTS source_attribution_requirements (
  source_id BIGINT NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
  source_version TEXT NOT NULL,
  license_name TEXT NOT NULL,
  license_url TEXT NOT NULL,
  attribution_text TEXT NOT NULL,
  publisher_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  publication_required BOOLEAN NOT NULL DEFAULT true,
  publication_gate TEXT NOT NULL DEFAULT 'before_public_activation',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (source_id, source_version)
);

CREATE OR REPLACE VIEW occupation_promotion_matrix AS
SELECT
  count(*) AS source_imported,
  count(*) FILTER (WHERE profile.lifecycle_state IN (
    'normalized','identity_resolved','scoring_ready','scored','editorially_approved','public'
  )) AS normalized,
  count(*) FILTER (WHERE profile.lifecycle_state IN (
    'identity_resolved','scoring_ready','scored','editorially_approved','public'
  )) AS identity_resolved,
  count(*) FILTER (WHERE profile.scoring_eligible) AS scoring_ready,
  count(*) FILTER (WHERE NOT profile.scoring_eligible) AS insufficient_for_scoring,
  count(*) FILTER (WHERE resolution.review_status='pending') AS identity_review_required,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM onet_occupation_domain_coverage coverage
    WHERE coverage.occupation_code=profile.source_occupation_code
      AND coverage.coverage_status IN ('partial','missing')
  )) AS partial_data,
  count(*) FILTER (WHERE profile.public_activation_eligible) AS public_ready,
  count(*) FILTER (WHERE publication.activation_status='public') AS public
FROM occupation_promotion_profiles profile
LEFT JOIN LATERAL (
  SELECT CASE WHEN bool_or(review_status='pending') THEN 'pending' ELSE 'resolved' END review_status
  FROM occupation_identity_resolutions item WHERE item.target_identity_id=profile.identity_id AND item.is_current
) resolution ON true
LEFT JOIN occupation_publications publication
  ON publication.identity_id=profile.identity_id AND publication.locale='en' AND publication.source_geography='US';

COMMIT;
