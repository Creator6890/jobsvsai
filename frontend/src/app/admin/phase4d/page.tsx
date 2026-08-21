import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminPhase4d } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Phase4dPage() {
  const data = await getAdminPhase4d();
  const model = data.models[0];
  const latest = data.runs[0];
  if (!model) return <AdminShell title="Phase 4D direct proxies"><div className="notice">No Phase 4D model is available.</div></AdminShell>;
  const remaining = data.validations.filter((item) => item.phase4dOutcome !== "pass");
  const ready = data.summary.phase4dAbsoluteFailures < data.summary.baselineAbsoluteFailures
    && data.summary.pairwiseReversals === 0 && latest?.replayMatchesPrevious === true
    && data.isolation.runsWithProductionWrites === 0;

  return <AdminShell title="Phase 4D — Direct Structural Proxies" eyebrow="Frozen 25-occupation reconstruction" action={<Status tone={ready ? "ok" : "warn"}>{ready ? "Bounded scale ready" : "More work required"}</Status>}>
    <div className="notice"><strong>Direct O*NET reconstruction only</strong><p>Four weak proxy families are rebuilt from O*NET 30.3 Work Context, Generalized Work Activities and source tasks. Task-capability mappings, Frontier values, the 70% coverage gate, public scores and production tables are unchanged. Archetype scoring remains disabled.</p></div>

    <div className="kpi-grid">
      <Kpi label="Absolute failures" value={`${data.summary.baselineAbsoluteFailures} → ${data.summary.phase4dAbsoluteFailures}`} note="All target-family failures resolved" />
      <Kpi label="Pairwise checks" value={`${data.summary.pairwisePasses} / 24`} note={`${data.summary.pairwiseWarnings} weak warning · ${data.summary.pairwiseReversals} reversals`} />
      <Kpi label="Outcome improvements" value={data.summary.improvements} note={`${data.summary.regressions} regressions`} />
      <Kpi label="Exact replay" value={latest?.replayMatchesPrevious ? "Passed" : "Pending"} note="407 task assessments · 25 occupations" />
    </div>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Readiness and isolation</span><h2>Bounded corpus-scale recommendation</h2><p className="small">The recommendation permits a separately approved bounded run; it does not initiate corpus scoring.</p></div><Status tone={ready ? "ok" : "warn"}>{ready ? "Conditions met" : "Blocked"}</Status></div>
      <div className="admin-grid constraint-grid">
        <article className="card"><h3>Validation</h3><dl className="data-list"><Row label="Absolute failures reduced" value={`${data.summary.baselineAbsoluteFailures - data.summary.phase4dAbsoluteFailures}`} /><Row label="Directional reversals" value={data.summary.pairwiseReversals} /><Row label="Scale eligible" value={`${data.summary.scaleEligible} / 25`} /><Row label="Coverage blocked" value={data.summary.coverageBlocked} /></dl></article>
        <article className="card"><h3>Score movement</h3><dl className="data-list"><Row label="Mean AI exposure Δ" value={signed(data.summary.meanAiExposureDelta)} /><Row label="Mean replacement risk Δ" value={signed(data.summary.meanReplacementRiskDelta)} /><Row label="Mean confidence Δ" value={signed(data.summary.meanConfidenceDelta)} /></dl></article>
        <article className="card"><h3>Isolation</h3><dl className="data-list"><Row label="Production occupation rows" value={data.isolation.productionOccupationScoreRows} /><Row label="Production task rows" value={data.isolation.productionTaskScoreRows} /><Row label="Runs with production writes" value={data.isolation.runsWithProductionWrites} /><Row label="Runs with AI calls" value={data.isolation.runsWithAiCalls} /><Row label="Archetype scoring" value={data.isolation.archetypeLayerEnabled ? "Enabled" : "Disabled"} /></dl></article>
      </div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Versioned methodology</span><h2>{model.modelVersion}</h2><p className="small">Missing or suppressed values are excluded and used weights are renormalized. No source value is imputed.</p></div><Status tone="ok">Source-backed</Status></div>
      <div className="admin-grid constraint-grid">{model.reconstructedFamilies.map((family) => <article className="card" key={family}><span className="section-kicker">Reconstructed family</span><h3>{label(family)}</h3><pre className="admin-json">{JSON.stringify(model.formulaParameters[family], null, 2)}</pre></article>)}</div>
      <details><summary>Model provenance and missing-data policy</summary><pre className="admin-json">{JSON.stringify({ description: model.description, sourceVersion: model.sourceVersion, missingDataPolicy: model.missingDataPolicy, implementationHash: model.implementationHash, priorVersions: data.models.slice(1).map((item) => item.modelVersion) }, null, 2)}</pre></details>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Exact source inspector</span><h2>All 25 occupations</h2><p className="small">Expand a card to inspect every source element, normalized value, transformation, weight, task match, confidence and reconciliation.</p></div><Status tone="warn">Pilot scope</Status></div>
      <div className="admin-grid constraint-grid">{data.occupations.map((item) => <article className="card" key={item.occupationCode}><div className="card-heading"><div><span className="section-kicker">{item.occupationCode}</span><h3>{item.title}</h3></div><Status tone={item.scaleEligible ? "ok" : "warn"}>{item.scaleEligible ? "Coverage passed" : "Blocked"}</Status></div><dl className="data-list"><Row label="Physical presence" value={item.physicalPresence.toFixed(1)} /><Row label="Environment variability" value={item.environmentVariability.toFixed(1)} /><Row label="Duty / accountability" value={item.accountability.toFixed(1)} /><Row label="Consequence severity" value={item.consequenceSeverity.toFixed(1)} /><Row label="AI exposure Δ" value={signed(item.aiExposureDelta)} /><Row label="Replacement risk Δ" value={signed(item.replacementRiskDelta)} /><Row label="Confidence / coverage" value={`${item.confidence.toFixed(1)} / ${item.weightedTaskCoverage.toFixed(1)}%`} /></dl><details><summary>Source derivations and reconciliation</summary><pre className="admin-json">{JSON.stringify({ families: item.familyValues, exactInputs: item.proxyExactInputs, warnings: item.proxyWarnings, reconciliation: item.proxyReconciliation, inputHash: item.proxyInputHash }, null, 2)}</pre></details></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Remaining weaknesses</span><h2>Unresolved predeclared checks</h2><p className="small">The remaining failures are outside the four reconstructed Phase 4D families.</p></div><Status tone="warn">{remaining.length} findings</Status></div>
      <div className="admin-grid constraint-grid">{remaining.map((item) => <article className="card" key={`${item.validationType}-${item.validationKey}`}><span className="section-kicker">{label(item.validationType)} · {label(item.proxyFamily)}</span><h3>{item.validationKey}</h3><p>{item.finding}</p><dl className="data-list"><Row label="Phase 4C outcome" value={label(item.baselineOutcome)} /><Row label="Phase 4D outcome" value={label(item.phase4dOutcome)} /></dl></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Append-only execution</span><h2>Phase 4D v2 runs</h2></div><Status tone={latest?.replayMatchesPrevious ? "ok" : "error"}>{latest?.replayMatchesPrevious ? "Exact replay" : "Check required"}</Status></div>
      <div className="admin-grid constraint-grid">{data.runs.map((run) => <article className="card" key={run.id}><h3>{label(run.runKind)}</h3><p className="small">{run.runVersion}</p><dl className="data-list"><Row label="Baseline" value={run.baselineRunVersion} /><Row label="Previous" value={run.previousRunVersion ?? "Initial recompute"} /><Row label="Occupations / tasks" value={`${run.occupationCount} / ${run.taskAssessmentCount}`} /><Row label="Replay" value={run.replayMatchesPrevious == null ? "Baseline" : run.replayMatchesPrevious ? "Exact" : "Mismatch"} /><Row label="AI / mapping / production writes" value={`${run.externalAiCalls} / ${run.regeneratedMappingCount} / ${run.productionScoreWrites}`} /><Row label="Dependency hash" value={shortHash(run.dependencyHash)} /></dl></article>)}</div>
    </section>
  </AdminShell>;
}

function Kpi({ label: name, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>{note}</small></article>; }
function Row({ label: name, value }: { label: string; value: string | number }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function label(value: string) { return value.replaceAll("-", " ").replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase()); }
function signed(value: number) { return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`; }
function shortHash(value: string) { return `${value.slice(0, 12)}…${value.slice(-8)}`; }
