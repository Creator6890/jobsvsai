-- 026 — Register the validated Phase 4B/Phase 5 scoring model, inactive.
--
-- This migration registers the engine model so production snapshots can reference something
-- truthful. It does NOT activate it: `is_active` stays false and JVS 1.0.3 remains the
-- active production model until the Phase 6 launch-quality review says otherwise.
--
-- The two models are NOT harmonised. They have different factor sets, different weights and
-- different semantics, and conflating them would destroy the ability to explain either. The
-- new `methodology_family` column makes the incompatibility explicit and enforceable:
--
--   legacy-jvs-1        JVS 1.0.3. Six factors over hand-authored occupation columns.
--   jobsvsai-engine-v2  Phase 4B/4D/5. Six factors over task-derived capability, automation
--                       feasibility and direct structural proxies.
--
-- Two triggers bind arithmetic to family, so the legacy worker can never stamp legacy
-- arithmetic with a v2 model id, and a production snapshot can never claim to be v2 while
-- referencing the legacy model.

BEGIN;

ALTER TABLE scoring_model_versions
  ADD COLUMN IF NOT EXISTS methodology_family TEXT NOT NULL DEFAULT 'legacy-jvs-1';

ALTER TABLE scoring_model_versions
  DROP CONSTRAINT IF EXISTS scoring_model_versions_methodology_family_check;
ALTER TABLE scoring_model_versions
  ADD CONSTRAINT scoring_model_versions_methodology_family_check
  CHECK (methodology_family IN ('legacy-jvs-1','jobsvsai-engine-v2'));

COMMENT ON COLUMN scoring_model_versions.methodology_family IS
  'Which arithmetic produces scores under this version. Legacy and engine models are not '
  'interchangeable and are never harmonised; the family is enforced by trigger.';

-- ---------------------------------------------------------------------------
-- The validated engine model.
--
-- replacement_config is copied verbatim from `phase4b-occupation-score-v2-calibration`
-- (migration 019, phase4a_occupation_formula_versions.parameters -> replacementWeights).
-- Factor keys are the engine's own, deliberately different from the legacy column names.
--
--   taskAutomationExposure           0.35   weighted mean task Automation Feasibility
--   aiCapabilityProximity            0.10   weighted mean task AI Capability Fit
--   humanDependencyResistance        0.15   100 - human dependency (inverse)
--   physicalDependencyResistance     0.15   100 - physical dependency (inverse)
--   adoptionPressure                 0.15   PROVISIONAL
--   labourMarketResilienceResistance 0.10   PROVISIONAL, inverse
--
-- exposure_config records the rest of the validated occupation formula so the registration
-- is self-describing: the task-exposure blend, the coverage gate, and the confidence
-- weights. The application does not read these for v2 — the engine carries its own
-- versioned parameters — but a registered model that cannot explain itself is not a record.
-- ---------------------------------------------------------------------------
INSERT INTO scoring_model_versions (version, description, exposure_config, replacement_config, is_active, methodology_family)
VALUES (
  'JVS 2.0.0-phase4b',
  'JobsVsAI engine model: Phase 4B occupation calibration over Phase 4D direct structural '
  'proxies, validated at corpus scale in Phase 5. Registered inactive pending launch-quality review.',
  '{
     "occupationFormulaVersion": "phase4b-occupation-score-v2-calibration",
     "taskExposureWeights": {"aiCapabilityFit": 0.35, "automationFeasibility": 0.45, "augmentationPotential": 0.20},
     "taskWeight": "importance_score_x_frequency_score",
     "minimumWeightedCoverage": 70,
     "coverageConfidencePenaltyPerPoint": 0.75,
     "minimumScaleConfidence": 70,
     "confidenceWeights": {"weightedCoverage": 0.40, "mappingConfidence": 0.20, "frontierConfidence": 0.15, "sourceCompleteness": 0.10, "proxyConfidence": 0.15},
     "belowCoveragePolicy": "retain_score_block_scale_and_apply_confidence_penalty",
     "structuralProxyModelVersion": "phase4d-direct-structural-proxy-v2",
     "baseProxyModelVersion": "phase4b-occupation-proxy-v1",
     "provisionalFactors": ["adoptionPressure", "labourMarketResilienceResistance"]
   }'::jsonb,
  '{
     "taskAutomationExposure": 0.35,
     "aiCapabilityProximity": 0.10,
     "humanDependencyResistance": 0.15,
     "physicalDependencyResistance": 0.15,
     "adoptionPressure": 0.15,
     "labourMarketResilienceResistance": 0.10
   }'::jsonb,
  false,
  'jobsvsai-engine-v2'
)
ON CONFLICT (version) DO NOTHING;

-- Registration must not have disturbed the active model.
DO $$
DECLARE active_version TEXT;
BEGIN
  SELECT version INTO active_version FROM scoring_model_versions WHERE is_active;
  IF active_version IS DISTINCT FROM 'JVS 1.0.3' THEN
    RAISE EXCEPTION 'Migration 026 must leave JVS 1.0.3 active, found %', active_version;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Guard 1 — legacy arithmetic may only be stamped with a legacy model.
--
-- worker/jobs.py computes JVS 1.0.3 arithmetic and writes occupation_scores under whichever
-- model is active. If the active model were ever flipped to the engine model, it would keep
-- computing legacy numbers and label them v2. The database now refuses.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_legacy_score_model_family()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE family TEXT;
BEGIN
  SELECT methodology_family INTO family
  FROM scoring_model_versions WHERE id = NEW.model_version_id;
  IF family <> 'legacy-jvs-1' THEN
    RAISE EXCEPTION
      'occupation_scores holds legacy JVS 1.x arithmetic and cannot be written under model family %. '
      'Engine scores belong in production_occupation_score_snapshots via a promotion run.', family;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER occupation_scores_legacy_family_only
  BEFORE INSERT OR UPDATE ON occupation_scores
  FOR EACH ROW EXECUTE FUNCTION enforce_legacy_score_model_family();

CREATE TRIGGER score_derivations_legacy_family_only
  BEFORE INSERT OR UPDATE ON score_derivations
  FOR EACH ROW EXECUTE FUNCTION enforce_legacy_score_model_family();

-- ---------------------------------------------------------------------------
-- Guard 2 — the production score store only accepts engine models.
--
-- The mirror of guard 1: a promotion run or snapshot cannot reference JVS 1.0.3 and claim to
-- carry engine intelligence.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_engine_score_model_family()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE family TEXT;
BEGIN
  SELECT methodology_family INTO family
  FROM scoring_model_versions WHERE id = NEW.scoring_model_version_id;
  IF family <> 'jobsvsai-engine-v2' THEN
    RAISE EXCEPTION
      'the production score store carries JobsVsAI engine scores and cannot reference model family %', family;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER production_promotion_runs_engine_family_only
  BEFORE INSERT ON production_promotion_runs
  FOR EACH ROW EXECUTE FUNCTION enforce_engine_score_model_family();

CREATE TRIGGER production_snapshots_engine_family_only
  BEFORE INSERT ON production_occupation_score_snapshots
  FOR EACH ROW EXECUTE FUNCTION enforce_engine_score_model_family();

COMMIT;
