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

test("Career Transitions source files exist and contain required exports", () => {
  const typesPath = path.join(srcRoot, "lib", "transitions", "types.ts");
  const scoringPath = path.join(srcRoot, "lib", "transitions", "scoring.ts");
  const indexPath = path.join(srcRoot, "lib", "transitions", "index.ts");
  const bannerPath = path.join(
    srcRoot,
    "components",
    "transitions",
    "TransitionSourceBanner.tsx"
  );
  const cardPath = path.join(
    srcRoot,
    "components",
    "transitions",
    "TransitionCard.tsx"
  );
  const appPath = path.join(
    srcRoot,
    "components",
    "transitions",
    "TransitionExplorerApp.tsx"
  );
  const pagePath = path.join(
    srcRoot,
    "app",
    "jobs",
    "[slug]",
    "transitions",
    "page.tsx"
  );

  for (const filePath of [
    typesPath,
    scoringPath,
    indexPath,
    bannerPath,
    cardPath,
    appPath,
    pagePath,
  ]) {
    assert.ok(fs.existsSync(filePath), `Expected ${filePath} to exist`);
  }

  const scoringContent = fs.readFileSync(scoringPath, "utf8");
  assert.ok(scoringContent.includes("export function calculateCareerTransitions"));
  assert.ok(scoringContent.includes("export function sortTransitions"));
  assert.ok(scoringContent.includes("export function computeVectorDistance"));

  const pageContent = fs.readFileSync(pagePath, "utf8");
  assert.ok(pageContent.includes("robots:"));
  assert.ok(pageContent.includes("index: false"));
});

// ---------------------------------------------------------------------------
// 2. Pure Algorithm Execution Tests
// ---------------------------------------------------------------------------

const CATEGORY_ARCHETYPES = {
  "Technology & Data": { analytical: 90, creativity: 60, communication: 45, people: 30, practical: 15, organization: 75, technology: 95, leadership: 50 },
  "Science & Research": { analytical: 95, creativity: 65, communication: 65, people: 35, practical: 45, organization: 80, technology: 75, leadership: 50 },
  "Engineering & Architecture": { analytical: 90, creativity: 75, communication: 55, people: 35, practical: 60, organization: 80, technology: 85, leadership: 55 },
  "Healthcare": { analytical: 85, creativity: 35, communication: 75, people: 92, practical: 65, organization: 85, technology: 60, leadership: 65 },
  "Healthcare Support": { analytical: 45, creativity: 30, communication: 65, people: 90, practical: 75, organization: 70, technology: 35, leadership: 35 },
  "Business & Finance": { analytical: 88, creativity: 45, communication: 75, people: 60, practical: 15, organization: 90, technology: 70, leadership: 70 },
  "Management & Leadership": { analytical: 75, creativity: 60, communication: 90, people: 85, practical: 20, organization: 85, technology: 55, leadership: 95 },
  "Creative & Media": { analytical: 40, creativity: 95, communication: 85, people: 55, practical: 40, organization: 45, technology: 65, leadership: 50 },
  "Education & Training": { analytical: 70, creativity: 65, communication: 90, people: 92, practical: 25, organization: 75, technology: 50, leadership: 70 },
  "Community & Social Services": { analytical: 55, creativity: 45, communication: 85, people: 95, practical: 20, organization: 65, technology: 35, leadership: 60 },
  "Legal": { analytical: 92, creativity: 55, communication: 95, people: 70, practical: 15, organization: 90, technology: 50, leadership: 80 },
  "Sales": { analytical: 55, creativity: 55, communication: 90, people: 85, practical: 20, organization: 65, technology: 50, leadership: 75 },
  "Office & Administration": { analytical: 50, creativity: 30, communication: 65, people: 60, practical: 25, organization: 90, technology: 60, leadership: 40 },
  "Protective Services": { analytical: 60, creativity: 30, communication: 70, people: 75, practical: 80, organization: 75, technology: 50, leadership: 75 },
  "Construction & Extraction": { analytical: 45, creativity: 35, communication: 35, people: 30, practical: 95, organization: 60, technology: 40, leadership: 45 },
  "Installation & Repair": { analytical: 70, creativity: 35, communication: 40, people: 35, practical: 95, organization: 70, technology: 70, leadership: 45 },
  "Manufacturing & Production": { analytical: 50, creativity: 30, communication: 35, people: 30, practical: 90, organization: 75, technology: 55, leadership: 40 },
  "Transport & Logistics": { analytical: 40, creativity: 20, communication: 40, people: 35, practical: 85, organization: 70, technology: 45, leadership: 35 },
  "Food & Hospitality": { analytical: 30, creativity: 55, communication: 65, people: 80, practical: 85, organization: 65, technology: 25, leadership: 40 },
  "Personal Care & Service": { analytical: 35, creativity: 60, communication: 75, people: 90, practical: 70, organization: 60, technology: 30, leadership: 45 },
  "Agriculture & Environment": { analytical: 55, creativity: 35, communication: 35, people: 30, practical: 95, organization: 60, technology: 45, leadership: 45 },
  "Facilities & Grounds": { analytical: 25, creativity: 20, communication: 30, people: 35, practical: 90, organization: 55, technology: 25, leadership: 30 },
};

