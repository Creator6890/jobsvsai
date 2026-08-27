import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";
import { AdSlot } from "@/components/AdSlot";
import { RankingsExplorer } from "@/components/RankingsExplorer";
import { getRankings } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI Job Risk Rankings: Jobs Most and Least at Risk From AI",
  description:
    "Compare occupations by AI Exposure and Replacement Risk across verified careers. Discover jobs most exposed to automation and careers built for long-term human resilience.",
  openGraph: {
    title: "AI Job Risk Rankings: Jobs Most and Least at Risk From AI | JobsVsAI",
    description:
      "Task-level AI Exposure and Replacement Risk rankings across 507 verified occupations. Evidence-led analysis from JobsVsAI.",
  },
};

export default async function RankingsPage() {
  const occupations = await getRankings();
  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Verified Cohort (507 Occupations)"
        title="AI Job Risk Rankings"
        copy="Compare occupations by AI Exposure and Replacement Risk. Exposure measures what AI can do; Replacement Risk estimates how much that capability threatens human labour demand after structural constraints."
      />
      <main className="page-main" id="main-content">
        <div className="container">
          <RankingsExplorer occupations={occupations} />

          {/* Rankings FAQ Section */}
          <section className="section" aria-labelledby="rankings-faq-heading" style={{ marginTop: "48px" }}>
            <div className="section-kicker">Rankings FAQ</div>
            <h2 id="rankings-faq-heading">Understanding the Rankings</h2>
            <div className="faq-stack" style={{ marginTop: "20px" }}>
              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Why are AI Exposure and Replacement Risk ranked separately?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  A job can have high AI Exposure because software tools can assist with its analytical or written tasks, yet have lower Replacement Risk due to high human dependency, required stakeholder trust, physical agility, or legal accountability.
                </p>
              </details>

              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Are preliminary estimates included in these headline rankings?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  No. In accordance with our trust policy, headline rankings include only fully verified occupations with complete task-level capability mapping. Preliminary estimates are published with explicit uncertainty ranges on their individual pages.
                </p>
              </details>

              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Does a high rank mean an occupation is doomed?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  No. A high ranking reflects structural pressure on how tasks are executed. It is a signal for professionals to integrate AI tools for routine tasks while focusing on high-judgment, supervisory, and interpersonal strengths.
                </p>
              </details>
            </div>
          </section>

          <AdSlot slot="rankings" format="horizontal" />
        </div>
      </main>
    </PageShell>
  );
}
