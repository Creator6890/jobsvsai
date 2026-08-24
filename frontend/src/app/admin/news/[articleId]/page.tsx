import Link from "next/link";
import { notFound } from "next/navigation";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminNewsArticle, getArticleCandidates, getNewsImpactPolicy, getNewsPublicationCheck } from "@/lib/api";
import {
  addSource, archiveArticle, assessImpact, overrideImpact, publishArticle,
  regenerateArticle, rejectArticle, restoreArticle, saveArticle, unpublishArticle,
} from "../actions";

export const dynamic = "force-dynamic";

const FACTOR_FIELDS = [
  ["capabilityAdvancement", "Capability advancement"],
  ["commercialDeployability", "Commercial deployability"],
  ["breadthOfAffectedWork", "Breadth of affected work"],
  ["adoptionSpeed", "Adoption speed"],
  ["humanWorkReductionPotential", "Human work reduction potential"],
] as const;

function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
    : "—";
}


export default async function AdminNewsArticlePage({ params }: PageProps<"/admin/news/[articleId]">) {
  const { articleId } = await params;
  const [article, policy, check, candidates] = await Promise.all([
    getAdminNewsArticle(articleId),
    getNewsImpactPolicy(),
    getNewsPublicationCheck(articleId).catch(() => ({ publishable: false, blockers: ["Article not found"] })),
    getArticleCandidates(articleId).catch(() => []),
  ]);
  if (!article) notFound();

  const overridden = Boolean(article.impactOverriddenAt);

  return (
    <AdminShell
      title={article.headline}
      eyebrow="AI News article"
      modelVersion={article.impactPolicyVersion ?? policy.policyVersion}
      action={<Status tone={article.status === "published" ? "ok" : "warn"}>{article.status.replace("_", " ")}</Status>}
    >
      <div className="news-editor">
        {/* ------------------------------------------- what the brief was written from */}
        {candidates.length > 0 && (
          <div className="card" style={{ padding: "var(--pad-card)" }}>
            <span className="section-kicker">Source material &amp; AI decision</span>
            {candidates.map((candidate) => (
              <div className="news-assessment" key={candidate.id}>
                <dl>
                  <dt>Source</dt>
                  <dd>{candidate.sourceName} (trust tier {candidate.trustTier})</dd>
                  <dt>Original title</dt>
                  <dd>{candidate.originalTitle}</dd>
                  {candidate.originalExcerpt && (
                    <>
                      <dt>Source excerpt</dt>
                      {/* Feed text, reduced to plain text at ingestion. Shown so the brief
                          above can be checked against the material it came from. */}
                      <dd>{candidate.originalExcerpt}</dd>
                    </>
                  )}
                  <dt>Source published</dt>
                  <dd>{formatDate(candidate.sourcePublishedAt)}</dd>
                  <dt>Keyword prefilter</dt>
                  <dd>
                    {candidate.relevanceScore ?? "—"}/100
                    {candidate.relevancePolicyVersion && ` · ${candidate.relevancePolicyVersion}`}
                  </dd>
                  {candidate.isAiNews !== null && (
                    <>
                      <dt>AI verdict</dt>
                      <dd>
                        <strong>{candidate.isAiNews ? "relevant AI news" : "not AI news"}</strong>
                        {candidate.aiRelevanceConfidence !== null &&
                          ` · semantic confidence ${candidate.aiRelevanceConfidence}`}
                        {candidate.semanticPolicyVersion && ` · ${candidate.semanticPolicyVersion}`}
                      </dd>
                      <dt>AI reasoning</dt>
                      <dd>{candidate.aiRelevanceReason ?? "—"}</dd>
                    </>
                  )}
                  {candidate.generationInputTokens !== null && (
                    <>
                      <dt>Tokens</dt>
                      <dd>
                        {candidate.generationInputTokens} in / {candidate.generationOutputTokens} out
                      </dd>
                    </>
                  )}
                </dl>
                <p className="small">
                  <a href={candidate.externalUrl} target="_blank" rel="noopener noreferrer nofollow">
                    Read the original source ↗
                  </a>
                </p>
              </div>
            ))}
          </div>
        )}

        {/* -------------------------------------------------- assessment, before editing */}
        <div className="card" style={{ padding: "var(--pad-card)" }}>
          <span className="section-kicker">Jobs Impact</span>
          <div className="news-assessment">
            <dl>
              <dt>Automated</dt>
              <dd>
                {article.automatedImpactLevel
                  ? `${article.automatedImpactLevel.toUpperCase()} · score ${article.automatedImpactScore ?? "—"} · confidence ${article.impactConfidence ?? "—"}`
                  : "Not assessed"}
              </dd>
              <dt>Final editorial</dt>
              <dd>{article.impactLevel ? article.impactLevel.toUpperCase() : "Not set"}{overridden ? " (overridden)" : ""}</dd>
              <dt>Impact factors</dt>
              <dd>
                {FACTOR_FIELDS.every(([field]) => article[field] === null)
                  ? "Not assessed"
                  : FACTOR_FIELDS.map(([field, label]) => `${label} ${article[field] ?? "—"}`).join(" · ")}
              </dd>
              <dt>Policy</dt>
              <dd>{article.impactPolicyVersion ?? policy.policyVersion}</dd>
              {article.impactAssessedBy && <><dt>Assessed by</dt><dd>{article.impactAssessedBy}</dd></>}
              {overridden && <><dt>Overridden by</dt><dd>{article.impactOverriddenBy} · {article.impactOverrideReason ?? "no reason given"}</dd></>}
              {article.generationProvider && <><dt>Generated by</dt><dd>{article.generationProvider} / {article.generationModel}</dd></>}
            </dl>
            {article.impactReasoning && <p className="small">{article.impactReasoning}</p>}
            {/* The internal score is shown here and nowhere public. */}
            <p className="small">Score is internal for V1. Public pages show only the band.</p>
          </div>
        </div>

        {/* ------------------------------------------------------------------- the brief */}
        <form action={saveArticle} className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <input type="hidden" name="articleId" value={article.id} />
          <span className="section-kicker">Brief</span>
          <label>Headline
            <input name="headline" defaultValue={article.headline} required maxLength={300} />
          </label>
          <label>What happened
            <textarea name="whatHappened" defaultValue={article.whatHappened} required />
          </label>
          <label>Why it matters for jobs
            <textarea name="whyItMattersForJobs" defaultValue={article.whyItMattersForJobs} required />
          </label>
          <label>Tags <small>(comma separated)</small>
            <input name="tags" defaultValue={article.tags.join(", ")} />
          </label>
          <label>Affected job areas <small>(comma separated)</small>
            <input name="jobAreas" defaultValue={article.jobAreas.join(", ")} />
          </label>
          <div className="form-actions"><button className="button" type="submit">Save draft</button></div>
        </form>

        {/* ------------------------------------------------------------------ assessment */}
        <form action={assessImpact} className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <input type="hidden" name="articleId" value={article.id} />
          <span className="section-kicker">Assess impact ({policy.policyVersion})</span>
          <p className="small">
            Enter the five factors 0–100. The score and level are computed server-side by the
            policy; they are never entered directly. Confidence below {policy.minimumPublishConfidence} moves the
            article to review required.
          </p>
          <div className="factor-grid">
            {FACTOR_FIELDS.map(([field, label]) => {
              const weight = policy.factors.find((factor) => factor.key === toSnake(field))?.weight;
              return (
                <label key={field}>{label} <small>({weight !== undefined ? `${Math.round(weight * 100)}%` : "—"})</small>
                  <input type="number" name={field} min={0} max={100} required defaultValue={article[field] ?? ""} />
                </label>
              );
            })}
          </div>
          <label>Confidence <small>(0.00–1.00)</small>
            <input type="number" name="impactConfidence" min={0} max={1} step={0.01} required defaultValue={article.impactConfidence ?? ""} />
          </label>
          <label>Impact reasoning
            <textarea name="impactReasoning" required defaultValue={article.impactReasoning ?? ""} />
          </label>
          <div className="form-actions"><button className="button" type="submit">Calculate impact</button></div>
        </form>

        {/* -------------------------------------------------------------------- override */}
        <form action={overrideImpact} className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <input type="hidden" name="articleId" value={article.id} />
          <span className="section-kicker">Editorial override</span>
          <p className="small">The automated score and level are preserved and stay visible above.</p>
          <label>Final impact level
            <select name="impactLevel" defaultValue={article.impactLevel ?? "medium"}>
              <option value="low">LOW</option><option value="medium">MEDIUM</option><option value="high">HIGH</option>
            </select>
          </label>
          <label>Reason
            <input name="reason" defaultValue={article.impactOverrideReason ?? ""} placeholder="Why the automated level was wrong" />
          </label>
          <div className="form-actions"><button className="button secondary" type="submit">Override impact</button></div>
        </form>

        {/* ---------------------------------------------------------------------- source */}
        <div className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <span className="section-kicker">Sources</span>
          {article.sources.length > 0 ? (
            <ul className="small">
              {article.sources.map((source) => (
                <li key={source.sourceUrl}>
                  <strong>{source.sourceName}</strong>{source.isPrimary ? " (primary)" : ""} — {source.originalTitle}
                  {" "}<a href={source.sourceUrl} target="_blank" rel="noopener noreferrer nofollow">open ↗</a>
                </li>
              ))}
            </ul>
          ) : <p className="small">No source attached. Publication is blocked until one is.</p>}

          <form action={addSource} className="news-editor">
            <input type="hidden" name="articleId" value={article.id} />
            <label>Source name<input name="sourceName" required placeholder="Reuters" /></label>
            <label>Site URL<input name="siteUrl" required placeholder="https://reuters.com" /></label>
            <label>Article URL<input name="externalUrl" required placeholder="https://reuters.com/..." /></label>
            <label>Original title<input name="originalTitle" required placeholder="Headline as published by the source" /></label>
            <label>Source published at <small>(optional)</small><input name="sourcePublishedAt" type="datetime-local" /></label>
            <div className="form-actions"><button className="button secondary" type="submit">Attach as primary source</button></div>
          </form>
        </div>

        {/* ----------------------------------------------------------------- publication */}
        <div className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <span className="section-kicker">Publication</span>
          {check.blockers.length > 0 ? (
            <>
              <p className="small">Publication is blocked:</p>
              <ul className="news-blockers">{check.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>
            </>
          ) : <p className="small">All publication requirements are met.</p>}

          <div className="form-actions">
            <form action={publishArticle}>
              <input type="hidden" name="articleId" value={article.id} />
              <button className="button" type="submit" disabled={!check.publishable}>Publish</button>
            </form>
            <form action={rejectArticle}>
              <input type="hidden" name="articleId" value={article.id} />
              <button className="button secondary" type="submit">Reject</button>
            </form>
            {article.status === "published" && (
              <form action={unpublishArticle}>
                <input type="hidden" name="articleId" value={article.id} />
                <button className="button secondary" type="submit">Unpublish</button>
              </form>
            )}
            {article.status === "published" && (
              <Link className="button secondary" href={`/news/${article.slug}`}>View public page ↗</Link>
            )}
          </div>
        </div>

        {/* ------------------------------------------------------- lifecycle actions */}
        <div className="card news-editor" style={{ padding: "var(--pad-card)" }}>
          <span className="section-kicker">Lifecycle</span>

          {article.status === "archived" ? (
            <>
              <p className="small">
                Archived {formatDate(article.archivedAt)} by {article.archivedBy}
                {article.archiveReason && <> — {article.archiveReason}</>}.
                {article.publishedAt && " It was published before being archived; that record is kept."}
              </p>
              <div className="form-actions">
                <form action={restoreArticle}>
                  <input type="hidden" name="articleId" value={article.id} />
                  <button className="button secondary" type="submit">Restore to review</button>
                </form>
              </div>
            </>
          ) : (
            <form action={archiveArticle} className="news-editor">
              <input type="hidden" name="articleId" value={article.id} />
              <p className="small">
                Archiving retires the article. Unlike rejecting, it keeps
                <code> published_at</code>, so the record of what the site served is preserved.
                An archived article is not public.
              </p>
              <label>Reason <small>(optional)</small>
                <input name="reason" placeholder="Superseded, no longer accurate, …" />
              </label>
              <div className="form-actions">
                <button className="button secondary" type="submit">Archive</button>
              </div>
            </form>
          )}

          {candidates.length > 0 && (
            <form action={regenerateArticle}>
              <input type="hidden" name="articleId" value={article.id} />
              <p className="small">
                Regenerate rewrites the brief from the source candidate, in place — it never
                creates a second article. Any editorial impact override is cleared, because it
                was a judgement about prose that will no longer exist. Counts against the
                daily generation limit.
                {article.regenerationCount > 0 &&
                  ` Regenerated ${article.regenerationCount} time${article.regenerationCount === 1 ? "" : "s"}, last ${formatDate(article.regeneratedAt)}.`}
              </p>
              <div className="form-actions">
                <button className="button secondary" type="submit"
                  disabled={article.status === "published"}>
                  Regenerate with AI
                </button>
              </div>
              {article.status === "published" && (
                <p className="small">
                  Published articles cannot be regenerated in place — readers are already
                  being served this text. Unpublish or archive it first.
                </p>
              )}
            </form>
          )}
        </div>
      </div>
    </AdminShell>
  );
}

function toSnake(value: string): string {
  return value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}
