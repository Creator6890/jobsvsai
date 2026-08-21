import { notFound } from "next/navigation";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { MetricBar } from "@/components/ScoreCard";
import { getOccupation, getScoreDerivation } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AdminJobPage({ params }: PageProps<"/admin/jobs/[slug]">) {
  const { slug } = await params;
  const [job, derivation] = await Promise.all([getOccupation(slug), getScoreDerivation(slug)]);
  if (!job || !derivation) notFound();
  const reconciled = Math.abs(derivation.calculatedTotal - derivation.replacementRisk) < .011;
  return <AdminShell title={job.title} eyebrow={`${job.category} · Score inspector`} modelVersion={derivation.modelVersion} modelUpdated={derivation.calculatedAt} action={<Status tone={reconciled ? "ok" : "error"}>{reconciled ? "Reconciled" : "Mismatch"}</Status>}>
    <div className="kpi-grid"><Kpi label="AI Exposure" value={derivation.aiExposure.toFixed(2)} /><Kpi label="Replacement Risk" value={derivation.replacementRisk.toFixed(2)} /><Kpi label="Confidence" value={derivation.confidence} /><Kpi label="Trend" value={derivation.trend} /></div>
    <div className="admin-grid"><article className="card"><h3>Calculated factors</h3><div className="metric-stack">{derivation.factors.map((factor) => <MetricBar label={factor.label} value={factor.rawValue} key={factor.key} />)}</div></article><article className="card"><h3>Snapshot metadata</h3><dl className="data-list"><div><dt>Score snapshot</dt><dd>#{derivation.scoreId}</dd></div><div><dt>Model version</dt><dd>{derivation.modelVersion}</dd></div><div><dt>Calculated</dt><dd>{formatDate(derivation.calculatedAt)}</dd></div><div><dt>Task coverage</dt><dd>{derivation.taskContributions.length} tasks</dd></div><div><dt>Input versions</dt><dd>{formatVersions(derivation.inputVersions)}</dd></div></dl></article></div>
    <article className="card"><div className="card-heading"><div><h3>Replacement-risk contribution breakdown</h3><p>Raw resilience factors are inverted before weighting.</p></div><Status tone={reconciled ? "ok" : "error"}>{reconciled ? "Exact match" : "Review required"}</Status></div><div className="admin-table derivation-table"><div className="admin-row admin-row-head"><b>Factor</b><b>Raw → transformed</b><b>Weight</b><b>Contribution</b><b>Rule</b></div>{derivation.factors.map((factor) => <div className="admin-row" key={factor.key}><strong>{factor.label}</strong><span data-label="Raw → transformed">{factor.rawValue} → {factor.transformedValue}</span><span data-label="Weight">{Math.round(factor.weight * 100)}%</span><span data-label="Contribution">{factor.contribution.toFixed(2)}</span><span data-label="Rule">{factor.transformation}</span></div>)}</div><div className="derivation-total"><span>Contribution total</span><strong>{derivation.calculatedTotal.toFixed(2)}</strong><span>Stored risk</span><strong>{derivation.replacementRisk.toFixed(2)}</strong></div></article>
    <article className="card admin-inspector"><div className="card-heading"><div><h3>Task-exposure derivation</h3><p>Importance and frequency normalized across this occupation.</p></div><strong>{derivation.taskContributions.reduce((sum, task) => sum + task.exposureContribution, 0).toFixed(2)}</strong></div><div className="admin-table task-derivation-table"><div className="admin-row admin-row-head"><b>Task</b><b>Exposure</b><b>Importance</b><b>Normalized weight</b><b>Contribution</b></div>{derivation.taskContributions.map((task) => <div className="admin-row" key={task.taskId}><strong>{task.task}</strong><span data-label="Exposure">{task.exposure}</span><span data-label="Importance">{task.importance}</span><span data-label="Normalized weight">{(task.normalizedWeight * 100).toFixed(1)}%</span><span data-label="Contribution">{task.exposureContribution.toFixed(2)}</span></div>)}</div></article>
  </AdminShell>;
}

function Kpi({ label, value }: { label: string; value: string | number }) { return <article className="kpi"><span>{label}</span><strong>{value}</strong><small>Current snapshot</small></article>; }
function formatDate(value: string) { return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function formatVersions(versions: Record<string, unknown>) { const entries = Object.entries(versions); return entries.length ? entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ") : "None recorded"; }
