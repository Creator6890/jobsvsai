import test from "node:test";
import assert from "node:assert/strict";
import { getScoreSemantics } from "../src/lib/scoreSemantics.ts";

test("1. Adverse Metrics (Higher = Worse) semantic mapping and thresholds", () => {
  // Low risk band: 0–33 -> "safe" (green)
  const expLow = getScoreSemantics("ai_exposure", 20);
  assert.equal(expLow.direction, "adverse");
  assert.equal(expLow.band, "Low");
  assert.equal(expLow.tone, "safe");
  assert.equal(expLow.label, "Low exposure");
  assert.match(expLow.chipClass, /safe/);
  assert.match(expLow.badgeClass, /safe/);

  const riskLow = getScoreSemantics("replacement_risk", 20);
  assert.equal(riskLow.direction, "adverse");
  assert.equal(riskLow.band, "Low");
  assert.equal(riskLow.tone, "safe");
  assert.equal(riskLow.label, "Low replacement risk");

  // Moderate risk band: 34–66 -> "moderate" (amber)
  const expMod = getScoreSemantics("ai_exposure", 50);
  assert.equal(expMod.direction, "adverse");
  assert.equal(expMod.band, "Moderate");
  assert.equal(expMod.tone, "moderate");
  assert.equal(expMod.label, "Moderate exposure");

  const riskMod = getScoreSemantics("replacement_risk", 50);
  assert.equal(riskMod.direction, "adverse");
  assert.equal(riskMod.band, "Moderate");
  assert.equal(riskMod.tone, "moderate");
  assert.equal(riskMod.label, "Moderate replacement risk");

  // High risk band: 67–100 -> "risk" (red)
  const expHigh = getScoreSemantics("ai_exposure", 80);
  assert.equal(expHigh.direction, "adverse");
  assert.equal(expHigh.band, "High");
  assert.equal(expHigh.tone, "risk");
  assert.equal(expHigh.label, "High exposure");

  const riskHigh = getScoreSemantics("replacement_risk", 80);
  assert.equal(riskHigh.direction, "adverse");
  assert.equal(riskHigh.band, "High");
  assert.equal(riskHigh.tone, "risk");
  assert.equal(riskHigh.label, "High replacement risk");

  // Adoption pressure and task exposure
  const adopt = getScoreSemantics("adoption_pressure", 70);
  assert.equal(adopt.direction, "adverse");
  assert.equal(adopt.tone, "risk");
  assert.equal(adopt.label, "High adoption pressure");

  const task = getScoreSemantics("task_exposure", 30);
  assert.equal(task.direction, "adverse");
  assert.equal(task.tone, "safe");
  assert.equal(task.label, "Low exposure");
});

test("2. Protective / Resilience Metrics (Higher = Better) semantic mapping", () => {
  // Weak band: 0–33 -> "risk" (red)
  const humWeak = getScoreSemantics("human_dependency", 20);
  assert.equal(humWeak.direction, "protective");
  assert.equal(humWeak.band, "Weak");
  assert.equal(humWeak.tone, "risk");
  assert.equal(humWeak.label, "Weak human dependency");

  const physWeak = getScoreSemantics("physical_dependency", 18);
  assert.equal(physWeak.direction, "protective");
  assert.equal(physWeak.band, "Weak");
  assert.equal(physWeak.tone, "risk");
  assert.equal(physWeak.label, "Weak physical dependency");

  const resWeak = getScoreSemantics("labour_market_resilience", 25);
  assert.equal(resWeak.direction, "protective");
  assert.equal(resWeak.band, "Weak");
  assert.equal(resWeak.tone, "risk");
  assert.equal(resWeak.label, "Weak resilience");

  // Moderate band: 34–66 -> "moderate" (amber)
  const humMod = getScoreSemantics("human_dependency", 50);
  assert.equal(humMod.direction, "protective");
  assert.equal(humMod.band, "Moderate");
  assert.equal(humMod.tone, "moderate");
  assert.equal(humMod.label, "Moderate human dependency");

  // Strong band: 67–100 -> "safe" (green)
  const humStrong = getScoreSemantics("human_dependency", 80);
  assert.equal(humStrong.direction, "protective");
  assert.equal(humStrong.band, "Strong");
  assert.equal(humStrong.tone, "safe");
  assert.equal(humStrong.label, "Strong human dependency");

  const physStrong = getScoreSemantics("physical_dependency", 75);
  assert.equal(physStrong.direction, "protective");
  assert.equal(physStrong.band, "Strong");
  assert.equal(physStrong.tone, "safe");
  assert.equal(physStrong.label, "Strong physical dependency");

  const resStrong = getScoreSemantics("labour_market_resilience", 85);
  assert.equal(resStrong.direction, "protective");
  assert.equal(resStrong.band, "Strong");
  assert.equal(resStrong.tone, "safe");
  assert.equal(resStrong.label, "Strong resilience");
});

