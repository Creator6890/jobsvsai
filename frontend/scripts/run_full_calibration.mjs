const CATEGORY_ARCHETYPES = {
  "Technology & Data": { analytical: 90, creativity: 60, communication: 45, people: 30, practical: 15, organization: 75, technology: 95, leadership: 50 },
  "Science & Research": { analytical: 95, creativity: 65, communication: 65, people: 35, practical: 45, organization: 80, technology: 75, leadership: 50 },
  "Engineering & Architecture": { analytical: 90, creativity: 75, communication: 55, people: 35, practical: 60, organization: 80, technology: 85, leadership: 55 },
  "Healthcare": { analytical: 85, creativity: 35, communication: 75, people: 92, practical: 65, organization: 85, technology: 60, leadership: 65 },
  "Healthcare Support": { analytical: 45, creativity: 30, communication: 65, people: 90, practical: 75, organization: 70, technology: 35, leadership: 35 },
  "Business & Finance": { analytical: 88, creativity: 45, communication: 75, people: 60, practical: 15, organization: 90, technology: 70, leadership: 70 },
  "Management & Leadership": { analytical: 75, creativity: 60, communication: 90, people: 85, practical: 20, organization: 85, technology: 55, leadership: 95 },
  "Creative & Media": { analytical: 40, creativity: 95, communication: 85, people: 55, practical: 40, organization: 45, technology: 65, leadership: 50 },
  "Education & Training": { analytical: 70, creativity: 65, communication: 90, people: 92, practical: 25, organization: 75, technology: 50, leadership: 70 },
  "Community & Social Services": { analytical: 55, creativity: 45, communication: 85, people: 95, practical: 20, organization: 65, technology: 35, leadership: 60 },
  "Legal": { analytical: 92, creativity: 55, communication: 95, people: 70, practical: 15, organization: 90, technology: 50, leadership: 80 },
  "Sales": { analytical: 55, creativity: 55, communication: 90, people: 85, practical: 20, organization: 65, technology: 50, leadership: 75 },
  "Office & Administration": { analytical: 50, creativity: 30, communication: 65, people: 60, practical: 25, organization: 90, technology: 60, leadership: 40 },
  "Protective Services": { analytical: 60, creativity: 30, communication: 70, people: 75, practical: 80, organization: 75, technology: 50, leadership: 75 },
  "Construction & Extraction": { analytical: 45, creativity: 35, communication: 35, people: 30, practical: 95, organization: 60, technology: 40, leadership: 45 },
  "Installation & Repair": { analytical: 70, creativity: 35, communication: 40, people: 35, practical: 95, organization: 70, technology: 70, leadership: 45 },
  "Manufacturing & Production": { analytical: 50, creativity: 30, communication: 35, people: 30, practical: 90, organization: 75, technology: 55, leadership: 40 },
  "Transport & Logistics": { analytical: 40, creativity: 20, communication: 40, people: 35, practical: 85, organization: 70, technology: 45, leadership: 35 },
  "Food & Hospitality": { analytical: 30, creativity: 55, communication: 65, people: 80, practical: 85, organization: 65, technology: 25, leadership: 40 },
  "Personal Care & Service": { analytical: 35, creativity: 60, communication: 75, people: 90, practical: 70, organization: 60, technology: 30, leadership: 45 },
  "Agriculture & Environment": { analytical: 55, creativity: 35, communication: 35, people: 30, practical: 95, organization: 60, technology: 45, leadership: 45 },
  "Facilities & Grounds": { analytical: 25, creativity: 20, communication: 30, people: 35, practical: 90, organization: 55, technology: 25, leadership: 30 },
};

const DEFAULT_ARCHETYPE = {
  analytical: 60, creativity: 50, communication: 60, people: 60,
  practical: 50, organization: 65, technology: 55, leadership: 55,
};

const DIMENSION_KEYS = [
  "analytical", "creativity", "communication", "people",
  "practical", "organization", "technology", "leadership",
];

