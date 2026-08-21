import Link from "next/link";
import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminPhase5 } from "@/lib/api";

export const dynamic = "force-dynamic";

type Search = Record<string, string | string[] | undefined>;

export default async function Phase5Page({ searchParams }: { searchParams: Promise<Search> }) {
  const raw = await searchParams;
  const allowed = ["candidate_status", "exposure_min", "exposure_max", "replacement_min",
    "replacement_max", "confidence_min", "coverage_min", "soc", "warning",
    "provisional_sensitive", "limit", "offset"];
  const query = new URLSearchParams();
  for (const key of allowed) {
    const value = first(raw[key]);
    if (value) query.set(key, value);
  }
  if (!query.has("limit")) query.set("limit", "50");
  const data = await getAdminPhase5(query.toString());
  const report = data.report;
  const latest = data.runs[0];
  if (!report || !latest) return <AdminShell title="Phase 5 bounded corpus"><div className="notice">No Phase 5 run is available.</div></AdminShell>;
  const corpus = report.corpusSummary;
  const exact = report.exactReconciliation;
  const replayPassed = latest.replayMatchesPrevious === true;
  const currentOffset = Number(query.get("offset") ?? 0);
  const currentLimit = Number(query.get("limit") ?? 50);

  return <AdminShell title="Phase 5 — Bounded Corpus Scoring" eyebrow="878 scoring-ready occupations · candidate namespace only" action={<Status tone={replayPassed ? "ok" : "warn"}>{replayPassed ? "Exact replay" : "Replay pending"}</Status>}>
    <div className="notice"><strong>Production-isolated candidate dataset</strong><p>These scores are not public and do not replace production data. The 70% weighted-coverage gate remains enforced, provisional regulation/adoption/labour inputs remain visible, and archetype scoring remains disabled.</p></div>

    <div className="kpi-grid">
      <Kpi label="Attempted" value={corpus.scoringReadyOccupationsAttempted} note={`${corpus.totalSourceOccupations} total O*NET occupations`} />
      <Kpi label="Review ready" value={corpus.reviewReadyOccupations} note={`${corpus.blockedOccupations} blocked`} />
      <Kpi label="Task assessments" value={latest.taskAssessmentCount.toLocaleString()} note={`${latest.newMappingCount.toLocaleString()} new mappings`} />
      <Kpi label="Launch candidate" value={report.recommendedLaunchCohort.recommendedCount} note="Identified · not activated" />
    </div>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Corpus controls</span><h2>Isolation, replay, and gates</h2></div><Status tone={report.anomalySummary.bySeverity.error ? "error" : "ok"}>{report.anomalySummary.bySeverity.error ?? 0} errors</Status></div>
      <div className="admin-grid constraint-grid">
        <article className="card"><h3>Coverage</h3><dl className="data-list"><Row label="Review ready" value={corpus.reviewReadyOccupations} /><Row label="Coverage blocked" value={corpus.coverageBlockedOccupations} /><Row label="Confidence blocked above coverage" value={corpus.confidenceBlockedOccupations} /><Row label="Gate violations" value={String(exact.coverageGateViolations ?? 0)} /></dl></article>
        <article className="card"><h3>Mapping reuse</h3><dl className="data-list"><Row label="Exact task reuse" value={number(report.mappingReuseSummary.reused_exact_mappings)} /><Row label="Statement-hash reuse" value={number(report.mappingReuseSummary.reused_hash_mappings)} /><Row label="New deterministic mappings" value={number(report.mappingReuseSummary.new_mappings)} /><Row label="External AI / tokens" value={`${number(report.mappingReuseSummary.externalAiCalls)} / ${number(report.mappingReuseSummary.estimatedAiTokens)}`} /></dl></article>
        <article className="card"><h3>Anomalies</h3><dl className="data-list"><Row label="Total findings" value={report.anomalySummary.totalFindings} /><Row label="Occupations flagged" value={report.anomalySummary.occupationsFlagged} /><Row label="Warnings / errors" value={`${report.anomalySummary.bySeverity.warning ?? 0} / ${report.anomalySummary.bySeverity.error ?? 0}`} /><Row label="Provisional sensitivity" value={report.provisionalImpact.flaggedOccupations} /></dl></article>
        <article className="card"><h3>Isolation</h3><dl className="data-list"><Row label="Production occupation / task rows" value={`${data.isolation.productionOccupationScoreRows} / ${data.isolation.productionTaskScoreRows}`} /><Row label="Public occupations" value={data.isolation.publicOccupationRows} /><Row label="Phase 5 production/public writes" value={`${data.isolation.runsWithProductionWrites} / ${data.isolation.runsWithPublicActivations}`} /><Row label="Archetype scoring" value={data.isolation.archetypeLayerEnabled ? "Enabled" : "Disabled"} /></dl></article>
      </div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Corpus distributions</span><h2>Scale and variance checks</h2><p className="small">All calculated candidates are included; blocked scores remain diagnostic and are never publishable.</p></div><Status tone="ok">No saturation</Status></div>
      <div className="admin-grid constraint-grid">
        {(["weightedCoverage", "confidence", "aiExposure", "replacementRisk"] as const).map((key) => <Distribution key={key} name={label(key)} values={report.distributions[key]} />)}
      </div>
      <dl className="data-list"><Row label="Exposure ↔ Replacement correlation" value={`${report.correlation.aiExposureVsReplacementRisk.toFixed(4)} Pearson`} /><Row label="Namespace" value={data.namespace.namespaceVersion} /><Row label="Anomaly policy" value={data.namespace.anomalyPolicyVersion} /><Row label="Report hash" value={shortHash(report.inputHash)} /></dl>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Filterable corpus inspector</span><h2>{data.totalFiltered.toLocaleString()} matching occupations</h2></div><Status tone="warn">Candidate only</Status></div>
      <form className="form-grid" method="get">
        <label>Status<select name="candidate_status" defaultValue={first(raw.candidate_status)}><option value="">All</option><option value="scored">Review ready</option><option value="blocked">Blocked</option></select></label>
        <label>SOC prefix<input name="soc" defaultValue={first(raw.soc)} placeholder="e.g. 15-" /></label>
        <label>Minimum AI Exposure<input type="number" min="0" max="100" step="0.1" name="exposure_min" defaultValue={first(raw.exposure_min)} /></label>
        <label>Maximum AI Exposure<input type="number" min="0" max="100" step="0.1" name="exposure_max" defaultValue={first(raw.exposure_max)} /></label>
        <label>Minimum Replacement Risk<input type="number" min="0" max="100" step="0.1" name="replacement_min" defaultValue={first(raw.replacement_min)} /></label>
        <label>Maximum Replacement Risk<input type="number" min="0" max="100" step="0.1" name="replacement_max" defaultValue={first(raw.replacement_max)} /></label>
        <label>Minimum confidence<input type="number" min="0" max="100" step="0.1" name="confidence_min" defaultValue={first(raw.confidence_min)} /></label>
        <label>Minimum weighted coverage<input type="number" min="0" max="100" step="0.1" name="coverage_min" defaultValue={first(raw.coverage_min)} /></label>
        <label>Warning / anomaly<input name="warning" defaultValue={first(raw.warning)} placeholder="e.g. provisional_input_sensitivity" /></label>
        <label>Provisional sensitivity<select name="provisional_sensitive" defaultValue={first(raw.provisional_sensitive)}><option value="">All</option><option value="true">Flagged ≥3 points</option><option value="false">Below 3 points</option></select></label>
        <input type="hidden" name="limit" value={currentLimit} />
        <div className="form-actions full-field"><button className="button" type="submit">Apply filters</button><Link className="button secondary" href="/admin/phase5">Reset</Link></div>
      </form>
    </section>

    <section className="admin-inspector">
      <div className="admin-grid constraint-grid">{data.occupations.map((item) => <article className="card" key={item.occupationCode}>
        <div className="card-heading"><div><span className="section-kicker">{item.occupationCode}</span><h3>{item.title}</h3></div><Status tone={item.candidateStatus === "review_ready" ? "ok" : "warn"}>{item.candidateStatus === "review_ready" ? "Review ready" : "Blocked"}</Status></div>
        <dl className="data-list"><Row label="AI Exposure / Replacement" value={`${item.aiExposure.toFixed(1)} / ${item.replacementRisk.toFixed(1)}`} /><Row label="Confidence / Coverage" value={`${item.confidence.toFixed(1)} / ${item.weightedTaskCoverage.toFixed(1)}%`} /><Row label="Eligible / excluded tasks" value={`${item.eligibleTaskCount} / ${item.excludedTaskCount}`} /><Row label="Physical / human constraint" value={`${item.physicalPresence.toFixed(1)} / ${item.humanDependency.toFixed(1)}`} /><Row label="Provisional sensitivity" value={Number(item.provisionalSensitivity.maximumAbsoluteScoreImpact ?? 0).toFixed(2)} /><Row label="Anomalies" value={`${item.anomalyCount}${item.anomalyTypes.length ? ` · ${item.anomalyTypes.map(label).join(", ")}` : ""}`} /></dl>
        {item.blockingReasons.length > 0 && <div className="notice"><strong>Blocking reasons</strong><pre className="admin-json">{JSON.stringify(item.blockingReasons, null, 2)}</pre></div>}
        <details><summary>Drivers, constraints, proxies, versions, and reconciliation</summary><pre className="admin-json">{JSON.stringify({ topExposureTasks: item.topExposureTasks, topAutomationConstraints: item.topAutomationConstraints, augmentationHeavyTasks: item.augmentationHeavyTasks, structuralProxyInputs: item.structuralProxyInputs, provisionalSensitivity: item.provisionalSensitivity, warnings: item.warnings, formulaInputs: item.exactInputs, reconciliation: item.reconciliation, inputHash: item.inputHash }, null, 2)}</pre></details>
        <details><summary>Complete Phase 4D structural derivation</summary><pre className="admin-json">{JSON.stringify({ families: item.familyValues, baseComponents: item.proxyComponentContributions, exactInputs: item.proxyExactInputs, provisionalFlags: item.provisionalFlags, warnings: item.proxyWarnings, reconciliation: item.proxyReconciliation, inputHash: item.proxyInputHash }, null, 2)}</pre></details>
      </article>)}</div>
      <div className="form-actions">
        {currentOffset > 0 ? <Link className="button secondary" href={pageHref(query, Math.max(0, currentOffset - currentLimit))}>Previous</Link> : <span />}
        {currentOffset + data.occupations.length < data.totalFiltered && <Link className="button secondary" href={pageHref(query, currentOffset + currentLimit)}>Next</Link>}
      </div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Review queue</span><h2>Anomaly findings</h2><p className="small">Findings flag records for later review; they do not tune individual scores.</p></div><Status tone="warn">{report.anomalySummary.totalFindings} warnings</Status></div>
      <div className="admin-grid constraint-grid">{data.anomalies.slice(0, 40).map((item) => <article className="card" key={item.id}><span className="section-kicker">{label(item.anomalyType)} · {item.severity}</span><h3>{item.title ?? "Corpus-level check"}</h3><p>{item.explanation}</p><pre className="admin-json">{JSON.stringify({ metrics: item.metricValues, thresholds: item.thresholdValues }, null, 2)}</pre></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Manual launch planning</span><h2>Recommended first cohort: {report.recommendedLaunchCohort.recommendedCount}</h2><p className="small">Identified from review-ready candidates and ranked by provisional sensitivity, anomaly count, confidence, coverage, then SOC. Nothing is activated.</p></div><Status tone="warn">Not activated</Status></div>
      <details><summary>Selection policy and full 400-occupation recommendation</summary><pre className="admin-json">{JSON.stringify(report.recommendedLaunchCohort, null, 2)}</pre></details>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Append-only run history</span><h2>Phase 5 executions</h2></div><Status tone={replayPassed ? "ok" : "warn"}>{replayPassed ? "Replay exact" : "Check required"}</Status></div>
      <div className="admin-grid constraint-grid">{data.runs.map((run) => <article className="card" key={run.id}><h3>{label(run.runKind)}</h3><p className="small">{run.runVersion}</p><dl className="data-list"><Row label="Attempted / ready / blocked" value={`${run.attemptedOccupationCount} / ${run.scoredOccupationCount} / ${run.blockedOccupationCount}`} /><Row label="Tasks / new / exact / hash" value={`${run.taskAssessmentCount} / ${run.newMappingCount} / ${run.reusedExactMappingCount} / ${run.reusedHashMappingCount}`} /><Row label="AI calls / estimated tokens" value={`${run.externalAiCalls} / ${run.estimatedAiTokens}`} /><Row label="Production / public writes" value={`${run.productionScoreWrites} / ${run.publicActivations}`} /><Row label="Replay" value={run.replayMatchesPrevious == null ? "Baseline" : run.replayMatchesPrevious ? "Exact" : "Mismatch"} /><Row label="Dependency hash" value={shortHash(run.dependencyHash)} /></dl></article>)}</div>
    </section>
  </AdminShell>;
}

function Kpi({ label: name, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>{note}</small></article>; }
function Row({ label: name, value }: { label: string; value: string | number }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function Distribution({ name, values }: { name: string; values: { minimum: number; p10: number; median: number; p90: number; maximum: number; mean: number; standardDeviation: number } }) { return <article className="card"><h3>{name}</h3><dl className="data-list"><Row label="Mean / SD" value={`${values.mean.toFixed(2)} / ${values.standardDeviation.toFixed(2)}`} /><Row label="P10 / median / P90" value={`${values.p10.toFixed(1)} / ${values.median.toFixed(1)} / ${values.p90.toFixed(1)}`} /><Row label="Range" value={`${values.minimum.toFixed(1)}–${values.maximum.toFixed(1)}`} /></dl></article>; }
function first(value: string | string[] | undefined) { return Array.isArray(value) ? value[0] ?? "" : value ?? ""; }
function label(value: string) { return value.replaceAll("-", " ").replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase()); }
function number(value: number | undefined) { return Number(value ?? 0).toLocaleString(); }
function shortHash(value: string) { return `${value.slice(0, 12)}…${value.slice(-8)}`; }
function pageHref(query: URLSearchParams, offset: number) { const next = new URLSearchParams(query); next.set("offset", String(offset)); return `/admin/phase5?${next.toString()}`; }
