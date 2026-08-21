import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AdminJobsPage() {
  const jobs = await getOccupations();
  return <AdminShell title="Occupations" eyebrow="Data coverage" action={<Status>{jobs.length} live records</Status>}><div className="card"><div className="admin-table occupation-table"><div className="admin-row occupation-admin-row admin-row-head"><b>Occupation</b><b>Exposure</b><b>Risk</b><b>Updated</b><b>Status</b></div>{jobs.map((job) => <Link className="admin-row occupation-admin-row" href={`/admin/jobs/${job.slug}`} key={job.slug}><strong>{job.title}<small>{job.category}</small></strong><span data-label="Exposure">{job.aiExposure}</span><span data-label="Risk">{job.replacementRisk}</span><span data-label="Updated">{job.updatedAt}</span><Status>Scored</Status></Link>)}</div></div></AdminShell>;
}
