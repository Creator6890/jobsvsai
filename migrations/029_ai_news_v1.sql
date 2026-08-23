-- 029 — AI News v1.
--
-- A news-significance layer. It is NOT occupation scoring and shares nothing with it.
--
-- THE SEPARATION RULE, ENFORCED BY ISOLATION
-- ------------------------------------------
-- Nothing in this migration references `occupations`, `occupation_publications`,
-- `production_occupation_score_snapshots`, `scoring_model_versions` or any Phase 4/5/6
-- table. Jobs Impact answers "how significant is this development for work?" for one news
-- event. AI Exposure and Replacement Risk answer a different question about an occupation,
-- from O*NET evidence, under a different versioned methodology. A news article can never
-- move an occupation score because there is no path between them — not a policy, a schema
-- fact.
--
-- `job_areas` are free-text editorial groupings ("Software Development", "Legal"), never
-- SOC codes and never canonical occupation identities. Linking them would create exactly
-- the coupling this design exists to prevent.
--
-- PROVENANCE AND COPYRIGHT
-- ------------------------
-- `news_ingest_items` holds third-party material: the original title, a short excerpt and
-- the URL. `news_articles` holds only JobsVsAI-written prose. The two never merge. A public
-- page renders the JobsVsAI columns and links out; it never republishes a source body.
--
-- IMPACT IS COMPUTED, NOT ASSERTED
-- --------------------------------
-- A generation provider returns five 0-100 factor readings and a confidence. It does not
-- return a level. `impact_score` and `impact_level` are computed by news-impact-v1 in
-- application code from those factors, so the same factors always yield the same level.

BEGIN;

