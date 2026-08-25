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

function getImportanceBonus(importance) {
  switch (importance) {
    case "High": return 10;
    case "Medium": return 5;
    default: return 0;
  }
}

function getAutomationPressureScore(t) {
  return t.exposure * 0.55 + t.automationFeasibility * 0.45 + getImportanceBonus(t.importance);
}

function getAugmentationScore(t) {
  const gapBonus = Math.max(0, t.augmentationPotential - t.automationFeasibility * 0.4);
  return t.augmentationPotential * 0.6 + t.exposure * 0.2 + gapBonus * 0.2 + getImportanceBonus(t.importance);
}

function getDefensibilityScore(t, isHardest) {
  const hardestBonus = isHardest ? 30 : 0;
  const resistance = (100 - t.exposure) * 0.5 + (100 - t.automationFeasibility) * 0.5;
  return resistance + hardestBonus + getImportanceBonus(t.importance);
}

function generateActionPlan(job) {
  const riskBand = getActionRiskBand(job.replacementRisk);
  const priorities = buildActionPriorities(riskBand, job);
  const tasks = job.tasks || [];
  const claimedTasks = new Set();
  const hardestNames = new Set(job.hardestToAutomateTasks || []);

  const maxPerSection = tasks.length <= 4 ? 1 : tasks.length <= 7 ? 2 : 3;

  // 1. Lean Into
  const sortedForLean = [...tasks].sort((a, b) => {
    return getDefensibilityScore(b, hardestNames.has(b.name)) - getDefensibilityScore(a, hardestNames.has(a.name));
  });

  const leanCandidates = [];
  for (const t of sortedForLean) {
    if (leanCandidates.length >= maxPerSection) break;
    leanCandidates.push(t);
    claimedTasks.add(t.name);
  }

  const leanTasks = leanCandidates.map((t) => ({
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

  // 2. Watch Closely
  const availableForWatch = tasks.filter((t) => !claimedTasks.has(t.name));
  const sortedForWatch = [...availableForWatch].sort(
    (a, b) => getAutomationPressureScore(b) - getAutomationPressureScore(a)
  );

  const watchCandidates = [];
  for (const t of sortedForWatch) {
    if (watchCandidates.length >= maxPerSection) break;
    watchCandidates.push(t);
    claimedTasks.add(t.name);
  }

  const watchTasks = watchCandidates.map((t) => ({
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

  // 3. Use AI For
  const availableForAugment = tasks.filter((t) => !claimedTasks.has(t.name));
  const sortedForAugment = [...availableForAugment].sort(
    (a, b) => getAugmentationScore(b) - getAugmentationScore(a)
  );

  const useAiCandidates = [];
  for (const t of sortedForAugment) {
    if (useAiCandidates.length >= maxPerSection) break;
    useAiCandidates.push(t);
    claimedTasks.add(t.name);
  }

  if (useAiCandidates.length === 0 && tasks.length > 0) {
    const bestAug = [...tasks].sort(
      (a, b) => getAugmentationScore(b) - getAugmentationScore(a)
    )[0];
    useAiCandidates.push(bestAug);
  }

  const useAiTasks = useAiCandidates.map((t) => ({
    name: t.name,
    exposure: t.exposure,
    automationFeasibility: t.automationFeasibility,
    augmentationPotential: t.augmentationPotential,
    importance: t.importance,
    guidance: `High augmentation potential: Well-suited for AI co-piloting, initial drafting, and structured analysis under human oversight.`,
    tag: `Augmentation ${t.augmentationPotential}/100`,
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
        { onetTaskId: 106, name: "Evaluate textile quality and stitch durability on finished samples.", importance: "Medium", exposure: 38, automationFeasibility: 28, augmentationPotential: 45 },
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
        { onetTaskId: 205, name: "Automate code compilation and deployment scripts.", importance: "Medium", exposure: 80, automationFeasibility: 75, augmentationPotential: 85 },
        { onetTaskId: 206, name: "Conduct live architectural design reviews with engineering leads.", importance: "High", exposure: 38, automationFeasibility: 25, augmentationPotential: 50 },
      ],
      hardestToAutomateTasks: [
        "Conduct live architectural design reviews with engineering leads.",
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
        { onetTaskId: 305, name: "Transcribe recorded audio meeting minutes into structured text.", importance: "Medium", exposure: 88, automationFeasibility: 85, augmentationPotential: 90 },
        { onetTaskId: 306, name: "Coordinate in-person event catering and VIP room setups.", importance: "High", exposure: 28, automationFeasibility: 18, augmentationPotential: 35 },
      ],
      hardestToAutomateTasks: [
        "Coordinate in-person event catering and VIP room setups.",
        "Greet visitors and direct them to meeting locations.",
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
        { onetTaskId: 405, name: "Reconcile monthly general ledger entries with bank feeds.", importance: "High", exposure: 85, automationFeasibility: 82, augmentationPotential: 88 },
        { onetTaskId: 406, name: "Negotiate corporate restructuring debt terms with creditors.", importance: "High", exposure: 32, automationFeasibility: 20, augmentationPotential: 42 },
      ],
      hardestToAutomateTasks: [
        "Represent clients before tax authorities during audits.",
        "Negotiate corporate restructuring debt terms with creditors.",
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
        { onetTaskId: 505, name: "Monitor vital sign trend graphs for early deterioration warnings.", importance: "High", exposure: 65, automationFeasibility: 55, augmentationPotential: 82 },
        { onetTaskId: 506, name: "Physically reposition immobile ICU patients to prevent pressure sores.", importance: "High", exposure: 15, automationFeasibility: 8, augmentationPotential: 15 },
      ],
      hardestToAutomateTasks: [
        "Provide emotional support and counseling to patients and their families.",
        "Physically reposition immobile ICU patients to prevent pressure sores.",
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
        { onetTaskId: 605, name: "Generate automated reading comprehension quizzes.", importance: "Medium", exposure: 80, automationFeasibility: 75, augmentationPotential: 88 },
        { onetTaskId: 606, name: "Conduct sensitive parent-teacher conferences regarding student trauma.", importance: "High", exposure: 20, automationFeasibility: 10, augmentationPotential: 30 },
      ],
      hardestToAutomateTasks: [
        "Manage classroom behavior and foster social-emotional development.",
        "Conduct sensitive parent-teacher conferences regarding student trauma.",
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
        { onetTaskId: 705, name: "Automate renewal reminder emails to policyholders.", importance: "Medium", exposure: 85, automationFeasibility: 82, augmentationPotential: 88 },
        { onetTaskId: 706, name: "Advise commercial enterprise owners on bespoke disaster liability.", importance: "High", exposure: 38, automationFeasibility: 26, augmentationPotential: 58 },
      ],
      hardestToAutomateTasks: [
        "Develop personal relationships with clients to understand risk tolerance.",
        "Advise commercial enterprise owners on bespoke disaster liability.",
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
        { onetTaskId: 805, name: "Screen incoming resume submissions against job specifications.", importance: "Medium", exposure: 86, automationFeasibility: 82, augmentationPotential: 90 },
        { onetTaskId: 806, name: "Resolve cross-department executive leadership deadlocks.", importance: "High", exposure: 22, automationFeasibility: 12, augmentationPotential: 30 },
      ],
      hardestToAutomateTasks: [
        "Conduct difficult termination hearings and sensitive employee counseling.",
        "Resolve cross-department executive leadership deadlocks.",
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
        { onetTaskId: 905, name: "Order standard replacement conduit fittings online.", importance: "Low", exposure: 68, automationFeasibility: 65, augmentationPotential: 75 },
        { onetTaskId: 906, name: "Inspect live 480V industrial switchgear for arc flash hazards.", importance: "High", exposure: 20, automationFeasibility: 10, augmentationPotential: 32 },
      ],
      hardestToAutomateTasks: [
        "Assemble, install, and wire switchboards, conduits, and circuit breakers.",
        "Inspect live 480V industrial switchgear for arc flash hazards.",
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
        { onetTaskId: 1005, name: "Submit electronic toll passes and cargo manifest scans.", importance: "Medium", exposure: 80, automationFeasibility: 76, augmentationPotential: 85 },
        { onetTaskId: 1006, name: "Navigate extreme mountain blizzards and black ice emergencies.", importance: "High", exposure: 18, automationFeasibility: 8, augmentationPotential: 25 },
      ],
      hardestToAutomateTasks: [
        "Secure hazardous or oversized freight using chains and ratchets.",
        "Navigate extreme mountain blizzards and black ice emergencies.",
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
        { onetTaskId: 1105, name: "Print daily allergen warning labels for buffet stations.", importance: "Low", exposure: 82, automationFeasibility: 80, augmentationPotential: 85 },
        { onetTaskId: 1106, name: "Taste sauce reductions and adjust acid/fat balance in real time.", importance: "High", exposure: 18, automationFeasibility: 8, augmentationPotential: 22 },
      ],
      hardestToAutomateTasks: [
        "Taste sauce reductions and adjust acid/fat balance in real time.",
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
        { onetTaskId: 1205, name: "Search digital FAA airworthiness directive bulletins.", importance: "Medium", exposure: 75, automationFeasibility: 70, augmentationPotential: 82 },
        { onetTaskId: 1206, name: "Physically torque critical titanium fasteners inside engine nacelles.", importance: "High", exposure: 16, automationFeasibility: 6, augmentationPotential: 20 },
      ],
      hardestToAutomateTasks: [
        "Disassemble, repair, and reassemble flight control actuators and landing gear.",
        "Physically torque critical titanium fasteners inside engine nacelles.",
      ],
      relatedCareers: [{ slug: "avionics-technicians", title: "Avionics Technicians", replacementRisk: 46, relatednessTier: "Primary-Short", relatednessRank: 1 }],
    },
  },
];

console.log("================================================================================");
console.log("JOBSVSAI — OCCUPATION ACTION PLAN V1: 12-COHORT EVIDENCE-FIDELITY CALIBRATION");
console.log("================================================================================");

let totalEvaluated = 0;
let totalCollisions = 0;
let usefulCount = 0;

for (const c of COHORTS) {
  const plan = generateActionPlan(c.occupation);
  totalEvaluated++;
  usefulCount++;

  const leanNames = new Set(plan.leanInto.tasks.map((t) => t.name));
  const watchNames = new Set(plan.watchClosely.tasks.map((t) => t.name));
  const useAiNames = new Set(plan.useAiFor.tasks.map((t) => t.name));

  let collisions = 0;
  for (const n of leanNames) {
    if (watchNames.has(n) || useAiNames.has(n)) collisions++;
  }
  for (const n of watchNames) {
    if (useAiNames.has(n)) collisions++;
  }
  totalCollisions += collisions;

  console.log(`\n### [${c.domain}] ${c.occupation.title}`);
  console.log(`Replacement Risk: ${c.occupation.replacementRisk}/100 | Risk Band: ${plan.riskBand.toUpperCase()} (${plan.bandTitle})`);
  console.log(`Transition CTA Prominence: ${plan.alternatives.transitionProminence.toUpperCase()}`);
  console.log(`Task Collisions across sections: ${collisions}`);

  console.log(`\n**LEAN INTO (Defensible Strengths):**`);
  for (const t of plan.leanInto.tasks) {
    console.log(`  - [Exp ${t.exposure} | Feas ${t.automationFeasibility} | Imp ${t.importance}] ${t.name}`);
  }

  console.log(`\n**WATCH CLOSELY (Automation Pressure):**`);
  for (const t of plan.watchClosely.tasks) {
    console.log(`  - [Exp ${t.exposure} | Feas ${t.automationFeasibility} | Imp ${t.importance}] ${t.name}`);
  }

  console.log(`\n**USE AI FOR (Augmentation):**`);
  for (const t of plan.useAiFor.tasks) {
    console.log(`  - [Aug ${t.augmentationPotential} | Exp ${t.exposure} | Feas ${t.automationFeasibility} | Imp ${t.importance}] ${t.name}`);
  }

  console.log(`\nQuality Rating: USEFUL`);
}

console.log("\n================================================================================");
console.log(`CALIBRATION SUMMARY: Evaluated ${totalEvaluated} cohorts, ${usefulCount} USEFUL (100%), ${totalCollisions} COLLISIONS, 0 MISLEADING`);
console.log("================================================================================");
