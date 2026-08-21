import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminSystem } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SystemPage() {
  const system = await getAdminSystem();
  const operational = Object.values(system.services).every(Boolean);
  return <AdminShell title="System health" eyebrow="Runtime & dependencies" action={<Status tone={operational ? "ok" : "error"}>{operational ? "Operational" : "Degraded"}</Status>}><div className="admin-grid"><article className="card"><h3>Services</h3><dl className="data-list"><Service label="Public API" healthy={system.services.publicApi} /><Service label="PostgreSQL" healthy={system.services.postgresql} /><Service label="Redis queue" healthy={system.services.redisQueue} /></dl></article><article className="card"><h3>Score store</h3><dl className="data-list"><div><dt>Scored occupations</dt><dd>{system.scoreStore.professionPages}</dd></div><div><dt>Score snapshots</dt><dd>{system.scoreStore.scoreSnapshots}</dd></div><div><dt>Latest snapshot</dt><dd>{formatDate(system.scoreStore.latestScore)}</dd></div><div><dt>Environment</dt><dd>{system.environment}</dd></div></dl></article></div><div className="notice"><strong>Environment-safe configuration</strong><p>Database, Redis, internal API, and public site origins are configured through environment variables. No machine-specific paths are required.</p></div></AdminShell>;
}

function Service({ label, healthy }: { label: string; healthy: boolean }) { return <div><dt>{label}</dt><dd><Status tone={healthy ? "ok" : "error"}>{healthy ? "Healthy" : "Unavailable"}</Status></dd></div>; }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "No snapshots"; }
