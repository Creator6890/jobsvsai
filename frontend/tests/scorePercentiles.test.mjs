import test from "node:test";
import assert from "node:assert/strict";
import {
  calculatePercentile,
  formatExposurePercentile,
  formatReplacementRiskPercentile,
} from "../src/lib/scorePercentiles.ts";

test("calculatePercentile - Basic distribution", () => {
  const values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  // Score 55 has 5 values strictly less (10, 20, 30, 40, 50) -> 5/10 = 50%
  assert.equal(calculatePercentile(55, values), 50);
  // Score 95 has 9 values strictly less -> 9/10 = 90%
  assert.equal(calculatePercentile(95, values), 90);
  // Score 5 has 0 values strictly less -> 0%
  assert.equal(calculatePercentile(5, values), 0);
});

test("calculatePercentile - Boundary cases", () => {
  const values = [0, 50, 100];
  // Minimum score (0) -> 0%
  assert.equal(calculatePercentile(0, values), 0);
  // Maximum score (100) -> 2/3 = 67%
  assert.equal(calculatePercentile(100, values), 67);
  // Beyond maximum score (101) -> 3/3 = capped at 99%
  assert.equal(calculatePercentile(101, values), 99);
});

test("calculatePercentile - Tie handling and identical groups", () => {
  const values = [40, 50, 50, 50, 50, 60, 70, 80, 90, 100];
  // Score 50 has 1 value strictly less (40) -> 1/10 = 10%
  assert.equal(calculatePercentile(50, values), 10);
  // All 4 tied items get the exact same deterministic percentile
  assert.equal(calculatePercentile(50, values), calculatePercentile(50, [...values].reverse()));
});

test("calculatePercentile - Order invariance", () => {
  const sorted = [10, 20, 30, 40, 50, 60, 70, 80, 90];
  const shuffled = [50, 90, 20, 80, 10, 70, 30, 60, 40];
  assert.equal(calculatePercentile(65, sorted), calculatePercentile(65, shuffled));
  assert.equal(calculatePercentile(30, sorted), calculatePercentile(30, shuffled));
});

test("Percentile Formatting - Exposure copy safety", () => {
  assert.equal(formatExposurePercentile(0), "Lowest AI exposure in verified cohort");
  assert.equal(formatExposurePercentile(82), "More exposed than 82% of verified occupations");
  assert.equal(formatExposurePercentile(99), "More exposed than 99% of verified occupations");

  // No probability words allowed
  const label = formatExposurePercentile(75);
  assert.doesNotMatch(label, /chance|likelihood|probability/i);
});

test("Percentile Formatting - Replacement Risk copy safety", () => {
  assert.equal(formatReplacementRiskPercentile(0), "Lowest replacement risk in verified cohort");
  assert.equal(formatReplacementRiskPercentile(64), "Higher replacement pressure than 64% of verified occupations");
  assert.equal(formatReplacementRiskPercentile(99), "Higher replacement pressure than 99% of verified occupations");

  // No probability words allowed
  const label = formatReplacementRiskPercentile(60);
  assert.doesNotMatch(label, /chance|likelihood|probability/i);
});
