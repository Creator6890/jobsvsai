import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAllResearchArticles,
  getResearchArticle,
} from "@/lib/researchArticles";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { PageHero, PageShell } from "@/components/PageShell";
import { getScoreSemantics } from "@/lib/scoreSemantics";

interface ResearchArticlePageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return getAllResearchArticles().map((a) => ({
    slug: a.slug,
  }));
}

export async function generateMetadata({ params }: ResearchArticlePageProps): Promise<Metadata> {
  const { slug } = await params;
  const article = getResearchArticle(slug);
  if (!article) return {};

  const title = article.seoTitle;
  const description = article.description;
  const url = `https://jobsvsai.com/research/${article.slug}`;

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
      type: "article",
      publishedTime: article.datePublished,
      modifiedTime: article.dateModified,
    },
  };
}

export default async function ResearchArticlePage({ params }: ResearchArticlePageProps) {
  const { slug } = await params;
  const article = getResearchArticle(slug);

  if (!article) {
    notFound();
  }

  const breadcrumbs = [
    { name: "Home", item: "/" },
    { name: "Research", item: "/research" },
    { name: article.title, item: `/research/${article.slug}` },
  ];

  const relatedArticles = article.relatedArticleSlugs
    .map((rSlug) => getResearchArticle(rSlug))
    .filter(Boolean);

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: article.headline,
    description: article.description,
    datePublished: article.datePublished,
    dateModified: article.dateModified,
    mainEntityOfPage: `https://jobsvsai.com/research/${article.slug}`,
    author: {
      "@type": "Organization",
      name: "JobsVsAI Research",
      url: "https://jobsvsai.com",
    },
    publisher: {
      "@type": "Organization",
      name: "JobsVsAI",
      logo: {
        "@type": "ImageObject",
        url: "https://jobsvsai.com/logo.png",
      },
    },
  };

  return (
    <PageShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />

      <PageHero
        eyebrow={article.clusterLabel}
        title={article.headline}
        copy={article.description}
      />

      <main className="page-main" id="main-content">
        <div className="container" style={{ maxWidth: "860px", margin: "0 auto" }}>
          <div style={{ paddingBottom: "24px" }}>
            <Breadcrumbs items={breadcrumbs} />
          </div>

          {/* Article Meta Strip */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
              paddingBottom: "24px",
              borderBottom: "1px solid var(--line)",
              marginBottom: "32px",
              fontSize: "0.85rem",
              color: "var(--muted)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
              <span>
                By <strong style={{ color: "var(--ink)" }}>JobsVsAI Research</strong>
              </span>
              <span>•</span>
              <span>{article.readTime}</span>
              <span>•</span>
              <span>
                Published {new Date(article.datePublished).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </span>
            </div>
            {article.dateModified !== article.datePublished && (
              <span className="chip" style={{ fontSize: "0.72rem" }}>
                Updated {new Date(article.dateModified).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
              </span>
            )}
          </div>

          {/* Direct Answer Box */}
          <article
            className="card"
            style={{
              padding: "28px 32px",
              marginBottom: "40px",
              background: "linear-gradient(135deg, #fbfaff, #fff)",
              borderColor: "var(--violet-soft)",
            }}
          >
            <span className="section-kicker">Direct Answer</span>
            <h2 style={{ fontSize: "1.25rem", margin: "6px 0 12px", color: "var(--ink)" }}>
              Summary & Key Takeaway
            </h2>
            <p style={{ fontSize: "1.05rem", lineHeight: 1.7, color: "var(--ink)", margin: 0, fontWeight: 500 }}>
              {article.shortAnswer}
            </p>
          </article>

          {/* Section 1: Evidence */}
          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "1.45rem", marginBottom: "16px", color: "var(--ink)" }}>
              {article.evidenceSection.heading}
            </h2>
            {article.evidenceSection.paragraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "1.02rem", lineHeight: 1.75, color: "var(--text)", marginBottom: "16px" }}>
                {p}
              </p>
            ))}
          </section>

          {/* Section 2: Mechanism / Why this happens */}
          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "1.45rem", marginBottom: "16px", color: "var(--ink)" }}>
              {article.mechanismSection.heading}
            </h2>
            {article.mechanismSection.paragraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "1.02rem", lineHeight: 1.75, color: "var(--text)", marginBottom: "16px" }}>
                {p}
              </p>
            ))}

            {article.mechanismSection.keyPoints && (
              <div style={{ display: "grid", gap: "16px", marginTop: "24px" }}>
                {article.mechanismSection.keyPoints.map((pt) => (
                  <div key={pt.title} className="card" style={{ padding: "20px", background: "var(--soft)" }}>
                    <h3 style={{ fontSize: "1rem", margin: "0 0 6px", color: "var(--violet)" }}>
                      {pt.title}
                    </h3>
                    <p style={{ fontSize: "0.92rem", lineHeight: 1.6, margin: 0, color: "var(--text)" }}>
                      {pt.text}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section 3: Affected Careers */}
          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "1.45rem", marginBottom: "16px", color: "var(--ink)" }}>
              {article.affectedCareersSection.heading}
            </h2>
            {article.affectedCareersSection.paragraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "1.02rem", lineHeight: 1.75, color: "var(--text)", marginBottom: "16px" }}>
                {p}
              </p>
            ))}

            <div style={{ display: "grid", gap: "16px", marginTop: "20px" }}>
              {article.affectedCareersSection.sampleOccupations.map((occ) => {
                const expSem = getScoreSemantics("ai_exposure", occ.exposure);
                const riskSem = getScoreSemantics("replacement_risk", occ.replacementRisk);

                return (
                  <div key={occ.slug} className="card" style={{ padding: "22px 24px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "8px", marginBottom: "10px" }}>
                      <h3 style={{ fontSize: "1.1rem", margin: 0 }}>
                        <Link href={`/jobs/${occ.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                          {occ.title} →
                        </Link>
                      </h3>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <span className={`score-badge ${riskSem.tone}`} title={riskSem.label}>
                          {occ.replacementRisk} Risk
                        </span>
                        <span className={`score-badge ${expSem.tone}`} title={expSem.label}>
                          {occ.exposure} Exposure
                        </span>
                      </div>
                    </div>
                    <p style={{ fontSize: "0.9rem", lineHeight: 1.6, margin: 0, color: "var(--text)" }}>
                      {occ.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Section 4: What this means for workers */}
          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "1.45rem", marginBottom: "16px", color: "var(--ink)" }}>
              {article.workerImpactSection.heading}
            </h2>
            {article.workerImpactSection.paragraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "1.02rem", lineHeight: 1.75, color: "var(--text)", marginBottom: "16px" }}>
                {p}
              </p>
            ))}

            {article.workerImpactSection.actionItems && (
              <div className="card" style={{ padding: "24px", marginTop: "20px", borderLeft: "4px solid var(--violet)" }}>
                <h3 style={{ fontSize: "1.02rem", margin: "0 0 12px", color: "var(--ink)" }}>
                  Practical Next Steps
                </h3>
                <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "10px" }}>
                  {article.workerImpactSection.actionItems.map((item, idx) => (
                    <li key={idx} style={{ fontSize: "0.92rem", lineHeight: 1.6, color: "var(--text)" }}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* Section 5: Limitations */}
          <section className="card" style={{ padding: "24px 28px", marginBottom: "40px", background: "var(--soft)" }}>
            <h2 style={{ fontSize: "1.1rem", marginBottom: "8px", color: "var(--ink)" }}>
              {article.limitationsSection.heading}
            </h2>
            {article.limitationsSection.paragraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "0.88rem", lineHeight: 1.6, color: "var(--muted)", margin: idx === article.limitationsSection.paragraphs.length - 1 ? 0 : "8px 0" }}>
                {p}
              </p>
            ))}
          </section>

          {/* Section 6: Sources and Methodology */}
          <section style={{ padding: "24px 0", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)", marginBottom: "40px" }}>
            <h3 style={{ fontSize: "0.95rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", marginBottom: "12px" }}>
              Data Sources & Methodology
            </h3>
            <p style={{ fontSize: "0.88rem", lineHeight: 1.6, color: "var(--text)", margin: "0 0 12px" }}>
              Data analyzed in this article is drawn from the JobsVsAI verified occupational dataset, evaluating 507 occupations, 8,218 O*NET tasks, and 15 frontier AI capability dimensions.
            </p>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "0.88rem" }}>
              <Link className="text-link" href="/methodology">
                Read Scoring Methodology →
              </Link>
              <Link className="text-link" href="/methodology/technical">
                View Technical Formulas →
              </Link>
              <Link className="text-link" href="/rankings">
                Explore Full 507 Rankings →
              </Link>
            </div>
          </section>

          {/* Section 7: Related Research */}
          {relatedArticles.length > 0 && (
            <section style={{ marginBottom: "48px" }}>
              <h2 style={{ fontSize: "1.3rem", marginBottom: "20px", color: "var(--ink)" }}>
                Related JobsVsAI Research
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "18px" }}>
                {relatedArticles.map((rel) => {
                  if (!rel) return null;
                  return (
                    <article key={rel.slug} className="card" style={{ padding: "20px" }}>
                      <span className="chip" style={{ fontSize: "0.72rem", marginBottom: "8px" }}>
                        {rel.clusterLabel}
                      </span>
                      <h3 style={{ fontSize: "1rem", margin: "6px 0 8px" }}>
                        <Link href={`/research/${rel.slug}`} style={{ color: "var(--ink)", textDecoration: "none" }}>
                          {rel.title}
                        </Link>
                      </h3>
                      <p style={{ fontSize: "0.84rem", color: "var(--muted)", margin: 0, lineHeight: 1.5 }}>
                        {rel.description}
                      </p>
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {/* Bottom Back Button */}
          <div style={{ textAlign: "center", paddingBottom: "32px" }}>
            <Link className="button secondary" href="/research">
              ← Back to All Research Explainers
            </Link>
          </div>
        </div>
      </main>
    </PageShell>
  );
}
