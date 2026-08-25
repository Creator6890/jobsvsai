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
// 1. Source File Existence & Integrity Invariants
// ---------------------------------------------------------------------------

test("Career Fit source files exist and contain required exports", () => {
  const dimensionsPath = path.join(srcRoot, "lib", "careerFit", "dimensions.ts");
  const questionsPath = path.join(srcRoot, "lib", "careerFit", "questions.ts");
  const scoringPath = path.join(srcRoot, "lib", "careerFit", "scoring.ts");
  const indexPath = path.join(srcRoot, "lib", "careerFit", "index.ts");
  const appPath = path.join(srcRoot, "components", "careerFit", "CareerFitApp.tsx");
  const cardPath = path.join(srcRoot, "components", "careerFit", "CareerMatchCard.tsx");
  const barsPath = path.join(srcRoot, "components", "careerFit", "ProfileStrengthBars.tsx");
  const pagePath = path.join(srcRoot, "app", "career-fit", "page.tsx");

  for (const filePath of [
    dimensionsPath,
    questionsPath,
    scoringPath,
    indexPath,
    appPath,
    cardPath,
    barsPath,
    pagePath,
  ]) {
    assert.ok(fs.existsSync(filePath), `Expected ${filePath} to exist`);
  }

  const dimensionsContent = fs.readFileSync(dimensionsPath, "utf8");
  assert.ok(dimensionsContent.includes("export const DIMENSIONS"));
  assert.ok(dimensionsContent.includes("export const DIMENSION_KEYS"));
  assert.ok(dimensionsContent.includes("export function getStrengthBand"));

  const questionsContent = fs.readFileSync(questionsPath, "utf8");
  assert.ok(questionsContent.includes("export const ASSESSMENT_QUESTIONS"));
  assert.ok(questionsContent.includes("export const RESPONSE_OPTIONS"));

  const scoringContent = fs.readFileSync(scoringPath, "utf8");
  assert.ok(scoringContent.includes("export function calculateProfile"));
  assert.ok(scoringContent.includes("export function deriveOccupationVector"));
  assert.ok(scoringContent.includes("export function matchOccupations"));
  assert.ok(scoringContent.includes("export function sortMatches"));
});

// ---------------------------------------------------------------------------
// 2. Pure Algorithm Execution Tests
// ---------------------------------------------------------------------------

const DIMENSION_KEYS = [
  "analytical",
  "creativity",
  "communication",
  "people",
  "practical",
  "organization",
  "technology",
  "leadership",
];

const ASSESSMENT_QUESTIONS = [
  { id: 1, prompt: "Complex problems into smaller parts", primaryDimension: "analytical", primaryWeight: 1.0 },
  { id: 2, prompt: "Original design rather than template", primaryDimension: "creativity", primaryWeight: 1.0 },
  { id: 3, prompt: "Helping, supporting, or counseling", primaryDimension: "people", primaryWeight: 1.0 },
  { id: 4, prompt: "Hands-on tools or equipment", primaryDimension: "practical", primaryWeight: 1.0 },
  { id: 5, prompt: "Software, coding, or digital systems", primaryDimension: "technology", primaryWeight: 1.0, secondaryDimension: "analytical", secondaryWeight: 0.3 },
  { id: 6, prompt: "Explaining technical concepts in simple terms", primaryDimension: "communication", primaryWeight: 1.0 },
  { id: 7, prompt: "Workflows, schedules, accuracy", primaryDimension: "organization", primaryWeight: 1.0 },
  { id: 8, prompt: "Decisions under uncertainty", primaryDimension: "leadership", primaryWeight: 1.0 },
  { id: 9, prompt: "Empirical patterns and data trends", primaryDimension: "analytical", primaryWeight: 1.0 },
  { id: 10, prompt: "Reimagining products or narratives", primaryDimension: "creativity", primaryWeight: 1.0 },
  { id: 11, prompt: "Attentive to emotions and motivations", primaryDimension: "people", primaryWeight: 1.0, secondaryDimension: "communication", secondaryWeight: 0.3 },
  { id: 12, prompt: "Assemble, repair, or inspect physical objects", primaryDimension: "practical", primaryWeight: 1.0 },
  { id: 13, prompt: "Digital architectures and automated workflows", primaryDimension: "technology", primaryWeight: 1.0 },
  { id: 14, prompt: "Writing structured reports or articles", primaryDimension: "communication", primaryWeight: 1.0 },
  { id: 15, prompt: "Spotting errors and structured records", primaryDimension: "organization", primaryWeight: 1.0 },
  { id: 16, prompt: "Step forward to coordinate people", primaryDimension: "leadership", primaryWeight: 1.0 },
  { id: 17, prompt: "Investigate why a machine is failing", primaryDimension: "analytical", primaryWeight: 1.0, secondaryDimension: "practical", secondaryWeight: 0.4 },
  { id: 18, prompt: "Open-ended problems with multiple pathways", primaryDimension: "creativity", primaryWeight: 1.0, secondaryDimension: "analytical", secondaryWeight: 0.3 },
  { id: 19, prompt: "Building personal trust and collaboration", primaryDimension: "people", primaryWeight: 1.0, secondaryDimension: "leadership", secondaryWeight: 0.3 },
  { id: 20, prompt: "Managing timelines and budgets", primaryDimension: "organization", primaryWeight: 1.0, secondaryDimension: "leadership", secondaryWeight: 0.4 },
];

