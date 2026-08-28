import type { Metadata } from "next";
import Link from "next/link";
import { AdSlot } from "@/components/AdSlot";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { getOccupations } from "@/lib/api";
import { getCanonicalFieldSlug, CANONICAL_CAREER_FIELDS } from "@/lib/careerFields";
import { getScoreSemantics } from "@/lib/scoreSemantics";
import { OccupationMapExplorer, ExplorerOccupation } from "@/components/OccupationMapExplorer";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: {
    absolute: "Explore AI Job Risk by Occupation | JobsVsAI",
  },
  description:
    "Explore occupations by AI Exposure and Replacement Risk. See how AI affects different careers and why capability overlap does not always lead to the same replacement pressure.",
  alternates: {
    canonical: "https://jobsvsai.com/explore",
  },
  openGraph: {
    title: "Explore AI Job Risk by Occupation | JobsVsAI",
    description:
      "Interactive 2D occupation map comparing AI Exposure and Replacement Risk across hundreds of verified occupations.",
    url: "https://jobsvsai.com/explore",
  },
};

const FAQ_ITEMS = [
  {
    question: "What does this 2D occupation map show?",
    answer:
      "The occupation map plots verified careers across two independent dimensions: AI Exposure (horizontal X-axis) and Replacement Risk (vertical Y-axis). Each point represents one occupation, allowing you to instantly visualize how task-level software capability compares against structural labour-market vulnerability.",
  },
  {
    question: "What is the difference between AI Exposure and Replacement Risk?",
    answer:
      "AI Exposure (0–100) measures how much of an occupation's day-to-day task mix overlaps with current AI capabilities. Replacement Risk (0–100) measures structural vulnerability after accounting for real-world friction—including physical constraints, human dependency, fiduciary accountability, adoption economics, and institutional regulations.",
  },
  {
    question: "Why are some high-exposure jobs lower on replacement risk?",
    answer:
      "A job can be highly exposed to AI without being easy to replace. Occupations such as software developers, nurse practitioners, and financial advisors have high capability overlap with AI for drafting and analysis, yet statutory liability, system architecture, and human bedside care prevent direct headcount reduction.",
  },
  {
    question: "Does a high Replacement Risk score mean job loss is guaranteed?",
    answer:
      "No. JobsVsAI scores are index ratings on a 0–100 scale, not probabilities or unemployment forecasts. A score of 75 indicates that an occupation exhibits higher relative structural vulnerability compared to lower-scoring occupations across the economy.",
  },
  {
    question: "Are all occupations included in this explorer?",
    answer:
      "This explorer plots our verified cohort of 507 occupations with complete task-level evidence. Preliminary estimates are excluded from the default map to maintain strict methodology and empirical rigor.",
  },
];

