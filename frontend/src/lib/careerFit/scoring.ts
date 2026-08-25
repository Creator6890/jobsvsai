import type { Occupation } from "@/types/occupation";
import {
  DIMENSIONS,
  DIMENSION_KEYS,
  getStrengthBand,
  type DimensionKey,
  type StrengthBand,
} from "./dimensions";
import { ASSESSMENT_QUESTIONS } from "./questions";

export type UserProfile = {
  dimensionScores: Record<DimensionKey, number>;
  dimensionBands: Record<DimensionKey, StrengthBand>;
  topStrengths: DimensionKey[];
  summaryHeadline: string;
  summaryNarrative: string;
};

export type CareerMatch = {
  occupation: Occupation;
  careerFit: number;
  keyStrengths: DimensionKey[];
  whyFit: string;
  considerations: string[];
};

export type SortOption = "fit" | "risk" | "exposure";

// ---------------------------------------------------------------------------
// 1. Profile Calculation
// ---------------------------------------------------------------------------

export function calculateProfile(answers: Record<number, number>): UserProfile {
  const dimensionWeightedSums: Record<DimensionKey, number> = {
    analytical: 0,
    creativity: 0,
    communication: 0,
    people: 0,
    practical: 0,
    organization: 0,
    technology: 0,
    leadership: 0,
  };

  const dimensionTotalWeights: Record<DimensionKey, number> = {
    analytical: 0,
    creativity: 0,
    communication: 0,
    people: 0,
    practical: 0,
    organization: 0,
    technology: 0,
    leadership: 0,
  };

  for (const question of ASSESSMENT_QUESTIONS) {
    // Default unanswered questions to 3 (neutral)
    const rawAnswer = answers[question.id] ?? 3;
    // Bound answer between 1 and 5
    const clampedAnswer = Math.max(1, Math.min(5, rawAnswer));
    // Normalize response from [1..5] to [0.0..1.0]
    const normalizedResponse = (clampedAnswer - 1) / 4.0;

    // Primary dimension
    dimensionWeightedSums[question.primaryDimension] +=
      normalizedResponse * question.primaryWeight;
    dimensionTotalWeights[question.primaryDimension] += question.primaryWeight;

    // Secondary dimension
    if (question.secondaryDimension && question.secondaryWeight) {
      dimensionWeightedSums[question.secondaryDimension] +=
        normalizedResponse * question.secondaryWeight;
      dimensionTotalWeights[question.secondaryDimension] +=
        question.secondaryWeight;
    }
  }

  const dimensionScores: Record<DimensionKey, number> = {} as Record<
    DimensionKey,
    number
  >;
  const dimensionBands: Record<DimensionKey, StrengthBand> = {} as Record<
    DimensionKey,
    StrengthBand
  >;

  for (const key of DIMENSION_KEYS) {
    const totalWeight = dimensionTotalWeights[key] || 1.0;
    const score = Math.round((dimensionWeightedSums[key] / totalWeight) * 100);
    // Ensure strict [0..100] clamp
    const clampedScore = Math.max(0, Math.min(100, score));
    dimensionScores[key] = clampedScore;
    dimensionBands[key] = getStrengthBand(clampedScore);
  }

  // Sort dimensions by score descending to find top 3 strengths
  const sortedDimensions = [...DIMENSION_KEYS].sort(
    (a, b) => dimensionScores[b] - dimensionScores[a]
  );
  const topStrengths = sortedDimensions.slice(0, 3);

  const topLabels = topStrengths.map((k) => DIMENSIONS[k].label);
  const summaryHeadline = `${topLabels[0]} & ${topLabels[1]}`;
  const summaryNarrative = `Your assessment reveals strong aptitude in ${topLabels[0]} (${dimensionScores[topStrengths[0]]}/100), ${topLabels[1]} (${dimensionScores[topStrengths[1]]}/100), and ${topLabels[2]} (${dimensionScores[topStrengths[2]]}/100). Occupations requiring these core competencies will offer the highest day-to-day engagement and career velocity.`;

  return {
    dimensionScores,
    dimensionBands,
    topStrengths,
    summaryHeadline,
    summaryNarrative,
  };
}

