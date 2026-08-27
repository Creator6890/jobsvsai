import type { Metadata } from "next";
import Link from "next/link";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "Methodology Changelog & Version History",
  description:
    "Public version history and methodological updates for the JobsVsAI scoring pipeline, taxonomy revisions, and calibration snapshots.",
  alternates: {
    canonical: "https://jobsvsai.com/methodology/changelog",
  },
  openGraph: {
    title: "Methodology Changelog & Version History | JobsVsAI",
    description:
      "Historical record of methodological releases, calibration adjustments, and taxonomy upgrades in the JobsVsAI career intelligence platform.",
    url: "https://jobsvsai.com/methodology/changelog",
  },
};

const RELEASES = [
  {
    version: "2026 Q3 — Direction-Aware Semantic System",
    date: "August 2026",
    summary:
      "Implemented direction-aware semantic visual layers to clearly distinguish adverse risk metrics (higher score = greater exposure/risk) from protective capability metrics (higher score = greater human resilience).",
    whatChanged: [
      "Explicit direction classification across 10 distinct metric types.",
      "Calibrated 3-tier boundary thresholds [0–33 low/weak, 34–66 moderate, 67–100 high/strong].",
      "Added percentile population ranks on verified occupation analyses.",
    ],
    whyChanged:
      "Usability research showed users occasionally misread protective metrics (e.g. Human Dependency) under a universal high=danger mental model.",
    affectedScope: "All public score cards, comparison views, rankings, and transition recommendations.",
    status: "Active Production",
  },
  {
    version: "2026 Q3 — Multi-Factor Calibration & Proxy Pipeline",
    date: "July 2026",
    summary:
      "Completed Phase 4 multi-factor calibration, introducing the 15-dimension capability taxonomy, geometric bottleneck caps, and provisional proxy estimation framework (E1, E2, E3).",
    whatChanged: [
      "Upgraded baseline capability evaluation to 15 discrete structural dimensions.",
      "Introduced geometric mean aggregation to prevent high cognitive scores from averaging away physical bottlenecks.",
      "Deployed three-tier preliminary estimation framework covering 390 unverified occupations.",
    ],
    whyChanged:
      "Linear score aggregation previously underestimated the barrier posed by specialized physical, legal, and stakeholder requirements.",
    affectedScope: "507 verified occupations recalculated; 390 preliminary estimates generated.",
    status: "Active Production Snapshot",
  },
  {
    version: "2026 Q1 — Initial Ingestion Baseline",
    date: "March 2026",
    summary:
      "Initial production baseline ingesting O*NET 30.3 task statements, importance and frequency weights, and initial AI capability proximity assessments.",
    whatChanged: [
      "Parsed and weighted 8,218 occupation task statements from O*NET 30.3.",
      "Established foundational AI Exposure and Replacement Risk two-score separation.",
    ],
    whyChanged:
      "Established initial evidence-based dataset separating software capability from economic human replacement.",
    affectedScope: "Foundational verified cohort.",
    status: "Archived Baseline",
  },
];

export default function MethodologyChangelogPage() {
  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Methodology", item: "/methodology" },
    { name: "Changelog", item: "/methodology/changelog" },
  ];

  return (
    <PageShell>
      <PageHero
        eyebrow="Version History"
        title="JobsVsAI methodology changelog"
        copy="A public historical record of model updates, taxonomy revisions, calibration milestones, and scoring snapshot releases."
      />

      <main className="page-main" id="main-content">
        <div className="container">
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          <div className="card" style={{ padding: "16px 24px", marginBottom: "32px", display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--ink)" }}>Methodology Navigation</span>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
              <Link className="text-link" href="/methodology">
                ← Plain-Language Overview
              </Link>
              <Link className="text-link" href="/methodology/technical">
                Technical Methodology →
              </Link>
            </div>
          </div>

          <div className="changelog-stack" style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
            {RELEASES.map((rel) => (
              <article className="card" key={rel.version} style={{ padding: "32px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", flexWrap: "wrap", borderBottom: "1px solid var(--line)", paddingBottom: "16px", marginBottom: "20px" }}>
                  <div>
                    <h2 style={{ fontSize: "1.25rem", margin: 0, color: "var(--ink)" }}>{rel.version}</h2>
                    <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>{rel.date}</span>
                  </div>
                  <span className="chip safe" style={{ fontSize: "0.78rem" }}>
                    {rel.status}
                  </span>
                </div>

                <p style={{ fontSize: "1rem", lineHeight: 1.65, color: "var(--ink)", marginBottom: "20px" }}>
                  {rel.summary}
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
                  <div style={{ background: "var(--soft)", padding: "18px 20px", borderRadius: "var(--radius-xs)" }}>
                    <h3 style={{ fontSize: "0.88rem", fontWeight: 750, color: "var(--violet)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "8px" }}>
                      Key Changes
                    </h3>
                    <ul style={{ listStyle: "disc", paddingLeft: "20px", fontSize: "0.88rem", lineHeight: 1.6, margin: 0 }}>
                      {rel.whatChanged.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </div>

                  <div style={{ background: "var(--soft)", padding: "18px 20px", borderRadius: "var(--radius-xs)" }}>
                    <h3 style={{ fontSize: "0.88rem", fontWeight: 750, color: "var(--violet)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "8px" }}>
                      Rationale &amp; Scope
                    </h3>
                    <p style={{ fontSize: "0.88rem", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                      <strong>Why: </strong>{rel.whyChanged}
                    </p>
                    <p style={{ fontSize: "0.88rem", lineHeight: 1.6, margin: 0 }}>
                      <strong>Scope: </strong>{rel.affectedScope}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div style={{ marginTop: "36px", textAlign: "center" }}>
            <Link className="button secondary" href="/methodology">
              ← Return to Plain-Language Methodology
            </Link>
          </div>
        </div>
      </main>
    </PageShell>
  );
}