const ASSESSMENT_QUESTIONS = [
  { id: 1, prompt: "Complex problems into smaller parts", primaryDimension: "analytical", primaryWeight: 1.0 },
  { id: 2, prompt: "Original design rather than template", primaryDimension: "creativity", primaryWeight: 1.0 },
  { id: 3, prompt: "Helping, supporting, or counseling", primaryDimension: "people", primaryWeight: 1.0 },
  { id: 4, prompt: "Hands-on tools or equipment", primaryDimension: "practical", primaryWeight: 1.0 },
  { id: 5, prompt: "Software, coding, or digital systems", primaryDimension: "technology", primaryWeight: 1.0, secondaryDimension: "analytical", secondaryWeight: 0.3 },
  { id: 6, prompt: "Explaining technical concepts in simple terms", primaryDimension: "communication", primaryWeight: 1.0 },
  { id: 7, prompt: "Workflows, schedules, accuracy", primaryDimension: "organization", primaryWeight: 1.0 },
  { id: 8, prompt: "Decisions under uncertainty", primaryDimension: "leadership", primaryWeight: 1.0 },
  { id: 9, prompt: "Empirical patterns and data trends", primaryDimension: "analytical", primaryWeight: 1.0 },
  { id: 10, prompt: "Reimagining products or narratives", primaryDimension: "creativity", primaryWeight: 1.0 },
  { id: 11, prompt: "Attentive to emotions and motivations", primaryDimension: "people", primaryWeight: 1.0, secondaryDimension: "communication", secondaryWeight: 0.3 },
  { id: 12, prompt: "Assemble, repair, or inspect physical objects", primaryDimension: "practical", primaryWeight: 1.0 },
  { id: 13, prompt: "Digital architectures and automated workflows", primaryDimension: "technology", primaryWeight: 1.0 },
  { id: 14, prompt: "Writing structured reports or articles", primaryDimension: "communication", primaryWeight: 1.0 },
  { id: 15, prompt: "Spotting errors and structured records", primaryDimension: "organization", primaryWeight: 1.0 },
  { id: 16, prompt: "Step forward to coordinate people", primaryDimension: "leadership", primaryWeight: 1.0 },
  { id: 17, prompt: "Investigate why a machine is failing", primaryDimension: "analytical", primaryWeight: 1.0, secondaryDimension: "practical", secondaryWeight: 0.4 },
  { id: 18, prompt: "Open-ended problems with multiple pathways", primaryDimension: "creativity", primaryWeight: 1.0, secondaryDimension: "analytical", secondaryWeight: 0.3 },
  { id: 19, prompt: "Building personal trust and collaboration", primaryDimension: "people", primaryWeight: 1.0, secondaryDimension: "leadership", secondaryWeight: 0.3 },
  { id: 20, prompt: "Managing timelines and budgets", primaryDimension: "organization", primaryWeight: 1.0, secondaryDimension: "leadership", secondaryWeight: 0.4 },
];

function calculateProfile(answers) {
  const dimensionWeightedSums = {
    analytical: 0, creativity: 0, communication: 0, people: 0,
    practical: 0, organization: 0, technology: 0, leadership: 0,
  };
  const dimensionTotalWeights = {
    analytical: 0, creativity: 0, communication: 0, people: 0,
    practical: 0, organization: 0, technology: 0, leadership: 0,
  };

  for (const question of ASSESSMENT_QUESTIONS) {
    const rawAnswer = answers[question.id] ?? 3;
    const clampedAnswer = Math.max(1, Math.min(5, rawAnswer));
    const normalizedResponse = (clampedAnswer - 1) / 4.0;

    dimensionWeightedSums[question.primaryDimension] += normalizedResponse * question.primaryWeight;
    dimensionTotalWeights[question.primaryDimension] += question.primaryWeight;

    if (question.secondaryDimension && question.secondaryWeight) {
      dimensionWeightedSums[question.secondaryDimension] += normalizedResponse * question.secondaryWeight;
      dimensionTotalWeights[question.secondaryDimension] += question.secondaryWeight;
    }
  }

  const dimensionScores = {};
  for (const key of DIMENSION_KEYS) {
    const totalWeight = dimensionTotalWeights[key] || 1.0;
    const score = Math.round((dimensionWeightedSums[key] / totalWeight) * 100);
    dimensionScores[key] = Math.max(0, Math.min(100, score));
  }

  const sortedDimensions = [...DIMENSION_KEYS].sort((a, b) => dimensionScores[b] - dimensionScores[a]);
  const topStrengths = sortedDimensions.slice(0, 3);
  return { dimensionScores, topStrengths };
}

