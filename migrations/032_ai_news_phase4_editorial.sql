-- 032 — AI News Phase 4: archive status and regeneration provenance.
--
-- News-only. No reference to any occupation or scoring table; the isolation asserted by 029
-- and re-asserted by 030 and 031 is unchanged.
--
-- WHY 'archived' IS NOT 'rejected'
-- --------------------------------
-- They mean different things and collapsing them loses the difference. `rejected` is a
-- judgement about the content — this should not have been an article. `archived` is a
-- judgement about its currency — it was fine, and is now set aside or retired.
--
-- The distinction has a practical consequence: rejecting clears `published_at`, because a
-- rejected item is being treated as something that should never have gone out. Archiving
-- PRESERVES it, because an article that was published genuinely was published, and erasing
-- that would falsify the record of what the site once served.
--
-- Neither status is public: the reader predicate admits only `published`, so an archived
-- article leaves the public site the moment it is archived without any separate unpublish.

BEGIN;

ALTER TABLE news_articles
  DROP CONSTRAINT news_articles_status_check,
  ADD CONSTRAINT news_articles_status_check
    CHECK (status IN ('draft','review_required','published','rejected','archived'));

ALTER TABLE news_articles
  ADD COLUMN archived_at TIMESTAMPTZ,
  ADD COLUMN archived_by TEXT,
  ADD COLUMN archive_reason TEXT,

  -- Regeneration provenance. The generation_* columns are overwritten each time, so without
  -- a counter there would be no way to tell a first draft from a fifth attempt.
  ADD COLUMN regenerated_at TIMESTAMPTZ,
  ADD COLUMN regeneration_count INTEGER NOT NULL DEFAULT 0
    CHECK (regeneration_count >= 0),

  -- An archive is a complete record or it is not an archive. Losing the actor would make the
  -- action unauditable, which is the same standard the impact override is held to.
  ADD CONSTRAINT news_articles_archive_complete
    CHECK (archived_at IS NULL OR archived_by IS NOT NULL),
  -- Status and the audit column cannot disagree.
  ADD CONSTRAINT news_articles_archive_status
    CHECK ((status = 'archived') = (archived_at IS NOT NULL)),
  ADD CONSTRAINT news_articles_regeneration_recorded
    CHECK ((regeneration_count = 0) = (regenerated_at IS NULL));

-- The editorial queue filters by status; archived articles should not scan the whole table.
CREATE INDEX news_articles_archived_idx
  ON news_articles(archived_at DESC) WHERE status = 'archived';

COMMENT ON COLUMN news_articles.archived_at IS
  'Set when an article is retired. Distinct from rejected: archiving preserves published_at, '
  'because an article that was published genuinely was.';
COMMENT ON COLUMN news_articles.regeneration_count IS
  'How many times the brief has been regenerated. The generation_* columns hold only the '
  'most recent attempt.';

COMMIT;
