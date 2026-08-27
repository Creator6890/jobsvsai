import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";
import { CareerFitApp } from "@/components/careerFit/CareerFitApp";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI-Safe Career Finder: Find Careers That Fit Your Strengths",
  description:
    "Career safety alone is not enough. JobsVsAI combines your work strengths, preferences, and style with career fit and verified AI resilience metrics.",
  alternates: {
    canonical: "https://jobsvsai.com/career-fit",
  },
  openGraph: {
    title: "AI-Safe Career Finder: Find Careers That Fit Your Strengths | JobsVsAI",
    description:
      "Discover careers that align with your work strengths and preferences, paired with verified AI Exposure and Replacement Risk scores.",
    url: "https://jobsvsai.com/career-fit",
  },
};

export default async function CareerFitPage() {
  const occupations = await getOccupations();

  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Career Fit Assessment"
        title="Find careers that fit you — and the AI era"
        copy="Career safety alone is not enough. JobsVsAI combines your strengths, preferences and work style with career fit and AI resilience to identify realistic paths worth exploring."
      />
      <main className="page-main" id="main-content">
        <CareerFitApp occupations={occupations} />

        <div className="container">
          <section className="section" aria-labelledby="career-fit-faq-heading" style={{ marginTop: "40px" }}>
            <div className="section-kicker">Assessment FAQ</div>
            <h2 id="career-fit-faq-heading">Frequently Asked Questions</h2>
            <div className="faq-stack" style={{ marginTop: "20px" }}>
              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Why doesn&apos;t JobsVsAI simply recommend the careers with the lowest AI risk?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  Low AI risk is meaningless if the day-to-day work contradicts your strengths, cognitive style, and personal interests. A sustainable career strategy requires finding occupations where you can excel personally while remaining structurally resilient against automation.
                </p>
              </details>

              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  How are Career Fit scores calculated?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  The assessment measures your profile across 8 core dimensions (Analytical Thinking, Creative Problem Solving, Interpersonal Collaboration, Physical &amp; Practical Execution, Structural Organization, Technological Systems, Domain Specialization, and Ambiguity Navigation). This profile is geometrically matched against verified O*NET occupational vectors to derive normalized 10–99 Fit scores.
                </p>
              </details>

              <details className="card faq-item" style={{ padding: "18px 24px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  Are all recommendations verified?
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  Yes. Recommendations are generated exclusively across our 507 verified occupations with full task-level analysis and validated scoring.
                </p>
              </details>
            </div>
          </section>
        </div>
      </main>
    </PageShell>
  );
}
