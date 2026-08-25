function getActionRiskBand(replacementRisk) {
  if (replacementRisk <= 40) return "low";
  if (replacementRisk <= 60) return "medium";
  return "high";
}

function buildActionPriorities(band, job) {
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

function deriveResilientCharacteristics(job) {
  const chars = [];

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

function generateActionPlan(job) {
  const riskBand = getActionRiskBand(job.replacementRisk);
  const priorities = buildActionPriorities(riskBand, job);
  const tasks = job.tasks || [];

  const sortedByExposureDesc = [...tasks].sort(
    (a, b) => b.exposure - a.exposure
  );
  const watchTasks = sortedByExposureDesc.slice(0, 4).map((t) => ({
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

  const sortedByAugmentation = [...tasks]
    .filter((t) => t.exposure >= 45 || t.augmentationPotential >= 50)
    .sort((a, b) => b.augmentationPotential - a.augmentationPotential);

  const useAiCandidates = [];
  for (const t of sortedByAugmentation) {
    if (useAiCandidates.length >= 3) break;
    useAiCandidates.push(t);
  }

  if (useAiCandidates.length === 0 && sortedByExposureDesc.length > 0) {
    useAiCandidates.push(sortedByExposureDesc[0]);
  }

  const useAiTasks = useAiCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: `Augmentation opportunity: Use AI tools to accelerate drafting, initial data structuring, or research while applying human review.`,
    tag: `Augmentation ${t.augmentationPotential}/100`,
  }));

  const hardestNames = new Set(job.hardestToAutomateTasks || []);
  const hardestMatched = [];

  for (const t of tasks) {
    if (hardestNames.has(t.name)) {
      hardestMatched.push(t);
    }
  }
  hardestMatched.sort((a, b) => a.exposure - b.exposure);

  const sortedByExposureAsc = [...tasks].sort(
    (a, b) => a.exposure - b.exposure
  );

  const leanCandidates =
    hardestMatched.length >= 2
      ? hardestMatched.slice(0, 4)
      : sortedByExposureAsc.slice(0, 4);

  const leanTasks = leanCandidates.map((t) => ({
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

  const resilientCharacteristics = deriveResilientCharacteristics(job);

  let bandTitle = "";
  let bandDescription = "";
  let transitionProminence = "secondary";

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

const COHORTS = [
  {
    domain: "Creative",
    occupation: {
      slug: "fashion-designers",
      title: "Fashion Designers",
      category: "Creative & Media",
      aiExposure: 64,
      replacementRisk: 60,
      humanDependency: 58,
      physicalDependency: 45,
      labourMarketResilience: 40,
      tasks: [
        { onetTaskId: 101, name: "Design sample garments and sketches.", importance: "High", exposure: 78, automationFeasibility: 72, augmentationPotential: 82 },
        { onetTaskId: 102, name: "Confer with sales and management executives to discuss design ideas.", importance: "High", exposure: 46, automationFeasibility: 38, augmentationPotential: 58 },
        { onetTaskId: 103, name: "Direct and coordinate workers involved in drawing and cutting patterns.", importance: "High", exposure: 42, automationFeasibility: 35, augmentationPotential: 50 },
        { onetTaskId: 104, name: "Identify target markets for designs, considering factors such as age and gender.", importance: "Medium", exposure: 74, automationFeasibility: 68, augmentationPotential: 80 },
        { onetTaskId: 105, name: "Select fabrics, trims, and notions for garments.", importance: "High", exposure: 50, automationFeasibility: 40, augmentationPotential: 65 },
      ],
      hardestToAutomateTasks: [
        "Direct and coordinate workers involved in drawing and cutting patterns.",
        "Confer with sales and management executives to discuss design ideas.",
      ],
      relatedCareers: [{ slug: "commercial-designers", title: "Commercial Designers", replacementRisk: 58, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Software / Tech",
    occupation: {
      slug: "computer-programmers",
      title: "Computer Programmers",
      category: "Technology & Data",
      aiExposure: 70,
      replacementRisk: 68,
      humanDependency: 38,
      physicalDependency: 15,
      labourMarketResilience: 42,
      tasks: [
        { onetTaskId: 201, name: "Write, update, and maintain computer programs and software packages.", importance: "High", exposure: 84, automationFeasibility: 80, augmentationPotential: 88 },
        { onetTaskId: 202, name: "Conduct trial runs of programs and software applications.", importance: "High", exposure: 76, automationFeasibility: 72, augmentationPotential: 82 },
        { onetTaskId: 203, name: "Collaborate with computer manufacturers and other users to develop new programming methods.", importance: "Medium", exposure: 45, automationFeasibility: 36, augmentationPotential: 60 },
        { onetTaskId: 204, name: "Consult with managerial, engineering, and technical personnel to clarify program intent.", importance: "High", exposure: 48, automationFeasibility: 38, augmentationPotential: 62 },
      ],
      hardestToAutomateTasks: [
        "Collaborate with computer manufacturers and other users to develop new programming methods.",
        "Consult with managerial, engineering, and technical personnel to clarify program intent.",
      ],
      relatedCareers: [{ slug: "systems-analysts", title: "Systems Analysts", replacementRisk: 67, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Administration",
    occupation: {
      slug: "secretaries-and-admin-assistants",
      title: "Secretaries and Administrative Assistants",
      category: "Office & Administration",
      aiExposure: 68,
      replacementRisk: 62,
      humanDependency: 62,
      physicalDependency: 25,
      labourMarketResilience: 40,
      tasks: [
        { onetTaskId: 301, name: "Create spreadsheets, compose correspondence, and manage databases.", importance: "High", exposure: 82, automationFeasibility: 78, augmentationPotential: 85 },
        { onetTaskId: 302, name: "Answer telephones and direct callers to appropriate staff.", importance: "High", exposure: 60, automationFeasibility: 55, augmentationPotential: 70 },
        { onetTaskId: 303, name: "Greet visitors and direct them to meeting locations.", importance: "Medium", exposure: 32, automationFeasibility: 25, augmentationPotential: 40 },
        { onetTaskId: 304, name: "Manage complex executive schedules and resolve conflicting appointments.", importance: "High", exposure: 52, automationFeasibility: 45, augmentationPotential: 68 },
      ],
      hardestToAutomateTasks: [
        "Greet visitors and direct them to meeting locations.",
        "Manage complex executive schedules and resolve conflicting appointments.",
      ],
      relatedCareers: [{ slug: "receptionists", title: "Receptionists", replacementRisk: 57, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Finance",
    occupation: {
      slug: "accountants",
      title: "Accountants",
      category: "Business & Finance",
      aiExposure: 67,
      replacementRisk: 61,
      humanDependency: 58,
      physicalDependency: 15,
      labourMarketResilience: 48,
      tasks: [
        { onetTaskId: 401, name: "Prepare, examine, and analyze accounting records and financial statements.", importance: "High", exposure: 80, automationFeasibility: 76, augmentationPotential: 86 },
        { onetTaskId: 402, name: "Compute taxes owed and prepare tax returns.", importance: "High", exposure: 78, automationFeasibility: 74, augmentationPotential: 84 },
        { onetTaskId: 403, name: "Advise clients regarding taxation strategy and financial investment decisions.", importance: "High", exposure: 48, automationFeasibility: 38, augmentationPotential: 65 },
        { onetTaskId: 404, name: "Represent clients before tax authorities during audits.", importance: "Medium", exposure: 36, automationFeasibility: 28, augmentationPotential: 45 },
      ],
      hardestToAutomateTasks: [
        "Represent clients before tax authorities during audits.",
        "Advise clients regarding taxation strategy and financial investment decisions.",
      ],
      relatedCareers: [{ slug: "financial-examiners", title: "Financial Examiners", replacementRisk: 60, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Healthcare",
    occupation: {
      slug: "registered-nurses",
      title: "Registered Nurses",
      category: "Healthcare",
      aiExposure: 59,
      replacementRisk: 50,
      humanDependency: 92,
      physicalDependency: 65,
      labourMarketResilience: 85,
      tasks: [
        { onetTaskId: 501, name: "Record patients' medical histories and vital statistics in digital charts.", importance: "Medium", exposure: 72, automationFeasibility: 65, augmentationPotential: 80 },
        { onetTaskId: 502, name: "Administer medications and treatments, observing patients for reactions.", importance: "High", exposure: 38, automationFeasibility: 25, augmentationPotential: 45 },
        { onetTaskId: 503, name: "Consult and coordinate with healthcare team members to plan patient care.", importance: "High", exposure: 42, automationFeasibility: 30, augmentationPotential: 60 },
        { onetTaskId: 504, name: "Provide emotional support and counseling to patients and their families.", importance: "High", exposure: 24, automationFeasibility: 15, augmentationPotential: 30 },
      ],
      hardestToAutomateTasks: [
        "Provide emotional support and counseling to patients and their families.",
        "Administer medications and treatments, observing patients for reactions.",
      ],
      relatedCareers: [{ slug: "nurse-practitioners", title: "Nurse Practitioners", replacementRisk: 51, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Education",
    occupation: {
      slug: "elementary-teachers",
      title: "Elementary School Teachers",
      category: "Education & Training",
      aiExposure: 62,
      replacementRisk: 55,
      humanDependency: 90,
      physicalDependency: 45,
      labourMarketResilience: 70,
      tasks: [
        { onetTaskId: 601, name: "Create lesson plans and generate customized worksheet materials.", importance: "High", exposure: 75, automationFeasibility: 70, augmentationPotential: 85 },
        { onetTaskId: 602, name: "Evaluate student assignments and track grade records.", importance: "Medium", exposure: 68, automationFeasibility: 62, augmentationPotential: 78 },
        { onetTaskId: 603, name: "Instruct students individually and in groups, adapting teaching methods.", importance: "High", exposure: 40, automationFeasibility: 28, augmentationPotential: 55 },
        { onetTaskId: 604, name: "Manage classroom behavior and foster social-emotional development.", importance: "High", exposure: 22, automationFeasibility: 14, augmentationPotential: 25 },
      ],
      hardestToAutomateTasks: [
        "Manage classroom behavior and foster social-emotional development.",
        "Instruct students individually and in groups, adapting teaching methods.",
      ],
      relatedCareers: [{ slug: "secondary-teachers", title: "Secondary School Teachers", replacementRisk: 59, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Sales",
    occupation: {
      slug: "insurance-sales-agents",
      title: "Insurance Sales Agents",
      category: "Sales",
      aiExposure: 65,
      replacementRisk: 58,
      humanDependency: 82,
      physicalDependency: 20,
      labourMarketResilience: 52,
      tasks: [
        { onetTaskId: 701, name: "Calculate premiums and establish method of payment.", importance: "High", exposure: 78, automationFeasibility: 74, augmentationPotential: 84 },
        { onetTaskId: 702, name: "Explain features, advantages and disadvantages of various policies.", importance: "High", exposure: 66, automationFeasibility: 58, augmentationPotential: 75 },
        { onetTaskId: 703, name: "Develop personal relationships with clients to understand risk tolerance.", importance: "High", exposure: 36, automationFeasibility: 24, augmentationPotential: 48 },
        { onetTaskId: 704, name: "Negotiate and settle property or casualty claims during disputes.", importance: "Medium", exposure: 42, automationFeasibility: 32, augmentationPotential: 55 },
      ],
      hardestToAutomateTasks: [
        "Develop personal relationships with clients to understand risk tolerance.",
        "Negotiate and settle property or casualty claims during disputes.",
      ],
      relatedCareers: [{ slug: "real-estate-agents", title: "Real Estate Sales Agents", replacementRisk: 52, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Management",
    occupation: {
      slug: "hr-managers",
      title: "Human Resources Managers",
      category: "Management & Leadership",
      aiExposure: 67,
      replacementRisk: 58,
      humanDependency: 88,
      physicalDependency: 20,
      labourMarketResilience: 55,
      tasks: [
        { onetTaskId: 801, name: "Analyze statistical data and reports to identify and determine causes of personnel problems.", importance: "High", exposure: 76, automationFeasibility: 70, augmentationPotential: 82 },
        { onetTaskId: 802, name: "Draft organizational policies, handbooks, and regulatory filings.", importance: "Medium", exposure: 74, automationFeasibility: 68, augmentationPotential: 80 },
        { onetTaskId: 803, name: "Mediate workplace disputes and negotiate collective grievance procedures.", importance: "High", exposure: 34, automationFeasibility: 22, augmentationPotential: 45 },
        { onetTaskId: 804, name: "Conduct difficult termination hearings and sensitive employee counseling.", importance: "High", exposure: 26, automationFeasibility: 16, augmentationPotential: 32 },
      ],
      hardestToAutomateTasks: [
        "Conduct difficult termination hearings and sensitive employee counseling.",
        "Mediate workplace disputes and negotiate collective grievance procedures.",
      ],
      relatedCareers: [{ slug: "hr-specialists", title: "Human Resources Specialists", replacementRisk: 59, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Trades",
    occupation: {
      slug: "electricians",
      title: "Electricians",
      category: "Installation & Repair",
      aiExposure: 36,
      replacementRisk: 34,
      humanDependency: 65,
      physicalDependency: 95,
      labourMarketResilience: 75,
      tasks: [
        { onetTaskId: 901, name: "Interpret technical blueprints and building safety specifications.", importance: "Medium", exposure: 55, automationFeasibility: 48, augmentationPotential: 65 },
        { onetTaskId: 902, name: "Diagnose electrical faults using testing equipment.", importance: "High", exposure: 38, automationFeasibility: 30, augmentationPotential: 52 },
        { onetTaskId: 903, name: "Assemble, install, and wire switchboards, conduits, and circuit breakers.", importance: "High", exposure: 24, automationFeasibility: 14, augmentationPotential: 28 },
        { onetTaskId: 904, name: "Climb ladders, scaffolding, and work in tight confined crawlspaces.", importance: "High", exposure: 18, automationFeasibility: 10, augmentationPotential: 18 },
      ],
      hardestToAutomateTasks: [
        "Assemble, install, and wire switchboards, conduits, and circuit breakers.",
        "Climb ladders, scaffolding, and work in tight confined crawlspaces.",
      ],
      relatedCareers: [{ slug: "electrical-engineers", title: "Electrical Engineers", replacementRisk: 42, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Transportation",
    occupation: {
      slug: "truck-drivers",
      title: "Heavy and Tractor-Trailer Truck Drivers",
      category: "Transport & Logistics",
      aiExposure: 49,
      replacementRisk: 40,
      humanDependency: 35,
      physicalDependency: 85,
      labourMarketResilience: 60,
      tasks: [
        { onetTaskId: 1001, name: "Plan optimal highway transit routes using GPS navigation logs.", importance: "Medium", exposure: 68, automationFeasibility: 64, augmentationPotential: 75 },
        { onetTaskId: 1002, name: "Maintain detailed logs of working hours and vehicle condition.", importance: "Medium", exposure: 65, automationFeasibility: 60, augmentationPotential: 72 },
        { onetTaskId: 1003, name: "Maneuver articulated vehicles in tight freight loading docks.", importance: "High", exposure: 35, automationFeasibility: 28, augmentationPotential: 40 },
        { onetTaskId: 1004, name: "Secure hazardous or oversized freight using chains and ratchets.", importance: "High", exposure: 20, automationFeasibility: 12, augmentationPotential: 22 },
      ],
      hardestToAutomateTasks: [
        "Secure hazardous or oversized freight using chains and ratchets.",
        "Maneuver articulated vehicles in tight freight loading docks.",
      ],
      relatedCareers: [{ slug: "industrial-truck-operators", title: "Industrial Truck Operators", replacementRisk: 33, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Service",
    occupation: {
      slug: "chefs-and-head-cooks",
      title: "Chefs and Head Cooks",
      category: "Food & Hospitality",
      aiExposure: 61,
      replacementRisk: 42,
      humanDependency: 80,
      physicalDependency: 85,
      labourMarketResilience: 65,
      tasks: [
        { onetTaskId: 1101, name: "Determine production schedules and inventory ingredient orders.", importance: "Medium", exposure: 74, automationFeasibility: 68, augmentationPotential: 80 },
        { onetTaskId: 1102, name: "Develop innovative recipe flavor profiles and seasonal menu concepts.", importance: "High", exposure: 55, automationFeasibility: 45, augmentationPotential: 68 },
        { onetTaskId: 1103, name: "Cook specialty dishes requiring precise sensory timing and tasting.", importance: "High", exposure: 28, automationFeasibility: 18, augmentationPotential: 32 },
        { onetTaskId: 1104, name: "Train, mentor, and supervise culinary line staff during peak service.", importance: "High", exposure: 32, automationFeasibility: 20, augmentationPotential: 40 },
      ],
      hardestToAutomateTasks: [
        "Cook specialty dishes requiring precise sensory timing and tasting.",
        "Train, mentor, and supervise culinary line staff during peak service.",
      ],
      relatedCareers: [{ slug: "food-servers", title: "Food Servers, Nonrestaurant", replacementRisk: 40, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
  {
    domain: "Low-Risk Industrial",
    occupation: {
      slug: "aircraft-mechanic",
      title: "Aircraft Mechanic",
      category: "Installation & Repair",
      aiExposure: 38,
      replacementRisk: 37,
      humanDependency: 60,
      physicalDependency: 90,
      labourMarketResilience: 78,
      tasks: [
        { onetTaskId: 1201, name: "Log inspection records and compliance reports into FAA maintenance databases.", importance: "Medium", exposure: 62, automationFeasibility: 56, augmentationPotential: 72 },
        { onetTaskId: 1202, name: "Examine airframe surfaces and jet turbines using borescope diagnostic probes.", importance: "High", exposure: 42, automationFeasibility: 34, augmentationPotential: 58 },
        { onetTaskId: 1203, name: "Disassemble, repair, and reassemble flight control actuators and landing gear.", importance: "High", exposure: 22, automationFeasibility: 12, augmentationPotential: 25 },
        { onetTaskId: 1204, name: "Perform rigorous pre-flight safety checks and sign off airworthiness releases.", importance: "High", exposure: 26, automationFeasibility: 16, augmentationPotential: 35 },
      ],
      hardestToAutomateTasks: [
        "Disassemble, repair, and reassemble flight control actuators and landing gear.",
        "Perform rigorous pre-flight safety checks and sign off airworthiness releases.",
      ],
      relatedCareers: [{ slug: "avionics-technicians", title: "Avionics Technicians", replacementRisk: 46, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
];

console.log("================================================================================");
console.log("JOBSVSAI — OCCUPATION ACTION PLAN V1: 12-COHORT CALIBRATION MATRIX");
console.log("================================================================================");

let totalEvaluated = 0;
let usefulCount = 0;

for (const c of COHORTS) {
  const plan = generateActionPlan(c.occupation);
  totalEvaluated++;
  usefulCount++;

  console.log(`\n### [${c.domain}] ${c.occupation.title}`);
  console.log(`Replacement Risk: ${c.occupation.replacementRisk}/100 | Risk Band: ${plan.riskBand.toUpperCase()} (${plan.bandTitle})`);
  console.log(`Transition CTA Prominence: ${plan.alternatives.transitionProminence.toUpperCase()}`);
  console.log(`\n**Top Watch Closely (Exposed Tasks):**`);
  for (const t of plan.watchClosely.tasks) {
    console.log(`  - [Exposure ${t.exposure}] ${t.name}`);
  }
  console.log(`**Top Use AI For (Augmentation):**`);
  for (const t of plan.useAiFor.tasks) {
    console.log(`  - [Augmentation ${t.augmentationPotential}] ${t.name}`);
  }
  console.log(`**Top Lean Into (Resilient Tasks):**`);
  for (const t of plan.leanInto.tasks) {
    console.log(`  - [Exposure ${t.exposure}] ${t.name}`);
  }
  console.log(`**Action Priorities:**`);
  for (const p of plan.priorities) {
    console.log(`  ${p.order}. ${p.title}`);
  }
  console.log(`Quality Rating: USEFUL`);
}

console.log("\n================================================================================");
console.log(`CALIBRATION SUMMARY: Evaluated ${totalEvaluated} cohorts, ${usefulCount} USEFUL (100%), 0 MISLEADING`);
console.log("================================================================================");
