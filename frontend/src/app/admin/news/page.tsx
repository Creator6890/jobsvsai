import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminNewsArticles, getAdminNewsCounts, getNewsImpactPolicy, type NewsArticleStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

const QUEUES: { label: string; value: NewsArticleStatus }[] = [
  { label: "Draft", value: "draft" },
  { label: "Review required", value: "review_required" },
  { label: "Published", value: "published" },
  { label: "Rejected", value: "rejected" },
];

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value)) : "—";
}

export default async function AdminNewsPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status } = await searchParams;
  const active = QUEUES.find((queue) => queue.value === status)?.value;
  const [articles, counts, policy] = await Promise.all([
    getAdminNewsArticles(active),
    getAdminNewsCounts(),
    getNewsImpactPolicy(),
  ]);

  return (
    <AdminShell
      title="AI News"
      eyebrow="Editorial queue"
      modelVersion={policy.policyVersion}
      action={
        <Status tone={counts.review_required > 0 ? "warn" : "ok"}>
          {counts.review_required > 0 ? `${counts.review_required} awaiting review` : "Nothing awaiting review"}
        </Status>
      }
    >
      <div className="kpi-grid">
        {QUEUES.map((queue) => (
          <div className="card kpi" key={queue.value}>
            <span className="metric-label">{queue.label}</span>
            <strong>{counts[queue.value]}</strong>
          </div>
        ))}
      </div>

      <div className="admin-toolbar">
        <div className="tab-list" role="tablist" aria-label="Filter by status">
          <Link role="tab" aria-selected={!active} className={!active ? "active" : ""} href="/admin/news">All</Link>
          {QUEUES.map((queue) => (
            <Link
              key={queue.value}
              role="tab"
              aria-selected={active === queue.value}
              className={active === queue.value ? "active" : ""}
              href={`/admin/news?status=${queue.value}`}
            >{queue.label}</Link>
          ))}
        </div>
        <div className="form-actions">
          <Link className="button secondary" href="/admin/news/incoming">Incoming</Link>
          <Link className="button" href="/admin/news/new">New article</Link>
        </div>
      </div>

      {articles.length === 0 ? (
        <div className="empty-state">No articles in this queue.</div>
      ) : (
        <div className="card admin-table">
          <div className="admin-row admin-row-head news-admin-row">
            <b>Headline</b><b>Source</b><b>Impact</b><b>Score</b><b>Confidence</b>
            <b>Status</b><b>Created</b><b>Published</b><span></span>
          </div>
          {articles.map((article) => (
            <div className="admin-row news-admin-row" key={article.id}>
              <strong>
                <Link href={`/admin/news/${article.id}`}>{article.headline}</Link>
                <small>{article.slug}</small>
              </strong>
              <span>{article.primarySource?.sourceName ?? "—"}</span>
              <span>
                {article.impactLevel ? article.impactLevel.toUpperCase() : "Not assessed"}
                {article.impactOverriddenAt ? " · overridden" : ""}
              </span>
              {/* The internal score. Visible here and in the editor; never in a public payload. */}
              <span>{article.impactScore ?? "—"}</span>
              <span>{article.impactConfidence ?? "—"}</span>
              <span>{article.status.replace("_", " ")}</span>
              <span>{formatDate(article.createdAt)}</span>
              <span>{formatDate(article.publishedAt)}</span>
              <Link className="button secondary" href={`/admin/news/${article.id}`}>Open</Link>
            </div>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
