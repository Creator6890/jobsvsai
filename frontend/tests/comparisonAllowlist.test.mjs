import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  isComparisonAllowlisted,
  getAllowlistedComparisons,
} from "../src/lib/comparisonAllowlist.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("Comparison Allowlist - exactly <= 10 high-value comparisons defined", () => {
  const allowlist = getAllowlistedComparisons();
  assert.ok(allowlist.length > 0 && allowlist.length <= 10, "Must contain at most 10 allowlisted comparisons");
  assert.equal(allowlist.length, 10, "Contains exactly 10 curated comparisons");

  for (const comp of allowlist) {
    assert.ok(comp.slug.includes("-vs-"), "Slug must follow [a]-vs-[b] pattern");
    assert.ok(comp.aSlug.length > 0, "aSlug must be defined");
    assert.ok(comp.bSlug.length > 0, "bSlug must be defined");
    assert.equal(isComparisonAllowlisted(comp.slug), true);
  }
});

test("Comparison Allowlist - non-allowlisted comparisons are rejected", () => {
  assert.equal(isComparisonAllowlisted("random-job-vs-another-job"), false);
  assert.equal(isComparisonAllowlisted("accountant-vs-software-engineer"), false);
});

test("Compare Page Template - Enforces robots noindex on non-allowlisted comparisons", () => {
  const comparePagePath = path.join(srcRoot, "app", "compare", "[comparison]", "page.tsx");
  const compareSource = fs.readFileSync(comparePagePath, "utf8");

  assert.match(compareSource, /isComparisonAllowlisted\(comparison\)/);
  assert.match(compareSource, /robots:\s*isAllowlisted\s*\?\s*\{\s*index:\s*true,\s*follow:\s*true\s*\}\s*:\s*\{\s*index:\s*false,\s*follow:\s*true\s*\}/);
});
