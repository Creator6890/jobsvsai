import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRankings, RankingOccupation } from "@/lib/api";
import {
  CANONICAL_CAREER_FIELDS,
  calculateFieldAnalytics,
  getCanonicalField,
} from "@/lib/careerFields";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";
import { FieldExplorer } from "@/components/FieldExplorer";
import { getScoreSemantics } from "@/lib/scoreSemantics";

interface CareerFieldPageProps {
  params: Promise<{ field: string }>;
}

export async function generateStaticParams() {
  return Object.keys(CANONICAL_CAREER_FIELDS).map((slug) => ({
    field: slug,
  }));
}

export async function generateMetadata({ params }: CareerFieldPageProps): Promise<Metadata> {
  const { field: fieldParam } = await params;
  const field = getCanonicalField(fieldParam);
  if (!field) return {};

  const title = `AI Risk in ${field.name} Careers: Jobs Ranked by AI Exposure & Replacement Risk`;
  const description = `Explore AI exposure, replacement risk, and human resilience across verified ${field.name} occupations. See median scores, highest-risk roles, and structural job moats.`;
  const url = `https://jobsvsai.com/careers/${field.slug}`;

  return {
    title,
    description,
    alternates: {
      canonical: url,
    },
    openGraph: {
      title: `${title} | JobsVsAI`,
      description,
      url,
    },
  };
}