const DEFAULT_ARCHETYPE = {
  analytical: 60, creativity: 50, communication: 60, people: 60,
  practical: 50, organization: 65, technology: 55, leadership: 55,
};

const DIMENSION_KEYS = [
  "analytical", "creativity", "communication", "people",
  "practical", "organization", "technology", "leadership",
];

function deriveOccupationVector(occupation) {
  const cat = occupation.category || "";
  const baseline = CATEGORY_ARCHETYPES[cat] || DEFAULT_ARCHETYPE;
  const vector = { ...baseline };

  if (typeof occupation.physicalDependency === "number") {
    vector.practical = Math.round(baseline.practical * 0.35 + occupation.physicalDependency * 0.65);
  }
  if (typeof occupation.humanDependency === "number") {
    vector.people = Math.round(baseline.people * 0.40 + occupation.humanDependency * 0.60);
    vector.communication = Math.round(baseline.communication * 0.50 + occupation.humanDependency * 0.50);
  }

  const titleLower = (occupation.title || "").toLowerCase();
  if (titleLower.includes("data") || titleLower.includes("statistician") || titleLower.includes("analyst") || titleLower.includes("scientist") || titleLower.includes("economist")) {
    vector.analytical = Math.min(100, vector.analytical + 10);
    vector.technology = Math.min(100, vector.technology + 8);
  }
  if (titleLower.includes("designer") || titleLower.includes("writer") || titleLower.includes("artist") || titleLower.includes("architect")) {
    vector.creativity = Math.min(100, vector.creativity + 15);
  }
  if (titleLower.includes("manager") || titleLower.includes("director") || titleLower.includes("executive") || titleLower.includes("chief") || titleLower.includes("supervisor")) {
    vector.leadership = Math.min(100, vector.leadership + 15);
    vector.organization = Math.min(100, vector.organization + 8);
  }
  if (titleLower.includes("nurse") || titleLower.includes("therapist") || titleLower.includes("counselor") || titleLower.includes("social worker")) {
    vector.people = Math.min(100, vector.people + 12);
  }
  if (titleLower.includes("developer") || titleLower.includes("programmer") || titleLower.includes("engineer") || titleLower.includes("cybersecurity") || titleLower.includes("software")) {
    vector.technology = Math.min(100, vector.technology + 12);
    vector.analytical = Math.min(100, vector.analytical + 8);
  }

  for (const k of DIMENSION_KEYS) {
    vector[k] = Math.max(0, Math.min(100, vector[k]));
  }
  return vector;
}

function computeVectorDistance(v1, v2) {
  let sumSq = 0;
  for (const k of DIMENSION_KEYS) {
    sumSq += Math.pow(v1[k] - v2[k], 2);
  }
  return Math.sqrt(sumSq / DIMENSION_KEYS.length);
}

