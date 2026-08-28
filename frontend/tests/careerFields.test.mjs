import test from "node:test";
import assert from "node:assert/strict";
import {
  CANONICAL_CAREER_FIELDS,
  getCanonicalFieldSlug,
  getCanonicalField,
  calculateFieldAnalytics,
} from "../src/lib/careerFields.ts";

test("Canonical Career Fields - exactly 12 fields defined with rich metadata", () => {
  const keys = Object.keys(CANONICAL_CAREER_FIELDS);
  assert.equal(keys.length, 12, "Must contain exactly 12 canonical fields");

  const expectedSlugs = [
    "business-finance",
    "technology-data",
    "healthcare",
    "creative-media",
    "education",
    "legal",
    "management",
    "sales",
    "engineering",
    "skilled-trades",
    "transportation",
    "production",
  ];

  for (const slug of expectedSlugs) {
    const field = CANONICAL_CAREER_FIELDS[slug];
    assert.ok(field, `Field ${slug} must exist`);
    assert.equal(field.slug, slug);
    assert.ok(field.name.length > 0, "Name must not be empty");
    assert.ok(field.tagline.length > 0, "Tagline must not be empty");
    assert.ok(field.overviewIntro.length > 0, "Overview intro must not be empty");
    assert.ok(field.structuralDrivers.length >= 2, "Must have at least 2 structural drivers");
    assert.ok(field.faqItems.length >= 3, "Must have at least 3 FAQ items");
  }
});

test("Career Field Slug Mapping - deterministic mapping for standard categories and overrides", () => {
  // Test category mappings
  assert.equal(getCanonicalFieldSlug("accountant", "business-finance"), "business-finance");
  assert.equal(getCanonicalFieldSlug("computer-programmers", "technology-data"), "technology-data");
  assert.equal(getCanonicalFieldSlug("acute-care-nurses", "healthcare"), "healthcare");
  assert.equal(getCanonicalFieldSlug("editors", "creative-media"), "creative-media");
  assert.equal(getCanonicalFieldSlug("adult-basic-education-instructors", "education-training"), "education");
  assert.equal(getCanonicalFieldSlug("paralegals", "legal"), "legal");
  assert.equal(getCanonicalFieldSlug("aerospace-engineers", "engineering-architecture"), "engineering");
  assert.equal(getCanonicalFieldSlug("electricians", "installation-repair"), "skilled-trades");
  assert.equal(getCanonicalFieldSlug("airline-pilots", "transport-logistics"), "transportation");
  assert.equal(getCanonicalFieldSlug("chemical-equipment-operators", "manufacturing-production"), "production");

  // Test individual overrides
  assert.equal(getCanonicalFieldSlug("sales-managers", "management-leadership"), "sales");
  assert.equal(getCanonicalFieldSlug("medical-and-health-services-managers", "management-leadership"), "healthcare");
  assert.equal(getCanonicalFieldSlug("architectural-and-engineering-managers", "management-leadership"), "engineering");
  assert.equal(getCanonicalFieldSlug("financial-managers", "management-leadership"), "business-finance");
});

test("calculateFieldAnalytics - computes accurate aggregates on verified occupations", () => {
  const sampleJobs = [
    { slug: "job-1", title: "Job 1", category: "business-finance", aiExposure: 80, replacementRisk: 70 },
    { slug: "job-2", title: "Job 2", category: "business-finance", aiExposure: 60, replacementRisk: 40 },
    { slug: "job-3", title: "Job 3", category: "business-finance", aiExposure: 40, replacementRisk: 20 },
    { slug: "tech-1", title: "Tech 1", category: "technology-data", aiExposure: 90, replacementRisk: 50 },
  ];

  const result = calculateFieldAnalytics("business-finance", sampleJobs);
  assert.equal(result.analytics.verifiedCount, 3);
  assert.equal(result.analytics.medianAiExposure, 60);
  assert.equal(result.analytics.medianReplacementRisk, 40);
  assert.equal(result.analytics.highestAiExposure.slug, "job-1");
  assert.equal(result.analytics.highestAiExposure.score, 80);
  assert.equal(result.analytics.highestReplacementRisk.slug, "job-1");
  assert.equal(result.analytics.highestReplacementRisk.score, 70);
  assert.equal(result.analytics.lowestReplacementRisk.slug, "job-3");
  assert.equal(result.analytics.lowestReplacementRisk.score, 20);
  assert.equal(result.analytics.riskDistribution.low, 1);
  assert.equal(result.analytics.riskDistribution.moderate, 1);
  assert.equal(result.analytics.riskDistribution.high, 1);
});

test("Career Field Breadcrumbs & Links - verified routes and destinations", () => {
  const accountantFieldSlug = getCanonicalFieldSlug("accountant", "business-finance");
  const field = getCanonicalField(accountantFieldSlug);
  assert.ok(field);
  assert.equal(field.slug, "business-finance");
  assert.equal(field.name, "Business & Finance");

  const techFieldSlug = getCanonicalFieldSlug("software-developer", "technology-data");
  const techField = getCanonicalField(techFieldSlug);
  assert.ok(techField);
  assert.equal(techField.slug, "technology-data");
  assert.equal(techField.name, "Technology & Data");
});

