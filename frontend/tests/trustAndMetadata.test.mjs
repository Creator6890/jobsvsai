import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("EvidenceReceipt component exists and renders verified and preliminary states", () => {
  const receiptPath = path.join(srcRoot, "components", "EvidenceReceipt.tsx");
  assert.ok(fs.existsSync(receiptPath), "EvidenceReceipt.tsx must exist");
  const source = fs.readFileSync(receiptPath, "utf8");

  assert.match(source, /Taxonomy Source/);
  assert.match(source, /AI Capability Model/);
  assert.match(source, /Scoring Model/);
  assert.match(source, /Evidence Coverage/);
  assert.match(source, /Model Confidence/);
  assert.match(source, /Verified Analysis/);
  assert.match(source, /Preliminary Estimate/);
  assert.match(source, /Versioned Multi-Factor Scoring Pipeline/);
  assert.match(source, /Cross-Occupational Structural Proxy Engine/);
  assert.match(source, /href="\/methodology"/);
});

test("Breadcrumbs component exists and outputs valid BreadcrumbList schema", () => {
  const breadcrumbPath = path.join(srcRoot, "components", "Breadcrumbs.tsx");
  assert.ok(fs.existsSync(breadcrumbPath), "Breadcrumbs.tsx must exist");
  const source = fs.readFileSync(breadcrumbPath, "utf8");

  assert.match(source, /@type":\s*"BreadcrumbList"/);
  assert.match(source, /itemListElement/);
  assert.match(source, /@type":\s*"ListItem"/);
  assert.match(source, /aria-label="Breadcrumb"/);
});

test("Root layout includes Organization and WebSite structured data and excludes JobPosting", () => {
  const layoutPath = path.join(srcRoot, "app", "layout.tsx");
  const source = fs.readFileSync(layoutPath, "utf8");

  assert.match(source, /@type":\s*"Organization"/);
  assert.match(source, /@type":\s*"WebSite"/);
  assert.doesNotMatch(source, /JobPosting/);
});

test("No JobPosting schema exists anywhere in the frontend codebase", () => {
  const appDir = path.join(srcRoot, "app");
  function scan(dir) {
    for (const f of fs.readdirSync(dir)) {
      const full = path.join(dir, f);
      if (fs.statSync(full).isDirectory()) scan(full);
      else if (f.endsWith(".tsx") || f.endsWith(".ts")) {
        const content = fs.readFileSync(full, "utf8");
        assert.doesNotMatch(content, /"JobPosting"/, `Forbidden JobPosting schema found in ${full}`);
      }
    }
  }
  scan(appDir);
});

test("Technical methodology page exists with verified formulas and canonical metadata", () => {
  const techPath = path.join(srcRoot, "app", "methodology", "technical", "page.tsx");
  assert.ok(fs.existsSync(techPath), "methodology/technical/page.tsx must exist");
  const source = fs.readFileSync(techPath, "utf8");

  assert.match(source, /Technical Methodology & Scoring Architecture/);
  assert.match(source, /canonical:\s*"https:\/\/jobsvsai\.com\/methodology\/technical"/);
  assert.match(source, /15 AI Capability Dimensions/);
  assert.match(source, /CapabilityFit/);
  assert.match(source, /BottleneckCap/);
  assert.match(source, /href="\/methodology"/);
  assert.match(source, /href="\/methodology\/changelog"/);
});

test("Methodology changelog page exists with public version entries and canonical metadata", () => {
  const changelogPath = path.join(srcRoot, "app", "methodology", "changelog", "page.tsx");
  assert.ok(fs.existsSync(changelogPath), "methodology/changelog/page.tsx must exist");
  const source = fs.readFileSync(changelogPath, "utf8");

  assert.match(source, /JobsVsAI methodology changelog/);
  assert.match(source, /canonical:\s*"https:\/\/jobsvsai\.com\/methodology\/changelog"/);
  assert.match(source, /Preliminary Estimate Methodology — 2026 Q3/);
  assert.match(source, /Multi-Factor Occupational Scoring Model — 2026 Q3/);
  assert.doesNotMatch(source, /Semantic Direction System/);
  assert.match(source, /href="\/methodology"/);
  assert.match(source, /href="\/methodology\/technical"/);
});

test("Sitemap includes technical methodology, changelog, career-fit, career directory, career fields, research, and allowlisted comparisons, and excludes preliminary estimates and transitions", () => {
  const sitemapPath = path.join(srcRoot, "app", "sitemap.ts");
  const source = fs.readFileSync(sitemapPath, "utf8");

  assert.match(source, /"\/methodology\/technical"/);
  assert.match(source, /"\/methodology\/changelog"/);
  assert.match(source, /"\/career-fit"/);
  assert.match(source, /"\/careers"/);
  assert.match(source, /"\/research"/);
  assert.match(source, /CANONICAL_CAREER_FIELDS/);
  assert.match(source, /getAllResearchArticles/);
  assert.match(source, /getAllowlistedComparisons/);
  assert.doesNotMatch(source, /getOccupationEstimate/);
  assert.doesNotMatch(source, /\/transitions/);
});

test("News route preserves noindex, follow robots policy", () => {
  const newsPath = path.join(srcRoot, "app", "news", "page.tsx");
  const source = fs.readFileSync(newsPath, "utf8");

  assert.match(source, /index:\s*false/);
  assert.match(source, /follow:\s*true/);
});