export default async function CareerFieldPage({ params }: CareerFieldPageProps) {
  const { field: fieldParam } = await params;
  const fieldDef = getCanonicalField(fieldParam);

  if (!fieldDef) {
    notFound();
  }

  const allRankings = await getRankings();
  const { field, analytics, occupations } = calculateFieldAnalytics(
    fieldDef.slug,
    allRankings
  );

  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Career Fields", item: "/careers" },
    { name: field.name, item: `/careers/${field.slug}` },
  ];

  const medianExpSem = getScoreSemantics("ai_exposure", analytics.medianAiExposure);
  const medianRiskSem = getScoreSemantics("replacement_risk", analytics.medianReplacementRisk);

  return (
    <PageShell>
      <PageHero
        eyebrow="Career Field Intelligence"
        title={`AI risk in ${field.name} careers`}
        copy={field.tagline}
      />

      <main className="page-main" id="main-content">
        <div className="container">
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          {/* Section: Aggregate Field Metrics */}
          <section aria-labelledby="field-analytics-heading" style={{ marginBottom: "36px" }}>
            <h2 id="field-analytics-heading" className="sr-only">
              {field.name} Aggregate AI Analytics
            </h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "18px",
                marginBottom: "24px",
              }}
            >
              <div className="card" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
                  Verified Analyses
                </span>
                <strong style={{ fontSize: "2rem", color: "var(--violet)", lineHeight: 1.1 }}>
                  {analytics.verifiedCount}
                </strong>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                  Full task-level assessments
                </span>
              </div>

              <div className="card" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
                  Median AI Exposure
                </span>
                <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
                  <strong style={{ fontSize: "2rem", color: "var(--ink)", lineHeight: 1.1 }}>
                    {Math.round(analytics.medianAiExposure)}
                  </strong>
                  <span className={`score-badge ${medianExpSem.tone}`} style={{ fontSize: "0.74rem" }}>
                    {medianExpSem.shortLabel}
                  </span>
                </div>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                  Frontier software proximity
                </span>
              </div>

              <div className="card" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
                  Median Replacement Risk
                </span>
                <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
                  <strong style={{ fontSize: "2rem", color: "var(--ink)", lineHeight: 1.1 }}>
                    {Math.round(analytics.medianReplacementRisk)}
                  </strong>
                  <span className={`score-badge ${medianRiskSem.tone}`} style={{ fontSize: "0.74rem" }}>
                    {medianRiskSem.shortLabel}
                  </span>
                </div>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                  Net economic displacement
                </span>
              </div>

              <div className="card" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
                  Risk Distribution
                </span>
                <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                  <span className="score-badge safe" title="Low Risk (0-33)">
                    {analytics.riskDistribution.low} Low
                  </span>
                  <span className="score-badge moderate" title="Moderate Risk (34-66)">
                    {analytics.riskDistribution.moderate} Mod
                  </span>
                  <span className="score-badge risk" title="High Risk (67-100)">
                    {analytics.riskDistribution.high} High
                  </span>
                </div>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", marginTop: "auto" }}>
                  {Math.round((analytics.riskDistribution.low / (analytics.verifiedCount || 1)) * 100)}% low risk
                </span>
              </div>
            </div>

            {/* Field Spotlight Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "18px" }}>
              {analytics.highestReplacementRisk && (
                <div className="card" style={{ padding: "20px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--red)" }}>
                    Highest Replacement Risk
                  </span>
                  <h3 style={{ fontSize: "1.05rem", margin: "6px 0 8px" }}>
                    <Link href={`/jobs/${analytics.highestReplacementRisk.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                      {analytics.highestReplacementRisk.title}
                    </Link>
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="score-badge risk">
                      {analytics.highestReplacementRisk.score} Risk
                    </span>
                  </div>
                </div>
              )}

              {analytics.lowestReplacementRisk && (
                <div className="card" style={{ padding: "20px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--green)" }}>
                    Lowest Replacement Risk
                  </span>
                  <h3 style={{ fontSize: "1.05rem", margin: "6px 0 8px" }}>
                    <Link href={`/jobs/${analytics.lowestReplacementRisk.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                      {analytics.lowestReplacementRisk.title}
                    </Link>
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="score-badge safe">
                      {analytics.lowestReplacementRisk.score} Risk
                    </span>
                  </div>
                </div>
              )}

              {analytics.largestGapLeader && (
                <div className="card" style={{ padding: "20px" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 750, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--violet)" }}>
                    Largest Exposure Gap
                  </span>
                  <h3 style={{ fontSize: "1.05rem", margin: "6px 0 8px" }}>
                    <Link href={`/jobs/${analytics.largestGapLeader.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                      {analytics.largestGapLeader.title}
                    </Link>
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--muted)" }}>
                    <span>{analytics.largestGapLeader.exposure} Exposure</span>
                    <span>→</span>
                    <span>{analytics.largestGapLeader.replacementRisk} Risk</span>
                    <span className="chip safe" style={{ fontSize: "0.72rem" }}>
                      +{analytics.largestGapLeader.gap} Gap
                    </span>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Section: Overview & Structural Drivers */}
          <section className="card" style={{ padding: "32px", marginBottom: "36px" }}>
            <h2 style={{ fontSize: "1.35rem", marginBottom: "16px" }}>
              Understanding AI impact in {field.name}
            </h2>
            <p style={{ fontSize: "1.02rem", lineHeight: 1.65, color: "var(--ink)", marginBottom: "28px" }}>
              {field.overviewIntro}
            </p>

            <h3 style={{ fontSize: "1.05rem", fontWeight: 750, color: "var(--ink)", marginBottom: "16px" }}>
              Key Structural Drivers
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
              {field.structuralDrivers.map((driver) => (
                <div key={driver.title} style={{ background: "var(--soft)", padding: "18px 20px", borderRadius: "var(--radius-xs)" }}>
                  <h4 style={{ fontSize: "0.92rem", fontWeight: 750, color: "var(--violet)", margin: "0 0 6px" }}>
                    {driver.title}
                  </h4>
                  <p style={{ fontSize: "0.88rem", lineHeight: 1.55, margin: 0, color: "var(--text)" }}>
                    {driver.description}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Section: Verified Occupations Explorer */}
          <section style={{ marginBottom: "48px" }}>
            <div style={{ marginBottom: "20px" }}>
              <h2 style={{ fontSize: "1.35rem", margin: 0 }}>
                Verified {field.name} Occupations ({occupations.length})
              </h2>
              <p style={{ fontSize: "0.92rem", color: "var(--muted)", margin: "6px 0 0" }}>
                Complete task-level evidence analyses ranked by replacement risk and exposure.
              </p>
            </div>

            <FieldExplorer occupations={occupations as RankingOccupation[]} fieldName={field.name} />
          </section>

          {/* Section: Field FAQ */}
          <section className="card" style={{ padding: "32px", marginBottom: "36px" }}>
            <h2 style={{ fontSize: "1.35rem", marginBottom: "20px" }}>
              Frequently asked questions about {field.name} careers
            </h2>
            <div className="faq-stack">
              {field.faqItems.map((faq) => (
                <details key={faq.question} className="faq-item card" style={{ padding: "16px 20px", marginBottom: "10px" }}>
                  <summary style={{ fontSize: "0.98rem", fontWeight: 750, color: "var(--ink)", cursor: "pointer" }}>
                    {faq.question}
                  </summary>
                  <p style={{ margin: "12px 0 0", fontSize: "0.92rem", lineHeight: 1.6, color: "var(--text)" }}>
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </section>

          {/* Section: Cross-Navigation */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px", padding: "20px 0" }}>
            <Link className="button secondary" href="/rankings">
              ← View All Rankings
            </Link>
            <Link className="button secondary" href="/career-fit">
              Find AI-Safe Careers That Fit You →
            </Link>
          </div>
        </div>
      </main>
    </PageShell>
  );
}