test("3. Confidence & Evidence metrics remain neutral/evidence (never career-risk red/green)", () => {
  const confLow = getScoreSemantics("confidence", 20);
  assert.equal(confLow.direction, "confidence");
  assert.equal(confLow.band, "Lower");
  assert.equal(confLow.tone, "neutral");
  assert.equal(confLow.label, "Lower confidence");

  const confMod = getScoreSemantics("confidence", 50);
  assert.equal(confMod.direction, "confidence");
  assert.equal(confMod.band, "Moderate");
  assert.equal(confMod.tone, "neutral");
  assert.equal(confMod.label, "Moderate confidence");

  const confHigh = getScoreSemantics("confidence", 80);
  assert.equal(confHigh.direction, "confidence");
  assert.equal(confHigh.band, "Higher");
  assert.equal(confHigh.tone, "neutral");
  assert.equal(confHigh.label, "Higher confidence");

  const taskCov = getScoreSemantics("task_coverage", 85);
  assert.equal(taskCov.direction, "confidence");
  assert.equal(taskCov.tone, "neutral");
  assert.equal(taskCov.label, "85% coverage");
});

test("4. Career Fit & Transition Fit metrics are positive and never adverse/red", () => {
  const fit90 = getScoreSemantics("career_fit", 90);
  assert.equal(fit90.direction, "fit");
  assert.equal(fit90.tone, "accent");
  assert.notEqual(fit90.tone, "risk"); // Must NEVER be adverse/red
  assert.equal(fit90.band, "Strong fit");

  const fit40 = getScoreSemantics("career_fit", 40);
  assert.equal(fit40.direction, "fit");
  assert.notEqual(fit40.tone, "risk");
  assert.equal(fit40.band, "Developing fit");

  const transFit = getScoreSemantics("transition_fit", 82);
  assert.equal(transFit.direction, "fit");
  assert.notEqual(transFit.tone, "risk");
  assert.equal(transFit.band, "Strong fit");
});

test("5. Boundary value tests [0, 33, 34, 66, 67, 100]", () => {
  // Adverse boundaries
  assert.equal(getScoreSemantics("ai_exposure", 0).band, "Low");
  assert.equal(getScoreSemantics("ai_exposure", 0).tone, "safe");
  assert.equal(getScoreSemantics("ai_exposure", 33).band, "Low");
  assert.equal(getScoreSemantics("ai_exposure", 33).tone, "safe");

  assert.equal(getScoreSemantics("ai_exposure", 34).band, "Moderate");
  assert.equal(getScoreSemantics("ai_exposure", 34).tone, "moderate");
  assert.equal(getScoreSemantics("ai_exposure", 66).band, "Moderate");
  assert.equal(getScoreSemantics("ai_exposure", 66).tone, "moderate");

  assert.equal(getScoreSemantics("ai_exposure", 67).band, "High");
  assert.equal(getScoreSemantics("ai_exposure", 67).tone, "risk");
  assert.equal(getScoreSemantics("ai_exposure", 100).band, "High");
  assert.equal(getScoreSemantics("ai_exposure", 100).tone, "risk");

  // Protective boundaries
  assert.equal(getScoreSemantics("human_dependency", 0).band, "Weak");
  assert.equal(getScoreSemantics("human_dependency", 0).tone, "risk");
  assert.equal(getScoreSemantics("human_dependency", 33).band, "Weak");
  assert.equal(getScoreSemantics("human_dependency", 33).tone, "risk");

  assert.equal(getScoreSemantics("human_dependency", 34).band, "Moderate");
  assert.equal(getScoreSemantics("human_dependency", 34).tone, "moderate");
  assert.equal(getScoreSemantics("human_dependency", 66).band, "Moderate");
  assert.equal(getScoreSemantics("human_dependency", 66).tone, "moderate");

  assert.equal(getScoreSemantics("human_dependency", 67).band, "Strong");
  assert.equal(getScoreSemantics("human_dependency", 67).tone, "safe");
  assert.equal(getScoreSemantics("human_dependency", 100).band, "Strong");
  assert.equal(getScoreSemantics("human_dependency", 100).tone, "safe");
});

test("6. Preliminary estimate options and labels", () => {
  const estHighExp = getScoreSemantics("ai_exposure", 72, { isEstimated: true });
  assert.equal(estHighExp.label, "High estimated exposure");
  assert.equal(estHighExp.tone, "risk");

  const estModRisk = getScoreSemantics("replacement_risk", 55, { isEstimated: true });
  assert.equal(estModRisk.label, "Moderate estimated risk");
  assert.equal(estModRisk.tone, "moderate");

  const estLowRisk = getScoreSemantics("replacement_risk", 20, { isEstimated: true });
  assert.equal(estLowRisk.label, "Low estimated risk");
  assert.equal(estLowRisk.tone, "safe");
});

test("7. Unknown metric fallback to safe neutral", () => {
  const unknown = getScoreSemantics("unknown_metric_xyz", 50);
  assert.equal(unknown.direction, "neutral");
  assert.equal(unknown.tone, "neutral");
  assert.equal(unknown.band, "Neutral");
});
