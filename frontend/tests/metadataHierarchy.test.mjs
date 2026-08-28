import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("Metadata Hierarchy - Root layout title template uses '%s | JobsVsAI'", () => {
  const layoutPath = path.join(srcRoot, "app", "layout.tsx");
  const layoutSource = fs.readFileSync(layoutPath, "utf8");

  assert.match(layoutSource, /template:\s*["']%s \| JobsVsAI["']/);
  assert.match(layoutSource, /default:\s*["']Will AI Take Your Job\? AI Job Risk & Career Analysis \| JobsVsAI["']/);
});

test("Metadata Hierarchy - No route source files contain duplicate brand suffixes", () => {
  const appDir = path.join(srcRoot, "app");
  function scanDir(dir) {
    const files = fs.readdirSync(dir);
    for (const f of files) {
      const fullPath = path.join(dir, f);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        scanDir(fullPath);
      } else if (f.endsWith(".tsx") || f.endsWith(".ts")) {
        const source = fs.readFileSync(fullPath, "utf8");
        assert.doesNotMatch(
          source,
          /JobsVsAI\s*—\s*JobsVsAI/,
          `File ${fullPath} contains duplicate brand suffix 'JobsVsAI — JobsVsAI'`
        );
        assert.doesNotMatch(
          source,
          /JobsVsAI\s*\|\s*JobsVsAI/,
          `File ${fullPath} contains duplicate brand suffix 'JobsVsAI | JobsVsAI'`
        );
      }
    }
  }
  scanDir(appDir);
});

test("Homepage Career Field cards link to canonical career field routes", () => {
  const homePath = path.join(srcRoot, "app", "page.tsx");
  const homeSource = fs.readFileSync(homePath, "utf8");

  assert.match(homeSource, /className="career-grid"/);
  assert.match(homeSource, /href=\{`\/careers\/\$\{field\.slug\}`\}/);
  assert.match(homeSource, /Explore AI job risk rankings →/);
  assert.match(homeSource, /href="\/rankings"/);
  assert.match(homeSource, /Occupation tasks assessed/);
});
