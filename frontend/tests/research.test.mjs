import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  getResearchArticle,
  getAllResearchArticles,
} from "../src/lib/researchArticles.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

test("Research Articles - contains 5 foundational evidence-grounded articles", () => {
  const articles = getAllResearchArticles();
  assert.equal(articles.length, 5, "Must contain exactly 5 foundational articles");

  const expectedSlugs = [
    "ai-exposure-vs-replacement-risk",
    "why-ai-automates-tasks-before-whole-jobs",
    "which-jobs-are-most-at-risk-from-ai",
    "which-jobs-are-safest-from-ai",
    "what-to-do-if-your-job-has-high-ai-risk",
  ];

  for (const slug of expectedSlugs) {
    const article = getResearchArticle(slug);
    assert.ok(article, `Article ${slug} must exist`);
    assert.equal(article.slug, slug);
    assert.equal(article.datePublished, "2026-08-28T00:00:00Z");
    assert.equal(article.dateModified, "2026-08-28T00:00:00Z");
    assert.ok(article.title.length > 0, "Title must not be empty");
    assert.ok(article.headline.length > 0, "Headline must not be empty");
    assert.ok(article.seoTitle.length > 0, "SeoTitle must not be empty");
    assert.ok(article.description.length > 0, "Description must not be empty");
    assert.ok(article.shortAnswer.length > 0, "Short answer must not be empty");
    assert.ok(article.evidenceSection.paragraphs.length >= 2, "Must have at least 2 evidence paragraphs");
    assert.ok(article.mechanismSection.paragraphs.length >= 1, "Must have mechanism paragraphs");
    assert.ok(article.affectedCareersSection.sampleOccupations.length >= 3, "Must have at least 3 sample occupations");
    assert.ok(article.workerImpactSection.paragraphs.length >= 1, "Must have worker impact paragraphs");
    assert.ok(article.limitationsSection.paragraphs.length >= 1, "Must have limitations paragraphs");
  }
});

test("Research Article Template - Structured data and layout integrity", () => {
  const articleTemplatePath = path.join(srcRoot, "app", "research", "[slug]", "page.tsx");
  const templateSource = fs.readFileSync(articleTemplatePath, "utf8");

  assert.match(templateSource, /["']@type["']:\s*["']Article["']/, "Must declare Article schema");
  assert.match(templateSource, /author:\s*\{\s*["']@type["']:\s*["']Organization["']/, "Must declare Organization author");
  assert.match(templateSource, /publisher:\s*\{\s*["']@type["']:\s*["']Organization["']/, "Must declare Organization publisher");
  assert.doesNotMatch(templateSource, /JobPosting/, "Must never include JobPosting schema");
});

test("Research Hub - Page structure and clusters exist", () => {
  const hubPath = path.join(srcRoot, "app", "research", "page.tsx");
  const hubSource = fs.readFileSync(hubPath, "utf8");

  assert.match(hubSource, /AI & Jobs Research/);
  assert.match(hubSource, /UNDERSTANDING AI RISK/);
  assert.match(hubSource, /OCCUPATIONAL RESILIENCE/);
  assert.match(hubSource, /CAREER DECISIONS/);
  assert.match(hubSource, /getAllResearchArticles/);
});
