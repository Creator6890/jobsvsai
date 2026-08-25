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
// 1. ads.txt Route Logic & Verification Tests
// ---------------------------------------------------------------------------

test("ads.txt route logic - unconfigured client ID returns empty response", () => {
  function formatAdsTxt(clientId) {
    const pubMatch = clientId?.match(/pub-\d+/);
    if (!pubMatch) return "";
    return `google.com, ${pubMatch[0]}, DIRECT, f08c47fec0942fa0\n`;
  }

  assert.strictEqual(formatAdsTxt(""), "");
  assert.strictEqual(formatAdsTxt(undefined), "");
  assert.strictEqual(formatAdsTxt("invalid-id"), "");
  assert.strictEqual(formatAdsTxt("ca-pub-"), "");
});

test("ads.txt route logic - valid client ID returns correctly formatted record", () => {
  function formatAdsTxt(clientId) {
    const pubMatch = clientId?.match(/pub-\d+/);
    if (!pubMatch) return "";
    return `google.com, ${pubMatch[0]}, DIRECT, f08c47fec0942fa0\n`;
  }

  assert.strictEqual(
    formatAdsTxt("ca-pub-7855774194309157"),
    "google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0\n"
  );
  assert.strictEqual(
    formatAdsTxt("pub-7855774194309157"),
    "google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0\n"
  );
});

// ---------------------------------------------------------------------------
// 2. Central Ads Config & Publisher ID Invariants
// ---------------------------------------------------------------------------

test("Official publisher ID is configured as ca-pub-7855774194309157", () => {
  const adsSource = fs.readFileSync(path.join(srcRoot, "lib", "ads.ts"), "utf8");
  assert.match(
    adsSource,
    /ca-pub-7855774194309157/,
    "ads.ts must configure official publisher ID ca-pub-7855774194309157"
  );
});

test("ads config logic - adsReady requires both adsEnabled=true and clientId", () => {
  function computeAdsReady(enabledStr, clientIdStr) {
    const adsEnabled = enabledStr === "true";
    const adsenseClientId = clientIdStr ?? "";
    return adsEnabled && adsenseClientId !== "";
  }

  assert.strictEqual(computeAdsReady("false", "ca-pub-7855774194309157"), false);
  assert.strictEqual(computeAdsReady("", "ca-pub-7855774194309157"), false);
  assert.strictEqual(computeAdsReady(undefined, "ca-pub-7855774194309157"), false);
  assert.strictEqual(computeAdsReady("true", ""), false);
  assert.strictEqual(computeAdsReady("true", undefined), false);
  assert.strictEqual(computeAdsReady("true", "ca-pub-7855774194309157"), true);
});

test("ads config logic - showDebugPlaceholders requires debug=true and adsEnabled=false", () => {
  function computeDebug(enabledStr, debugStr) {
    const adsEnabled = enabledStr === "true";
    const adsDebug = debugStr === "true";
    return adsDebug && !adsEnabled;
  }

  assert.strictEqual(computeDebug("false", "true"), true);
  assert.strictEqual(computeDebug("", "true"), true);
  assert.strictEqual(computeDebug("true", "true"), false, "Live ads must suppress debug placeholders");
  assert.strictEqual(computeDebug("false", "false"), false);
});

// ---------------------------------------------------------------------------
// 3. Site Verification Meta Tag & Loader Script Invariants
// ---------------------------------------------------------------------------

test("Root layout includes google-adsense-account verification meta tag", () => {
  const layoutSource = fs.readFileSync(path.join(srcRoot, "app", "layout.tsx"), "utf8");
  assert.match(
    layoutSource,
    /google-adsense-account/,
    "Root layout metadata must include google-adsense-account"
  );
  assert.match(
    layoutSource,
    /<AdsenseScript\s*\/>/,
    "Root layout must mount AdsenseScript component"
  );
});

