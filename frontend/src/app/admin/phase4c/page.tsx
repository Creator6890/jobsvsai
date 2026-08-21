import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminPhase4c } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Phase4cPage() {
  const data = await getAdminPhase4c();
  const latest = data.runs[0];
  const blocked = data.occupations.filter((occupation) => !occupation.scaleEligible);
  const pairwiseIssues = data.pairwiseResults.filter((result) => !result.passed);
  const absoluteIssues = data.absoluteResults.filter((result) => !result.passed);
  const deterministic = latest?.replayMatchesPrevious === true && latest.reconciliationStatus === "passed";
  const safeForScale = deterministic && blocked.length === 0 && pairwiseIssues.length === 0 && absoluteIssues.length === 0;

  return (
    <AdminShell title="Phase 4C targeted validation" eyebrow="25-occupation cross-proxy stress test" action={<Status tone={safeForScale ? "ok" : "warn"}>{safeForScale ? "Scale gate passed" : "No-scale verdict"}</Status>}>
      <div className="notice"><strong>Targeted validation only — not corpus scoring</strong><p>The original 12 occupations are unchanged. Thirteen deliberately diverse occupations stress physical, human, regulatory, accountability, adoption and structural-resilience behavior. Scores remain private and production tables remain untouched.</p></div>

      <div className="kpi-grid">
        <Kpi label="Validation occupations" value={data.occupations.length} note={`${data.cohort.retainedOccupations} retained + ${data.cohort.addedOccupations} added`} />
        <Kpi label="Mappings reused" value={data.cohort.reusedMappings} note="Original rows referenced directly" />
        <Kpi label="New mapping rows" value={data.cohort.newMappingRows} note={`${data.cohort.generatedEligibleMappings} scoring eligible`} />
        <Kpi label="External AI calls" value={latest?.externalAiCalls ?? 0} note="Deterministic validation run" />
      </div>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Validation verdict</span><h2>Coverage and proxy behavior</h2><p className="small">The 70% weighted-coverage gate is unchanged. Pairwise expectations were defined before reading proxy outputs.</p></div><Status tone="warn">Not safe for corpus-wide scoring</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Coverage</h3><dl className="data-list"><Row label="Scale-eligible occupations" value={`${data.occupations.length - blocked.length} / ${data.occupations.length}`} /><Row label="Blocked occupations" value={blocked.length} /><Row label="Insufficient mapping attempts" value={data.cohort.insufficientMappingAttempts} /><Row label="Intentionally unmapped after gate" value={data.cohort.unmappedAfterGate} /></dl><p className="small">{blocked.map((occupation) => `${occupation.title} (${occupation.weightedTaskCoverage.toFixed(1)}%)`).join(" · ")}</p></article>
          <article className="card"><h3>Directional proxy checks</h3><dl className="data-list"><Row label="Pairwise checks passed" value={`${data.pairwiseResults.length - pairwiseIssues.length} / ${data.pairwiseResults.length}`} /><Row label="Weak-direction warnings" value={pairwiseIssues.filter((item) => item.severity === "warning").length} /><Row label="Reversed failures" value={pairwiseIssues.filter((item) => item.severity === "failure").length} /><Row label="Absolute-band exceptions" value={absoluteIssues.length} /></dl></article>
          <article className="card"><h3>Runtime isolation</h3><dl className="data-list"><Row label="Production occupation rows" value={data.isolation.productionOccupationScoreRows} /><Row label="Production task rows" value={data.isolation.productionTaskScoreRows} /><Row label="Phase 4C score rows" value={data.isolation.phase4cScoreRows} /><Row label="Runs with AI calls" value={data.isolation.runsWithAiCalls} /></dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Proxy exceptions</span><h2>Directional and absolute failures</h2><p className="small">A warning preserves the correct ordering but misses the predeclared minimum separation. Absolute bands are diagnostic expectations, not score adjustments.</p></div><Status tone={pairwiseIssues.some((item) => item.severity === "failure") ? "error" : "warn"}>{pairwiseIssues.length + absoluteIssues.length} findings</Status></div>
        <div className="admin-grid constraint-grid">
          {pairwiseIssues.map((result) => <article className="card" key={result.expectationId}><span className="section-kicker">{label(result.proxyMetric)} · {result.severity}</span><h3>{result.higherOccupationTitle} vs {result.lowerOccupationTitle}</h3><p>{result.rationale}</p><dl className="data-list"><Row label="Observed values" value={`${result.higherValue.toFixed(1)} vs ${result.lowerValue.toFixed(1)}`} /><Row label="Observed / required delta" value={`${result.observedDelta.toFixed(1)} / ${result.minimumDelta.toFixed(1)}`} /></dl></article>)}
          {absoluteIssues.map((result) => <article className="card" key={`${result.occupationCode}-${result.proxyMetric}`}><span className="section-kicker">Absolute-band exception</span><h3>{result.occupationTitle}</h3><dl className="data-list"><Row label="Proxy" value={label(result.proxyMetric)} /><Row label="Expected band" value={label(result.expectedBand)} /><Row label="Observed value" value={result.observedValue.toFixed(1)} /></dl><p className="small">{result.thresholdPolicy}</p></article>)}
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Cross-occupation inspector</span><h2>All 25 validation occupations</h2><p className="small">Each card exposes selection rationale, mapping scope, coverage, calibrated outputs and complete proxy domains.</p></div><Status tone="warn">Provisional</Status></div>
        <div className="admin-grid constraint-grid">{data.occupations.map((occupation) => <article className="card" key={occupation.validationOccupationId}><div className="card-heading"><div><span className="section-kicker">{occupation.occupationCode} · {label(occupation.cohortRole)}</span><h3>{occupation.title}</h3></div><Status tone={occupation.scaleEligible ? "ok" : "warn"}>{occupation.scaleEligible ? "Coverage passed" : "Blocked"}</Status></div><p>{occupation.selectionRationale}</p><dl className="data-list"><Row label="AI exposure / replacement" value={`${occupation.aiExposure.toFixed(1)} / ${occupation.replacementRisk.toFixed(1)}`} /><Row label="Coverage / confidence" value={`${occupation.weightedTaskCoverage.toFixed(1)}% / ${occupation.confidence.toFixed(1)}`} /><Row label="Reused / generated" value={`${occupation.reused} / ${occupation.generated}`} /><Row label="Insufficient / after gate" value={`${occupation.insufficient} / ${occupation.afterGate}`} /><Row label="Physical presence" value={domain(occupation, "physical-presence")} /><Row label="Environment variability" value={domain(occupation, "environment-variability")} /><Row label="Human dependency" value={domain(occupation, "human-dependency")} /><Row label="Regulation" value={domain(occupation, "regulation")} /><Row label="Accountability" value={domain(occupation, "accountability")} /><Row label="Consequence severity" value={domain(occupation, "consequence-severity")} /><Row label="Adoption pressure" value={occupation.adoptionPressure.toFixed(1)} /><Row label="Structural resilience" value={occupation.labourMarketResilience.toFixed(1)} /></dl><details><summary>Expected behavior and full provenance</summary><pre className="admin-json">{JSON.stringify({ expected: occupation.expectedProxyBehavior, stressDimensions: occupation.stressDimensions, proxyModelVersion: occupation.proxyModelVersion, contributions: occupation.componentContributions, exactInputs: occupation.proxyExactInputs, warnings: occupation.proxyWarnings, reconciliation: occupation.proxyReconciliation, inputHash: occupation.proxyInputHash }, null, 2)}</pre></details></article>)}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Deterministic execution</span><h2>Validation runs</h2></div><Status tone={deterministic ? "ok" : "error"}>{deterministic ? "Exact replay" : "Check required"}</Status></div>
        <div className="admin-grid constraint-grid">{data.runs.map((run) => <article className="card" key={run.id}><h3>{label(run.runKind)}</h3><p className="small">{run.runVersion}</p><dl className="data-list"><Row label="Previous run" value={run.previousRunVersion ?? "Initial validation"} /><Row label="Replay match" value={run.replayMatchesPrevious == null ? "Baseline" : run.replayMatchesPrevious ? "Exact" : "Mismatch"} /><Row label="Task assessments" value={run.taskAssessmentCount} /><Row label="New / reused mappings" value={`${run.newMappingCount} / ${run.reusedMappingCount}`} /><Row label="External AI calls" value={run.externalAiCalls} /><Row label="Mapping-scope hash" value={shortHash(run.mappingScopeHash)} /><Row label="Dependency hash" value={shortHash(run.dependencyHash)} /></dl></article>)}</div>
      </section>
    </AdminShell>
  );
}

function Kpi({ label: name, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>{note}</small></article>; }
function Row({ label: name, value }: { label: string; value: string | number }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function label(value: string) { return value.replaceAll("-", " ").replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase()); }
function shortHash(value: string) { return `${value.slice(0, 12)}…${value.slice(-8)}`; }
function domain(occupation: { domainValues: Record<string, { value: number }> }, key: string) { return occupation.domainValues[key].value.toFixed(1); }