function deriveOccupationVector(occupation) {
  const cat = occupation.category || "";
  const baseline = CATEGORY_ARCHETYPES[cat] || DEFAULT_ARCHETYPE;
  const vector = { ...baseline };

  if (typeof occupation.physicalDependency === "number") {
    vector.practical = Math.round(baseline.practical * 0.35 + occupation.physicalDependency * 0.65);
  }
  if (typeof occupation.humanDependency === "number") {
    vector.people = Math.round(baseline.people * 0.40 + occupation.humanDependency * 0.60);
    vector.communication = Math.round(baseline.communication * 0.50 + occupation.humanDependency * 0.50);
  }

  const titleLower = (occupation.title || "").toLowerCase();
  if (titleLower.includes("data") || titleLower.includes("statistician") || titleLower.includes("analyst") || titleLower.includes("scientist") || titleLower.includes("economist")) {
    vector.analytical = Math.min(100, vector.analytical + 10);
    vector.technology = Math.min(100, vector.technology + 8);
  }
  if (titleLower.includes("designer") || titleLower.includes("writer") || titleLower.includes("artist") || titleLower.includes("architect")) {
    vector.creativity = Math.min(100, vector.creativity + 15);
  }
  if (titleLower.includes("manager") || titleLower.includes("director") || titleLower.includes("executive") || titleLower.includes("chief") || titleLower.includes("supervisor")) {
    vector.leadership = Math.min(100, vector.leadership + 15);
    vector.organization = Math.min(100, vector.organization + 8);
  }
  if (titleLower.includes("nurse") || titleLower.includes("therapist") || titleLower.includes("counselor") || titleLower.includes("social worker")) {
    vector.people = Math.min(100, vector.people + 12);
  }
  if (titleLower.includes("developer") || titleLower.includes("programmer") || titleLower.includes("engineer") || titleLower.includes("cybersecurity") || titleLower.includes("software")) {
    vector.technology = Math.min(100, vector.technology + 12);
    vector.analytical = Math.min(100, vector.analytical + 8);
  }

  for (const k of DIMENSION_KEYS) {
    vector[k] = Math.max(0, Math.min(100, vector[k]));
  }
  return vector;
}

function matchOccupations(userProfile, occupations, limit = 15) {
  const matches = [];

  for (const occ of occupations) {
    const occVector = deriveOccupationVector(occ);
    let totalWeight = 0;
    let weightedSquaredDiff = 0;

    for (const key of DIMENSION_KEYS) {
      const u = userProfile.dimensionScores[key];
      const o = occVector[key];

      let w = 1.0;
      if (u >= 80) w = 2.5;
      else if (u >= 60) w = 1.8;
      else if (u <= 20) w = 1.4;

      totalWeight += w;
      weightedSquaredDiff += w * Math.pow(u - o, 2);
    }

    const rms = Math.sqrt(weightedSquaredDiff / totalWeight);
    const fitPct = Math.round(98 - Math.pow(rms / 4.2, 1.45));
    const careerFit = Math.max(12, Math.min(98, fitPct));

    const keyStrengths = [...DIMENSION_KEYS]
      .filter((k) => userProfile.dimensionScores[k] >= 55 && occVector[k] >= 55)
      .sort((a, b) => (userProfile.dimensionScores[b] + occVector[b]) - (userProfile.dimensionScores[a] + occVector[a]))
      .slice(0, 3);

    const weakDimensions = [...DIMENSION_KEYS]
      .sort((a, b) => Math.abs(userProfile.dimensionScores[b] - occVector[b]) - Math.abs(userProfile.dimensionScores[a] - occVector[a]))
      .slice(0, 2);

    matches.push({
      occupation: occ,
      careerFit,
      keyStrengths,
      weakDimensions,
      occVector,
    });
  }

  matches.sort((a, b) => b.careerFit - a.careerFit);
  return matches.slice(0, limit);
}

