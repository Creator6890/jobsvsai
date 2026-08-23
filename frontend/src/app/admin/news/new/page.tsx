import { AdminShell } from "@/components/admin/AdminShell";
import { createArticle } from "../actions";

export const dynamic = "force-dynamic";

// Manual creation, no LLM involved. A brief written by an editor is a first-class article;
// generation is an alternative way to fill these fields, not a prerequisite.
export default function NewArticlePage() {
  return (
    <AdminShell title="New article" eyebrow="AI News">
      <form action={createArticle} className="card news-editor" style={{ padding: "var(--pad-card)" }}>
        <label>Headline
          <input name="headline" required maxLength={300} placeholder="What happened, in one line" />
        </label>
        <label>What happened
          <textarea name="whatHappened" required placeholder="JobsVsAI's own summary of the development. Never paste source text." />
        </label>
        <label>Why it matters for jobs
          <textarea name="whyItMattersForJobs" required placeholder="Which work is affected, and how." />
        </label>
        <label>Tags <small>(comma separated)</small>
          <input name="tags" placeholder="agents, finance" />
        </label>
        <label>Affected job areas <small>(comma separated)</small>
          <input name="jobAreas" placeholder="Finance, Administration" />
        </label>
        <div className="form-actions">
          <button className="button" type="submit">Create draft</button>
        </div>
      </form>
    </AdminShell>
  );
}
