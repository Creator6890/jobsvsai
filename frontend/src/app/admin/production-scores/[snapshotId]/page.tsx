import Link from "next/link";
import { notFound } from "next/navigation";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { ApiError, getProductionScoreDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

// Read-only inspector for one immutable snapshot. Shows the candidate it was promoted from
// beside the promoted values, so a divergence between the two is visible rather than
// inferred.
export default async function ProductionScoreDetailPage({ params }: PageProps<"/admin/production-scores/[snapshotId]">) {
  const { snapshotId } = await params;
  let detail;
  try {
    detail = await getProductionScoreDetail(snapshotId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const snapshot = detail.snapshot as Record<string, never> as Record<string, unknown>;
  const candidate = detail.candidate;
  const reconciliation = detail.recomputedReconciliation;
  const reconciles = Boolean(reconciliation.factorsReconcile) && Boolean(reconciliation.tasksReconcile);

  return (
    <AdminShell
      title={String(snapshot.title ?? snapshot.identityId)}
      eyebrow={`Snapshot ${snapshotId} · ${String(snapshot.runKey)}`}
      modelVersion={String(snapshot.scoringModelVersion)}
      action={<Status tone={reconciles ? "ok" : "error"}>{reconciles ? "Reconciles" : "Does not reconcile"}</Status>}
    >
      <p><Link className="text-link" href="/admin/production-scores">← All production scores</Link></p>

      <div className="kpi-grid">
        <Kpi label="AI Exposure" value={fixed(snapshot.aiExposure)} note="0–100 index" />
        <Kpi label="Replacement Risk" value={fixed(snapshot.replacementRisk)} note="0–100 index" />
        <Kpi label="Confidence" value={fixed(snapshot.confidence)} note="numeric, not banded" />
        <Kpi label="Weighted coverage" value={fixed(snapshot.weightedTaskCoverage)} note="70% gate" />
      </div>

      <article className="card">
        <h3>Candidate vs production snapshot</h3>
        {candidate ? (
          <div className="admin-table-scroll">
            <table className="admin-table">
              <thead><tr><th>Metric</th><th>Phase 5 candidate</th><th>Production snapshot</th><th>Δ</th></tr></thead>
              <tbody>
                {(["aiExposure", "replacementRisk", "confidence", "weightedTaskCoverage"] as const).map((key) => {
                  const candidateValue = Number(candidate[key]);
                  const snapshotValue = Number(snapshot[key]);
                  const delta = snapshotValue - candidateValue;
                  return (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>{candidateValue.toFixed(4)}</td>
                      <td>{snapshotValue.toFixed(4)}</td>
                      <td><Status tone={Math.abs(delta) < 0.0001 ? "ok" : "error"}>{delta.toFixed(4)}</Status></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state compact">
            <p>
              This snapshot has no source candidate, so it was not promoted from Phase 5.
              Source kind: <code>{String(snapshot.sourceKind)}</code>.
            </p>
          </div>
        )}
      </article>

      <article className="card">
        <h3>Factor contributions</h3>
        <div className="admin-table-scroll">
          <table className="admin-table">
            <thead>
              <tr><th>Factor</th><th>Value</th><th>Transformation</th><th>Weight</th><th>Contribution</th><th>Provenance</th></tr>
            </thead>
            <tbody>
              {detail.factorContributions.map((factor) => (
                <tr key={String(factor.factorKey)}>
                  <td>{String(factor.factorLabel)}</td>
                  <td>{fixed(factor.value)}</td>
                  <td><small>{String(factor.transformation)}</small></td>
                  <td>{Number(factor.weight).toFixed(2)}</td>
                  <td>{fixed(factor.weightedContribution)}</td>
                  <td>
                    {factor.isProvisionalProxy
                      ? <Status tone="warn">provisional · {String(factor.proxyModelVersion)}</Status>
                      : <Status tone="ok">direct</Status>}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}><strong>Recomputed total</strong></td>
                <td><strong>{Number(reconciliation.factorContributionTotal).toFixed(4)}</strong></td>
                <td><Status tone={reconciliation.factorsReconcile ? "ok" : "error"}>vs {Number(reconciliation.replacementRisk).toFixed(4)}</Status></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p><small>{detail.provisionalWeightShare}% of replacement-risk weight rests on provisional proxy models.</small></p>
      </article>

      <article className="card">
        <h3>Task contributions</h3>
        <div className="admin-table-scroll">
          <table className="admin-table">
            <thead>
              <tr><th>O*NET task</th><th>Fit</th><th>Automation</th><th>Augmentation</th><th>Exposure</th><th>Weight</th><th>Contribution</th></tr>
            </thead>
            <tbody>
              {detail.taskContributions.map((task) => (
                <tr key={String(task.onetTaskId)}>
                  <td><small>{String(task.onetTaskId)}</small> {String(task.taskStatement)}</td>
                  <td>{fixed(task.aiCapabilityFit)}</td>
                  <td>{fixed(task.automationFeasibility)}</td>
                  <td>{fixed(task.augmentationPotential)}</td>
                  <td>{fixed(task.taskAiExposure)}</td>
                  <td>{Number(task.normalizedCoveredWeight).toFixed(4)}</td>
                  <td>{fixed(task.exposureContribution)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={6}><strong>Recomputed total</strong></td>
                <td>
                  <Status tone={reconciliation.tasksReconcile ? "ok" : "error"}>
                    {Number(reconciliation.taskContributionTotal).toFixed(4)} vs {Number(reconciliation.aiExposure).toFixed(4)}
                  </Status>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </article>

      <div className="two-column">
        <article className="card">
          <h3>Versions and provenance</h3>
          <dl className="data-list">
            <Row label="Scoring model" value={`${String(snapshot.scoringModelVersion)} (${String(snapshot.methodologyFamily)})`} />
            <Row label="Occupation formula" value={String(snapshot.occupationFormulaVersion)} />
            <Row label="Frontier index" value={`${String(snapshot.frontierIndexVersion)} · ${String(snapshot.frontierTrack)}`} />
            <Row label="Structural proxies" value={String(snapshot.structuralProxyModelVersion)} />
            <Row label="Base proxies" value={String(snapshot.baseProxyModelVersion)} />
            <Row label="Capability taxonomy" value={String(snapshot.capabilityTaxonomyVersion)} />
            <Row label="Mapping rubric" value={String(snapshot.mappingRubricVersion)} />
            <Row label="Evidence policy" value={String(snapshot.evidencePolicyVersion)} />
            <Row label="Calculated" value={String(snapshot.calculatedAt)} />
            <Row label="Promoted" value={String(snapshot.promotedAt)} />
            <Row label="Input hash" value={String(snapshot.inputHash).slice(0, 16) + "…"} />
          </dl>
        </article>

        <article className="card">
          <h3>Eligibility and publication</h3>
          <dl className="data-list">
            <Row label="Scoring eligibility" value={String(snapshot.scoringEligibility)} />
            <Row label="Coverage gate" value={String(snapshot.coverageGateStatus)} />
            <Row label="Confidence gate" value={String(snapshot.confidenceGateStatus)} />
            <Row label="Publishable" value={snapshot.publishable ? "yes" : "no"} />
            <Row label="Activation status" value={String(snapshot.activationStatus ?? "not published")} />
            <Row label="Consistency" value={String(snapshot.consistencyState ?? "no publication")} />
            <Row label="Promotion run" value={`${String(snapshot.runKey)} · ${String(snapshot.promotionRunStatus)}`} />
          </dl>
          <p><small>Publishable means editorially permissible, not published. Activation is a separate decision.</small></p>
        </article>
      </div>

      <article className="card">
        <h3>Warnings and provisional sensitivity</h3>
        <pre className="admin-json">{JSON.stringify({
          warnings: snapshot.warnings,
          blockingReasons: snapshot.blockingReasons,
          provisionalSensitivity: snapshot.provisionalSensitivity,
          storedReconciliation: snapshot.reconciliation,
        }, null, 2)}</pre>
      </article>
    </AdminShell>
  );
}

function Kpi({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function fixed(value: unknown): string {
  return value === null || value === undefined ? "—" : Number(value).toFixed(2);
}
