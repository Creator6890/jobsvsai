/**
 * JobsVsAI Direction-Aware Semantic Score Color & Label System (V1)
 *
 * Implements a centralized, direction-aware semantic score classification utility
 * for all numeric intelligence metrics across JobsVsAI surfaces.
 *
 * Core Semantic Rules:
 * 1. Adverse Metrics (Higher = Worse / Greater Risk):
 *    - 0–33:   LOW      -> "safe" (muted green)
 *    - 34–66:  MODERATE -> "moderate" (accessible amber/orange)
 *    - 67–100: HIGH     -> "risk" (red)
 *    Examples: AI Exposure, Replacement Risk, Adoption Pressure, Task Exposure.
 *
 * 2. Protective / Resilience Metrics (Higher = Better / Stronger Resistance):
 *    - 0–33:   WEAK     -> "risk" (red)
 *    - 34–66:  MODERATE -> "moderate" (accessible amber/orange)
 *    - 67–100: STRONG   -> "safe" (muted green)
 *    Examples: Human Dependency, Physical Dependency, Labour-market Resilience.
 *
 * 3. Confidence & Evidence Metrics (Evidence Quality):
 *    - Visually distinct neutral / violet treatment (never career-risk red/green).
 *    - 0–33:   Lower confidence
 *    - 34–66:  Moderate confidence
 *    - 67–100: Higher confidence
 *
 * 4. Positive / Fit Metrics:
 *    - Higher = Better fit. Uses positive brand/accent (violet) treatment, never adverse red.
 *
 * 5. Accessibility Invariant:
 *    - Color is never used alone: every prominent score provides a semantic text label.
 */

export type MetricDirection = "adverse" | "protective" | "confidence" | "fit" | "neutral";
export type SemanticTone = "safe" | "moderate" | "risk" | "neutral" | "accent";

export interface ScoreSemanticsOptions {
  isEstimated?: boolean;
  compact?: boolean;
}

export interface ScoreSemantics {
  metric: string;
  canonicalKey: string;
  value: number;
  direction: MetricDirection;
  band: string;
  label: string;
  shortLabel: string;
  tone: SemanticTone;
  chipClass: string;
  badgeClass: string;
  textClass: string;
}

// ---------------------------------------------------------------------------
// Metric Registry & Direction Definitions
// ---------------------------------------------------------------------------

interface MetricConfig {
  canonicalKey: string;
  direction: MetricDirection;
  noun: string;
  estimatedNoun?: string;
}

