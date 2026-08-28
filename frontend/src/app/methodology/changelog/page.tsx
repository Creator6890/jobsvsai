import type { Metadata } from "next";
import Link from "next/link";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "Methodology Changelog & Version History",
  description:
    "Public analytical version history and methodological updates for the JobsVsAI scoring pipeline, taxonomy revisions, and calibration snapshots.",
  alternates: {
    canonical: "https://jobsvsai.com/methodology/changelog",
  },
  openGraph: {
    title: "Methodology Changelog & Version History | JobsVsAI",
    description:
      "Public record of analytical methodology releases, capability taxonomy updates, and estimation frameworks in JobsVsAI.",
    url: "https://jobsvsai.com/methodology/changelog",
  },
};

const RELEASES = [
  {
    version: "Preliminary Estimate Methodology — 2026 Q3",
    date: "August 2026",
    summary:
      "Introduced a transparent, multi-tiered estimation methodology to provide provisional AI exposure and replacement risk indicators for 390 occupations undergoing full task analysis.",
    whatChanged: [
      "Deployed three-tier estimation framework: E1 (point estimates from high task coverage), E2 (bounded range intervals from partial task coverage), and E3 — related-occupation proxy estimates derived from the closest fully analysed occupations supported by O*NET relationships.",
      "Explicitly separated Preliminary estimates from Verified analyses across all public interfaces and sitemaps.",
      "Established strict evidence-basis disclosures and confidence interval boundaries.",
    ],
    whyChanged:
      "To provide users with directional career clarity across hundreds of searchable occupations while preserving strict methodological integrity and preventing provisional estimates from being mistaken for validated task analyses.",
    affectedScope: "390 preliminary occupation estimates published; 507 Verified scores remained completely unaltered.",
    status: "Active Production",
  },
  {
    version: "Multi-Factor Occupational Scoring Model — 2026 Q3",
    date: "July 2026",
    summary:
      "Launched the production multi-factor scoring architecture, evaluating occupational tasks across 15 capability dimensions with geometric bottleneck modeling and four structural friction layers.",
    whatChanged: [
      "Expanded capability evaluation from linear proximity to 15 discrete structural dimensions spanning cognitive, perceptual, physical, and governance domains.",
      "Implemented weighted geometric mean aggregation with critical bottleneck caps to prevent cognitive strengths from masking physical or legal impossibilities.",
      "Integrated four structural friction layers: Environmental & Physical Dependency, Human Accountability & Trust, Adoption Economics, and Labour-Market Resilience.",
    ],
    whyChanged:
      "Task automation cannot be modeled as a simple linear average; specialized physical requirements, legal liability, and economic friction represent real-world barriers that separate software capability from actual human displacement.",
    affectedScope: "507 verified occupations published under the versioned scoring pipeline.",
    status: "Active Production Baseline",
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
        copy="A public historical record of analytical model updates, capability taxonomy revisions, and estimation framework releases."
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
                      Key Methodological Changes
                    </h3>
                    <ul style={{ listStyle: "disc", paddingLeft: "20px", fontSize: "0.88rem", lineHeight: 1.6, margin: 0 }}>
                      {rel.whatChanged.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </div>

                  <div style={{ background: "var(--soft)", padding: "18px 20px", borderRadius: "var(--radius-xs)" }}>
                    <h3 style={{ fontSize: "0.88rem", fontWeight: 750, color: "var(--violet)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "8px" }}>
                      Rationale &amp; Analytical Scope
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
