import type { Occupation } from "@/types/occupation";
import type { RankingOccupation } from "@/lib/api";

export type CareerFieldSlug =
  | "business-finance"
  | "technology-data"
  | "office-administration"
  | "healthcare"
  | "science-research"
  | "engineering"
  | "education"
  | "community-social-services"
  | "legal"
  | "management"
  | "sales"
  | "creative-media"
  | "protective-services"
  | "food-hospitality"
  | "personal-care-services"
  | "agriculture-environment"
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
    tagline: "Strategic advisory, fiduciary accounting, financial analysis, and investment planning.",
    description: "Occupations spanning accounting, financial analysis, investment management, actuarial modeling, and risk underwriting.",
    overviewIntro: "Business and financial careers face high cognitive exposure because algorithmic workflows excel at structured data processing, compliance auditing, and quantitative modeling. However, statutory fiduciary sign-off, regulatory accountability, and strategic advisory create meaningful human moats.",
    structuralDrivers: [
      {
        title: "High Quantitative & Analytical Exposure",
        description: "Frontier AI tools can rapidly draft reconciliation reports, parse financial statements, and execute complex financial modeling.",
      },
      {
        title: "Fiduciary & Statutory Accountability",
        description: "Legal liability, formal audit sign-offs, and statutory governance require licensed human professionals rather than unsupervised algorithms.",
      },
      {
        title: "Strategic Client Consulting",
        description: "High-stakes tax strategy, investment consulting, and client negotiations demand deep human trust and nuanced relationship management.",
      },
    ],
    faqItems: [
      {
        question: "Are business and finance jobs at high risk from AI?",
        answer: "Business and finance roles exhibit elevated AI Exposure scores in our dataset due to quantitative and documentation tasks. However, replacement risk varies widely: roles requiring fiduciary certification and client advisory retain strong human moats.",
      },
      {
        question: "Which finance careers have the lowest replacement risk?",
        answer: "Roles involving complex client relationships, crisis negotiation, and statutory accountability (such as senior financial advisors and restructuring specialists) exhibit substantially lower replacement risk than back-office processing roles.",
      },
      {
        question: "Is accounting still a good career choice in the AI era?",
        answer: "Accounting is evolving from manual ledger reconciliation to strategic advisory and audit assurance. Professionals who master analytical AI tools while developing forensic, ethical, and client advisory skills remain in high demand.",
      },
    ],
  },

  "technology-data": {
    slug: "technology-data",
    name: "Technology & Data",
    shortName: "Technology & Data",
    tagline: "Software engineering, data architecture, machine learning, and systems infrastructure.",
    description: "Careers in software development, cloud infrastructure, database engineering, artificial intelligence, and cybersecurity.",
    overviewIntro: "Technology and data professionals operate directly at the frontier of AI capabilities. While AI copilots accelerate routine coding and data querying, high-level system architecture, distributed reliability, and complex problem decomposition remain deeply anchored in human engineering expertise.",
    structuralDrivers: [
      {
        title: "High Task-Level Automation Feasibility",
        description: "Syntax generation, unit test boilerplate, SQL querying, and API integration are readily assisted by modern code-generation models.",
      },
      {
        title: "Architectural & Distributed Systems Complexity",
        description: "Synthesizing cross-service trade-offs, edge-case failure modes, and long-term maintainability requires holistic human systems judgment.",
      },
      {
        title: "Rapid Tooling & Productivity Evolution",
        description: "Engineers who master AI development tools experience dramatic output multipliers, shifting work from low-level syntax to high-level architecture.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace software developers and engineers?",
        answer: "In our verified dataset, developers face high AI Exposure due to code-generation tools, but Replacement Risk is moderate. The occupation is evolving from manual syntax writing toward systems architecture, security review, and product orchestration.",
      },
      {
        question: "What technology skills are most resilient to AI automation?",
        answer: "Distributed systems design, cloud reliability engineering, domain-specific business translation, cybersecurity forensics, and complex data pipeline governance exhibit the highest resilience.",
      },
      {
        question: "How should data professionals adapt to generative AI?",
        answer: "Focus on upstream problem formulation, causal inference, data quality verification, and translating complex algorithmic insights into executive business decisions.",
      },
    ],
  },

  "office-administration": {
    slug: "office-administration",
    name: "Office & Administrative Support",
    shortName: "Office & Administration",
    tagline: "Organizational coordination, clerical records, executive administration, and workflow support.",
    description: "Careers in office management, executive assistance, document processing, records management, and organizational scheduling.",
    overviewIntro: "Office and administrative support careers experience direct automation pressure because document synthesis, scheduling, and structured data handling are core strengths of modern AI tools. Roles requiring executive discretion, multi-stakeholder diplomacy, and physical office orchestration retain defensive moats.",
    structuralDrivers: [
      {
        title: "Standardized Digital Documentation",
        description: "Routine transcription, form filing, and calendar scheduling are directly addressable by automated software pipelines.",
      },
      {
        title: "Executive Discretion & Stakeholder Diplomacy",
        description: "Navigating sensitive personnel dynamics, confidentiality, and executive gatekeeping requires human emotional intelligence.",
      },
      {
        title: "Physical Facility & Event Coordination",
        description: "On-site resource logistics, vendor management, and physical office operations cannot be performed by pure software.",
      },
    ],
    faqItems: [
      {
        question: "Why do administrative roles show high AI risk scores?",
        answer: "Administrative roles often feature a high proportion of screen-based, standardized text and scheduling tasks, which overlap heavily with AI capability dimensions.",
      },
      {
        question: "How can administrative professionals protect their careers?",
        answer: "By expanding into executive operations, event management, project management, and becoming power users of AI automation software within their organizations.",
      },
      {
        question: "Will executive assistants be completely automated?",
        answer: "High-level executive assistants who manage confidential relationships, anticipate leadership needs, and handle high-stakes communications maintain durable human moats.",
      },
    ],
  },

  "healthcare": {
    slug: "healthcare",
    name: "Healthcare & Medical",
    shortName: "Healthcare",
    tagline: "Clinical diagnostics, surgical care, nursing, physical therapy, and patient support.",
    description: "Occupations spanning clinical medicine, nursing, surgery, emergency response, therapy, and specialized patient healthcare.",
    overviewIntro: "Healthcare occupations demonstrate exceptional structural resilience against AI replacement. While AI provides powerful diagnostic recommendations and image triage, direct physical patient intervention, life-safety responsibility, and bedside empathetic trust anchor healthcare firmly with human practitioners.",
    structuralDrivers: [
      {
        title: "Physical & Tactile Dexterity Moat",
        description: "Emergency procedures, surgical interventions, and physical bedside care require real-time physical manipulation in unpredictable environments.",
      },
      {
        title: "Direct Empathetic Connection & Trust",
        description: "Patients in physical or emotional distress require human presence, bedside empathy, and personalized moral reassurance.",
      },
      {
        title: "Life-Safety Legal & Ethical Liability",
        description: "Medical diagnoses and treatment administration carry severe statutory liability, requiring certified human medical licenses.",
      },
    ],
    faqItems: [
      {
        question: "Why is healthcare one of the safest career fields from AI?",
        answer: "Healthcare roles require physical bedside care, empathetic patient communication, and licensed statutory responsibility—barriers that software cannot replicate.",
      },
      {
        question: "How will AI impact doctors and nurses?",
        answer: "AI will act as a clinical copilot, accelerating medical imaging review, clinical note transcription, and drug discovery while leaving patient treatment and bedside care to human professionals.",
      },
      {
        question: "Which healthcare careers have the highest AI exposure?",
        answer: "Radiology interpretation, pathology review, and medical transcription show high technical exposure, but clinical sign-off requirements preserve human involvement.",
      },
    ],
  },

  "science-research": {
    slug: "science-research",
    name: "Science & Research",
    shortName: "Science & Research",
    tagline: "Physical sciences, biological research, laboratory experimentation, and social science inquiry.",
    description: "Careers in physics, chemistry, biology, environmental research, economics, psychology, and academic scientific inquiry.",
    overviewIntro: "Science and research careers exhibit high analytical exposure paired with strong methodological moats. AI accelerates literature reviews, statistical modeling, and experimental simulation, but novel hypothesis formulation, physical laboratory experimentation, and peer validation remain driven by human scientists.",
    structuralDrivers: [
      {
        title: "High Computational & Synthesis Exposure",
        description: "AI models excel at aggregating literature, discovering molecular patterns, and analyzing complex multivariate experimental datasets.",
      },
      {
        title: "Physical Laboratory Experimentation",
        description: "Synthesizing biological samples, handling specialized lab instruments, and troubleshooting physical assays require manual precision.",
      },
      {
        title: "Novel Theoretical Formulation",
        description: "Generating non-derivative scientific hypotheses, paradigm shifts, and causal research designs requires human intellectual creativity.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace research scientists?",
        answer: "No. AI is serving as a massive research accelerator, helping scientists model molecular structures and parse papers while humans direct experimental strategy and validate conclusions.",
      },
      {
        question: "How is AI changing laboratory research careers?",
        answer: "Repetitive data collection and literature summarization are being automated, allowing scientists to focus on experimental design, physical lab work, and theoretical analysis.",
      },
      {
        question: "Which scientific disciplines are most resilient?",
        answer: "Disciplines combining intensive wet-lab experimentation, field work, and novel theoretical development maintain the highest resilience.",
      },
    ],
  },

  "engineering": {
    slug: "engineering",
    name: "Engineering & Architecture",
    shortName: "Engineering",
    tagline: "Structural design, civil infrastructure, mechanical engineering, and physical spatial planning.",
    description: "Occupations spanning mechanical, civil, aerospace, and electrical engineering, alongside architectural design and construction surveying.",
    overviewIntro: "Engineering and architectural professions combine computational simulation with physical-world reality. While generative design and CAD tools automate drafting, life-safety certification, site topography inspections, and physical material validation ensure human engineers remain essential.",
    structuralDrivers: [
      {
        title: "Parametric & Computational Drafting Exposure",
        description: "Modern software can iterate structural calculations, CAD models, and architectural layouts with remarkable speed.",
      },
      {
        title: "Public Safety & Professional Licensure",
        description: "Building codes, bridge integrity, and aerospace certifications legally mandate sign-off by licensed Professional Engineers.",
      },
      {
        title: "Physical Site Topography & Material Reality",
        description: "Real-world environmental constraints, soil dynamics, and constructability audits require on-site human inspection and validation.",
      },
    ],
    faqItems: [
      {
        question: "Are engineering jobs safe from AI replacement?",
        answer: "Yes, engineering careers show low replacement risk due to public safety liability, physical site inspections, and mandatory Professional Engineer (PE) licensing seals.",
      },
      {
        question: "How is AI transforming architecture and drafting?",
        answer: "Generative tools accelerate early concept modeling and space optimization, shifting architects toward zoning negotiation, client advisory, and construction oversight.",
      },
      {
        question: "Which engineering disciplines have the strongest human moats?",
        answer: "Civil, structural, and aerospace engineering have exceptionally strong moats due to catastrophic failure liabilities and strict regulatory governance.",
      },
    ],
  },

  "education": {
    slug: "education",
    name: "Education & Training",
    shortName: "Education & Training",
    tagline: "Pedagogical instruction, academic curriculum development, teaching, and educational leadership.",
    description: "Careers in primary, secondary, higher education, special education, vocational instruction, and academic administration.",
    overviewIntro: "Education is deeply anchored in human pedagogy, emotional motivation, and classroom dynamics. While AI generates lesson plans, automated quizzes, and personalized practice exercises, the core educational mission of inspiring students and fostering critical thinking remains profoundly human.",
    structuralDrivers: [
      {
        title: "Curriculum & Lesson Planning Exposure",
        description: "Generative AI can instantly produce lesson frameworks, grading rubrics, reading comprehension passages, and practice problem sets.",
      },
      {
        title: "Interpersonal Motivation & Mentorship",
        description: "Inspiring disengaged students, managing diverse classroom behaviors, and building confidence require human empathy and connection.",
      },
      {
        title: "Adaptive Real-Time Pedagogy",
        description: "Skilled educators read non-verbal cues, adjust pacing in real time, and tailor complex explanations to individual student psychology.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace teachers and professors?",
        answer: "In our verified analysis, educators exhibit low replacement risk. AI assists with administrative grading and lesson drafting, but cannot replicate the human mentorship and social development essential to learning.",
      },
      {
        question: "How can teachers leverage AI productively?",
        answer: "By using AI to automate lesson drafting, create differentiated worksheets, and summarize administrative records, educators reclaim hours for direct student engagement.",
      },
      {
        question: "What education roles are most resilient?",
        answer: "Early childhood educators, special education specialists, and interactive classroom teachers maintain exceptionally high human resilience scores.",
      },
    ],
  },

  "community-social-services": {
    slug: "community-social-services",
    name: "Community & Social Services",
    shortName: "Community & Social Services",
    tagline: "Mental health counseling, family social work, community outreach, and rehabilitation support.",
    description: "Occupations spanning social work, marriage and family counseling, substance abuse rehabilitation, and community advocacy.",
    overviewIntro: "Community and social service careers represent some of the most resilient professions in our dataset. Counseling families in crisis, conducting home safety evaluations, and navigating trauma require profound interpersonal trust, cultural sensitivity, and ethical accountability.",
    structuralDrivers: [
      {
        title: "Deep Emotional Intelligence & Trauma Support",
        description: "Building therapeutic rapport with vulnerable individuals in distress requires genuine human empathy, presence, and active listening.",
      },
      {
        title: "Complex Family & Community Context",
        description: "Evaluating household safety, navigating foster care systems, and assessing non-verbal behavioral cues cannot be automated.",
      },
      {
        title: "Ethical & Legal Safeguarding",
        description: "Statutory child welfare, mental health holds, and rehabilitation certifications require accountable human professional judgment.",
      },
    ],
    faqItems: [
      {
        question: "Why are social work and counseling careers safe from AI?",
        answer: "These roles depend entirely on human trust, therapeutic rapport, and assessing complex family environments—qualities that digital algorithms cannot deliver.",
      },
      {
        question: "How will AI support mental health and social workers?",
        answer: "AI will help transcribe session case notes, organize community resource directories, and track client appointments, reducing administrative burden.",
      },
      {
        question: "Can AI provide therapy instead of human counselors?",
        answer: "While conversational apps offer basic wellness check-ins, clinical therapy for trauma, severe depression, and crisis intervention strictly requires licensed human practitioners.",
      },
    ],
  },

  "legal": {
    slug: "legal",
    name: "Legal",
    shortName: "Legal",
    tagline: "Statutory jurisprudence, litigation advocacy, judicial clerkship, and contract analysis.",
    description: "Occupations spanning attorneys, judges, judicial law clerks, paralegals, court reporters, and legal compliance analysts.",
    overviewIntro: "Legal careers experience high task exposure in document discovery, case law research, and contract drafting. However, courtroom litigation, statutory fiduciary duty, judicial authority, and strategic client advocacy maintain formidable human boundaries.",
    structuralDrivers: [
      {
        title: "Intensive Document Analysis & Research Exposure",
        description: "Large language models excel at indexing thousands of case filings, comparing contract clauses, and drafting initial briefs.",
      },
      {
        title: "Courtroom Advocacy & Oral Argument",
        description: "Persuading judges and juries, examining witnesses in real time, and navigating courtroom tactics require live human presence and rhetorical nuance.",
      },
      {
        title: "Fiduciary Duty & Bar Licensure",
        description: "Legal practice is strictly regulated by state bar associations, legally requiring authorized human attorneys to represent clients.",
      },
    ],
    faqItems: [
      {
        question: "Are lawyers and paralegals going to be replaced by AI?",
        answer: "Routine document indexing and clause comparison are highly exposed, but courtroom advocacy, judicial sentencing, and strategic settlement negotiation remain firmly human.",
      },
      {
        question: "How should legal professionals adapt to AI tools?",
        answer: "Master generative legal research copilots to produce briefs and diligence reports faster, while developing deeper client counseling, litigation, and trial advocacy skills.",
      },
      {
        question: "Which legal roles face the highest replacement risk?",
        answer: "Document discovery clerks and basic title searchers show elevated risk, whereas courtroom trial lawyers and judicial officers have low replacement risk.",
      },
    ],
  },

  "management": {
    slug: "management",
    name: "Management & Leadership",
    shortName: "Management",
    tagline: "Enterprise strategy, operational oversight, cross-functional leadership, and organizational direction.",
    description: "Careers in executive leadership, general operations management, departmental direction, and strategic planning.",
    overviewIntro: "Management careers balance analytical planning with human organizational leadership. While AI tools synthesize operational metrics and generate status summaries, aligning competing stakeholders, resolving internal crises, and bearing accountability for strategic decisions remain uniquely human.",
    structuralDrivers: [
      {
        title: "Operational Metric & Reporting Exposure",
        description: "AI copilots readily compile KPI dashboards, synthesize departmental status updates, and model operational scenarios.",
      },
      {
        title: "Stakeholder Alignment & Conflict Resolution",
        description: "Building team culture, mediating interpersonal conflicts, and negotiating resource allocation across departments require human leadership.",
      },
      {
        title: "Strategic Accountability & Crisis Navigation",
        description: "Making high-stakes capital allocation decisions under extreme ambiguity requires personal executive responsibility.",
      },
    ],
    faqItems: [
      {
        question: "Can artificial intelligence replace managers and executives?",
        answer: "AI provides analytical dashboards and operational insights, but executive decision-making, team motivation, culture, and ethical accountability require human leadership.",
      },
      {
        question: "How will the manager's role change in the AI era?",
        answer: "Managers will spend less time creating status decks and tracking spreadsheets, and more time coaching talent, orchestrating AI workflows, and driving strategy.",
      },
      {
        question: "What leadership skills are most resistant to AI?",
        answer: "Empathetic communication, strategic negotiation, ethical judgment, crisis management, and cross-functional coalition building.",
      },
    ],
  },

  "sales": {
    slug: "sales",
    name: "Sales & Marketing",
    shortName: "Sales & Marketing",
    tagline: "Client acquisition, consultative selling, commercial account management, and market growth.",
    description: "Occupations spanning enterprise sales, consultative account management, advertising strategy, and commercial client development.",
    overviewIntro: "Sales careers exhibit a sharp bifurcation. Automated systems handle transactional e-commerce and generic lead nurturing, but high-value enterprise sales, complex contract negotiations, and trusted client partnerships remain insulated by human social dynamics.",
    structuralDrivers: [
      {
        title: "Lead Generation & Outreach Automation",
        description: "Prospect indexing, email drafting, and sales funnel analytics are rapidly augmented by automated marketing software.",
      },
      {
        title: "Consultative Value Discovery",
        description: "Uncovering latent client pain points, navigating enterprise procurement politics, and building multi-year trust require human sales acumen.",
      },
      {
        title: "High-Stakes Contract Negotiation",
        description: "Closing multi-million dollar deals and managing executive relationships require live rapport, reading body language, and creative deal structuring.",
      },
    ],
    faqItems: [
      {
        question: "Will AI replace sales representatives?",
        answer: "Transactional order taking and cold email outreach are being automated, but consultative B2B selling and relationship-driven sales maintain strong human moats.",
      },
      {
        question: "How can sales professionals use AI to sell more?",
        answer: "By using AI to research prospects, generate meeting summaries, and draft proposals, reps can spend more time in direct customer conversations.",
      },
      {
        question: "What sales roles have the lowest replacement risk?",
        answer: "Enterprise account executives, commercial real estate brokers, and complex technical sales engineers show the highest career resilience.",
      },
    ],
  },

  "creative-media": {
    slug: "creative-media",
    name: "Creative, Arts & Media",
    shortName: "Creative & Media",
    tagline: "Visual design, investigative journalism, narrative writing, multimedia production, and artistic direction.",
    description: "Careers in graphic design, journalism, video editing, creative writing, photography, fine arts, and multimedia direction.",
    overviewIntro: "Creative and media industries face intensive task exposure from multimodal generative models. While basic asset generation and draft copywriting are commoditized, original investigative reporting, auteur artistic vision, and nuanced cultural storytelling remain deeply human.",
    structuralDrivers: [
      {
        title: "High Generative Media Exposure",
        description: "Generative image, audio, and text models can instantly produce derivative mockups, video cuts, and first-draft articles.",
      },
      {
        title: "Investigative Sourcing & Physical Presence",
        description: "Cultivating confidential human sources, conducting on-the-ground reporting, and capturing authentic live moments require human journalists.",
      },
      {
        title: "Cultural Relevance & Authentic Point of View",
        description: "Audiences seek genuine human perspective, lived experience, and cultural resonance that purely algorithmic content lacks.",
      },
    ],
    faqItems: [
      {
        question: "Are creative and writing careers safe from AI?",
        answer: "Generative AI heavily impacts entry-level drafting and derivative asset creation. Creative professionals who evolve into art directors, investigative reporters, and narrative strategists maintain strong value.",
      },
      {
        question: "How should designers and artists adapt to generative AI?",
        answer: "Integrate generative tools into early ideation and rapid concept pitching, while focusing on brand identity, physical craft, and holistic creative direction.",
      },
      {
        question: "Which creative roles have the highest AI resilience?",
        answer: "Investigative journalists, creative directors, live broadcast camera operators, and physical fine artists maintain the highest resilience in our dataset.",
      },
    ],
  },

  "protective-services": {
    slug: "protective-services",
    name: "Protective & Security Services",
    shortName: "Protective Services",
    tagline: "Public emergency response, law enforcement, fire protection, and critical asset security.",
    description: "Careers in policing, firefighting, criminal investigation, emergency dispatch, corrections, and physical security.",
    overviewIntro: "Protective and security services are anchored in physical response, tactical crisis de-escalation, and public safety enforcement. While AI enhances surveillance analysis and emergency dispatch routing, on-scene physical interventions and law enforcement authority strictly require human officers.",
    structuralDrivers: [
      {
        title: "Physical Emergency Response & Tactics",
        description: "Entering burning buildings, apprehending suspects, and securing crime scenes require rapid physical action in unpredictable environments.",
      },
      {
        title: "Crisis De-escalation & Legal Authority",
        description: "Defusing hostile confrontations and exercising statutory arrest powers require human emotional control and legal accountability.",
      },
      {
        title: "Investigative Forensics & Testimony",
        description: "Collecting on-site physical evidence, interviewing witnesses, and providing courtroom testimony require human forensic judgment.",
      },
    ],
    faqItems: [
      {
        question: "Why do protective service jobs have low AI risk scores?",
        answer: "These roles require physical presence in hazardous, chaotic environments, tactical decision-making under stress, and legal enforcement authority.",
      },
      {
        question: "How is AI used in policing and firefighting?",
        answer: "AI assists with predictive resource dispatching, automated license plate recognition, thermal imaging analysis, and administrative incident reporting.",
      },
      {
        question: "Can security robots replace human security guards?",
        answer: "Robots assist with perimeter scanning and surveillance, but investigating anomalies, physically detaining intruders, and handling complex human situations require human guards.",
      },
    ],
  },

  "food-hospitality": {
    slug: "food-hospitality",
    name: "Food & Hospitality",
    shortName: "Food & Hospitality",
    tagline: "Culinary arts, restaurant operations, guest hospitality, and food preparation.",
    description: "Occupations spanning executive chefs, line cooks, restaurant managers, food servers, and culinary artisans.",
    overviewIntro: "Food and hospitality careers blend manual dexterity, culinary artistry, and warm human hospitality. While automated kiosks handle basic ordering, culinary preparation in dynamic kitchen environments and hospitable guest service remain firmly human.",
    structuralDrivers: [
      {
        title: "Sensory Taste & Artisanal Craftsmanship",
        description: "Flavor balancing, recipe innovation, visual plating, and sensory quality control require human palate and culinary mastery.",
      },
      {
        title: "Fast-Paced Kitchen Physical Dexterity",
        description: "Operating hot grills, sauté pans, knives, and managing simultaneous dish timings in tight physical kitchens resist automated robotics.",
      },
      {
        title: "Hospitality & Guest Experience",
        description: "Warm interpersonal service, beverage recommendations, and managing dining ambiance define the emotional value of hospitality.",
      },
    ],
    faqItems: [
      {
        question: "Will robots replace chefs and restaurant cooks?",
        answer: "Fast-food fryers and standardized burger assembly may automate, but dynamic scratch cooking, flavor tasting, and creative menu design require human chefs.",
      },
      {
        question: "How is technology changing restaurant jobs?",
        answer: "Digital ordering kiosks and automated inventory systems streamline front-of-house logistics, allowing staff to focus on food quality and hospitality.",
      },
      {
        question: "What hospitality roles are most resilient?",
        answer: "Executive chefs, fine-dining servers, sommeliers, and boutique hospitality managers maintain high resilience due to the human experience they provide.",
      },
    ],
  },

  "personal-care-services": {
    slug: "personal-care-services",
    name: "Personal Care & Services",
    shortName: "Personal Care",
    tagline: "Personal grooming, wellness therapy, recreation assistance, and personal care support.",
    description: "Occupations spanning hairstylists, barbers, cosmetologists, skincare specialists, fitness instructors, and personal attendants.",
    overviewIntro: "Personal care careers are insulated by direct tactile physical manipulation and personal rapport. Styling hair, performing skincare treatments, and guiding fitness clients require fine motor control on unique human bodies and individualized interpersonal connection.",
    structuralDrivers: [
      {
        title: "Fine Tactile Manipulation on Human Bodies",
        description: "Cutting hair, applying treatments, and performing body therapies require delicate, responsive physical touch that robotics cannot replicate.",
      },
      {
        title: "Personal Connection & Emotional Well-Being",
        description: "Clients value the trusted personal conversation, relaxation, and self-esteem boost provided by human personal care professionals.",
      },
      {
        title: "Custom Aesthetic & Style Judgment",
        description: "Assessing face shapes, skin tones, and personal preferences to create tailored styling requires intuitive aesthetic judgment.",
      },
    ],
    faqItems: [
      {
        question: "Why are barbers and hairstylists safe from AI?",
        answer: "Grooming requires delicate physical shears and blade work on moving human heads in a personalized setting—capabilities far beyond software.",
      },
      {
        question: "How will fitness and personal wellness professionals use AI?",
        answer: "AI apps will generate workout templates and diet tracking, while human trainers provide accountability, motivation, and physical form correction.",
      },
      {
        question: "What makes personal care services resilient?",
        answer: "Direct physical contact, empathetic conversation, and customized aesthetic judgment create an enduring moat against digital automation.",
      },
    ],
  },

  "agriculture-environment": {
    slug: "agriculture-environment",
    name: "Agriculture & Natural Resources",
    shortName: "Agriculture",
    tagline: "Agricultural cultivation, animal husbandry, forestry management, and environmental stewardship.",
    description: "Careers in farming operations, agricultural inspection, animal breeding, forestry, wildlife conservation, and soil management.",
    overviewIntro: "Agriculture and natural resource occupations operate across unconstrained outdoor ecosystems. While precision sensors and GPS guidance assist crop monitoring, managing living biological systems, unpredictable weather, and heavy field machinery requires resilient human stewardship.",
    structuralDrivers: [
      {
        title: "Dynamic Outdoor Environmental Conditions",
        description: "Navigating muddy terrain, changing weather, dense forest canopies, and varied field topography presents high physical barriers to complete automation.",
      },
      {
        title: "Biological System Oversight & Animal Care",
        description: "Assessing animal health, diagnosing crop diseases, and managing soil health require holistic biological intuition and experience.",
      },
      {
        title: "Heavy Equipment Operation & Field Maintenance",
        description: "Operating and field-repairing combines, tractors, chainsaws, and irrigation infrastructure require versatile mechanical problem-solving.",
      },
    ],
    faqItems: [
      {
        question: "How is AI impacting farming and agriculture careers?",
        answer: "AI powers satellite crop monitoring, automated weed spraying, and yield forecasting, helping agricultural workers optimize productivity without replacing hands-on farm management.",
      },
      {
        question: "Are forestry and conservation careers safe from AI?",
        answer: "Yes. Foresters, wildlife managers, and environmental conservationists work in rugged outdoor terrain that software cannot access.",
      },
      {
        question: "What agricultural roles have the lowest replacement risk?",
        answer: "Agricultural equipment mechanics, livestock managers, and forestry inspectors maintain strong physical and ecological moats.",
      },
    ],
  },

  "skilled-trades": {
    slug: "skilled-trades",
    name: "Skilled Trades & Construction",
    shortName: "Skilled Trades",
    tagline: "Electrical systems, plumbing, structural carpentry, mechanical repair, and physical fabrication.",
    description: "Occupations spanning electricians, plumbers, HVAC technicians, carpenters, mechanics, and specialized construction craftsmen.",
    overviewIntro: "Skilled trades and construction occupations represent the premier physical strongholds of the economy. Troubleshooting complex mechanical systems in tight crawlspaces, rewiring century-old buildings, and performing tactile repairs cannot be automated by software.",
    structuralDrivers: [
      {
        title: "Unstructured Physical Workspaces",
        description: "Navigating attics, trenches, scaffolding, and custom renovations requires human physical agility and spatial navigation.",
      },
      {
        title: "Tactile Problem Solving & Diagnostics",
        description: "Feeling mechanical vibration, hearing engine anomalies, and manually fitting physical components require real-world sensory mastery.",
      },
      {
        title: "Safety Code Compliance & Trade Licensing",
        description: "National electrical and plumbing codes legally mandate licensed master tradespeople to pull permits and sign off on installations.",
      },
    ],
    faqItems: [
      {
        question: "Why are skilled trades considered the most AI-proof careers?",
        answer: "Trades require physical dexterity, spatial reasoning in unconstrained environments, and trade licensing that software cannot replicate.",
      },
      {
        question: "How will electricians and plumbers use AI?",
        answer: "AI will assist with diagnostic lookup, electrical load calculations, and administrative invoicing, while hands-on tool work remains fully human.",
      },
      {
        question: "Which trades have the highest long-term security?",
        answer: "Electricians, commercial HVAC technicians, service plumbers, and industrial machinery mechanics maintain elite human resilience ratings.",
      },
    ],
  },

  "transportation": {
    slug: "transportation",
    name: "Transportation & Logistics",
    shortName: "Transportation",
    tagline: "Aviation flight operations, commercial freight, maritime navigation, and supply chain dispatch.",
    description: "Careers in airline flight operations, commercial trucking, maritime navigation, rail transit, air traffic control, and freight logistics.",
    overviewIntro: "Transportation careers operate at the intersection of automation software and real-world physical transit. While routing algorithms optimize flight plans and freight corridors, managing emergency weather anomalies, life-safety liabilities, and physical vehicle operations keep human operators central.",
    structuralDrivers: [
      {
        title: "High Optimization & Route Exposure",
        description: "Automated routing engines, fuel optimization algorithms, and dispatch software handle routine logistics calculations.",
      },
      {
        title: "Critical Life-Safety Liability",
        description: "Commercial aviation and passenger rail carry absolute life-safety accountability, legally requiring certified human pilots and operators.",
      },
      {
        title: "Dynamic Weather & Emergency Navigation",
        description: "Managing severe turbulence, maritime storms, mechanical failures, and unexpected obstacles requires human operational judgment under pressure.",
      },
    ],
    faqItems: [
      {
        question: "Will autonomous vehicles replace commercial pilots and drivers?",
        answer: "While freight tracking is automated, passenger aviation and heavy equipment transport retain certified human pilots and operators for safety and liability.",
      },
      {
        question: "How is AI changing the role of air traffic controllers?",
        answer: "AI assists with trajectory prediction and conflict detection, but ultimate airspace separation and emergency decisions remain human responsibilities.",
      },
      {
        question: "Which transportation careers have the highest resilience?",
        answer: "Airline pilots, ship captains, air traffic controllers, and specialized cargo supervisors show exceptional career resilience.",
      },
    ],
  },

  "production": {
    slug: "production",
    name: "Manufacturing & Production",
    shortName: "Manufacturing",
    tagline: "Industrial fabrication, precision machining, assembly operations, and chemical processing.",
    description: "Occupations spanning CNC machinists, industrial welders, chemical plant operators, tool and die makers, and quality control technicians.",
    overviewIntro: "Manufacturing and industrial production combine computerized automation with high-precision physical craftsmanship. While routine repetitive assembly is mechanized, custom precision machining, plant system troubleshooting, and physical quality assurance rely on human industrial expertise.",
    structuralDrivers: [
      {
        title: "Industrial Automation & Robotics Integration",
        description: "Repetitive assembly, automated welding arms, and robotic material handling handle structured high-volume workflows.",
      },
      {
        title: "Custom Tooling & Precision Machining",
        description: "Setting up complex 5-axis CNC machines, adjusting tool offsets, and fabricating prototype parts require specialized human machinists.",
      },
      {
        title: "Physical Plant Diagnostics & Quality Assurance",
        description: "Troubleshooting industrial line breakdowns, monitoring chemical processes, and inspecting aerospace tolerances require on-site technical inspection.",
      },
    ],
    faqItems: [
      {
        question: "Is manufacturing at high risk from AI and robotics?",
        answer: "Standardized assembly lines face high mechanization, but custom fabrication, CNC programming, plant maintenance, and quality inspection require skilled human technicians.",
      },
      {
        question: "How are machinists and plant technicians using AI?",
        answer: "AI optimizes toolpath generation and predicts machine maintenance needs, while human technicians set up fixtures and verify physical tolerances.",
      },
      {
        question: "What manufacturing roles offer the greatest career security?",
        answer: "Tool and die makers, specialized CNC machinists, industrial machinery repairers, and chemical plant operators maintain strong career moats.",
      },
    ],
  },
};

