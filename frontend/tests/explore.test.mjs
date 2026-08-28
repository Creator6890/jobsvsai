import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(__dirname, "..", "src");

test("Explore page source exists, exports metadata, visible FAQs without FAQPage schema", () => {
  const explorePagePath = path.join(srcRoot, "app", "explore", "page.tsx");
  assert.ok(fs.existsSync(explorePagePath), "frontend/src/app/explore/page.tsx must exist");

  const content = fs.readFileSync(explorePagePath, "utf8");

  // Metadata verification
  assert.match(content, /Explore AI Job Risk by Occupation \| JobsVsAI/);
  assert.match(content, /https:\/\/jobsvsai\.com\/explore/);

  // Invariant: FAQPage schema MUST BE ABSENT
  assert.doesNotMatch(content, /"@type":\s*"FAQPage"/, "FAQPage JSON-LD schema must be absent");
  assert.doesNotMatch(content, /FAQPage/, "FAQPage schema reference must be absent");

  // Breadcrumb verification
  assert.match(content, /name:\s*"Occupation Map"/);

  // Visible HTML content intact
  assert.match(content, /OccupationMapExplorer/);
  assert.match(content, /AI can do the work\. That does not always mean AI can take the job\./);
  assert.match(content, /Largest Exposure vs\. Risk Score Gaps/);
  assert.match(content, /Key occupational profiles across the map/);
});

test("OccupationMapExplorer component contains 2D SVG scatter map, Search V2 resolver, and robust hit targets", () => {
  const explorerPath = path.join(srcRoot, "components", "OccupationMapExplorer.tsx");
  assert.ok(fs.existsSync(explorerPath), "frontend/src/components/OccupationMapExplorer.tsx must exist");

  const content = fs.readFileSync(explorerPath, "utf8");

  // SVG and Chart Elements
  assert.match(content, /<svg/);
  assert.match(content, /AI Exposure \(0–100\)/);
  assert.match(content, /Replacement Risk \(0–100\)/);
  assert.match(content, /Parity \(Exposure = Risk\)/);
  assert.match(content, /HIGH EXPOSURE \/ ELEVATED RISK/);
  assert.match(content, /HIGH EXPOSURE \/ LOWER RISK/);
  assert.match(content, /LOWER EXPOSURE \/ HIGHER RISK/);
  assert.match(content, /LOW EXPOSURE \/ LOW RISK/);

  // Touch hit target & Search V2
  assert.match(content, /touch-hit-target/);
  assert.match(content, /\/api\/occupations\/search\/resolve/);
  assert.match(content, /currently has a Preliminary estimate and is not included in this Verified occupation map/);

  // Controls
  assert.match(content, /map-search-input/);
  assert.match(content, /All Fields/);
  assert.match(content, /All Risk/);
  assert.match(content, /All Exposure/);
  assert.match(content, /map-tooltip/);
  assert.match(content, /map-selected-card/);
  assert.match(content, /quadrant-guide-grid/);
});

test("Global navigation and sitemap integrate /explore route", () => {
  const exploreDropdownPath = path.join(srcRoot, "components", "ExploreDropdown.tsx");
  const exploreDropdownContent = fs.readFileSync(exploreDropdownPath, "utf8");
  assert.match(exploreDropdownContent, /href:\s*"\/explore"/);
  assert.match(exploreDropdownContent, /Occupation Map/);

  const siteHeaderPath = path.join(srcRoot, "components", "SiteHeader.tsx");
  const siteHeaderContent = fs.readFileSync(siteHeaderPath, "utf8");
  assert.match(siteHeaderContent, /href="\/explore"/);

  const siteFooterPath = path.join(srcRoot, "components", "SiteFooter.tsx");
  const siteFooterContent = fs.readFileSync(siteFooterPath, "utf8");
  assert.match(siteFooterContent, /href="\/explore"/);

  const sitemapPath = path.join(srcRoot, "app", "sitemap.ts");
  const sitemapContent = fs.readFileSync(sitemapPath, "utf8");
  assert.match(sitemapContent, /"\/explore"/);
});
