import type { Metadata } from "next";
import Link from "next/link";
import { PageHero, PageShell } from "@/components/PageShell";
import { NewsImpactBadge } from "@/components/NewsImpactBadge";
import { AdSlot } from "@/components/AdSlot";
import { getNewsArticles, type NewsImpactLevel } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI News: Workplace Developments & Job Impact | JobsVsAI",
  description: "AI developments and capability shifts assessed for their real-world occupational impact.",
  alternates: { canonical: "https://jobsvsai.com/news" },
  robots: {
    index: false,
    follow: true,
  },
};

const FILTERS = [
  ["All", undefined],
  ["High impact", "high"],
  ["Medium impact", "medium"],
  ["Low impact", "low"],
] as const;

function formatDate(value: string | null): string {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

export default async function NewsPage({ searchParams }: { searchParams: Promise<{ impact?: string }> }) {
  const { impact } = await searchParams;
  // Filtering happens server-side through the API so the list is never filtered from a
  // payload larger than the one displayed.
  const active = (["low", "medium", "high"] as const).find((level) => level === impact);
  const articles = await getNewsArticles(active as NewsImpactLevel | undefined);

  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="JobsVsAI Newsroom"
        title="Latest AI developments — and what they mean for jobs."
        copy="Every story answers the same three questions: what happened, why it matters for jobs, and how significant it is for work."
      />
      <main className="page-main">
        <div className="container">
          <div className="filter-panel">
            <div className="tab-list" role="tablist" aria-label="Filter by jobs impact">
              {FILTERS.map(([label, value]) => {
                const isActive = value === active || (!value && !active);
                return (
                  <Link
                    key={label}
                    role="tab"
                    aria-selected={isActive}
                    className={isActive ? "active" : ""}
                    href={value ? `/news?impact=${value}` : "/news"}
                  >{label}</Link>
                );
              })}
            </div>
          </div>

          {articles.length === 0 ? (
            <div className="empty-state">
              {active ? `No ${active}-impact stories published yet.` : "No stories published yet."}
            </div>
          ) : (
            <div className="news-grid">
              {articles.slice(0, 4).map((article) => (
                <article className="card news-card" key={article.slug}>
                  <NewsImpactBadge level={article.impactLevel} />
                  <h2><Link href={`/news/${article.slug}`}>{article.headline}</Link></h2>
                  <p>{article.whatHappened}</p>
                  {article.jobAreas.length > 0 && (
                    <div className="news-areas">
                      {article.jobAreas.map((area) => <span className="chip" key={area}>{area}</span>)}
                    </div>
                  )}
                  <footer className="news-meta">
                    {/* Source name and the source's own publication date, when the source
                        supplied one. Never a date we inferred: an absent source date is
                        left absent rather than substituted with ours. */}
                    {article.primarySource && (
                      <span>
                        {article.primarySource.sourceName}
                        {article.primarySource.sourcePublishedAt && (
                          <> · <time dateTime={article.primarySource.sourcePublishedAt}>
                            {formatDate(article.primarySource.sourcePublishedAt)}
                          </time></>
                        )}
                      </span>
                    )}
                    {article.publishedAt && (
                      <time dateTime={article.publishedAt} title="JobsVsAI publication date">
                        {formatDate(article.publishedAt)}
                      </time>
                    )}
                  </footer>
                </article>
              ))}
              {articles.length > 4 && <AdSlot slot="newsList" format="horizontal" className="ad-slot-news-list" />}
              {articles.slice(4).map((article) => (
                <article className="card news-card" key={article.slug}>
                  <NewsImpactBadge level={article.impactLevel} />
                  <h2><Link href={`/news/${article.slug}`}>{article.headline}</Link></h2>
                  <p>{article.whatHappened}</p>
                  {article.jobAreas.length > 0 && (
                    <div className="news-areas">
                      {article.jobAreas.map((area) => <span className="chip" key={area}>{area}</span>)}
                    </div>
                  )}
                  <footer className="news-meta">
                    {/* Source name and the source's own publication date, when the source
                        supplied one. Never a date we inferred: an absent source date is
                        left absent rather than substituted with ours. */}
                    {article.primarySource && (
                      <span>
                        {article.primarySource.sourceName}
                        {article.primarySource.sourcePublishedAt && (
                          <> · <time dateTime={article.primarySource.sourcePublishedAt}>
                            {formatDate(article.primarySource.sourcePublishedAt)}
                          </time></>
                        )}
                      </span>
                    )}
                    {article.publishedAt && (
                      <time dateTime={article.publishedAt} title="JobsVsAI publication date">
                        {formatDate(article.publishedAt)}
                      </time>
                    )}
                  </footer>
                </article>
              ))}
            </div>
          )}
        </div>
      </main>
    </PageShell>
  );
}
