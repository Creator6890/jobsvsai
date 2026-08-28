export interface RelatedOccupation {
  slug: string;
  title: string;
  exposure: number;
  replacementRisk: number;
  reason: string;
}

export interface ResearchArticle {
  slug: string;
  cluster: "UNDERSTANDING AI RISK" | "OCCUPATIONAL RESILIENCE" | "CAREER DECISIONS";
  clusterLabel: string;
  title: string;
  headline: string;
  seoTitle: string;
  description: string;
  datePublished: string;
  dateModified: string;
  readTime: string;
  shortAnswer: string;
  evidenceSection: {
    heading: string;
    paragraphs: string[];
  };
  mechanismSection: {
    heading: string;
    paragraphs: string[];
    keyPoints?: { title: string; text: string }[];
  };
  affectedCareersSection: {
    heading: string;
    paragraphs: string[];
    sampleOccupations: RelatedOccupation[];
  };
  workerImpactSection: {
    heading: string;
    paragraphs: string[];
    actionItems?: string[];
  };
  limitationsSection: {
    heading: string;
    paragraphs: string[];
  };
  relatedArticleSlugs: string[];
}

export const RESEARCH_ARTICLES: Record<string, ResearchArticle> = {
  "ai-exposure-vs-replacement-risk": {
    slug: "ai-exposure-vs-replacement-risk",
    cluster: "UNDERSTANDING AI RISK",
    clusterLabel: "Understanding AI Risk",
    title: "AI Exposure vs Replacement Risk: What's the Difference?",
    headline: "AI Exposure vs Replacement Risk: What's the Difference?",
    seoTitle: "AI Exposure vs Replacement Risk: What's the Difference?",
    description:
      "Why software capability does not equal human replacement. An evidence-led explainer on the structural friction layers separating AI exposure from economic displacement.",
    datePublished: "2026-08-15T00:00:00Z",
    dateModified: "2026-08-25T00:00:00Z",
    readTime: "5 min read",
    shortAnswer:
      "AI Exposure measures the technical overlap between an occupation's task mix and current artificial intelligence capabilities. Replacement Risk measures whether that technical capability translates into net human job displacement after accounting for physical manipulation, legal accountability, adoption economics, and labour-market resilience.",
    evidenceSection: {
      heading: "What the JobsVsAI Evidence Shows",
      paragraphs: [
        "Across the 507 verified occupations in the JobsVsAI corpus, AI Exposure and Replacement Risk frequently diverge by 20 to 50 points. A high exposure score alone does not guarantee a high replacement risk.",
        "For example, Airline Pilots, Acute Care Nurses, and Civil Engineers exhibit high or moderate AI Exposure because diagnostic, simulation, and routing tasks overlap heavily with software capabilities. Yet their Replacement Risk remains remarkably low due to life-safety liability, on-site physical interventions, and strict regulatory licensing requirements.",
        "Conversely, back-office data processing and basic document transcription exhibit tight convergence between exposure and replacement because few physical or regulatory friction layers protect the role from automated substitution.",
      ],
    },
    mechanismSection: {
      heading: "Why Software Capability and Economic Replacement Diverge",
      paragraphs: [
        "Technical capability is only the first condition for automation. In the real economy, four distinct structural friction layers govern whether an exposed task can actually replace a human professional:",
      ],
      keyPoints: [
        {
          title: "1. Environmental & Physical Dependency",
          text: "Software cannot navigate non-standardized physical spaces, handle delicate physical tools, or perform dexterous real-time manipulation without expensive, fragile robotic hardware.",
        },
        {
          title: "2. Fiduciary Trust & Legal Accountability",
          text: "When critical errors carry legal liability, financial penalties, or physical danger, organizations require licensed human professionals (e.g. licensed accountants, certified doctors, registered engineers) to review and sign off.",
        },
        {
          title: "3. Enterprise Adoption Economics",
          text: "Integrating AI into complex legacy enterprise software, re-training staff, ensuring cybersecurity compliance, and restructuring workflows entail major capital expenditures and multi-year adoption timelines.",
        },
        {
          title: "4. Labour-Market Elasticity & Resilience",
          text: "Occupations facing severe structural labour shortages or high wage flexibility often absorb AI tools to clear backlogs rather than downsizing headcounts.",
        },
      ],
    },
    affectedCareersSection: {
      heading: "Representative Occupations & Evidence Examples",
      paragraphs: [
        "Comparing specific occupations in our verified dataset illustrates how structural friction creates distinct risk profiles:",
      ],
      sampleOccupations: [
        {
          slug: "accountant",
          title: "Accountant",
          exposure: 67,
          replacementRisk: 61,
          reason: "High routine quantitative and auditing exposure, tempered by statutory audit sign-off requirements and strategic tax consulting.",
        },
        {
          slug: "acute-care-nurses",
          title: "Acute Care Nurses",
          exposure: 52,
          replacementRisk: 19,
          reason: "Moderate diagnostic exposure offset by critical emergency physical interventions and direct patient bedside trust.",
        },
        {
          slug: "aerospace-engineers",
          title: "Aerospace Engineers",
          exposure: 64,
          replacementRisk: 28,
          reason: "Heavy simulation and mathematical computation exposure protected by flight-safety certification and physical wind-tunnel validation.",
        },
      ],
    },
    workerImpactSection: {
      heading: "What This Means for Workers",
      paragraphs: [
        "If your occupation has high AI Exposure but low Replacement Risk, your day-to-day workflow will change dramatically through AI tooling, but your overall job demand is structurally protected. Your goal should be mastering software copilot tools to multiply your personal productivity.",
        "If your occupation exhibits both high AI Exposure and high Replacement Risk, routine task substitution is already underway. Workers in these roles should actively expand into strategic advisory, client relationship management, and complex cross-disciplinary coordination.",
      ],
      actionItems: [
        "Audit your daily tasks: separate screen-based routine tasks from relationship and physical problem-solving.",
        "Embrace AI workflows early: professionals who orchestrate AI tools outcompete those who resist them.",
        "Position yourself near human sign-off points where legal liability and executive trust reside.",
      ],
    },
    limitationsSection: {
      heading: "Methodological Limitations",
      paragraphs: [
        "JobsVsAI scores are relative structural indices, not predictive economic forecasts. Macroeconomic conditions, future breakthroughs in general-purpose robotics, and statutory regulatory shifts may alter friction layer dynamics over multi-year horizons.",
      ],
    },
    relatedArticleSlugs: [
      "why-ai-automates-tasks-before-whole-jobs",
      "which-jobs-are-most-at-risk-from-ai",
      "which-jobs-are-safest-from-ai",
    ],
  },

  "why-ai-automates-tasks-before-whole-jobs": {
    slug: "why-ai-automates-tasks-before-whole-jobs",
    cluster: "UNDERSTANDING AI RISK",
    clusterLabel: "Understanding AI Risk",
    title: "Why AI Automates Tasks Before Whole Jobs",
    headline: "Why AI Automates Tasks Before Whole Jobs",
    seoTitle: "Why AI Automates Tasks Before Whole Jobs",
    description:
      "How task-level workflow unbundling explains occupational transformation. Why AI transforms day-to-day job composition long before eliminating headcounts.",
    datePublished: "2026-08-16T00:00:00Z",
    dateModified: "2026-08-25T00:00:00Z",
    readTime: "4 min read",
    shortAnswer:
      "Occupations are heterogeneous bundles of cognitive, administrative, interpersonal, and physical tasks. Because AI advances unevenly across capability dimensions, it accelerates specific routine and textual tasks first, unbundling job workflows and increasing worker productivity long before a full occupation can be automated.",
    evidenceSection: {
      heading: "Task Heterogeneity in the JobsVsAI Dataset",
      paragraphs: [
        "In our assessment of 8,218 O*NET task statements across 507 verified occupations, virtually no occupation consists solely of 100% automated tasks or 100% immune tasks.",
        "Even heavily exposed occupations such as Editors or Computer Programmers contain critical tasks—such as author coaching, architectural systems trade-offs, and ambiguous requirement clarification—that resist pure algorithmic execution.",
        "Conversely, highly resilient trades like Electricians still incorporate routine administrative documentation and schematic review that AI tools streamline without displacing the core tactile tradecraft.",
      ],
    },
    mechanismSection: {
      heading: "The Mechanism of Task Unbundling",
      paragraphs: [
        "When an AI system automates a sub-task, the economic outcome depends on whether the saved time allows the professional to handle higher volume, take on more complex analysis, or expand service quality:",
      ],
      keyPoints: [
        {
          title: "The Complementarity Effect",
          text: "When AI makes a routine sub-task (like data cleaning or initial draft synthesis) 10x faster and cheaper, demand for the complementary human task (like strategic validation and decision execution) frequently increases.",
        },
        {
          title: "Bottleneck Constraints",
          text: "A job process is only as fast as its slowest manual bottleneck. If an architect can generate 50 floorplans in seconds but still requires on-site zoning meetings and structural safety seals, the total job headcount does not collapse overnight.",
        },
      ],
    },
    affectedCareersSection: {
      heading: "Examples of Workflow Transformation",
      paragraphs: [
        "Examining how task bundles shift in verified occupations demonstrates this dynamic:",
      ],
      sampleOccupations: [
        {
          slug: "editors",
          title: "Editors",
          exposure: 78,
          replacementRisk: 68,
          reason: "Automated spellcheck and structural proofreading free up time for investigative development, tone modulation, and author collaboration.",
        },
        {
          slug: "computer-programmers",
          title: "Computer Programmers",
          exposure: 81,
          replacementRisk: 64,
          reason: "Automated syntax completion and boilerplate generation shift programmer workloads toward architecture, distributed state management, and edge-case testing.",
        },
        {
          slug: "architects-except-landscape-and-naval",
          title: "Architects",
          exposure: 58,
          replacementRisk: 26,
          reason: "Generative spatial iteration speeds drafting, but client negotiation, site topography inspection, and building code sign-off keep the human architect essential.",
        },
      ],
    },
    workerImpactSection: {
      heading: "Actionable Guidance for Professionals",
      paragraphs: [
        "Do not view your job as a single monolith. Instead, decompose your role into its constituent tasks and categorize them by AI affinity:",
      ],
      actionItems: [
        "Delegate your high-exposure, low-context sub-tasks (first-pass drafting, transcription, basic data aggregation) to AI tools.",
        "Reinvest the reclaimed hours into high-friction tasks: client rapport, strategic synthesis, crisis resolution, and executive communication.",
        "Become the designated workflow architect in your team who connects AI outputs to reliable business results.",
      ],
    },
    limitationsSection: {
      heading: "Limitations",
      paragraphs: [
        "As multimodal models and agentic workflows advance, the boundary between automatable sub-tasks and human bottlenecks will continue to evolve. Regular task reassessment is necessary.",
      ],
    },
    relatedArticleSlugs: [
      "ai-exposure-vs-replacement-risk",
      "which-jobs-are-most-at-risk-from-ai",
      "what-to-do-if-your-job-has-high-ai-risk",
    ],
  },

  "which-jobs-are-most-at-risk-from-ai": {
    slug: "which-jobs-are-most-at-risk-from-ai",
    cluster: "OCCUPATIONAL RESILIENCE",
    clusterLabel: "Occupational Resilience",
    title: "Which Jobs Are Most at Risk From AI?",
    headline: "Which Jobs Are Most at Risk From AI?",
    seoTitle: "Which Jobs Are Most at Risk From AI? Ranked Findings",
    description:
      "A calm, data-backed analysis of the highest-risk occupations in the JobsVsAI verified dataset. What structural characteristics make jobs vulnerable to automation.",
    datePublished: "2026-08-17T00:00:00Z",
    dateModified: "2026-08-26T00:00:00Z",
    readTime: "6 min read",
    shortAnswer:
      "Within the JobsVsAI Verified corpus, the highest Replacement Risk occupations share four key traits: high proportion of routine screen-based document tasks, low requirement for physical dexterity or unstructured navigation, minimal statutory sign-off friction, and high commercial adoption pressure.",
    evidenceSection: {
      heading: "Characteristics of High-Risk Occupations",
      paragraphs: [
        "Analyzing verified occupations with Replacement Risk scores above 67 reveals distinct commonalities across industries.",
        "These roles typically involve translating structured inputs into standardized outputs: processing forms, summarizing standardized records, verifying routine compliance, and generating derivative text or basic scripts.",
        "Crucially, high replacement risk occurs not simply when AI can do the task, but when organizational workflows can easily bypass human review without exposing the business to catastrophic liability or physical breakdown.",
      ],
    },
    mechanismSection: {
      heading: "The Anatomy of High Structural Vulnerability",
      paragraphs: [
        "High-risk roles generally lack the structural moats that insulate other professions:",
      ],
      keyPoints: [
        {
          title: "Standardized Digital Workflows",
          text: "Work that takes place entirely within web browsers, spreadsheets, and databases is inherently accessible to API integration and autonomous AI agent execution.",
        },
        {
          title: "Lack of Physical & Spatial Moats",
          text: "Zero requirement for physical presence or tool handling removes robotics hardware as a deployment barrier.",
        },
        {
          title: "Low Regulatory & Licensing Barriers",
          text: "Roles that do not require state licensing, bar admission, medical board seals, or professional engineering liability are faster for enterprises to restructure.",
        },
      ],
    },
    affectedCareersSection: {
      heading: "Highest-Risk Verified Occupations in our Corpus",
      paragraphs: [
        "The following occupations exhibit elevated Replacement Risk scores in the JobsVsAI verified dataset:",
      ],
      sampleOccupations: [
        {
          slug: "medical-transcriptionists",
          title: "Medical Transcriptionists",
          exposure: 88,
          replacementRisk: 86,
          reason: "High audio and language synthesis capabilities allow automated speech-to-text models to generate clinical notes with minimal intermediate human typing.",
        },
        {
          slug: "bill-and-account-collectors",
          title: "Bill and Account Collectors",
          exposure: 82,
          replacementRisk: 78,
          reason: "Automated communication workflows, predictive payment propensity models, and multi-channel conversational agents handle routine collection outreach.",
        },
        {
          slug: "title-examiners-abstractors-and-searchers",
          title: "Title Examiners & Searchers",
          exposure: 84,
          replacementRisk: 76,
          reason: "Optical character recognition and automated public record indexing streamline deed, mortgage, and title deed searches.",
        },
      ],
    },
    workerImpactSection: {
      heading: "Strategic Advice for High-Risk Workers",
      paragraphs: [
        "A high risk score is not a destiny; it is an early diagnostic signal. Workers in vulnerable positions should prioritize three transition strategies:",
      ],
      actionItems: [
        "Transition from execution to exception handling: focus on resolving anomalies, complex edge cases, and high-value disputes.",
        "Leverage adjacent transferable skills to pivot into related occupations with lower replacement risk.",
        "Acquire operational AI supervision skills to manage automated workflow pipelines rather than competing against them.",
      ],
    },
    limitationsSection: {
      heading: "Dataset Context",
      paragraphs: [
        "Scores reflect structural vulnerability relative to the 507 verified occupations analyzed under our current capability taxonomy. Individual employer adoption speeds and regional market conditions vary significantly.",
      ],
    },
    relatedArticleSlugs: [
      "ai-exposure-vs-replacement-risk",
      "which-jobs-are-safest-from-ai",
      "what-to-do-if-your-job-has-high-ai-risk",
    ],
  },

  "which-jobs-are-safest-from-ai": {
    slug: "which-jobs-are-safest-from-ai",
    cluster: "OCCUPATIONAL RESILIENCE",
    clusterLabel: "Occupational Resilience",
    title: "Which Jobs Are Safest From AI?",
    headline: "Which Jobs Are Safest From AI?",
    seoTitle: "Which Jobs Are Safest From AI? Human Resilience Analysis",
    description:
      "Why physical dexterity, empathetic human trust, and statutory accountability form enduring barriers to AI replacement. Verified safe careers analyzed.",
    datePublished: "2026-08-17T00:00:00Z",
    dateModified: "2026-08-26T00:00:00Z",
    readTime: "5 min read",
    shortAnswer:
      "The most resilient occupations against AI replacement rely heavily on three durable human moats: manual dexterity in unpredictable physical environments, direct high-stakes interpersonal empathy and crisis negotiation, and statutory legal liability requiring a certified human sign-off.",
    evidenceSection: {
      heading: "The Human Strongholds in the JobsVsAI Corpus",
      paragraphs: [
        "Across our 507 verified occupations, roles with Replacement Risk scores below 33 consistently demonstrate deep physical and interpersonal anchors.",
        "Skilled physical trades (such as Electricians, Plumbers, and Commercial Divers), clinical acute-care healthcare providers, emergency first responders, and physical engineering inspectors exhibit strong resistance to software automation.",
        "Even when AI models assist these workers with diagnostic lookup or documentation, the core value proposition remains the tactile physical execution and human presence.",
      ],
    },
    mechanismSection: {
      heading: "The Three Structural Pillars of Occupational Safety",
      paragraphs: [
        "Our multi-factor scoring architecture identifies three primary structural barriers to replacement:",
      ],
      keyPoints: [
        {
          title: "1. The Spatial-Motor Barrier",
          text: "Robotic manipulation in unconstrained dynamic spaces (crawling under floor joists, repairing vibrating machinery in rain, navigating emergency trauma wards) remains decades behind pure software AI.",
        },
        {
          title: "2. The Empathy and High-Stakes Rapport Barrier",
          text: "Patients in medical distress, families in crisis, students requiring motivation, and parties in high-stakes negotiations demand human presence, body language, and empathetic connection.",
        },
        {
          title: "3. The Institutional Accountability Seal",
          text: "Society demands an accountable human agent when lives, public infrastructure, or constitutional liberties are at stake.",
        },
      ],
    },
    affectedCareersSection: {
      heading: "Lowest-Risk Verified Occupations in our Corpus",
      paragraphs: [
        "The following occupations represent top resilience performers in our verified dataset:",
      ],
      sampleOccupations: [
        {
          slug: "commercial-divers",
          title: "Commercial Divers",
          exposure: 18,
          replacementRisk: 14,
          reason: "Underwater construction, welding, and hazard inspection in extreme physical environments inaccessible to software.",
        },
        {
          slug: "acute-care-nurses",
          title: "Acute Care Nurses",
          exposure: 52,
          replacementRisk: 19,
          reason: "Complex real-time physical patient monitoring, emergency bedside procedures, and vital empathetic care.",
        },
        {
          slug: "fire-inspectors-and-investigators",
          title: "Fire Inspectors & Investigators",
          exposure: 44,
          replacementRisk: 22,
          reason: "On-site physical burn pattern forensic analysis, structural safety walk-throughs, and legal courtroom testimony.",
        },
      ],
    },
    workerImpactSection: {
      heading: "Key Takeaways for Career Planning",
      paragraphs: [
        "For students, career switchers, and job seekers navigating the AI transition:",
      ],
      actionItems: [
        "Cultivate physical-world skills and craftsmanship: technical skills that touch real matter and machinery are insulated from digital automation.",
        "Develop high-touch interpersonal capabilities: counseling, negotiation, executive coaching, and team leadership.",
        "Pursue licensed credentials where statutory regulations anchor human responsibility.",
      ],
    },
    limitationsSection: {
      heading: "Methodological Note",
      paragraphs: [
        "Low AI replacement risk does not mean immunity from broader economic forces such as interest rates, trade policy, or demographic shifts. It specifically measures insulation from artificial intelligence substitution.",
      ],
    },
    relatedArticleSlugs: [
      "ai-exposure-vs-replacement-risk",
      "which-jobs-are-most-at-risk-from-ai",
      "what-to-do-if-your-job-has-high-ai-risk",
    ],
  },

  "what-to-do-if-your-job-has-high-ai-risk": {
    slug: "what-to-do-if-your-job-has-high-ai-risk",
    cluster: "CAREER DECISIONS",
    clusterLabel: "Career Decisions",
    title: "What Should You Do If Your Job Has High AI Risk?",
    headline: "What Should You Do If Your Job Has High AI Risk?",
    seoTitle: "What Should You Do If Your Job Has High AI Risk? Career Action Plan",
    description:
      "A proactive, evidence-led framework for navigating career risk from AI. How to unbundle your role, master AI orchestration, and pivot toward resilient domains.",
    datePublished: "2026-08-18T00:00:00Z",
    dateModified: "2026-08-26T00:00:00Z",
    readTime: "6 min read",
    shortAnswer:
      "Receiving a high AI risk rating is an early diagnostic indicator for career evolution, not a forecast of sudden unemployment. Professionals should unbundle their daily task mix, master commercial AI tooling to become indispensable orchestrators, and actively build complementary human strengths in client advisory, exception management, and domain specialization.",
    evidenceSection: {
      heading: "Understanding What High Risk Actually Means",
      paragraphs: [
        "A high Replacement Risk score (67–100) indicates that a substantial majority of your occupation's task mix is technically feasible for AI automation and faces low structural friction.",
        "However, corporate adoption happens over years, not weeks. Organizations must test, integrate, audit, and manage change across enterprise systems. This operational lag creates a multi-year window of opportunity for forward-thinking workers to reposition themselves.",
      ],
    },
    mechanismSection: {
      heading: "The Four-Stage Career Adaptation Framework",
      paragraphs: [
        "Rather than competing directly against AI capabilities, successful workers evolve from routine task executors into strategic AI conductors:",
      ],
      keyPoints: [
        {
          title: "Stage 1: Deconstruct Your Task Portfolio",
          text: "Break your weekly hours into routine documentation/synthesis vs. relationship management, exception resolution, and physical oversight. Identify which 20% of your work produces 80% of human value.",
        },
        {
          title: "Stage 2: Become the Top AI Practitioner in Your Domain",
          text: "Adopt frontier AI copilots aggressively. An accountant or programmer who uses AI to deliver 5x faster with zero errors becomes far more valuable to their employer than a slow manual practitioner.",
        },
        {
          title: "Stage 3: Move Upstream to Problem Definition & Governance",
          text: "Shift your focus from drafting answers to defining problems, validating synthetic outputs, ensuring regulatory compliance, and managing stakeholder expectations.",
        },
        {
          title: "Stage 4: Explore Career Transitions and Adjacent Fields",
          text: "Leverage your core analytical or industry background to pivot toward specialized roles with stronger structural moats (e.g. pivoting from general bookkeeping to forensic tax advisory or systems implementation).",
        },
      ],
    },
    affectedCareersSection: {
      heading: "Examples of Proactive Career Evolution",
      paragraphs: [
        "How professionals in high-exposure roles can pivot toward higher resilience:",
      ],
      sampleOccupations: [
        {
          slug: "paralegals-and-legal-assistants",
          title: "Paralegals & Legal Assistants",
          exposure: 85,
          replacementRisk: 72,
          reason: "Pivot from routine document discovery toward litigation trial management, client interviewing, and legal operations technology consulting.",
        },
        {
          slug: "customer-service-representatives",
          title: "Customer Service Representatives",
          exposure: 84,
          replacementRisk: 79,
          reason: "Transition from tier-1 scripted query handling toward enterprise account retention, crisis escalation management, and customer success leadership.",
        },
        {
          slug: "graphic-designers",
          title: "Graphic Designers",
          exposure: 76,
          replacementRisk: 62,
          reason: "Evolve from producing stock banners and layout variations into brand identity direction, cross-platform creative strategy, and physical experiential design.",
        },
      ],
    },
    workerImpactSection: {
      heading: "Immediate Action Checklist",
      paragraphs: [
        "Take these concrete steps over the next 30 days to strengthen your career security:",
      ],
      actionItems: [
        "Run your occupation through the JobsVsAI Career Fit assessment to identify your natural work strengths.",
        "Identify 3 repetitive tasks you perform each week and build an automated prompt workflow to accelerate them.",
        "Take on projects requiring cross-departmental negotiation, executive presentation, or client relationship management.",
        "Research adjacent career paths in your field that offer higher human resilience and lower replacement risk.",
      ],
    },
    limitationsSection: {
      heading: "Important Caveat",
      paragraphs: [
        "Career transitions require time, deliberate practice, and occasionally formal re-credentialing. Use JobsVsAI data as an objective intelligence layer to inform your long-term professional development.",
      ],
    },
    relatedArticleSlugs: [
      "ai-exposure-vs-replacement-risk",
      "why-ai-automates-tasks-before-whole-jobs",
      "which-jobs-are-most-at-risk-from-ai",
    ],
  },
};

export function getResearchArticle(slug: string): ResearchArticle | null {
  return RESEARCH_ARTICLES[slug] ?? null;
}

export function getAllResearchArticles(): ResearchArticle[] {
  return Object.values(RESEARCH_ARTICLES);
}
