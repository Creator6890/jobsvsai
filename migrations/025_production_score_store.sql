-- 025 — Option B production score store.
--
-- Adds a versioned, immutable production score namespace fed by promoting persisted
-- Phase 5 candidate calculations. Nothing is promoted by this migration: every table
-- below is created empty and no occupation becomes public.
--
-- Design commitments encoded here:
--   * snapshots are append-only; there is no mutable "current score" column anywhere
--   * currency is DERIVED from promotion-run status, so rollback rewrites no score row
--   * score existence, publishability and publication are three separate states
--   * provisional-proxy provenance is stored as queryable columns, not buried in JSON
--   * task derivations key on O*NET task identity, never the legacy `tasks` table
--
-- The legacy chain (occupation_scores, score_derivations, score_history, task_ai_scores)
-- is deliberately left untouched and continues to serve /career-finder.

BEGIN;

-- ---------------------------------------------------------------------------
-- Promotion runs — the unit of promotion and of rollback.
-- This is the only mutable table in the store, and only its status/rollback
-- columns ever change.
-- ---------------------------------------------------------------------------
CREATE TABLE production_promotion_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('phase5_candidate','architecture_test_fixture')),
  source_namespace_id BIGINT REFERENCES phase5_candidate_namespaces(id),
  source_calculation_run_id BIGINT REFERENCES phase5_calculation_runs(id),
  scoring_model_version_id BIGINT NOT NULL REFERENCES scoring_model_versions(id),
  promotion_policy_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('in_progress','completed','rolled_back','failed')),
  occupation_count INTEGER NOT NULL DEFAULT 0 CHECK (occupation_count >= 0),
  is_test_fixture BOOLEAN NOT NULL DEFAULT false,
  input_version_bundle JSONB NOT NULL,
  selection_policy JSONB NOT NULL,
  reconciliation JSONB NOT NULL DEFAULT '{}'::jsonb,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  rolled_back_at TIMESTAMPTZ,
  rolled_back_by TEXT,
  rolled_back_reason TEXT,
  CHECK (jsonb_typeof(input_version_bundle)='object'),
  CHECK (jsonb_typeof(selection_policy)='object'),
  CHECK (status <> 'rolled_back' OR (rolled_back_at IS NOT NULL AND rolled_back_reason IS NOT NULL)),
  CHECK (status <> 'completed' OR completed_at IS NOT NULL),
  -- A real promotion must name the candidate run it came from. Only an explicitly
  -- flagged architecture fixture may omit it.
  CHECK (source_kind <> 'phase5_candidate'
         OR (source_namespace_id IS NOT NULL AND source_calculation_run_id IS NOT NULL)),
  CHECK ((source_kind='architecture_test_fixture') = is_test_fixture)
);
CREATE INDEX production_promotion_runs_status_idx
  ON production_promotion_runs(status, created_at DESC);

COMMENT ON TABLE production_promotion_runs IS
  'One promotion of approved candidate scores into the production namespace. Rollback is '
  'status=rolled_back; snapshots are never deleted and never recalculated.';

