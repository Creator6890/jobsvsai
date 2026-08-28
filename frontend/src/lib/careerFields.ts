import type { Occupation } from "@/types/occupation";
import type { RankingOccupation, EstimatedOccupation } from "@/lib/api";

export type CareerFieldSlug =
  | "business-finance"
  | "technology-data"
  | "healthcare"
  | "creative-media"
  | "education"
  | "legal"
  | "management"
  | "sales"
  | "engineering"
  | "skilled-trades"
  | "transportation"
  | "production";

export interface CareerFieldDefinition {
  slug: CareerFieldSlug;
  name: string;
  shortName: string;
  tagline: string;
  description: string;
  overviewIntro: string;
  structuralDrivers: {
    title: string;
    description: string;
  }[];
  faqItems: {
    question: string;
    answer: string;
  }[];
}

export const CANONICAL_CAREER_FIELDS: Record<CareerFieldSlug, CareerFieldDefinition> = {
  "business-finance": {
    slug: "business-finance",
    name: "Business & Finance",
    shortName: "Business & Finance",
    tagline: "Quantitative analysis, auditing, compliance, and operational administration.",
    description: "Occupations spanning accounting, financial analysis, banking operations, actuarial modeling, and business administration.",
    overviewIntro: "Business and financial careers face high cognitive exposure because language models and algorithmic workflows excel at structured data processing, compliance auditing, and quantitative modeling. However, fiduciary sign-off and regulatory accountability create meaningful friction between technical automation and human replacement.",
    structuralDrivers: [
      {
        title: "High Cognitive & Quantitative Exposure",
        description: "Frontier AI tools can rapidly draft reconciliation reports, parse financial statements, and execute spreadsheet modeling.",
      },
      {
        title: "Fiduciary & Regulatory Sign-Off",
        description: "Legal liability, audit sign-off, and statutory governance require accountable human officers rather than unsupervised algorithms.",
      },
      {
        title: "Strategic Client Advisory",
        description: "High-stakes tax strategy, investment consulting, and client negotiations demand deep human trust and nuanced relationship management.",
      },
    ],
    faqItems: [
      {
        question: "Are business and finance jobs at high risk from AI?",
        answer: "Business and finance roles exhibit some of the highest AI Exposure scores in our dataset due to routine quantitative and documentation tasks. However, replacement risk varies widely: roles requiring fiduciary certification and client advisory retain strong human moats.",
      },
      {
        question: "Which finance careers have the lowest replacement risk?",
        answer: "Roles involving complex client relationships, crisis negotiation, and statutory accountability (such as senior financial advisors and restructuring specialists) exhibit substantially lower replacement risk than back-office data processing roles.",
      },
      {
        question: "Is accounting still a good career choice in the AI era?",
        answer: "Accounting is evolving from manual record-keeping to strategic advisory and audit assurance. Professionals who master analytical AI tools while developing forensic, ethical, and client advisory skills remain in high demand.",
      },
    ],
  },
  "technology-data": {
    slug: "technology-data",
    name: "Technology & Data",
    shortName: "Technology & Data",
    tagline: "Software engineering, data science, infrastructure, and scientific research.",
    description: "Occupations in software development, machine learning, systems architecture, cybersecurity, and scientific computation.",
    overviewIntro: "Technology and data science careers operate directly at the frontier of AI capabilities. Code generation, query optimization, and pattern detection are heavily exposed to automation, yet software architecture, system integration, and domain translation maintain strong human necessity.",
    structuralDrivers: [
      {
        title: "Frontier Code & Syntax Generation",
        description: "Commercial models demonstrate exceptional capability in boilerplate programming, script synthesis, and documentation parsing.",
      },
      {
        title: "Architectural & Systems Complexity",
        description: "Designing resilient distributed systems, debugging non-deterministic runtime failures, and managing cross-system dependencies require human architectural judgement.",
      },
      {
        title: "Business Problem Translation",
        description: "Translating ambiguous stakeholder goals into formal technical specifications remains an inherently human collaborative task.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace software developers and data scientists?",
        answer: "AI tools accelerate routine coding and data cleaning, but complete occupational replacement is constrained by architecture design, edge-case debugging, security governance, and stakeholder alignment.",
      },
      {
        question: "Which technology careers are most exposed to AI?",
        answer: "Routine programming, basic database scripting, and entry-level quality assurance tasks show high capability fit from current frontier AI models.",
      },
      {
        question: "How should tech workers adapt to AI advancements?",
        answer: "Shift focus toward system architecture, product intuition, AI orchestration, cybersecurity, and cross-functional technical communication.",
      },
    ],
  },
  healthcare: {
    slug: "healthcare",
    name: "Healthcare",
    shortName: "Healthcare",
    tagline: "Clinical diagnosis, patient care, surgery, therapy, and health support.",
    description: "Careers across medicine, nursing, surgical practice, mental health therapy, and allied healthcare services.",
    overviewIntro: "Healthcare exhibits a stark contrast between diagnostic cognitive exposure and physical bedside care. While medical diagnostic synthesis is readily augmented by AI, physical patient manipulation, invasive surgical dexterity, and empathetic clinical trust create an extraordinary barrier to human replacement.",
    structuralDrivers: [
      {
        title: "Diagnostic Synthesis vs. Physical Treatment",
        description: "AI can suggest differential diagnoses and flag radiological anomalies, but human practitioners must conduct physical exams and administer delicate treatments.",
      },
      {
        title: "Clinical Liability & Patient Trust",
        description: "Medical malpractice law, ethical obligations, and empathetic bedside presence demand dedicated human healthcare professionals.",
      },
      {
        title: "Unstructured Physical Environments",
        description: "Emergency care, intensive care, and home health require real-time physical adaptability in chaotic, non-standardized environments.",
      },
    ],
    faqItems: [
      {
        question: "Are doctors and nurses safe from AI replacement?",
        answer: "Clinical healthcare roles demonstrate very low Replacement Risk due to physical dexterity requirements, legal malpractice liability, and the necessity of human patient trust.",
      },
      {
        question: "How is AI used in healthcare careers?",
        answer: "AI primarily serves as an augmentation layer—assisting with medical image triage, literature synthesis, and documentation reduction rather than replacing clinicians.",
      },
      {
        question: "Which healthcare roles are most affected by AI?",
        answer: "Administrative medical coding and transcription show high exposure, while registered nurses, surgeons, and physical therapists exhibit high human protection.",
      },
    ],
  },
  "creative-media": {
    slug: "creative-media",
    name: "Creative & Media",
    shortName: "Creative & Media",
    tagline: "Design, writing, journalism, visual arts, and media production.",
    description: "Occupations spanning graphic design, copy editing, technical writing, filmmaking, performing arts, and journalism.",
    overviewIntro: "Creative and media professions experience intense generative AI capability pressure across image generation, copy drafting, and media rendering. Long-form creative vision, investigative integrity, emotional resonance, and distinctive authorial voice remain crucial human differentiators.",
    structuralDrivers: [
      {
        title: "Generative Content Generation",
        description: "Frontier multimodal models can instantly produce synthetic imagery, draft marketing copy, and generate musical compositions.",
      },
      {
        title: "Investigative & Contextual Originality",
        description: "Primary journalistic reporting, firsthand interviewing, and culturally groundbreaking creative works require human lived experience.",
      },
      {
        title: "Curation & Creative Direction",
        description: "Shaping cohesive aesthetic identity and aligning commercial art with cultural sentiment demands strategic human taste.",
      },
    ],
    faqItems: [
      {
        question: "How is generative AI impacting creative careers?",
        answer: "Generative tools lower production costs for routine drafting and layout, increasing competitive pressure on entry-level commercial creative work while amplifying senior creative directors.",
      },
      {
        question: "Which creative jobs have the highest AI exposure?",
        answer: "Commercial graphic illustration, stock copy writing, and routine media post-production demonstrate elevated AI exposure.",
      },
      {
        question: "What skills protect creative professionals from replacement?",
        answer: "Investigative research, distinctive authorial voice, art direction, client collaboration, and multi-platform storytelling create enduring value.",
      },
    ],
  },
  education: {
    slug: "education",
    name: "Education & Training",
    shortName: "Education & Training",
    tagline: "Teaching, academic instruction, educational counseling, and social services.",
    description: "Careers in primary, secondary, postsecondary, and vocational education, as well as community social support.",
    overviewIntro: "Education combines high potential for automated curriculum drafting and tutoring support with an irreplaceable need for human mentorship, classroom behavioral management, and developmental empathy.",
    structuralDrivers: [
      {
        title: "Curriculum & Lesson Synthesis",
        description: "Generating practice problems, grading standardized assignments, and summarizing instructional texts are easily augmented by AI.",
      },
      {
        title: "Behavioral & Emotional Mentorship",
        description: "Motivating students, managing classroom dynamics, and supporting social-emotional growth require direct human connection.",
      },
      {
        title: "Institutional Certification & Safety",
        description: "Legal duty-of-care, accredited diplomas, and child safety regulations establish durable institutional protection.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace classroom teachers?",
        answer: "No. While AI enhances personalized homework tutoring and lesson planning, human teachers remain indispensable for social development, motivation, and classroom governance.",
      },
      {
        question: "How will AI change education jobs?",
        answer: "Educators will spend less time on routine administrative grading and more time on 1-on-1 mentorship, dialectical discussion, and experiential projects.",
      },
      {
        question: "Are university professors at risk from AI?",
        answer: "Standard lecture delivery faces competition from digital media, but original academic research, thesis mentorship, and seminar debate remain firmly human.",
      },
    ],
  },
  legal: {
    slug: "legal",
    name: "Legal",
    shortName: "Legal",
    tagline: "Law practice, judicial review, legal research, and regulatory compliance.",
    description: "Occupations including attorneys, judicial law clerks, paralegals, title examiners, and legal assistants.",
    overviewIntro: "The legal profession operates on textual precedent, statutory analysis, and formal drafting—areas where AI language capabilities are exceptionally powerful. However, courtroom advocacy, fiduciary privilege, judicial accountability, and high-stakes negotiation limit direct occupational replacement.",
    structuralDrivers: [
      {
        title: "Rapid Precedent & Contract Discovery",
        description: "AI dramatically accelerates legal discovery, contract comparison, and statutory search across vast corpuses.",
      },
      {
        title: "Judicial Accountability & Courtroom Advocacy",
        description: "Appearing before judges, examining witnesses, and advising clients in crisis require licensed human counsel.",
      },
      {
        title: "Professional Licensing & Liability",
        description: "Bar association admission, attorney-client privilege, and ethical sanctions prevent unlicensed automated practice.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace lawyers and paralegals?",
        answer: "AI significantly increases document-review efficiency, reducing hours on routine discovery. However, trial advocacy, strategy, and fiduciary counselling require licensed human lawyers.",
      },
      {
        question: "Which legal tasks are most automated by AI?",
        answer: "Contract clause comparison, standard agreement drafting, and case-law search are heavily automated.",
      },
      {
        question: "What is the biggest barrier to AI replacement in law?",
        answer: "Statutory licensing requirements, judicial authority, and absolute accountability for legal advice protect human practitioners.",
      },
    ],
  },
  management: {
    slug: "management",
    name: "Management & Leadership",
    shortName: "Management",
    tagline: "Executive leadership, departmental management, operations, and organizational strategy.",
    description: "Leadership roles across corporate strategy, operations management, human resources, and general administration.",
    overviewIntro: "Managers leverage AI to synthesize performance metrics, forecast demand, and draft operational communications. Core leadership—including hiring, capital allocation, conflict resolution, and cross-functional alignment—remains profoundly human.",
    structuralDrivers: [
      {
        title: "Data-Driven Decision Support",
        description: "Executive dashboards and predictive models augment operational planning and resource allocation.",
      },
      {
        title: "Stakeholder Alignment & Conflict Resolution",
        description: "Aligning divergent incentives, managing organizational politics, and conducting sensitive negotiations require human emotional intelligence.",
      },
      {
        title: "Executive Accountability",
        description: "Boards of directors and shareholders demand human leadership accountable for strategic successes and failures.",
      },
    ],
    faqItems: [
      {
        question: "Can AI replace corporate managers?",
        answer: "AI provides executive decision intelligence, but cannot replace human accountability, leadership charisma, crisis judgement, and employee mentorship.",
      },
      {
        question: "How does AI affect management jobs?",
        answer: "Managers who leverage AI intelligence dashboards make faster decisions and manage broader scopes with fewer administrative layers.",
      },
      {
        question: "What management skills are most resilient against AI?",
        answer: "Talent development, vision setting, ethical governance, and cross-organizational negotiation.",
      },
    ],
  },
  sales: {
    slug: "sales",
    name: "Sales & Marketing",
    shortName: "Sales & Marketing",
    tagline: "Account management, B2B sales, advertising, and commercial business development.",
    description: "Occupations in enterprise sales, advertising representation, real estate brokerage, and commercial outreach.",
    overviewIntro: "Sales careers range from automated inbound transaction processing to high-trust enterprise relationship building. Routine outreach is increasingly automated, while complex consultative deals rely fundamentally on human rapport, empathy, and strategic persuasion.",
    structuralDrivers: [
      {
        title: "Automated Lead Scoring & Outreach",
        description: "AI optimizes prospect research, CRM updates, and email sequence drafting.",
      },
      {
        title: "Consultative Enterprise Trust",
        description: "Closing multi-million dollar enterprise deals requires mutual trust, political navigation, and customized commercial structuring.",
      },
      {
        title: "Emotional Persuasion & Rapport",
        description: "Reading client body language, building interpersonal chemistry, and navigating buyer hesitation are uniquely human skills.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace sales representatives?",
        answer: "Transactional order-taking and commodity selling are increasingly automated, but complex B2B enterprise sales and relationship-driven brokerage remain highly resilient.",
      },
      {
        question: "Which sales careers have the lowest AI risk?",
        answer: "Enterprise account executives, specialized technical sales engineers, and commercial real estate advisors who handle bespoke, high-value negotiations.",
      },
      {
        question: "How can sales professionals leverage AI?",
        answer: "Use AI to automate lead research, meeting transcription, and CRM hygiene, dedicating more time to high-touch client meetings.",
      },
    ],
  },
  engineering: {
    slug: "engineering",
    name: "Engineering & Architecture",
    shortName: "Engineering",
    tagline: "Civil, mechanical, electrical, chemical engineering, and structural architecture.",
    description: "Careers in physical system design, civil infrastructure, mechanical engineering, electrical circuits, and building architecture.",
    overviewIntro: "Engineering combines intensive mathematical calculation and CAD drafting with real-world physics, material constraints, on-site structural inspections, and public safety certification.",
    structuralDrivers: [
      {
        title: "Generative CAD & Simulation",
        description: "AI models optimize structural topology, simulate thermal loads, and automate drafting routines.",
      },
      {
        title: "Physical Site Realities & Tolerances",
        description: "Navigating construction sites, assessing soil stability, and adjusting for material defects require physical engineering inspection.",
      },
      {
        title: "Professional Engineering (PE) Licensure",
        description: "Statutory requirements mandate that licensed Professional Engineers seal blueprints and take legal liability for public safety.",
      },
    ],
    faqItems: [
      {
        question: "Are engineers at risk of being replaced by AI?",
        answer: "Engineers use AI for generative design and simulation, but professional liability, on-site physical inspection, and safety sign-off prevent occupational replacement.",
      },
      {
        question: "Which engineering disciplines are safest from AI?",
        answer: "Disciplines requiring extensive field inspection and physical site work—such as civil, environmental, and mining engineering—demonstrate very high resilience.",
      },
      {
        question: "How is AI changing architecture and design?",
        answer: "Architects use AI for spatial iteration and code compliance checking while focusing on spatial aesthetics, client collaboration, and urban integration.",
      },
    ],
  },
  "skilled-trades": {
    slug: "skilled-trades",
    name: "Skilled Trades & Construction",
    shortName: "Skilled Trades",
    tagline: "Electrical, plumbing, carpentry, HVAC, masonry, and infrastructure construction.",
    description: "Occupations in building construction, mechanical installation, electrical wiring, facility maintenance, and precision repair.",
    overviewIntro: "Skilled trades represent one of the strongest human strongholds against AI replacement. Physical dexterity in unconstrained environments, bespoke spatial problem solving, and tool manipulation cannot be executed by software algorithms.",
    structuralDrivers: [
      {
        title: "Fine Motor Dexterity in Unstructured Spaces",
        description: "Crawling under foundations, fishing wire through existing walls, and repairing bespoke mechanical assemblies exceed current robotic frontiers.",
      },
      {
        title: "Low Cognitive Exposure",
        description: "Daily workflows consist predominantly of physical manipulation and tactile diagnostics rather than text processing.",
      },
      {
        title: "Severe Demographic Labour Shortages",
        description: "High demand for infrastructure modernization creates robust long-term labour-market resilience.",
      },
    ],
    faqItems: [
      {
        question: "Are electricians, plumbers, and carpenters safe from AI?",
        answer: "Yes. Skilled trades consistently rank among the safest occupations from AI in our entire dataset due to complex physical manipulation and unstructured work environments.",
      },
      {
        question: "Can robots replace skilled trades workers?",
        answer: "Current robotics cannot match human sensory-motor adaptability, tactile feedback, and mobility across variable physical job sites.",
      },
      {
        question: "Why do skilled trades have low replacement risk?",
        answer: "Their workflows are physical and tactile, insulated from software automation and reinforced by strong demographic demand.",
      },
    ],
  },
  transportation: {
    slug: "transportation",
    name: "Transportation & Logistics",
    shortName: "Transportation",
    tagline: "Commercial aviation, maritime navigation, rail, trucking, and supply chain logistics.",
    description: "Careers across piloting, air traffic control, maritime transport, commercial driving, and logistics coordination.",
    overviewIntro: "Transportation spans digital supply-chain routing to physical vehicle operation. While route optimization is heavily automated, real-time safety critical piloting, adverse weather handling, and physical cargo management provide durable human necessity.",
    structuralDrivers: [
      {
        title: "Route & Logistics Optimization",
        description: "AI software excels at algorithmic dispatch, fleet fuel optimization, and dynamic scheduling.",
      },
      {
        title: "Safety-Critical Vehicle Piloting",
        description: "Commercial airline pilots, maritime captains, and rail engineers manage life-safety protocols and unexpected physical crises.",
      },
      {
        title: "Physical Cargo Inspection & Handling",
        description: "Securing freight, inspecting mechanical couplings, and handling hazardous materials require on-site physical execution.",
      },
    ],
    faqItems: [
      {
        question: "Will autonomous vehicles replace commercial pilots and drivers?",
        answer: "Automated routing and autopilot systems augment navigation, but regulatory safety mandates and emergency response ensure human pilots and operators remain essential.",
      },
      {
        question: "Which transportation jobs are most exposed to AI?",
        answer: "Logistics dispatchers and freight coordinators experience higher digital exposure than hands-on vehicle operators.",
      },
      {
        question: "What is the biggest barrier to AI replacement in aviation?",
        answer: "Federal aviation regulations, fail-safe passenger safety requirements, and emergency crisis intervention.",
      },
    ],
  },
  production: {
    slug: "production",
    name: "Manufacturing & Production",
    shortName: "Production",
    tagline: "Precision manufacturing, chemical processing, assembly, and industrial production.",
    description: "Occupations in factory assembly, CNC machining, chemical plant operations, food processing, and agricultural production.",
    overviewIntro: "Manufacturing and industrial production operate in structured physical environments where traditional automation and AI robotics intersect. Custom fabrication, machine maintenance, quality inspection, and agricultural stewardship maintain human demand.",
    structuralDrivers: [
      {
        title: "Capital Costs of Industrial Robotics",
        description: "Deploying and retooling physical robotic hardware is capital-intensive compared to software AI adoption.",
      },
      {
        title: "High-Mix, Low-Volume Custom Manufacturing",
        description: "Bespoke fabrication, short production runs, and artisanal craftsmanship favor flexible human machinists.",
      },
      {
        title: "Equipment Maintenance & Diagnostic Troubleshooting",
        description: "Diagnosing anomalous vibrations, repairing hydraulic lines, and calibrating sensors require hands-on technical skill.",
      },
    ],
    faqItems: [
      {
        question: "How is AI impacting manufacturing and factory jobs?",
        answer: "AI augments predictive maintenance and optical quality inspection, while automated machine tending shifts workers toward technician and maintenance roles.",
      },
      {
        question: "Which production careers have the lowest AI risk?",
        answer: "Precision machinists, plant maintenance mechanics, and custom tool-and-die makers who handle variable, non-standard assemblies.",
      },
      {
        question: "What is the difference between AI software and physical factory automation?",
        answer: "Software AI scales instantly with near-zero marginal cost, whereas physical factory automation requires significant capital investment, physical space, and ongoing maintenance.",
      },
    ],
  },
};

