-- 035 — Preliminary occupation estimates: a second, explicitly separate score class.
--
-- Additive only. No verified score is read, written, moved or reinterpreted. Promotion run
-- 30, the 507 production snapshots, `occupation_publications.activation_status` and the
-- JVS 1.0.3 publication semantics are all untouched, and nothing here can alter them.
--
-- ## Why a separate store rather than columns on the production snapshot
--
-- The production score store already carries trigger-enforced guarantees: append-only,
-- engine-family-restricted, one live row per identity through
-- `current_production_occupation_scores`. An estimate is a different kind of claim — it is
-- not the output of the validated engine over complete evidence, and for the proxy tiers it
-- is not the output of the engine at all. Putting it in the same table would mean every
-- reader of a verified score now has to remember to filter, and the first reader that forgets
-- publishes an estimate as verified. That failure is silent and it is unrecoverable in the
-- sense that matters: a user has already seen a number we did not stand behind.
--
-- So estimates live in their own table, and the separation is enforced structurally rather
-- than by convention:
--
--   * `score_status` is CHECK-pinned to 'estimated'. The string 'verified' cannot be stored
--     in this table at all. There is no code path, no backfill and no admin action that can
--     make a row here claim verified standing.
--   * There is no foreign key to `production_occupation_score_snapshots`, so an estimate can
--     never be mistaken for a promoted snapshot or join its way into one.
--   * Publication of an estimate is recorded here, on `is_published`, **not** on
--     `occupation_publications.activation_status`. That column keeps meaning exactly what it
--     has always meant: 507 occupations carry a verified, promoted, activated analysis. The
--     public *page* count and the verified count are now two different numbers, and the
--     schema keeps them two different columns in two different tables.
--
-- ## Why runs
--
-- Estimates are regenerated as evidence improves — an occupation acquires task mappings, a
-- relative gets promoted and changes a proxy, the estimator itself is revised. Recording the
-- run makes an estimate reproducible and lets a bad run be withdrawn wholesale rather than
-- row by row. The table is append-only for the same reason the production store is: an
-- estimate that was shown to a user is history, and history is not edited.

BEGIN;