-- ---------------------------------------------------------------------------
-- Immutable occupation score snapshots.
-- ---------------------------------------------------------------------------
CREATE TABLE production_occupation_score_snapshots (
  id BIGSERIAL PRIMARY KEY,
  promotion_run_id BIGINT NOT NULL REFERENCES production_promotion_runs(id),
  identity_id BIGINT NOT NULL REFERENCES canonical_occupation_identities(id),
  -- Nullable on purpose: scores may be promoted and reviewed before the editorial
  -- `occupations` row (slug, category, summary, verdict) exists. Publication needs both.
  occupation_id BIGINT REFERENCES occupations(id),
  source_candidate_score_id BIGINT REFERENCES phase5_occupation_scores(id),
  scoring_model_version_id BIGINT NOT NULL REFERENCES scoring_model_versions(id),

  ai_exposure NUMERIC(7,4) NOT NULL CHECK (ai_exposure BETWEEN 0 AND 100),
  replacement_risk NUMERIC(7,4) NOT NULL CHECK (replacement_risk BETWEEN 0 AND 100),
  -- Retained for future use. Never published until separately validated; see
  -- augmentation_publishable below, which is CHECK-pinned false at this schema version.
  augmentation_potential NUMERIC(7,4) CHECK (augmentation_potential BETWEEN 0 AND 100),
  augmentation_publishable BOOLEAN NOT NULL DEFAULT false CHECK (augmentation_publishable = false),
  confidence NUMERIC(7,4) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  weighted_task_coverage NUMERIC(7,4) NOT NULL CHECK (weighted_task_coverage BETWEEN 0 AND 100),

  source_task_count INTEGER NOT NULL CHECK (source_task_count >= 0),
  eligible_task_count INTEGER NOT NULL CHECK (eligible_task_count >= 0),
  excluded_task_count INTEGER NOT NULL CHECK (excluded_task_count >= 0),
  weighting_eligible_task_count INTEGER NOT NULL CHECK (weighting_eligible_task_count >= 0),

  coverage_gate_status TEXT NOT NULL
    CHECK (coverage_gate_status IN ('passed','below_threshold','no_usable_evidence')),
  confidence_gate_status TEXT NOT NULL
    CHECK (confidence_gate_status IN ('passed','below_threshold')),
  scoring_eligibility TEXT NOT NULL CHECK (scoring_eligibility IN ('production_ready','blocked')),
  -- "may be published", NOT "is published". Activation lives in occupation_publications.
  publishable BOOLEAN NOT NULL DEFAULT false,

  frontier_index_version TEXT NOT NULL,
  frontier_track TEXT NOT NULL,
  structural_proxy_model_version TEXT NOT NULL,
  base_proxy_model_version TEXT NOT NULL,
  occupation_formula_version TEXT NOT NULL,
  task_formula_versions JSONB NOT NULL,
  capability_taxonomy_version TEXT NOT NULL,
  mapping_rubric_version TEXT NOT NULL,
  evidence_policy_version TEXT NOT NULL,

  -- When the engine calculated the score (carried from Phase 5) vs when it was promoted.
  -- Conflating these would misdate the "last updated" line on public pages.
  calculated_at TIMESTAMPTZ NOT NULL,
  promoted_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  exact_inputs JSONB NOT NULL,
  provisional_sensitivity JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  blocking_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (promotion_run_id, identity_id),
  CHECK (jsonb_typeof(task_formula_versions)='object'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(provisional_sensitivity)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(blocking_reasons)='array'),
  CHECK (jsonb_typeof(reconciliation)='object'),
  -- Publishability restates the validated gates rather than trusting the promoter.
  CHECK (publishable = false OR (scoring_eligibility='production_ready'
         AND coverage_gate_status='passed' AND confidence_gate_status='passed'
         AND weighted_task_coverage >= 70 AND confidence >= 70)),
  CHECK (scoring_eligibility <> 'production_ready'
         OR (coverage_gate_status='passed' AND confidence_gate_status='passed'))
);
CREATE INDEX production_snapshots_identity_idx
  ON production_occupation_score_snapshots(identity_id);
CREATE INDEX production_snapshots_occupation_idx
  ON production_occupation_score_snapshots(occupation_id);
CREATE INDEX production_snapshots_run_idx
  ON production_occupation_score_snapshots(promotion_run_id);
CREATE INDEX production_snapshots_exposure_idx
  ON production_occupation_score_snapshots(ai_exposure DESC);
CREATE INDEX production_snapshots_replacement_idx
  ON production_occupation_score_snapshots(replacement_risk DESC);

COMMENT ON COLUMN production_occupation_score_snapshots.publishable IS
  'Editorially permissible to publish. Being publishable does not make an occupation '
  'public; occupation_publications.activation_status does.';
COMMENT ON COLUMN production_occupation_score_snapshots.augmentation_potential IS
  'Weighted occupation-level augmentation, retained for future use. Not a launch metric: '
  'it has never been through the Phase 4C/4D validation frame.';

