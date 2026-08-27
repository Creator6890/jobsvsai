import type { Metadata } from "next";
import Link from "next/link";
import { AdSlot } from "@/components/AdSlot";
import { OccupationSearch } from "@/components/OccupationSearch";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { getOccupations } from "@/lib/api";
import type { Occupation } from "@/types/occupation";
import { getScoreSemantics } from "@/lib/scoreSemantics";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Will AI Take Your Job? AI Job Risk & Career Analysis | JobsVsAI",
  description:
    "Find out how AI could affect your job. Explore AI Exposure, Replacement Risk, vulnerable tasks, human advantages and safer career paths across hundreds of occupations.",
  openGraph: {
    title: "Will AI Take Your Job? AI Job Risk & Career Analysis | JobsVsAI",
    description:
      "The intelligence layer for navigating your career through AI. Task-level evidence, verified AI Exposure and Replacement Risk scores.",
  },
};

export default async function Home() {
  const occupations = await getOccupations();

  // Derived datasets from verified cohort
  const exposed = [...occupations].sort((a, b) => b.aiExposure - a.aiExposure).slice(0, 5);
  const resilient = [...occupations].sort((a, b) => a.replacementRisk - b.replacementRisk).slice(0, 5);
  const gapLeaders = [...occupations]
    .sort((a, b) => (b.aiExposure - b.replacementRisk) - (a.aiExposure - a.replacementRisk))
    .slice(0, 5);

  const totalTasks = occupations.reduce((acc, curr) => acc + (curr.tasks?.length || 0), 0);

  // Field counts for directory preview
  const fieldDefinitions = [
    { title: "Technology & Data", slug: "technology-data", match: (c: string) => c.includes("Technology") || c.includes("Data") },
    { title: "Business & Finance", slug: "business-finance", match: (c: string) => c.includes("Business") || c.includes("Finance") },
    { title: "Healthcare", slug: "healthcare", match: (c: string) => c.includes("Healthcare") },
    { title: "Creative & Media", slug: "creative-media", match: (c: string) => c.includes("Creative") || c.includes("Media") },
    { title: "Education & Training", slug: "education", match: (c: string) => c.includes("Education") || c.includes("Training") },
    { title: "Legal", slug: "legal", match: (c: string) => c.includes("Legal") },
    { title: "Management & Leadership", slug: "management", match: (c: string) => c.includes("Management") || c.includes("Leadership") },
    { title: "Sales", slug: "sales", match: (c: string) => c.includes("Sales") },
    { title: "Engineering & Architecture", slug: "engineering", match: (c: string) => c.includes("Engineering") || c.includes("Architecture") },
    { title: "Skilled Trades", slug: "skilled-trades", match: (c: string) => c.includes("Installation") || c.includes("Construction") || c.includes("Repair") },
    { title: "Transport & Logistics", slug: "transportation", match: (c: string) => c.includes("Transport") || c.includes("Logistics") },
    { title: "Manufacturing & Production", slug: "production", match: (c: string) => c.includes("Manufacturing") || c.includes("Production") },
  ];

  const fieldStats = fieldDefinitions.map((fd) => {
    const matching = occupations.filter((o) => fd.match(o.category));
    return {
      ...fd,
      count: matching.length,
    };
  });

  return (
    <>
      <SiteHeader />
      <main id="main-content">
        {/* Hero */}
        <section className="home-hero">
          <div className="container hero-inner">
            <div className="eyebrow">Evidence-based career intelligence for the AI era</div>
            <h1>
              Will AI
              <br />
              take your job<span className="accent">?</span>
            </h1>
            <p className="hero-copy">
              Explore what AI can already do, what still depends on humans, and what stands between software capability and actual job replacement across hundreds of careers.
            </p>
            <OccupationSearch popularOccupations={occupations.slice(0, 3)} />
            <div className="hero-actions-row">
              <Link className="button secondary" href="/rankings">
                Explore AI Job Risk Rankings →
              </Link>
              <Link className="button secondary" href="/career-fit">
                Take Career Fit Assessment →
              </Link>
            </div>

            {/* Dynamic Proof Strip */}
            <div className="proof-strip-card">
              <div className="proof-metric">
                <strong>507</strong>
                <span>Verified analyses</span>
              </div>
              <div className="proof-metric-divider" aria-hidden="true" />
              <div className="proof-metric">
                <strong>390</strong>
                <span>Preliminary estimates</span>
              </div>
              <div className="proof-metric-divider" aria-hidden="true" />
              <div className="proof-metric">
                <strong>897</strong>
                <span>Searchable occupations</span>
              </div>
              <div className="proof-metric-divider" aria-hidden="true" />
              <div className="proof-metric">
                <strong>{totalTasks.toLocaleString()}</strong>
                <span>Assessed tasks (verified)</span>
              </div>
              <div className="proof-metric-divider" aria-hidden="true" />
              <div className="proof-metric">
                <strong>15</strong>
                <span>AI capability dimensions</span>
              </div>
            </div>
          </div>
        </section>

        {/* Section: Why Two Scores? */}
        <section className="section section-tint" aria-labelledby="why-two-scores-title">
          <div className="container">
            <div className="section-kicker">Core Intelligence</div>
            <div className="section-heading-row">
              <div>
                <h2 id="why-two-scores-title">
                  AI can do the work.
                  <br />
                  That doesn&apos;t always mean AI can take the job.
                </h2>
                <p>
                  JobsVsAI separates task capability from structural replacement to provide calm, realistic career clarity.
                </p>
              </div>
              <Link className="text-link desktop-only" href="/methodology">
                Read our methodology →
              </Link>
            </div>

            <div className="two-column" style={{ marginTop: "24px" }}>
              <article className="card definition-card">
                <span className="section-kicker">Capability Measurement</span>
                <h3>AI Exposure</h3>
                <p>
                  Measures how strongly an occupation&apos;s daily tasks overlap with current AI system capabilities. High exposure means AI can draft, analyze, generate, or assist with significant portions of the workflow.
                </p>
                <div className="metric-callout">
                  <strong>High capability overlap ≠ Immediate unemployment</strong>
                </div>
              </article>

              <article className="card definition-card">
                <span className="section-kicker">Structural Vulnerability</span>
                <h3>Replacement Risk</h3>
                <p>
                  Estimates relative labour-market vulnerability after applying real-world friction: physical manipulation, human accountability, stakeholder trust, regulatory governance, and adoption economics.
                </p>
                <div className="metric-callout">
                  <strong>Relative risk index (0–100) ≠ Probability percentage</strong>
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* Section: How It Works */}
        <section className="section" aria-labelledby="how-it-works-title">
          <div className="container">
            <div className="section-kicker">Methodology in 3 Steps</div>
            <h2 id="how-it-works-title">How JobsVsAI evaluates career risk</h2>
            <div className="factor-grid" style={{ marginTop: "24px" }}>
              <article className="card factor-card">
                <strong>01</strong>
                <h3>We break jobs into tasks</h3>
                <p>
                  Jobs are not monolithic. We analyze individual task statements from O*NET 30.3, weighting each task by importance and frequency.
                </p>
              </article>
              <article className="card factor-card">
                <strong>02</strong>
                <h3>We measure task capability</h3>
                <p>
                  Each task is evaluated across 15 distinct AI capability dimensions to calculate baseline capability overlap and automation feasibility.
                </p>
              </article>
              <article className="card factor-card">
                <strong>03</strong>
                <h3>We apply structural barriers</h3>
                <p>
                  We incorporate physical constraints, human dependency, commercial adoption pressure, and institutional resilience before publishing scores.
                </p>
              </article>
            </div>
            <div style={{ marginTop: "24px", textAlign: "center" }}>
              <Link className="button secondary" href="/methodology">
                See the Full Methodology & Sources →
              </Link>
            </div>
          </div>
        </section>

        {/* Section: Rankings at a glance */}
        <section className="section section-tint" aria-labelledby="ranking-preview-title">
          <div className="container">
            <div className="section-kicker">Verified Cohort (507 Occupations)</div>
            <div className="section-heading-row">
              <div>
                <h2 id="ranking-preview-title">Rankings at a glance</h2>
                <p>Explore highest exposure careers, resilient human strongholds, and large capability gaps.</p>
              </div>
              <Link className="text-link desktop-only" href="/rankings">
                Explore all rankings →
              </Link>
            </div>
            <div className="ranking-grid home-ranking-grid">
              <RankingPreview title="Most AI-Exposed" jobs={exposed} score="aiExposure" />
              <RankingPreview title="Lowest Replacement Risk" jobs={resilient} score="replacementRisk" />
              <RankingPreview title="Largest Exposure Gap" jobs={gapLeaders} score="aiExposure" />
            </div>
            <Link className="button secondary mobile-ranking-link" href="/rankings">
              Explore all rankings →
            </Link>
          </div>
        </section>

        {/* Section: Career Fields Preview */}
        <section className="section" aria-labelledby="career-fields-title">
          <div className="container">
            <div className="section-kicker">Industry Taxonomy</div>
            <div className="section-heading-row">
              <div>
                <h2 id="career-fields-title">Explore by Career Field</h2>
                <p>Browse verified analyses grouped by occupational domain and sector.</p>
              </div>
            </div>
            <div className="career-grid" style={{ marginTop: "20px" }}>
              {fieldStats.map((field) => (
                <article className="card" key={field.slug} style={{ padding: "20px" }}>
                  <h3>{field.title}</h3>
                  <p className="muted" style={{ fontSize: "0.85rem", marginTop: "6px" }}>
                    {field.count} verified {field.count === 1 ? "occupation" : "occupations"}
                  </p>
                  <Link
                    className="text-link"
                    href={`/rankings`}
                    style={{ marginTop: "12px", display: "inline-block", fontSize: "0.85rem" }}
                  >
                    View in rankings →
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Career Fit Assessment CTA */}
        <section className="section section-tint" aria-labelledby="career-fit-cta-title">
          <div className="container">
            <div className="card career-fit-cta-card">
              <div>
                <div className="section-kicker">Personal Work Strengths</div>
                <h2 id="career-fit-cta-title">Find careers that match how you work</h2>
                <p>
                  Low AI risk alone does not make a career the right fit. Take a 3-minute assessment across 8 core work dimensions to discover occupations aligned with your strengths and preferences, paired with verified AI risk metrics.
                </p>
              </div>
              <Link className="button primary" href="/career-fit">
                Take Career Fit Assessment →
              </Link>
            </div>
          </div>
        </section>

        {/* AdSlot */}
        <div className="container ad-break">
          <AdSlot slot="home" format="horizontal" />
        </div>

        {/* Section: Comprehensive FAQ */}
        <section className="section" aria-labelledby="home-faq-title">
          <div className="container">
            <div className="section-kicker">Frequently Asked Questions</div>
            <h2 id="home-faq-title">Common questions about AI and career risk</h2>
            <div className="faq-stack" style={{ marginTop: "28px" }}>
              <FaqItem
                question="Will AI replace my job?"
                answer="AI rarely eliminates an entire occupation overnight. Instead, AI automates or accelerates specific tasks within a job. Roles dominated by routine, screen-based data processing experience high workflow change, while jobs requiring physical dexterity, unconstrained environment navigation, deep stakeholder trust, and legal accountability remain anchored by human professionals."
              />
              <FaqItem
                question="What is AI Exposure?"
                answer="AI Exposure (0–100) measures how much of an occupation's day-to-day task mix overlaps with the technical capabilities of current artificial intelligence systems. A high exposure score means software can perform or assist with a significant share of the workload."
              />
              <FaqItem
                question="What is Replacement Risk?"
                answer="Replacement Risk (0–100) estimates whether technical AI exposure translates into reduced human demand. It accounts for real-world friction—including physical constraints, human dependency, professional accountability, adoption economics, and institutional regulations."
              />
              <FaqItem
                question="Does a Replacement Risk score of 70 mean a 70% probability of job loss?"
                answer="No. JobsVsAI scores are index ratings on a 0–100 scale, not probabilities or unemployment forecasts. A score of 70 indicates that the occupation exhibits higher structural vulnerability compared to lower-scoring occupations across the economy."
              />
              <FaqItem
                question="Why can AI Exposure be high while Replacement Risk is lower?"
                answer="A job can be highly exposed to AI without being easy to replace. For example, software developers or healthcare practitioners perform many analytical and administrative tasks AI can accelerate, yet human architecture, regulatory liability, and bedside care prevent direct headcount reduction."
              />
              <FaqItem
                question="Where does JobsVsAI get occupation data?"
                answer="JobsVsAI uses official occupational taxonomy and task data from the U.S. Department of Labor's O*NET database (Version 30.3), encompassing detailed task ratings, work activities, and importance weights."
              />
              <FaqItem
                question="How are JobsVsAI scores calculated?"
                answer="We evaluate every task in an occupation against 15 AI capability dimensions from our Capability Index, compute task-level automation feasibility, aggregate weighted task exposure, and then apply structural modifiers for physical work, human dependency, and commercial adoption pressure."
              />
              <FaqItem
                question="Does ChatGPT generate occupation scores?"
                answer="No chatbot generates the score when a page is opened. JobsVsAI scores are calculated through a versioned scoring pipeline from occupational task evidence and mapped AI capabilities."
              />
              <FaqItem
                question="How often are scores updated?"
                answer="Scores are recalculated when new major AI capability milestones are verified, when underlying O*NET taxonomy releases occur, or when methodology calibrations are published in our changelog."
              />
              <FaqItem
                question="Does location affect AI job risk?"
                answer="Yes. Local adoption speed, wages, regulatory requirements, and union protections alter how quickly businesses invest in automation. JobsVsAI scores reflect baseline occupation structure rather than local market variations."
              />
              <FaqItem
                question="What should I do if my occupation has high risk?"
                answer="High risk is a signal to adapt, not panic. Workers in exposed fields should proactively adopt AI tools to accelerate routine tasks while leaning into interpersonal leadership, specialized domain judgment, and complex verification work that algorithms cannot replace."
              />
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function RankingPreview({
  title,
  jobs,
  score,
}: {
  title: string;
  jobs: Occupation[];
  score: "aiExposure" | "replacementRisk";
}) {
  return (
    <article className="card ranking-preview">
      <div className="card-heading">
        <h3 style={{ fontSize: "1.05rem" }}>{title}</h3>
        <span className="muted small">Score /100</span>
      </div>
      {jobs.length === 0 && <p className="empty-state compact">No occupations are published yet.</p>}
      <ol className="ranking-list">
        {jobs.map((job, index) => {
          const sem = getScoreSemantics(score, job[score]);
          return (
            <li key={job.slug}>
              <span className="rank-number">{index + 1}</span>
              <Link href={`/jobs/${job.slug}`}>{job.title}</Link>
              <span className={sem.badgeClass} title={sem.label}>
                {job[score]}
              </span>
            </li>
          );
        })}
      </ol>
    </article>
  );
}

function FaqItem({ question, answer }: { question: string; answer: string }) {
  return (
    <details className="card faq-item" style={{ padding: "18px 24px", marginBottom: "12px" }}>
      <summary style={{ fontWeight: 750, fontSize: "1.05rem", cursor: "pointer" }}>
        {question}
      </summary>
      <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
        {answer}
      </p>
    </details>
  );
}
