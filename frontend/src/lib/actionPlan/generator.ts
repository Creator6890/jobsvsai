import type { Occupation, TaskImpact } from "@/types/occupation";
import type {
  ActionPlanData,
  ActionPlanPriority,
  ActionRiskBand,
  TaskActionItem,
} from "./types";

/**
 * Derives the action risk band from Replacement Risk.
 */
export function getActionRiskBand(replacementRisk: number): ActionRiskBand {
  if (replacementRisk <= 40) return "low";
  if (replacementRisk <= 60) return "medium";
  return "high";
}

/**
 * Builds structured action priorities tailored to the occupation's risk band.
 */
function buildActionPriorities(
  band: ActionRiskBand,
  job: Occupation
): ActionPlanPriority[] {
  switch (band) {
    case "low":
      return [
        {
          order: 1,
          title: "Integrate AI productivity tools into routine tasks",
          guidance: `Experiment with AI assistants for standard reporting, documentation, and research to free up time for core domain work.`,
        },
        {
          order: 2,
          title: "Deepen specialized contextual expertise",
          guidance: `Strengthen the human judgment, physical oversight, or stakeholder navigation that gives ${job.title} its structural resilience.`,
        },
        {
          order: 3,
          title: "Explore adjacent career growth paths",
          guidance: `Stay aware of specialized leadership or related technical tracks that leverage your core capabilities.`,
        },
      ];
    case "medium":
      return [
        {
          order: 1,
          title: "Adopt AI as a workflow co-pilot",
          guidance: `Build fluency with AI tools for drafting, synthesis, and routine data operations to maintain competitive throughput.`,
        },
        {
          order: 2,
          title: "Shift focus toward human-dependent responsibilities",
          guidance: `Deliberately allocate more bandwidth to advisory, cross-functional collaboration, and nuanced decision-making.`,
        },
        {
          order: 3,
          title: "Monitor exposed task areas & career alternatives",
          guidance: `Keep track of evolving automation in your field while evaluating transferable career moves with lower AI exposure.`,
        },
      ];
    case "high":
    default:
      return [
        {
          order: 1,
          title: "Master AI workflows immediately",
          guidance: `Develop deep practical familiarity with automated tools to handle high-exposure deliverables faster and with higher quality.`,
        },
        {
          order: 2,
          title: "Elevate your role above routine execution",
          guidance: `Transition your daily focus from creating standardized outputs toward strategic framing, quality control, and client relationship management.`,
        },
        {
          order: 3,
          title: "Actively evaluate transferable career transitions",
          guidance: `Review adjacent occupations with shared work fundamentals and significantly lower AI replacement risk.`,
        },
      ];
  }
}

/**
 * Identifies resilient work characteristics supported by stored data.
 */
function deriveResilientCharacteristics(job: Occupation): string[] {
  const chars: string[] = [];

  if (job.humanDependency >= 60) {
    chars.push(
      "High human dependency: Direct interpersonal collaboration, empathy, and relationship management resist end-to-end automation."
    );
  } else if (job.humanDependency >= 45) {
    chars.push(
      "Moderate interpersonal interaction: Communication and stakeholder coordination remain human-led."
    );
  }

  if (job.physicalDependency >= 50) {
    chars.push(
      "Physical and real-world presence: Hands-on spatial coordination, tactile dexterity, or on-site operations face minimal digital automation pressure."
    );
  }

  if (job.labourMarketResilience >= 60) {
    chars.push(
      "Labor market resilience: Structural market demand and institutional necessity buffer against rapid workforce contraction."
    );
  }

  if (chars.length === 0) {
    chars.push(
      "Contextual accountability: High-stakes judgment, ethical oversight, and edge-case resolution remain distinct human contributions."
    );
  }

  return chars;
}

/**
 * Generates deterministic Occupation Action Plan data from structured evidence.
 */
