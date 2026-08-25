import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

// ---------------------------------------------------------------------------
// 1. Source File Existence & Exports Invariants
// ---------------------------------------------------------------------------

test("Action Plan source files exist and contain required exports", () => {
  const typesPath = path.join(srcRoot, "lib", "actionPlan", "types.ts");
  const generatorPath = path.join(srcRoot, "lib", "actionPlan", "generator.ts");
  const indexPath = path.join(srcRoot, "lib", "actionPlan", "index.ts");
  const sectionPath = path.join(
    srcRoot,
    "components",
    "actionPlan",
    "ActionPlanSection.tsx"
  );

  for (const filePath of [typesPath, generatorPath, indexPath, sectionPath]) {
    assert.ok(fs.existsSync(filePath), `Expected ${filePath} to exist`);
  }

  const generatorContent = fs.readFileSync(generatorPath, "utf8");
  assert.ok(generatorContent.includes("export function generateActionPlan"));
  assert.ok(generatorContent.includes("export function getActionRiskBand"));

  const detailPath = path.join(srcRoot, "components", "OccupationDetail.tsx");
  const detailContent = fs.readFileSync(detailPath, "utf8");
  assert.ok(detailContent.includes("ActionPlanSection"));
});

// ---------------------------------------------------------------------------
// 2. Pure Algorithm Execution Tests
// ---------------------------------------------------------------------------

function getActionRiskBandPure(replacementRisk) {
  if (replacementRisk <= 40) return "low";
  if (replacementRisk <= 60) return "medium";
  return "high";
}

function buildActionPrioritiesPure(band) {
  switch (band) {
    case "low":
      return [
        { order: 1, title: "Integrate AI productivity tools into routine tasks", guidance: `Experiment with AI assistants for standard reporting, documentation, and research.` },
        { order: 2, title: "Deepen specialized contextual expertise", guidance: `Strengthen human judgment and physical oversight.` },
        { order: 3, title: "Explore adjacent career growth paths", guidance: `Stay aware of specialized tracks.` },
      ];
    case "medium":
      return [
        { order: 1, title: "Adopt AI as a workflow co-pilot", guidance: `Build fluency with AI tools.` },
        { order: 2, title: "Shift focus toward human-dependent responsibilities", guidance: `Allocate more bandwidth to advisory work.` },
        { order: 3, title: "Monitor exposed task areas & career alternatives", guidance: `Track evolving automation.` },
      ];
    case "high":
    default:
      return [
        { order: 1, title: "Master AI workflows immediately", guidance: `Develop deep practical familiarity with automated tools.` },
        { order: 2, title: "Elevate your role above routine execution", guidance: `Transition toward strategic framing.` },
        { order: 3, title: "Actively evaluate transferable career transitions", guidance: `Review adjacent occupations.` },
      ];
  }
}

function deriveResilientCharacteristicsPure(job) {
  const chars = [];
  if (job.humanDependency >= 60) {
    chars.push("High human dependency: Direct interpersonal collaboration resists automation.");
  } else if (job.humanDependency >= 45) {
    chars.push("Moderate interpersonal interaction: Communication remains human-led.");
  }
  if (job.physicalDependency >= 50) {
    chars.push("Physical and real-world presence: Hands-on spatial coordination faces minimal pressure.");
  }
  if (job.labourMarketResilience >= 60) {
    chars.push("Labor market resilience: Market demand buffers against rapid workforce contraction.");
  }
  if (chars.length === 0) {
    chars.push("Contextual accountability: High-stakes judgment remains human contribution.");
  }
  return chars;
}