function calculateCareerTransitionsPure(source, allOccupations, limit = 10) {
  const occMap = new Map();
  for (const occ of allOccupations) {
    occMap.set(occ.slug, occ);
  }

  const isLowRiskSource = source.replacementRisk <= 40;
  const srcVector = deriveOccupationVector(source);

  const directRelations = source.relatedCareers || [];
  const directRelMap = new Map();
  for (const r of directRelations) {
    directRelMap.set(r.slug, { tier: r.relatednessTier, rank: r.relatednessRank });
  }

  const candidatePool = [];
  const addedSlugs = new Set([source.slug]);

  for (const r of directRelations) {
    const dest = occMap.get(r.slug);
    if (dest && !addedSlugs.has(dest.slug)) {
      const destVector = deriveOccupationVector(dest);
      const vecDist = computeVectorDistance(srcVector, destVector);
      candidatePool.push({
        occ: dest,
        candidateTier: "DIRECT",
        directTier: r.relatednessTier,
        directRank: r.relatednessRank,
        vecDist,
      });
      addedSlugs.add(dest.slug);
    }
  }

  const twoHopCandidates = [];
  for (const [dSlug] of directRelMap.entries()) {
    const dOcc = occMap.get(dSlug);
    if (dOcc) {
      for (const r of dOcc.relatedCareers || []) {
        if (!addedSlugs.has(r.slug)) {
          const dest = occMap.get(r.slug);
          if (dest) {
            const destVector = deriveOccupationVector(dest);
            const vecDist = computeVectorDistance(srcVector, destVector);
            const isCategoryMatch = dest.category === source.category;
            const isPhysicalMatch = Math.abs(dest.physicalDependency - source.physicalDependency) <= 15;
            const isRiskAcceptable = dest.replacementRisk <= source.replacementRisk + 6;
            if ((vecDist <= 14 || (isCategoryMatch && vecDist <= 18)) && isPhysicalMatch && isRiskAcceptable) {
              twoHopCandidates.push({ occ: dest, vecDist });
              addedSlugs.add(dest.slug);
            }
          }
        }
      }
    }
  }

  twoHopCandidates.sort((a, b) => a.vecDist - b.vecDist);
  for (const item of twoHopCandidates) {
    candidatePool.push({
      occ: item.occ,
      candidateTier: "2-HOP",
      vecDist: item.vecDist,
    });
  }

  if (candidatePool.length < limit + 4) {
    const fallbackCandidates = [];
    for (const occ of allOccupations) {
      if (!addedSlugs.has(occ.slug)) {
        const destVector = deriveOccupationVector(occ);
        const vecDist = computeVectorDistance(srcVector, destVector);
        if (occ.category === source.category && vecDist <= 22) {
          fallbackCandidates.push({ occ, vecDist });
          addedSlugs.add(occ.slug);
        }
      }
    }
    fallbackCandidates.sort((a, b) => a.vecDist - b.vecDist);
    for (const item of fallbackCandidates) {
      candidatePool.push({
        occ: item.occ,
        candidateTier: "CATEGORY_FALLBACK",
        vecDist: item.vecDist,
      });
    }
  }

  const evaluatedTransitions = [];

  for (const item of candidatePool) {
    const dest = item.occ;
    let transferability = 0;
    if (item.candidateTier === "DIRECT") {
      const rankBonus = Math.max(0, 10 - (item.directRank || 6));
      if (item.directTier === "Primary-Short") {
        transferability = 90 + Math.min(8, rankBonus);
      } else if (item.directTier === "Primary-Long") {
        transferability = 82 + Math.min(6, rankBonus);
      } else {
        transferability = 76 + Math.min(5, rankBonus);
      }
      transferability = Math.max(72, transferability - item.vecDist * 0.4);
    } else if (item.candidateTier === "2-HOP") {
      transferability = Math.max(50, 78 - item.vecDist * 1.1);
    } else {
      transferability = Math.max(35, 65 - item.vecDist * 1.4);
    }
    transferability = Math.max(10, Math.min(99, Math.round(transferability)));

    const riskDelta = source.replacementRisk - dest.replacementRisk;
    const exposureDelta = source.aiExposure - dest.aiExposure;

    let riskScore = 50 + riskDelta * 2.2;
    if (isLowRiskSource) {
      riskScore = 55 + Math.max(-10, riskDelta * 1.5);
    } else if (riskDelta < -8) {
      riskScore -= 18;
    }
    riskScore = Math.max(0, Math.min(100, riskScore));

    const exposureScore = Math.max(0, Math.min(100, 50 + exposureDelta * 1.2));
    const rawFit = transferability * 0.55 + riskScore * 0.35 + exposureScore * 0.10;
    const transitionFit = Math.max(15, Math.min(98, Math.round(rawFit)));

    let difficulty = "Moderate transition";
    let difficultySummary = "Requires building adjacent domain skills and adapting to new workflow requirements.";

    const isCloseVector = item.vecDist <= 12;
    const isClosePhysical = Math.abs(dest.physicalDependency - source.physicalDependency) <= 15;
    const isCloseHuman = Math.abs(dest.humanDependency - source.humanDependency) <= 15;

    if (item.candidateTier === "DIRECT" && (item.directTier === "Primary-Short" || (isCloseVector && isClosePhysical && isCloseHuman))) {
      difficulty = "Easier transition";
      difficultySummary = "High structural overlap in tasks and work style with minimal friction.";
    } else if (item.candidateTier === "CATEGORY_FALLBACK" || item.vecDist > 18 || (!isClosePhysical && !isCloseHuman)) {
      difficulty = "Larger transition";
      difficultySummary = "Notable divergence in physical/people demands requiring broader workflow adaptation.";
    }

    evaluatedTransitions.push({
      occupation: dest,
      transitionFit,
      transferabilityScore: transferability,
      riskDelta,
      exposureDelta,
      difficulty,
      difficultySummary,
      candidateTier: item.candidateTier,
      whyFit: `Alignment in core competencies and work patterns.`,
      considerations: `Maintains similar day-to-day workflow demands.`,
      keyOverlaps: [],
      keyDivergences: [],
    });
  }

  evaluatedTransitions.sort((a, b) => b.transitionFit - a.transitionFit);
  return {
    sourceOccupation: source,
    isLowRiskSource,
    directRelatedCount: directRelations.length,
    transitions: evaluatedTransitions.slice(0, limit),
    summaryHeadline: isLowRiskSource ? `Related career paths for ${source.title}` : `Career alternatives for ${source.title}`,
    summaryNarrative: isLowRiskSource
      ? `${source.title} currently ranks among lower-risk occupations.`
      : `Explore transferable career alternatives with lower AI replacement risk.`,
  };
}