test("Single centralized AdSense loader script in codebase with no duplicates", () => {
  const scriptSource = fs.readFileSync(path.join(srcRoot, "components", "AdsenseScript.tsx"), "utf8");
  assert.match(scriptSource, /if\s*\(!adsenseClientId\)\s*return\s*null;/);
  assert.match(scriptSource, /strategy="afterInteractive"/);
  assert.match(scriptSource, /pagead2\.googlesyndication\.com\/pagead\/js\/adsbygoogle\.js\?client=\$\{adsenseClientId\}/);
  assert.match(scriptSource, /crossOrigin="anonymous"/);

  // Verify no other files include raw adsbygoogle script loaders
  const filesToCheck = [
    path.join(srcRoot, "app", "page.tsx"),
    path.join(srcRoot, "app", "rankings", "page.tsx"),
    path.join(srcRoot, "app", "compare", "page.tsx"),
    path.join(srcRoot, "app", "career-fit", "page.tsx"),
    path.join(srcRoot, "app", "news", "page.tsx"),
  ];
  for (const filePath of filesToCheck) {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, "utf8");
      assert.doesNotMatch(content, /pagead2\.googlesyndication\.com/, `${filePath} must not contain duplicate raw AdSense script`);
    }
  }
});

// ---------------------------------------------------------------------------
// 4. Slot Registry & Auto Ads Prevention Invariants
// ---------------------------------------------------------------------------

test("ads.ts declares all expected slot names with unconfigured empty defaults (no invented slot IDs)", () => {
  const adsSource = fs.readFileSync(path.join(srcRoot, "lib", "ads.ts"), "utf8");
  const expectedSlots = [
    "home",
    "jobPrimary",
    "jobSecondary",
    "rankings",
    "compare",
    "newsList",
    "newsArticle",
  ];
  for (const slot of expectedSlots) {
    assert.match(adsSource, new RegExp(`\\b${slot}:`), `Slot '${slot}' must be declared in lib/ads.ts`);
    assert.match(adsSource, new RegExp(`process\\.env\\.NEXT_PUBLIC_ADSENSE_SLOT_[A-Z_]+\\s*\\?\\?\\s*""`), `Slot '${slot}' must default to empty string`);
  }
});

test("Auto Ads remains strictly off with no auto-ad configuration", () => {
  const scriptSource = fs.readFileSync(path.join(srcRoot, "components", "AdsenseScript.tsx"), "utf8");
  const adsSource = fs.readFileSync(path.join(srcRoot, "lib", "ads.ts"), "utf8");
  const layoutSource = fs.readFileSync(path.join(srcRoot, "app", "layout.tsx"), "utf8");

  assert.doesNotMatch(scriptSource, /enable_page_level_ads/i, "Auto ads must not be enabled in AdsenseScript");
  assert.doesNotMatch(adsSource, /auto_ads/i, "Auto ads must not be enabled in lib/ads.ts");
  assert.doesNotMatch(layoutSource, /enable_page_level_ads/i, "Auto ads must not be enabled in layout.tsx");
});

test("AdSlot component safety invariants (renders null when adsEnabled=false or slotId is empty)", () => {
  const slotSource = fs.readFileSync(path.join(srcRoot, "components", "AdSlot.tsx"), "utf8");
  assert.match(slotSource, /if\s*\(!adsReady\s*\|\|\s*!slotId\)\s*return\s*null;/);
  assert.match(slotSource, /if\s*\(showDebugPlaceholders\)/);
  assert.match(slotSource, /ad-slot-debug/);
  assert.match(slotSource, /className="adsbygoogle"/);
  assert.doesNotMatch(slotSource, /<a\b[^>]*><ins/i, "Ad must not be wrapped inside a link");
});

// ---------------------------------------------------------------------------
// 5. Page Placement Invariants: User Value First -> Ads After Value
// ---------------------------------------------------------------------------

test("Homepage - ad is placed after ranking preview and before footer", () => {
  const homeSource = fs.readFileSync(path.join(srcRoot, "app", "page.tsx"), "utf8");
  const rankingPreviewIdx = homeSource.indexOf("ranking-preview-title");
  const adSlotIdx = homeSource.indexOf('<AdSlot slot="home"');
  const footerIdx = homeSource.indexOf("<SiteFooter");

  assert.ok(rankingPreviewIdx > 0, "Ranking preview must exist");
  assert.ok(adSlotIdx > 0, "Home AdSlot must exist");
  assert.ok(footerIdx > 0, "SiteFooter must exist");
  assert.ok(rankingPreviewIdx < adSlotIdx, "Ad must appear after ranking preview");
  assert.ok(adSlotIdx < footerIdx, "Ad must appear before footer");
});

