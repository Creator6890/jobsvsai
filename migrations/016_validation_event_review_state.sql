-- Preserve the originating AI review state on failed validation events.
-- Clean installs already receive this value from migration 015; this migration
-- upgrades databases where 015 was applied before the audit-event state was added.
ALTER TABLE ai_task_mapping_validation_events
  DROP CONSTRAINT IF EXISTS ai_task_mapping_validation_events_review_state_check;

ALTER TABLE ai_task_mapping_validation_events
  ADD CONSTRAINT ai_task_mapping_validation_events_review_state_check
  CHECK (review_state IN (
    'unreviewed',
    'ai_self_checked',
    'ai_validated',
    'pending_human_review',
    'human_reviewed',
    'rejected'
  ));