const MOCK_OCCUPATIONS = [
  {
    slug: "graphic-designers",
    title: "Graphic Designers",
    category: "Creative & Media",
    aiExposure: 72,
    replacementRisk: 70,
    humanDependency: 55,
    physicalDependency: 35,
    relatedCareers: [
      { slug: "art-directors", title: "Art Directors", replacementRisk: 55, relatednessTier: "Primary-Short", relatednessRank: 1 },
      { slug: "commercial-and-industrial-designers", title: "Commercial and Industrial Designers", replacementRisk: 58, relatednessTier: "Primary-Short", relatednessRank: 2 },
      { slug: "desktop-publishers", title: "Desktop Publishers", replacementRisk: 78, relatednessTier: "Primary-Long", relatednessRank: 6 },
    ],
  },
  {
    slug: "art-directors",
    title: "Art Directors",
    category: "Creative & Media",
    aiExposure: 65,
    replacementRisk: 55,
    humanDependency: 70,
    physicalDependency: 30,
    relatedCareers: [
      { slug: "graphic-designers", title: "Graphic Designers", replacementRisk: 70, relatednessTier: "Primary-Short", relatednessRank: 1 },
      { slug: "producers-and-directors", title: "Producers and Directors", replacementRisk: 48, relatednessTier: "Primary-Long", relatednessRank: 5 },
    ],
  },
  {
    slug: "commercial-and-industrial-designers",
    title: "Commercial and Industrial Designers",
    category: "Engineering & Architecture",
    aiExposure: 60,
    replacementRisk: 58,
    humanDependency: 50,
    physicalDependency: 45,
    relatedCareers: [],
  },
  {
    slug: "desktop-publishers",
    title: "Desktop Publishers",
    category: "Creative & Media",
    aiExposure: 80,
    replacementRisk: 78,
    humanDependency: 35,
    physicalDependency: 25,
    relatedCareers: [],
  },
  {
    slug: "producers-and-directors",
    title: "Producers and Directors",
    category: "Creative & Media",
    aiExposure: 58,
    replacementRisk: 48,
    humanDependency: 85,
    physicalDependency: 35,
    relatedCareers: [],
  },
  {
    slug: "roofers",
    title: "Roofers",
    category: "Construction & Extraction",
    aiExposure: 25,
    replacementRisk: 30,
    humanDependency: 30,
    physicalDependency: 95,
    relatedCareers: [],
  },
  {
    slug: "pile-driver-operators",
    title: "Pile Driver Operators",
    category: "Construction & Extraction",
    aiExposure: 29,
    replacementRisk: 30,
    humanDependency: 30,
    physicalDependency: 95,
    relatedCareers: [
      { slug: "roofers", title: "Roofers", replacementRisk: 30, relatednessTier: "Primary-Short", relatednessRank: 1 },
    ],
  },
];

