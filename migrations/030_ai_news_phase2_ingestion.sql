-- 030 — AI News Phase 2: RSS/Atom ingestion, dedupe and relevance prefilter.
--
-- News-only. Touches nothing outside the `news_*` namespace, and adds no reference to any
-- occupation or scoring table — the separation asserted by migration 029 and by
-- `test_job_areas_are_editorial_text_not_occupation_links` holds unchanged.
--
-- WHY A MIGRATION RATHER THAN REUSING 029's COLUMNS
-- -------------------------------------------------
-- Phase 2 produces three facts per ingest item that 029 has nowhere to put: how relevant the
-- prefilter judged it, which policy version made that judgement, and which earlier item it
-- duplicates. Overloading `status` or `original_excerpt` to carry them would destroy exactly
-- the auditability the news system exists to have. The alternative — deriving relevance on
-- read — would mean a stored candidate could silently change category when the policy
-- changes, which is the failure mode `news-impact-v1` was designed to avoid for impact.
--
-- FEED FORMAT IS NOT SOURCE TYPE
-- ------------------------------
-- `news_sources.source_type` already means primary/secondary provenance — whether the
-- organisation did the thing or reported on it — and trust logic reads it. Feed format is an
-- unrelated transport fact, so it gets its own column rather than widening that CHECK.

BEGIN;

-- ---------------------------------------------------------------- sources: feed transport
ALTER TABLE news_sources
  ADD COLUMN feed_format TEXT CHECK (feed_format IN ('rss','atom')),
  -- Conservative retry state. A source that fails repeatedly is backed off rather than
  -- retried at full cadence; hammering a free feed is how a free feed stops being available.
  ADD COLUMN last_fetched_at TIMESTAMPTZ,
  ADD COLUMN last_success_at TIMESTAMPTZ,
  ADD COLUMN last_error TEXT,
  ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0
    CHECK (consecutive_failures >= 0),
  -- A source with a feed_url must say what format it serves.
  ADD CONSTRAINT news_sources_feed_format_required
    CHECK (feed_url IS NULL OR feed_format IS NOT NULL);

COMMENT ON COLUMN news_sources.feed_format IS
  'Transport format of feed_url. Unrelated to source_type, which is primary/secondary provenance.';

-- -------------------------------------------------------- ingest items: relevance + dedupe
ALTER TABLE news_ingest_items
  ADD COLUMN relevance_score SMALLINT CHECK (relevance_score BETWEEN 0 AND 100),
  ADD COLUMN relevance_policy_version TEXT,
  -- The signals that produced the score. Stored so a triage decision can be explained
  -- months later without re-running the policy against text that may have changed.
  ADD COLUMN relevance_signals JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(relevance_signals) = 'object'),
  -- Feed-provided categories, kept for future relevance tuning. Not rendered anywhere.
  ADD COLUMN feed_categories JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(feed_categories) = 'array'),
  -- Near-duplicate provenance. The row is kept — cross-source coverage of one event is
  -- evidence about the event — and points at the item it duplicates. Deliberately NOT a
  -- story-cluster table: clustering is a Phase 3+ concern and a premature one here.
  ADD COLUMN duplicate_of_ingest_item_id BIGINT REFERENCES news_ingest_items(id),
  -- The normalised token string the near-duplicate check compares. Persisted so the same
  -- comparison is reproducible and so a future policy can be back-tested over history.
  ADD COLUMN title_fingerprint TEXT,
  ADD COLUMN near_duplicate_similarity NUMERIC(4,3)
    CHECK (near_duplicate_similarity BETWEEN 0 AND 1),
  -- A scored item must record which policy scored it, or the number means nothing.
  ADD CONSTRAINT news_ingest_relevance_versioned
    CHECK (relevance_score IS NULL OR relevance_policy_version IS NOT NULL),
  -- An item cannot duplicate itself, and a duplicate link implies duplicate status.
  ADD CONSTRAINT news_ingest_no_self_duplicate
    CHECK (duplicate_of_ingest_item_id IS NULL OR duplicate_of_ingest_item_id <> id),
  ADD CONSTRAINT news_ingest_duplicate_status
    CHECK (duplicate_of_ingest_item_id IS NULL OR status = 'duplicate');

CREATE INDEX news_ingest_items_candidate_idx
  ON news_ingest_items(status, relevance_score DESC, source_published_at DESC);