export default async function ExplorePage() {
  const allOccupations = await getOccupations();

  // Map to ExplorerOccupation format with canonical field slugs
  const mappedOccupations: ExplorerOccupation[] = allOccupations.map((job) => {
    const fieldSlug = getCanonicalFieldSlug(job.slug, job.category);
    const fieldDef = CANONICAL_CAREER_FIELDS[fieldSlug];
    return {
      slug: job.slug,
      title: job.title,
      category: job.category,
      fieldSlug,
      fieldName: fieldDef ? fieldDef.name : job.category,
      aiExposure: Math.round(job.aiExposure),
      replacementRisk: Math.round(job.replacementRisk),
      confidence: job.confidence,
    };
  });

  // Derived Cohort: Largest Exposure Gap Leaders (High Exposure, Lower Risk)
  const gapLeaders = [...mappedOccupations]
    .sort((a, b) => b.aiExposure - b.replacementRisk - (a.aiExposure - a.replacementRisk))
    .slice(0, 5);

  // Curated Insight Cohorts
  const humanMoatsCohort = mappedOccupations
    .filter((j) => j.aiExposure >= 65 && j.replacementRisk <= 55)
    .sort((a, b) => b.aiExposure - b.replacementRisk - (a.aiExposure - a.replacementRisk))
    .slice(0, 4);

  const elevatedRiskCohort = mappedOccupations
    .filter((j) => j.aiExposure >= 65 && j.replacementRisk >= 65)
    .sort((a, b) => b.replacementRisk - a.replacementRisk)
    .slice(0, 4);

  const resilientPhysicalCohort = mappedOccupations
    .filter((j) => j.aiExposure <= 40 && j.replacementRisk <= 40)
    .sort((a, b) => a.replacementRisk - b.replacementRisk)
    .slice(0, 4);

  // Structured Data Schema
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  const breadcrumbsList = [
    { name: "Home", item: "/" },
    { name: "Explore AI Job Risk Map", item: "/explore" },
  ];

  return (
    <>
      <SiteHeader />
      <main id="main-content" className="explore-page">
        {/* Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
        />

        {/* Hero Section */}
        <section className="explore-hero">
          <div className="container">
            <Breadcrumbs items={breadcrumbsList} />

            <div className="explore-hero-inner">
              <div className="eyebrow">Visual Career Intelligence</div>
              <h1>Explore occupations in the AI era</h1>
              <p className="hero-copy">
                Compare occupations by AI Exposure and Replacement Risk. See which jobs are highly exposed to AI, which face greater replacement pressure, and which remain more resilient because of human, physical, or structural factors.
              </p>
            </div>

            {/* Intro Explainer & What to Look For Card */}
            <div className="card explore-intro-card" style={{ marginTop: "28px" }}>
              <div className="intro-main">
                <span className="section-kicker">Core Visual Guide</span>
                <h2 style={{ fontSize: "1.25rem", margin: "6px 0 10px" }}>
                  AI can do the work. That does not always mean AI can take the job.
                </h2>
                <p style={{ color: "var(--ink)", lineHeight: 1.6 }}>
                  This explorer maps occupations using two JobsVsAI measures. <strong>AI Exposure</strong> shows how much of the occupation’s task bundle overlaps with current AI capability. <strong>Replacement Risk</strong> shows how much of that exposure translates into structural pressure on the human role after physical constraints, accountability, and adoption realities are applied.
                </p>
              </div>

              <div className="intro-bullets-grid">
                <div className="intro-bullet">
                  <strong className="bullet-num">01</strong>
                  <div>
                    <strong>Upper-Right Quadrant:</strong>
                    <p className="small muted">Jobs in this zone are both highly exposed and under elevated structural replacement pressure.</p>
                  </div>
                </div>
                <div className="intro-bullet">
                  <strong className="bullet-num">02</strong>
                  <div>
                    <strong>Bottom-Right (Moat Zone):</strong>
                    <p className="small muted">Jobs far to the right but lower on the chart prove why exposure is not the same as replacement.</p>
                  </div>
                </div>
                <div className="intro-bullet">
                  <strong className="bullet-num">03</strong>
                  <div>
                    <strong>Bottom-Left Quadrant:</strong>
                    <p className="small muted">Occupations anchored in tactile trades and physical reality have low exposure and low risk.</p>
                  </div>
                </div>
                <div className="intro-bullet">
                  <strong className="bullet-num">04</strong>
                  <div>
                    <strong>Interactive Exploration:</strong>
                    <p className="small muted">Search or click any point on the chart to inspect task breakdown and full verified analysis.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Primary Interactive Explorer */}
        <section className="section" aria-labelledby="map-explorer-title">
          <div className="container">
            <div className="section-heading-row">
              <div>
                <h2 id="map-explorer-title">Interactive 2D Occupation Map</h2>
                <p>Plotting {mappedOccupations.length} verified occupations across capability exposure and structural risk.</p>
              </div>
            </div>

            <OccupationMapExplorer occupations={mappedOccupations} />
          </div>
        </section>

        {/* Curated Highlighted Groups */}
        <section className="section section-tint" aria-labelledby="curated-insights-title">
          <div className="container">
            <div className="section-kicker">Curated Patterns</div>
            <div className="section-heading-row">
              <div>
                <h2 id="curated-insights-title">Key occupational profiles across the map</h2>
                <p>Explore representative career cohorts that illustrate how AI exposure interacts with real-world barriers.</p>
              </div>
            </div>

            <div className="explore-curated-grid">
              {/* Group 1: Human Moats */}
              <article className="card curated-group-card">
                <span className="section-kicker" style={{ color: "var(--violet)" }}>High Exposure / High Shield</span>
                <h3>Strong Human &amp; Regulatory Moats</h3>
                <p className="small muted">
                  Substantial cognitive and documentation tasks overlap with AI, but statutory accountability, client advisory, or physical presence limit workforce reduction.
                </p>
                <div className="curated-links-list">
                  {humanMoatsCohort.map((job) => (
                    <Link key={job.slug} href={`/jobs/${job.slug}`} className="curated-job-link">
                      <span className="curated-job-title">{job.title}</span>
                      <div className="curated-job-scores">
                        <span className={getScoreSemantics("aiExposure", job.aiExposure).badgeClass}>
                          Exp: {job.aiExposure}
                        </span>
                        <span className={getScoreSemantics("replacementRisk", job.replacementRisk).badgeClass}>
                          Risk: {job.replacementRisk}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </article>

              {/* Group 2: Elevated Risk */}
              <article className="card curated-group-card">
                <span className="section-kicker" style={{ color: "var(--red)" }}>High Exposure / High Risk</span>
                <h3>Elevated Replacement Pressure</h3>
                <p className="small muted">
                  Standardized, screen-based transactional workflows facing aggressive commercial automation pressure with few regulatory or physical moats.
                </p>
                <div className="curated-links-list">
                  {elevatedRiskCohort.map((job) => (
                    <Link key={job.slug} href={`/jobs/${job.slug}`} className="curated-job-link">
                      <span className="curated-job-title">{job.title}</span>
                      <div className="curated-job-scores">
                        <span className={getScoreSemantics("aiExposure", job.aiExposure).badgeClass}>
                          Exp: {job.aiExposure}
                        </span>
                        <span className={getScoreSemantics("replacementRisk", job.replacementRisk).badgeClass}>
                          Risk: {job.replacementRisk}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </article>

              {/* Group 3: Resilient Physical */}
              <article className="card curated-group-card">
                <span className="section-kicker" style={{ color: "var(--green)" }}>Low Exposure / Low Risk</span>
                <h3>Physical &amp; Trade Resilience</h3>
                <p className="small muted">
                  Occupations anchored in unconstrained physical environments, fine manual dexterity, tactile diagnostics, and localized human presence.
                </p>
                <div className="curated-links-list">
                  {resilientPhysicalCohort.map((job) => (
                    <Link key={job.slug} href={`/jobs/${job.slug}`} className="curated-job-link">
                      <span className="curated-job-title">{job.title}</span>
                      <div className="curated-job-scores">
                        <span className={getScoreSemantics("aiExposure", job.aiExposure).badgeClass}>
                          Exp: {job.aiExposure}
                        </span>
                        <span className={getScoreSemantics("replacementRisk", job.replacementRisk).badgeClass}>
                          Risk: {job.replacementRisk}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* Biggest Gap Leaderboard */}
        <section className="section" aria-labelledby="gap-leaders-title">
          <div className="container">
            <div className="section-kicker">Differential Analysis</div>
            <div className="section-heading-row">
              <div>
                <h2 id="gap-leaders-title">Largest Exposure vs. Risk Gaps</h2>
                <p>Occupations where AI task capability overlap is highest relative to actual labour-market vulnerability.</p>
              </div>
              <Link className="text-link desktop-only" href="/rankings">
                View all rankings →
              </Link>
            </div>

            <div className="card gap-leaders-card">
              <div className="gap-leaders-table">
                <div className="gap-table-header">
                  <span>#</span>
                  <span>Occupation</span>
                  <span>Career Field</span>
                  <span style={{ textAlign: "center" }}>AI Exposure</span>
                  <span style={{ textAlign: "center" }}>Replacement Risk</span>
                  <span style={{ textAlign: "right" }}>Protection Gap</span>
                </div>
                {gapLeaders.map((job, idx) => {
                  const gap = job.aiExposure - job.replacementRisk;
                  return (
                    <div key={job.slug} className="gap-table-row">
                      <strong className="rank-number">{idx + 1}</strong>
                      <Link href={`/jobs/${job.slug}`} className="gap-job-link">
                        <strong>{job.title}</strong>
                      </Link>
                      <span className="gap-job-field muted">{job.fieldName}</span>
                      <div style={{ textAlign: "center" }}>
                        <span className={getScoreSemantics("aiExposure", job.aiExposure).badgeClass}>
                          {job.aiExposure}
                        </span>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <span className={getScoreSemantics("replacementRisk", job.replacementRisk).badgeClass}>
                          {job.replacementRisk}
                        </span>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span className="score-badge safe" title="Structural Protection Differential">
                          +{gap} pts
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* Ad Break */}
        <div className="container ad-break">
          <AdSlot slot="rankings" format="horizontal" />
        </div>

        {/* Comprehensive FAQ Section */}
        <section className="section section-tint" aria-labelledby="explore-faq-title">
          <div className="container">
            <div className="section-kicker">Frequently Asked Questions</div>
            <h2 id="explore-faq-title">Understanding the 2D Occupation Map</h2>
            <div className="faq-stack" style={{ marginTop: "28px" }}>
              {FAQ_ITEMS.map((item) => (
                <details
                  key={item.question}
                  className="card faq-item"
                  style={{ padding: "18px 24px", marginBottom: "12px" }}
                >
                  <summary style={{ fontWeight: 750, fontSize: "1.05rem", cursor: "pointer" }}>
                    {item.question}
                  </summary>
                  <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                    {item.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
