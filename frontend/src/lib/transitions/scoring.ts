import type { Occupation } from "../../types/occupation";
import {
  DIMENSIONS,
  DIMENSION_KEYS,
  type DimensionKey,
  deriveOccupationVector,
} from "../careerFit";
import type {
  CandidateTier,
  CareerTransition,
  RiskDeltaPresentation,
  TransitionAnalysis,
  TransitionDifficulty,
  TransitionSortOption,
} from "./types";

/**
 * Computes root-mean-square Euclidean distance between two 8-dimension occupation vectors.
 */
export function computeVectorDistance(
  v1: Record<DimensionKey, number>,
  v2: Record<DimensionKey, number>
): number {
  let sumSq = 0;
  for (const k of DIMENSION_KEYS) {
    sumSq += Math.pow(v1[k] - v2[k], 2);
  }
  return Math.sqrt(sumSq / DIMENSION_KEYS.length);
}

/**
 * Formats factual risk-delta presentation distinguishing meaningful reduction from similar/higher risk.
 */
export function getRiskDeltaPresentation(riskDelta: number): RiskDeltaPresentation {
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

/**
 * Derives observable structural overlaps and divergences between source and destination occupations.
 */
function deriveStructuralCharacteristics(
  source: Occupation,
  dest: Occupation,
  srcVector: Record<DimensionKey, number>,
  destVector: Record<DimensionKey, number>
): {
  whyFit: string;
  considerations: string;
  keyOverlaps: string[];
  keyDivergences: string[];
} {
  const overlaps: string[] = [];
  const divergences: string[] = [];

  // 1. Evaluate top overlapping dimensions (both >= 55)
  for (const k of DIMENSION_KEYS) {
    if (srcVector[k] >= 55 && destVector[k] >= 55) {
      overlaps.push(DIMENSIONS[k].label);
    }
  }

  // 2. Evaluate notable divergences (|diff| >= 25)
  const humanDiff = dest.humanDependency - source.humanDependency;
  if (humanDiff >= 20) {
    divergences.push("Significantly more people-facing and interpersonal than your current role.");
  } else if (humanDiff <= -20) {
    divergences.push("Substantially less dependent on direct interpersonal collaboration.");
  }

  const physicalDiff = dest.physicalDependency - source.physicalDependency;
  if (physicalDiff >= 20) {
    divergences.push("Requires substantially more hands-on, physical or on-site work.");
  } else if (physicalDiff <= -20) {
    divergences.push("Less physically dependent and more office/digital-focused.");
  }

  const techDiff = destVector.technology - srcVector.technology;
  if (techDiff >= 25) {
    divergences.push("Involves higher technical and digital systems complexity.");
  }

  const analyticalDiff = destVector.analytical - srcVector.analytical;
  if (analyticalDiff >= 25) {
    divergences.push("Requires deeper quantitative data analysis and structured modeling.");
  }

  const creativeDiff = destVector.creativity - srcVector.creativity;
  if (creativeDiff >= 25) {
    divergences.push("Requires greater original visual, narrative, or conceptual design.");
  }

  // Fallback if no extreme divergence
  if (divergences.length === 0) {
    if (dest.category !== source.category) {
      divergences.push(`Transitions workflow from ${source.category} into ${dest.category} domain practices.`);
    } else {
      divergences.push("Maintains very similar day-to-day workflow demands and environment.");
    }
  }

  // Generate clear 'whyFit'
  let whyFit = "";
  if (overlaps.length >= 2) {
    whyFit = `Strong alignment in ${overlaps[0]} and ${overlaps[1]}.`;
  } else if (overlaps.length === 1) {
    whyFit = `Direct alignment in ${overlaps[0]} competencies.`;
  } else if (dest.category === source.category) {
    whyFit = `Shared ${source.category} industry fundamentals and work context.`;
  } else {
    whyFit = `Balanced structural overlap in problem-solving and task requirements.`;
  }

  const considerations = divergences[0];

  return {
    whyFit,
    considerations,
    keyOverlaps: overlaps.slice(0, 3),
    keyDivergences: divergences.slice(0, 2),
  };
}

/**
 * Generates ranked career transitions for a given source occupation using tiered candidate expansion.
 *
 * Tier 1: Direct O*NET related occupations (highest structural priority)
 * Tier 2: 2-Hop O*NET relations (only when Tier 1 < target count, with strict similarity threshold)
 * Tier 3: Same-category / structural fallback (only when Tiers 1 & 2 < target count)
 */
export function calculateCareerTransitions(
  source: Occupation,
  allOccupations: Occupation[],
  limit = 10
): TransitionAnalysis {
  const occMap = new Map<string, Occupation>();
  for (const occ of allOccupations) {
    occMap.set(occ.slug, occ);
  }

  const isLowRiskSource = source.replacementRisk <= 40;
  const srcVector = deriveOccupationVector(source);

  // -------------------------------------------------------------------------
  // Tier 1: Direct O*NET Relations
  // -------------------------------------------------------------------------
  const directRelations = source.relatedCareers || [];
  const directRelMap = new Map<string, { tier: string; rank: number }>();
  for (const r of directRelations) {
    directRelMap.set(r.slug, { tier: r.relatednessTier, rank: r.relatednessRank });
  }

  const candidatePool: Array<{
    occ: Occupation;
    candidateTier: CandidateTier;
    directTier?: string;
    directRank?: number;
    vecDist: number;
  }> = [];

  const addedSlugs = new Set<string>([source.slug]);

  // Add Tier 1 candidates
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

  // -------------------------------------------------------------------------
  // Tier 2: 2-Hop O*NET Relations (Cautious expansion)
  // -------------------------------------------------------------------------
  const twoHopCandidates: Array<{ occ: Occupation; vecDist: number }> = [];
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
            const isPhysicalMatch =
              Math.abs(dest.physicalDependency - source.physicalDependency) <= 15;
            const isRiskAcceptable =
              dest.replacementRisk <= source.replacementRisk + 6;

            // Strict similarity gate for 2-hop relations to prevent unrelated jumps:
            // Must have tight vector distance <= 15, physical compatibility, and no severe risk regression
            if (
              (vecDist <= 14 || (isCategoryMatch && vecDist <= 18)) &&
              isPhysicalMatch &&
              isRiskAcceptable
            ) {
              twoHopCandidates.push({ occ: dest, vecDist });
              addedSlugs.add(dest.slug);
            }
          }
        }
      }
    }
  }

  // Sort 2-hop candidates by vector distance and add up to what's needed
  twoHopCandidates.sort((a, b) => a.vecDist - b.vecDist);
  for (const item of twoHopCandidates) {
    candidatePool.push({
      occ: item.occ,
      candidateTier: "2-HOP",
      vecDist: item.vecDist,
    });
  }

  // -------------------------------------------------------------------------
  // Tier 3: Same Category / Structural Fallback
  // -------------------------------------------------------------------------
  if (candidatePool.length < limit + 4) {
    const fallbackCandidates: Array<{ occ: Occupation; vecDist: number }> = [];
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

  // -------------------------------------------------------------------------
  // Scoring & Ranking
  // -------------------------------------------------------------------------
  const evaluatedTransitions: CareerTransition[] = [];

  for (const item of candidatePool) {
    const dest = item.occ;
    const destVector = deriveOccupationVector(dest);

    // 1. Transferability Score [10..99]
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
      // Minor adjustment based on competency distance
      transferability = Math.max(72, transferability - item.vecDist * 0.4);
    } else if (item.candidateTier === "2-HOP") {
      transferability = Math.max(50, 78 - item.vecDist * 1.1);
    } else {
      transferability = Math.max(35, 65 - item.vecDist * 1.4);
    }
    transferability = Math.max(10, Math.min(99, Math.round(transferability)));

    // 2. Risk & Exposure Deltas
    const riskDelta = source.replacementRisk - dest.replacementRisk; // positive = lower risk
    const exposureDelta = source.aiExposure - dest.aiExposure;
    const riskPresentation = getRiskDeltaPresentation(riskDelta);

    // 3. Replacement Risk Contribution
    let riskScore = 50 + riskDelta * 2.2;
    if (isLowRiskSource) {
      // For already low-risk careers (<= 40), finding strong related paths is primary
      riskScore = 55 + Math.max(-10, riskDelta * 1.5);
    } else if (riskDelta < -8) {
      // Penalty if destination has significantly worse replacement risk
      riskScore -= 18;
    }
    riskScore = Math.max(0, Math.min(100, riskScore));

    // 4. AI Exposure Contribution
    const exposureScore = Math.max(0, Math.min(100, 50 + exposureDelta * 1.2));

    // 5. Final Transition Fit: 55% Transferability, 35% Risk Reduction, 10% Exposure Reduction
    const rawFit =
      transferability * 0.55 + riskScore * 0.35 + exposureScore * 0.10;
    const transitionFit = Math.max(15, Math.min(98, Math.round(rawFit)));

    // 6. Transition Difficulty (based on observable structural factors)
    let difficulty: TransitionDifficulty = "Moderate transition";
    let difficultySummary =
      "Requires building adjacent domain skills and adapting to new workflow requirements.";

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

    // 7. Structural Rationale
    const { whyFit, considerations, keyOverlaps, keyDivergences } =
      deriveStructuralCharacteristics(source, dest, srcVector, destVector);

    evaluatedTransitions.push({
      occupation: dest,
      transitionFit,
      transferabilityScore: transferability,
      riskDelta,
      exposureDelta,
      riskPresentation,
      difficulty,
      difficultySummary,
      candidateTier: item.candidateTier,
      whyFit,
      considerations,
      keyOverlaps,
      keyDivergences,
    });
  }

  // Sort by default Best Transition Match
  evaluatedTransitions.sort((a, b) => b.transitionFit - a.transitionFit);

  const topTransitions = evaluatedTransitions.slice(0, limit);

  // Generate headline & narrative with precise risk-framing
  const directRelatedCount = directRelations.length;
  const hasMeaningfulReduction = topTransitions.some(
    (t) => t.riskPresentation.isMeaningfulReduction
  );
  let summaryHeadline = `Career alternatives for ${source.title}`;
  let summaryNarrative = "";

  if (isLowRiskSource) {
    summaryHeadline = `Related career paths for ${source.title}`;
    summaryNarrative = `${source.title} currently ranks among the lower-risk occupations in our database (${source.replacementRisk}/100 Replacement Risk). The alternatives below represent adjacent career moves with shared work characteristics.`;
  } else if (hasMeaningfulReduction) {
    const maxDrop = Math.max(...topTransitions.map((t) => t.riskDelta));
    summaryHeadline = `Career alternatives for ${source.title}`;
    summaryNarrative = `Explore related occupations with transferable characteristics, including options with up to ${maxDrop} points lower AI-replacement risk.`;
  } else {
    summaryHeadline = `Career alternatives for ${source.title}`;
    summaryNarrative = `Explore related career paths for ${source.title} with transferable occupational characteristics and compatible competency profiles.`;
  }

  return {
    sourceOccupation: source,
    isLowRiskSource,
    hasMeaningfulReduction,
    directRelatedCount,
    transitions: topTransitions,
    summaryHeadline,
    summaryNarrative,
  };
}

/**
 * Sorts transitions by user-selected sort option.
 */
export function sortTransitions(
  transitions: CareerTransition[],
  sortOption: TransitionSortOption
): CareerTransition[] {
  const sorted = [...transitions];
  switch (sortOption) {
    case "risk":
      return sorted.sort(
        (a, b) => a.occupation.replacementRisk - b.occupation.replacementRisk
      );
    case "exposure":
      return sorted.sort(
        (a, b) => a.occupation.aiExposure - b.occupation.aiExposure
      );
    case "fit":
    default:
      return sorted.sort((a, b) => b.transitionFit - a.transitionFit);
  }
}