/**
 * Deterministic mapping from 22 source category slugs to 19 canonical consumer fields.
 */
const SOURCE_CATEGORY_TO_FIELD: Record<string, CareerFieldSlug> = {
  // Business & Finance
  "business-finance": "business-finance",

  // Technology & Data
  "technology-data": "technology-data",
  "computer-mathematical": "technology-data",

  // Office & Administration
  "office-administration": "office-administration",

  // Healthcare
  "healthcare": "healthcare",
  "healthcare-practitioners-technical": "healthcare",
  "healthcare-support": "healthcare",

  // Science & Research
  "science-research": "science-research",
  "life-physical-social-science": "science-research",

  // Engineering & Architecture
  "engineering-architecture": "engineering",
  "architecture-engineering": "engineering",

  // Education & Training
  "education": "education",
  "education-training": "education",
  "education-training-library": "education",

  // Community & Social Services
  "community-social-services": "community-social-services",
  "community-social-service": "community-social-services",

  // Legal
  "legal": "legal",

  // Management & Leadership
  "management-leadership": "management",
  "management": "management",

  // Sales & Marketing
  "sales": "sales",
  "sales-marketing": "sales",
  "sales-and-related": "sales",

  // Creative, Arts & Media
  "creative-media": "creative-media",
  "arts-design-entertainment-sports-media": "creative-media",

  // Protective Services
  "protective-services": "protective-services",
  "protective-service": "protective-services",

  // Food & Hospitality
  "food-hospitality": "food-hospitality",
  "food-preparation-serving-related": "food-hospitality",

  // Personal Care & Services
  "personal-care-service": "personal-care-services",
  "personal-care-services": "personal-care-services",

  // Agriculture & Natural Resources
  "agriculture-environment": "agriculture-environment",
  "farming-fishing-forestry": "agriculture-environment",

  // Skilled Trades & Construction
  "skilled-trades": "skilled-trades",
  "construction-extraction": "skilled-trades",
  "installation-repair": "skilled-trades",
  "installation-maintenance-repair": "skilled-trades",
  "facilities-grounds": "skilled-trades",
  "building-grounds-cleaning-maintenance": "skilled-trades",

  // Transportation & Logistics
  "transport-logistics": "transportation",
  "transportation": "transportation",
  "transportation-material-moving": "transportation",

  // Manufacturing & Production
  "manufacturing-production": "production",
  "production": "production",
};

