export type TaskImpact = { onetTaskId: number; name: string; importance: "High" | "Medium" | "Low"; exposure: number; automationFeasibility: number; augmentationPotential: number };
export type CareerRelationship = { slug: string; title: string; replacementRisk: number; relatednessTier: string; relatednessRank: number };

export type Occupation = {
  slug: string;
  title: string;
  category: string;
  summary: string;
  verdict: string;
  aiExposure: number;
  replacementRisk: number;
  taskExposure: number;
  aiCapabilityProximity: number;
  /** Numeric 0-100, not the legacy High/Medium/Low band. */
  confidence: number;
  weightedTaskCoverage: number;
  humanDependency: number;
  physicalDependency: number;
  adoptionPressure: number;
  labourMarketResilience: number;
  /** Percent of replacement-risk weight resting on provisional proxy models. */
  provisionalWeightShare: number;
  tasks: TaskImpact[];
  hardestToAutomateTasks: string[];
  relatedCareers: CareerRelationship[];
  updatedAt: string;
  modelVersion: string;
};

export type CareerRecommendation = {
  category: string;
  slug: string;
  title: string;
  occupationCategory: string;
  aiExposure: number;
  replacementRisk: number;
  aiResilience: number;
  skillOverlap: number;
  transitionDifficulty: string;
  retrainingMonths: string;
  estimatedMonthsMin: number;
  estimatedMonthsMax: number;
  salaryDirection: string;
  futureDemand: number;
  whyFit: string;
  transferableSkills: string[];
  missingSkills: string[];
  rankScore: number;
  scoreComponents: Record<string, number>;
};

export type CareerFinderResponse = {
  currentOccupationSlug: string;
  currentOccupationTitle: string;
  method: string;
  modelVersion: string;
  constraints: Record<string, unknown>;
  recommendations: CareerRecommendation[];
};

export type ScoreFactor = {
  key: string;
  label: string;
  rawValue: number;
  transformedValue: number;
  transformation: string;
  weight: number;
  contribution: number;
  isProvisionalProxy?: boolean;
  proxyModelVersion?: string | null;
};

export type TaskContribution = {
  taskId: number;
  task: string;
  exposure: number;
  importance: number;
  frequency: number;
  normalizedWeight: number;
  exposureContribution: number;
};

export type ScoreDerivation = {
  scoreId: number;
  occupationSlug: string;
  occupationTitle: string;
  aiExposure: number;
  replacementRisk: number;
  confidence: string;
  trend: string;
  taskExposure: number;
  aiCapabilityProximity: number;
  modelVersion: string;
  calculatedAt: string;
  calculatedTotal: number;
  inputVersions: Record<string, unknown>;
  factors: ScoreFactor[];
  taskContributions: TaskContribution[];
};
