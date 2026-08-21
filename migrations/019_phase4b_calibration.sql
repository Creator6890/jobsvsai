BEGIN;

INSERT INTO data_sources (name,source_url,version,metadata)
VALUES (
  'JobsVsAI Phase 4B calibration',
  'internal://jobsvsai/phase4b-calibration',
  '2026-Q3-v1',
  '{"scope":"phase4a_frozen_cohort","public":false,"production_scoring":false,"new_mapping_calls_allowed":false}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE phase4b_proxy_model_versions (
  id BIGSERIAL PRIMARY KEY,
  model_version TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  parameters JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','calibration','retired')),
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(parameters)='object')
);

CREATE TABLE phase4b_occupation_proxy_snapshots (
  id BIGSERIAL PRIMARY KEY,
  proxy_model_version_id BIGINT NOT NULL REFERENCES phase4b_proxy_model_versions(id),
  pilot_occupation_id BIGINT NOT NULL REFERENCES phase4a_pilot_occupations(id),
  adoption_pressure NUMERIC(7,4) NOT NULL CHECK (adoption_pressure BETWEEN 0 AND 100),
  labour_market_resilience NUMERIC(7,4) NOT NULL CHECK (labour_market_resilience BETWEEN 0 AND 100),
  proxy_confidence NUMERIC(7,4) NOT NULL CHECK (proxy_confidence BETWEEN 0 AND 100),
  domain_values JSONB NOT NULL,
  component_contributions JSONB NOT NULL,
  exact_inputs JSONB NOT NULL,
  warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
  reconciliation JSONB NOT NULL,
  input_hash CHAR(64) NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (proxy_model_version_id,pilot_occupation_id),
  CHECK (jsonb_typeof(domain_values)='object'),
  CHECK (jsonb_typeof(component_contributions)='object'),
  CHECK (jsonb_typeof(exact_inputs)='object'),
  CHECK (jsonb_typeof(warnings)='array'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

ALTER TABLE phase4a_calculation_runs
  ADD COLUMN methodology_phase TEXT NOT NULL DEFAULT '4A' CHECK (methodology_phase IN ('4A','4B')),
  ADD COLUMN proxy_model_version_id BIGINT REFERENCES phase4b_proxy_model_versions(id),
  ADD COLUMN baseline_run_id BIGINT REFERENCES phase4a_calculation_runs(id);

ALTER TABLE phase4a_task_assessments
  ADD COLUMN methodology_phase TEXT NOT NULL DEFAULT '4A' CHECK (methodology_phase IN ('4A','4B')),
  ADD COLUMN proxy_snapshot_id BIGINT REFERENCES phase4b_occupation_proxy_snapshots(id),
  ADD COLUMN proxy_confidence_penalty NUMERIC(7,4) NOT NULL DEFAULT 0 CHECK (proxy_confidence_penalty BETWEEN 0 AND 100);

ALTER TABLE phase4a_occupation_scores
  ADD COLUMN methodology_phase TEXT NOT NULL DEFAULT '4A' CHECK (methodology_phase IN ('4A','4B')),
  ADD COLUMN proxy_snapshot_id BIGINT REFERENCES phase4b_occupation_proxy_snapshots(id),
  ADD COLUMN coverage_gate_status TEXT NOT NULL DEFAULT 'not_evaluated'
    CHECK (coverage_gate_status IN ('not_evaluated','passed','below_threshold')),
  ADD COLUMN confidence_penalty NUMERIC(7,4) NOT NULL DEFAULT 0 CHECK (confidence_penalty BETWEEN 0 AND 100),
  ADD COLUMN scale_eligible BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE phase4b_distribution_diagnostics (
  id BIGSERIAL PRIMARY KEY,
  baseline_run_id BIGINT NOT NULL REFERENCES phase4a_calculation_runs(id),
  calibration_run_id BIGINT NOT NULL REFERENCES phase4a_calculation_runs(id),
  metric_scope TEXT NOT NULL CHECK (metric_scope IN ('task','occupation')),
  metric_name TEXT NOT NULL,
  baseline_summary JSONB NOT NULL,
  calibrated_summary JSONB NOT NULL,
  delta_summary JSONB NOT NULL,
  reconciliation JSONB NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (calibration_run_id,metric_scope,metric_name),
  CHECK (jsonb_typeof(baseline_summary)='object'),
  CHECK (jsonb_typeof(calibrated_summary)='object'),
  CHECK (jsonb_typeof(delta_summary)='object'),
  CHECK (jsonb_typeof(reconciliation)='object')
);

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4B calibration')
INSERT INTO phase4b_proxy_model_versions (
  model_version,name,description,parameters,status,source_id,provenance,created_by
)
SELECT 'phase4b-occupation-proxy-v1','Phase 4B occupation metadata proxy model v1',
  'Deterministic provisional environment, adoption and structural labour-resilience proxies derived from normalized O*NET occupation work-context and work-activity ratings. These are not direct labour-market measurements.',
  $proxy$
  {
    "sourcePolicy": {
      "allowed": ["onet_element_ratings.normalized_value", "sample_size", "standard_error", "recommend_suppress", "not_relevant"],
      "excluded": ["phase1_seed_market_signals", "production_scores", "downstream_automation_outcomes"],
      "suppressedRatingPolicy": "exclude_and_renormalize_without_imputation",
      "missingRatingPolicy": "exclude_and_renormalize_with_confidence_penalty"
    },
    "baseConfidence": 78,
    "missingComponentPenaltyMaximum": 30,
    "missingSampleSizePenalty": 8,
    "smallSampleThreshold": 20,
    "smallSamplePenalty": 5,
    "suppressedComponentPenalty": 10,
    "domains": {
      "physical-presence": [
        {"elementType":"work_activity","elementId":"4.A.3.a.1","scaleId":"IM","weight":0.35,"label":"Performing General Physical Activities"},
        {"elementType":"work_context","elementId":"4.C.2.d.1.b","scaleId":"CX","weight":0.20,"label":"Spend Time Standing"},
        {"elementType":"work_context","elementId":"4.C.2.d.1.d","scaleId":"CX","weight":0.15,"label":"Spend Time Walking or Running"},
        {"elementType":"work_context","elementId":"4.C.2.d.1.h","scaleId":"CX","weight":0.10,"label":"Spend Time Bending or Twisting"},
        {"elementType":"work_context","elementId":"4.C.2.a.1.c","scaleId":"CX","weight":0.10,"label":"Outdoors All Weather"},
        {"elementType":"work_context","elementId":"4.C.2.c.1.e","scaleId":"CX","weight":0.10,"label":"Hazardous Equipment"}
      ],
      "environment-variability": [
        {"elementType":"work_context","elementId":"4.C.2.a.1.c","scaleId":"CX","weight":0.25,"label":"Outdoors All Weather"},
        {"elementType":"work_context","elementId":"4.C.2.a.1.d","scaleId":"CX","weight":0.10,"label":"Outdoors Under Cover"},
        {"elementType":"work_context","elementId":"4.C.2.c.1.d","scaleId":"CX","weight":0.20,"label":"Hazardous Conditions"},
        {"elementType":"work_context","elementId":"4.C.2.c.1.e","scaleId":"CX","weight":0.15,"label":"Hazardous Equipment"},
        {"elementType":"work_context","elementId":"4.C.2.b.1.b","scaleId":"CX","weight":0.15,"label":"Very Hot or Cold Temperatures"},
        {"elementType":"work_context","elementId":"4.C.2.b.1.a","scaleId":"CX","weight":0.05,"label":"Distracting Noise"},
        {"elementType":"work_context","elementId":"4.C.3.d.1","scaleId":"CX","weight":0.10,"label":"Time Pressure"}
      ],
      "human-dependency": [
        {"elementType":"work_context","elementId":"4.C.1.a.4","scaleId":"CX","weight":0.30,"label":"Contact With Others"},
        {"elementType":"work_context","elementId":"4.C.1.a.2.l","scaleId":"CX","weight":0.25,"label":"Face-to-Face Discussions"},
        {"elementType":"work_context","elementId":"4.C.1.b.1.f","scaleId":"CX","weight":0.20,"label":"External Customers or Public"},
        {"elementType":"work_activity","elementId":"4.A.4.a.8","scaleId":"IM","weight":0.15,"label":"Working Directly With the Public"},
        {"elementType":"work_context","elementId":"4.C.1.b.1.g","scaleId":"CX","weight":0.10,"label":"Coordinate or Lead Others"}
      ],
      "regulation": [
        {"elementType":"work_activity","elementId":"4.A.2.a.3","scaleId":"IM","weight":0.60,"label":"Evaluate Compliance With Standards"},
        {"elementType":"work_context","elementId":"4.C.3.a.1","scaleId":"CX","weight":0.20,"label":"Consequence of Error"},
        {"elementType":"work_context","elementId":"4.C.3.a.2.a","scaleId":"CX","weight":0.20,"label":"Impact of Decisions"}
      ],
      "accountability": [
        {"elementType":"work_context","elementId":"4.C.3.a.1","scaleId":"CX","weight":0.35,"label":"Consequence of Error"},
        {"elementType":"work_context","elementId":"4.C.3.a.2.a","scaleId":"CX","weight":0.30,"label":"Impact of Decisions"},
        {"elementType":"work_context","elementId":"4.C.3.a.2.b","scaleId":"CX","weight":0.20,"label":"Decision Frequency"},
        {"elementType":"work_context","elementId":"4.C.3.a.4","scaleId":"CX","weight":0.15,"label":"Decision Freedom"}
      ],
      "consequence-severity": [
        {"elementType":"work_context","elementId":"4.C.3.a.1","scaleId":"CX","weight":0.45,"label":"Consequence of Error"},
        {"elementType":"work_context","elementId":"4.C.2.c.1.d","scaleId":"CX","weight":0.20,"label":"Hazardous Conditions"},
        {"elementType":"work_context","elementId":"4.C.2.c.1.e","scaleId":"CX","weight":0.15,"label":"Hazardous Equipment"},
        {"elementType":"work_context","elementId":"4.C.3.a.2.a","scaleId":"CX","weight":0.20,"label":"Impact of Decisions"}
      ]
    },
    "adoptionPressure": {
      "components": [
        {"elementType":"work_context","elementId":"4.C.3.b.2","scaleId":"CX","weight":0.40,"label":"Current Degree of Automation"},
        {"elementType":"work_activity","elementId":"4.A.3.b.1","scaleId":"IM","weight":0.30,"label":"Working with Computers"},
        {"elementType":"work_activity","elementId":"4.A.2.a.2","scaleId":"IM","weight":0.15,"label":"Processing Information"},
        {"elementType":"work_activity","elementId":"4.A.3.b.6","scaleId":"IM","weight":0.15,"label":"Documenting or Recording Information"}
      ],
      "confidenceCeiling": 68,
      "interpretation":"structural adoption pressure proxy, not observed employer adoption"
    },
    "labourMarketResilience": {
      "components": [
        {"derivedDomain":"human-dependency","weight":0.30,"label":"Human dependency"},
        {"derivedDomain":"physical-presence","weight":0.20,"label":"Physical presence"},
        {"derivedDomain":"consequence-severity","weight":0.20,"label":"Consequence severity"},
        {"elementType":"work_activity","elementId":"4.A.2.b.1","scaleId":"IM","weight":0.10,"label":"Decision and problem-solving importance"},
        {"elementType":"work_context","elementId":"4.C.3.a.4","scaleId":"CX","weight":0.10,"label":"Decision freedom"},
        {"elementType":"work_context","elementId":"4.C.3.b.2","scaleId":"CX","weight":0.10,"transform":"inverse","label":"Inverse current automation"}
      ],
      "confidenceCeiling": 60,
      "interpretation":"structural resilience proxy; no direct employment or transition measurement"
    }
  }
  $proxy$::jsonb,
  'calibration',source.id,
  '{"phase":"4B","provisional":true,"production_allowed":false,"market_signal_limitation":"available market signals are incomplete phase1 seeds and are excluded"}'::jsonb,
  'system:migration-019'
FROM source;

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4B calibration')
INSERT INTO phase4a_task_formula_versions (
  formula_type,formula_version,name,description,parameters,status,source_id,provenance,created_by
)
SELECT item.formula_type,item.formula_version,item.name,item.description,item.parameters,'pilot',source.id,
  '{"phase":"4B","calibration_only":true,"mapping_changes":false,"production_allowed":false}'::jsonb,
  'system:migration-019'
FROM source CROSS JOIN (VALUES
  ('capability_fit','task-capability-fit-v2-calibration','Task Capability Fit v2 calibration',
   'Logistic attainment by AI-minus-required capability margin, aggregated geometrically with a tighter critical-capability bottleneck. This removes the automatic 100 assigned whenever AI merely exceeds a requirement.',
   '{"logisticSlope":14,"geometricFloor":0.5,"criticalWeightThreshold":0.35,"criticalSecondaryWeightThreshold":0.20,"criticalRequiredLevelThreshold":70,"bottleneckMatchThreshold":50,"bottleneckHeadroom":8}'::jsonb),
  ('automation_feasibility','automation-feasibility-v2-calibration','Automation Feasibility v2 calibration',
   'Equal-weight capability and nonlinear constraint resistance using direct task constraints or explicitly lower-confidence occupation proxies, with domain-specific critical caps.',
   '{"capabilityFitWeight":0.50,"constraintResistanceWeight":0.50,"constraintExponent":1.35,"criticalConstraintThreshold":65,"domainWeights":{"physical-presence":0.14,"fine-motor-control":0.12,"mobility":0.10,"environment-variability":0.10,"human-dependency":0.16,"regulation":0.08,"accountability":0.08,"consequence-severity":0.12,"data-access":0.05,"workflow-integration":0.05},"directConstraintMap":{"physical-presence":"physical-presence","fine-motor-control":"fine-motor-control","mobility":"mobility","environment-variability":"real-world-sensing","human-dependency":"synchronous-human-interaction","regulation":"legal-accountability","accountability":"legal-accountability","consequence-severity":"safety-criticality","data-access":"data-access","workflow-integration":"workflow-integration"},"proxyDomains":["physical-presence","environment-variability","human-dependency","regulation","accountability","consequence-severity"],"bottleneckCapStrength":{"physical-presence":0.75,"fine-motor-control":0.80,"mobility":0.80,"environment-variability":0.55,"human-dependency":0.45,"regulation":0.55,"accountability":0.55,"consequence-severity":0.70},"maximumProxyConfidencePenalty":18,"proxyUsagePenaltyWeight":10,"proxyUncertaintyPenaltyWeight":8}'::jsonb),
  ('augmentation_potential','augmentation-potential-v2-calibration','Augmentation Potential v2 calibration',
   'Capability fit multiplied by an automation-complement curve with a small collaboration floor, avoiding the Phase 4A cluster near 70 for fully automatable tasks.',
   '{"collaborationFloor":0.15,"constraintComplementWeight":0.85,"complementExponent":0.50}'::jsonb)
) AS item(formula_type,formula_version,name,description,parameters);

WITH source AS (SELECT id FROM data_sources WHERE name='JobsVsAI Phase 4B calibration')
INSERT INTO phase4a_occupation_formula_versions (
  formula_version,name,description,parameters,status,source_id,provenance,created_by
)
SELECT 'phase4b-occupation-score-v2-calibration','Phase 4B occupation score v2 calibration',
  'Frozen-cohort aggregation using calibrated task metrics, versioned adoption and structural resilience proxies, and an enforced weighted-coverage gate with confidence penalties.',
  '{"taskExposureWeights":{"aiCapabilityFit":0.35,"automationFeasibility":0.45,"augmentationPotential":0.20},"replacementWeights":{"taskAutomationExposure":0.35,"aiCapabilityProximity":0.10,"humanDependencyResistance":0.15,"physicalDependencyResistance":0.15,"adoptionPressure":0.15,"labourMarketResilienceResistance":0.10},"taskWeight":"importance_score_x_frequency_score","minimumWeightedCoverage":70,"coverageConfidencePenaltyPerPoint":0.75,"minimumScaleConfidence":70,"confidenceWeights":{"weightedCoverage":0.40,"mappingConfidence":0.20,"frontierConfidence":0.15,"sourceCompleteness":0.10,"proxyConfidence":0.15},"proxyPolicy":"versioned_occupation_metadata_with_task_level_missing_direct_fallback","belowCoveragePolicy":"retain_score_block_scale_and_apply_confidence_penalty"}'::jsonb,
  'pilot',source.id,
  '{"phase":"4B","calibration_only":true,"public":false,"production_score_namespace":false}'::jsonb,
  'system:migration-019'
FROM source;

CREATE TRIGGER phase4b_proxy_models_append_only
  BEFORE UPDATE OR DELETE ON phase4b_proxy_model_versions
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4b_proxy_snapshots_append_only
  BEFORE UPDATE OR DELETE ON phase4b_occupation_proxy_snapshots
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();
CREATE TRIGGER phase4b_distribution_diagnostics_append_only
  BEFORE UPDATE OR DELETE ON phase4b_distribution_diagnostics
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

COMMIT;
