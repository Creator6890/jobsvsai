-- 027 — Persistence for Phase 6 launch-quality triage.
--
-- Triage reads persisted Phase 5 candidate scores and classifies them. It never rescores and
-- never writes to any phase5_* table (all of which are append-only from migration 024).
--
-- The cohort recorded here is advisory input to promotion, not an approval. Promotion still
-- requires an explicit approved identity list.

BEGIN;

CREATE TABLE phase6_launch_triage_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  policy_version TEXT NOT NULL,
  source_calculation_run_id BIGINT NOT NULL REFERENCES phase5_calculation_runs(id),
  gates JSONB NOT NULL,
  candidates_assessed INTEGER NOT NULL CHECK (candidates_assessed >= 0),
  launch_cohort_size INTEGER NOT NULL CHECK (launch_cohort_size >= 0),
  excluded_count INTEGER NOT NULL CHECK (excluded_count >= 0),
  severity_totals JSONB NOT NULL,
  finding_totals JSONB NOT NULL,
  exclusion_reasons JSONB NOT NULL,
  -- The cohort is derived, never targeted. Recorded so the absence is auditable rather than
  -- merely asserted in a report.
  cohort_selection TEXT NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (candidates_assessed = launch_cohort_size + excluded_count),
  CHECK (jsonb_typeof(gates)='object'),
  CHECK (jsonb_typeof(severity_totals)='object'),
  CHECK (jsonb_typeof(exclusion_reasons)='object')
);

CREATE TABLE phase6_launch_triage_results (
  id BIGSERIAL PRIMARY KEY,
  triage_run_id BIGINT NOT NULL REFERENCES phase6_launch_triage_runs(id),
  candidate_occupation_id BIGINT NOT NULL REFERENCES phase5_candidate_occupations(id),
  occupation_code TEXT NOT NULL,
  title TEXT NOT NULL,
  ai_exposure NUMERIC(7,4),
  replacement_risk NUMERIC(7,4),
  confidence NUMERIC(7,4) NOT NULL,
  weighted_task_coverage NUMERIC(7,4) NOT NULL,
  launch_eligible BOOLEAN NOT NULL,
  highest_severity TEXT CHECK (highest_severity IN ('critical','high','medium','low')),
  blocking_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
  severity_counts JSONB NOT NULL,
  findings JSONB NOT NULL,
  UNIQUE (triage_run_id, candidate_occupation_id),
  CHECK (jsonb_typeof(blocking_codes)='array'),
  CHECK (jsonb_typeof(findings)='array'),
  -- Eligibility and blocking findings must agree; a row cannot claim both.
  CHECK (launch_eligible = (jsonb_array_length(blocking_codes) = 0))
);
CREATE INDEX phase6_triage_results_run_idx
  ON phase6_launch_triage_results(triage_run_id, launch_eligible);
CREATE INDEX phase6_triage_results_severity_idx
  ON phase6_launch_triage_results(triage_run_id, highest_severity);

CREATE TRIGGER phase6_triage_runs_append_only
  BEFORE UPDATE OR DELETE ON phase6_launch_triage_runs
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase6_triage_results_append_only
  BEFORE UPDATE OR DELETE ON phase6_launch_triage_results
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMENT ON TABLE phase6_launch_triage_runs IS
  'One deterministic launch-quality triage over a Phase 5 calculation run. Re-running the '
  'same policy over the same candidates produces the same findings.';
COMMENT ON COLUMN phase6_launch_triage_runs.cohort_selection IS
  'How the cohort was derived. Phase 5 truncated to a 400 target; this policy takes every '
  'candidate that clears the gates and records how many that is.';

COMMIT;
