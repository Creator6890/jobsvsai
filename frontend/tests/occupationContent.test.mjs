import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("Occupation content generator source file exists and exports getOccupationContent", () => {
  const contentPath = path.join(srcRoot, "lib", "occupationContent.ts");
  assert.ok(fs.existsSync(contentPath), "occupationContent.ts must exist");
  const contentSource = fs.readFileSync(contentPath, "utf8");
  assert.match(contentSource, /export function getOccupationContent/);
  assert.match(contentSource, /directAnswer:/);
  assert.match(contentSource, /verdictParagraphs:/);
  assert.match(contentSource, /exposureVsReplacementContrast:/);
  assert.match(contentSource, /keyDrivers:/);
  assert.match(contentSource, /humanAdvantages:/);
  assert.match(contentSource, /faqs:/);
});

test("OccupationDetail integrates multi-dimensional verdict, direct answer, and FAQ", () => {
  const detailPath = path.join(srcRoot, "components", "OccupationDetail.tsx");
  assert.ok(fs.existsSync(detailPath), "OccupationDetail.tsx must exist");
  const detailSource = fs.readFileSync(detailPath, "utf8");

  assert.match(detailSource, /getOccupationContent/);
  assert.match(detailSource, /direct-answer-card/);
  assert.match(detailSource, /<Breadcrumbs/);
  assert.match(detailSource, /<EvidenceReceipt/);
  assert.match(detailSource, /Questions about \{job\.title\} and AI/);
  assert.match(detailSource, /<ActionPlanSection job=\{job\} \/>/);
});

test("Copy safety invariants - no sensationalism or probability claims", () => {
  const contentPath = path.join(srcRoot, "lib", "occupationContent.ts");
  const contentSource = fs.readFileSync(contentPath, "utf8");

  assert.doesNotMatch(contentSource, /ai-proof/i);
  assert.doesNotMatch(contentSource, /guaranteed job loss/i);
  assert.doesNotMatch(contentSource, /doom/i);
});