/**
 * Specific domain leadership / specialized cross-functional role overrides.
 */
const OCCUPATION_SLUG_OVERRIDES: Record<string, CareerFieldSlug> = {
  "sales-managers": "sales",
  "medical-and-health-services-managers": "healthcare",
  "architectural-and-engineering-managers": "engineering",
  "financial-managers": "business-finance",
  "computer-and-information-systems-managers": "technology-data",
  "education-administrators-kindergarten-through-secondary": "education",
  "education-administrators-postsecondary": "education",
  "education-administrators-all-other": "education",
  "project-management-specialists": "business-finance",
  "digital-interface-designers": "creative-media",
  "technical-writers": "creative-media",
};

/**
 * Resolve the canonical field slug for an occupation.
 */
export function getCanonicalFieldSlug(occupationSlug?: string, categorySlugOrName?: string): CareerFieldSlug {
  if (occupationSlug && OCCUPATION_SLUG_OVERRIDES[occupationSlug]) {
    return OCCUPATION_SLUG_OVERRIDES[occupationSlug];
  }

  if (categorySlugOrName) {
    const norm = categorySlugOrName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    if (SOURCE_CATEGORY_TO_FIELD[norm]) {
      return SOURCE_CATEGORY_TO_FIELD[norm];
    }
  }

  return "business-finance";
}