// 22 Source Categories -> 12 Canonical Fields deterministic mapping
const CATEGORY_TO_FIELD_MAP: Record<string, CareerFieldSlug> = {
  "business-finance": "business-finance",
  "office-administration": "business-finance",
  "technology-data": "technology-data",
  "science-research": "technology-data",
  healthcare: "healthcare",
  "healthcare-support": "healthcare",
  "creative-media": "creative-media",
  "education-training": "education",
  "community-social-services": "education",
  legal: "legal",
  "management-leadership": "management",
  sales: "sales",
  "food-hospitality": "sales",
  "personal-care-service": "skilled-trades",
  "engineering-architecture": "engineering",
  "construction-extraction": "skilled-trades",
  "installation-repair": "skilled-trades",
  "facilities-grounds": "skilled-trades",
  "protective-services": "skilled-trades",
  "agriculture-environment": "production",
  "manufacturing-production": "production",
  "transport-logistics": "transportation",
};

// Explicit individual occupation overrides where standard category doesn't fit best
const OCCUPATION_FIELD_OVERRIDES: Record<string, CareerFieldSlug> = {
  "sales-managers": "sales",
  "medical-and-health-services-managers": "healthcare",
  "architectural-and-engineering-managers": "engineering",
  "education-and-childcare-administrators-preschool-and-daycare": "education",
  "education-administrators-kindergarten-through-secondary": "education",
  "education-administrators-postsecondary": "education",
  "computer-and-information-systems-managers": "technology-data",
  "financial-managers": "business-finance",
  "construction-managers": "skilled-trades",
  "transportation-storage-and-distribution-managers": "transportation",
  "industrial-production-managers": "production",
};