// ---------------------------------------------------------------------------
// 2. Occupational Vector Derivation
// ---------------------------------------------------------------------------

// Baseline archetype vectors per SOC major category
const CATEGORY_ARCHETYPES: Record<string, Record<DimensionKey, number>> = {
  "Computer & Mathematical": {
    analytical: 90,
    creativity: 65,
    communication: 50,
    people: 35,
    practical: 20,
    organization: 75,
    technology: 95,
    leadership: 50,
  },
  "Architecture & Engineering": {
    analytical: 88,
    creativity: 70,
    communication: 55,
    people: 40,
    practical: 65,
    organization: 80,
    technology: 85,
    leadership: 60,
  },
  "Life, Physical, & Social Science": {
    analytical: 95,
    creativity: 60,
    communication: 65,
    people: 45,
    practical: 55,
    organization: 80,
    technology: 75,
    leadership: 55,
  },
  "Healthcare Practitioners & Technical": {
    analytical: 85,
    creativity: 40,
    communication: 75,
    people: 90,
    practical: 70,
    organization: 85,
    technology: 65,
    leadership: 65,
  },
  "Healthcare Support": {
    analytical: 45,
    creativity: 30,
    communication: 65,
    people: 90,
    practical: 75,
    organization: 70,
    technology: 40,
    leadership: 35,
  },
  "Business & Financial Operations": {
    analytical: 85,
    creativity: 45,
    communication: 75,
    people: 65,
    practical: 20,
    organization: 90,
    technology: 70,
    leadership: 70,
  },
  Management: {
    analytical: 75,
    creativity: 60,
    communication: 90,
    people: 85,
    practical: 25,
    organization: 85,
    technology: 60,
    leadership: 95,
  },
  "Arts, Design, Entertainment, Sports, & Media": {
    analytical: 40,
    creativity: 95,
    communication: 85,
    people: 60,
    practical: 45,
    organization: 50,
    technology: 65,
    leadership: 55,
  },
  "Educational Instruction & Library": {
    analytical: 70,
    creativity: 65,
    communication: 90,
    people: 90,
    practical: 30,
    organization: 75,
    technology: 55,
    leadership: 70,
  },
  Legal: {
    analytical: 92,
    creativity: 55,
    communication: 95,
    people: 70,
    practical: 15,
    organization: 90,
    technology: 55,
    leadership: 80,
  },
  "Community & Social Service": {
    analytical: 55,
    creativity: 50,
    communication: 85,
    people: 95,
    practical: 25,
    organization: 65,
    technology: 40,
    leadership: 65,
  },
  "Sales & Related": {
    analytical: 55,
    creativity: 55,
    communication: 90,
    people: 85,
    practical: 25,
    organization: 65,
    technology: 50,
    leadership: 75,
  },
  "Office & Administrative Support": {
    analytical: 50,
    creativity: 30,
    communication: 65,
    people: 60,
    practical: 30,
    organization: 90,
    technology: 60,
    leadership: 40,
  },
  "Protective Service": {
    analytical: 60,
    creativity: 30,
    communication: 70,
    people: 75,
    practical: 80,
    organization: 75,
    technology: 50,
    leadership: 75,
  },
  "Construction & Extraction": {
    analytical: 50,
    creativity: 35,
    communication: 35,
    people: 35,
    practical: 95,
    organization: 60,
    technology: 45,
    leadership: 50,
  },
  "Installation, Maintenance, & Repair": {
    analytical: 70,
    creativity: 35,
    communication: 40,
    people: 40,
    practical: 95,
    organization: 70,
    technology: 70,
    leadership: 45,
  },
  "Production / Manufacturing": {
    analytical: 50,
    creativity: 30,
    communication: 35,
    people: 30,
    practical: 90,
    organization: 75,
    technology: 55,
    leadership: 40,
  },
  "Transportation & Material Moving": {
    analytical: 40,
    creativity: 20,
    communication: 40,
    people: 35,
    practical: 85,
    organization: 70,
    technology: 45,
    leadership: 35,
  },
  "Food Preparation & Serving": {
    analytical: 30,
    creativity: 55,
    communication: 60,
    people: 75,
    practical: 85,
    organization: 65,
    technology: 25,
    leadership: 40,
  },
  "Personal Care & Service": {
    analytical: 35,
    creativity: 60,
    communication: 75,
    people: 90,
    practical: 70,
    organization: 60,
    technology: 30,
    leadership: 45,
  },
  "Farming, Fishing, & Forestry": {
    analytical: 45,
    creativity: 30,
    communication: 30,
    people: 30,
    practical: 95,
    organization: 55,
    technology: 40,
    leadership: 45,
  },
  "Building & Grounds Cleaning": {
    analytical: 25,
    creativity: 20,
    communication: 30,
    people: 35,
    practical: 90,
    organization: 55,
    technology: 25,
    leadership: 30,
  },
};

