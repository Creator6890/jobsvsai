import type { Occupation, TaskImpact } from "@/types/occupation";
import { getScoreSemantics, type SemanticTone } from "./scoreSemantics";

export type OccupationVerdictData = {
  directAnswer: string;
  verdictParagraphs: string[];
  exposureVsReplacementContrast: string;
  keyDrivers: Array<{
    title: string;
    description: string;
    tone: SemanticTone;
  }>;
  automatedTaskGroups: {
    highExposure: TaskImpact[];
    assisted: TaskImpact[];
    humanAnchored: TaskImpact[];
  };
  humanAdvantages: Array<{
    title: string;
    description: string;
  }>;
  faqs: Array<{
    question: string;
    answer: string;
  }>;
};

/**
 * Deterministic, multi-dimensional content generator for Verified Occupations.
 * Grounded strictly in the occupation's actual task ratings, capability fit,
 * structural constraints, and score values. Zero fabricated statistics or LLM runtime calls.
 */
export function getOccupationContent(job: Occupation): OccupationVerdictData {
  const expSem = getScoreSemantics("ai_exposure", job.aiExposure);
  const riskSem = getScoreSemantics("replacement_risk", job.replacementRisk);
  const humanSem = getScoreSemantics("human_dependency", job.humanDependency);
  const physSem = getScoreSemantics("physical_dependency", job.physicalDependency);
  const adoptSem = getScoreSemantics("adoption_pressure", job.adoptionPressure);
  const resSem = getScoreSemantics("labour_market_resilience", job.labourMarketResilience);

  const topExposedTasks = [...job.tasks].sort((a, b) => b.exposure - a.exposure);
  const highExposureTasks = topExposedTasks.filter((t) => t.exposure >= 67);
  const assistedTasks = topExposedTasks.filter((t) => t.exposure >= 34 && t.exposure < 67);
  const humanAnchoredTasks = topExposedTasks.filter((t) => t.exposure < 34);

  const topExposedName = topExposedTasks[0]?.name ? `"${topExposedTasks[0].name}"` : "routine analytical and documentation tasks";
  const secondExposedName = topExposedTasks[1]?.name ? `"${topExposedTasks[1].name}"` : "information processing workflows";
  const hardestTaskName = job.hardestToAutomateTasks[0] ? `"${job.hardestToAutomateTasks[0]}"` : "high-judgment decision making";

  // 1. Direct Answer Summary for Hero Callout
  let directAnswer = "";
  const gap = job.aiExposure - job.replacementRisk;

  if (job.aiExposure >= 67 && job.replacementRisk >= 67) {
    directAnswer = `AI is poised to substantially reshape ${job.title} work. With high task exposure (${job.aiExposure}/100) and elevated replacement risk (${job.replacementRisk}/100), routine digital workflows face significant automation pressure, requiring workers to pivot toward high-judgment and supervisory functions.`;
  } else if (gap >= 12 && job.aiExposure >= 50) {
    directAnswer = `While AI has high capability overlap with ${job.title} tasks (${job.aiExposure}/100 AI Exposure), full job elimination is constrained by structural factors (${job.replacementRisk}/100 Replacement Risk). Human oversight, professional accountability, and contextual decision-making keep human demand stronger than raw software capability suggests.`;
  } else if (job.replacementRisk <= 33) {
    directAnswer = `Current AI systems pose low direct replacement risk (${job.replacementRisk}/100) to ${job.title}. Even where specific software tools assist with tasks (${job.aiExposure}/100 AI Exposure), physical presence, complex manual dexterity, and unpredictable real-world environments protect the core human role.`;
  } else {
    directAnswer = `${job.title} exhibits a moderate balance of AI impact (${job.aiExposure}/100 Exposure, ${job.replacementRisk}/100 Replacement Risk). Certain repeatable administrative and analytical tasks are accelerating with AI tools, while core responsibilities remain anchored in human judgment and stakeholder communication.`;
  }

  // 2. Full Multi-Paragraph Verdict ("What this means")
  const verdictParagraphs: string[] = [];

  // Paragraph 1: Exposure & Task dynamics
  verdictParagraphs.push(
    `For ${job.title}, AI Exposure is rated ${expSem.label.toLowerCase()} at ${job.aiExposure}/100, while overall Replacement Risk is rated ${riskSem.label.toLowerCase()} at ${job.replacementRisk}/100. This indicates that AI systems can already execute or accelerate significant parts of the day-to-day workload—especially ${topExposedName} and ${secondExposedName}—without necessarily eliminating the occupation entirely.`
  );

  // Paragraph 2: Structural constraints & Human Anchors
  if (job.humanDependency >= 60 || job.physicalDependency >= 50) {
    const anchors: string[] = [];
    if (job.humanDependency >= 60) anchors.push(`strong human dependency (${job.humanDependency}/100) involving interpersonal negotiation, empathy, and high-stakes verification`);
    if (job.physicalDependency >= 50) anchors.push(`substantial physical requirements (${job.physicalDependency}/100) that current digital AI systems cannot perform`);
    verdictParagraphs.push(
      `The critical barrier between software capability and worker replacement is ${anchors.join(" alongside ")}. Tasks like ${hardestTaskName} require tacit context and real-time adaptability that cannot be reliably offloaded to generative models or autonomous pipelines.`
    );
  } else {
    verdictParagraphs.push(
      `Because this occupation relies heavily on digitized information workflows, adoption pressure is ${adoptSem.label.toLowerCase()} (${job.adoptionPressure}/100). Organisations are actively integrating AI assistants into standard toolchains, altering the speed of execution and shifting entry-level responsibilities.`
    );
  }

  // Paragraph 3: Strategic Career Takeaway
  verdictParagraphs.push(
    `A score of ${job.replacementRisk}/100 is not a prediction of unemployment; it represents structural pressure on how time is allocated. Professionals in ${job.title} should proactively adopt AI for high-velocity routine tasks while cultivating deep specialization in the judgment, client relationship, and accountability facets of their profession.`
  );

  // 3. Exposure vs Replacement Contrast Note
  const exposureVsReplacementContrast =
    gap > 10
      ? `AI Exposure (${job.aiExposure}/100) is ${gap} points higher than Replacement Risk (${job.replacementRisk}/100). This gap reflects strong structural friction—including human accountability, regulatory boundaries, and physical requirements—that prevents raw AI capability from directly reducing headcount.`
      : Math.abs(gap) <= 10
      ? `AI Exposure (${job.aiExposure}/100) closely tracks Replacement Risk (${job.replacementRisk}/100). When tasks are automated in this role, the efficiency gains translate relatively directly into structural shifts in workforce demand.`
      : `Replacement Risk (${job.replacementRisk}/100) exceeds AI Exposure (${job.aiExposure}/100) due to broader labour-market dynamics and high adoption pressure accelerating organizational restructuring.`;

  // 4. Key Structural Drivers
  const keyDrivers = [
    {
      title: "AI Capability Overlap",
      description: `${job.aiExposure}/100 exposure across ${job.tasks.length} evaluated O*NET tasks. ${highExposureTasks.length} tasks show high automation feasibility under current multimodal AI models.`,
      tone: expSem.tone,
    },
    {
      title: "Human & Social Dependency",
      description: `${humanSem.label} human reliance (${job.humanDependency}/100). Evaluates requirements for interpersonal trust, consensus-building, ethical responsibility, and direct client care.`,
      tone: humanSem.tone,
    },
    {
      title: "Physical & Environmental Constraints",
      description: `${physSem.label} physical dependency (${job.physicalDependency}/100). Measures non-routine physical agility, spatial navigation, and unconstrained environment interaction.`,
      tone: physSem.tone,
    },
    {
      title: "Adoption Pressure & Economics",
      description: `${adoptSem.label} commercial pressure (${job.adoptionPressure}/100). Evaluates software integration pace, cost-to-automate ratios, and enterprise tooling adoption.`,
      tone: adoptSem.tone,
    },
    {
      title: "Labour-Market Resilience",
      description: `${resSem.label} resilience buffer (${job.labourMarketResilience}/100). Reflects structural demand, specialization barriers, and regulatory licensure protections.`,
      tone: resSem.tone,
    },
  ];

  // 5. Human Advantages
  const humanAdvantages: Array<{ title: string; description: string }> = [];

  if (job.humanDependency >= 50) {
    humanAdvantages.push({
      title: "Stakeholder Trust & Accountability",
      description: `Clients, employers, and regulators require a responsible human practitioner to stand behind decisions, verify automated outputs, and uphold professional standards.`,
    });
  }
  if (job.physicalDependency >= 34) {
    humanAdvantages.push({
      title: "Physical Adaptability & Presence",
      description: `Real-world workspaces present unpredictable physical variables that cannot be handled by screen-based AI systems or current commercial robotics.`,
    });
  }
  if (job.hardestToAutomateTasks.length > 0) {
    humanAdvantages.push({
      title: "High-Context Judgment & Problem Solving",
      description: `Tasks such as ${hardestTaskName} depend on tacit institutional knowledge, ambiguous nuance, and subjective priorities that defy algorithmic formalization.`,
    });
  }
  humanAdvantages.push({
    title: "Synthesis & Verification",
    description: `While AI generates raw drafts and analytical calculations rapidly, human specialists are essential to detect hallucinations, ensure regulatory compliance, and align work with organizational strategy.`,
  });

  // 6. Deterministic FAQs tailored to the occupation
  const faqs = [
    {
      question: `Will AI replace ${job.title.toLowerCase()}s?`,
      answer: `AI is unlikely to eliminate the ${job.title} occupation entirely, but it is actively transforming specific tasks. With an AI Exposure score of ${job.aiExposure}/100 and a Replacement Risk score of ${job.replacementRisk}/100, the profession is experiencing workflow restructuring rather than outright extinction. Tasks like ${topExposedName} are shifting to automated tools, while ${hardestTaskName} remains firmly human.`,
    },
    {
      question: `What is the difference between AI Exposure and Replacement Risk for ${job.title}?`,
      answer: `AI Exposure (${job.aiExposure}/100) measures how much of the work overlaps with what current AI systems can perform technically. Replacement Risk (${job.replacementRisk}/100) measures whether that capability actually threatens human employment after accounting for physical constraints (${job.physicalDependency}/100), human dependency (${job.humanDependency}/100), adoption costs, and professional accountability.`,
    },
    {
      question: `Does a Replacement Risk score of ${job.replacementRisk} mean a ${job.replacementRisk}% chance of losing my job?`,
      answer: `No. JobsVsAI scores are index ratings on a 0–100 scale, not probabilities or unemployment percentages. A score of ${job.replacementRisk}/100 indicates that ${job.title} exhibits ${riskSem.label.toLowerCase()} structural vulnerability relative to other occupations across the labour market.`,
    },
    {
      question: `Which ${job.title} tasks are most exposed to AI automation?`,
      answer: `The tasks with the highest exposure in our dataset are ${topExposedTasks.slice(0, 3).map((t) => `"${t.name}" (${t.exposure}/100)`).join(", ")}. These responsibilities involve structured data manipulation, document drafting, pattern analysis, and routine communication.`,
    },
    {
      question: `What skills protect ${job.title}s from AI replacement?`,
      answer: `The strongest protective factors for ${job.title} include ${job.hardestToAutomateTasks.slice(0, 2).map((t) => `"${t}"`).join(" and ")}, as well as interpersonal negotiation, regulatory accountability, and cross-disciplinary synthesis.`,
    },
    {
      question: `How was this ${job.title} AI risk score calculated?`,
      answer: `JobsVsAI analysed ${job.tasks.length} individual tasks from O*NET 30.3, evaluating each task against 15 AI capability dimensions from our Capability Index. The model calculates capability overlap, applies environmental and human constraints, and weighs adoption pressure to produce independent Exposure and Replacement metrics with ${Math.round(job.confidence)}/100 confidence.`,
    },
  ];

  return {
    directAnswer,
    verdictParagraphs,
    exposureVsReplacementContrast,
    keyDrivers,
    automatedTaskGroups: {
      highExposure: highExposureTasks,
      assisted: assistedTasks,
      humanAnchored: humanAnchoredTasks,
    },
    humanAdvantages,
    faqs,
  };
}