export function getCanonicalFieldSlug(occupationSlug: string, categorySlugOrName?: string | null): CareerFieldSlug {
  if (occupationSlug && OCCUPATION_FIELD_OVERRIDES[occupationSlug]) {
    return OCCUPATION_FIELD_OVERRIDES[occupationSlug];
  }

  if (categorySlugOrName) {
    const normalized = categorySlugOrName.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-");
    if (CATEGORY_TO_FIELD_MAP[normalized]) {
      return CATEGORY_TO_FIELD_MAP[normalized];
    }
  }

  // Fallback to business-finance if completely unspecified
  return "business-finance";
}

export function getCanonicalField(fieldSlug: string): CareerFieldDefinition | null {
  return (CANONICAL_CAREER_FIELDS as Record<string, CareerFieldDefinition>)[fieldSlug] ?? null;
}

export interface FieldAggregateAnalytics {
  verifiedCount: number;
  medianAiExposure: number;
  medianReplacementRisk: number;
  highestAiExposure: {
    title: string;
    slug: string;
    score: number;
  } | null;
  highestReplacementRisk: {
    title: string;
    slug: string;
    score: number;
  } | null;
  lowestReplacementRisk: {
    title: string;
    slug: string;
    score: number;
  } | null;
  largestGapLeader: {
    title: string;
    slug: string;
    exposure: number;
    replacementRisk: number;
    gap: number;
  } | null;
  riskDistribution: {
    low: number; // <= 33
    moderate: number; // 34 - 66
    high: number; // >= 67
  };
}