const METRIC_CONFIGS: Record<string, MetricConfig> = {
  // Adverse Metrics (Higher = Worse)
  ai_exposure: { canonicalKey: "ai_exposure", direction: "adverse", noun: "exposure", estimatedNoun: "estimated exposure" },
  aiexposure: { canonicalKey: "ai_exposure", direction: "adverse", noun: "exposure", estimatedNoun: "estimated exposure" },
  exposure: { canonicalKey: "ai_exposure", direction: "adverse", noun: "exposure", estimatedNoun: "estimated exposure" },
  "ai exposure": { canonicalKey: "ai_exposure", direction: "adverse", noun: "exposure", estimatedNoun: "estimated exposure" },
  "estimated ai exposure": { canonicalKey: "ai_exposure", direction: "adverse", noun: "exposure", estimatedNoun: "estimated exposure" },

  replacement_risk: { canonicalKey: "replacement_risk", direction: "adverse", noun: "replacement risk", estimatedNoun: "estimated risk" },
  replacementrisk: { canonicalKey: "replacement_risk", direction: "adverse", noun: "replacement risk", estimatedNoun: "estimated risk" },
  risk: { canonicalKey: "replacement_risk", direction: "adverse", noun: "risk", estimatedNoun: "estimated risk" },
  "replacement risk": { canonicalKey: "replacement_risk", direction: "adverse", noun: "replacement risk", estimatedNoun: "estimated risk" },
  "estimated replacement risk": { canonicalKey: "replacement_risk", direction: "adverse", noun: "replacement risk", estimatedNoun: "estimated risk" },

  adoption_pressure: { canonicalKey: "adoption_pressure", direction: "adverse", noun: "adoption pressure" },
  adoptionpressure: { canonicalKey: "adoption_pressure", direction: "adverse", noun: "adoption pressure" },
  "adoption pressure": { canonicalKey: "adoption_pressure", direction: "adverse", noun: "adoption pressure" },

  task_exposure: { canonicalKey: "task_exposure", direction: "adverse", noun: "exposure" },
  taskexposure: { canonicalKey: "task_exposure", direction: "adverse", noun: "exposure" },
  automation_feasibility: { canonicalKey: "automation_feasibility", direction: "adverse", noun: "automation exposure" },

  // Protective Metrics (Higher = Better)
  human_dependency: { canonicalKey: "human_dependency", direction: "protective", noun: "human dependency" },
  humandependency: { canonicalKey: "human_dependency", direction: "protective", noun: "human dependency" },
  "human dependency": { canonicalKey: "human_dependency", direction: "protective", noun: "human dependency" },

  physical_dependency: { canonicalKey: "physical_dependency", direction: "protective", noun: "physical dependency" },
  physicaldependency: { canonicalKey: "physical_dependency", direction: "protective", noun: "physical dependency" },
  "physical dependency": { canonicalKey: "physical_dependency", direction: "protective", noun: "physical dependency" },

  labour_market_resilience: { canonicalKey: "labour_market_resilience", direction: "protective", noun: "resilience" },
  labourmarketresilience: { canonicalKey: "labour_market_resilience", direction: "protective", noun: "resilience" },
  "labour-market resilience": { canonicalKey: "labour_market_resilience", direction: "protective", noun: "resilience" },
  "labour market resilience": { canonicalKey: "labour_market_resilience", direction: "protective", noun: "resilience" },
  resilience: { canonicalKey: "labour_market_resilience", direction: "protective", noun: "resilience" },

  // Confidence & Evidence (Evidence Quality - Neutral)
  confidence: { canonicalKey: "confidence", direction: "confidence", noun: "confidence" },
  confidence_score: { canonicalKey: "confidence", direction: "confidence", noun: "confidence" },
  task_coverage: { canonicalKey: "task_coverage", direction: "confidence", noun: "coverage" },
  weightedtaskcoverage: { canonicalKey: "task_coverage", direction: "confidence", noun: "coverage" },
  "task coverage": { canonicalKey: "task_coverage", direction: "confidence", noun: "coverage" },
  evidence_coverage: { canonicalKey: "evidence_coverage", direction: "confidence", noun: "task coverage" },
  evidencecoverage: { canonicalKey: "evidence_coverage", direction: "confidence", noun: "task coverage" },

  // Fit Metrics (Higher = Better Fit)
  career_fit: { canonicalKey: "career_fit", direction: "fit", noun: "career fit" },
  careerfit: { canonicalKey: "career_fit", direction: "fit", noun: "career fit" },
  "career fit": { canonicalKey: "career_fit", direction: "fit", noun: "career fit" },
  transition_fit: { canonicalKey: "transition_fit", direction: "fit", noun: "transition fit" },
  transitionfit: { canonicalKey: "transition_fit", direction: "fit", noun: "transition fit" },
  "transition fit": { canonicalKey: "transition_fit", direction: "fit", noun: "transition fit" },
};

// ---------------------------------------------------------------------------
// Normalizer
// ---------------------------------------------------------------------------

function normalizeMetricKey(metric: string): string {
  return metric.trim().toLowerCase().replace(/[-_]/g, " ");
}

function resolveMetricConfig(metric: string): MetricConfig {
  const exact = METRIC_CONFIGS[metric.toLowerCase()];
  if (exact) return exact;

  const normalized = normalizeMetricKey(metric);
  const byNorm = METRIC_CONFIGS[normalized];
  if (byNorm) return byNorm;

  // Unknown metric: fallback to safe neutral
  return {
    canonicalKey: metric,
    direction: "neutral",
    noun: metric,
  };
}

// ---------------------------------------------------------------------------
// Main Shared Semantic Utility
// ---------------------------------------------------------------------------

