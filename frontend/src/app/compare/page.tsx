import type { Metadata } from "next";
import Link from "next/link";
import { CompareSelector } from "@/components/CompareSelector";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Compare Careers by AI Risk, Exposure & Resilience | JobsVsAI",
  description:
    "Compare two careers side by side across AI Exposure, Replacement Risk, human dependency, physical constraints, and long-term resilience.",
  openGraph: {
    title: "Compare Careers by AI Risk, Exposure & Resilience | JobsVsAI",
    description:
      "Transparent side-by-side AI career comparisons. Compare AI Exposure and Replacement Risk across verified occupations.",
  },
};

const CURATED_COMPARISONS = [
  { a: "accountant", b: "advertising-sales-agents", label: "Accountant vs Advertising Sales Agents" },
  { a: "software-developer", b: "data-scientists", label: "Software Developer vs Data Scientists" },
  { a: "registered-nurse", b: "medical-assistant", label: "Registered Nurse vs Medical Assistant" },
  { a: "graphic-designer", b: "web-developers", label: "Graphic Designer vs Web Developers" },
  { a: "financial-analyst", b: "accountant", label: "Financial Analyst vs Accountant" },
  { a: "customer-service-representatives", b: "sales-representatives-wholesale-and-manufacturing", label: "Customer Service vs Sales Representatives" },
];

export default async function ComparePage() {
  const occupations = await getOccupations();
  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Side-by-Side Analysis"
        title="Compare two careers in the age of AI"
        copy="Compare AI Exposure, Replacement Risk, human advantage, and structural career resilience side by side across verified occupations."
      />
      <main className="page-main" id="main-content">
        <div className="container">
          <CompareSelector occupations={occupations} />

          <div className="compare-empty" style={{ marginTop: "24px" }}>
            <span className="vs-badge">VS</span>
            <h2>Choose any two careers to see the full evidence comparison</h2>
            <p style={{ maxWidth: "600px", margin: "10px auto 0", lineHeight: 1.6 }}>
              We keep technical task exposure separate from real-world replacement risk, so you can see where AI assists work versus where it threatens human employment.
            </p>
          </div>

          {/* Curated comparisons */}
          <section className="section" aria-labelledby="curated-comparisons-title" style={{ marginTop: "40px" }}>
            <div className="section-kicker">Popular Comparisons</div>
            <h2 id="curated-comparisons-title">Common career path comparisons</h2>
            <div className="career-grid" style={{ marginTop: "18px" }}>
              {CURATED_COMPARISONS.map((pair) => (
                <article className="card" key={`${pair.a}-vs-${pair.b}`} style={{ padding: "18px 22px" }}>
                  <h3 style={{ fontSize: "1.05rem", marginBottom: "8px" }}>{pair.label}</h3>
                  <Link className="text-link" href={`/compare/${pair.a}-vs-${pair.b}`}>
                    Compare these careers →
                  </Link>
                </article>
              ))}
            </div>
          </section>

          {/* FAQ */}
          <section className="section" aria-labelledby="compare-faq-heading" style={{ marginTop: "32px" }}>
            <div className="section-kicker">Comparison FAQ</div>
            <h2 id="compare-faq-heading">How comparisons work</h2>
            <div className="faq-stack" style={{ marginTop: "20px" }}>
              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  How does JobsVsAI determine which career has the advantage?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  Advantage is direction-aware: for adverse metrics (AI Exposure, Replacement Risk, Adoption Pressure), the occupation with the LOWER score has the advantage. For protective metrics (Human Dependency, Physical Dependency, Labour-Market Resilience), the occupation with the HIGHER score has the advantage.
                </p>
              </details>
              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Can I compare any occupation on the site?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  Full multi-factor comparisons are supported across all verified occupations with complete task ratings. Preliminary estimates are evaluated individually on their dedicated pages.
                </p>
              </details>
            </div>
          </section>
        </div>
      </main>
    </PageShell>
  );
}
