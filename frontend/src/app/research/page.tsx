import type { Metadata } from "next";
import Link from "next/link";
import { getAllResearchArticles } from "@/lib/researchArticles";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "AI Jobs Research: Automation, Job Risk & Future Careers",
  description:
    "Evidence-led research, data findings, and explainers on AI exposure, occupational replacement risk, and career resilience from JobsVsAI.",
  alternates: {
    canonical: "https://jobsvsai.com/research",
  },
  openGraph: {
    title: "AI Jobs Research: Automation, Job Risk & Future Careers | JobsVsAI",
    description:
      "Evidence-led research, data findings, and explainers on AI exposure, occupational replacement risk, and career resilience from JobsVsAI.",
    url: "https://jobsvsai.com/research",
  },
};

export default function ResearchHubPage() {
  const articles = getAllResearchArticles();

  const clusters = [
    {
      id: "UNDERSTANDING AI RISK",
      title: "Understanding AI Risk",
      description: "Foundational frameworks separating task-level AI capability from economic job displacement.",
    },
    {
      id: "OCCUPATIONAL RESILIENCE",
      title: "Occupational Resilience",
      description: "Data-driven analyses of high-risk vulnerabilities and durable human strongholds across 507 verified occupations.",
    },
    {
      id: "CAREER DECISIONS",
      title: "Career Decisions",
      description: "Actionable strategies, workflow unbundling, and adaptation frameworks for workers navigating AI transitions.",
    },
  ];

  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Research", item: "/research" },
  ];

  return (
    <PageShell>
      <PageHero
        eyebrow="Intelligence & Analysis"
        title="AI & Jobs Research"
        copy="Evidence-led analysis and data findings exploring the mechanisms of AI automation, occupational friction, and the future of human work."
      />

      <main className="page-main" id="main-content">
        <div className="container">
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          {/* Research Intro Note */}
          <div className="card" style={{ padding: "28px 32px", marginBottom: "40px", background: "linear-gradient(135deg, #fbfaff, #fff)", borderColor: "var(--violet-soft)" }}>
            <span className="section-kicker">Research Grounding</span>
            <h2 style={{ fontSize: "1.25rem", margin: "6px 0 12px", color: "var(--ink)" }}>
              Data-backed analysis, not speculative headlines
            </h2>
            <p style={{ fontSize: "0.98rem", lineHeight: 1.65, color: "var(--text)", margin: 0 }}>
              JobsVsAI research investigates occupational transformation from the bottom up—grounded in 8,218 detailed task-to-capability mappings, 15 frontier AI dimensions, and multi-factor structural friction models across the US economy.
            </p>
          </div>

          {/* Thematic Clusters */}
          {clusters.map((cluster) => {
            const clusterArticles = articles.filter((a) => a.cluster === cluster.id);
            if (clusterArticles.length === 0) return null;

            return (
              <section key={cluster.id} style={{ marginBottom: "48px" }}>
                <div style={{ marginBottom: "20px" }}>
                  <div className="section-kicker">{cluster.title}</div>
                  <h2 style={{ fontSize: "1.45rem", margin: "4px 0 6px", color: "var(--ink)" }}>
                    {cluster.title}
                  </h2>
                  <p style={{ fontSize: "0.92rem", color: "var(--muted)", margin: 0 }}>
                    {cluster.description}
                  </p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
                  {clusterArticles.map((article) => (
                    <article
                      key={article.slug}
                      className="card"
                      style={{
                        padding: "28px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        transition: "transform 0.15s ease, border-color 0.15s ease",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                          <span className="chip" style={{ fontSize: "0.75rem" }}>
                            {article.readTime}
                          </span>
                          <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                            Updated {new Date(article.dateModified).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
                          </span>
                        </div>

                        <h3 style={{ fontSize: "1.2rem", lineHeight: 1.35, margin: "0 0 12px" }}>
                          <Link href={`/research/${article.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                            {article.title}
                          </Link>
                        </h3>

                        <p style={{ fontSize: "0.92rem", lineHeight: 1.6, color: "var(--text)", margin: "0 0 20px" }}>
                          {article.description}
                        </p>
                      </div>

                      <div>
                        <Link
                          href={`/research/${article.slug}`}
                          className="button secondary small"
                          style={{ display: "inline-block" }}
                        >
                          Read Research Explainer →
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}

          {/* Quick Methodology Link */}
          <section className="card" style={{ padding: "28px", background: "var(--soft)", marginBottom: "40px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", margin: "0 0 4px", color: "var(--ink)" }}>
                  Looking for the underlying mathematical formulas?
                </h3>
                <p style={{ fontSize: "0.88rem", color: "var(--muted)", margin: 0 }}>
                  Explore our complete open scoring methodology and logistic capability equations.
                </p>
              </div>
              <Link className="button secondary" href="/methodology/technical">
                View Technical Methodology →
              </Link>
            </div>
          </section>
        </div>
      </main>
    </PageShell>
  );
}
