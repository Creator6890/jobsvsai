BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE data_sources (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  source_url TEXT,
  version TEXT,
  published_at TIMESTAMPTZ,
  retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE occupation_categories (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE occupations (
  id BIGSERIAL PRIMARY KEY,
  external_code TEXT UNIQUE,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  category_id BIGINT NOT NULL REFERENCES occupation_categories(id),
  summary TEXT NOT NULL DEFAULT '',
  verdict TEXT NOT NULL DEFAULT '',
  is_active BOOLEAN NOT NULL DEFAULT true,
  source_id BIGINT REFERENCES data_sources(id),
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX occupations_title_trgm_idx ON occupations USING gin (title gin_trgm_ops);
CREATE INDEX occupations_category_idx ON occupations(category_id) WHERE is_active;

CREATE TABLE tasks (
  id BIGSERIAL PRIMARY KEY,
  external_code TEXT UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_id BIGINT REFERENCES data_sources(id),
  UNIQUE(name)
);

CREATE TABLE skills (
  id BIGSERIAL PRIMARY KEY,
  external_code TEXT UNIQUE,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  source_id BIGINT REFERENCES data_sources(id)
);

CREATE TABLE occupation_tasks (
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  importance NUMERIC(5,2) NOT NULL CHECK (importance BETWEEN 0 AND 100),
  frequency NUMERIC(5,2) CHECK (frequency BETWEEN 0 AND 100),
  is_resilient BOOLEAN NOT NULL DEFAULT false,
  source_version TEXT,
  PRIMARY KEY (occupation_id, task_id)
);
CREATE INDEX occupation_tasks_task_idx ON occupation_tasks(task_id);

CREATE TABLE occupation_skills (
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  skill_id BIGINT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  importance NUMERIC(5,2) NOT NULL CHECK (importance BETWEEN 0 AND 100),
  PRIMARY KEY (occupation_id, skill_id)
);

CREATE TABLE ai_capabilities (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  capability_level NUMERIC(5,2) NOT NULL CHECK (capability_level BETWEEN 0 AND 100),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  version TEXT NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_id BIGINT REFERENCES data_sources(id)
);

CREATE TABLE task_ai_scores (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  capability_id BIGINT REFERENCES ai_capabilities(id),
  exposure NUMERIC(5,2) NOT NULL CHECK (exposure BETWEEN 0 AND 100),
  confidence NUMERIC(5,2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(task_id, capability_id, calculated_at)
);
CREATE INDEX task_ai_scores_latest_idx ON task_ai_scores(task_id, calculated_at DESC);

CREATE TABLE scoring_model_versions (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  exposure_config JSONB NOT NULL,
  replacement_config JSONB NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_active_scoring_model_idx ON scoring_model_versions(is_active) WHERE is_active;

CREATE TABLE occupation_scores (
  id BIGSERIAL PRIMARY KEY,
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  model_version_id BIGINT NOT NULL REFERENCES scoring_model_versions(id),
  ai_exposure NUMERIC(5,2) NOT NULL CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(5,2) NOT NULL CHECK (replacement_risk BETWEEN 0 AND 100),
  confidence TEXT NOT NULL CHECK (confidence IN ('High','Medium','Low')),
  trend TEXT NOT NULL CHECK (trend IN ('Rising','Stable','Falling')),
  human_dependency NUMERIC(5,2) NOT NULL,
  physical_dependency NUMERIC(5,2) NOT NULL,
  adoption_pressure NUMERIC(5,2) NOT NULL,
  market_resilience NUMERIC(5,2) NOT NULL,
  salary_potential NUMERIC(5,2) NOT NULL,
  future_demand NUMERIC(5,2) NOT NULL,
  input_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(occupation_id, model_version_id, calculated_at)
);
CREATE INDEX occupation_scores_latest_idx ON occupation_scores(occupation_id, calculated_at DESC);
CREATE INDEX occupation_scores_exposure_idx ON occupation_scores(ai_exposure DESC);
CREATE INDEX occupation_scores_risk_idx ON occupation_scores(replacement_risk DESC);

CREATE TABLE score_history (
  id BIGSERIAL PRIMARY KEY,
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  model_version_id BIGINT NOT NULL REFERENCES scoring_model_versions(id),
  ai_exposure NUMERIC(5,2) NOT NULL,
  replacement_risk NUMERIC(5,2) NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,
  source_score_id BIGINT REFERENCES occupation_scores(id),
  UNIQUE(occupation_id, model_version_id, snapshot_at)
);

CREATE TABLE career_relationships (
  source_occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  target_occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (relationship_type IN ('adjacent','related','comparison')),
  skill_overlap NUMERIC(5,2) NOT NULL CHECK (skill_overlap BETWEEN 0 AND 100),
  transition_difficulty TEXT NOT NULL,
  retraining_months TEXT NOT NULL,
  fit_score NUMERIC(5,2) NOT NULL CHECK (fit_score BETWEEN 0 AND 100),
  model_version_id BIGINT REFERENCES scoring_model_versions(id),
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (source_occupation_id, target_occupation_id, relationship_type)
);

CREATE TABLE market_signals (
  id BIGSERIAL PRIMARY KEY,
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  country_code CHAR(2) NOT NULL,
  signal_type TEXT NOT NULL,
  value NUMERIC(14,4) NOT NULL,
  observed_at DATE NOT NULL,
  source_id BIGINT REFERENCES data_sources(id),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(occupation_id, country_code, signal_type, observed_at, source_id)
);
CREATE INDEX market_signals_lookup_idx ON market_signals(occupation_id, country_code, observed_at DESC);

CREATE TABLE import_runs (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT REFERENCES data_sources(id),
  status TEXT NOT NULL CHECK (status IN ('pending','running','complete','failed')),
  records_read INTEGER NOT NULL DEFAULT 0,
  records_written INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE scoring_jobs (
  id BIGSERIAL PRIMARY KEY,
  occupation_id BIGINT REFERENCES occupations(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  dependency_type TEXT,
  dependency_id BIGINT,
  status TEXT NOT NULL CHECK (status IN ('pending','running','complete','failed')) DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);
CREATE INDEX scoring_jobs_queue_idx ON scoring_jobs(status, queued_at) WHERE status IN ('pending','running');

COMMIT;