/**
 * Retrieve metadata definition for a canonical field.
 */
export function getCanonicalField(slug: string): CareerFieldDefinition | null {
  return (CANONICAL_CAREER_FIELDS as Record<string, CareerFieldDefinition>)[slug] ?? null;
}

export interface FieldAggregateAnalytics {
  verifiedCount: number;
  medianAiExposure: number;
  medianReplacementRisk: number;
  highestAiExposure: { slug: string; title: string; score: number };
  lowestAiExposure: { slug: string; title: string; score: number };
  highestReplacementRisk: { slug: string; title: string; score: number };
  lowestReplacementRisk: { slug: string; title: string; score: number };
  largestGapLeader: { slug: string; title: string; exposure: number; risk: number; gap: number };
  riskDistribution: {
    low: number; // 0-33
    moderate: number; // 34-66
    high: number; // 67-100
  };
}

/**
 * Compute verified-only aggregate analytics for a canonical field.
 */
export function calculateFieldAnalytics(
  fieldSlug: CareerFieldSlug,
  occupations: (Occupation | RankingOccupation)[]
): {
  field: CareerFieldDefinition;
  analytics: FieldAggregateAnalytics;
  occupations: RankingOccupation[];
} {
  const field = CANONICAL_CAREER_FIELDS[fieldSlug] || CANONICAL_CAREER_FIELDS["business-finance"];

  const fieldOccupations = occupations
    .filter((job) => {
      const matchSlug = getCanonicalFieldSlug(job.slug, job.category);
      return matchSlug === fieldSlug;
    })
    .map((j) => ({
      slug: j.slug,
      title: j.title,
      category: j.category,
      aiExposure: j.aiExposure,
      replacementRisk: j.replacementRisk,
    }));

  if (fieldOccupations.length === 0) {
    return {
      field,
      analytics: {
        verifiedCount: 0,
        medianAiExposure: 0,
        medianReplacementRisk: 0,
        highestAiExposure: { slug: "", title: "N/A", score: 0 },
        lowestAiExposure: { slug: "", title: "N/A", score: 0 },
        highestReplacementRisk: { slug: "", title: "N/A", score: 0 },
        lowestReplacementRisk: { slug: "", title: "N/A", score: 0 },
        largestGapLeader: { slug: "", title: "N/A", exposure: 0, risk: 0, gap: 0 },
        riskDistribution: { low: 0, moderate: 0, high: 0 },
      },
      occupations: [],
    };
  }

  const sortedByExposure = [...fieldOccupations].sort((a, b) => a.aiExposure - b.aiExposure);
  const sortedByRisk = [...fieldOccupations].sort((a, b) => a.replacementRisk - b.replacementRisk);

  const mid = Math.floor(fieldOccupations.length / 2);
  const medianAiExposure =
    fieldOccupations.length % 2 !== 0
      ? sortedByExposure[mid].aiExposure
      : (sortedByExposure[mid - 1].aiExposure + sortedByExposure[mid].aiExposure) / 2;

  const medianReplacementRisk =
    fieldOccupations.length % 2 !== 0
      ? sortedByRisk[mid].replacementRisk
      : (sortedByRisk[mid - 1].replacementRisk + sortedByRisk[mid].replacementRisk) / 2;

  let largestGap = { slug: "", title: "", exposure: 0, risk: 0, gap: -999 };
  let lowCount = 0;
  let modCount = 0;
  let highCount = 0;

  for (const job of fieldOccupations) {
    const gap = job.aiExposure - job.replacementRisk;
    if (gap > largestGap.gap) {
      largestGap = {
        slug: job.slug,
        title: job.title,
        exposure: job.aiExposure,
        risk: job.replacementRisk,
        gap,
      };
    }

    if (job.replacementRisk >= 67) highCount++;
    else if (job.replacementRisk >= 34) modCount++;
    else lowCount++;
  }

  return {
    field,
    analytics: {
      verifiedCount: fieldOccupations.length,
      medianAiExposure: Math.round(medianAiExposure),
      medianReplacementRisk: Math.round(medianReplacementRisk),
      highestAiExposure: {
        slug: sortedByExposure[sortedByExposure.length - 1].slug,
        title: sortedByExposure[sortedByExposure.length - 1].title,
        score: Math.round(sortedByExposure[sortedByExposure.length - 1].aiExposure),
      },
      lowestAiExposure: {
        slug: sortedByExposure[0].slug,
        title: sortedByExposure[0].title,
        score: Math.round(sortedByExposure[0].aiExposure),
      },
      highestReplacementRisk: {
        slug: sortedByRisk[sortedByRisk.length - 1].slug,
        title: sortedByRisk[sortedByRisk.length - 1].title,
        score: Math.round(sortedByRisk[sortedByRisk.length - 1].replacementRisk),
      },
      lowestReplacementRisk: {
        slug: sortedByRisk[0].slug,
        title: sortedByRisk[0].title,
        score: Math.round(sortedByRisk[0].replacementRisk),
      },
      largestGapLeader: largestGap,
      riskDistribution: {
        low: lowCount,
        moderate: modCount,
        high: highCount,
      },
    },
    occupations: fieldOccupations,
  };
}