-- ---------------------------------------------------------------------------
-- Normalized replacement-risk factor derivation. Six rows per snapshot.
-- Provisional-proxy provenance is columnar so it can be queried, not parsed.
-- ---------------------------------------------------------------------------
CREATE TABLE production_score_factor_contributions (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES production_occupation_score_snapshots(id),
  factor_key TEXT NOT NULL,
  factor_label TEXT NOT NULL,
  value NUMERIC(9,4) NOT NULL,
  source_proxy_value NUMERIC(9,4),
  transformation TEXT NOT NULL,
  weight NUMERIC(9,6) NOT NULL CHECK (weight >= 0 AND weight <= 1),
  weighted_contribution NUMERIC(9,4) NOT NULL,
  is_provisional_proxy BOOLEAN NOT NULL DEFAULT false,
  proxy_model_version TEXT,
  placeholder BOOLEAN NOT NULL DEFAULT false,
  display_order SMALLINT NOT NULL,
  UNIQUE (snapshot_id, factor_key),
  CHECK (is_provisional_proxy = false OR proxy_model_version IS NOT NULL)
);
CREATE INDEX production_factor_snapshot_idx
  ON production_score_factor_contributions(snapshot_id, display_order);
CREATE INDEX production_factor_provisional_idx
  ON production_score_factor_contributions(is_provisional_proxy) WHERE is_provisional_proxy;

-- ---------------------------------------------------------------------------
-- Normalized task derivation, keyed to O*NET task identity.
-- Deliberately does not reference the legacy `tasks` table.
-- ---------------------------------------------------------------------------
CREATE TABLE production_score_task_contributions (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES production_occupation_score_snapshots(id),
  onet_task_id BIGINT NOT NULL,
  onet_soc_code TEXT NOT NULL,
  task_statement TEXT NOT NULL,
  task_statement_hash TEXT NOT NULL,
  source_mapping_set_id BIGINT,
  ai_capability_fit NUMERIC(7,4) NOT NULL CHECK (ai_capability_fit BETWEEN 0 AND 100),
  automation_feasibility NUMERIC(7,4) NOT NULL CHECK (automation_feasibility BETWEEN 0 AND 100),
  augmentation_potential NUMERIC(7,4) NOT NULL CHECK (augmentation_potential BETWEEN 0 AND 100),
  task_ai_exposure NUMERIC(7,4) NOT NULL CHECK (task_ai_exposure BETWEEN 0 AND 100),
  task_confidence NUMERIC(7,4) CHECK (task_confidence BETWEEN 0 AND 100),
  source_importance NUMERIC(7,4),
  source_frequency NUMERIC(7,4),
  source_weight NUMERIC(14,4),
  normalized_covered_weight NUMERIC(9,6) NOT NULL,
  exposure_contribution NUMERIC(9,4) NOT NULL,
  weighting_eligible BOOLEAN NOT NULL,
  UNIQUE (snapshot_id, onet_task_id)
);
CREATE INDEX production_task_snapshot_idx
  ON production_score_task_contributions(snapshot_id, exposure_contribution DESC);
CREATE INDEX production_task_onet_idx
  ON production_score_task_contributions(onet_task_id);

COMMENT ON COLUMN production_score_task_contributions.onet_task_id IS
  'O*NET task identity. Intentionally not a FK to the legacy `tasks` table, which holds '
  'editorial demo tasks with unrelated ids.';

-- ---------------------------------------------------------------------------
-- Immutability. Snapshots and their derivations are append-only; corrections are a
-- new promotion run. Because nothing is ever deleted, no FK cascade is declared.
-- ---------------------------------------------------------------------------
CREATE TRIGGER production_snapshots_append_only
  BEFORE UPDATE OR DELETE ON production_occupation_score_snapshots
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER production_factor_contributions_append_only
  BEFORE UPDATE OR DELETE ON production_score_factor_contributions
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER production_task_contributions_append_only
  BEFORE UPDATE OR DELETE ON production_score_task_contributions
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

