/**
 * Deterministic Population Percentile Calculator for Verified Occupations.
 *
 * POLICY INVARIANTS:
 * 1. Reference cohort MUST consist solely of Verified occupations (N = 507).
 *    Preliminary estimates are NEVER mixed into the reference distribution.
 * 2. Percentile is a population rank, NOT a probability or likelihood.
 *    Language must strictly describe comparative cohort position.
 * 3. Deterministic tie-handling:
 *    percentile = round((count_strictly_less / total_verified) * 100)
 *    This represents the exact proportion of verified occupations with a strictly lower score.
 */

export type MetricType = "aiExposure" | "replacementRisk";

/**
 * Calculates deterministic percentile rank against a reference cohort.
 *
 * @param score The target score (0–100).
 * @param values The array of all verified scores for this metric.
 * @returns An integer between 0 and 99 representing the percentage of verified occupations scoring strictly lower.
 */
export function calculatePercentile(score: number, values: number[]): number {
  if (!values || values.length === 0) return 50;
  const countStrictlyLess = values.filter((v) => v < score).length;
  const rawPercentile = Math.round((countStrictlyLess / values.length) * 100);
  // Cap at 99 so an occupation cannot claim to have a higher score than 100% of its own cohort
  return Math.max(0, Math.min(99, rawPercentile));
}

/**
 * Generates user-facing comparative copy for AI Exposure percentile.
 *
 * @param percentile The calculated percentile (0–99).
 */
export function formatExposurePercentile(percentile: number): string {
  if (percentile <= 0) {
    return "Lowest AI exposure in verified cohort";
  }
  if (percentile >= 99) {
    return "More exposed than 99% of verified occupations";
  }
  return `More exposed than ${percentile}% of verified occupations`;
}

/**
 * Generates user-facing comparative copy for Replacement Risk percentile.
 *
 * @param percentile The calculated percentile (0–99).
 */
export function formatReplacementRiskPercentile(percentile: number): string {
  if (percentile <= 0) {
    return "Lowest replacement risk in verified cohort";
  }
  if (percentile >= 99) {
    return "Higher replacement pressure than 99% of verified occupations";
  }
  return `Higher replacement pressure than ${percentile}% of verified occupations`;
}