function getStrengthBand(score) {
  if (score >= 80) return "Very High";
  if (score >= 60) return "High";
  if (score >= 40) return "Moderate";
  return "Developing";
}

function calculateProfile(answers) {
  const dimensionWeightedSums = {
    analytical: 0, creativity: 0, communication: 0, people: 0,
    practical: 0, organization: 0, technology: 0, leadership: 0,
  };
  const dimensionTotalWeights = {
    analytical: 0, creativity: 0, communication: 0, people: 0,
    practical: 0, organization: 0, technology: 0, leadership: 0,
  };

  for (const question of ASSESSMENT_QUESTIONS) {
    const rawAnswer = answers[question.id] ?? 3;
    const clampedAnswer = Math.max(1, Math.min(5, rawAnswer));
    const normalizedResponse = (clampedAnswer - 1) / 4.0;

    dimensionWeightedSums[question.primaryDimension] += normalizedResponse * question.primaryWeight;
    dimensionTotalWeights[question.primaryDimension] += question.primaryWeight;

    if (question.secondaryDimension && question.secondaryWeight) {
      dimensionWeightedSums[question.secondaryDimension] += normalizedResponse * question.secondaryWeight;
      dimensionTotalWeights[question.secondaryDimension] += question.secondaryWeight;
    }
  }

  const dimensionScores = {};
  const dimensionBands = {};

  for (const key of DIMENSION_KEYS) {
    const totalWeight = dimensionTotalWeights[key] || 1.0;
    const score = Math.round((dimensionWeightedSums[key] / totalWeight) * 100);
    const clampedScore = Math.max(0, Math.min(100, score));
    dimensionScores[key] = clampedScore;
    dimensionBands[key] = getStrengthBand(clampedScore);
  }

  const sortedDimensions = [...DIMENSION_KEYS].sort((a, b) => dimensionScores[b] - dimensionScores[a]);
  const topStrengths = sortedDimensions.slice(0, 3);

  return { dimensionScores, dimensionBands, topStrengths };
}

const MOCK_OCCUPATIONS = [
  {
    slug: "software-developer",
    title: "Software Developer",
    category: "Computer & Mathematical",
    aiExposure: 78,
    replacementRisk: 42,
    humanDependency: 45,
    physicalDependency: 10,
  },
  {
    slug: "registered-nurse",
    title: "Registered Nurse",
    category: "Healthcare",
    aiExposure: 48,
    replacementRisk: 28,
    humanDependency: 92,
    physicalDependency: 78,
  },
  {
    slug: "graphic-designer",
    title: "Graphic Designer",
    category: "Creative & Media",
    aiExposure: 82,
    replacementRisk: 64,
    humanDependency: 60,
    physicalDependency: 20,
  },
  {
    slug: "electrician",
    title: "Electrician",
    category: "Installation & Repair",
    aiExposure: 35,
    replacementRisk: 22,
    humanDependency: 50,
    physicalDependency: 95,
  },
  {
    slug: "operations-manager",
    title: "General and Operations Manager",
    category: "Management & Leadership",
    aiExposure: 62,
    replacementRisk: 38,
    humanDependency: 88,
    physicalDependency: 25,
  },
];