// Default fallback archetype
const DEFAULT_ARCHETYPE: Record<DimensionKey, number> = {
  analytical: 60,
  creativity: 50,
  communication: 60,
  people: 60,
  practical: 50,
  organization: 65,
  technology: 55,
  leadership: 55,
};

export function deriveOccupationVector(
  occupation: Occupation
): Record<DimensionKey, number> {
  const categoryMatch = Object.entries(CATEGORY_ARCHETYPES).find(([cat]) =>
    occupation.category.toLowerCase().includes(cat.toLowerCase().split(" ")[0])
  );
  const baseline = categoryMatch ? categoryMatch[1] : DEFAULT_ARCHETYPE;

  const vector: Record<DimensionKey, number> = { ...baseline };

  // 1. Calibrate practical with real physicalDependency
  if (typeof occupation.physicalDependency === "number") {
    vector.practical = Math.round(
      baseline.practical * 0.4 + occupation.physicalDependency * 0.6
    );
  }

  // 2. Calibrate people & communication with real humanDependency
  if (typeof occupation.humanDependency === "number") {
    vector.people = Math.round(
      baseline.people * 0.45 + occupation.humanDependency * 0.55
    );
    vector.communication = Math.round(
      baseline.communication * 0.55 + occupation.humanDependency * 0.45
    );
  }

  // 3. Keyword / title refinements for specialized domains
  const titleLower = occupation.title.toLowerCase();
  if (titleLower.includes("data") || titleLower.includes("statistician") || titleLower.includes("analyst") || titleLower.includes("scientist") || titleLower.includes("economist")) {
    vector.analytical = Math.min(100, vector.analytical + 12);
    vector.technology = Math.min(100, vector.technology + 10);
  }
  if (titleLower.includes("designer") || titleLower.includes("writer") || titleLower.includes("artist") || titleLower.includes("architect")) {
    vector.creativity = Math.min(100, vector.creativity + 15);
  }
  if (titleLower.includes("manager") || titleLower.includes("director") || titleLower.includes("executive") || titleLower.includes("chief")) {
    vector.leadership = Math.min(100, vector.leadership + 15);
    vector.organization = Math.min(100, vector.organization + 8);
  }
  if (titleLower.includes("nurse") || titleLower.includes("therapist") || titleLower.includes("counselor") || titleLower.includes("social worker")) {
    vector.people = Math.min(100, vector.people + 12);
  }
  if (titleLower.includes("developer") || titleLower.includes("programmer") || titleLower.includes("engineer") || titleLower.includes("cybersecurity")) {
    vector.technology = Math.min(100, vector.technology + 12);
    vector.analytical = Math.min(100, vector.analytical + 8);
  }

  // Ensure all values strictly bounded [0..100]
  for (const k of DIMENSION_KEYS) {
    vector[k] = Math.max(0, Math.min(100, vector[k]));
  }

  return vector;
}

