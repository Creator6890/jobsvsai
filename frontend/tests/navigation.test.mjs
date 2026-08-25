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
// 1. Desktop Primary Navigation Invariants
// ---------------------------------------------------------------------------

test("Desktop primary nav contains Rankings, Career Tools dropdown, News, About and excludes Home and Methodology", () => {
  const headerPath = path.join(srcRoot, "components", "SiteHeader.tsx");
  assert.ok(fs.existsSync(headerPath), "SiteHeader.tsx must exist");
  const headerContent = fs.readFileSync(headerPath, "utf8");

  // Home link must NOT be present in primary nav (Logo handles '/')
  assert.ok(!headerContent.includes('["Home", "/"]'), "Header must NOT contain an explicit Home link");
  assert.ok(!headerContent.includes('<Link href="/">Home</Link>'), "Header must NOT contain an explicit Home link");

  // Methodology must NOT be present in header navigation
  assert.ok(!headerContent.includes('href="/methodology"'), "Methodology must NOT be in header primary navigation");

  // Desktop nav must render Rankings, CareerToolsDropdown, News, About
  assert.ok(headerContent.includes('<Link href="/rankings">Rankings</Link>'), "Desktop nav must include Rankings link");
  assert.ok(headerContent.includes("<CareerToolsDropdown />"), "Desktop nav must include CareerToolsDropdown");
  assert.ok(headerContent.includes('<Link href="/news">News</Link>'), "Desktop nav must include News link");
  assert.ok(headerContent.includes('<Link href="/about">About</Link>'), "Desktop nav must include About link");
});

// ---------------------------------------------------------------------------
// 2. Career Tools Dropdown Invariants
// ---------------------------------------------------------------------------

test("CareerToolsDropdown contains Career Fit and Compare Careers destinations with descriptions", () => {
  const dropdownPath = path.join(srcRoot, "components", "CareerToolsDropdown.tsx");
  assert.ok(fs.existsSync(dropdownPath), "CareerToolsDropdown.tsx must exist");
  const dropdownContent = fs.readFileSync(dropdownPath, "utf8");

  // Accessible button with aria attributes
  assert.ok(dropdownContent.includes("Career Tools"), "Dropdown must have Career Tools label");
  assert.ok(dropdownContent.includes('aria-haspopup="true"'), "Dropdown button must declare aria-haspopup");
  assert.ok(dropdownContent.includes("aria-expanded"), "Dropdown button must declare aria-expanded");

  // Career Fit destination
  assert.ok(dropdownContent.includes('href="/career-fit"'), "Dropdown must link to /career-fit");
  assert.ok(dropdownContent.includes("Find careers aligned with your work preferences and strengths."), "Career Fit description must match specification");

  // Compare Careers destination
  assert.ok(dropdownContent.includes('href="/compare"'), "Dropdown must link to /compare");
  assert.ok(dropdownContent.includes("Compare AI Exposure and Replacement Risk side by side."), "Compare description must match specification");

  // Keyboard navigation & a11y
  assert.ok(dropdownContent.includes('"Escape"'), "Dropdown must handle Escape key");
});

// ---------------------------------------------------------------------------
// 3. Mobile Navigation Invariants (Aligned with Desktop Hierarchy)
// ---------------------------------------------------------------------------

test("Mobile navigation contains Rankings, Career Tools (Career Fit + Compare), News, and About", () => {
  const headerContent = fs.readFileSync(path.join(srcRoot, "components", "SiteHeader.tsx"), "utf8");

  assert.ok(headerContent.includes('className="mobile-menu"'), "Mobile menu must be present");
  assert.ok(headerContent.includes('href="/rankings"'), "Mobile menu must contain Rankings");
  assert.ok(headerContent.includes('href="/career-fit"'), "Mobile menu must contain Career Fit");
  assert.ok(headerContent.includes('href="/compare"'), "Mobile menu must contain Compare Careers");
  assert.ok(headerContent.includes('href="/news"'), "Mobile menu must contain News");
  assert.ok(headerContent.includes('href="/about"'), "Mobile menu must contain About");

  // Methodology is not in mobile primary nav
  assert.ok(!headerContent.includes('href="/methodology"'), "Mobile navigation must NOT contain Methodology as a primary link");
});

