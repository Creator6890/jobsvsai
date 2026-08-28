import type { Metadata } from "next";
import Link from "next/link";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "Technical Methodology & Scoring Architecture",
  description:
    "Mathematical and structural specification of the JobsVsAI scoring pipeline: 15-factor capability taxonomy, bottleneck caps, task weighting, and proxy estimation.",
  alternates: {
    canonical: "https://jobsvsai.com/methodology/technical",
  },
  openGraph: {
    title: "Technical Methodology & Scoring Architecture | JobsVsAI",
    description:
      "Deep technical documentation of the JobsVsAI deterministic scoring pipeline, task weighting, geometric capability aggregation, and structural friction models.",
    url: "https://jobsvsai.com/methodology/technical",
  },
};

const CAPABILITY_DIMENSIONS = [
  {
    group: "Cognitive & Analytical",
    items: [
      "Complex Reasoning & Deduction",
      "Quantitative & Mathematical Computation",
      "Document & Data Synthesis",
      "Code & Algorithmic Generation",
      "Creative Pattern Synthesis",
    ],
  },
  {
    group: "Perceptual & Spatial",
    items: [
      "Visual Scene Recognition & Interpretation",
      "Spatial Awareness & Environmental Navigation",
      "Audio & Speech Processing",
      "Multi-Modal Sensor Integration",
    ],
  },
  {
    group: "Physical & Manipulation",
    items: [
      "Fine Motor Dexterity & Tool Operation",
      "Gross Motor Coordination & Physical Stamina",
      "Real-Time Physical Manipulation in Unstructured Settings",
    ],
  },
  {
    group: "Social, Emotional & Governance",
    items: [
      "Empathetic Interpersonal Communication",
      "High-Stakes Ethical & Strategic Judgement",
      "Accountability, Liability & Regulatory Governance",
    ],
  },
];

