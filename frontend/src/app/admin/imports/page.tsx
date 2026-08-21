import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminImports } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ImportsPage() {
  const data = await getAdminImports();
  const coverage = data.onetCoverage;
  return (
    <AdminShell
      title="Data imports"
      eyebrow="Source pipeline"
      action={<Status tone={data.summary.failed ? "error" : data.summary.running ? "warn" : "ok"}>
        {data.summary.running ? `${data.summary.running} running` : data.summary.failed ? `${data.summary.failed} failed` : "Idle"}
      </Status>}
    >
      <div className="kpi-grid">
        <Kpi label="Pending" value={data.summary.pending} />
        <Kpi label="Running" value={data.summary.running} />
        <Kpi label="Complete" value={data.summary.complete} />
        <Kpi label="Failed" value={data.summary.failed} />
      </div>

      {coverage.sourceVersion && <section className="admin-inspector">
        <div className="card-heading">
          <div><span className="section-kicker">O*NET private import validation</span><h2>Release {coverage.sourceVersion}</h2></div>
          <Status tone={coverage.relationshipChecksPass ? "ok" : "error"}>
            {coverage.relationshipChecksPass ? "Structural relationships valid" : "Integrity review required"}
          </Status>
        </div>
        <div className="kpi-grid">
          <Kpi label="Occupations" value={coverage.occupations} />
          <Kpi label="Source titles" value={coverage.sourceTitles} />
          <Kpi label="Scales" value={coverage.scales} />
          <Kpi label="SOC mappings" value={coverage.successionMappings} />
        </div>
        <article className="card promotion-matrix-card">
          <div className="card-heading"><div><h3>Occupation promotion matrix</h3><p className="small">Private ingestion, scoring readiness, and public activation are independent gates.</p></div><Status tone={coverage.promotionMatrix.public ? "error" : "ok"}>{coverage.promotionMatrix.public ? `${coverage.promotionMatrix.public} public` : "0 source occupations public"}</Status></div>
          <div className="kpi-grid">
            <Kpi label="Source imported" value={coverage.promotionMatrix.sourceImported} />
            <Kpi label="Identity resolved" value={coverage.promotionMatrix.identityResolved} />
            <Kpi label="Scoring ready" value={coverage.promotionMatrix.scoringReady} />
            <Kpi label="Public ready" value={coverage.promotionMatrix.publicReady} />
          </div>
          <div className="admin-grid compact-admin-grid">
            <dl className="data-list">
              <Row label="Normalized" value={coverage.promotionMatrix.normalized} />
              <Row label="Partial source data" value={coverage.promotionMatrix.partialData} />
              <Row label="Insufficient for scoring" value={coverage.promotionMatrix.insufficientForScoring} />
              <Row label="Identity review required" value={coverage.promotionMatrix.identityReviewRequired} />
            </dl>
            <dl className="data-list">
              {coverage.identityResolutions.map((item) => <Row key={`${item.resolutionType}-${item.reviewStatus}`} label={`${labelDomain(item.resolutionType)} · ${item.reviewStatus}`} value={item.mappings} />)}
            </dl>
          </div>
        </article>
        <div className="admin-grid">
          <article className="card">
            <h3>Generalized source model</h3>
            <dl className="data-list">
              <Row label="Source taxonomies" value={coverage.sourceTaxonomies} />
              <Row label="Taxonomy nodes" value={coverage.sourceTaxonomyNodes} />
              <Row label="Occupation memberships" value={coverage.taxonomyMemberships} />
              <Row label="Task ratings" value={coverage.taskRatings} />
              <Row label="Skill ratings" value={coverage.skillRatings} />
              <Row label="Ability ratings" value={coverage.abilityRatings} />
              <Row label="Work activity ratings" value={coverage.workActivityRatings} />
              <Row label="Work context ratings" value={coverage.workContextRatings} />
              <Row label="O*NET related links" value={coverage.relatedOccupations} />
            </dl>
          </article>
          <article className="card">
            <h3>Missing-task-rating policy</h3>
            <p className="small">Policy v1 never imputes absent importance or frequency values. Incomplete tasks remain stored but are ineligible for any future weighted use.</p>
            <dl className="data-list">
              <Row label="Eligible tasks" value={coverage.weightingEligibleTasks} />
              <Row label="Ineligible tasks" value={coverage.weightingIneligibleTasks} />
              <Row label="Missing importance" value={coverage.tasksMissingImportance} />
              <Row label="Missing frequency" value={coverage.tasksMissingFrequency} />
              <Row label="Incomplete domains" value={coverage.incompleteDomainRows} />
              <Row label="JobsVsAI bridge links" value={coverage.productLinks} />
            </dl>
          </article>
        </div>
        <article className="card">
          <div className="card-heading"><div><h3>Incomplete domain coverage</h3><p className="small">Visible staging gaps; no missing values were fabricated. The list is capped at 100 rows.</p></div><Status tone={coverage.incompleteDomainRows ? "warn" : "ok"}>{coverage.incompleteDomainRows ? `${coverage.incompleteDomainRows} gaps` : "Complete"}</Status></div>
          {coverage.incompleteDomains.length ? <dl className="data-list coverage-list">
            {coverage.incompleteDomains.map((item) => <div key={`${item.onetSocCode}-${item.domain}`}>
              <dt>{item.onetSocCode} · {item.title}<small>{labelDomain(item.domain)} · {item.coverageStatus}</small></dt>
              <dd>{item.entityCount} entities / {item.ratingCount} ratings</dd>
            </div>)}
          </dl> : <p className="small">No incomplete source domains detected.</p>}
        </article>
      </section>}

      <article className="card">
        {data.runs.length ? <div className="admin-table import-table">
          <div className="admin-row admin-row-head"><b>Source</b><b>Version</b><b>Records</b><b>Completed</b><b>Status</b></div>
          {data.runs.map((run) => <div className="admin-row" key={String(run.id)}>
            <strong>{String(run.source ?? "Unknown source")}</strong>
            <span data-label="Version">{String(run.sourceVersion ?? "—")}</span>
            <span data-label="Records">{String(run.recordsWritten ?? 0)}</span>
            <span data-label="Completed">{formatDate(run.completedAt)}</span>
            <Status tone={tone(String(run.status))}>{String(run.status)}</Status>
          </div>)}
        </div> : <div className="empty-state compact"><h3>No external imports have run.</h3><p>No staged source import has completed.</p></div>}
      </article>
    </AdminShell>
  );
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return <article className="kpi"><span>{label}</span><strong>{value}</strong><small>Live import state</small></article>;
}
function Row({ label, value }: { label: string; value: string | number }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
function labelDomain(value: string) { return value.replaceAll("_", " "); }
function tone(status: string): "ok" | "warn" | "error" { return status === "failed" ? "error" : status === "pending" || status === "running" ? "warn" : "ok"; }
function formatDate(value: unknown) { return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(String(value))) : "—"; }