// ---------------------------------------------------------------------------
// 4. Footer Invariants (Trust & Full Discovery)
// ---------------------------------------------------------------------------

test("Footer contains Rankings, Career Fit, Compare, News, Methodology, and About", () => {
  const footerContent = fs.readFileSync(path.join(srcRoot, "components", "SiteFooter.tsx"), "utf8");

  assert.ok(footerContent.includes('href="/rankings"'), "Footer must contain Rankings");
  assert.ok(footerContent.includes('href="/career-fit"'), "Footer must contain Career Fit");
  assert.ok(footerContent.includes('href="/compare"'), "Footer must contain Compare");
  assert.ok(footerContent.includes('href="/news"'), "Footer must contain News");
  assert.ok(footerContent.includes('href="/methodology"'), "Footer must contain Methodology");
  assert.ok(footerContent.includes('href="/about"'), "Footer must contain About");
});

// ---------------------------------------------------------------------------
// 5. Homepage Search Handoff Invariants
// ---------------------------------------------------------------------------

test("Homepage search result renders original result first and Career Fit continuation CTA second", () => {
  const searchContent = fs.readFileSync(path.join(srcRoot, "components", "OccupationSearch.tsx"), "utf8");

  // Result card renders original occupation analysis CTA
  assert.ok(searchContent.includes("See the full analysis"), "Search result must contain primary analysis link");

  // Continuation handoff block
  assert.ok(searchContent.includes("search-career-fit-handoff"), "Search result must contain handoff container");
  assert.ok(searchContent.includes("Thinking about other options?"), "Handoff must contain 'Thinking about other options?'");
  assert.ok(searchContent.includes("Find careers that align with your strengths and work preferences."), "Handoff copy must match specification");
  assert.ok(searchContent.includes("Find My Career Fit"), "Handoff must contain 'Find My Career Fit' button");
  assert.ok(searchContent.includes("Takes about 3 minutes"), "Handoff must contain 'Takes about 3 minutes'");
  assert.ok(searchContent.includes('href="/career-fit?from=homepage_search"'), "Handoff link must pass from=homepage_search");
});

// ---------------------------------------------------------------------------
// 6. Rankings Page Simplification Invariants (Editorial Top-10)
// ---------------------------------------------------------------------------

test("Rankings page renders Top 10 Highest and Lowest Replacement Risk with factual copy", () => {
  const rankingsContent = fs.readFileSync(path.join(srcRoot, "components", "RankingsExplorer.tsx"), "utf8");

  // Top 10 sections
  assert.ok(rankingsContent.includes("Highest Replacement Risk"), "Must include 'Highest Replacement Risk' section");
  assert.ok(rankingsContent.includes("Lowest Replacement Risk"), "Must include 'Lowest Replacement Risk' section");
  assert.ok(rankingsContent.includes("Careers currently showing the highest estimated replacement risk"), "Must include approved subtitle");
  assert.ok(rankingsContent.includes("Careers currently showing comparatively lower estimated replacement risk"), "Must include approved subtitle");

  // Top 10 slicing
  assert.ok(rankingsContent.includes(".slice(0, 10)"), "Must slice to top 10 items");

  // Banned sensational words check
  const lower = rankingsContent.toLowerCase();
  assert.ok(!lower.includes("ai-proof"), "Must not use 'ai-proof'");
  assert.ok(!lower.includes("safe jobs"), "Must not use 'safe jobs'");
  assert.ok(!lower.includes("doomed jobs"), "Must not use 'doomed jobs'");
  assert.ok(!lower.includes("worst jobs"), "Must not use 'worst jobs'");
});