export function generateActionPlan(job: Occupation): ActionPlanData {
  const riskBand = getActionRiskBand(job.replacementRisk);
  const priorities = buildActionPriorities(riskBand, job);
  const tasks = job.tasks || [];

  // 1. WATCH CLOSELY: Most exposed tasks (highest exposure, up to 4)
  const sortedByExposureDesc = [...tasks].sort(
    (a, b) => b.exposure - a.exposure
  );
  const watchTasks: TaskActionItem[] = sortedByExposureDesc.slice(0, 4).map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance:
      t.exposure >= 70
        ? "High AI exposure: Standardized or repeatable components make this a primary focus of automation tooling."
        : "Moderate AI exposure: Machine capabilities can assist with portions of this task mix.",
    tag: `Exposure ${t.exposure}/100`,
  }));



  // 2. USE AI FOR: Tasks with high augmentation potential and notable exposure
  // Look for tasks where augmentationPotential >= 50 or exposure >= 50, sorted by augmentationPotential desc
  const sortedByAugmentation = [...tasks]
    .filter((t) => t.exposure >= 45 || t.augmentationPotential >= 50)
    .sort((a, b) => b.augmentationPotential - a.augmentationPotential);

  const useAiCandidates: TaskImpact[] = [];
  for (const t of sortedByAugmentation) {
    if (useAiCandidates.length >= 3) break;
    useAiCandidates.push(t);
  }

  // Fallback if no task matched filter
  if (useAiCandidates.length === 0 && sortedByExposureDesc.length > 0) {
    useAiCandidates.push(sortedByExposureDesc[0]);
  }

  const useAiTasks: TaskActionItem[] = useAiCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: `Augmentation opportunity: Use AI tools to accelerate drafting, initial data structuring, or research while applying human review.`,
    tag: `Augmentation ${t.augmentationPotential}/100`,
  }));

  // 3. LEAN INTO: Resilient / Hardest to Automate Tasks
  // Match hardestToAutomateTasks strings back to TaskImpact if possible, or sort by exposure asc
  const hardestNames = new Set(job.hardestToAutomateTasks || []);
  const hardestMatched: TaskImpact[] = [];

  for (const t of tasks) {
    if (hardestNames.has(t.name)) {
      hardestMatched.push(t);
    }
  }
  hardestMatched.sort((a, b) => a.exposure - b.exposure);

  const sortedByExposureAsc = [...tasks].sort(
    (a, b) => a.exposure - b.exposure
  );

  const leanCandidates: TaskImpact[] =
    hardestMatched.length >= 2
      ? hardestMatched.slice(0, 4)
      : sortedByExposureAsc.slice(0, 4);

  const leanTasks: TaskActionItem[] = leanCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance:
      t.exposure <= 45
        ? "Lower exposure: Real-world complexity, interpersonal nuance, or judgment resist automated replacement."
        : "Defensible execution: Human context and situational discernment remain essential for reliable outcomes.",
    tag: `Exposure ${t.exposure}/100`,
  }));

  // Characteristics
  const resilientCharacteristics = deriveResilientCharacteristics(job);

  // Band Descriptions
  let bandTitle = "";
  let bandDescription = "";
  let transitionProminence: "prominent" | "secondary" = "secondary";

  switch (riskBand) {
    case "low":
      bandTitle = "Resilient Core Profile";
      bandDescription = `${job.title} demonstrates strong structural resilience (${job.replacementRisk}/100 Replacement Risk). Focus on adopting AI tools for productivity while deepening specialized, human-centered responsibilities.`;
      transitionProminence = "secondary";
      break;
    case "medium":
      bandTitle = "Evolving Workflow Profile";
      bandDescription = `${job.title} has moderate replacement risk (${job.replacementRisk}/100). Certain routine and analytical components face automation pressure, making proactive AI adoption and skill diversification valuable.`;
      transitionProminence = "prominent";
      break;
    case "high":
      bandTitle = "High-Exposure Transition Profile";
      bandDescription = `${job.title} faces substantial replacement pressure (${job.replacementRisk}/100). Prioritize immediate AI tool literacy, shift scope toward strategic human responsibilities, and evaluate adjacent career transitions.`;
      transitionProminence = "prominent";
      break;
  }

  const transitionCount = (job.relatedCareers || []).length;
  const hasTransitions = transitionCount > 0;

  return {
    occupation: job,
    riskBand,
    bandTitle,
    bandDescription,
    priorities,
    leanInto: {
      title: "Lean into human-led strengths",
      description:
        "Focus your energy on responsibilities that rely on interpersonal trust, physical execution, and contextual judgment.",
      characteristics: resilientCharacteristics,
      tasks: leanTasks,
    },
    useAiFor: {
      title: "Use AI to augment routine workflows",
      description:
        "Adopt generative and analytical AI tools to accelerate repeatable deliverables rather than resisting automation.",
      tasks: useAiTasks,
    },
    watchClosely: {
      title: "Watch closely for automation pressure",
      description:
        "These tasks have higher exposure to machine capability and are most likely to experience shifting workflow demands.",
      tasks: watchTasks,
    },
    alternatives: {
      title: "Consider adjacent career paths",
      description:
        hasTransitions
          ? `Discover ${transitionCount} related occupations that build upon your existing background, including options with lower AI replacement risk.`
          : `Explore related career paths with transferable occupational characteristics.`,
      transitionProminence,
      transitionCount,
      hasTransitions,
    },
  };
}
