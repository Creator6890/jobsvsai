import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

function calculateCareerTransitions(source, allOccupations, limit = 10) {
  const occMap = new Map();
  for (const occ of allOccupations) {
    occMap.set(occ.slug, occ);
  }

  const isLowRiskSource = source.replacementRisk <= 40;
  const srcVector = deriveOccupationVector(source);

  // Tier 1: Direct O*NET relations
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

  // Tier 2: 2-Hop O*NET relations (only when similar)
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

  // Tier 3: Same category fallback if needed
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
      vecDist: Math.round(item.vecDist),
    });
  }

  evaluatedTransitions.sort((a, b) => b.transitionFit - a.transitionFit);

  return {
    sourceOccupation: source,
    isLowRiskSource,
    directRelatedCount: directRelations.length,
    transitions: evaluatedTransitions.slice(0, limit),
  };
}

async function runCalibration() {
  const r1 = await fetch("http://localhost:8000/api/v1/occupations?limit=500").then(r => r.json());
  const r2 = await fetch("http://localhost:8000/api/v1/occupations?limit=500&offset=500").then(r => r.json());
  const allOccupations = [...r1, ...r2];
  const occMap = new Map(allOccupations.map(o => [o.slug, o]));

  const testCohorts = [
    { domain: "Creative", slug: "fashion-designers" },
    { domain: "Software / Tech", slug: "computer-programmers" },
    { domain: "Administrative", slug: "secretaries-and-administrative-assistants-except-legal-medical-and-executive" },
    { domain: "Finance", slug: "accountant" },
    { domain: "Healthcare", slug: "registered-nurses" },
    { domain: "Education", slug: "elementary-school-teachers-except-special-education" },
    { domain: "Sales", slug: "insurance-sales-agents" },
    { domain: "Management", slug: "human-resources-managers" },
    { domain: "Trades", slug: "electricians" },
    { domain: "Transportation", slug: "heavy-and-tractor-trailer-truck-drivers" },
    { domain: "Service", slug: "chefs-and-head-cooks" },
    { domain: "Low-Risk", slug: "aircraft-mechanic" },
  ];

  console.log("================================================================================");
  console.log("CAREER TRANSITION EXPLORER V1 — 12-COHORT CALIBRATION MATRIX");
  console.log("================================================================================\n");

  let totalRecommendations = 0;
  let directCount = 0;
  let twoHopCount = 0;
  let fallbackCount = 0;

  const riskDeltasExposed = [];
  const cohortResults = [];

  for (const cohort of testCohorts) {
    const src = occMap.get(cohort.slug);
    if (!src) {
      console.error("Missing test occupation:", cohort.slug);
      continue;
    }

    const analysis = calculateCareerTransitions(src, allOccupations, 10);
    const transitions = analysis.transitions;

    let cohortDirect = 0;
    let cohortTwoHop = 0;
    let cohortFallback = 0;

    const rowItems = [];
    for (const [idx, t] of transitions.entries()) {
      totalRecommendations++;
      if (t.candidateTier === "DIRECT") { directCount++; cohortDirect++; }
      else if (t.candidateTier === "2-HOP") { twoHopCount++; cohortTwoHop++; }
      else { fallbackCount++; cohortFallback++; }

      if (src.replacementRisk > 40) {
        riskDeltasExposed.push(t.riskDelta);
      }

      // Quality heuristic
      let quality = "STRONG";
      if (t.candidateTier === "CATEGORY_FALLBACK" && t.vecDist > 16) quality = "PLAUSIBLE";
      if (t.riskDelta < -10) quality = "QUESTIONABLE";

      rowItems.push({
        rank: idx + 1,
        title: t.occupation.title,
        category: t.occupation.category,
        fit: t.transitionFit,
        srcRisk: src.replacementRisk,
        destRisk: t.occupation.replacementRisk,
        delta: t.riskDelta,
        tier: t.candidateTier,
        difficulty: t.difficulty,
        quality,
      });
    }

    cohortResults.push({
      domain: cohort.domain,
      source: src,
      directAvailable: analysis.directRelatedCount,
      cohortDirect,
      cohortTwoHop,
      cohortFallback,
      recommendations: rowItems,
    });
  }

  // Print Detailed Cohort Summaries
  for (const c of cohortResults) {
    console.log(`### ${c.domain}: ${c.source.title} (${c.source.category})`);
    console.log(`Source Metrics: Replacement Risk ${c.source.replacementRisk} | AI Exposure ${c.source.aiExposure} | Direct O*NET Available: ${c.directAvailable}`);
    console.log(`Tier Breakdown in Top 10: ${c.cohortDirect} Direct | ${c.cohortTwoHop} 2-Hop | ${c.cohortFallback} Fallback\n`);
    console.log("| # | Destination Occupation | Category | Fit | Risk (Src→Dest) | Delta | Tier | Difficulty | Quality |");
    console.log("|---|---|---|---|---|---|---|---|---|");
    for (const r of c.recommendations) {
      const deltaStr = r.delta > 0 ? `-${r.delta} pts` : (r.delta < 0 ? `+${Math.abs(r.delta)} pts` : "0 pts");
      console.log(`| ${r.rank} | ${r.title} | ${r.category} | ${r.fit}% | ${r.srcRisk} → ${r.destRisk} | ${deltaStr} | ${r.tier} | ${r.difficulty} | ${r.quality} |`);
    }
    console.log("\n--------------------------------------------------------------------------------\n");
  }

  // Overall Statistics
  riskDeltasExposed.sort((a, b) => a - b);
  const meanDelta = (riskDeltasExposed.reduce((a, b) => a + b, 0) / riskDeltasExposed.length).toFixed(1);
  const medianDelta = riskDeltasExposed[Math.floor(riskDeltasExposed.length / 2)];
  const minDelta = Math.min(...riskDeltasExposed);
  const maxDelta = Math.max(...riskDeltasExposed);

  console.log("================================================================================");
  console.log("GLOBAL CALIBRATION METRICS & INVARIANTS");
  console.log("================================================================================");
  console.log(`Total Recommendations Evaluated: ${totalRecommendations}`);
  console.log(`Direct O*NET Relations:          ${directCount} (${((directCount/totalRecommendations)*100).toFixed(1)}%)`);
  console.log(`2-Hop O*NET Relations:           ${twoHopCount} (${((twoHopCount/totalRecommendations)*100).toFixed(1)}%)`);
  console.log(`Category / Structural Fallbacks: ${fallbackCount} (${((fallbackCount/totalRecommendations)*100).toFixed(1)}%)`);
  console.log(`\nRisk Reduction Statistics for Exposed Sources (Risk > 40, n = ${riskDeltasExposed.length}):`);
  console.log(`  Mean Risk Improvement:   ${meanDelta} points lower`);
  console.log(`  Median Risk Improvement: ${medianDelta} points lower`);
  console.log(`  Minimum Risk Change:     ${minDelta} points`);
  console.log(`  Maximum Risk Reduction:  ${maxDelta} points lower`);
  console.log("================================================================================");
}

runCalibration();
