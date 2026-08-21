import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHero, PageShell } from "@/components/PageShell";
import { MetricBar } from "@/components/ScoreCard";
import { getCareerRecommendations } from "@/lib/api";
import type { CareerRecommendation } from "@/types/occupation";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Your career matches", robots: { index: false, follow: true } };

export default async function CareerResultsPage({ searchParams }: PageProps<"/career-finder/results">) {
  const query = await searchParams;
  const from = typeof query.from === "string" ? query.from : "";
  if (!from) redirect("/career-finder");
  const experienceYears = Number(typeof query.experienceYears === "string" ? query.experienceYears : 4);
  const skills = typeof query.skills === "string" ? query.skills.split(",").map((skill) => skill.trim()).filter(Boolean) : [];
  const education = typeof query.education === "string" ? query.education : "bachelors";
  const country = typeof query.country === "string" ? query.country : "India";
  const salaryExpectation = typeof query.salaryExpectation === "string" ? query.salaryExpectation : "same_or_higher";
  const retrainingTolerance = typeof query.retrainingTolerance === "string" ? query.retrainingTolerance : "few_months";
  const result = await getCareerRecommendations({
    currentOccupationSlug: from,
    experienceYears,
    skills,
    education,
    country,
    salaryExpectation,
    retrainingTolerance,
  });
  const [featured, ...secondary] = result.recommendations;
  const transferable = unique(result.recommendations.flatMap((career) => career.transferableSkills));
  const missing = unique(result.recommendations.flatMap((career) => career.missingSkills));
  const retrainingLabel = retrainingTolerance.replaceAll("_", " ");

  return <PageShell><PageHero dark eyebrow="Personal career analysis" title="Your strongest career moves." copy={`Based on your ${result.currentOccupationTitle} background, ${experienceYears} years of experience, ${country}, and a ${retrainingLabel} retraining limit.`}><Link className="button secondary" href={`/career-finder?occupation=${result.currentOccupationSlug}`}>Edit answers</Link></PageHero><main>
    {!featured && <section className="content-section"><div className="container narrow"><div className="empty-state"><h2>No transition fits these limits yet.</h2><p>Try a broader retraining range or add more transferable skills. We will not recommend a move that exceeds your stated limit.</p><Link className="button" href={`/career-finder?occupation=${result.currentOccupationSlug}`}>Edit my answers</Link></div></div></section>}
    {featured && <section className="content-section"><div className="container"><RecommendationFeature career={featured} /></div></section>}
    {secondary.length > 0 && <section className="content-section section-tint"><div className="container recommendation-grid">{secondary.map((career) => <RecommendationCard career={career} key={career.slug} />)}</div></section>}
    {featured && <section className="content-section"><div className="container two-column"><article className="card"><div className="section-kicker">Transferable skills</div><h2>You already bring</h2><div className="skill-cloud">{transferable.length ? transferable.map((skill) => <span className="chip safe" key={skill}>{skill}</span>) : <p>We found general experience overlap, but no exact skill labels yet.</p>}</div></article><article className="card"><div className="section-kicker">Skill gaps</div><h2>Add these next</h2><div className="skill-cloud">{missing.map((skill) => <span className="chip" key={skill}>{skill}</span>)}</div></article></div></section>}
  </main></PageShell>;
}

function RecommendationFeature({ career }: { career: CareerRecommendation }) {
  return <article className="featured-match"><div><span className="chip">{career.category}</span><h2>{career.title}</h2><p>{career.whyFit}</p><Link className="button" href={`/jobs/${career.slug}`}>Explore this career →</Link></div><div className="match-metrics"><div><span className="metric-label">Replacement risk</span><strong>{career.replacementRisk}</strong></div><div><span className="metric-label">Skill overlap</span><strong>{career.skillOverlap}%</strong></div><div><span className="metric-label">Transition</span><strong>{career.transitionDifficulty}</strong></div><div><span className="metric-label">Retraining</span><strong>{career.retrainingMonths}</strong></div></div></article>;
}

function RecommendationCard({ career }: { career: CareerRecommendation }) {
  return <article className="card career-card"><span className="chip safe">{career.category}</span><h3>{career.title}</h3><p>{career.whyFit}</p><MetricBar label="Skill overlap" value={career.skillOverlap} suffix="%" /><dl className="compact-list"><div><dt>AI risk</dt><dd>{career.replacementRisk}/100</dd></div><div><dt>AI resilience</dt><dd>{career.aiResilience}/100</dd></div><div><dt>Difficulty</dt><dd>{career.transitionDifficulty}</dd></div><div><dt>Salary direction</dt><dd>{career.salaryDirection}</dd></div><div><dt>Retraining</dt><dd>{career.retrainingMonths}</dd></div></dl><Link className="text-link" href={`/jobs/${career.slug}`}>View career details →</Link></article>;
}

function unique(values: string[]) { return [...new Set(values)].slice(0, 8); }