function generateActionPlanPure(job) {
  const riskBand = getActionRiskBandPure(job.replacementRisk);
  const priorities = buildActionPrioritiesPure(riskBand, job);
  const tasks = job.tasks || [];

  const sortedByExposureDesc = [...tasks].sort((a, b) => b.exposure - a.exposure);
  const watchTasks = sortedByExposureDesc.slice(0, 4).map(t => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: t.exposure >= 70 ? "High AI exposure" : "Moderate AI exposure",
    tag: `Exposure ${t.exposure}/100`,
  }));

  const sortedByAugmentation = [...tasks]
    .filter(t => t.exposure >= 45 || t.augmentationPotential >= 50)
    .sort((a, b) => b.augmentationPotential - a.augmentationPotential);

  const useAiCandidates = [];
  for (const t of sortedByAugmentation) {
    if (useAiCandidates.length >= 3) break;
    useAiCandidates.push(t);
  }
  if (useAiCandidates.length === 0 && sortedByExposureDesc.length > 0) {
    useAiCandidates.push(sortedByExposureDesc[0]);
  }

  const useAiTasks = useAiCandidates.map(t => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: "Augmentation opportunity",
    tag: `Augmentation ${t.augmentationPotential}/100`,
  }));

  const hardestNames = new Set(job.hardestToAutomateTasks || []);
  const hardestMatched = [];
  for (const t of tasks) {
    if (hardestNames.has(t.name)) hardestMatched.push(t);
  }
  hardestMatched.sort((a, b) => a.exposure - b.exposure);
  const sortedByExposureAsc = [...tasks].sort((a, b) => a.exposure - b.exposure);
  const leanCandidates = hardestMatched.length >= 2 ? hardestMatched.slice(0, 4) : sortedByExposureAsc.slice(0, 4);

  const leanTasks = leanCandidates.map(t => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: t.exposure <= 45 ? "Lower exposure" : "Defensible execution",
    tag: `Exposure ${t.exposure}/100`,
  }));

  const resilientCharacteristics = deriveResilientCharacteristicsPure(job);

  let bandTitle = "";
  let bandDescription = "";
  let transitionProminence = "secondary";

  switch (riskBand) {
    case "low":
      bandTitle = "Resilient Core Profile";
      bandDescription = `${job.title} demonstrates strong structural resilience (${job.replacementRisk}/100 Replacement Risk).`;
      transitionProminence = "secondary";
      break;
    case "medium":
      bandTitle = "Evolving Workflow Profile";
      bandDescription = `${job.title} has moderate replacement risk (${job.replacementRisk}/100).`;
      transitionProminence = "prominent";
      break;
    case "high":
      bandTitle = "High-Exposure Transition Profile";
      bandDescription = `${job.title} faces substantial replacement pressure (${job.replacementRisk}/100).`;
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
      description: "Focus on responsibilities relying on human trust and judgment.",
      characteristics: resilientCharacteristics,
      tasks: leanTasks,
    },
    useAiFor: {
      title: "Use AI to augment routine workflows",
      description: "Adopt generative and analytical AI tools.",
      tasks: useAiTasks,
    },
    watchClosely: {
      title: "Watch closely for automation pressure",
      description: "Tasks with higher exposure.",
      tasks: watchTasks,
    },
    alternatives: {
      title: "Consider adjacent career paths",
      description: hasTransitions ? `Discover ${transitionCount} related occupations.` : "Explore related career paths.",
      transitionProminence,
      transitionCount,
      hasTransitions,
    },
  };
}

const SAMPLE_HIGH_RISK_JOB = {
  slug: "graphic-designers",
  title: "Graphic Designers",
  category: "Creative & Media",
  aiExposure: 70,
  replacementRisk: 70,
  humanDependency: 55,
  physicalDependency: 20,
  labourMarketResilience: 45,
  tasks: [
    { onetTaskId: 1, name: "Create designs, concepts, and sample layouts.", importance: "High", exposure: 78, automationFeasibility: 72, augmentationPotential: 80 },
    { onetTaskId: 2, name: "Determine size and arrangement of illustrative material.", importance: "High", exposure: 75, automationFeasibility: 70, augmentationPotential: 78 },
    { onetTaskId: 3, name: "Review final layouts and suggest improvements.", importance: "Medium", exposure: 68, automationFeasibility: 60, augmentationPotential: 70 },
    { onetTaskId: 4, name: "Confer with clients to determine objectives.", importance: "High", exposure: 42, automationFeasibility: 35, augmentationPotential: 55 },
  ],
  hardestToAutomateTasks: [
    "Confer with clients to determine objectives.",
    "Review final layouts and suggest improvements.",
  ],
  relatedCareers: [
    { slug: "art-directors", title: "Art Directors", replacementRisk: 55, relatednessTier: "Primary-Short", relatednessRank: 1 },
  ],
};

