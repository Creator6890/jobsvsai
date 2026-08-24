-- 033 — AI News Phase 4: generation latency and failure category.
--
-- News-only. No reference to any occupation or scoring table.
--
-- Deliberately two columns, not a table. Everything else Step 5 needs to answer "does the
-- generated content justify the cost and editorial effort" is already recorded:
--
--   cost per article    -> generation_input_tokens + generation_output_tokens
--   acceptance rate     -> is_ai_news over generation_attempts
--   rejection rate      -> is_ai_news = false, with ai_relevance_reason
--   regeneration rate   -> news_articles.regeneration_count (032)
--   quality proxies     -> impact_score, impact_confidence, ai_relevance_confidence
--   model used          -> generation_model, generation_prompt_version
--
-- What could not be derived from any of those is how long a call took, and what kind of
-- failure a failed one was. `generation_error` holds a message; grouping failures by
-- string-matching a message is the sort of thing that works until the message changes.

BEGIN;

ALTER TABLE news_ingest_items
  ADD COLUMN generation_latency_ms INTEGER CHECK (generation_latency_ms >= 0),
  -- A small, stable vocabulary. `unknown` is deliberate: a category that cannot represent
  -- "we do not know" tempts the caller to guess, and a guessed category is worse than none.
  ADD COLUMN generation_error_kind TEXT CHECK (generation_error_kind IN (
    'rate_limited','server_error','timeout','invalid_response',
    'credentials','provider_error','unknown'
  )),
  -- A category without a message is unactionable; a message without a category is
  -- ungroupable. Neither exists without the other.
  ADD CONSTRAINT news_ingest_error_kind_paired
    CHECK ((generation_error_kind IS NULL) = (generation_error IS NULL));

COMMENT ON COLUMN news_ingest_items.generation_latency_ms IS
  'Wall-clock time of the provider call, including its internal retries.';
COMMENT ON COLUMN news_ingest_items.generation_error_kind IS
  'Stable failure category, so Step 5 can group model failures without parsing messages.';

COMMIT;
