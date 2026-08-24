import { cache } from "react";
import type { CareerFinderResponse, Occupation, ScoreDerivation } from "@/types/occupation";

const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiUrl}/api/v1${path}`, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!response.ok) {
    throw new ApiError(`JobsVsAI API request failed: ${response.status}`, response.status);
  }
  return response.json() as Promise<T>;
}

function adminHeaders(): HeadersInit {
  const username = process.env.ADMIN_USERNAME;
  const password = process.env.ADMIN_PASSWORD;
  if (!username || !password) throw new Error("Admin API credentials are not configured");
  return { Authorization: `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}` };
}

function camelize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(camelize);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()), camelize(item)]));
  return value;
}

async function adminRequest<T>(path: string): Promise<T> {
  return camelize(await request<unknown>(path, { headers: adminHeaders() })) as T;
}

export const getOccupation = cache(async (slug: string): Promise<Occupation | null> => {
  try {
    return await request<Occupation>(`/occupations/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

// The API caps a single page at 500. The published cohort is larger than that and will
// keep growing, so this walks the pages instead of asking for one big one — a fixed limit
// here silently truncates the sitemap, the compare selector and the admin lists.
const OCCUPATION_PAGE_SIZE = 500;

export const getOccupations = cache(async (): Promise<Occupation[]> => {
  const all: Occupation[] = [];
  for (let offset = 0; ; offset += OCCUPATION_PAGE_SIZE) {
    const page = await request<Occupation[]>(
      `/occupations?limit=${OCCUPATION_PAGE_SIZE}&offset=${offset}`,
    );
    all.push(...page);
    if (page.length < OCCUPATION_PAGE_SIZE) return all;
  }
});

// The rankings page needs five fields per occupation, not the full record. Fetching the
// whole cohort through getOccupations() shipped every task list and verdict to the browser
// — roughly 3.6 MB of RSC payload for a table that renders none of it. This reader asks the
// dedicated rankings endpoint instead, which returns one flat row per occupation.
//
// The endpoint caps limit at 1000 and the published cohort is 507, so a single request
// covers it. Revisit if the cohort ever approaches the cap.
const RANKINGS_LIMIT = 1000;

/** One row exactly as the API returns it: snake_case, numerics serialised as strings. */
export type RankingApiRow = {
  slug: string;
  title: string;
  category: string;
  ai_exposure: string;
  replacement_risk: string;
};

/** The shape the rankings UI consumes. Deliberately a subset of Occupation. */
export type RankingOccupation = {
  slug: string;
  title: string;
  category: string;
  aiExposure: number;
  replacementRisk: number;
};

export const getRankings = cache(async (): Promise<RankingOccupation[]> => {
  const rows = await request<RankingApiRow[]>(`/rankings?limit=${RANKINGS_LIMIT}`);
  return rows.map((row) => ({
    slug: row.slug,
    title: row.title,
    category: row.category,
    // PostgreSQL numerics arrive as strings; the table shows whole numbers, matching the
    // occupation page, which rounds the same way.
    aiExposure: Math.round(Number(row.ai_exposure)),
    replacementRisk: Math.round(Number(row.replacement_risk)),
  }));
});

export async function searchOccupations(query: string): Promise<Occupation[]> {
  if (query.trim().length < 2) return [];
  return request<Occupation[]>(`/occupations/search?q=${encodeURIComponent(query.trim())}`);
}