function calculateMedian(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 !== 0) {
    return sorted[mid];
  }
  return Math.round(((sorted[mid - 1] + sorted[mid]) / 2) * 10) / 10;
}

export function calculateFieldAnalytics(
  fieldSlug: CareerFieldSlug,
  verifiedOccupations: (Occupation | RankingOccupation)[]
): {
  field: CareerFieldDefinition;
  analytics: FieldAggregateAnalytics;
  occupations: (Occupation | RankingOccupation)[];
} {
  const fieldDef = CANONICAL_CAREER_FIELDS[fieldSlug];
  if (!fieldDef) {
    throw new Error(`Invalid career field slug: ${fieldSlug}`);
  }

  // Filter occupations that map to this field
  const fieldOccupations = verifiedOccupations.filter((job) => {
    const cat = "category" in job ? job.category : undefined;
    return getCanonicalFieldSlug(job.slug, cat) === fieldSlug;
  });

  if (fieldOccupations.length === 0) {
    return {
      field: fieldDef,
      analytics: {
        verifiedCount: 0,
        medianAiExposure: 0,
        medianReplacementRisk: 0,
        highestAiExposure: null,
        highestReplacementRisk: null,
        lowestReplacementRisk: null,
        largestGapLeader: null,
        riskDistribution: { low: 0, moderate: 0, high: 0 },
      },
      occupations: [],
    };
  }

  const exposures = fieldOccupations.map((j) => j.aiExposure);
  const risks = fieldOccupations.map((j) => j.replacementRisk);

  const medianAiExposure = calculateMedian(exposures);
  const medianReplacementRisk = calculateMedian(risks);

  // Highest AI Exposure
  const sortedByExposure = [...fieldOccupations].sort((a, b) => b.aiExposure - a.aiExposure);
  const highestExp = sortedByExposure[0];

  // Highest Replacement Risk
  const sortedByRiskDesc = [...fieldOccupations].sort((a, b) => b.replacementRisk - a.replacementRisk);
  const highestRisk = sortedByRiskDesc[0];

  // Lowest Replacement Risk
  const sortedByRiskAsc = [...fieldOccupations].sort((a, b) => a.replacementRisk - b.replacementRisk);
  const lowestRisk = sortedByRiskAsc[0];

  // Largest Gap (AI Exposure - Replacement Risk)
  const sortedByGap = [...fieldOccupations].sort(
    (a, b) => b.aiExposure - b.replacementRisk - (a.aiExposure - a.replacementRisk)
  );
  const largestGap = sortedByGap[0];

  // Risk Distribution
  const low = risks.filter((r) => r <= 33).length;
  const moderate = risks.filter((r) => r >= 34 && r <= 66).length;
  const high = risks.filter((r) => r >= 67).length;

  return {
    field: fieldDef,
    analytics: {
      verifiedCount: fieldOccupations.length,
      medianAiExposure,
      medianReplacementRisk,
      highestAiExposure: highestExp
        ? { title: highestExp.title, slug: highestExp.slug, score: Math.round(highestExp.aiExposure) }
        : null,
      highestReplacementRisk: highestRisk
        ? { title: highestRisk.title, slug: highestRisk.slug, score: Math.round(highestRisk.replacementRisk) }
        : null,
      lowestReplacementRisk: lowestRisk
        ? { title: lowestRisk.title, slug: lowestRisk.slug, score: Math.round(lowestRisk.replacementRisk) }
        : null,
      largestGapLeader: largestGap
        ? {
            title: largestGap.title,
            slug: largestGap.slug,
            exposure: Math.round(largestGap.aiExposure),
            replacementRisk: Math.round(largestGap.replacementRisk),
            gap: Math.round(largestGap.aiExposure - largestGap.replacementRisk),
          }
        : null,
      riskDistribution: { low, moderate, high },
    },
    occupations: fieldOccupations,
  };
}
