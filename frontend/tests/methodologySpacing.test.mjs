import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("Methodology page structure has normalized rhythm and closing stack", () => {
  const methodSource = fs.readFileSync(path.join(srcRoot, "app", "methodology", "page.tsx"), "utf8");

  // Section classes
  assert.match(methodSource, /className="content-section methodology-section"/);
  assert.match(methodSource, /className="content-section section-tint methodology-section"/);
  assert.match(methodSource, /className="content-section methodology-section methodology-closing-section"/);

  // Score block grouping
  assert.match(methodSource, /<div className="two-column">[\s\S]*?<article className="card definition-card">[\s\S]*?<\/div>[\s\S]*?<div className="notice methodology-notice">/);

  // Closing stack
  assert.match(methodSource, /<div className="container methodology-closing-stack">[\s\S]*?<div className="notice">[\s\S]*?<\/div>[\s\S]*?<div className="card methodology-attribution-card">/);

  // Preliminary estimates anchor
  assert.match(methodSource, /<section className="content-section methodology-section" id="preliminary-estimates">/);

  // Copy invariants
  assert.match(methodSource, /How JobsVsAI scores work\./);
  assert.match(methodSource, /These two are not the same number, and the gap is the point\./);
  assert.match(methodSource, /What these scores are not\./);
  assert.match(methodSource, /Source attribution/);
  assert.match(methodSource, /Occupational data from O\*NET 30\.3/);
});

test("CSS rules for methodology vertical rhythm and anchor offsets exist", () => {
  const cssSource = fs.readFileSync(path.join(srcRoot, "app", "globals.css"), "utf8");

  assert.match(cssSource, /\.methodology-section\s*\{/);
  assert.match(cssSource, /\.methodology-notice\s*\{/);
  assert.match(cssSource, /\.methodology-closing-stack\s*\{/);
  assert.match(cssSource, /\.methodology-attribution-card\s*\{/);
  assert.match(cssSource, /#preliminary-estimates\s*\{\s*scroll-margin-top:/);
  assert.match(cssSource, /\.method-list\s*\{/);
});
