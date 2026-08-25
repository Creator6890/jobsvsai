import type { DimensionKey } from "./dimensions";

export type Question = {
  id: number;
  prompt: string;
  primaryDimension: DimensionKey;
  primaryWeight: number;
  secondaryDimension?: DimensionKey;
  secondaryWeight?: number;
};

export const ASSESSMENT_QUESTIONS: Question[] = [
  {
    id: 1,
    prompt: "I enjoy breaking complicated problems down into smaller, logical parts to find a solution.",
    primaryDimension: "analytical",
    primaryWeight: 1.0,
  },
  {
    id: 2,
    prompt: "I would rather create an original design or concept than follow an established template.",
    primaryDimension: "creativity",
    primaryWeight: 1.0,
  },
  {
    id: 3,
    prompt: "I get energized by directly helping, supporting, or counseling people with their needs.",
    primaryDimension: "people",
    primaryWeight: 1.0,
  },
  {
    id: 4,
    prompt: "I prefer hands-on work where I interact with physical equipment, tools, or tangible materials.",
    primaryDimension: "practical",
    primaryWeight: 1.0,
  },
  {
    id: 5,
    prompt: "I am naturally drawn to experimenting with new software, coding tools, or digital systems.",
    primaryDimension: "technology",
    primaryWeight: 1.0,
    secondaryDimension: "analytical",
    secondaryWeight: 0.3,
  },
  {
    id: 6,
    prompt: "I feel confident explaining technical or difficult concepts in simple terms to different audiences.",
    primaryDimension: "communication",
    primaryWeight: 1.0,
  },
  {
    id: 7,
    prompt: "I thrive when organizing workflows, tracking detailed schedules, and ensuring consistent accuracy.",
    primaryDimension: "organization",
    primaryWeight: 1.0,
  },
  {
    id: 8,
    prompt: "I am comfortable making decisions under uncertainty and taking responsibility for project outcomes.",
    primaryDimension: "leadership",
    primaryWeight: 1.0,
  },
  {
    id: 9,
    prompt: "I naturally search for empirical patterns, data trends, and hard evidence before making a judgment.",
    primaryDimension: "analytical",
    primaryWeight: 1.0,
  },
  {
    id: 10,
    prompt: "I enjoy reimagining how products, spaces, narratives, or visual presentations look and work.",
    primaryDimension: "creativity",
    primaryWeight: 1.0,
  },
  {
    id: 11,
    prompt: "I am attentive to other people's emotions, motivations, and unspoken concerns during conversations.",
    primaryDimension: "people",
    primaryWeight: 1.0,
    secondaryDimension: "communication",
    secondaryWeight: 0.3,
  },
  {
    id: 12,
    prompt: "I find it deeply satisfying to assemble, repair, or inspect physical objects to see how they function.",
    primaryDimension: "practical",
    primaryWeight: 1.0,
  },
  {
    id: 13,
    prompt: "I like understanding how digital architectures, networks, or automated workflows operate behind the scenes.",
    primaryDimension: "technology",
    primaryWeight: 1.0,
  },
  {
    id: 14,
    prompt: "I enjoy writing structured articles, reports, or presentations designed to persuade or educate readers.",
    primaryDimension: "communication",
    primaryWeight: 1.0,
  },
  {
    id: 15,
    prompt: "I take pride in spotting subtle errors, adhering to quality standards, and maintaining structured records.",
    primaryDimension: "organization",
    primaryWeight: 1.0,
  },
  {
    id: 16,
    prompt: "I naturally step forward to coordinate people, establish priorities, and delegate tasks when a project stalls.",
    primaryDimension: "leadership",
    primaryWeight: 1.0,
  },
  {
    id: 17,
    prompt: "I find it engaging to investigate why a process or machine is failing and devise a systematic fix.",
    primaryDimension: "analytical",
    primaryWeight: 1.0,
    secondaryDimension: "practical",
    secondaryWeight: 0.4,
  },
  {
    id: 18,
    prompt: "I am energized by open-ended problems that have multiple valid creative pathways rather than one formula.",
    primaryDimension: "creativity",
    primaryWeight: 1.0,
    secondaryDimension: "analytical",
    secondaryWeight: 0.3,
  },
  {
    id: 19,
    prompt: "I prefer roles where building personal trust, mentoring, or collaborating with colleagues is central to the job.",
    primaryDimension: "people",
    primaryWeight: 1.0,
    secondaryDimension: "leadership",
    secondaryWeight: 0.3,
  },
  {
    id: 20,
    prompt: "I enjoy managing timelines, budgets, and operational deliverables to ensure projects finish on target.",
    primaryDimension: "organization",
    primaryWeight: 1.0,
    secondaryDimension: "leadership",
    secondaryWeight: 0.4,
  },
];

export const RESPONSE_OPTIONS = [
  { value: 1, label: "Strongly disagree", shortLabel: "Strongly disagree" },
  { value: 2, label: "Disagree", shortLabel: "Disagree" },
  { value: 3, label: "Neutral", shortLabel: "Neutral" },
  { value: 4, label: "Agree", shortLabel: "Agree" },
  { value: 5, label: "Strongly agree", shortLabel: "Strongly agree" },
] as const;
