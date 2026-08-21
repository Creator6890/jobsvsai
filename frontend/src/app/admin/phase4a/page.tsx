import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminPhase4a, type AdminPhase4a } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Phase4aPage() {
  const data = await getAdminPhase4a();
  const latest = data.runs[0];
  const calibratedReplay = data.runs.find((run) => run.methodologyPhase === "4B" && run.runKind === "deterministic_replay");
  const passed = latest?.methodologyPhase === "4B" && latest.reconciliationStatus === "passed" && calibratedReplay?.replayMatchesPrevious === true && data.diagnostics.every((item) => item.reconciliation.passed);
  const tasksByOccupation = new Map<number, AdminPhase4a["tasks"]>();
  const excludedByOccupation = new Map<number, AdminPhase4a["excludedTasks"]>();
  for (const task of data.tasks) tasksByOccupation.set(task.pilotOccupationId, [...(tasksByOccupation.get(task.pilotOccupationId) ?? []), task]);
  for (const task of data.excludedTasks) excludedByOccupation.set(task.pilotOccupationId, [...(excludedByOccupation.get(task.pilotOccupationId) ?? []), task]);

  return (
    <AdminShell title="Phase 4B calibration" eyebrow="Phase 4A frozen-cohort comparison" action={<Status tone={passed ? "ok" : "error"}>{passed ? "Calibration checks passed" : "Calibration incomplete"}</Status>}>
      <div className="notice"><strong>Calibration-only namespace — not public or production scoring</strong><p>Phase 4B reuses the exact 12 occupations and 230 eligible Phase 4A mappings. It makes no mapping calls, uses deterministic formula changes, and keeps provisional proxy values isolated from public scores.</p></div>

      <div className="kpi-grid">
        <Kpi label="Pilot occupations" value={data.cohort.targetOccupationCount} note={data.cohort.cohortVersion} />
        <Kpi label="Eligible tasks" value={data.cohort.scoringEligibleMappings} note={`${data.cohort.excludedMappings} policy exclusions`} />
        <Kpi label="Latest task assessments" value={latest?.taskAssessmentCount ?? 0} note="Same Phase 4A inputs" />
        <Kpi label="New mapping calls" value={latest?.newAiMappingCalls ?? 0} note="Required to remain zero" />
      </div>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Before / after distributions</span><h2>Saturation diagnosis</h2><p className="small">Phase 4A formula-only baseline compared with the Phase 4B deterministic calibration.</p></div><Status tone={data.diagnostics.every((item) => item.reconciliation.passed) ? "ok" : "error"}>{data.diagnostics.length} reconciled metrics</Status></div>
        <div className="admin-grid capability-definition-grid">{data.diagnostics.map((metric) => <article className="card" key={`${metric.metricScope}-${metric.metricName}`}><span className="section-kicker">{metric.metricScope}</span><h3>{label(metric.metricName)}</h3><dl className="data-list"><Row label="Mean" value={`${metric.baselineSummary.mean.toFixed(1)} → ${metric.calibratedSummary.mean.toFixed(1)} (${signed(metric.deltaSummary.mean)})`} /><Row label="Median" value={`${metric.baselineSummary.median.toFixed(1)} → ${metric.calibratedSummary.median.toFixed(1)}`} /><Row label="Std. deviation" value={`${metric.baselineSummary.standardDeviation.toFixed(1)} → ${metric.calibratedSummary.standardDeviation.toFixed(1)}`} /><Row label="Scores ≥ 90" value={`${metric.baselineSummary.atOrAbove90} → ${metric.calibratedSummary.atOrAbove90}`} /><Row label="Range" value={`${metric.calibratedSummary.minimum.toFixed(1)}–${metric.calibratedSummary.maximum.toFixed(1)}`} /></dl></article>)}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Isolation and provenance</span><h2>{data.cohort.name}</h2><p className="small">{data.cohort.description}</p></div><Status tone="warn">{data.cohort.status}</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Score-blind mapping run</h3><dl className="data-list"><Row label="Run" value={data.cohort.mappingRunVersion} /><Row label="Provider / mapper" value={`${data.cohort.mappingProvider} · ${data.cohort.mappingModel}`} /><Row label="Prompt version" value={data.cohort.promptVersion} /><Row label="Input / output" value={`${data.cohort.inputTaskCount} / ${data.cohort.outputTaskCount}`} /><Row label="Prohibited-input attestation" value={data.cohort.prohibitedInputAttestation ? "Present" : "Missing"} /></dl></article>
          <article className="card"><h3>Runtime separation</h3><dl className="data-list"><Row label="Production occupation score rows" value={data.isolation.productionOccupationScoreRows} /><Row label="Legacy task score rows" value={data.isolation.legacyTaskScoreRows} /><Row label="Pilot score rows" value={data.isolation.pilotScoreRows} /><Row label="Pilot task assessment rows" value={data.isolation.pilotTaskAssessmentRows} /><Row label="Technical-frontier values used" value={data.isolation.technicalFrontierValues} /></dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Versioned provisional metadata model</span><h2>Adoption, resilience, and missing-constraint proxies</h2><p className="small">O*NET work-context and work-activity ratings are transformed without imputation. Missing or suppressed inputs are excluded, weights are renormalized, and confidence is penalized.</p></div><Status tone="warn">Calibration only</Status></div>
        <div className="admin-grid constraint-grid">{data.proxyModels.map((model) => <article className="card" key={model.id}><span className="section-kicker">{model.modelVersion}</span><h3>{model.name}</h3><p>{model.description}</p><dl className="data-list"><Row label="Source" value={model.sourceName} /><Row label="Status" value={label(model.status)} /></dl><details><summary>Exact model parameters and source policy</summary><pre className="admin-json">{JSON.stringify(model.parameters, null, 2)}</pre></details></article>)}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Versioned deterministic formulas</span><h2>Formula registry</h2><p className="small">Every run pins these immutable versions and their parameter payloads.</p></div><Status tone="ok">{data.taskFormulas.length + data.occupationFormulas.length} versions</Status></div>
        <div className="admin-grid capability-definition-grid">
          {[...data.taskFormulas, ...data.occupationFormulas.map((formula) => ({ ...formula, formulaType: "occupation_aggregation" }))].map((formula) => <article className="card" key={formula.formulaVersion}><span className="section-kicker">{label(formula.formulaType)}</span><h3>{formula.name}</h3><p>{formula.description}</p><details><summary>Exact parameters</summary><pre className="admin-json">{JSON.stringify(formula.parameters, null, 2)}</pre></details></article>)}
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Replay and recompute</span><h2>Calculation runs</h2><p className="small">Immutable inputs can be replayed or recomputed without generating mappings.</p></div><Status tone={passed ? "ok" : "error"}>{passed ? "Deterministic" : "Check required"}</Status></div>
        <div className="admin-grid constraint-grid">{data.runs.map((run) => <article className="card" key={run.id}><div className="card-heading"><div><span className="section-kicker">Phase {run.methodologyPhase}</span><h3>{label(run.runKind)}</h3><p className="small">{run.runVersion}</p></div><Status tone={run.reconciliationStatus === "passed" ? "ok" : "error"}>{run.reconciliationStatus}</Status></div><dl className="data-list"><Row label="Previous run" value={run.previousRunVersion ?? "Initial run"} /><Row label="Baseline run" value={run.baselineRunVersion ?? "—"} /><Row label="Proxy model" value={run.proxyModelVersion ?? "None"} /><Row label="Replay match" value={run.replayMatchesPrevious == null ? "Baseline" : run.replayMatchesPrevious ? "Exact match" : "Mismatch"} /><Row label="Reused mappings" value={run.reusedMappingCount} /><Row label="New mapping calls" value={run.newAiMappingCalls} /><Row label="Dependency hash" value={shortHash(run.dependencyHash)} /></dl></article>)}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Occupation comparison</span><h2>12-occupation pilot</h2><p className="small">Scores are provisional pilot outputs, not public JobsVsAI scores.</p></div><Status tone="warn">Pilot only</Status></div>
        <div className="admin-grid constraint-grid">{data.occupations.map((occupation) => <article className="card" key={occupation.pilotOccupationId}><div className="card-heading"><div><span className="section-kicker">{occupation.occupationCode}</span><h3>{occupation.sourceTitle}</h3></div><Status tone={occupation.scaleEligible ? "ok" : "warn"}>{occupation.scaleEligible ? "Scale eligible" : "Below coverage gate"}</Status></div><dl className="data-list"><Row label="AI Exposure" value={`${formatMaybe(occupation.baselineAiExposure)} → ${occupation.aiExposure.toFixed(1)}`} /><Row label="Replacement Risk" value={`${formatMaybe(occupation.baselineReplacementRisk)} → ${occupation.replacementRisk.toFixed(1)}`} /><Row label="Confidence" value={`${formatMaybe(occupation.baselineConfidence)} → ${occupation.confidence.toFixed(1)}`} /><Row label="Weighted coverage" value={`${occupation.weightedTaskCoverage.toFixed(1)}% · ${label(occupation.coverageGateStatus)}`} /><Row label="Coverage confidence penalty" value={occupation.confidencePenalty.toFixed(1)} /><Row label="Adoption pressure proxy" value={`${formatMaybe(occupation.adoptionPressure)} · ${occupation.proxyModelVersion}`} /><Row label="Structural resilience proxy" value={formatMaybe(occupation.labourMarketResilience)} /><Row label="Proxy confidence" value={formatMaybe(occupation.proxyConfidence)} /><Row label="Contribution reconciliation" value={occupation.reconciliation.passed ? "Passed" : "Failed"} /></dl>{occupation.substitutionReason && <p className="small"><strong>Substitution:</strong> {occupation.substitutionReason}</p>}<details><summary>Factor derivation</summary><dl className="data-list">{occupation.factorContributions.map((factor) => <Row key={factor.factor} label={`${label(factor.factor)}${factor.provisionalProxy ? " (provisional proxy)" : ""}`} value={`${factor.value.toFixed(1)} × ${factor.weight.toFixed(2)} = ${factor.weightedContribution.toFixed(2)}`} />)}</dl></details><details><summary>Proxy domains and provenance</summary><pre className="admin-json">{JSON.stringify({ domains: occupation.proxyDomainValues, contributions: occupation.proxyComponentContributions, inputs: occupation.proxyExactInputs, warnings: occupation.proxyWarnings, reconciliation: occupation.proxyReconciliation, inputHash: occupation.proxyInputHash }, null, 2)}</pre></details></article>)}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Full explainability path</span><h2>Occupation → task → requirements → Frontier evidence → constraints</h2><p className="small">Open any occupation, then any task, to inspect exact inputs and bottlenecks.</p></div><Status tone="ok">{data.tasks.length} task derivations</Status></div>
        {data.occupations.map((occupation) => {
          const tasks = tasksByOccupation.get(occupation.pilotOccupationId) ?? [];
          const excluded = excludedByOccupation.get(occupation.pilotOccupationId) ?? [];
          return <details className="card mapping-set-card pilot-occupation" key={occupation.pilotOccupationId}><summary>{occupation.sourceTitle} · {tasks.length} scored · {excluded.length} excluded</summary>
            {tasks.map((task) => <details className="pilot-task" key={task.id}><summary>{task.taskStatement}</summary>
              <div className="kpi-grid enrichment-kpis"><Kpi label="Capability fit" value={task.aiCapabilityFit.toFixed(1)} note="Geometric + bottleneck" /><Kpi label="Automation" value={task.automationFeasibility.toFixed(1)} note="Fit + environment" /><Kpi label="Augmentation" value={task.augmentationPotential.toFixed(1)} note="Human complement" /><Kpi label="Task exposure" value={task.taskAiExposure.toFixed(1)} note={`${task.confidence.toFixed(1)} confidence`} /></div>
              <div className="admin-grid constraint-grid"><article className="card"><h3>Capability requirements</h3>{task.capabilityContributions.map((requirement) => <details key={requirement.slug}><summary>{requirement.name} · {(requirement.weight * 100).toFixed(1)}% · level {requirement.requiredLevel.toFixed(0)}</summary><dl className="data-list"><Row label="Commercial AI value" value={requirement.currentCommercialAI.toFixed(0)} /><Row label="Capability match" value={requirement.capabilityMatch.toFixed(1)} /><Row label="Critical / bottleneck" value={`${requirement.criticalCapability ? "Critical" : "No"}${requirement.bottleneckCap == null ? "" : ` · cap ${requirement.bottleneckCap.toFixed(1)}`}`} /><Row label="Mapping / Frontier confidence" value={`${requirement.mappingConfidence.toFixed(0)} / ${requirement.frontierConfidence.toFixed(0)}`} /><Row label="Weighted log contribution" value={requirement.weightedLogContribution.toFixed(6)} /></dl><p className="small">{requirement.rationale}</p>{requirement.frontierEvidenceIds.map((id) => { const evidence = data.frontierEvidence.find((item) => item.id === id); return evidence ? <div className="notice" key={id}><strong>{evidence.benchmarkName} · {evidence.reportedResult}</strong><p>{evidence.sourceTier} / {evidence.sourceType} · {evidence.providerName ?? "provider n/a"} · {evidence.modelName ?? "model n/a"}</p><a href={evidence.sourceReference} target="_blank" rel="noreferrer">Evidence source ↗</a></div> : null; })}</details>)}</article>
                <article className="card"><h3>Environment constraints</h3><p className="small">Task-local mappings take precedence; approved occupation metadata proxies fill only the six defined missing domains and apply a {task.proxyConfidencePenalty.toFixed(1)} confidence penalty.</p><dl className="data-list">{task.constraintContributions.map((constraint) => <Row key={constraint.slug} label={`${label(constraint.slug)} · ${constraint.source === "occupation_metadata_proxy" ? "proxy" : constraint.explicitlyMapped ? "direct" : "unfilled"}${constraint.criticalConstraint ? " · critical" : ""}`} value={`${constraint.level.toFixed(0)} → ${constraint.transformedLevel.toFixed(1)} × ${constraint.fixedWeight.toFixed(2)} = ${constraint.burdenContribution.toFixed(2)}${constraint.bottleneckCap == null ? "" : ` · cap ${constraint.bottleneckCap.toFixed(1)}`}`} />)}</dl><details><summary>Exact versioned inputs</summary><pre className="admin-json">{JSON.stringify(task.exactInputs, null, 2)}</pre></details><p className="small">Input hash: {task.inputHash}</p></article></div>
            </details>)}
            {excluded.length > 0 && <details><summary>{excluded.length} policy-excluded task descriptions</summary><dl className="data-list">{excluded.map((task) => <Row key={task.onetTaskId} label={task.taskStatement} value={label(task.ambiguityState)} />)}</dl></details>}
          </details>;
        })}
      </section>
    </AdminShell>
  );
}

function Kpi({ label: name, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>{note}</small></article>; }
function Row({ label: name, value }: { label: string; value: string | number }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function label(value: string) { return value.replaceAll("-", " ").replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase()); }
function shortHash(value: string) { return `${value.slice(0, 12)}…${value.slice(-8)}`; }
function signed(value: number) { return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`; }
function formatMaybe(value: number | null) { return value == null ? "—" : value.toFixed(1); }