export default function TechnicalMethodologyPage() {
  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Methodology", item: "/methodology" },
    { name: "Technical Architecture", item: "/methodology/technical" },
  ];

  return (
    <PageShell>
      <PageHero
        eyebrow="Mathematical Specification"
        title="Technical Methodology & Scoring Architecture"
        copy="A detailed technical reference on our deterministic multi-factor pipeline, 15-dimension capability taxonomy, geometric bottleneck modeling, and structural constraint layers."
      />

      <main className="page-main" id="main-content">
        <div className="container">
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          <div
            className="methodology-subnav card"
            style={{
              padding: "16px 24px",
              marginBottom: "32px",
              display: "flex",
              gap: "20px",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--ink)" }}>
              Methodology Navigation
            </span>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
              <Link className="text-link" href="/methodology">
                ← Plain-Language Overview
              </Link>
              <Link className="text-link" href="/methodology/changelog">
                Public Methodology Changelog →
              </Link>
            </div>
          </div>

          <article className="prose-content">
            <section className="card" style={{ padding: "32px", marginBottom: "28px" }}>
              <h2>1. The 15 AI Capability Dimensions</h2>
              <p>
                To avoid evaluating &ldquo;AI&rdquo; as a monolithic entity, JobsVsAI maps
                occupational workflows against fifteen discrete capability dimensions spanning four
                structural domains:
              </p>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "20px",
                  marginTop: "20px",
                }}
              >
                {CAPABILITY_DIMENSIONS.map((dim) => (
                  <div
                    key={dim.group}
                    style={{
                      background: "var(--soft)",
                      padding: "18px 20px",
                      borderRadius: "var(--radius-xs)",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "0.95rem",
                        fontWeight: 750,
                        color: "var(--violet)",
                        marginBottom: "10px",
                      }}
                    >
                      {dim.group}
                    </h3>
                    <ul
                      style={{
                        listStyle: "disc",
                        paddingLeft: "20px",
                        fontSize: "0.88rem",
                        lineHeight: 1.6,
                        margin: 0,
                      }}
                    >
                      {dim.items.map((it) => (
                        <li key={it}>{it}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>

            <section className="card" style={{ padding: "32px", marginBottom: "28px" }}>
              <h2>2. Task-Level Geometric Mean &amp; Bottleneck Caps</h2>
              <p>
                Standard linear averaging fails in occupational risk modeling because strong
                capability in text synthesis cannot compensate for zero dexterity in physical
                surgery.
              </p>
              <p>
                For every task \(T\), capability match across each dimension \(i\) is computed
                using a logistic capability margin curve against commercial AI frontier
                capabilities. Overall task capability fit is aggregated via a{" "}
                <strong>weighted geometric mean</strong> with critical bottleneck caps:
              </p>

              <div
                style={{
                  background: "var(--bg-warm, #f8f6fb)",
                  padding: "18px 24px",
                  borderRadius: "var(--radius-xs)",
                  margin: "20px 0",
                  fontFamily: "monospace",
                  fontSize: "0.92rem",
                  lineHeight: 1.6,
                }}
              >
                <div>{"Margin(i) = AI_Frontier(i) - Required_Level(i)"}</div>
                <div style={{ marginTop: "6px" }}>
                  {"Match(i) = 100 / (1 + exp(-Margin(i) / sigma))"}
                </div>
                <div style={{ marginTop: "8px" }}>
                  {"CapabilityFit(T) = min(BottleneckCap, exp(sum(w(i) * ln(max(Floor, Match(i))))))"}
                </div>
              </div>

              <p>
                <strong>Critical Bottleneck Caps:</strong> When a task requires high capability in a
                dimension where commercial AI exhibits a severe shortfall, a deterministic
                bottleneck cap is enforced, bounding the task score regardless of strength in other
                dimensions.
              </p>
            </section>

            <section className="card" style={{ padding: "32px", marginBottom: "28px" }}>
              <h2>3. Task Weighting and AI Exposure Aggregation</h2>
              <p>
                Individual task scores are aggregated into occupational headline scores using{" "}
                <strong>O*NET 30.3</strong> empirical weights. Each task statement is scaled by its
                surveyed importance and frequency across the verified occupation:
              </p>
              <div
                style={{
                  background: "var(--bg-warm, #f8f6fb)",
                  padding: "18px 24px",
                  borderRadius: "var(--radius-xs)",
                  margin: "20px 0",
                  fontFamily: "monospace",
                  fontSize: "0.92rem",
                  lineHeight: 1.6,
                }}
              >
                <div>{"Weight(T) = Importance(T) * Frequency(T)"}</div>
                <div style={{ marginTop: "8px" }}>
                  {"AI Exposure = sum(Weight(T) * CapabilityFit(T)) / sum(Weight(T))"}
                </div>
              </div>
            </section>

            <section className="card" style={{ padding: "32px", marginBottom: "28px" }}>
              <h2>4. Structural Friction &amp; Replacement Risk Modeling</h2>
              <p>
                AI Exposure and Replacement Risk diverge because technical capability is subject to
                real-world friction before human labour can be substituted. JobsVsAI combines
                task-level automation feasibility with four structural friction layers:
              </p>
              <ul style={{ listStyle: "disc", paddingLeft: "24px", lineHeight: 1.7, fontSize: "0.95rem" }}>
                <li>
                  <strong>Environmental &amp; Physical Dependency:</strong> Requirements for
                  physical presence, dexterity, tool handling, and unconstrained spatial navigation
                  in dynamic environments.
                </li>
                <li>
                  <strong>Human Accountability &amp; Trust:</strong> Legal liability, fiduciary
                  responsibility, ethical sign-off, patient/client rapport, and high-consequence
                  decision-making requiring an accountable human party.
                </li>
                <li>
                  <strong>Adoption Economics &amp; Integration Friction:</strong> Capital costs of
                  enterprise deployment, system integration complexity, regulatory compliance
                  timelines, and organizational workflow inertia.
                </li>
                <li>
                  <strong>Labour-Market Resilience:</strong> Macroeconomic workforce elasticity,
                  demographic shortages, institutional certification barriers, and wage dynamics.
                </li>
              </ul>
            </section>

            <section className="card" style={{ padding: "32px", marginBottom: "28px" }}>
              <h2>5. Preliminary Estimation Framework (E1, E2, E3)</h2>
              <p>
                For occupations that have not completed full individual task-level analysis,
                JobsVsAI produces provisional estimates bounded by empirical confidence tiers:
              </p>
              <div className="factor-grid" style={{ marginTop: "20px" }}>
                <div className="factor-card card" style={{ padding: "20px" }}>
                  <strong>E1</strong>
                  <h3 style={{ fontSize: "1rem", marginTop: "8px" }}>Point Estimate</h3>
                  <p style={{ fontSize: "0.88rem" }}>
                    High direct task coverage (&gt;80%) from mapped shared work activities.
                  </p>
                </div>
                <div className="factor-card card" style={{ padding: "20px" }}>
                  <strong>E2</strong>
                  <h3 style={{ fontSize: "1rem", marginTop: "8px" }}>Range Estimate</h3>
                  <p style={{ fontSize: "0.88rem" }}>
                    Partial task coverage (30%–80%) with bounded upper and lower uncertainty
                    intervals.
                  </p>
                </div>
                <div className="factor-card card" style={{ padding: "20px" }}>
                  <strong>E3</strong>
                  <h3 style={{ fontSize: "1rem", marginTop: "8px" }}>Cluster Proxy</h3>
                  <p style={{ fontSize: "0.88rem" }}>
                    Structural proxy mapping derived from nearest-neighbor verified occupational
                    clusters.
                  </p>
                </div>
              </div>
            </section>
          </article>

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
