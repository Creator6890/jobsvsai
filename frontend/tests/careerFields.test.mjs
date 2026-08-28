import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CANONICAL_CAREER_FIELDS,
  getCanonicalFieldSlug,
  calculateFieldAnalytics,
} from "../src/lib/careerFields.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcRoot = path.resolve(__dirname, "..", "src");

test("Canonical Career Fields - exactly 19 coherent consumer fields defined with rich metadata", () => {
  const keys = Object.keys(CANONICAL_CAREER_FIELDS);
  assert.equal(keys.length, 19, "Must contain exactly 19 canonical fields");

  const expectedSlugs = [
    "business-finance",
    "technology-data",
    "office-administration",
    "healthcare",
    "science-research",
    "engineering",
    "education",
    "community-social-services",
    "legal",
    "management",
    "sales",
    "creative-media",
    "protective-services",
    "food-hospitality",
    "personal-care-services",
    "agriculture-environment",
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
  assert.equal(getCanonicalFieldSlug("paralegals-and-legal-assistants", "legal"), "legal");
  assert.equal(getCanonicalFieldSlug("aerospace-engineers", "engineering-architecture"), "engineering");
  assert.equal(getCanonicalFieldSlug("electricians", "installation-repair"), "skilled-trades");
  assert.equal(getCanonicalFieldSlug("airline-pilots", "transport-logistics"), "transportation");
  assert.equal(getCanonicalFieldSlug("chemical-equipment-operators", "manufacturing-production"), "production");

  // Specific 10 roles required by Architect audit:
  assert.equal(getCanonicalFieldSlug("data-scientists", "technology-data"), "technology-data");
  assert.equal(getCanonicalFieldSlug("software-developer", "technology-data"), "technology-data");
  assert.equal(getCanonicalFieldSlug("digital-interface-designers", "creative-media"), "creative-media");
  assert.equal(getCanonicalFieldSlug("technical-writers", "creative-media"), "creative-media");
  assert.equal(getCanonicalFieldSlug("project-management-specialists", "business-finance"), "business-finance");
  assert.equal(getCanonicalFieldSlug("sales-managers", "management-leadership"), "sales");
  assert.equal(getCanonicalFieldSlug("medical-and-health-services-managers", "management-leadership"), "healthcare");
  assert.equal(getCanonicalFieldSlug("architectural-and-engineering-managers", "management-leadership"), "engineering");
  assert.equal(getCanonicalFieldSlug("education-administrators-kindergarten-through-secondary", "management-leadership"), "education");
  assert.equal(getCanonicalFieldSlug("paralegals-and-legal-assistants", "legal"), "legal");

  // Additional category correctness roles:
  assert.equal(getCanonicalFieldSlug("child-family-and-school-social-workers", "community-social-services"), "community-social-services");
  assert.equal(getCanonicalFieldSlug("police-and-sheriffs-patrol-officers", "protective-services"), "protective-services");
  assert.equal(getCanonicalFieldSlug("physicists", "science-research"), "science-research");
  assert.equal(getCanonicalFieldSlug("chefs-and-head-cooks", "food-hospitality"), "food-hospitality");
  assert.equal(getCanonicalFieldSlug("agricultural-inspectors", "agriculture-environment"), "agriculture-environment");
  assert.equal(getCanonicalFieldSlug("hairdressers-hairstylists-and-cosmetologists", "personal-care-service"), "personal-care-services");
  assert.equal(getCanonicalFieldSlug("executive-secretaries-and-executive-administrative-assistants", "office-administration"), "office-administration");
  assert.equal(getCanonicalFieldSlug("data-entry-keyers", "office-administration"), "office-administration");
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

test("Career Fields Directory /careers page exists and has correct metadata", () => {
  const careersPagePath = path.join(srcRoot, "app", "careers", "page.tsx");
  assert.ok(fs.existsSync(careersPagePath), "/careers/page.tsx must exist");
  const source = fs.readFileSync(careersPagePath, "utf8");

  assert.match(source, /Explore careers by field/);
  assert.match(source, /canonical:\s*"https:\/\/jobsvsai\.com\/careers"/);
  assert.match(source, /calculateFieldAnalytics/);
});
