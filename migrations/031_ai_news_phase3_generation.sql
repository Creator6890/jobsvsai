-- 031 — AI News Phase 3: semantic relevance and generation provenance.
--
-- News-only. No reference to any occupation or scoring table; the separation asserted by
-- 029 and re-asserted by 030 holds unchanged.
--
-- WHY THIS MIGRATION IS NEEDED
-- ----------------------------
-- Phase 2 stores a *deterministic* relevance verdict. Phase 3 adds a second, semantic one
-- from a language model, and the two are different claims that must not share a column: the
-- deterministic score says "this matched enough vocabulary", the semantic verdict says
-- "this is genuinely AI news, and here is why". Overloading `relevance_score` or `status`
-- with the model's opinion would make it impossible to answer, later, which stage rejected
-- a candidate and on what basis.
--
-- Rejection provenance matters as much as acceptance. An item the model declines is the
-- single most useful record for calibrating the prompt, so the verdict, its confidence and
-- its stated reason are retained on the item rather than discarded with it.
--
-- Generation attempt state lives here too so a failed call leaves a retryable candidate
-- instead of a silently lost one.

BEGIN;

ALTER TABLE news_ingest_items
  -- The model's semantic verdict. NULL means "not yet assessed", which is distinct from
  -- false, and both are distinct from a deterministic `ignored`.
  ADD COLUMN is_ai_news BOOLEAN,
  ADD COLUMN ai_relevance_confidence NUMERIC(3,2)
    CHECK (ai_relevance_confidence BETWEEN 0 AND 1),
  ADD COLUMN ai_relevance_reason TEXT,
  ADD COLUMN semantic_policy_version TEXT,

  -- Generation provenance, per item. The article carries its own copy (029); this records
  -- the attempt even when no article resulted.
  ADD COLUMN generation_provider TEXT,
  ADD COLUMN generation_model TEXT,
  ADD COLUMN generation_prompt_version TEXT,
  ADD COLUMN generation_attempted_at TIMESTAMPTZ,
  ADD COLUMN generation_attempts INTEGER NOT NULL DEFAULT 0
    CHECK (generation_attempts >= 0),
  -- A concise, safe failure reason. Never a stack trace, never a provider payload, and
  -- never anything derived from the API key.
  ADD COLUMN generation_error TEXT,
  -- Token accounting, when the provider reports it. Nullable because absence of usage
  -- metadata must not fail a generation.
  ADD COLUMN generation_input_tokens INTEGER CHECK (generation_input_tokens >= 0),
  ADD COLUMN generation_output_tokens INTEGER CHECK (generation_output_tokens >= 0),

  -- A semantic verdict is meaningless without the policy that produced it.
  ADD CONSTRAINT news_ingest_semantic_versioned
    CHECK (is_ai_news IS NULL OR semantic_policy_version IS NOT NULL),
  -- A recorded verdict must state how sure it was.
  ADD CONSTRAINT news_ingest_semantic_confidence
    CHECK (is_ai_news IS NULL OR ai_relevance_confidence IS NOT NULL);

-- Batch selection reads this: unassessed candidates, best deterministic score first.
CREATE INDEX news_ingest_items_generation_queue_idx
  ON news_ingest_items(status, relevance_score DESC, source_published_at DESC)
  WHERE status = 'candidate' AND is_ai_news IS NULL;

COMMENT ON COLUMN news_ingest_items.is_ai_news IS
  'Semantic verdict from the generation provider. NULL = not yet assessed, which is not the '
  'same as false. The deterministic prefilter''s verdict lives in relevance_score.';
COMMENT ON COLUMN news_ingest_items.generation_error IS
  'Concise, safe failure reason for admin display. Never a stack trace or provider payload.';

CREATE TABLE news_generation_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','completed','failed')),

  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  impact_policy_version TEXT NOT NULL,
  semantic_policy_version TEXT NOT NULL,

  batch_size INTEGER NOT NULL CHECK (batch_size > 0),
  daily_limit INTEGER NOT NULL CHECK (daily_limit > 0),

  candidates_selected INTEGER NOT NULL DEFAULT 0 CHECK (candidates_selected >= 0),
  calls_made INTEGER NOT NULL DEFAULT 0 CHECK (calls_made >= 0),
  accepted INTEGER NOT NULL DEFAULT 0 CHECK (accepted >= 0),
  rejected INTEGER NOT NULL DEFAULT 0 CHECK (rejected >= 0),
  failed INTEGER NOT NULL DEFAULT 0 CHECK (failed >= 0),
  skipped_existing INTEGER NOT NULL DEFAULT 0 CHECK (skipped_existing >= 0),
  articles_draft INTEGER NOT NULL DEFAULT 0 CHECK (articles_draft >= 0),
  articles_review_required INTEGER NOT NULL DEFAULT 0 CHECK (articles_review_required >= 0),

  input_tokens INTEGER CHECK (input_tokens >= 0),
  output_tokens INTEGER CHECK (output_tokens >= 0),

  errors JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(errors) = 'array'),

  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER CHECK (duration_ms >= 0),
  triggered_by TEXT NOT NULL,

  CHECK (status = 'running' OR completed_at IS NOT NULL)
);
CREATE INDEX news_generation_runs_recent_idx ON news_generation_runs(started_at DESC);

COMMENT ON TABLE news_generation_runs IS
  'One generation batch. Counters and token totals only - no prompt or response body is '
  'stored here.';

COMMIT;
