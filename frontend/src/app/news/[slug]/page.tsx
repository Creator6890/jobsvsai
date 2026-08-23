import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHero, PageShell } from "@/components/PageShell";
import { NewsImpactBadge } from "@/components/NewsImpactBadge";
import { getNewsArticle } from "@/lib/api";

export const dynamic = "force-dynamic";

function formatDate(value: string | null): string {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", { dateStyle: "long" }).format(new Date(value));
}

export async function generateMetadata({ params }: PageProps<"/news/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const article = await getNewsArticle(slug);
  if (!article) return { title: "Article not found" };
  // The brief's own opening is the description: it is JobsVsAI prose, so there is no risk
  // of putting a source publication's sentence into our metadata.
  const description = article.whatHappened.slice(0, 200);
  return {
    title: article.headline,
    description,
    alternates: { canonical: `/news/${article.slug}` },
    openGraph: {
      title: article.headline,
      description,
      type: "article",
      publishedTime: article.publishedAt ?? undefined,
    },
  };
}

export default async function NewsArticlePage({ params }: PageProps<"/news/[slug]">) {
  const { slug } = await params;
  const article = await getNewsArticle(slug);
  if (!article) notFound();

  const source = article.primarySource;
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

  // NewsArticle JSON-LD carrying only fields we actually hold. Deliberately omitted:
  //   * `image` — the site OG image is not this article's image, and asserting it would be
  //     a claim about content we do not have. Rich-result eligibility needs a real
  //     per-article image; that is a content decision, not a markup one.
  //   * `dateModified` — the public payload does not expose updatedAt, and inferring it
  //     from publishedAt would state something we have not checked.
  // `isBasedOn` points at the source we summarised, which is the honest relationship:
  // JobsVsAI wrote this brief about that reporting, and did not reproduce it.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: article.headline,
    description: article.whatHappened,
    articleSection: "AI News",
    mainEntityOfPage: { "@type": "WebPage", "@id": `${origin}/news/${article.slug}` },
    ...(article.publishedAt ? { datePublished: article.publishedAt } : {}),
    ...(article.tags.length ? { keywords: article.tags.join(", ") } : {}),
    author: { "@type": "Organization", name: "JobsVsAI", url: origin },
    publisher: { "@type": "Organization", name: "JobsVsAI", url: origin },
    ...(source ? { isBasedOn: source.sourceUrl } : {}),
  };

  return (
    <PageShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <PageHero eyebrow="AI News" title={article.headline}>
        <NewsImpactBadge level={article.impactLevel} />
      </PageHero>
      <main className="page-main">
        <div className="container news-article">
          {source && (
            <p className="news-source-line">
              Source: <strong>{source.sourceName}</strong>
              {source.sourcePublishedAt && <> · {formatDate(source.sourcePublishedAt)}</>}
            </p>
          )}

          <section className="content-section">
            <div className="section-kicker">What happened</div>
            <p>{article.whatHappened}</p>
          </section>

          <section className="content-section">
            <div className="section-kicker">Why it matters for jobs</div>
            <p>{article.whyItMattersForJobs}</p>
          </section>

          {article.jobAreas.length > 0 && (
            <section className="content-section">
              <div className="section-kicker">Affected areas</div>
              <div className="news-areas">
                {article.jobAreas.map((area) => <span className="chip" key={area}>{area}</span>)}
              </div>
            </section>
          )}

          {article.tags.length > 0 && (
            <section className="content-section">
              <div className="section-kicker">Tags</div>
              <div className="news-areas">
                {article.tags.map((tag) => <span className="chip" key={tag}>{tag}</span>)}
              </div>
            </section>
          )}

          {/* JobsVsAI never republishes a source article. The brief above is original; this
              link is how a reader reaches the reporting it describes. */}
          {source && (
            <p className="news-source-link">
              <a href={source.sourceUrl} target="_blank" rel="noopener noreferrer nofollow">
                Read original source <span aria-hidden="true">→</span>
              </a>
              <small>{source.originalTitle} — {source.sourceName}</small>
            </p>
          )}

          {article.publishedAt && (
            <p className="news-published">
              Published by JobsVsAI on <time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time>
            </p>
          )}

          <p className="news-disclaimer">
            Jobs Impact is a news-significance indicator for this development. It is not an
            occupation score, and it does not change any occupation&rsquo;s AI Exposure or
            Replacement Risk. <Link href="/methodology">See the methodology</Link>.
          </p>
        </div>
      </main>
    </PageShell>
  );
}