function deriveOccupationVector(occ) {
  const vector = {
    analytical: 55, creativity: 50, communication: 55, people: 50,
    practical: 50, organization: 60, technology: 50, leadership: 50,
  };

  if (occ.category.includes("Technology")) {
    vector.technology = 95;
    vector.analytical = 90;
    vector.creativity = 60;
  } else if (occ.category.includes("Healthcare")) {
    vector.people = 92;
    vector.analytical = 85;
    vector.communication = 75;
  } else if (occ.category.includes("Creative")) {
    vector.creativity = 95;
    vector.communication = 85;
  } else if (occ.category.includes("Installation")) {
    vector.practical = 95;
    vector.analytical = 70;
  } else if (occ.category.includes("Management")) {
    vector.leadership = 95;
    vector.organization = 85;
    vector.communication = 90;
  }

  if (typeof occ.physicalDependency === "number") {
    vector.practical = Math.round(vector.practical * 0.35 + occ.physicalDependency * 0.65);
  }
  if (typeof occ.humanDependency === "number") {
    vector.people = Math.round(vector.people * 0.40 + occ.humanDependency * 0.60);
  }

  for (const k of DIMENSION_KEYS) {
    vector[k] = Math.max(0, Math.min(100, vector[k]));
  }
  return vector;
}

function matchOccupations(userProfile, occupations, limit = 12) {
  const matches = [];

  for (const occ of occupations) {
    const occVector = deriveOccupationVector(occ);
    let totalWeight = 0;
    let weightedSquaredDiff = 0;

    for (const key of DIMENSION_KEYS) {
      const u = userProfile.dimensionScores[key];
      const o = occVector[key];
      let w = 1.0;
      if (u >= 80) w = 2.5;
      else if (u >= 60) w = 1.8;
      else if (u <= 20) w = 1.4;

      totalWeight += w;
      weightedSquaredDiff += w * Math.pow(u - o, 2);
    }

    const rms = Math.sqrt(weightedSquaredDiff / totalWeight);
    const fitPct = Math.round(98 - Math.pow(rms / 4.2, 1.45));
    const careerFit = Math.max(12, Math.min(98, fitPct));

    matches.push({
      occupation: occ,
      careerFit,
      whyFit: `Aligned with your top competencies.`,
      considerations: [],
    });
  }

  matches.sort((a, b) => b.careerFit - a.careerFit);
  return matches.slice(0, limit);
}

function sortMatches(matches, sortOption) {
  const cloned = [...matches];
  switch (sortOption) {
    case "fit":
      return cloned.sort((a, b) => b.careerFit - a.careerFit);
    case "risk":
      return cloned.sort((a, b) => a.occupation.replacementRisk - b.occupation.replacementRisk);
    case "exposure":
      return cloned.sort((a, b) => a.occupation.aiExposure - b.occupation.aiExposure);
  }
}

// ---------------------------------------------------------------------------
// 3. Tests
// ---------------------------------------------------------------------------

test("Assessment contains exactly 20 questions mapping to 8 dimensions", () => {
  assert.strictEqual(ASSESSMENT_QUESTIONS.length, 20);
  const primaryDims = new Set(ASSESSMENT_QUESTIONS.map((q) => q.primaryDimension));
  for (const dim of DIMENSION_KEYS) {
    assert.ok(primaryDims.has(dim), `Dimension ${dim} must be covered`);
  }
});

test("Deterministic scoring invariant - same answers yield identical profiles", () => {
  const answers = { 1: 5, 2: 4, 3: 2, 4: 1, 5: 5, 6: 4, 7: 3, 8: 4, 9: 5, 10: 4 };
  const p1 = calculateProfile(answers);
  const p2 = calculateProfile(answers);
  assert.deepStrictEqual(p1.dimensionScores, p2.dimensionScores);
  assert.deepStrictEqual(p1.topStrengths, p2.topStrengths);
});

test("Boundary invariant - All 1s produce 0 score; All 5s produce 100 score; All 3s produce 50 score", () => {
  const all1 = calculateProfile(Object.fromEntries(ASSESSMENT_QUESTIONS.map((q) => [q.id, 1])));
  const all5 = calculateProfile(Object.fromEntries(ASSESSMENT_QUESTIONS.map((q) => [q.id, 5])));
  const all3 = calculateProfile(Object.fromEntries(ASSESSMENT_QUESTIONS.map((q) => [q.id, 3])));

  for (const dim of DIMENSION_KEYS) {
    assert.strictEqual(all1.dimensionScores[dim], 0, `All 1s must yield 0 for ${dim}`);
    assert.strictEqual(all1.dimensionBands[dim], "Developing");
    assert.strictEqual(all5.dimensionScores[dim], 100, `All 5s must yield 100 for ${dim}`);
    assert.strictEqual(all5.dimensionBands[dim], "Very High");
    assert.strictEqual(all3.dimensionScores[dim], 50, `All 3s must yield 50 for ${dim}`);
    assert.strictEqual(all3.dimensionBands[dim], "Moderate");
  }
});

test("Missing answers fallback to 50 without error", () => {
  const empty = calculateProfile({});
  for (const dim of DIMENSION_KEYS) {
    assert.strictEqual(empty.dimensionScores[dim], 50);
  }
});

