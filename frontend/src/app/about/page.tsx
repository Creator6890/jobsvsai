import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "About JobsVsAI — Evidence-Based AI Career Risk Research",
  description:
    "Learn how JobsVsAI provides evidence-based career intelligence for the AI era. Task-level analysis, verified scoring standards, and calm career navigation.",
  openGraph: {
    title: "About JobsVsAI — Evidence-Based AI Career Risk Research",
    description:
      "The intelligence layer for navigating your career through AI. Task-level evidence, transparent methodology, and actionable outcomes.",
  },
};

export default function AboutPage() {
  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Our Mission & Standards"
        title={
          <>
            AI is changing work.
            <br />
            People need an evidence layer.
          </>
        }
        copy="JobsVsAI measures how artificial intelligence is reshaping occupational tasks, helping professionals understand what is vulnerable, what remains uniquely human, and where to move next."
      />
      <main id="main-content">
        {/* Core Narrative */}
        <section className="content-section">
          <div className="container two-column editorial">
            <div>
              <div className="section-kicker">The Problem</div>
              <h2>Career decisions need more than dramatic headlines</h2>
              <p>
                Most public discussion around AI and employment swings between tech-utopian optimism and sensational doom. Neither extreme helps an individual professional decide whether to specialize, retrain, adopt new tools, or transition careers.
              </p>
              <p>
                Broad predictions based on job titles alone ignore how work actually happens. Two occupations with similar titles can have completely different task compositions, physical demands, and regulatory environments.
              </p>
            </div>
            <div>
              <div className="section-kicker">Our Approach</div>
              <h2>Evidence first. Action second.</h2>
              <p>
                We believe career intelligence must be grounded in task-level evidence rather than speculation. We decompose occupations into discrete work activities from O*NET 30.3, evaluate those activities against verified AI capability benchmarks, and apply structural modifiers for physical reality, human dependency, and adoption economics.
              </p>
              <p>
                A high score is a signal to adapt, not a prediction of unemployment. Our mission is to help people make informed career moves with confidence.
              </p>
            </div>
          </div>
        </section>

        {/* Purpose Banner */}
        <section className="section section-tint">
          <div className="container purpose-card" style={{ textAlign: "center", padding: "40px 24px" }}>
            <div className="section-kicker">Core Philosophy</div>
            <h2 style={{ fontSize: "2rem", marginTop: "10px", marginBottom: "16px" }}>
              Know what AI can change.
              <br />
              <span className="accent" style={{ color: "var(--violet)" }}>
                Know what you can do next.
              </span>
            </h2>
            <p style={{ maxWidth: "680px", margin: "0 auto", fontSize: "1.05rem", lineHeight: 1.6, color: "var(--muted)" }}>
              JobsVsAI is career decision infrastructure—not a fear calculator. We provide the intelligence layer for navigating modern work.
            </p>
          </div>
        </section>

        {/* Published Standards */}
        <section className="content-section">
          <div className="container">
            <div className="section-kicker">Integrity &amp; Research Standards</div>
            <div className="section-head">
              <div>
                <h2>The principles guiding our research</h2>
                <p>How we ensure independence, reproducibility, and rigorous disclosure.</p>
              </div>
            </div>

            <div className="factor-grid" style={{ marginTop: "24px" }}>
              <article className="card factor-card">
                <strong>01</strong>
                <h3>Evidence before inference</h3>
                <p>Every score originates from validated task statements, not high-level impressions of an occupation&apos;s prestige or title.</p>
              </article>

              <article className="card factor-card">
                <strong>02</strong>
                <h3>No pay-to-rank</h3>
                <p>Scores, rankings, and career comparisons are 100% algorithmic and independent of commercial advertisers or corporate sponsors.</p>
              </article>

              <article className="card factor-card">
                <strong>03</strong>
                <h3>Limitations published</h3>
                <p>Where proxy models are used or evidence coverage is partial, confidence scores and provisional shares are disclosed openly.</p>
              </article>

              <article className="card factor-card">
                <strong>04</strong>
                <h3>Uncertainty shown</h3>
                <p>Preliminary estimates are displayed as ranges rather than fake precision points, and excluded from headline rankings.</p>
              </article>

              <article className="card factor-card">
                <strong>05</strong>
                <h3>Traceable sources</h3>
                <p>Data connects directly to O*NET 30.3 classifications and our published Frontier AI Capability Index.</p>
              </article>

              <article className="card factor-card">
                <strong>06</strong>
                <h3>Actionable outcomes</h3>
                <p>Every risk assessment is paired with human advantage highlights, action plans, and realistic career transition paths.</p>
              </article>
            </div>
          </div>
        </section>
      </main>
    </PageShell>
  );
}