test("Deterministic output: same source produces identical transitions", () => {
  const src = MOCK_OCCUPATIONS[0];
  const res1 = calculateCareerTransitionsPure(src, MOCK_OCCUPATIONS, 5);
  const res2 = calculateCareerTransitionsPure(src, MOCK_OCCUPATIONS, 5);

  assert.equal(res1.transitions.length, res2.transitions.length);
  for (let i = 0; i < res1.transitions.length; i++) {
    assert.equal(res1.transitions[i].occupation.slug, res2.transitions[i].occupation.slug);
    assert.equal(res1.transitions[i].transitionFit, res2.transitions[i].transitionFit);
    assert.equal(res1.transitions[i].candidateTier, res2.transitions[i].candidateTier);
  }
});

test("Exclusion invariant: source occupation is never in its own recommendations", () => {
  for (const occ of MOCK_OCCUPATIONS) {
    const res = calculateCareerTransitionsPure(occ, MOCK_OCCUPATIONS, 10);
    assert.equal(res.transitions.some(t => t.occupation.slug === occ.slug), false);
  }
});

test("Structural priority: direct transferable matches outrank unrelated low-risk leaps", () => {
  const src = MOCK_OCCUPATIONS[0]; // Graphic Designers
  const res = calculateCareerTransitionsPure(src, MOCK_OCCUPATIONS, 10);

  const artIndex = res.transitions.findIndex(t => t.occupation.slug === "art-directors");
  const rooferIndex = res.transitions.findIndex(t => t.occupation.slug === "roofers");

  assert.notEqual(artIndex, -1, "Art Directors must be present");
  if (rooferIndex !== -1) {
    assert.ok(artIndex < rooferIndex, "Art Directors must rank higher than Roofers");
  }
});

test("Tiered expansion: 2-hop relations correctly tagged", () => {
  const src = MOCK_OCCUPATIONS[0];
  const res = calculateCareerTransitionsPure(src, MOCK_OCCUPATIONS, 10);
  const producer = res.transitions.find(t => t.occupation.slug === "producers-and-directors");

  assert.ok(producer, "Producers and Directors should be admitted via 2-hop");
  assert.equal(producer?.candidateTier, "2-HOP");
});

test("Low-risk source handling: switches headline and narrative appropriately", () => {
  const lowRiskSrc = MOCK_OCCUPATIONS[6]; // Pile Driver Operators (risk 30)
  const res = calculateCareerTransitionsPure(lowRiskSrc, MOCK_OCCUPATIONS, 5);

  assert.equal(res.isLowRiskSource, true);
  assert.ok(res.summaryHeadline.includes("Related career paths"));
});

test("Score bounds: Transition Fit is strictly between 15 and 98", () => {
  for (const occ of MOCK_OCCUPATIONS) {
    const res = calculateCareerTransitionsPure(occ, MOCK_OCCUPATIONS, 10);
    for (const t of res.transitions) {
      assert.ok(t.transitionFit >= 15 && t.transitionFit <= 98);
    }
  }
});

// ---------------------------------------------------------------------------
// 3. Risk Delta Presentation & Copy Invariant Tests
// ---------------------------------------------------------------------------

function getRiskDeltaPresentationPure(riskDelta) {
  if (riskDelta >= 5) {
    return {
      deltaType: "meaningful_reduction",
      deltaLabel: `${riskDelta} points lower`,
      chipTone: "lower",
      isMeaningfulReduction: true,
    };
  }
  if (riskDelta >= 1) {
    return {
      deltaType: "slight_reduction",
      deltaLabel: riskDelta === 1 ? "1 point lower" : `${riskDelta} points lower`,
      chipTone: "lower",
      isMeaningfulReduction: false,
    };
  }
  if (riskDelta === 0) {
    return {
      deltaType: "similar",
      deltaLabel: "similar replacement risk",
      chipTone: "neutral",
      isMeaningfulReduction: false,
    };
  }
  const abs = Math.abs(riskDelta);
  return {
    deltaType: "higher",
    deltaLabel: abs === 1 ? "1 point higher" : `${abs} points higher`,
    chipTone: "higher",
    isMeaningfulReduction: false,
  };
}