async function main() {
  console.log("Loading all 507 published occupations from local API...");
  const r1 = await fetch("http://localhost:8000/api/v1/occupations?limit=500").then((r) => r.json());
  const r2 = await fetch("http://localhost:8000/api/v1/occupations?limit=500&offset=500").then((r) => r.json());
  const occupations = [...r1, ...r2];
  console.log(`Loaded ${occupations.length} occupations.\n`);

  // 8 Target Personas
  const personas = [
    {
      id: "A",
      name: "Analytical + Technology",
      description: "Software, data, engineering, technical analysis",
      answers: { 1: 5, 5: 5, 9: 5, 13: 5, 17: 5, 2: 2, 3: 1, 4: 1, 6: 3, 7: 4, 8: 3, 10: 2, 11: 1, 12: 1, 14: 2, 15: 4, 16: 2, 18: 3, 19: 1, 20: 3 },
    },
    {
      id: "B",
      name: "Creativity + Communication",
      description: "Design, writing, media, creative communication",
      answers: { 2: 5, 6: 5, 10: 5, 14: 5, 18: 5, 1: 2, 3: 3, 4: 2, 5: 2, 7: 2, 8: 3, 9: 2, 11: 4, 12: 1, 13: 2, 15: 2, 16: 3, 17: 1, 19: 4, 20: 2 },
    },
    {
      id: "C",
      name: "People + Communication",
      description: "Counseling, teaching, HR, relationship-heavy roles",
      answers: { 3: 5, 6: 5, 11: 5, 14: 5, 19: 5, 1: 2, 2: 3, 4: 1, 5: 1, 7: 3, 8: 4, 9: 2, 10: 3, 12: 1, 13: 1, 15: 3, 16: 4, 17: 1, 18: 3, 20: 3 },
    },
    {
      id: "D",
      name: "Practical + Physical",
      description: "Trades, field work, maintenance, hands-on roles",
      answers: { 4: 5, 12: 5, 17: 5, 1: 3, 2: 1, 3: 1, 5: 2, 6: 1, 7: 3, 8: 2, 9: 2, 10: 1, 11: 1, 13: 2, 14: 1, 15: 4, 16: 2, 18: 1, 19: 1, 20: 2 },
    },
    {
      id: "E",
      name: "Organization + Leadership",
      description: "Operations, management, administration, coordination",
      answers: { 7: 5, 8: 5, 15: 5, 16: 5, 20: 5, 1: 3, 2: 2, 3: 3, 4: 1, 5: 2, 6: 4, 9: 3, 10: 2, 11: 3, 12: 1, 13: 2, 14: 4, 17: 2, 18: 2, 19: 4 },
    },
    {
      id: "F",
      name: "Analytical + Organization (Low People)",
      description: "Finance, accounting, analysis, compliance",
      answers: { 1: 5, 7: 5, 9: 5, 15: 5, 20: 5, 2: 2, 3: 1, 4: 1, 5: 4, 6: 2, 8: 3, 10: 1, 11: 1, 12: 1, 13: 4, 14: 2, 16: 2, 17: 4, 18: 2, 19: 1 },
    },
    {
      id: "G",
      name: "People + Leadership",
      description: "Management, sales leadership, organizational roles",
      answers: { 3: 5, 8: 5, 11: 5, 16: 5, 19: 5, 1: 2, 2: 3, 4: 1, 5: 1, 6: 5, 7: 4, 9: 2, 10: 2, 12: 1, 13: 1, 14: 4, 15: 3, 17: 1, 18: 2, 20: 4 },
    },
    {
      id: "H",
      name: "Creative + Practical",
      description: "Design/build/making-oriented occupations",
      answers: { 2: 5, 4: 5, 10: 5, 12: 5, 18: 5, 1: 3, 3: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 11: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 3, 19: 2, 20: 2 },
    },
  ];

  console.log("================================================================================");
  console.log("TOP 15 RECOMMENDATIONS FOR 8 PERSONAS");
  console.log("================================================================================");

  const personaResults = [];
  const top10Occupations = new Set();
  const occupationFrequencyInTop10 = {};

  for (const p of personas) {
    const profile = calculateProfile(p.answers);
    const matches = matchOccupations(profile, occupations, 15);
    personaResults.push({ persona: p, profile, matches });

    matches.slice(0, 10).forEach((m) => {
      top10Occupations.add(m.occupation.slug);
      occupationFrequencyInTop10[m.occupation.title] = (occupationFrequencyInTop10[m.occupation.title] || 0) + 1;
    });

    console.log(`\n### Persona ${p.id}: ${p.name}`);
    console.log(`Profile:`, JSON.stringify(profile.dimensionScores));
    matches.forEach((m, idx) => {
      console.log(
        `  ${idx + 1}. [${m.careerFit}%] ${m.occupation.title} (${m.occupation.category}) | AI Exp: ${m.occupation.aiExposure}, Repl Risk: ${m.occupation.replacementRisk}`
      );
    });
  }

  // Adversarial Profiles
  console.log("\n================================================================================");
  console.log("ADVERSARIAL EXTREMES");
  console.log("================================================================================");
  const adversarialProfiles = [
    {
      name: "Adv 1: Tech=100, Analytical=100, Others=0",
      answers: { 1: 5, 5: 5, 9: 5, 13: 5, 17: 5, 2: 1, 3: 1, 4: 1, 6: 1, 7: 1, 8: 1, 10: 1, 11: 1, 12: 1, 14: 1, 15: 1, 16: 1, 18: 1, 19: 1, 20: 1 },
    },
    {
      name: "Adv 2: People=100, Comm=100, Tech=0, Practical=0",
      answers: { 3: 5, 6: 5, 11: 5, 14: 5, 19: 5, 1: 1, 2: 1, 4: 1, 5: 1, 7: 1, 8: 1, 9: 1, 10: 1, 12: 1, 13: 1, 15: 1, 16: 1, 17: 1, 18: 1, 20: 1 },
    },
    {
      name: "Adv 3: Practical=100, Tech=0, Comm=0",
      answers: { 4: 5, 12: 5, 1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1 },
    },
    {
      name: "Adv 4: Creativity=100, Analytical=0, Org=0",
      answers: { 2: 5, 10: 5, 18: 5, 1: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 11: 1, 12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1, 19: 1, 20: 1 },
    },
  ];

  for (const adv of adversarialProfiles) {
    const profile = calculateProfile(adv.answers);
    const matches = matchOccupations(profile, occupations, 5);
    console.log(`\n${adv.name}`);
    console.log(`Profile:`, JSON.stringify(profile.dimensionScores));
    matches.forEach((m, idx) => {
      console.log(`  ${idx + 1}. [${m.careerFit}%] ${m.occupation.title} (${m.occupation.category})`);
    });
  }

  // Monotonicity Test
  console.log("\n================================================================================");
  console.log("MONOTONICITY TESTS");
  console.log("================================================================================");
  const targetOccSlug = "computer-programmers";
  console.log(`Testing occupation: ${targetOccSlug} while increasing Technology affinity:`);
  for (const techLevel of [20, 50, 80, 100]) {
    const testProfile = {
      dimensionScores: {
        analytical: 80, creativity: 40, communication: 40, people: 20, practical: 20, organization: 70, technology: techLevel, leadership: 40,
      },
    };
    const all = matchOccupations(testProfile, occupations, 507);
    const rank = all.findIndex((m) => m.occupation.slug === targetOccSlug) + 1;
    const match = all.find((m) => m.occupation.slug === targetOccSlug);
    console.log(`  Technology=${techLevel} -> Rank #${rank}/507, Fit=${match?.careerFit}%`);
  }

  console.log(`Testing People orientation while increasing from 20 to 100:`);
  for (const peopleLevel of [20, 50, 80, 100]) {
    const testProfile = {
      dimensionScores: {
        analytical: 60, creativity: 30, communication: 70, people: peopleLevel, practical: 30, organization: 70, technology: 30, leadership: 40,
      },
    };
    const all = matchOccupations(testProfile, occupations, 507);
    const topMatch = all[0];
    console.log(`  People=${peopleLevel} -> Top Match: ${topMatch.occupation.title} (${topMatch.occupation.category}), Fit=${topMatch.careerFit}%`);
  }

  console.log(`Testing Practical work while increasing from 20 to 100:`);
  for (const practicalLevel of [20, 50, 80, 100]) {
    const testProfile = {
      dimensionScores: {
        analytical: 40, creativity: 30, communication: 30, people: 30, practical: practicalLevel, organization: 50, technology: 40, leadership: 30,
      },
    };
    const all = matchOccupations(testProfile, occupations, 507);
    const topMatch = all[0];
    console.log(`  Practical=${practicalLevel} -> Top Match: ${topMatch.occupation.title} (${topMatch.occupation.category}), Fit=${topMatch.careerFit}%`);
  }

  console.log(`Testing Leadership while increasing from 20 to 100:`);
  for (const leadLevel of [20, 50, 80, 100]) {
    const testProfile = {
      dimensionScores: {
        analytical: 50, creativity: 40, communication: 80, people: 70, practical: 20, organization: 80, technology: 40, leadership: leadLevel,
      },
    };
    const all = matchOccupations(testProfile, occupations, 507);
    const topMatch = all[0];
    console.log(`  Leadership=${leadLevel} -> Top Match: ${topMatch.occupation.title} (${topMatch.occupation.category}), Fit=${topMatch.careerFit}%`);
  }

  // Distribution Statistics
  console.log("\n================================================================================");
  console.log("DISTRIBUTION OVER 507 OCCUPATIONS");
  console.log("================================================================================");
  for (const pr of personaResults) {
    const allMatches = matchOccupations(pr.profile, occupations, 507);
    const scores = allMatches.map((m) => m.careerFit).sort((a, b) => a - b);
    const min = scores[0];
    const max = scores[scores.length - 1];
    const median = scores[Math.floor(scores.length / 2)];
    const mean = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1);
    const p90 = scores[Math.floor(scores.length * 0.9)];
    console.log(`${pr.persona.id}. ${pr.persona.name}: Min=${min}%, Median=${median}%, Mean=${mean}%, P90=${p90}%, Max=${max}% (Diff: ${max - min}%)`);
  }

  // Duplication Check
  console.log("\n================================================================================");
  console.log("DOMINANCE & OVERLAP ANALYSIS");
  console.log("================================================================================");
  console.log(`Unique occupations in top 10 across 8 personas: ${top10Occupations.size} / 80 slots`);
  console.log("Occurrences across personas in top 10:");
  const sortedFreq = Object.entries(occupationFrequencyInTop10).sort((a, b) => b[1] - a[1]);
  sortedFreq.forEach(([title, freq]) => {
    if (freq >= 2) {
      console.log(`  - ${title}: in ${freq}/8 personas (${((freq / 8) * 100).toFixed(0)}%)`);
    }
  });

  // Perturbation Stability Test
  console.log("\n================================================================================");
  console.log("STABILITY PERTURBATION TEST (Single Likert Step)");
  console.log("================================================================================");
  for (const p of personas.slice(0, 3)) {
    const p1 = calculateProfile(p.answers);
    const top10_1 = matchOccupations(p1, occupations, 10).map((m) => m.occupation.slug);

    // Perturb question 1 by +1
    const perturbedAnswers = { ...p.answers, 1: Math.min(5, (p.answers[1] || 3) + 1) };
    const p2 = calculateProfile(perturbedAnswers);
    const top10_2 = matchOccupations(p2, occupations, 10).map((m) => m.occupation.slug);

    const overlap = top10_1.filter((slug) => top10_2.includes(slug)).length;
    console.log(`Persona ${p.id} (${p.name}): Single Likert step on Q1 retained ${overlap}/10 top occupations.`);
  }
}

main();
