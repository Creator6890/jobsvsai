import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminScores } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ScoresPage() {
  const data = await getAdminScores();
  return <AdminShell title="Scoring queue" eyebrow="JVS scoring engine" action={<Status tone={data.summary.failed ? "error" : "ok"}>{data.summary.failed ? `${data.summary.failed} failed` : "Queue healthy"}</Status>}><div className="kpi-grid"><Kpi label="Queued" value={data.summary.queued} /><Kpi label="Running" value={data.summary.running} /><Kpi label="Completed today" value={data.summary.completedToday} /><Kpi label="Failed" value={data.summary.failed} /></div><article className="card"><h3>Recent scoring jobs</h3>{data.jobs.length ? <dl className="data-list">{data.jobs.map((job) => <div key={String(job.id)}><dt>{String(job.occupationTitle ?? "All occupations")} · {String(job.reason)}</dt><dd><Status tone={tone(String(job.status))}>{String(job.status)}</Status></dd></div>)}</dl> : <div className="empty-state compact"><p>No scoring jobs have been queued.</p></div>}</article></AdminShell>;
}

function Kpi({ label, value }: { label: string; value: string | number }) { return <article className="kpi"><span>{label}</span><strong>{value}</strong><small>Live queue</small></article>; }
function tone(status: string): "ok" | "warn" | "error" { return status === "failed" ? "error" : status === "pending" || status === "running" ? "warn" : "ok"; }