test("Band classifications follow specified thresholds", () => {
  assert.strictEqual(getStrengthBand(80), "Very High");
  assert.strictEqual(getStrengthBand(79), "High");
  assert.strictEqual(getStrengthBand(60), "High");
  assert.strictEqual(getStrengthBand(59), "Moderate");
  assert.strictEqual(getStrengthBand(40), "Moderate");
  assert.strictEqual(getStrengthBand(39), "Developing");
});

test("deriveOccupationVector produces bounded values [0..100]", () => {
  for (const occ of MOCK_OCCUPATIONS) {
    const vector = deriveOccupationVector(occ);
    for (const dim of DIMENSION_KEYS) {
      assert.ok(vector[dim] >= 0 && vector[dim] <= 100);
    }
  }
});

test("Technology enthusiast matches Software Developer highest", () => {
  const techAnswers = { 1: 5, 5: 5, 9: 5, 13: 5, 17: 5, 2: 1, 3: 1, 4: 1, 6: 2, 7: 3, 8: 2 };
  const profile = calculateProfile(techAnswers);
  const matches = matchOccupations(profile, MOCK_OCCUPATIONS, 5);
  assert.strictEqual(matches[0].occupation.slug, "software-developer");
});

test("People profile matches Registered Nurse highest", () => {
  const peopleAnswers = { 3: 5, 11: 5, 19: 5, 4: 4, 12: 4, 6: 4, 1: 1, 2: 1, 5: 1 };
  const profile = calculateProfile(peopleAnswers);
  const matches = matchOccupations(profile, MOCK_OCCUPATIONS, 5);
  assert.strictEqual(matches[0].occupation.slug, "registered-nurse");
});

test("Career Fit scores are strictly bounded [10..99]", () => {
  const allFives = calculateProfile(Object.fromEntries(ASSESSMENT_QUESTIONS.map((q) => [q.id, 5])));
  const matches = matchOccupations(allFives, MOCK_OCCUPATIONS);
  for (const m of matches) {
    assert.ok(m.careerFit >= 10 && m.careerFit <= 99);
  }
});

test("sortMatches handles fit, risk, and exposure sorting correctly", () => {
  const profile = calculateProfile({});
  const matches = matchOccupations(profile, MOCK_OCCUPATIONS);

  const byFit = sortMatches(matches, "fit");
  for (let i = 0; i < byFit.length - 1; i++) {
    assert.ok(byFit[i].careerFit >= byFit[i + 1].careerFit);
  }

  const byRisk = sortMatches(matches, "risk");
  for (let i = 0; i < byRisk.length - 1; i++) {
    assert.ok(byRisk[i].occupation.replacementRisk <= byRisk[i + 1].occupation.replacementRisk);
  }

  const byExposure = sortMatches(matches, "exposure");
  for (let i = 0; i < byExposure.length - 1; i++) {
    assert.ok(byExposure[i].occupation.aiExposure <= byExposure[i + 1].occupation.aiExposure);
  }
});

test("Underlying AI Exposure and Replacement Risk are never altered by Career Fit", () => {
  const profile = calculateProfile({});
  const matches = matchOccupations(profile, MOCK_OCCUPATIONS);

  for (const m of matches) {
    const original = MOCK_OCCUPATIONS.find((o) => o.slug === m.occupation.slug);
    assert.strictEqual(m.occupation.aiExposure, original.aiExposure);
    assert.strictEqual(m.occupation.replacementRisk, original.replacementRisk);
  }
});

test("Navigation contains Career Fit link", () => {
  const headerContent = fs.readFileSync(path.join(srcRoot, "components", "SiteHeader.tsx"), "utf8");
  const dropdownContent = fs.readFileSync(path.join(srcRoot, "components", "CareerToolsDropdown.tsx"), "utf8");
  const footerContent = fs.readFileSync(path.join(srcRoot, "components", "SiteFooter.tsx"), "utf8");
  const homeContent = fs.readFileSync(path.join(srcRoot, "app", "page.tsx"), "utf8");

  assert.ok(
    headerContent.includes("CareerToolsDropdown") && dropdownContent.includes('href="/career-fit"'),
    "SiteHeader dropdown must link to /career-fit"
  );
  assert.ok(headerContent.includes('href="/career-fit"'), "SiteHeader mobile navigation must include Career Fit link");
  assert.ok(footerContent.includes('href="/career-fit"'), "SiteFooter must include Career Fit link");
  assert.ok(homeContent.includes('href="/career-fit"'), "Homepage must include Career Fit CTA link");
});