export async function getCareerRecommendations(payload: Record<string, unknown>): Promise<CareerFinderResponse> {
  return request<CareerFinderResponse>("/careers/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ------------------------------------------------------------------------------ AI News
//
// Jobs Impact is a news-significance indicator. It is unrelated to occupation AI Exposure
// and Replacement Risk, and the public payload deliberately carries no numeric score: V1
// publishes only the band.

export type NewsImpactLevel = "low" | "medium" | "high";
export type NewsArticleStatus = "draft" | "review_required" | "published" | "rejected";

export type NewsSource = {
  sourceName: string;
  sourceUrl: string;
  originalTitle: string;
  sourcePublishedAt: string | null;
  isPrimary: boolean;
};

export type NewsArticleSummary = {
  slug: string;
  headline: string;
  whatHappened: string;
  impactLevel: NewsImpactLevel;
  publishedAt: string | null;
  tags: string[];
  jobAreas: string[];
  primarySource: NewsSource | null;
};

export type NewsArticleDetail = NewsArticleSummary & {
  whyItMattersForJobs: string;
  sources: NewsSource[];
};

export const getNewsArticles = cache(async (impact?: NewsImpactLevel): Promise<NewsArticleSummary[]> => {
  const query = impact ? `?impact=${impact}&limit=60` : "?limit=60";
  return request<NewsArticleSummary[]>(`/news${query}`);
});

export const getNewsArticle = cache(async (slug: string): Promise<NewsArticleDetail | null> => {
  try {
    return await request<NewsArticleDetail>(`/news/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

/** Published articles only — the backend predicate decides, not this reader. */
export const getNewsSitemapEntries = cache(async (): Promise<{ slug: string; publishedAt: string; updatedAt: string }[]> =>
  request<{ slug: string; publishedAt: string; updatedAt: string }[]>("/news/sitemap"));

export type AdminNewsArticle = NewsArticleDetail & {
  id: number;
  status: NewsArticleStatus;
  impactScore: number | null;
  impactConfidence: number | null;
  impactReasoning: string | null;
  impactPolicyVersion: string | null;
  capabilityAdvancement: number | null;
  commercialDeployability: number | null;
  breadthOfAffectedWork: number | null;
  adoptionSpeed: number | null;
  humanWorkReductionPotential: number | null;
  automatedImpactScore: number | null;
  automatedImpactLevel: NewsImpactLevel | null;
  generationProvider: string | null;
  generationModel: string | null;
  impactAssessedAt: string | null;
  impactAssessedBy: string | null;
  impactOverriddenAt: string | null;
  impactOverriddenBy: string | null;
  impactOverrideReason: string | null;
  createdAt: string;
  updatedAt: string;
};

export type NewsImpactPolicy = {
  policyVersion: string;
  minimumPublishConfidence: number;
  factors: { key: string; label: string; weight: number }[];
  thresholds: Record<string, string>;
};

// Admin news reads are NOT camelized client-side: the API already returns camelCase for
// these models, unlike the raw dict-returning admin endpoints that adminRequest handles.
async function adminNewsRequest<T>(path: string): Promise<T> {
  return request<T>(path, { headers: adminHeaders() });
}

export const getAdminNewsArticles = cache(async (status?: NewsArticleStatus): Promise<AdminNewsArticle[]> =>
  adminNewsRequest<AdminNewsArticle[]>(`/admin/news${status ? `?status=${status}` : ""}`));

export const getAdminNewsCounts = cache(async (): Promise<Record<NewsArticleStatus, number>> =>
  adminNewsRequest<Record<NewsArticleStatus, number>>("/admin/news/counts"));

export const getAdminNewsArticle = cache(async (id: string): Promise<AdminNewsArticle | null> => {
  try {
    return await adminNewsRequest<AdminNewsArticle>(`/admin/news/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

/** The source candidates behind an article, with their semantic verdicts. Admin-only. */
export const getArticleCandidates = cache(async (id: string): Promise<IngestItem[]> => {
  try {
    return await adminNewsRequest<IngestItem[]>(`/admin/news/${id}/candidates`);
  } catch (error) {
    // A hand-written article has no ingest candidate; that is not an error.
    if (error instanceof ApiError && error.status === 404) return [];
    throw error;
  }
});

export const getNewsImpactPolicy = cache(async (): Promise<NewsImpactPolicy> =>
  adminNewsRequest<NewsImpactPolicy>("/admin/news/policy"));

export const getNewsPublicationCheck = cache(async (id: string): Promise<{ publishable: boolean; blockers: string[] }> =>
  adminNewsRequest<{ publishable: boolean; blockers: string[] }>(`/admin/news/${id}/publication-check`));

/** Admin mutations. Server-side only; credentials never reach the browser. */
export async function adminNewsMutate<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(`/admin/news${path}`, {
    method: "POST",
    headers: { ...adminHeaders(), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// --- Phase 2 ingestion. Admin-only: there is no public reader for ingest items, because
// there is no public route that serves one.

export type IngestStatus = "new" | "candidate" | "ignored" | "duplicate" | "processed";

export type IngestItem = {
  id: number;
  sourceId: number;
  sourceName: string;
  trustTier: number;
  externalUrl: string;
  canonicalUrl: string;
  originalTitle: string;
  originalExcerpt: string | null;
  sourcePublishedAt: string | null;
  fetchedAt: string;
  status: IngestStatus;
  relevanceScore: number | null;
  relevancePolicyVersion: string | null;
  relevanceSignals: Record<string, unknown>;
  feedCategories: string[];
  duplicateOfIngestItemId: number | null;
  nearDuplicateSimilarity: number | null;
  // Phase 3 semantic verdict. null = not yet assessed, distinct from false.
  isAiNews: boolean | null;
  aiRelevanceConfidence: number | null;
  aiRelevanceReason: string | null;
  semanticPolicyVersion: string | null;
  generationProvider: string | null;
  generationModel: string | null;
  generationPromptVersion: string | null;
  generationAttemptedAt: string | null;
  generationAttempts: number;
  generationError: string | null;
  generationInputTokens: number | null;
  generationOutputTokens: number | null;
};

export type GenerationStatus = {
  /** Ingestion and generation are gated independently. */
  ingestionEnabled: boolean;
  generationEnabled: boolean;
  /** True when behaviour still comes from the deprecated single NEWS_ENABLED variable. */
  usesLegacyNewsFlag: boolean;
  provider: string;
  model: string | null;
  /** Presence only — the key itself is never serialised by the API. */
  apiKeyConfigured: boolean;
  autoPublish: boolean;
  dailyLimit: number;
  batchSize: number;
  promptVersion: string;
  semanticPolicyVersion: string;
  minimumSemanticConfidence: number;
  runs: Record<string, unknown>[];
};

export const getGenerationStatus = cache(async (): Promise<GenerationStatus> =>
  adminNewsRequest<GenerationStatus>("/admin/news/generation/status"));

export type IngestOverview = {
  statuses: Record<IngestStatus, number>;
  relevancePolicyVersion: string;
  candidateThreshold: number;
  confidentThreshold: number;
  runs: Record<string, unknown>[];
};

export const getIncomingItems = cache(async (status?: IngestStatus): Promise<IngestItem[]> =>
  adminNewsRequest<IngestItem[]>(`/admin/news/incoming${status ? `?status=${status}` : ""}`));

export const getIncomingOverview = cache(async (): Promise<IngestOverview> =>
  adminNewsRequest<IngestOverview>("/admin/news/incoming/counts"));

export type AdminOverview = {
  occupations: number;
  tasks: number;
  skills: number;
  scored: number;
  pending: number;
  errors: number;
  completedImports: number;
  failedImports: number;
  latestRecalculation: string | null;
  marketOccupations: number;
  scoreCoverage: number;
  marketCoverage: number;
  activeModel: { id: number; version: string; description: string; replacementConfig: Record<string, number>; createdAt: string } | null;
  latestImport: Record<string, unknown> | null;
  latestCapability: { name: string; version: string; capabilityLevel: number; validFrom: string } | null;
};

export type AdminScores = {
  summary: { queued: number; running: number; completedToday: number; failed: number };
  jobs: Array<Record<string, unknown>>;
};

export type AdminPhase4a = {
  cohort: {
    id: number; cohortVersion: string; name: string; description: string; status: string;
    targetOccupationCount: number; mappingRunId: number; mappingRunVersion: string;
    mappingProvider: string; mappingModel: string; promptVersion: string;
    prohibitedInputAttestation: boolean; inputTaskCount: number; outputTaskCount: number;
    scoringEligibleMappings: number; excludedMappings: number; scopePolicy: Record<string, unknown>;
  };
  runs: Array<{
    id: number; runVersion: string; runKind: string; methodologyPhase: "4A" | "4B"; capabilityFitFormula: string;
    automationFormula: string; augmentationFormula: string; occupationFormula: string;
    mappingRunVersion: string; frontierTrack: string; dependencyHash: string;
    newAiMappingCalls: number; reusedMappingCount: number; taskAssessmentCount: number;
    occupationScoreCount: number; reconciliationStatus: string;
    replayMatchesPrevious: boolean | null; previousRunVersion: string | null;
    baselineRunVersion: string | null; proxyModelVersion: string | null; createdAt: string;
  }>;
  taskFormulas: Array<{ formulaType: string; formulaVersion: string; name: string; description: string; parameters: Record<string, unknown>; status: string }>;
  occupationFormulas: Array<{ formulaVersion: string; name: string; description: string; parameters: Record<string, unknown>; status: string }>;
  occupations: Array<{
    pilotOccupationId: number; requestedName: string; occupationCode: string; sourceTitle: string;
    cohortOrder: number; selectionStatus: string; substitutionReason: string | null;
    readinessSnapshot: Record<string, unknown>; readinessWarnings: Array<Record<string, unknown>>;
    sourceTaskCount: number; mappedTaskCount: number; excludedTaskCount: number;
    weightingEligibleTaskCount: number; weightedTaskCoverage: number; aiExposure: number;
    replacementRisk: number; confidence: number; methodologyPhase: "4A" | "4B";
    coverageGateStatus: string; confidencePenalty: number; scaleEligible: boolean;
    baselineAiExposure: number | null; baselineReplacementRisk: number | null; baselineConfidence: number | null;
    adoptionPressure: number | null; labourMarketResilience: number | null; proxyConfidence: number | null;
    proxyDomainValues: Record<string, { value: number; confidence: number }> | null;
    proxyComponentContributions: Record<string, unknown> | null; proxyExactInputs: Record<string, unknown> | null;
    proxyWarnings: Array<Record<string, unknown>> | null; proxyReconciliation: Record<string, unknown> | null;
    proxyInputHash: string | null; proxyModelVersion: string | null;
    factorContributions: Array<{ factor: string; value: number; weight: number; weightedContribution: number; placeholder: boolean; provisionalProxy?: boolean; proxyModelVersion?: string | null }>;
    taskContributions: Array<Record<string, unknown>>; exactInputs: Record<string, unknown>;
    warnings: Array<Record<string, unknown>>; reconciliation: Record<string, unknown>; inputHash: string;
  }>;
  tasks: Array<{
    id: number; pilotOccupationId: number; onetTaskId: number; taskStatement: string;
    importanceScore: number | null; frequencyScore: number | null; weightingEligible: boolean;
    aiCapabilityFit: number; automationFeasibility: number; augmentationPotential: number;
    taskAiExposure: number; confidence: number; mappingConfidence: number; ambiguityState: string;
    methodologyPhase: "4A" | "4B"; proxyConfidencePenalty: number;
    capabilityContributions: Array<{
      slug: string; name: string; weight: number; requiredLevel: number; currentCommercialAI: number;
      capabilityMatch: number; criticalCapability: boolean; bottleneckCap: number | null;
      mappingConfidence: number; frontierConfidence: number; frontierEvidenceIds: number[];
      weightedLogContribution: number; rationale: string; evidence: Array<Record<string, unknown>>;
    }>;
    constraintContributions: Array<{
      slug: string; level: number; fixedWeight: number; burdenContribution: number;
      explicitlyMapped: boolean; mappingConfidence: number | null; criticalConstraint: boolean;
      bottleneckCap: number | null; mappingEvidence: Array<Record<string, unknown>>;
      source: string; proxyDomain?: string; transformedLevel: number;
    }>;
    exactInputs: Record<string, unknown>; warnings: Array<Record<string, unknown>>;
    reconciliation: Record<string, unknown>; inputHash: string;
  }>;
  excludedTasks: Array<{
    pilotOccupationId: number; onetTaskId: number; taskStatement: string; ambiguityState: string;
    mappingConfidence: number; failureReasons: Array<Record<string, unknown>>; validationStatus: string; reviewState: string;
  }>;
  frontierEvidence: Array<{
    id: number; capabilitySlug: string; capabilityName: string; capabilityScore: number;
    capabilityConfidence: number; sourceTier: string; sourceType: string; providerName: string | null;
    modelName: string | null; modelVersion: string | null; evidenceDate: string;
    benchmarkName: string; reportedResult: string; sourceReference: string; rationale: string; confidence: number;
  }>;
  proxyModels: Array<{
    id: number; modelVersion: string; name: string; description: string; parameters: Record<string, unknown>;
    status: string; provenance: Record<string, unknown>; sourceName: string; createdAt: string;
  }>;
  diagnostics: Array<{
    metricScope: "task" | "occupation"; metricName: string;
    baselineSummary: { count: number; minimum: number; median: number; maximum: number; mean: number; standardDeviation: number; atOrAbove90: number; atOrAbove95: number };
    calibratedSummary: { count: number; minimum: number; median: number; maximum: number; mean: number; standardDeviation: number; atOrAbove90: number; atOrAbove95: number };
    deltaSummary: { mean: number; median: number; standardDeviation: number; atOrAbove90: number; atOrAbove95: number };
    reconciliation: { baselineCount: number; calibratedCount: number; passed: boolean };
    baselineRunVersion: string; calibrationRunVersion: string;
  }>;
  isolation: {
    productionOccupationScoreRows: number; legacyTaskScoreRows: number; technicalFrontierValues: number;
    pilotScoreRows: number; pilotTaskAssessmentRows: number;
  };
};

export type AdminPhase4c = {
  cohort: {
    id: number; cohortVersion: string; name: string; description: string; status: string;
    retainedOccupations: number; addedOccupations: number; totalOccupationCount: number;
    minimumWeightedCoverage: number; newMappingRunVersion: string; newMappingRows: number;
    reusedMappings: number; generatedEligibleMappings: number; insufficientMappingAttempts: number;
    unmappedAfterGate: number; sourceTasks: number; prohibitedInputAttestation: boolean;
    inferenceConfiguration: Record<string, unknown>; scopePolicy: Record<string, unknown>;
  };
  runs: Array<{
    id: number; runVersion: string; runKind: string; mappingScopeHash: string; dependencyHash: string;
    newMappingCount: number; reusedMappingCount: number; externalAiCalls: number;
    taskAssessmentCount: number; occupationScoreCount: number; reconciliationStatus: string;
    replayMatchesPrevious: boolean | null; previousRunVersion: string | null;
    capabilityFitFormula: string; automationFormula: string; augmentationFormula: string;
    occupationFormula: string; proxyModelVersion: string; frontierTrack: string;
  }>;
  occupations: Array<{
    validationOccupationId: number; occupationCode: string; title: string; cohortOrder: number;
    cohortRole: "retained_phase4a" | "added_validation"; stressDimensions: string[];
    selectionRationale: string; expectedProxyBehavior: Record<string, string>;
    sourceTasks: number; reused: number; generated: number; insufficient: number; afterGate: number;
    sourceTaskCount: number; mappedTaskCount: number; excludedTaskCount: number;
    weightedTaskCoverage: number; aiExposure: number; replacementRisk: number; confidence: number;
    coverageGateStatus: string; confidencePenalty: number; scaleEligible: boolean;
    adoptionPressure: number; labourMarketResilience: number; proxyConfidence: number;
    domainValues: Record<string, { value: number; confidence: number }>;
    componentContributions: Record<string, unknown>; proxyExactInputs: Record<string, unknown>;
    proxyWarnings: Array<Record<string, unknown>>; proxyReconciliation: { passed: boolean };
    proxyInputHash: string; proxyModelVersion: string;
  }>;
  pairwiseResults: Array<{
    expectationId: number; expectationVersion: string; proxyMetric: string;
    higherOccupationCode: string; higherOccupationTitle: string;
    lowerOccupationCode: string; lowerOccupationTitle: string;
    minimumDelta: number; rationale: string; higherValue: number; lowerValue: number;
    observedDelta: number; passed: boolean; severity: "pass" | "warning" | "failure"; finding: string;
  }>;
  absoluteResults: Array<{
    occupationCode: string; occupationTitle: string; proxyMetric: string; expectedBand: string;
    observedValue: number; passed: boolean; thresholdPolicy: string;
  }>;
  isolation: {
    productionOccupationScoreRows: number; productionTaskScoreRows: number;
    phase4cScoreRows: number; phase4cTaskAssessmentRows: number; runsWithAiCalls: number;
  };
};

export type AdminImports = {
  summary: { pending: number; running: number; complete: number; failed: number };
  runs: Array<Record<string, unknown>>;
  onetCoverage: {
    sourceVersion: string | null;
    occupations: number;
    productLinks: number;
    alternateTitles: number;
    sourceTitles: number;
    scales: number;
    sourceTaxonomies: number;
    sourceTaxonomyNodes: number;
    taxonomyMemberships: number;
    successionMappings: number;
    tasks: number;
    taskRatings: number;
    skillRatings: number;
    abilityRatings: number;
    workActivityRatings: number;
    workContextRatings: number;
    relatedOccupations: number;
    tasksMissingImportance: number;
    tasksMissingFrequency: number;
    weightingEligibleTasks: number;
    weightingIneligibleTasks: number;
    incompleteDomainRows: number;
    occupationsWithoutTasks: number;
    orphanTaskRatings: number;
    orphanElementRatings: number;
    currentSourceRecords: number;
    missingSkillOccupations: Array<{ onetSocCode: string; title: string }>;
    incompleteDomains: Array<{
      onetSocCode: string;
      title: string;
      domain: string;
      coverageStatus: "partial" | "missing";
      entityCount: number;
      ratingCount: number;
      issues: Array<Record<string, unknown>>;
    }>;
    incompleteDomainSummary: Array<{ domain: string; coverageStatus: string; occupations: number }>;
    promotionMatrix: {
      sourceImported: number;
      normalized: number;
      identityResolved: number;
      scoringReady: number;
      insufficientForScoring: number;
      identityReviewRequired: number;
      partialData: number;
      publicReady: number;
      public: number;
    };
    lifecycleStates: Array<{ lifecycleState: string; occupations: number }>;
    identityResolutions: Array<{ resolutionType: string; reviewStatus: string; mappings: number }>;
    latestRun: Record<string, unknown> | null;
    relationshipChecksPass: boolean;
  };
};

export type AdminSystem = {
  services: { publicApi: boolean; postgresql: boolean; redisQueue: boolean };
  scoreStore: { professionPages: number; scoreSnapshots: number; latestScore: string | null };
  environment: string;
};

export type AdminArchetypes = {
  featureFlag: { flagKey: string; layerVersion: string; enabled: boolean; productionAllowed: boolean; configuration: Record<string, unknown> };
  model: null | {
    id: number; modelVersion: string; name: string; description: string; status: string;
    sourceVersion: string; algorithm: string; clusterCount: number; featureSchema: Record<string, unknown>;
    discoveryConfiguration: Record<string, unknown>; sourceInputHash: string; implementationHash: string;
  };
  archetypes: Array<{
    id: number; archetypeCode: string; name: string; description: string; interpretationStatus: string;
    memberCount: number; secondaryMemberships: number; topFeatures: Array<{ label: string; centroidZ: number }>;
    representativeOccupations: Array<{ occupationCode: string; title: string; distance: number }>;
    qualityMetrics: { meanNearestDistance: number; meanSeparation: number; meanFeatureCompleteness: number; singleton: boolean };
    baselines: Record<string, { value: number; confidence: number; supportingOccupations: number; dispersion: number; formula: string }>;
  }>;
  runs: Array<{
    id: number; runVersion: string; runKind: string; occupationCount: number; taskAssessmentCount: number;
    externalAiCalls: number; regeneratedMappingCount: number; reconciliationStatus: string;
    replayMatchesPrevious: boolean | null; baselineRunVersion: string; previousRunVersion: string | null;
    dependencyHash: string;
  }>;
  occupations: Array<{
    occupationCode: string; title: string; primaryCode: string; primaryName: string;
    primaryStrength: number; primaryConfidence: number; secondaryCode: string | null;
    adjustments: Record<string, { baseline: number; sourceEvidence: number | null; evidenceConfidence: number;
      priorWeight: number; adjustment: number; result: number; resultConfidence: number; formula: string;
      warnings: Array<Record<string, unknown>>; reconciliation: Record<string, unknown> }>;
    aiExposure: number; replacementRisk: number; confidence: number; weightedTaskCoverage: number;
    coverageGateStatus: string; scaleEligible: boolean; aiExposureDelta: number;
    replacementRiskDelta: number; confidenceDelta: number; warnings: Array<Record<string, unknown>>;
  }>;
  validations: Array<{
    validationType: string; validationKey: string; structuralDimension: string;
    baselineOutcome: string; archetypeOutcome: string; baselineValue: Record<string, number | string>;
    archetypeValue: Record<string, number | string>; improved: boolean; regressed: boolean; finding: string;
  }>;
  isolation: { productionOccupationScoreRows: number; productionTaskScoreRows: number;
    pilotScoreRows: number; pilotTaskRows: number; runsWithAiCalls: number; runsWithRegeneratedMappings: number };
};

export type AdminPhase4d = {
  models: Array<{
    id: number; modelVersion: string; name: string; description: string; status: string;
    sourceVersion: string; reconstructedFamilies: string[]; formulaParameters: Record<string, unknown>;
    missingDataPolicy: Record<string, unknown>; implementationHash: string; createdAt: string;
  }>;
  runs: Array<{
    id: number; runVersion: string; runKind: string; occupationCount: number; taskAssessmentCount: number;
    externalAiCalls: number; regeneratedMappingCount: number; archetypeScoringEnabled: boolean;
    productionScoreWrites: number; dependencyHash: string; reconciliationStatus: string;
    replayMatchesPrevious: boolean | null; previousRunVersion: string | null; baselineRunVersion: string;
  }>;
  occupations: Array<{
    occupationCode: string; title: string; proxySnapshotId: number;
    physicalPresence: number; environmentVariability: number; accountability: number;
    consequenceSeverity: number; proxyConfidence: number;
    familyValues: Record<string, { value: number; confidence: number; formulaVersion: string;
      components: Array<Record<string, unknown>>; clinicalComponents?: Array<Record<string, unknown>>;
      clinicalGate?: Record<string, unknown>; clinicalGatePassed?: boolean; reconciliation: Record<string, unknown> }>;
    proxyExactInputs: Record<string, unknown>; proxyWarnings: Array<Record<string, unknown>>;
    proxyReconciliation: Record<string, unknown>; proxyInputHash: string;
    aiExposure: number; replacementRisk: number; confidence: number; weightedTaskCoverage: number;
    coverageGateStatus: string; scaleEligible: boolean; aiExposureDelta: number;
    replacementRiskDelta: number; confidenceDelta: number;
  }>;
  validations: Array<{
    validationType: string; validationKey: string; proxyFamily: string;
    baselineOutcome: string; phase4dOutcome: string; baselineValue: Record<string, number | string>;
    phase4dValue: Record<string, number | string>; improved: boolean; regressed: boolean; finding: string;
  }>;
  summary: { baselineAbsoluteFailures: number; phase4dAbsoluteFailures: number;
    pairwisePasses: number; pairwiseWarnings: number; pairwiseReversals: number;
    improvements: number; regressions: number; scaleEligible: number; coverageBlocked: number;
    meanAiExposureDelta: number; meanReplacementRiskDelta: number; meanConfidenceDelta: number };
  isolation: { productionOccupationScoreRows: number; productionTaskScoreRows: number;
    phase4dScoreRows: number; phase4dTaskRows: number; runsWithAiCalls: number;
    runsWithRegeneratedMappings: number; runsWithProductionWrites: number; archetypeLayerEnabled: boolean };
};

export type AdminPhase5 = {
  namespace: { namespaceVersion: string; occupationPopulationHash: string; anomalyPolicyVersion: string };
  runs: Array<{
    id: number; runVersion: string; runKind: string; attemptedOccupationCount: number;
    scoredOccupationCount: number; blockedOccupationCount: number; taskAssessmentCount: number;
    newMappingCount: number; reusedExactMappingCount: number; reusedHashMappingCount: number;
    externalAiCalls: number; estimatedAiTokens: number; localComputeMilliseconds: number;
    productionScoreWrites: number; publicActivations: number; archetypeScoringEnabled: boolean;
    dependencyHash: string; reconciliationStatus: string; replayMatchesPrevious: boolean | null;
    previousRunVersion: string | null; createdAt: string;
  }>;
  report: null | {
    reportVersion: string;
    corpusSummary: { totalSourceOccupations: number; scoringReadyOccupationsAttempted: number;
      candidateCalculationsCompleted: number; reviewReadyOccupations: number; blockedOccupations: number;
      coverageBlockedOccupations: number; confidenceBlockedOccupations: number;
      publicActivations: number; productionScoreWrites: number };
    distributions: Record<string, { count: number; minimum: number; p05: number; p10: number;
      p25: number; median: number; p75: number; p90: number; p95: number; maximum: number;
      mean: number; standardDeviation: number }>;
    percentiles: Record<string, unknown>; correlation: { metric: string; aiExposureVsReplacementRisk: number; count: number };
    extremes: Record<string, Array<Record<string, string | number>>>; socOutliers: Array<Record<string, unknown>>;
    provisionalImpact: { flagThreshold: number; flaggedOccupations: number; highestImpact: Array<Record<string, unknown>> };
    anomalySummary: { totalFindings: number; occupationsFlagged: number; bySeverity: Record<string, number>; byType: Record<string, number> };
    mappingReuseSummary: Record<string, number>;
    recommendedLaunchCohort: { status: string; targetCount: number; recommendedCount: number;
      selectionPolicy: Record<string, unknown>; occupations: Array<Record<string, string | number>>; activated: boolean };
    exactReconciliation: Record<string, unknown>; inputHash: string; createdAt: string;
  };
  occupations: Array<{
    candidateOccupationId: number; occupationCode: string; title: string; socMajorGroup: string;
    calculationStatus: string; aiExposure: number; replacementRisk: number; confidence: number;
    weightedTaskCoverage: number; sourceTaskCount: number; eligibleTaskCount: number;
    excludedTaskCount: number; weightingEligibleTaskCount: number; coverageGateStatus: string;
    confidenceGateStatus: string; candidateStatus: "review_ready" | "blocked";
    publicActivationEligible: false; topExposureTasks: Array<Record<string, unknown>>;
    topAutomationConstraints: Array<Record<string, unknown>>; augmentationHeavyTasks: Array<Record<string, unknown>>;
    structuralProxyInputs: Record<string, unknown>; provisionalSensitivity: Record<string, number | string | Record<string, string>>;
    factorContributions: Array<Record<string, unknown>>; taskContributions: Array<Record<string, unknown>>;
    exactInputs: Record<string, unknown>; warnings: Array<Record<string, unknown>>;
    blockingReasons: Array<Record<string, unknown>>; reconciliation: Record<string, unknown>; inputHash: string;
    physicalPresence: number; environmentVariability: number; accountability: number;
    consequenceSeverity: number; humanDependency: number; regulation: number;
    adoptionPressure: number; labourMarketResilience: number; proxyConfidence: number;
    familyValues: Record<string, unknown>; proxyComponentContributions: Record<string, unknown>;
    proxyExactInputs: Record<string, unknown>; proxyWarnings: Array<Record<string, unknown>>;
    proxyReconciliation: Record<string, unknown>; provisionalFlags: Record<string, unknown>;
    proxyInputHash: string; anomalyCount: number; anomalyTypes: string[]; anomalySeverities: string[];
  }>;
  anomalies: Array<{ id: number; anomalyType: string; severity: string; metricValues: Record<string, unknown>;
    thresholdValues: Record<string, unknown>; explanation: string; reviewStatus: string;
    occupationCode: string | null; title: string | null }>;
  totalFiltered: number;
  filters: Record<string, string | number | boolean | null>;
  isolation: { productionOccupationScoreRows: number; productionTaskScoreRows: number;
    publicOccupationRows: number; runsWithProductionWrites: number; runsWithPublicActivations: number;
    archetypeLayerEnabled: boolean };
};

export type AdminAiEnrichment = {
  taxonomies: Array<{ id: number; version: string; name: string; description: string; status: string; methodologyVersion: string; definitions: number }>;
  capabilities: Array<{ id: number; taxonomyVersion: string; slug: string; name: string; description: string; capabilityCategory: string; definitionVersion: number }>;
  mappingSets: Array<{
    id: number; onetTaskId: number; occupationCode: string; occupationTitle: string;
    taskStatement: string; taxonomyVersion: string; mappingSetVersion: string;
    mappingMethod: string; mappingMethodVersion: string; reviewState: string;
    isTestFixture: boolean; weightTotal: number;
    mappings: Array<{ capabilitySlug: string; capabilityName: string; weight: number; requiredCapabilityLevel: number; confidence: number; rationale: string }>;
  }>;
  environmentTaxonomies: Array<{ id: number; version: string; name: string; description: string; status: string; definitions: number }>;
  constraints: Array<{ id: number; taxonomyVersion: string; slug: string; name: string; description: string; constraintCategory: string; valueSemantics: string; definitionVersion: number; testMappings: number }>;
  constraintMappings: Array<{ id: number; onetTaskId: number; occupationCode: string; taskStatement: string; constraintSlug: string; constraintName: string; constraintLevel: number; confidence: number; mappingVersion: string; mappingMethod: string; reviewState: string; isTestFixture: boolean }>;
  snapshots: Array<Record<string, unknown>>;
  assessments: Array<Record<string, unknown>>;
  rubrics: Array<{
    id: number; version: string; name: string; description: string; status: string;
    capabilityTaxonomyVersion: string; environmentTaxonomyVersion: string;
    minimumMeaningfulWeight: number; dominantWeightThreshold: number; maximumCapabilitiesPerTask: number;
    minimumMeaningfulRequirementLevel: number; minimumMeaningfulConstraintLevel: number;
    ambiguityConfidenceCeiling: number; normalizationTolerance: number; documentationPath: string;
  }>;
  capabilityAnchors: Array<{ slug: string; name: string; anchors: Array<{ value: number; label: string; description: string; evidenceRule: string }> }>;
  constraintAnchors: Array<{ slug: string; name: string; anchors: Array<{ value: number; label: string; description: string; evidenceRule: string }> }>;
  confidenceStates: Array<{ code: string; name: string; minimumConfidence: number; maximumConfidence: number; definition: string; reviewRule: string }>;
  goldDatasets: Array<{
    id: number; datasetVersion: string; name: string; description: string; status: string;
    expectedTaskCount: number; isTestFixture: boolean; createdBy: string; reviewedBy: string;
    reviewedAt: string; items: number; mappableItems: number; insufficientItems: number; ambiguousItems: number;
  }>;
  goldItems: Array<{
    id: number; onetTaskId: number; occupationCode: string; taskStatement: string; disposition: string;
    dispositionRationale: string; taskStatementHash: string; reviewerProvenance: Array<Record<string, string>>;
    reviewedAt: string; capabilityRequirements: number; environmentConstraints: number; capabilityWeightTotal: number;
  }>;
  goldComparisons: Array<{
    candidateMappingSetId: number; onetTaskId: number;
    report: { summary: {
      meanAbsoluteWeightDeviation: number; meanAbsoluteLevelDeviation: number;
      meanAbsoluteCapabilityConfidenceDeviation: number; meanAbsoluteConstraintDeviation: number;
      meanAbsoluteConstraintConfidenceDeviation: number; missingCapabilities: number; extraCapabilities: number;
      candidateWeightTotal: number; thresholdViolations: number; maximumCapabilityCountExceeded: boolean;
    } };
  }>;
  rubricValidation: Array<{ rubricId: number; version: string; status: string; capabilityAnchors: number; constraintAnchors: number; confidenceStates: number; goldDatasets: number; goldItems: number; invalidGoldDatasets: number; rubricValid: boolean }>;
  mapperBenchmarks: Array<{
    goldDatasetId: number; datasetVersion: string; status: string; tasks: number; occupations: number;
    mappableTasks: number; ambiguousTasks: number; insufficientTasks: number; humanReviewedTasks: number;
    independentlyHumanReviewedTasks: number; adjudicatedTasks: number;
  }>;
  candidateRuns: Array<{
    id: number; runVersion: string; mapperName: string; mapperVersion: string; mapperKind: string;
    status: string; prohibitedInputAttestation: boolean; inputTaskCount: number; outputTaskCount: number;
    mappableTasks: number; ambiguousTasks: number; insufficientTasks: number; invalidTasks: number;
    verificationStatus: string | null; verificationVersion: string | null;
    verificationSummary: Record<string, number | boolean> | null;
    evaluationStatus: string | null; evaluationVersion: string | null;
    evaluationMetrics: Record<string, number> | null; gateResults: Record<string, boolean> | null;
  }>;
  acceptanceGates: Array<{
    id: number; gateVersion: string; name: string; status: string; minimumHumanReviewedTasks: number;
    minimumOccupations: number; minimumCapabilitySetAgreement: number; maximumMeanWeightDeviation: number;
    maximumMeanRequirementLevelDeviation: number; maximumMeanConstraintDeviation: number;
    minimumConfidenceAgreement: number; maximumExtraDimensionRate: number;
    maximumMissingDimensionRate: number; maximumFalseInferenceRate: number;
    requireIndependentVerification: boolean;
  }>;
  mvpEvidencePolicies: Array<{
    policyId: number; policyVersion: string; status: string; policyScope: string; name: string; description: string;
    minimumMappingConfidence: number; minimumDimensionConfidence: number;
    minimumEvidencedDimensionCoverage: number; minimumRationaleCoverage: number;
    minimumCapabilityDimensions: number; maximumCapabilityDimensions: number;
    allowAmbiguousScope: boolean; allowInsufficientDescription: boolean;
    requireModelProvenance: boolean; requirePromptProvenance: boolean;
    requireIndependentStructuralValidation: boolean; allowedScoringReviewStates: string[];
    aiMappingRuns: number; aiTaskMappings: number; validationEvents: number;
    scoringEligibleMappings: number; failedMappings: number; humanGoldRequired: boolean;
  }>;
  frontierIndexes: Array<{
    indexVersionId: number; indexVersion: string; status: string; expectedCapabilityCount: number;
    assessmentTracks: number; populatedTracks: number; capabilityValues: number;
    commerciallyDeployableValues: number; technicalFrontierValues: number;
    provisionalValues: number; evidenceRecords: number; indexValid: boolean;
    name: string; description: string; taxonomyVersion: string; methodologyVersion: string;
    scoreScaleMin: number; scoreScaleMax: number; asOfDate: string | null;
  }>;
  frontierTracks: Array<{
    id: number; indexVersionId: number; indexVersion: string; trackCode: string; name: string;
    description: string; status: string; expectedCapabilityCount: number; assessmentDate: string | null;
    methodologyNotes: string; provenance: Record<string, unknown>; createdAt: string;
    capabilityValues: number; evidenceRecords: number;
  }>;
  frontierEntries: Array<{
    id: number; indexVersion: string; trackCode: string; trackName: string;
    capabilitySlug: string; capabilityName: string; capabilityCategory: string;
    capabilityScore: number; confidence: number; assessmentStatus: string; assessmentDate: string;
    sourceType: string; providerName: string | null; modelName: string | null; modelVersion: string | null;
    observedAt: string; rationale: string; benchmarkEvidence: Array<Record<string, unknown>>;
    provenance: Record<string, unknown>;
    evidenceRecords: Array<{
      id: number; sourceTier: string; sourceType: string; providerName: string | null;
      modelName: string | null; modelVersion: string | null; evidenceDate: string;
      benchmarkName: string; reportedResult: string; sourceReference: string;
      rationale: string; confidence: number | null; evidencePayload: Record<string, unknown>;
      provenance: Record<string, unknown>;
    }>;
  }>;
  validation: { invalidMappingSets: number; invalidSnapshots: number; invalidConstraintMappings: number; invalidAssessments: number; taskAssessments: number; benchmarkScores: number; productionScoreRows: number; legacyTaskAiScoreRows: number };
};

export const getAdminOverview = cache(async (): Promise<AdminOverview> =>
  adminRequest<AdminOverview>("/admin/overview"));

export const getAdminScores = cache(async (): Promise<AdminScores> =>
  adminRequest<AdminScores>("/admin/scores"));

export const getAdminPhase4a = cache(async (): Promise<AdminPhase4a> =>
  adminRequest<AdminPhase4a>("/admin/phase4a"));

export const getAdminPhase4c = cache(async (): Promise<AdminPhase4c> =>
  adminRequest<AdminPhase4c>("/admin/phase4c"));

export const getAdminArchetypes = cache(async (): Promise<AdminArchetypes> =>
  adminRequest<AdminArchetypes>("/admin/archetypes"));

export const getAdminPhase4d = cache(async (): Promise<AdminPhase4d> =>
  adminRequest<AdminPhase4d>("/admin/phase4d"));

export async function getAdminPhase5(query = ""): Promise<AdminPhase5> {
  return adminRequest<AdminPhase5>(`/admin/phase5${query ? `?${query}` : ""}`);
}

export const getAdminImports = cache(async (): Promise<AdminImports> =>
  adminRequest<AdminImports>("/admin/imports"));

export const getAdminSystem = cache(async (): Promise<AdminSystem> =>
  adminRequest<AdminSystem>("/admin/system"));

export const getAdminAiEnrichment = cache(async (): Promise<AdminAiEnrichment> =>
  adminRequest<AdminAiEnrichment>("/admin/ai-enrichment"));

export const getScoreDerivation = cache(async (slug: string): Promise<ScoreDerivation | null> => {
  try {
    return await adminRequest<ScoreDerivation>(`/admin/jobs/${encodeURIComponent(slug)}/derivation`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

export type ProductionScoreOverview = {
  totals: Record<string, string | number | null>;
  promotionRuns: Record<string, unknown>[];
  currentSnapshots: Record<string, unknown>[];
  consistencyCounts: { consistencyState: string; total: number }[];
  triageRuns: Record<string, unknown>[];
};

export type ProductionScoreDetail = {
  snapshot: Record<string, unknown>;
  candidate: Record<string, unknown> | null;
  factorContributions: Record<string, unknown>[];
  taskContributions: Record<string, unknown>[];
  recomputedReconciliation: Record<string, number | boolean>;
  provisionalWeightShare: number;
};

export const getProductionScores = cache(async (): Promise<ProductionScoreOverview> =>
  adminRequest<ProductionScoreOverview>("/admin/production-scores"));

export const getProductionScoreDetail = cache(async (snapshotId: string): Promise<ProductionScoreDetail> =>
  adminRequest<ProductionScoreDetail>(`/admin/production-scores/${snapshotId}`));
