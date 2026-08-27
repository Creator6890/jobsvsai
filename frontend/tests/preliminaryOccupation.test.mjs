import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

// ---------------------------------------------------------------------------
// 1. Verified Page Invariant Tests
// ---------------------------------------------------------------------------

test("Verified page structure remains intact and free of preliminary styles", () => {
  const verifiedSource = fs.readFileSync(path.join(srcRoot, "components", "OccupationDetail.tsx"), "utf8");
  assert.match(verifiedSource, /className="score-section"/);
  assert.match(verifiedSource, /className="container score-grid"/);
  assert.match(verifiedSource, /<ScoreCard\s+[\s\S]*?label="AI Exposure"/);
  assert.match(verifiedSource, /<ScoreCard\s+[\s\S]*?label="Replacement Risk"/);
  assert.match(verifiedSource, /className="card task-table"/);
  assert.match(verifiedSource, /<ActionPlanSection/);
  assert.match(verifiedSource, /Related occupations/);
  assert.doesNotMatch(verifiedSource, /estimate-banner/i);
  assert.doesNotMatch(verifiedSource, /Preliminary estimate/i);
});

// ---------------------------------------------------------------------------
// 2. PageHero Layout & Title Invariants
// ---------------------------------------------------------------------------

test("PageHero renders title cleanly with optional status element", () => {
  const pageHeroSource = fs.readFileSync(path.join(srcRoot, "components", "PageShell.tsx"), "utf8");
  assert.match(pageHeroSource, /<h1>\{title\}<\/h1>/);
  assert.match(pageHeroSource, /\{status && <div className="page-hero-status">\{status\}<\/div>\}/);
  assert.match(pageHeroSource, /\{copy && <p className="lead">\{copy\}<\/p>\}/);

  const jobPageSource = fs.readFileSync(path.join(srcRoot, "app", "jobs", "[slug]", "page.tsx"), "utf8");
  assert.match(jobPageSource, /<PageHero[\s\S]*?status=\{[\s\S]*?estimate-status-row/);
  assert.match(jobPageSource, /Preliminary estimate/);
  assert.match(jobPageSource, /estimate\.confidenceLabel/);
});

// ---------------------------------------------------------------------------
// 3. EstimatedOccupationDetail Structural Invariants
// ---------------------------------------------------------------------------

test("EstimatedOccupationDetail reuses verified containers, grids, and card sizing", () => {
  const estSource = fs.readFileSync(path.join(srcRoot, "components", "EstimatedOccupationDetail.tsx"), "utf8");

  // Reuses .score-section and .container and .score-grid
  assert.match(estSource, /<section className="score-section">/);
  assert.match(estSource, /<div className="container">/);
  assert.match(estSource, /<div className="score-grid">/);

  // Uses .card .score-card for metrics with semantic tone
  assert.match(estSource, /<article className=\{`card score-card \$\{exposureSemantics\.tone\}`\}>/);
  assert.match(estSource, /<article className=\{`card score-card \$\{riskSemantics\.tone\}`\}>/);

  // Soft preliminary banner inside container
  assert.match(estSource, /<div className="card estimate-banner"/);
  assert.match(estSource, /Preliminary estimate · \{job\.confidenceLabel\}/);
  assert.match(estSource, /href="\/methodology#preliminary-estimates"/);

  // Evidence base and pending section inside .content-section and .container
  assert.match(estSource, /<section className="content-section">/);
  assert.match(estSource, /<div className="card estimate-evidence-card">/);
  assert.match(estSource, /<div className="card estimate-pending-card">/);
  assert.match(estSource, /<EvidenceReceipt/);
});

// ---------------------------------------------------------------------------
// 4. Estimation State Adaptations (E1, E2, E3)
// ---------------------------------------------------------------------------

test("E1 / E2 / E3 range vs point estimate rendering logic", () => {
  function formatScores(job) {
    const isExposureRange =
      job.aiExposureLow !== null &&
      job.aiExposureHigh !== null &&
      job.aiExposureLow !== job.aiExposureHigh;
    const isRiskRange =
      job.replacementRiskLow !== null &&
      job.replacementRiskHigh !== null &&
      job.replacementRiskLow !== job.replacementRiskHigh;

    const expText = isExposureRange
      ? `${job.aiExposureLow}–${job.aiExposureHigh}`
      : `~${job.aiExposure}`;

    const riskText = isRiskRange
      ? `${job.replacementRiskLow}–${job.replacementRiskHigh}`
      : `~${job.replacementRisk}`;

    return { isExposureRange, isRiskRange, expText, riskText };
  }

  // E1: Point estimates with high coverage
  const e1Job = {
    aiExposure: 78,
    replacementRisk: 62,
    aiExposureLow: null,
    aiExposureHigh: null,
    replacementRiskLow: null,
    replacementRiskHigh: null,
    evidenceCoverage: 98.2,
    estimateMethod: "E1",
  };
  const e1 = formatScores(e1Job);
  assert.strictEqual(e1.isExposureRange, false);
  assert.strictEqual(e1.expText, "~78");
  assert.strictEqual(e1.riskText, "~62");

  // E2: Range estimates with partial coverage
  const e2Job = {
    aiExposure: 60,
    replacementRisk: 55,
    aiExposureLow: 52,
    aiExposureHigh: 68,
    replacementRiskLow: 48,
    replacementRiskHigh: 62,
    evidenceCoverage: 50.9,
    estimateMethod: "E2",
  };
  const e2 = formatScores(e2Job);
  assert.strictEqual(e2.isExposureRange, true);
  assert.strictEqual(e2.expText, "52–68");
  assert.strictEqual(e2.riskText, "48–62");

  // E3: Range estimates from related occupations
  const e3Job = {
    aiExposure: 76,
    replacementRisk: 71,
    aiExposureLow: 67,
    aiExposureHigh: 85,
    replacementRiskLow: 63,
    replacementRiskHigh: 79,
    evidenceCoverage: null,
    supportingRelativeCount: 13,
    basedOn: ["Financial Quantitative Analysts", "Statisticians"],
    estimateMethod: "E3",
  };
  const e3 = formatScores(e3Job);
  assert.strictEqual(e3.isExposureRange, true);
  assert.strictEqual(e3.expText, "67–85");
  assert.strictEqual(e3.riskText, "63–79");
});