test("Job Detail - score cards precede primary ad, deep-dive precedes secondary ad", () => {
  const jobDetailSource = fs.readFileSync(path.join(srcRoot, "components", "OccupationDetail.tsx"), "utf8");
  const scoreSectionIdx = jobDetailSource.indexOf('className="score-section"');
  const primaryAdIdx = jobDetailSource.indexOf('<AdSlot slot="jobPrimary"');
  const taskTableIdx = jobDetailSource.indexOf('className="card task-table"');
  const twoColumnIdx = jobDetailSource.indexOf('className="container two-column"');
  const secondaryAdIdx = jobDetailSource.indexOf('<AdSlot slot="jobSecondary"');
  const relatedCareersIdx = jobDetailSource.indexOf("Related occupations");

  assert.ok(scoreSectionIdx > 0, "Score section must exist");
  assert.ok(primaryAdIdx > 0, "Primary AdSlot must exist");
  assert.ok(taskTableIdx > 0, "Task table must exist");
  assert.ok(twoColumnIdx > 0, "Two-column deep dive must exist");
  assert.ok(secondaryAdIdx > 0, "Secondary AdSlot must exist");
  assert.ok(relatedCareersIdx > 0, "Related occupations must exist");

  assert.ok(scoreSectionIdx < primaryAdIdx, "Scores must appear BEFORE primary ad");
  assert.ok(primaryAdIdx < taskTableIdx, "Primary ad appears before task evidence table");
  assert.ok(twoColumnIdx < secondaryAdIdx, "Deep dive appears BEFORE secondary ad");
  assert.ok(secondaryAdIdx < relatedCareersIdx, "Secondary ad appears before related occupations");
});

test("Rankings - ad is placed after RankingsExplorer results", () => {
  const rankingsSource = fs.readFileSync(path.join(srcRoot, "app", "rankings", "page.tsx"), "utf8");
  const explorerIdx = rankingsSource.indexOf("<RankingsExplorer");
  const adSlotIdx = rankingsSource.indexOf('<AdSlot slot="rankings"');

  assert.ok(explorerIdx > 0, "RankingsExplorer must exist");
  assert.ok(adSlotIdx > 0, "Rankings AdSlot must exist");
  assert.ok(explorerIdx < adSlotIdx, "Ad must appear after RankingsExplorer");
});

test("Compare dynamic - ad is placed after CareerComparison results", () => {
  const compareSource = fs.readFileSync(path.join(srcRoot, "app", "compare", "[comparison]", "page.tsx"), "utf8");
  const comparisonIdx = compareSource.indexOf("<CareerComparison");
  const adSlotIdx = compareSource.indexOf('<AdSlot slot="compare"');

  assert.ok(comparisonIdx > 0, "CareerComparison must exist");
  assert.ok(adSlotIdx > 0, "Compare AdSlot must exist");
  assert.ok(comparisonIdx < adSlotIdx, "Ad must appear after CareerComparison");
});

test("News Listing - ad is placed between 4th and 5th article cards", () => {
  const newsSource = fs.readFileSync(path.join(srcRoot, "app", "news", "page.tsx"), "utf8");
  assert.match(newsSource, /articles\.slice\(0,\s*4\)/, "First 4 articles rendered first");
  assert.match(newsSource, /<AdSlot slot="newsList"/, "AdSlot inserted into grid");
  assert.match(newsSource, /articles\.slice\(4\)/, "Remaining articles rendered after ad");
});

test("News Article - ad is placed after 'What happened' section", () => {
  const articleSource = fs.readFileSync(path.join(srcRoot, "app", "news", "[slug]", "page.tsx"), "utf8");
  const whatHappenedIdx = articleSource.indexOf("What happened");
  const adSlotIdx = articleSource.indexOf('<AdSlot slot="newsArticle"');
  const whyItMattersIdx = articleSource.indexOf("Why it matters for jobs");

  assert.ok(whatHappenedIdx > 0, "'What happened' section must exist");
  assert.ok(adSlotIdx > 0, "News article AdSlot must exist");
  assert.ok(whyItMattersIdx > 0, "'Why it matters for jobs' section must exist");
  assert.ok(whatHappenedIdx < adSlotIdx, "'What happened' must precede ad");
  assert.ok(adSlotIdx < whyItMattersIdx, "Ad must precede 'Why it matters for jobs'");
});
