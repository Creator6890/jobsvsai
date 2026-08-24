import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getGenerationStatus, getIncomingItems, getIncomingOverview, type IngestStatus } from "@/lib/api";
import { draftFromIncoming, generateFromIncoming, runGenerationBatch, runIngestion, setIncomingStatus } from "../actions";

export const dynamic = "force-dynamic";

const QUEUES: { label: string; value: IngestStatus }[] = [
  { label: "Candidates", value: "candidate" },
  { label: "New", value: "new" },
  { label: "Ignored", value: "ignored" },
  { label: "Duplicates", value: "duplicate" },
  { label: "Processed", value: "processed" },
];

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

/** The matched signals, summarised. The full object is stored; this is the readable part. */
function signalSummary(signals: Record<string, unknown>): string {
  const pick = (key: string) => (Array.isArray(signals[key]) ? (signals[key] as string[]) : []);
  const parts: string[] = [];
  for (const [label, key] of [["AI", "aiTerms"], ["capability", "capabilityTerms"], ["work", "workTerms"], ["negative", "negativeTerms"]] as const) {
    const terms = pick(key);
    if (terms.length) parts.push(`${label}: ${terms.slice(0, 4).join(", ")}`);
  }
  if (signals.sourceFloorApplied === true) parts.push("source floor applied");
  return parts.join(" · ") || "no signals matched";
}