-- The near-duplicate window scans recent items only; this is the index it uses.
CREATE INDEX news_ingest_items_recent_idx
  ON news_ingest_items(fetched_at DESC) WHERE title_fingerprint IS NOT NULL;

COMMENT ON COLUMN news_ingest_items.relevance_score IS
  'news-relevance-v1 prefilter score 0-100. Internal only; never exposed publicly.';
COMMENT ON COLUMN news_ingest_items.duplicate_of_ingest_item_id IS
  'Near-duplicate of an earlier item. The row is retained for provenance rather than dropped.';

-- ------------------------------------------------------------------------ run observability
CREATE TABLE news_ingestion_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','completed','failed')),

  relevance_policy_version TEXT NOT NULL,
  lookback_hours INTEGER NOT NULL CHECK (lookback_hours > 0),
  max_entries_per_feed INTEGER NOT NULL CHECK (max_entries_per_feed > 0),

  sources_attempted INTEGER NOT NULL DEFAULT 0 CHECK (sources_attempted >= 0),
  sources_succeeded INTEGER NOT NULL DEFAULT 0 CHECK (sources_succeeded >= 0),
  sources_failed INTEGER NOT NULL DEFAULT 0 CHECK (sources_failed >= 0),

  items_fetched INTEGER NOT NULL DEFAULT 0 CHECK (items_fetched >= 0),
  items_new INTEGER NOT NULL DEFAULT 0 CHECK (items_new >= 0),
  items_exact_duplicate INTEGER NOT NULL DEFAULT 0 CHECK (items_exact_duplicate >= 0),
  items_near_duplicate INTEGER NOT NULL DEFAULT 0 CHECK (items_near_duplicate >= 0),
  items_ignored INTEGER NOT NULL DEFAULT 0 CHECK (items_ignored >= 0),
  items_candidate INTEGER NOT NULL DEFAULT 0 CHECK (items_candidate >= 0),
  items_outside_window INTEGER NOT NULL DEFAULT 0 CHECK (items_outside_window >= 0),

  -- Per-source failures, so one broken feed is a recorded fact rather than a lost run.
  errors JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(errors) = 'array'),

  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER CHECK (duration_ms >= 0),
  triggered_by TEXT NOT NULL,

  CHECK (status = 'running' OR completed_at IS NOT NULL)
);
CREATE INDEX news_ingestion_runs_recent_idx ON news_ingestion_runs(started_at DESC);

COMMENT ON TABLE news_ingestion_runs IS
  'One RSS/Atom fetch run. Counters only - no feed content is stored here.';

-- --------------------------------------------------------------------------- seed sources
-- Every feed_url below was fetched and confirmed to return a parseable RSS document before
-- being written here. Sources are data, not code: adding one later is an INSERT.
--
-- Deliberately NOT seeded, because no reliable public feed was found when this migration was
-- written (all probed paths returned 404): Anthropic, Meta AI. They are documented as future
-- candidates in reports/AI_NEWS_PHASE2_INGESTION.md rather than scraped.
INSERT INTO news_sources (name, feed_url, site_url, source_type, trust_tier, feed_format, enabled)
VALUES
  ('OpenAI',                 'https://openai.com/news/rss.xml',                    'https://openai.com',            'primary',   1, 'rss', true),
  ('Google DeepMind',        'https://deepmind.google/blog/rss.xml',               'https://deepmind.google',       'primary',   1, 'rss', true),
  ('Google AI',              'https://blog.google/technology/ai/rss/',             'https://blog.google',           'primary',   1, 'rss', true),
  ('Microsoft Research',     'https://www.microsoft.com/en-us/research/feed/',     'https://www.microsoft.com/research', 'primary', 1, 'rss', true),
  ('NVIDIA',                 'https://blogs.nvidia.com/feed/',                     'https://blogs.nvidia.com',      'primary',   1, 'rss', true),
  ('Hugging Face',           'https://huggingface.co/blog/feed.xml',               'https://huggingface.co',        'primary',   1, 'rss', true),
  ('Mistral AI',             'https://mistral.ai/rss.xml',                         'https://mistral.ai',            'primary',   1, 'rss', true),
  ('MIT Technology Review',  'https://www.technologyreview.com/topic/artificial-intelligence/feed/', 'https://www.technologyreview.com', 'secondary', 2, 'rss', true),
  ('Ars Technica',           'https://arstechnica.com/ai/feed/',                   'https://arstechnica.com',       'secondary', 2, 'rss', true)
ON CONFLICT (name) DO NOTHING;

COMMIT;