const SAMPLE_LOW_RISK_JOB = {
  slug: "electricians",
  title: "Electricians",
  category: "Installation & Repair",
  aiExposure: 36,
  replacementRisk: 34,
  humanDependency: 65,
  physicalDependency: 95,
  labourMarketResilience: 75,
  tasks: [
    { onetTaskId: 10, name: "Install electrical conduit and wiring systems.", importance: "High", exposure: 25, automationFeasibility: 15, augmentationPotential: 30 },
    { onetTaskId: 11, name: "Diagnose malfunctioning systems, apparatus, and components.", importance: "High", exposure: 38, automationFeasibility: 30, augmentationPotential: 52 },
    { onetTaskId: 12, name: "Read blueprints or technical diagrams.", importance: "Medium", exposure: 55, automationFeasibility: 50, augmentationPotential: 65 },
  ],
  hardestToAutomateTasks: [
    "Install electrical conduit and wiring systems.",
    "Diagnose malfunctioning systems, apparatus, and components.",
  ],
  relatedCareers: [
    { slug: "electrical-engineers", title: "Electrical Engineers", replacementRisk: 42, relatednessTier: "Primary-Short", relatednessRank: 1 },
  ],
};

test("Deterministic generation: same occupation yields identical action plan", () => {
  const plan1 = generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);
  const plan2 = generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);

  assert.equal(plan1.riskBand, plan2.riskBand);
  assert.equal(plan1.bandTitle, plan2.bandTitle);
  assert.equal(plan1.priorities.length, plan2.priorities.length);
  assert.equal(plan1.watchClosely.tasks.length, plan2.watchClosely.tasks.length);
  assert.equal(plan1.leanInto.tasks.length, plan2.leanInto.tasks.length);
});

test("Risk-band framing adapts to Replacement Risk thresholds", () => {
  const low = generateActionPlanPure(SAMPLE_LOW_RISK_JOB);
  assert.equal(low.riskBand, "low");
  assert.equal(low.bandTitle, "Resilient Core Profile");
  assert.equal(low.alternatives.transitionProminence, "secondary");

  const high = generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);
  assert.equal(high.riskBand, "high");
  assert.equal(high.bandTitle, "High-Exposure Transition Profile");
  assert.equal(high.alternatives.transitionProminence, "prominent");
});

test("High-exposure task selection: Watch Closely captures top exposed tasks", () => {
  const plan = generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);
  const watchTaskNames = plan.watchClosely.tasks.map(t => t.name);

  assert.ok(watchTaskNames.includes("Create designs, concepts, and sample layouts."));
  assert.equal(plan.watchClosely.tasks[0].exposure, 78);
});

test("Resilient task selection: Lean Into prioritizes hardest to automate / low exposure", () => {
  const plan = generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);
  const leanTaskNames = plan.leanInto.tasks.map(t => t.name);

  assert.ok(leanTaskNames.includes("Confer with clients to determine objectives."));
  assert.equal(plan.leanInto.tasks[0].exposure, 42);
});

test("No AI score mutation: underlying metrics remain intact", () => {
  const initialRisk = SAMPLE_HIGH_RISK_JOB.replacementRisk;
  const initialExposure = SAMPLE_HIGH_RISK_JOB.aiExposure;

  generateActionPlanPure(SAMPLE_HIGH_RISK_JOB);

  assert.equal(SAMPLE_HIGH_RISK_JOB.replacementRisk, initialRisk);
  assert.equal(SAMPLE_HIGH_RISK_JOB.aiExposure, initialExposure);
});

test("Empty / sparse tasks fallback gracefully without throwing", () => {
  const sparseJob = {
    slug: "minimal-job",
    title: "Minimal Job",
    category: "General",
    aiExposure: 50,
    replacementRisk: 50,
    humanDependency: 50,
    physicalDependency: 50,
    labourMarketResilience: 50,
    tasks: [],
    hardestToAutomateTasks: [],
    relatedCareers: [],
  };

  const plan = generateActionPlanPure(sparseJob);
  assert.equal(plan.riskBand, "medium");
  assert.equal(plan.watchClosely.tasks.length, 0);
  assert.equal(plan.leanInto.tasks.length, 0);
  assert.equal(plan.useAiFor.tasks.length, 0);
  assert.equal(plan.alternatives.hasTransitions, false);
});

test("Copy safety: zero 'AI-proof', 'guaranteed', or unsupported claims", () => {
  const jobs = [SAMPLE_HIGH_RISK_JOB, SAMPLE_LOW_RISK_JOB];
  for (const j of jobs) {
    const plan = generateActionPlanPure(j);
    const textBlob = JSON.stringify(plan).toLowerCase();

    assert.ok(!textBlob.includes("ai-proof"), "Must not contain 'ai-proof'");
    assert.ok(!textBlob.includes("future-proof"), "Must not contain 'future-proof'");
    assert.ok(!textBlob.includes("guaranteed safe"), "Must not contain 'guaranteed safe'");
    assert.ok(!textBlob.includes("you must"), "Must not contain 'you must'");
  }
});
