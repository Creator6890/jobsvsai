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
 * Calculates importance bonus to ensure core occupational tasks are prioritized over obscure peripheral items.
 */
function getImportanceBonus(importance: "High" | "Medium" | "Low"): number {
  switch (importance) {
    case "High":
      return 10;
    case "Medium":
      return 5;
    case "Low":
    default:
      return 0;
  }
}

/**
 * Calculates automation pressure score combining exposure, automation feasibility, and task importance.
 */
function getAutomationPressureScore(t: TaskImpact): number {
  const bonus = getImportanceBonus(t.importance);
  return t.exposure * 0.55 + t.automationFeasibility * 0.45 + bonus;
}

/**
 * Calculates augmentation score emphasizing high augmentation potential and co-pilot utility.
 */
function getAugmentationScore(t: TaskImpact): number {
  const bonus = getImportanceBonus(t.importance);
  const gapBonus = Math.max(0, t.augmentationPotential - t.automationFeasibility * 0.4);
  return t.augmentationPotential * 0.6 + t.exposure * 0.2 + gapBonus * 0.2 + bonus;
}

/**
 * Calculates defensibility score for Lean Into section (lower exposure/automation feasibility + importance).
 */
function getDefensibilityScore(t: TaskImpact, isHardest: boolean): number {
  const bonus = getImportanceBonus(t.importance);
  const hardestBonus = isHardest ? 30 : 0;
  // Lower exposure and automation feasibility give higher defensibility
  const resistance = (100 - t.exposure) * 0.5 + (100 - t.automationFeasibility) * 0.5;
  return resistance + hardestBonus + bonus;
}

/**
 * Generates deterministic Occupation Action Plan data from structured evidence.
 * Enforces mutually distinct task selections across Lean Into, Use AI For, and Watch Closely.
 */
export function generateActionPlan(job: Occupation): ActionPlanData {
  const riskBand = getActionRiskBand(job.replacementRisk);
  const priorities = buildActionPriorities(riskBand, job);
  const tasks = job.tasks || [];
  const claimedTasks = new Set<string>();

  const hardestNames = new Set(job.hardestToAutomateTasks || []);

  // Determine target count per section to maintain mutually distinct selections
  const maxPerSection = tasks.length <= 4 ? 1 : tasks.length <= 7 ? 2 : 3;

  // -------------------------------------------------------------------------
  // 1. LEAN INTO: Select most defensible tasks
  // -------------------------------------------------------------------------
  const sortedForLean = [...tasks].sort((a, b) => {
    const scoreA = getDefensibilityScore(a, hardestNames.has(a.name));
    const scoreB = getDefensibilityScore(b, hardestNames.has(b.name));
    return scoreB - scoreA;
  });

  const leanCandidates: TaskImpact[] = [];
  for (const t of sortedForLean) {
    if (leanCandidates.length >= maxPerSection) break;
    leanCandidates.push(t);
    claimedTasks.add(t.name);
  }

  const leanTasks: TaskActionItem[] = leanCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance:
      t.exposure <= 45
        ? "Lower exposure: Real-world complexity, physical execution, or interpersonal nuance resist automated replacement."
        : "Defensible execution: Situational discernment, stakeholder trust, and human context remain essential.",
    tag: `Exposure ${t.exposure}/100`,
  }));

  // -------------------------------------------------------------------------
  // 2. WATCH CLOSELY: Select tasks facing high automation pressure
  // -------------------------------------------------------------------------
  const availableForWatch = tasks.filter((t) => !claimedTasks.has(t.name));
  const sortedForWatch = [...availableForWatch].sort(
    (a, b) => getAutomationPressureScore(b) - getAutomationPressureScore(a)
  );

  const watchCandidates: TaskImpact[] = [];
  for (const t of sortedForWatch) {
    if (watchCandidates.length >= maxPerSection) break;
    watchCandidates.push(t);
    claimedTasks.add(t.name);
  }

  const watchTasks: TaskActionItem[] = watchCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance:
      t.automationFeasibility >= 70
        ? "High automation feasibility: Standardized workflows and structured deliverables face increasing automation capability."
        : "Notable AI exposure: Machine capabilities can assist with portions of this task mix, shifting workflow expectations.",
    tag: `Feasibility ${t.automationFeasibility}/100`,
  }));

  // -------------------------------------------------------------------------
  // 3. USE AI FOR: Select tasks with high augmentation potential
  // -------------------------------------------------------------------------
  const availableForAugment = tasks.filter((t) => !claimedTasks.has(t.name));
  const sortedForAugment = [...availableForAugment].sort(
    (a, b) => getAugmentationScore(b) - getAugmentationScore(a)
  );

  const useAiCandidates: TaskImpact[] = [];
  for (const t of sortedForAugment) {
    if (useAiCandidates.length >= maxPerSection) break;
    useAiCandidates.push(t);
    claimedTasks.add(t.name);
  }

  // If very few tasks exist and useAi is still empty, take highest augmentation task with explicit co-pilot tag
  if (useAiCandidates.length === 0 && tasks.length > 0) {
    const bestAug = [...tasks].sort(
      (a, b) => getAugmentationScore(b) - getAugmentationScore(a)
    )[0];
    useAiCandidates.push(bestAug);
  }

  const useAiTasks: TaskActionItem[] = useAiCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: `High augmentation potential: Well-suited for AI co-piloting, initial drafting, and structured analysis under human oversight.`,
    tag: `Augmentation ${t.augmentationPotential}/100`,
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
        "These tasks have comparatively higher automation feasibility and are most likely to experience shifting workflow demands.",
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
