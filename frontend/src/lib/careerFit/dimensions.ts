/** 8 Core Work-Strength Dimensions for Career Fit Assessment V1.
 *
 * Grounded in interpretable behavioral concepts (analytical reasoning, creativity,
 * communication, people orientation, practical work, organization, technology affinity,
 * and leadership). Avoids pseudo-scientific personality claims.
 */

export type DimensionKey =
  | "analytical"
  | "creativity"
  | "communication"
  | "people"
  | "practical"
  | "organization"
  | "technology"
  | "leadership";

export type DimensionDefinition = {
  key: DimensionKey;
  label: string;
  shortLabel: string;
  tagline: string;
  description: string;
  highTraitSummary: string;
};

export const DIMENSIONS: Record<DimensionKey, DimensionDefinition> = {
  analytical: {
    key: "analytical",
    label: "Analytical Reasoning",
    shortLabel: "Analytical",
    tagline: "Systematic problem solving, data evaluation, and logic",
    description:
      "Evaluating evidence, dissecting complex systems into constituent parts, identifying patterns, and making structured, objective decisions.",
    highTraitSummary:
      "Thrives when investigating cause-and-effect relationships, working with quantitative models, and testing hypotheses with data.",
  },
  creativity: {
    key: "creativity",
    label: "Creativity & Innovation",
    shortLabel: "Creativity",
    tagline: "Original concept generation, design, and inventive ideation",
    description:
      "Generating novel ideas, reimagining traditional workflows, visual/spatial expression, and synthesizing non-obvious solutions to open-ended challenges.",
    highTraitSummary:
      "Excels in ambiguous environments requiring innovative visual, narrative, or conceptual design rather than fixed templates.",
  },
  communication: {
    key: "communication",
    label: "Communication & Expression",
    shortLabel: "Communication",
    tagline: "Articulating complex ideas, writing, and presentation",
    description:
      "Translating specialized concepts into clear, engaging messages across written, verbal, and visual media to educate, persuade, or align stakeholders.",
    highTraitSummary:
      "Strong command of structured writing, public advocacy, documentation, and interpersonal storytelling.",
  },
  people: {
    key: "people",
    label: "People & Interpersonal",
    shortLabel: "People",
    tagline: "Empathy, relationship-building, care, and collaboration",
    description:
      "Understanding individual motivations, providing guidance or care, mediating conflicts, and cultivating trusted professional relationships.",
    highTraitSummary:
      "Deeply motivated by direct human connection, counseling, client support, patient care, or collaborative teamwork.",
  },
  practical: {
    key: "practical",
    label: "Practical & Hands-On",
    shortLabel: "Practical",
    tagline: "Tangible execution, machinery, tools, and physical craft",
    description:
      "Working with physical instruments, spatial construction, machinery, outdoor environments, and tangible materials where real-world manipulation is primary.",
    highTraitSummary:
      "Prefers tangible, physical outputs, tactile problem-solving, and environments requiring real-world spatial dexterity.",
  },
  organization: {
    key: "organization",
    label: "Organization & Structure",
    shortLabel: "Organization",
    tagline: "Process rigor, compliance, operational precision, and detail",
    description:
      "Maintaining meticulous accuracy, establishing reliable operational workflows, ensuring quality control, and managing complex logistics.",
    highTraitSummary:
      "High attention to operational detail, systematic record-keeping, regulatory compliance, and process optimization.",
  },
  technology: {
    key: "technology",
    label: "Technology Affinity",
    shortLabel: "Technology",
    tagline: "Digital architectures, software systems, and automation",
    description:
      "Leveraging modern software platforms, programming languages, system architectures, digital infrastructure, and automation tools.",
    highTraitSummary:
      "Naturally drawn to technical tooling, software engineering, computational workflows, and systems engineering.",
  },
  leadership: {
    key: "leadership",
    label: "Leadership & Strategy",
    shortLabel: "Leadership",
    tagline: "Strategic direction, decision-making, and team coordination",
    description:
      "Setting long-term priorities, guiding teams toward shared goals, taking responsibility under uncertainty, and managing resources effectively.",
    highTraitSummary:
      "Confident navigating organizational dynamics, taking decisive initiative, and aligning cross-functional teams toward outcomes.",
  },
};

export const DIMENSION_KEYS = Object.keys(DIMENSIONS) as DimensionKey[];

export type StrengthBand = "Developing" | "Moderate" | "High" | "Very High";

export function getStrengthBand(score: number): StrengthBand {
  if (score >= 80) return "Very High";
  if (score >= 60) return "High";
  if (score >= 40) return "Moderate";
  return "Developing";
}

export function getStrengthTone(band: StrengthBand): "safe" | "accent" | "neutral" | "muted" {
  switch (band) {
    case "Very High":
      return "safe";
    case "High":
      return "accent";
    case "Moderate":
      return "neutral";
    case "Developing":
      return "muted";
  }
}
