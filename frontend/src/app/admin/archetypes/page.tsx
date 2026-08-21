import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminArchetypes } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ArchetypesPage() {
  const data = await getAdminArchetypes();
  if (!data.model) return <AdminShell title="Occupational archetypes"><div className="notice">No archetype model has been discovered.</div></AdminShell>;
  const latest = data.runs[0];
  const singletonCount = data.archetypes.filter((item) => item.qualityMetrics.singleton).length;
  const issues = data.validations.filter((item) => item.archetypeOutcome !== "pass");
  const regressions = data.validations.filter((item) => item.regressed);
  const blocked = data.occupations.filter((item) => !item.scaleEligible);
  const exactReplay = latest?.replayMatchesPrevious === true;
  const adopt = exactReplay && regressions.length === 0 && issues.length === 0 && blocked.length === 0;

  return <AdminShell title="Occupational Archetype Layer v1" eyebrow="Draft additive scoring enrichment" action={<Status tone={adopt ? "ok" : "warn"}>{adopt ? "Adopt" : "Do not adopt"}</Status>}>
    <div className="notice"><strong>Disabled, private and reversible</strong><p>The global feature flag is off. This inspector shows an isolated pilot on the existing 25-occupation Phase 4C cohort; O*NET, mappings, Frontier values, production scores and the public site are unchanged.</p></div>

    <div className="kpi-grid">
      <Kpi label="Candidate archetypes" value={data.archetypes.length} note={`${data.model.featureSchema.featureCount} work-characteristic features`} />
      <Kpi label="Discovery occupations" value={data.archetypes.reduce((sum, item) => sum + item.memberCount, 0)} note={`${data.model.featureSchema.excludedOccupationCount} low-coverage exclusions`} />
      <Kpi label="Phase 4C occupations" value={data.occupations.length} note={`${blocked.length} remain coverage-blocked`} />
      <Kpi label="External AI calls" value={latest?.externalAiCalls ?? 0} note="Offline deterministic discovery" />
    </div>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Layer controls</span><h2>Isolation and verdict</h2><p className="small">A pilot override is recorded per run; the global flag remains disabled.</p></div><Status tone="warn">No-adopt verdict</Status></div>
      <div className="admin-grid constraint-grid">
        <article className="card"><h3>Feature flag</h3><dl className="data-list"><Row label="Layer version" value={data.featureFlag.layerVersion} /><Row label="Globally enabled" value={data.featureFlag.enabled ? "Yes" : "No"} /><Row label="Production allowed" value={data.featureFlag.productionAllowed ? "Yes" : "No"} /><Row label="Model status" value={label(data.model.status)} /></dl></article>
        <article className="card"><h3>Validation</h3><dl className="data-list"><Row label="Exact deterministic replay" value={exactReplay ? "Passed" : "Not established"} /><Row label="Outcome regressions" value={regressions.length} /><Row label="Remaining warnings/failures" value={issues.length} /><Row label="Singleton clusters" value={singletonCount} /></dl></article>
        <article className="card"><h3>Runtime isolation</h3><dl className="data-list"><Row label="Production occupation rows" value={data.isolation.productionOccupationScoreRows} /><Row label="Production task rows" value={data.isolation.productionTaskScoreRows} /><Row label="Pilot score rows" value={data.isolation.pilotScoreRows} /><Row label="Runs with AI calls" value={data.isolation.runsWithAiCalls} /><Row label="Runs regenerating mappings" value={data.isolation.runsWithRegeneratedMappings} /></dl></article>
      </div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Discovered structure</span><h2>28 candidate work-characteristic archetypes</h2><p className="small">Names are generated after clustering from leading O*NET features and representative occupations. SOC, titles and industry are excluded from discovery features.</p></div><Status tone="warn">Human interpretation pending</Status></div>
      <div className="admin-grid constraint-grid">{data.archetypes.map((item) => <article className="card" key={item.id}><span className="section-kicker">{item.archetypeCode} · {item.memberCount} members</span><h3>{item.name}</h3><p>{item.description}</p><dl className="data-list"><Row label="Mean separation" value={item.qualityMetrics.meanSeparation.toFixed(3)} /><Row label="Feature completeness" value={`${item.qualityMetrics.meanFeatureCompleteness.toFixed(1)}%`} /><Row label="Secondary memberships" value={item.secondaryMemberships} /><Row label="Representatives" value={item.representativeOccupations.slice(0, 3).map((row) => row.title).join(" · ")} /></dl><details><summary>Baselines, features and provenance</summary><pre className="admin-json">{JSON.stringify({ topFeatures: item.topFeatures, representatives: item.representativeOccupations, quality: item.qualityMetrics, baselines: item.baselines }, null, 2)}</pre></details></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Bounded Phase 4C overlay</span><h2>Prior + occupation-source adjustment</h2><p className="small">Every proxy exposes its archetype baseline, O*NET-derived occupation evidence, prior weight, adjustment, result, confidence and reconciliation.</p></div><Status tone="warn">25 occupations only</Status></div>
      <div className="admin-grid constraint-grid">{data.occupations.map((item) => <article className="card" key={item.occupationCode}><div className="card-heading"><div><span className="section-kicker">{item.occupationCode} · {item.primaryCode}</span><h3>{item.title}</h3></div><Status tone={item.scaleEligible ? "ok" : "warn"}>{item.scaleEligible ? "Coverage passed" : "Blocked"}</Status></div><p className="small">{item.primaryName}</p><dl className="data-list"><Row label="Membership strength / confidence" value={`${item.primaryStrength.toFixed(1)} / ${item.primaryConfidence.toFixed(1)}`} /><Row label="Secondary archetype" value={item.secondaryCode ?? "None"} /><Row label="AI exposure Δ" value={signed(item.aiExposureDelta)} /><Row label="Replacement risk Δ" value={signed(item.replacementRiskDelta)} /><Row label="Confidence Δ" value={signed(item.confidenceDelta)} /><Row label="Coverage" value={`${item.weightedTaskCoverage.toFixed(1)}%`} /></dl><details><summary>All structural adjustments</summary><pre className="admin-json">{JSON.stringify({ adjustments: item.adjustments, warnings: item.warnings }, null, 2)}</pre></details></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Predeclared validation</span><h2>Phase 4C before/after findings</h2></div><Status tone="warn">{issues.length} unresolved</Status></div>
      <div className="admin-grid constraint-grid">{issues.map((item) => <article className="card" key={`${item.validationType}-${item.validationKey}`}><span className="section-kicker">{label(item.validationType)} · {label(item.structuralDimension)}</span><h3>{item.validationKey}</h3><p>{item.finding}</p><dl className="data-list"><Row label="Phase 4C outcome" value={label(item.baselineOutcome)} /><Row label="Archetype outcome" value={label(item.archetypeOutcome)} /><Row label="Regression" value={item.regressed ? "Yes" : "No"} /></dl></article>)}</div>
    </section>

    <section className="admin-inspector">
      <div className="card-heading"><div><span className="section-kicker">Append-only runs</span><h2>Execution history</h2></div><Status tone={exactReplay ? "ok" : "error"}>{exactReplay ? "Exact replay" : "Check required"}</Status></div>
      <div className="admin-grid constraint-grid">{data.runs.map((run) => <article className="card" key={run.id}><h3>{label(run.runKind)}</h3><p className="small">{run.runVersion}</p><dl className="data-list"><Row label="Baseline" value={run.baselineRunVersion} /><Row label="Previous" value={run.previousRunVersion ?? "Initial pilot"} /><Row label="Occupations / tasks" value={`${run.occupationCount} / ${run.taskAssessmentCount}`} /><Row label="Replay" value={run.replayMatchesPrevious == null ? "Baseline" : run.replayMatchesPrevious ? "Exact" : "Mismatch"} /><Row label="Dependency hash" value={shortHash(run.dependencyHash)} /></dl></article>)}</div>
    </section>
  </AdminShell>;
}

function Kpi({ label: name, value, note }: { label: string; value: string | number; note: string }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>{note}</small></article>; }
function Row({ label: name, value }: { label: string; value: string | number }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function label(value: string) { return value.replaceAll("-", " ").replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase()); }
function signed(value: number) { return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`; }
function shortHash(value: string) { return `${value.slice(0, 12)}…${value.slice(-8)}`; }
