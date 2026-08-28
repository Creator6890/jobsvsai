import type { Metadata } from "next";
import Link from "next/link";
import { getRankings } from "@/lib/api";
import {
  CANONICAL_CAREER_FIELDS,
  CareerFieldSlug,
  calculateFieldAnalytics,
} from "@/lib/careerFields";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";
import { getScoreSemantics } from "@/lib/scoreSemantics";

export const metadata: Metadata = {
  title: "Career Fields Ranked by AI Exposure & Replacement Risk",
  description:
    "Explore AI exposure, replacement risk, and human resilience across 12 canonical career fields. Compare median scores and structural moats across occupations.",
  alternates: {
    canonical: "https://jobsvsai.com/careers",
  },
  openGraph: {
    title: "Career Fields Ranked by AI Exposure & Replacement Risk | JobsVsAI",
    description:
      "Explore AI exposure, replacement risk, and human resilience across 12 canonical career fields. Compare median scores and structural moats across occupations.",
    url: "https://jobsvsai.com/careers",
  },
};

export default async function CareerFieldsDirectoryPage() {
  const allRankings = await getRankings();

  const fieldKeys = Object.keys(CANONICAL_CAREER_FIELDS) as CareerFieldSlug[];
  const fieldsWithAnalytics = fieldKeys.map((slug) => {
    return calculateFieldAnalytics(slug, allRankings);
  });

  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Career Fields", item: "/careers" },
  ];

  return (
    <PageShell>
      <PageHero
        eyebrow="Occupational Taxonomy"
        title="Explore careers by field"
        copy="Browse career fields to compare how AI Exposure and Replacement Risk differ across types of work."
      />

      <main className="page-main" id="main-content">
        <div className="container">
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          <section aria-labelledby="directory-overview-heading" style={{ marginBottom: "36px" }}>
            <h2 id="directory-overview-heading" className="sr-only">
              Canonical Career Fields Directory
            </h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "24px",
              }}
            >
              {fieldsWithAnalytics.map(({ field, analytics }) => {
                const expSem = getScoreSemantics("ai_exposure", analytics.medianAiExposure);
                const riskSem = getScoreSemantics("replacement_risk", analytics.medianReplacementRisk);

                return (
                  <article
                    key={field.slug}
                    className="card"
                    style={{
                      padding: "24px 28px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      transition: "transform 0.15s ease, border-color 0.15s ease",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "8px" }}>
                        <span className="chip" style={{ fontSize: "0.74rem" }}>
                          {analytics.verifiedCount} verified {analytics.verifiedCount === 1 ? "job" : "jobs"}
                        </span>
                        <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                          {analytics.riskDistribution.low} safe roles
                        </span>
                      </div>

                      <h3 style={{ fontSize: "1.25rem", margin: "4px 0 8px" }}>
                        <Link
                          href={`/careers/${field.slug}`}
                          style={{ color: "var(--ink)", textDecoration: "none" }}
                        >
                          {field.name}
                        </Link>
                      </h3>

                      <p style={{ fontSize: "0.9rem", color: "var(--text)", lineHeight: 1.55, margin: "0 0 20px" }}>
                        {field.tagline}
                      </p>
                    </div>

                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "12px 14px",
                          background: "var(--soft)",
                          borderRadius: "var(--radius-xs)",
                          marginBottom: "16px",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700 }}>
                            Median Risk
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "2px" }}>
                            <strong style={{ fontSize: "1.1rem", color: "var(--ink)" }}>
                              {Math.round(analytics.medianReplacementRisk)}
                            </strong>
                            <span className={riskSem.badgeClass} style={{ fontSize: "0.7rem", padding: "1px 6px" }}>
                              {riskSem.shortLabel}
                            </span>
                          </div>
                        </div>

                        <div style={{ width: "1px", height: "24px", background: "var(--line)" }} />

                        <div>
                          <div style={{ fontSize: "0.72rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700 }}>
                            Median Exposure
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "2px" }}>
                            <strong style={{ fontSize: "1.1rem", color: "var(--ink)" }}>
                              {Math.round(analytics.medianAiExposure)}
                            </strong>
                            <span className={expSem.badgeClass} style={{ fontSize: "0.7rem", padding: "1px 6px" }}>
                              {expSem.shortLabel}
                            </span>
                          </div>
                        </div>
                      </div>

                      <Link
                        href={`/careers/${field.slug}`}
                        className="button secondary small"
                        style={{ width: "100%", justifyContent: "center" }}
                      >
                        Explore {field.shortName} Careers →
                      </Link>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          {/* Quick Cross-Navigation Links */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "16px",
              padding: "24px 0 36px",
            }}
          >
            <Link className="button secondary" href="/rankings">
              ← View Full Economy Rankings
            </Link>
            <Link className="button secondary" href="/career-fit">
              Take Career Fit Assessment →
            </Link>
          </div>
        </div>
      </main>
    </PageShell>
  );
}