CREATE TABLE IF NOT EXISTS occupation_score_estimate_runs (
    id                      BIGSERIAL PRIMARY KEY,
    run_key                 TEXT NOT NULL UNIQUE,
    policy_version          TEXT NOT NULL,
    -- The verified cohort the proxy tiers drew on. An estimate is only reproducible if we
    -- know which scores were available to borrow from when it was made.
    source_promotion_run_id BIGINT REFERENCES production_promotion_runs(id),
    status                  TEXT NOT NULL DEFAULT 'in_progress'
                            CHECK (status IN ('in_progress','completed','failed','withdrawn')),
    estimates_written       INTEGER NOT NULL DEFAULT 0,
    tier_totals             JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Leave-one-out error statistics measured against the verified cohort at run time.
    -- Stored with the run so a published estimate can always be traced to the calibration
    -- that justified publishing it.
    calibration             JSONB NOT NULL DEFAULT '{}'::jsonb,
    external_model_calls    INTEGER NOT NULL DEFAULT 0,
    provenance              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by              TEXT NOT NULL DEFAULT current_user,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE occupation_score_estimate_runs IS
  'One row per preliminary-estimate generation run. Append-only; withdraw by status.';
COMMENT ON COLUMN occupation_score_estimate_runs.calibration IS
  'Leave-one-out error statistics against the verified cohort, measured at run time.';

CREATE TABLE IF NOT EXISTS occupation_score_estimates (
    id                        BIGSERIAL PRIMARY KEY,
    estimate_run_id           BIGINT NOT NULL REFERENCES occupation_score_estimate_runs(id),
    identity_id               BIGINT NOT NULL REFERENCES canonical_occupation_identities(id),
    occupation_code           TEXT NOT NULL,

    -- The whole point of this table. CHECK-pinned so the value cannot be anything else.
    score_status              TEXT NOT NULL DEFAULT 'estimated'
                              CHECK (score_status = 'estimated'),

    -- Which rung of the evidence hierarchy produced this. E1/E2 are real engine output over
    -- real task evidence; E3 is a proxy over verified relatives. E4 exists in the vocabulary
    -- but is unused — see the report.
    estimate_method           TEXT NOT NULL
                              CHECK (estimate_method IN ('E1','E2','E3','E4')),
    estimate_method_detail    TEXT NOT NULL,
    estimate_confidence       TEXT NOT NULL
                              CHECK (estimate_confidence IN ('higher','moderate','low')),

    -- Weighted task coverage where task evidence exists; NULL for proxy tiers, because a
    -- proxy has no coverage of its own and reporting 0 would read as "we checked and found
    -- nothing" rather than "this measure does not apply".
    evidence_coverage         NUMERIC(6,3),
    evidence_confidence       NUMERIC(6,3),
    supporting_relative_count INTEGER,

    -- Integers throughout. These are estimates; rendering 72.43 would assert a precision the
    -- calibration does not support.
    ai_exposure_estimate      INTEGER NOT NULL CHECK (ai_exposure_estimate BETWEEN 0 AND 100),
    ai_exposure_low           INTEGER CHECK (ai_exposure_low BETWEEN 0 AND 100),
    ai_exposure_high          INTEGER CHECK (ai_exposure_high BETWEEN 0 AND 100),
    replacement_risk_estimate INTEGER NOT NULL CHECK (replacement_risk_estimate BETWEEN 0 AND 100),
    replacement_risk_low      INTEGER CHECK (replacement_risk_low BETWEEN 0 AND 100),
    replacement_risk_high     INTEGER CHECK (replacement_risk_high BETWEEN 0 AND 100),

    -- A range must be a range. Either both bounds are absent, or they bracket the estimate.
    CONSTRAINT exposure_range_brackets_estimate CHECK (
        (ai_exposure_low IS NULL AND ai_exposure_high IS NULL)
        OR (ai_exposure_low <= ai_exposure_estimate AND ai_exposure_estimate <= ai_exposure_high)),
    CONSTRAINT replacement_range_brackets_estimate CHECK (
        (replacement_risk_low IS NULL AND replacement_risk_high IS NULL)
        OR (replacement_risk_low <= replacement_risk_estimate
            AND replacement_risk_estimate <= replacement_risk_high)),

    -- Which occupations the proxy borrowed from, with their tiers and weights. An estimate a
    -- reader cannot audit is a number without a warrant.
    evidence_sources          JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Publication of the estimate layer. Deliberately NOT occupation_publications.
    is_published              BOOLEAN NOT NULL DEFAULT FALSE,

    input_hash                CHAR(64),
    provenance                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by                TEXT NOT NULL DEFAULT current_user,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (estimate_run_id, identity_id)
);

COMMENT ON TABLE occupation_score_estimates IS
  'Preliminary occupation estimates. score_status is CHECK-pinned to ''estimated''; this '
  'table structurally cannot hold a verified score.';

CREATE INDEX IF NOT EXISTS occupation_score_estimates_identity_idx
    ON occupation_score_estimates (identity_id);
CREATE INDEX IF NOT EXISTS occupation_score_estimates_published_idx
    ON occupation_score_estimates (is_published) WHERE is_published;
CREATE INDEX IF NOT EXISTS occupation_score_estimates_code_idx
    ON occupation_score_estimates (occupation_code);

-- Append-only, matching the production store's discipline. Publication is the one mutable
-- fact: an estimate may be published or withdrawn, but the numbers it asserted never change.
CREATE OR REPLACE FUNCTION occupation_score_estimates_append_only()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'occupation_score_estimates is append-only; withdraw via is_published';
    END IF;
    IF ROW(NEW.*) IS DISTINCT FROM ROW(OLD.*) THEN
        IF NEW.ai_exposure_estimate      IS DISTINCT FROM OLD.ai_exposure_estimate
        OR NEW.replacement_risk_estimate IS DISTINCT FROM OLD.replacement_risk_estimate
        OR NEW.ai_exposure_low           IS DISTINCT FROM OLD.ai_exposure_low
        OR NEW.ai_exposure_high          IS DISTINCT FROM OLD.ai_exposure_high
        OR NEW.replacement_risk_low      IS DISTINCT FROM OLD.replacement_risk_low
        OR NEW.replacement_risk_high     IS DISTINCT FROM OLD.replacement_risk_high
        OR NEW.estimate_method           IS DISTINCT FROM OLD.estimate_method
        OR NEW.identity_id               IS DISTINCT FROM OLD.identity_id
        OR NEW.estimate_run_id           IS DISTINCT FROM OLD.estimate_run_id THEN
            RAISE EXCEPTION
              'occupation_score_estimates values are immutable; write a new run instead';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS occupation_score_estimates_append_only ON occupation_score_estimates;
CREATE TRIGGER occupation_score_estimates_append_only
    BEFORE UPDATE OR DELETE ON occupation_score_estimates
    FOR EACH ROW EXECUTE FUNCTION occupation_score_estimates_append_only();

-- An identity must never hold a verified score and a published estimate at the same time.
-- If an occupation earns a verified score, its estimate is withdrawn, not left to compete.
-- Enforced rather than documented, because "we will remember to withdraw it" is exactly the
-- kind of promise that fails quietly six months later.
CREATE OR REPLACE FUNCTION occupation_estimates_never_shadow_verified()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_published AND EXISTS (
        SELECT 1 FROM current_production_occupation_scores c
        WHERE c.identity_id = NEW.identity_id
    ) THEN
        RAISE EXCEPTION
          'identity % already has a verified production score; an estimate may not be published for it',
          NEW.identity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS occupation_estimates_never_shadow_verified ON occupation_score_estimates;
CREATE TRIGGER occupation_estimates_never_shadow_verified
    BEFORE INSERT OR UPDATE ON occupation_score_estimates
    FOR EACH ROW EXECUTE FUNCTION occupation_estimates_never_shadow_verified();

-- The single reader for published estimates, mirroring how every verified read goes through
-- `current_production_occupation_scores`. Divergent bespoke "latest estimate" clauses are how
-- readers previously came to disagree about which verified row was live; the same mistake is
-- not worth repeating in a second store.
CREATE OR REPLACE VIEW current_published_occupation_estimates AS
SELECT DISTINCT ON (e.identity_id)
       e.*,
       r.run_key,
       r.policy_version AS run_policy_version
FROM occupation_score_estimates e
JOIN occupation_score_estimate_runs r ON r.id = e.estimate_run_id
WHERE e.is_published
  AND r.status = 'completed'
  -- A verified score always wins, whichever was written first. The insert trigger stops an
  -- estimate being published for an already-verified occupation, but it cannot see the
  -- reverse: an occupation being promoted later, while its estimate sits published. That is
  -- the normal upgrade path, so the read layer settles it structurally rather than relying on
  -- a promotion run remembering to withdraw estimates.
  AND NOT EXISTS (
      SELECT 1 FROM current_production_occupation_scores verified
      WHERE verified.identity_id = e.identity_id)
ORDER BY e.identity_id, e.estimate_run_id DESC, e.id DESC;

COMMENT ON VIEW current_published_occupation_estimates IS
  'The live preliminary estimate per identity. Every public read of an estimate goes through '
  'this view, exactly as every verified read goes through current_production_occupation_scores.';

COMMIT;
