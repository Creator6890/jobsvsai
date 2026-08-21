import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { MetricBar } from "@/components/ScoreCard";
import { getAdminOverview, getOccupations, getScoreDerivation } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const [overview, occupations] = await Promise.all([getAdminOverview(), getOccupations()]);
  const inspected = occupations[0] ? await getScoreDerivation(occupations[0].slug) : null;
  const operational = overview.errors === 0;
  return <AdminShell title="JobsVsAI engine" modelVersion={overview.activeModel?.version} modelUpdated={overview.latestRecalculation ?? undefined} action={<Status tone={operational ? "ok" : "error"}>{operational ? "All systems operational" : `${overview.errors} scoring errors`}</Status>}>
    <div className="kpi-grid"><Kpi label="Occupations" value={overview.occupations} note="Active database records" /><Kpi label="Tasks" value={overview.tasks} note="Normalized task records" /><Kpi label="Skills" value={overview.skills} note="Recommendation inputs" /><Kpi label="Jobs scored" value={overview.scored} note={`${overview.scoreCoverage}% coverage`} /></div>
    <div className="admin-grid"><article className="card"><div className="card-heading"><h3>Pipeline health</h3><Link className="text-link small" href="/admin/system">Open system →</Link></div><dl className="data-list"><div><dt>Pending recalculations</dt><dd><Status tone={overview.pending ? "warn" : "ok"}>{overview.pending}</Status></dd></div><div><dt>Scoring failures</dt><dd><Status tone={overview.errors ? "error" : "ok"}>{overview.errors}</Status></dd></div><div><dt>Completed imports</dt><dd>{overview.completedImports}</dd></div><div><dt>Failed imports</dt><dd>{overview.failedImports}</dd></div></dl></article><article className="card"><div className="card-heading"><h3>Current scoring model</h3><span className="chip">{overview.activeModel?.version ?? "Unavailable"}</span></div><p>Last recalculation: {formatDate(overview.latestRecalculation)}</p><div className="metric-stack"><MetricBar label="Score coverage" value={overview.scoreCoverage} suffix="%" /><MetricBar label="Market signal coverage" value={overview.marketCoverage} suffix="%" /></div></article></div>
    {inspected && <article className="card admin-inspector"><div className="card-heading"><div><span className="section-kicker">Occupation inspector</span><h2>{inspected.occupationTitle}</h2></div><Link className="button secondary" href={`/admin/jobs/${inspected.occupationSlug}`}>Open occupation →</Link></div><div className="admin-table derivation-table"><div className="admin-row admin-row-head"><b>Dimension</b><b>Raw value</b><b>Weight</b><b>Contribution</b><b>Transform</b></div>{inspected.factors.map((factor) => <div className="admin-row" key={factor.key}><strong>{factor.label}</strong><span data-label="Raw value">{factor.rawValue}</span><span data-label="Weight">{formatPercent(factor.weight)}</span><span data-label="Contribution">{factor.contribution.toFixed(2)}</span><span data-label="Transform">{factor.transformation}</span></div>)}</div><div className="derivation-total"><span>Reconciled replacement risk</span><strong>{inspected.calculatedTotal.toFixed(2)}</strong></div></article>}
  </AdminShell>;
}

function Kpi({ label, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>; }
function formatPercent(value: number) { return `${Math.round(value * 100)}%`; }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "No score snapshots"; }
