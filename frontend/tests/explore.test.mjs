import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(__dirname, "..", "src");

test("Explore page source exists, exports metadata, structured data, and intro guide", () => {
  const explorePagePath = path.join(srcRoot, "app", "explore", "page.tsx");
  assert.ok(fs.existsSync(explorePagePath), "frontend/src/app/explore/page.tsx must exist");

  const content = fs.readFileSync(explorePagePath, "utf8");

  // Metadata verification
  assert.match(content, /Explore AI Job Risk by Occupation \| JobsVsAI/);
  assert.match(content, /https:\/\/jobsvsai\.com\/explore/);
  assert.match(content, /FAQPage/);

  // Component integration
  assert.match(content, /OccupationMapExplorer/);
  assert.match(content, /AI can do the work\. That does not always mean AI can take the job\./);
  assert.match(content, /Largest Exposure vs\. Risk Gaps/);
  assert.match(content, /Key occupational profiles across the map/);
});

test("OccupationMapExplorer component contains 2D SVG scatter map, quadrants, search, and filters", () => {
  const explorerPath = path.join(srcRoot, "components", "OccupationMapExplorer.tsx");
  assert.ok(fs.existsSync(explorerPath), "frontend/src/components/OccupationMapExplorer.tsx must exist");

  const content = fs.readFileSync(explorerPath, "utf8");

  // SVG and Chart Elements
  assert.match(content, /<svg/);
  assert.match(content, /AI Exposure \(0–100\)/);
  assert.match(content, /Replacement Risk \(0–100\)/);
  assert.match(content, /Parity \(Risk = Exposure\)/);
  assert.match(content, /HIGH EXPOSURE \/ HIGH RISK/);
  assert.match(content, /HIGH EXPOSURE \/ HUMAN MOATS/);
  assert.match(content, /LOW EXPOSURE \/ LOW RISK/);

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