export default async function IncomingPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status } = await searchParams;
  const active = (QUEUES.find((q) => q.value === status)?.value ?? "candidate") as IngestStatus;
  const [items, overview, generation] = await Promise.all([
    getIncomingItems(active), getIncomingOverview(), getGenerationStatus(),
  ]);
  const lastRun = overview.runs[0] as Record<string, unknown> | undefined;

  return (
    <AdminShell
      title="Incoming"
      eyebrow={`AI News ingestion · ${overview.relevancePolicyVersion}`}
      modelVersion={overview.relevancePolicyVersion}
      action={<Status tone={overview.statuses.candidate > 0 ? "warn" : "ok"}>
        {overview.statuses.candidate} candidate{overview.statuses.candidate === 1 ? "" : "s"}
      </Status>}
    >
      <div className="kpi-grid">
        {QUEUES.map((queue) => (
          <div className="card kpi" key={queue.value}>
            <span className="metric-label">{queue.label}</span>
            <strong>{overview.statuses[queue.value] ?? 0}</strong>
          </div>
        ))}
      </div>

      <div className="admin-toolbar">
        <div className="tab-list" role="tablist" aria-label="Filter incoming by status">
          {QUEUES.map((queue) => (
            <Link key={queue.value} role="tab" aria-selected={active === queue.value}
              className={active === queue.value ? "active" : ""}
              href={`/admin/news/incoming?status=${queue.value}`}>{queue.label}</Link>
          ))}
        </div>
        <form action={runIngestion}>
          <button className="button" type="submit" disabled={!generation.ingestionEnabled}>
            Fetch feeds now
          </button>
        </form>
      </div>

      {lastRun && (
        <p className="small">
          Last run {formatDate(String(lastRun.started_at ?? lastRun.startedAt ?? ""))} ·{" "}
          {String(lastRun.sources_succeeded ?? 0)}/{String(lastRun.sources_attempted ?? 0)} sources ·{" "}
          {String(lastRun.items_candidate ?? 0)} candidates ·{" "}
          {String(lastRun.items_ignored ?? 0)} ignored ·{" "}
          {String(lastRun.items_near_duplicate ?? 0)} near-duplicates
          {Array.isArray(lastRun.errors) && lastRun.errors.length > 0 && ` · ${lastRun.errors.length} source error(s)`}
        </p>
      )}

      <div className="card" style={{ padding: "var(--pad-card)", marginBottom: "var(--gap)" }}>
        <span className="section-kicker">AI news pipeline</span>
        {generation.usesLegacyNewsFlag && (
          <p className="small" style={{ color: "var(--amber)" }}>
            Gating is coming from the deprecated <code>NEWS_ENABLED</code> variable. Set
            <code> NEWS_INGESTION_ENABLED</code> and <code>NEWS_GENERATION_ENABLED</code> instead.
          </p>
        )}
        <p className="small">
          ingestion <strong>{generation.ingestionEnabled ? "enabled" : "disabled"}</strong> ·
          generation <strong>{generation.generationEnabled ? "enabled" : "disabled"}</strong> ·
          provider <strong>{generation.provider}</strong> ·
          model <strong>{generation.model ?? "default"}</strong> ·
          {/* Presence only. The key is never sent to the browser. */}
          key {generation.apiKeyConfigured ? "configured" : "NOT configured"} ·
          prompt {generation.promptVersion} ·
          daily cap {generation.dailyLimit} · batch {generation.batchSize} ·
          auto-publish {String(generation.autoPublish)}
        </p>
        <div className="form-actions">
          <form action={runGenerationBatch}>
            <button className="button" type="submit"
              disabled={!generation.generationEnabled || !generation.apiKeyConfigured}>
              Generate batch ({generation.batchSize})
            </button>
          </form>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">Nothing in this queue.</div>
      ) : (
        <div className="incoming-list">
          {items.map((item) => (
            <article className="card incoming-card" key={item.id}>
              <header>
                <span className="chip">{item.sourceName}</span>
                <span className="chip">tier {item.trustTier}</span>
                {item.relevanceScore !== null && (
                  <span className={`chip ${item.relevanceScore >= overview.confidentThreshold ? "safe" : ""}`}>
                    relevance {item.relevanceScore}
                  </span>
                )}
                {item.nearDuplicateSimilarity !== null && (
                  <span className="chip">near-dup {item.nearDuplicateSimilarity} of #{item.duplicateOfIngestItemId}</span>
                )}
                <span className="chip">{item.status}</span>
              </header>
              {/* Feed-provided title and excerpt, rendered as plain text. They were reduced
                  to text at ingestion, so no feed markup can reach this page. */}
              <h3>{item.originalTitle}</h3>
              {item.originalExcerpt && <p>{item.originalExcerpt}</p>}
              <p className="small">{signalSummary(item.relevanceSignals)}</p>
              {item.isAiNews !== null && (
                <p className="small">
                  <strong>AI verdict: {item.isAiNews ? "relevant" : "not AI news"}</strong>
                  {item.aiRelevanceConfidence !== null && ` · confidence ${item.aiRelevanceConfidence}`}
                  {item.generationModel && ` · ${item.generationProvider}/${item.generationModel}`}
                  {item.aiRelevanceReason && <> — {item.aiRelevanceReason}</>}
                </p>
              )}
              {item.generationError && (
                <p className="small" style={{ color: "var(--amber)" }}>
                  Generation failed ({item.generationAttempts} attempt
                  {item.generationAttempts === 1 ? "" : "s"}): {item.generationError}
                </p>
              )}
              <footer className="incoming-meta">
                <span>Source published {formatDate(item.sourcePublishedAt)}</span>
                <span>Fetched {formatDate(item.fetchedAt)}</span>
                <a href={item.externalUrl} target="_blank" rel="noopener noreferrer nofollow">Original ↗</a>
              </footer>
              <div className="form-actions">
                {item.status === "candidate" && item.isAiNews === null && (
                  <form action={generateFromIncoming}>
                    <input type="hidden" name="itemId" value={item.id} />
                    <button className="button" type="submit"
                      disabled={!generation.generationEnabled || !generation.apiKeyConfigured}>
                      Generate with AI
                    </button>
                  </form>
                )}
                {item.status !== "processed" && (
                  <form action={draftFromIncoming}>
                    <input type="hidden" name="itemId" value={item.id} />
                    <button className="button secondary" type="submit">Create draft manually</button>
                  </form>
                )}
                {item.status !== "ignored" && (
                  <form action={setIncomingStatus}>
                    <input type="hidden" name="itemId" value={item.id} />
                    <input type="hidden" name="status" value="ignored" />
                    <button className="button secondary" type="submit">Ignore</button>
                  </form>
                )}
                {item.status !== "candidate" && item.status !== "processed" && (
                  <form action={setIncomingStatus}>
                    <input type="hidden" name="itemId" value={item.id} />
                    <input type="hidden" name="status" value="candidate" />
                    <button className="button secondary" type="submit">Restore candidate</button>
                  </form>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