CREATE TABLE news_sources (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  feed_url TEXT,
  site_url TEXT NOT NULL,
  -- 'primary' is the organisation that did the thing (a lab's own announcement);
  -- 'secondary' is journalism about it.
  source_type TEXT NOT NULL CHECK (source_type IN ('primary','secondary')),
  -- Lower is more trusted. Drives future relevance filtering and dedupe precedence.
  trust_tier SMALLINT NOT NULL DEFAULT 2 CHECK (trust_tier BETWEEN 1 AND 5),
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX news_sources_enabled_idx ON news_sources(enabled, trust_tier);

CREATE TABLE news_ingest_items (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL REFERENCES news_sources(id),
  external_url TEXT NOT NULL,
  -- Redirects and tracking parameters removed. Dedupe keys on this, not on external_url.
  canonical_url TEXT NOT NULL,
  original_title TEXT NOT NULL,
  -- A short excerpt for relevance filtering and admin context. Never rendered publicly.
  original_excerpt TEXT,
  source_published_at TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash CHAR(64) NOT NULL,
  status TEXT NOT NULL DEFAULT 'new'
    CHECK (status IN ('new','duplicate','ignored','candidate','processed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Two independent dedupe axes: the same URL never enters twice, and the same body never
  -- enters twice even when syndicated under different URLs.
  UNIQUE (canonical_url),
  UNIQUE (source_id, content_hash)
);
CREATE INDEX news_ingest_items_status_idx ON news_ingest_items(status, fetched_at DESC);

CREATE TABLE news_articles (
  id BIGSERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,

  -- JobsVsAI original prose. Never a copy of source text.
  headline TEXT NOT NULL,
  what_happened TEXT NOT NULL,
  why_it_matters_for_jobs TEXT NOT NULL,

  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','review_required','published','rejected')),

  -- news-impact-v1 output. Score is internal for V1; only the level is public.
  impact_score NUMERIC(5,2) CHECK (impact_score BETWEEN 0 AND 100),
  impact_level TEXT CHECK (impact_level IN ('low','medium','high')),
  impact_confidence NUMERIC(3,2) CHECK (impact_confidence BETWEEN 0 AND 1),
  impact_reasoning TEXT,
  impact_policy_version TEXT,

  -- The five factors, retained so a score can be recomputed and a future policy version
  -- can be back-tested without re-calling a provider.
  capability_advancement SMALLINT CHECK (capability_advancement BETWEEN 0 AND 100),
  commercial_deployability SMALLINT CHECK (commercial_deployability BETWEEN 0 AND 100),
  breadth_of_affected_work SMALLINT CHECK (breadth_of_affected_work BETWEEN 0 AND 100),
  adoption_speed SMALLINT CHECK (adoption_speed BETWEEN 0 AND 100),
  human_work_reduction_potential SMALLINT CHECK (human_work_reduction_potential BETWEEN 0 AND 100),

  -- What the machine said, preserved verbatim across any editorial override.
  automated_impact_score NUMERIC(5,2) CHECK (automated_impact_score BETWEEN 0 AND 100),
  automated_impact_level TEXT CHECK (automated_impact_level IN ('low','medium','high')),

  generation_provider TEXT,
  generation_model TEXT,
  generation_prompt_version TEXT,
  generated_at TIMESTAMPTZ,

  impact_assessed_at TIMESTAMPTZ,
  impact_assessed_by TEXT,

  impact_overridden_at TIMESTAMPTZ,
  impact_overridden_by TEXT,
  impact_override_reason TEXT,

  published_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- An override is a complete record or it is not an override. Losing who or when would
  -- make the automated/editorial distinction unauditable.
  CHECK (impact_overridden_at IS NULL OR
         (impact_overridden_by IS NOT NULL AND automated_impact_level IS NOT NULL)),

  -- Published articles must be complete. This is the database's half of the publication
  -- guard; the repository enforces the source requirement, which SQL cannot see from here.
  CHECK (status <> 'published' OR (
    published_at IS NOT NULL
    AND length(btrim(headline)) > 0
    AND length(btrim(what_happened)) > 0
    AND length(btrim(why_it_matters_for_jobs)) > 0
    AND impact_level IS NOT NULL
    AND impact_score IS NOT NULL
    AND impact_policy_version IS NOT NULL
  ))
);
CREATE INDEX news_articles_public_idx
  ON news_articles(status, published_at DESC) WHERE status = 'published';
CREATE INDEX news_articles_queue_idx ON news_articles(status, created_at DESC);
CREATE INDEX news_articles_impact_idx
  ON news_articles(impact_level, published_at DESC) WHERE status = 'published';

CREATE TABLE news_article_sources (
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  ingest_item_id BIGINT NOT NULL REFERENCES news_ingest_items(id),
  is_primary BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (article_id, ingest_item_id)
);
-- At most one primary source per article: the "Read original source" link is singular.
CREATE UNIQUE INDEX news_article_primary_source_idx
  ON news_article_sources(article_id) WHERE is_primary;

CREATE TABLE news_article_tags (
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  tag TEXT NOT NULL CHECK (length(btrim(tag)) > 0),
  PRIMARY KEY (article_id, tag)
);

CREATE TABLE news_article_job_areas (
  article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  -- Editorial grouping only. Deliberately not a foreign key to any occupation table.
  job_area TEXT NOT NULL CHECK (length(btrim(job_area)) > 0),
  PRIMARY KEY (article_id, job_area)
);

COMMENT ON TABLE news_articles IS
  'JobsVsAI-written news briefs. Jobs Impact is a news-significance indicator and has no '
  'relationship to occupation AI Exposure or Replacement Risk.';
COMMENT ON COLUMN news_articles.impact_score IS
  'news-impact-v1 weighted score, 0-100. Internal for V1: public pages show only the level.';
COMMENT ON COLUMN news_articles.automated_impact_level IS
  'The level the pipeline computed, preserved unchanged when an editor overrides impact_level.';
COMMENT ON TABLE news_ingest_items IS
  'Third-party source material. Excerpts support relevance filtering and admin review; they '
  'are never rendered on a public page.';
COMMENT ON TABLE news_article_job_areas IS
  'Free-text editorial job groupings. Never SOC codes, never canonical occupation identities.';

COMMIT;
