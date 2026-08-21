import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getProductionScores } from "@/lib/api";

export const dynamic = "force-dynamic";

// Read-only. This console can inspect the production score store; it cannot promote,
// approve or activate anything. Those are deliberate, separately-authorised actions.
export default async function ProductionScoresPage() {
  const data = await getProductionScores();
  const totals = data.totals;
  const promoted = Number(totals.promotedFromCandidates ?? 0);
  const activeModel = String(totals.activeScoringModel ?? "unknown");

  return (
    <AdminShell
      title="Production scores"
      eyebrow="Promotion, snapshots and publication consistency"
      modelVersion={activeModel}
      action={
        <Status tone={promoted > 0 ? "warn" : "ok"}>
          {promoted > 0 ? `${promoted} promoted from candidates` : "No candidate promoted"}
        </Status>
      }
    >
      <div className="kpi-grid">
        <Kpi label="Promotion runs" value={totals.promotionRuns} note={`${totals.completedRuns} completed`} />
        <Kpi label="Snapshots" value={totals.snapshots} note={`${totals.currentSnapshots} current`} />
        <Kpi label="Publishable" value={totals.publishable} note="eligible, not published" />
        <Kpi label="Public occupations" value={totals.publicOccupations} note="activation status" />
      </div>

      <article className="card">
        <h3>Guardrails</h3>
        <dl className="data-list">
          <div>
            <dt>Active scoring model</dt>
            <dd><Status tone={activeModel === "JVS 1.0.3" ? "ok" : "warn"}>{activeModel}</Status></dd>
          </div>
          <div>
            <dt>Phase 5 candidates promoted</dt>
            <dd><Status tone={promoted > 0 ? "warn" : "ok"}>{promoted}</Status></dd>
          </div>
        </dl>
      </article>

      <article className="card">
        <h3>Promotion runs</h3>
        {data.promotionRuns.length ? (
          <div className="admin-table-scroll">
            <table className="admin-table">
              <thead>
                <tr><th>Run</th><th>Source</th><th>Model</th><th>Snapshots</th><th>Status</th></tr>
              </thead>
              <tbody>
                {data.promotionRuns.map((run) => (
                  <tr key={String(run.id)}>
                    <td>{String(run.runKey)}</td>
                    <td>
                      {String(run.sourceKind)}
                      {run.sourceCalculationRun ? ` · ${String(run.sourceCalculationRun)}` : ""}
                    </td>
                    <td>{String(run.scoringModelVersion)}</td>
                    <td>{String(run.snapshotCount)}</td>
                    <td>
                      <Status tone={run.status === "completed" ? "ok" : run.status === "rolled_back" ? "warn" : "error"}>
                        {String(run.status)}
                      </Status>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state compact"><p>No promotion run has been created. The production store is empty by design until the launch-quality review approves a cohort.</p></div>
        )}
      </article>

      <article className="card">
        <h3>Publication / snapshot consistency</h3>
        {data.consistencyCounts.length ? (
          <dl className="data-list">
            {data.consistencyCounts.map((row) => (
              <div key={row.consistencyState}>
                <dt>{row.consistencyState.replace(/_/g, " ")}</dt>
                <dd>
                  <Status tone={row.consistencyState === "consistent" ? "ok" : row.consistencyState === "no_approved_snapshot" ? "warn" : "error"}>
                    {row.total}
                  </Status>
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="empty-state compact"><p>No publications exist yet.</p></div>
        )}
      </article>

      <article className="card">
        <h3>Launch-quality triage</h3>
        {data.triageRuns.length ? (
          <dl className="data-list">
            {data.triageRuns.map((run) => {
              const severities = (run.severityTotals ?? {}) as Record<string, number>;
              return (
                <div key={String(run.id)}>
                  <dt>
                    {String(run.runKey)} · {String(run.policyVersion)}
                    <small> — {String(run.cohortSelection)}</small>
                  </dt>
                  <dd>
                    cohort {String(run.launchCohortSize)} / {String(run.candidatesAssessed)}
                    {" · "}
                    <Status tone={severities.critical ? "error" : severities.high ? "warn" : "ok"}>
                      {severities.critical ?? 0} critical, {severities.high ?? 0} high
                    </Status>
                  </dd>
                </div>
              );
            })}
          </dl>
        ) : (
          <div className="empty-state compact"><p>No triage run recorded. Run <code>scoring.run_phase6_launch_triage</code> against the Phase 5 corpus.</p></div>
        )}
      </article>

      <article className="card">
        <h3>Current snapshots</h3>
        {data.currentSnapshots.length ? (
          <div className="admin-table-scroll">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Occupation</th><th>Exposure</th><th>Replacement</th><th>Confidence</th>
                  <th>Coverage</th><th>Warnings</th><th>Publication</th><th>Approval</th><th></th>
                </tr>
              </thead>
              <tbody>
                {data.currentSnapshots.map((snapshot) => (
                  <tr key={String(snapshot.snapshotId)}>
                    <td>
                      {String(snapshot.title ?? "—")}
                      {snapshot.missingEditorialRecord ? <small> · no editorial record</small> : ""}
                    </td>
                    <td>{fixed(snapshot.aiExposure)}</td>
                    <td>{fixed(snapshot.replacementRisk)}</td>
                    <td>{fixed(snapshot.confidence)}</td>
                    <td>{fixed(snapshot.weightedTaskCoverage)}</td>
                    <td>{String(snapshot.warningCount ?? 0)}</td>
                    <td>{String(snapshot.activationStatus ?? "not published")}</td>
                    <td>
                      <Status tone={snapshot.approvalEligible ? "ok" : "warn"}>
                        {snapshot.approvalEligible ? "eligible" : "not eligible"}
                      </Status>
                    </td>
                    <td>
                      <Link className="text-link" href={`/admin/production-scores/${String(snapshot.snapshotId)}`}>
                        Inspect →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state compact"><p>No current production snapshot. Either nothing has been promoted, or every promotion run has been rolled back.</p></div>
        )}
      </article>
    </AdminShell>
  );
}

function Kpi({ label, value, note }: { label: string; value: unknown; note: string }) {
  return <article className="kpi"><span>{label}</span><strong>{String(value ?? 0)}</strong><small>{note}</small></article>;
}

function fixed(value: unknown): string {
  return value === null || value === undefined ? "—" : Number(value).toFixed(1);
}