-- A promotion run may only change status and rollback bookkeeping. Everything that
-- defines what was promoted is frozen once written.
CREATE OR REPLACE FUNCTION prevent_promotion_run_redefinition()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'production_promotion_runs is append-only; roll a run back instead of deleting it';
  END IF;
  IF NEW.run_key IS DISTINCT FROM OLD.run_key
     OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
     OR NEW.source_namespace_id IS DISTINCT FROM OLD.source_namespace_id
     OR NEW.source_calculation_run_id IS DISTINCT FROM OLD.source_calculation_run_id
     OR NEW.scoring_model_version_id IS DISTINCT FROM OLD.scoring_model_version_id
     OR NEW.promotion_policy_version IS DISTINCT FROM OLD.promotion_policy_version
     OR NEW.input_version_bundle IS DISTINCT FROM OLD.input_version_bundle
     OR NEW.selection_policy IS DISTINCT FROM OLD.selection_policy
     OR NEW.input_hash IS DISTINCT FROM OLD.input_hash
     OR NEW.is_test_fixture IS DISTINCT FROM OLD.is_test_fixture
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'production_promotion_runs definition columns are immutable; only status and rollback bookkeeping may change';
  END IF;
  IF OLD.status IN ('completed','rolled_back','failed') AND NEW.status = 'in_progress' THEN
    RAISE EXCEPTION 'a settled promotion run cannot return to in_progress';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER production_promotion_runs_definition_immutable
  BEFORE UPDATE OR DELETE ON production_promotion_runs
  FOR EACH ROW EXECUTE FUNCTION prevent_promotion_run_redefinition();

-- ---------------------------------------------------------------------------
-- The single deterministic currency path.
--
-- Every public consumer reads this view. No caller writes its own "latest score"
-- clause, which is what allowed the legacy readers to disagree: three of them ordered
-- by calculated_at with no tiebreak while others added `id DESC`, and rows inserted in
-- one transaction share now().
-- ---------------------------------------------------------------------------
CREATE VIEW current_production_occupation_scores AS
SELECT DISTINCT ON (snapshot.identity_id)
       snapshot.*,
       run.run_key,
       run.status AS promotion_run_status
FROM production_occupation_score_snapshots snapshot
JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
WHERE run.status = 'completed'
ORDER BY snapshot.identity_id, run.created_at DESC, run.id DESC, snapshot.id DESC;

COMMENT ON VIEW current_production_occupation_scores IS
  'The one source of production score currency. Ordering is fully deterministic; rolling '
  'a run back changes only production_promotion_runs.status and this view falls back to '
  'the previous completed run.';

-- ---------------------------------------------------------------------------
-- Publication now records which snapshot editorial approved. Nullable and
-- non-breaking; publication state itself is unchanged.
-- ---------------------------------------------------------------------------
ALTER TABLE occupation_publications
  ADD COLUMN IF NOT EXISTS approved_score_snapshot_id BIGINT
    REFERENCES production_occupation_score_snapshots(id);

CREATE INDEX occupation_publications_approved_snapshot_idx
  ON occupation_publications(approved_score_snapshot_id)
  WHERE approved_score_snapshot_id IS NOT NULL;

COMMENT ON COLUMN occupation_publications.approved_score_snapshot_id IS
  'The score snapshot editorial approved for this page. Lets a rollback identify pages '
  'still serving a withdrawn snapshot.';

-- Consistency surface: pages whose approved snapshot belongs to a run that is no longer
-- completed. A rollback procedure must demote everything this view reports.
CREATE VIEW publication_snapshot_consistency AS
SELECT publication.identity_id,
       publication.locale,
       publication.source_geography,
       publication.activation_status,
       publication.approved_score_snapshot_id,
       run.id AS promotion_run_id,
       run.run_key,
       run.status AS promotion_run_status,
       CASE
         WHEN publication.approved_score_snapshot_id IS NULL THEN 'no_approved_snapshot'
         WHEN run.status <> 'completed' THEN 'approved_snapshot_withdrawn'
         WHEN current_score.id IS NULL THEN 'approved_snapshot_superseded'
         WHEN current_score.id <> publication.approved_score_snapshot_id THEN 'approved_snapshot_superseded'
         ELSE 'consistent'
       END AS consistency_state
FROM occupation_publications publication
LEFT JOIN production_occupation_score_snapshots snapshot
       ON snapshot.id = publication.approved_score_snapshot_id
LEFT JOIN production_promotion_runs run ON run.id = snapshot.promotion_run_id
LEFT JOIN current_production_occupation_scores current_score
       ON current_score.identity_id = publication.identity_id;

COMMENT ON VIEW publication_snapshot_consistency IS
  'Reports pages whose approved snapshot was rolled back or superseded. Any row that is '
  'public and not `consistent` needs editorial action.';

COMMIT;