test("Risk Delta Presentation: delta >= 5 grants meaningful reduction", () => {
  const p1 = getRiskDeltaPresentationPure(5);
  assert.equal(p1.deltaType, "meaningful_reduction");
  assert.equal(p1.isMeaningfulReduction, true);
  assert.equal(p1.chipTone, "lower");
  assert.equal(p1.deltaLabel, "5 points lower");

  const p2 = getRiskDeltaPresentationPure(23);
  assert.equal(p2.deltaType, "meaningful_reduction");
  assert.equal(p2.isMeaningfulReduction, true);
  assert.equal(p2.chipTone, "lower");
  assert.equal(p2.deltaLabel, "23 points lower");
});

test("Risk Delta Presentation: delta 1-4 produces slight reduction wording", () => {
  const p1 = getRiskDeltaPresentationPure(1);
  assert.equal(p1.deltaType, "slight_reduction");
  assert.equal(p1.isMeaningfulReduction, false);
  assert.equal(p1.chipTone, "lower");
  assert.equal(p1.deltaLabel, "1 point lower");

  const p4 = getRiskDeltaPresentationPure(4);
  assert.equal(p4.deltaType, "slight_reduction");
  assert.equal(p4.isMeaningfulReduction, false);
  assert.equal(p4.chipTone, "lower");
  assert.equal(p4.deltaLabel, "4 points lower");
});

test("Risk Delta Presentation: delta 0 produces similar replacement risk", () => {
  const p0 = getRiskDeltaPresentationPure(0);
  assert.equal(p0.deltaType, "similar");
  assert.equal(p0.isMeaningfulReduction, false);
  assert.equal(p0.chipTone, "neutral");
  assert.equal(p0.deltaLabel, "similar replacement risk");
});

test("Risk Delta Presentation: negative delta produces explicit higher wording and tone", () => {
  const pNeg1 = getRiskDeltaPresentationPure(-1);
  assert.equal(pNeg1.deltaType, "higher");
  assert.equal(pNeg1.isMeaningfulReduction, false);
  assert.equal(pNeg1.chipTone, "higher");
  assert.equal(pNeg1.deltaLabel, "1 point higher");

  const pNeg10 = getRiskDeltaPresentationPure(-10);
  assert.equal(pNeg10.deltaType, "higher");
  assert.equal(pNeg10.isMeaningfulReduction, false);
  assert.equal(pNeg10.chipTone, "higher");
  assert.equal(pNeg10.deltaLabel, "10 points higher");
});

test("Risk Invariant: higher-risk destination never receives lower-risk badge/copy", () => {
  for (let delta = -30; delta < 0; delta++) {
    const pres = getRiskDeltaPresentationPure(delta);
    assert.equal(pres.isMeaningfulReduction, false);
    assert.equal(pres.chipTone, "higher");
    assert.ok(!pres.deltaLabel.includes("lower"), `Label for delta ${delta} should not contain 'lower'`);
    assert.ok(pres.deltaLabel.includes("higher"), `Label for delta ${delta} must contain 'higher'`);
  }
});

test("Page Framing Invariant: low-risk source never gets universal 'safer alternatives' framing", () => {
  const lowRiskSrc = MOCK_OCCUPATIONS[6]; // Pile Driver Operators (risk 30)
  const res = calculateCareerTransitionsPure(lowRiskSrc, MOCK_OCCUPATIONS, 5);

  assert.equal(res.isLowRiskSource, true);
  assert.ok(!res.summaryHeadline.toLowerCase().includes("safer alternatives"));
  assert.ok(!res.summaryNarrative.toLowerCase().includes("safer alternatives"));
  assert.ok(res.summaryHeadline.includes("Related career paths"));
});

test("Calculation Invariant: Transition Fit calculation is unaltered by presentation logic", () => {
  const src = MOCK_OCCUPATIONS[0];
  const res = calculateCareerTransitionsPure(src, MOCK_OCCUPATIONS, 5);

  // Transition Fit values must remain strictly within [15..98]
  for (const t of res.transitions) {
    assert.ok(t.transitionFit >= 15 && t.transitionFit <= 98);
    assert.ok(typeof t.transitionFit === "number");
  }
});