// ---------------------------------------------------------------------------
// 3. Occupation Matching Algorithm
// ---------------------------------------------------------------------------

export function matchOccupations(
  userProfile: UserProfile,
  occupations: Occupation[],
  limit = 12
): CareerMatch[] {
  const matches: CareerMatch[] = [];

  for (const occ of occupations) {
    const occVector = deriveOccupationVector(occ);

    // Compute weighted Euclidean similarity emphasizing user's strong dimensions
    let totalWeight = 0;
    let weightedSquaredDiff = 0;

    for (const key of DIMENSION_KEYS) {
      const userScore = userProfile.dimensionScores[key];
      const occScore = occVector[key];

      // Give higher weight (1.6x) to dimensions where user scored High/Very High (>= 60)
      const weight = userScore >= 60 ? 1.6 : 1.0;
      totalWeight += weight;
      weightedSquaredDiff += weight * Math.pow(userScore - occScore, 2);
    }

    const meanSquaredError = weightedSquaredDiff / totalWeight;
    const rootMeanSquare = Math.sqrt(meanSquaredError);

    // RMS error ranges from 0 to ~60 in practical profiles. Scale to 0..100%
    const rawFit = Math.round(100 - (rootMeanSquare / 55) * 100);
    const careerFit = Math.max(10, Math.min(99, rawFit));

    // Find the top overlapping competencies for this specific pairing
    const keyStrengths = [...DIMENSION_KEYS]
      .filter(
        (k) =>
          userProfile.dimensionScores[k] >= 55 && occVector[k] >= 55
      )
      .sort(
        (a, b) =>
          userProfile.dimensionScores[b] +
          occVector[b] -
          (userProfile.dimensionScores[a] + occVector[a])
      )
      .slice(0, 3);

    // If no strong overlap found, use top user strengths
    const activeStrengths =
      keyStrengths.length >= 2 ? keyStrengths : userProfile.topStrengths;

    const strengthLabels = activeStrengths.map((k) => DIMENSIONS[k].label);
    const whyFit =
      strengthLabels.length >= 2
        ? `Strong alignment with your profile in ${strengthLabels[0]} and ${strengthLabels[1]}.`
        : `Matches your strength in ${strengthLabels[0]}.`;

    // Contextual considerations derived from underlying occupation metrics
    const considerations: string[] = [];

    if (occ.physicalDependency >= 65) {
      considerations.push(
        `High physical dependency (${occ.physicalDependency}/100) — requires tangible presence.`
      );
    }
    if (occ.humanDependency >= 75) {
      considerations.push(
        `Heavy interpersonal focus (${occ.humanDependency}/100) — relies on trust and human judgment.`
      );
    }
    if (occ.aiExposure >= 75) {
      considerations.push(
        `High AI exposure (${occ.aiExposure}/100) — involves tasks subject to software automation.`
      );
    } else if (occ.replacementRisk <= 35) {
      considerations.push(
        `High career resilience (${occ.replacementRisk}/100 risk) — insulated by human/physical barriers.`
      );
    }

    matches.push({
      occupation: occ,
      careerFit,
      keyStrengths: activeStrengths,
      whyFit,
      considerations,
    });
  }

  // Sort by careerFit descending, take top `limit`
  matches.sort((a, b) => b.careerFit - a.careerFit);
  return matches.slice(0, limit);
}

// ---------------------------------------------------------------------------
// 4. Sort / Filter Helper
// ---------------------------------------------------------------------------

export function sortMatches(
  matches: CareerMatch[],
  sortOption: SortOption
): CareerMatch[] {
  const cloned = [...matches];
  switch (sortOption) {
    case "fit":
      return cloned.sort((a, b) => b.careerFit - a.careerFit);
    case "risk":
      return cloned.sort(
        (a, b) => a.occupation.replacementRisk - b.occupation.replacementRisk
      );
    case "exposure":
      return cloned.sort(
        (a, b) => a.occupation.aiExposure - b.occupation.aiExposure
      );
  }
}
