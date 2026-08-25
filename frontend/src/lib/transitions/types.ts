import type { Occupation } from "@/types/occupation";

export type TransitionDifficulty =
  | "Easier transition"
  | "Moderate transition"
  | "Larger transition";

export type TransitionSortOption = "fit" | "risk" | "exposure";

export type CandidateTier = "DIRECT" | "2-HOP" | "CATEGORY_FALLBACK";

export type CareerTransition = {
  occupation: Occupation;
  transitionFit: number; // 15..98%
  transferabilityScore: number; // 10..99%
  riskDelta: number; // source.replacementRisk - dest.replacementRisk (positive = safer)
  exposureDelta: number; // source.aiExposure - dest.aiExposure (positive = lower exposure)
  difficulty: TransitionDifficulty;
  difficultySummary: string;
  candidateTier: CandidateTier;
  whyFit: string;
  considerations: string;
  keyOverlaps: string[];
  keyDivergences: string[];
};

export type TransitionAnalysis = {
  sourceOccupation: Occupation;
  isLowRiskSource: boolean;
  directRelatedCount: number;
  transitions: CareerTransition[];
  summaryHeadline: string;
  summaryNarrative: string;
};
