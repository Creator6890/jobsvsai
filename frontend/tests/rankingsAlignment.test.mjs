import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(__dirname, "..", "src");

test("Rankings table header and rows share structural column definitions and geometry", () => {
  const rankingsPath = path.join(srcRoot, "components", "RankingsExplorer.tsx");
  const rankingsContent = fs.readFileSync(rankingsPath, "utf8");

  // Header column classes
  assert.match(rankingsContent, /<span className="ranking-col-rank">#/);
  assert.match(rankingsContent, /<span className="ranking-col-title">Occupation<\/span>/);
  assert.match(rankingsContent, /<span className="ranking-col-cat">Category<\/span>/);
  assert.match(rankingsContent, /<span className="ranking-col-risk">Replacement Risk<\/span>/);
  assert.match(rankingsContent, /<span className="ranking-col-exp">AI Exposure<\/span>/);
  assert.match(rankingsContent, /<span className="ranking-col-action"><\/span>/);

  // Row column classes
  assert.match(rankingsContent, /ranking-col-rank/);
  assert.match(rankingsContent, /ranking-col-title/);
  assert.match(rankingsContent, /ranking-col-cat/);
  assert.match(rankingsContent, /ranking-col-risk/);
  assert.match(rankingsContent, /ranking-col-exp/);
  assert.match(rankingsContent, /ranking-col-action/);

  // Check both tables (highest and lowest) are rendered with identical structure
  const headerCount = (rankingsContent.match(/ranking-header/g) || []).length;
  assert.equal(headerCount, 2, "Both Highest and Lowest risk tables must have header rows");
});

test("CSS rules enforce shared grid columns and centered score metrics for rankings", () => {
  const cssPath = path.join(srcRoot, "app", "globals.css");
  const cssContent = fs.readFileSync(cssPath, "utf8");

  // Desktop grid template
  assert.match(cssContent, /\.ranking-row\s*\{[^}]*grid-template-columns:\s*44px/);

  // Score column centering
  assert.match(cssContent, /\.ranking-col-risk\s*\{[^}]*justify-content:\s*center/);
  assert.match(cssContent, /\.ranking-col-exp\s*\{[^}]*justify-content:\s*center/);

  // Responsive breakpoints
  assert.match(cssContent, /@media\s*\(max-width:\s*950px\)[^}]*\{[\s\S]*?\.ranking-row\s*\{[^}]*grid-template-columns:/);
  assert.match(cssContent, /@media\s*\(max-width:\s*680px\)[^}]*\{[\s\S]*?\.ranking-header\s+\.ranking-col-risk/);
  assert.match(cssContent, /@media\s*\(max-width:\s*680px\)[^}]*\{[\s\S]*?\.ranking-header\s+\.ranking-col-exp/);
});