export function getScoreSemantics(
  metric: string,
  value: number,
  options: ScoreSemanticsOptions = {}
): ScoreSemantics {
  const config = resolveMetricConfig(metric);
  const { isEstimated = false, compact = false } = options;
  const clampedVal = Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 0;

  let band = "Moderate";
  let shortLabel = "Moderate";
  let label = "";
  let tone: SemanticTone = "neutral";

  const noun = isEstimated && config.estimatedNoun ? config.estimatedNoun : config.noun;

  switch (config.direction) {
    case "adverse": {
      // Adverse: 0–33 Low (safe/green), 34–66 Moderate (amber), 67–100 High (risk/red)
      if (clampedVal <= 33) {
        band = "Low";
        shortLabel = "Low";
        tone = "safe";
        label = compact ? "Low" : `Low ${noun}`;
      } else if (clampedVal <= 66) {
        band = "Moderate";
        shortLabel = "Moderate";
        tone = "moderate";
        label = compact ? "Moderate" : `Moderate ${noun}`;
      } else {
        band = "High";
        shortLabel = "High";
        tone = "risk";
        label = compact ? "High" : `High ${noun}`;
      }
      break;
    }

    case "protective": {
      // Protective: 0–33 Weak (risk/red), 34–66 Moderate (amber), 67–100 Strong (safe/green)
      if (clampedVal <= 33) {
        band = "Weak";
        shortLabel = "Weak";
        tone = "risk";
        label = compact ? "Weak" : `Weak ${noun}`;
      } else if (clampedVal <= 66) {
        band = "Moderate";
        shortLabel = "Moderate";
        tone = "moderate";
        label = compact ? "Moderate" : `Moderate ${noun}`;
      } else {
        band = "Strong";
        shortLabel = "Strong";
        tone = "safe";
        label = compact ? "Strong" : `Strong ${noun}`;
      }
      break;
    }

    case "confidence": {
      // Confidence & Evidence: Neutral/Violet language, never career-risk red/green
      tone = "neutral";
      if (config.canonicalKey === "confidence") {
        if (clampedVal <= 33) {
          band = "Lower";
          shortLabel = "Lower";
          label = compact ? "Lower" : "Lower confidence";
        } else if (clampedVal <= 66) {
          band = "Moderate";
          shortLabel = "Moderate";
          label = compact ? "Moderate" : "Moderate confidence";
        } else {
          band = "Higher";
          shortLabel = "Higher";
          label = compact ? "Higher" : "Higher confidence";
        }
      } else {
        // Task coverage / evidence coverage
        band = `${clampedVal}%`;
        shortLabel = `${clampedVal}%`;
        label = `${clampedVal}% ${noun}`;
      }
      break;
    }

    case "fit": {
      // Positive Fit: Higher = Better fit. Always uses accent (violet), never adverse red.
      tone = "accent";
      if (clampedVal >= 75) {
        band = "Strong fit";
        shortLabel = "Strong";
        label = compact ? `${clampedVal}%` : `Strong ${noun}`;
      } else if (clampedVal >= 50) {
        band = "Moderate fit";
        shortLabel = "Moderate";
        tone = "neutral";
        label = compact ? `${clampedVal}%` : `Moderate ${noun}`;
      } else {
        band = "Developing fit";
        shortLabel = "Developing";
        tone = "neutral";
        label = compact ? `${clampedVal}%` : `Developing ${noun}`;
      }
      break;
    }

    case "neutral":
    default: {
      band = "Neutral";
      shortLabel = String(clampedVal);
      label = `${noun}: ${clampedVal}`;
      tone = "neutral";
      break;
    }
  }

  const chipClass = `chip ${tone}`;
  const badgeClass = `score-badge ${tone}`;
  const textClass =
    tone === "safe"
      ? "text-semantic-safe"
      : tone === "moderate"
      ? "text-semantic-moderate"
      : tone === "risk"
      ? "text-semantic-risk"
      : "";

  return {
    metric,
    canonicalKey: config.canonicalKey,
    value: clampedVal,
    direction: config.direction,
    band,
    label,
    shortLabel,
    tone,
    chipClass,
    badgeClass,
    textClass,
  };
}

// ---------------------------------------------------------------------------
// Helpers for Risk Metric Groups
// ---------------------------------------------------------------------------

export const ADVERSE_METRICS = [
  "ai_exposure",
  "replacement_risk",
  "adoption_pressure",
  "task_exposure",
  "automation_feasibility",
] as const;

export const PROTECTIVE_METRICS = [
  "human_dependency",
  "physical_dependency",
  "labour_market_resilience",
] as const;

export const NEUTRAL_METRICS = [
  "confidence",
  "task_coverage",
  "evidence_coverage",
] as const;
