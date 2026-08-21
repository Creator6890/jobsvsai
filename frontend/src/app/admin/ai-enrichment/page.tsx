import { AdminShell, Status } from "@/components/admin/AdminShell";
import { getAdminAiEnrichment } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AiEnrichmentPage() {
  const data = await getAdminAiEnrichment();
  const taxonomy = data.taxonomies[0];
  const environment = data.environmentTaxonomies[0];
  const rubric = data.rubrics[0];
  const gold = data.goldDatasets.find((dataset) => dataset.datasetVersion === "gold-v1-representative-test") ?? data.goldDatasets[0];
  const benchmark = data.mapperBenchmarks.find((dataset) => dataset.datasetVersion === "gold-v1-175-pending-human-review")!;
  const candidate = data.candidateRuns[0];
  const gate = data.acceptanceGates[0];
  const mvpPolicy = data.mvpEvidencePolicies[0];
  const frontierIndex = data.frontierIndexes[0];
  const commercialTrack = data.frontierTracks.find((track) => track.trackCode === "commercially_deployable");
  const technicalTrack = data.frontierTracks.find((track) => track.trackCode === "technical_frontier");
  const commercialEntries = data.frontierEntries.filter((entry) => entry.trackCode === "commercially_deployable");
  const rubricValidation = data.rubricValidation[0];
  const valid = data.validation.invalidMappingSets === 0 && data.validation.invalidSnapshots === 0 && data.validation.invalidConstraintMappings === 0 && data.validation.invalidAssessments === 0 && rubricValidation.rubricValid && rubricValidation.invalidGoldDatasets === 0 && mvpPolicy.status === "active" && !mvpPolicy.humanGoldRequired && frontierIndex.indexValid;
  return (
    <AdminShell
      title="AI capability taxonomy"
      eyebrow="Private enrichment layer"
      action={<Status tone={valid ? "ok" : "error"}>{valid ? "Architecture valid" : "Validation failed"}</Status>}
    >
      <div className="notice">
        <strong>MVP evidence policy active; provisional Frontier Index values remain score-isolated</strong>
        <p>The policy can admit structurally valid, sufficiently evidenced provisional mappings without human gold. The 2026-Q3 capability assessment is inspectable evidence data only and does not modify O*NET source data, legacy task AI scores, occupation scores, recommendations, or public pages.</p>
      </div>
      <div className="kpi-grid enrichment-kpis">
        <Kpi label="Capabilities" value={data.capabilities.length} />
        <Kpi label="Test mapping sets" value={data.mappingSets.length} />
        <Kpi label="Constraints" value={data.constraints.length} />
        <Kpi label="Gold tasks" value={gold.items} />
      </div>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Mapping rubric</span><h2>{rubric.name}</h2><p className="small">{rubric.version} · documentation and validation only</p></div><Status tone="warn">{rubric.status}</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Meaningful mapping rules</h3><dl className="data-list">
            <Row label="Minimum capability weight" value={formatWeight(rubric.minimumMeaningfulWeight)} />
            <Row label="Dominant capability threshold" value={formatWeight(rubric.dominantWeightThreshold)} />
            <Row label="Maximum capabilities per task" value={rubric.maximumCapabilitiesPerTask} />
            <Row label="Minimum requirement level" value={rubric.minimumMeaningfulRequirementLevel} />
            <Row label="Minimum constraint level" value={rubric.minimumMeaningfulConstraintLevel} />
            <Row label="Ambiguity confidence ceiling" value={rubric.ambiguityConfidenceCeiling} />
          </dl></article>
          <article className="card"><h3>Confidence states</h3><dl className="data-list">{data.confidenceStates.map((state) => <div key={state.code}><dt>{state.name}<small>{state.definition}</small></dt><dd>{state.minimumConfidence}–{state.maximumConfidence}</dd></div>)}</dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">MVP mapping policy</span><h2>{mvpPolicy.name}</h2><p className="small">{mvpPolicy.policyVersion} · {label(mvpPolicy.policyScope)}</p></div><Status tone="ok">{mvpPolicy.status}</Status></div>
        <div className="notice"><strong>Human gold is not required for provisional scoring eligibility</strong><p>Human review and gold-standard evaluation remain available as a separate research-grade path. Every MVP mapping must independently pass deterministic structure, provenance, confidence, evidence, coverage, ambiguity, and review-state checks.</p></div>
        <div className="kpi-grid enrichment-kpis">
          <Kpi label="AI mapping runs" value={mvpPolicy.aiMappingRuns} />
          <Kpi label="Task mappings" value={mvpPolicy.aiTaskMappings} />
          <Kpi label="Eligible mappings" value={mvpPolicy.scoringEligibleMappings} />
          <Kpi label="Failed mappings" value={mvpPolicy.failedMappings} />
        </div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Confidence and coverage</h3><dl className="data-list"><Row label="Minimum mapping confidence" value={mvpPolicy.minimumMappingConfidence} /><Row label="Minimum dimension confidence" value={mvpPolicy.minimumDimensionConfidence} /><Row label="Evidence coverage" value={formatRatio(mvpPolicy.minimumEvidencedDimensionCoverage)} /><Row label="Rationale coverage" value={formatRatio(mvpPolicy.minimumRationaleCoverage)} /><Row label="Capability dimensions" value={`${mvpPolicy.minimumCapabilityDimensions}–${mvpPolicy.maximumCapabilityDimensions}`} /></dl></article>
          <article className="card"><h3>Eligibility controls</h3><dl className="data-list"><Row label="Deterministic structural validation" value={mvpPolicy.requireIndependentStructuralValidation ? "Required" : "Optional"} /><Row label="Model provenance" value={mvpPolicy.requireModelProvenance ? "Required" : "Optional"} /><Row label="Prompt/version provenance" value={mvpPolicy.requirePromptProvenance ? "Required" : "Optional"} /><Row label="Ambiguous scope eligible" value={mvpPolicy.allowAmbiguousScope ? "Yes" : "No"} /><Row label="Insufficient descriptions eligible" value={mvpPolicy.allowInsufficientDescription ? "Yes" : "No"} /><Row label="Allowed review states" value={mvpPolicy.allowedScoringReviewStates.map(label).join(", ")} /></dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Frontier AI Capability Index</span><h2>{frontierIndex.name}</h2><p className="small">{frontierIndex.indexVersion} · {frontierIndex.taxonomyVersion} · {frontierIndex.methodologyVersion}</p></div><Status tone="warn">{frontierIndex.status}</Status></div>
        <div className="notice"><strong>2026-Q3 commercial assessment populated provisionally</strong><p>All 15 supplied commercially deployable values are stored with confidence, rationale and primary evidence. The technical-frontier track is structurally separate and remains empty because no approved technical values were supplied. Neither track is connected to occupation scoring.</p></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Index reconciliation</h3><dl className="data-list"><Row label="Expected capabilities" value={frontierIndex.expectedCapabilityCount} /><Row label="Capability values" value={frontierIndex.capabilityValues} /><Row label="Evidence records" value={frontierIndex.evidenceRecords} /><Row label="Score scale" value={`${frontierIndex.scoreScaleMin}–${frontierIndex.scoreScaleMax}`} /><Row label="As-of date" value={frontierIndex.asOfDate ?? commercialTrack?.assessmentDate ?? "Not assigned"} /></dl></article>
          <article className="card"><h3>Current state</h3><dl className="data-list"><Row label="Assessment tracks" value={`${frontierIndex.populatedTracks} populated / ${frontierIndex.assessmentTracks} defined`} /><Row label="Provisional values" value={frontierIndex.provisionalValues} /><Row label="Index validation" value={frontierIndex.indexValid ? "Valid draft" : "Invalid"} /><Row label="Production score effect" value="None" /><Row label="Task scoring effect" value="None" /><Row label="Public activation" value="Not active" /></dl></article>
        </div>
        <div className="admin-grid constraint-grid">
          {commercialTrack && <article className="card"><div className="card-heading"><div><h3>{commercialTrack.name}</h3><p className="small">{commercialTrack.description}</p></div><Status tone="warn">{commercialTrack.status}</Status></div><dl className="data-list"><Row label="Assessment date" value={commercialTrack.assessmentDate ?? "—"} /><Row label="Capability values" value={`${commercialTrack.capabilityValues} / ${commercialTrack.expectedCapabilityCount}`} /><Row label="Evidence records" value={commercialTrack.evidenceRecords} /></dl><p className="small">{commercialTrack.methodologyNotes}</p></article>}
          {technicalTrack && <article className="card"><div className="card-heading"><div><h3>{technicalTrack.name}</h3><p className="small">{technicalTrack.description}</p></div><Status tone="warn">{technicalTrack.status}</Status></div><dl className="data-list"><Row label="Assessment date" value={technicalTrack.assessmentDate ?? "Not assigned"} /><Row label="Capability values" value={`${technicalTrack.capabilityValues} / ${technicalTrack.expectedCapabilityCount}`} /><Row label="Evidence records" value={technicalTrack.evidenceRecords} /></dl><p className="small">{technicalTrack.methodologyNotes}</p></article>}
        </div>
        <div className="admin-grid capability-definition-grid">
          {commercialEntries.map((entry) => <article className="card mapping-set-card" key={entry.id}>
            <div className="card-heading"><div><span className="section-kicker">{label(entry.capabilityCategory)}</span><h3>{entry.capabilityName}</h3></div><Status tone="warn">{entry.capabilityScore.toFixed(0)} · {entry.assessmentStatus}</Status></div>
            <dl className="data-list"><Row label="Confidence" value={entry.confidence.toFixed(0)} /><Row label="Assessment date" value={entry.assessmentDate} /><Row label="Assessment track" value={label(entry.trackCode)} /></dl>
            <p>{entry.rationale}</p>
            {entry.evidenceRecords.map((evidence) => <details key={evidence.id}><summary>{evidence.benchmarkName} · {evidence.reportedResult}</summary><dl className="data-list"><Row label="Source tier / type" value={`${label(evidence.sourceTier)} / ${label(evidence.sourceType)}`} /><Row label="Provider / model" value={[evidence.providerName, evidence.modelName, evidence.modelVersion].filter(Boolean).join(" · ")} /><Row label="Evidence date" value={evidence.evidenceDate} /><Row label="Evidence confidence" value={evidence.confidence?.toFixed(0) ?? "—"} /></dl><p className="small">{evidence.rationale}</p><a href={evidence.sourceReference} target="_blank" rel="noreferrer">Open source reference ↗</a></details>)}
          </article>)}
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Benchmark expansion</span><h2>175-task human-review frame</h2><p className="small">{benchmark.datasetVersion} · {benchmark.occupations} diverse occupations</p></div><Status tone="warn">Pending human review</Status></div>
        <div className="notice"><strong>Automated triage is not gold data</strong><p>The frame is selected and versioned, but it remains draft until real reviewers provide independent annotations and adjudication. Candidate outputs cannot satisfy the research human-review gate; that gate is separate from MVP policy eligibility.</p></div>
        <div className="kpi-grid enrichment-kpis">
          <Kpi label="Benchmark tasks" value={benchmark.tasks} />
          <Kpi label="Mappable stratum" value={benchmark.mappableTasks} />
          <Kpi label="Ambiguous stratum" value={benchmark.ambiguousTasks} />
          <Kpi label="Insufficient stratum" value={benchmark.insufficientTasks} />
        </div>
        <article className="card"><h3>Human review and adjudication</h3><dl className="data-list"><Row label="Human-reviewed tasks" value={`${benchmark.humanReviewedTasks} / ${gate.minimumHumanReviewedTasks}`} /><Row label="Independently reviewed" value={benchmark.independentlyHumanReviewedTasks} /><Row label="Adjudicated" value={benchmark.adjudicatedTasks} /><Row label="Occupation coverage" value={`${benchmark.occupations} / ${gate.minimumOccupations}`} /></dl></article>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Draft candidate mapper</span><h2>{candidate.mapperName}</h2><p className="small">{candidate.runVersion} · structured task requirements only</p></div><Status tone={candidate.verificationStatus === "passed" ? "ok" : "error"}>{candidate.verificationStatus ?? "not verified"}</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Blind mapping run</h3><dl className="data-list"><Row label="Input / output tasks" value={`${candidate.inputTaskCount} / ${candidate.outputTaskCount}`} /><Row label="Mappable outputs" value={candidate.mappableTasks} /><Row label="Ambiguous outputs" value={candidate.ambiguousTasks} /><Row label="Insufficient outputs" value={candidate.insufficientTasks} /><Row label="Invalid structures" value={candidate.invalidTasks} /><Row label="Score-blind attestation" value={candidate.prohibitedInputAttestation ? "Present" : "Missing"} /></dl></article>
          <article className="card"><h3>Independent verification</h3><dl className="data-list"><Row label="Verification version" value={candidate.verificationVersion ?? "—"} /><Row label="Tasks checked" value={Number(candidate.verificationSummary?.tasksChecked ?? 0)} /><Row label="Errors" value={Number(candidate.verificationSummary?.errors ?? 0)} /><Row label="False-inference findings" value={Number(candidate.verificationSummary?.falseInferenceFindings ?? 0)} /><Row label="Task hashes reconciled" value={candidate.verificationSummary?.taskHashesReconciled ? "Yes" : "No"} /></dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Research mapper evaluation</span><h2>Aggregate control metrics</h2><p className="small">{candidate.evaluationVersion} · research gates {gate.gateVersion}</p></div><Status tone="warn">{candidate.evaluationStatus}</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Agreement and deviation</h3><dl className="data-list"><Row label="Capability-set agreement" value={formatRatio(candidate.evaluationMetrics?.capabilitySetAgreement)} /><Row label="Mean weight deviation" value={formatDecimal(candidate.evaluationMetrics?.meanWeightDeviation, 3)} /><Row label="Mean requirement-level deviation" value={formatDecimal(candidate.evaluationMetrics?.meanRequirementLevelDeviation, 1)} /><Row label="Mean constraint deviation" value={formatDecimal(candidate.evaluationMetrics?.meanConstraintDeviation, 1)} /><Row label="Confidence agreement" value={formatRatio(candidate.evaluationMetrics?.confidenceAgreement)} /></dl></article>
          <article className="card"><h3>Error profile</h3><dl className="data-list"><Row label="Extra dimensions" value={candidate.evaluationMetrics?.extraDimensions ?? 0} /><Row label="Missing dimensions" value={candidate.evaluationMetrics?.missingDimensions ?? 0} /><Row label="False-inference rate" value={formatRatio(candidate.evaluationMetrics?.falseInferenceRate)} /><Row label="Disposition agreement" value={formatRatio(candidate.evaluationMetrics?.dispositionAgreement)} /><Row label="Research acceptance" value="Ineligible pending human gold review" /><Row label="MVP policy impact" value="Non-blocking" /></dl></article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Research-grade acceptance gates</span><h2>{gate.name}</h2><p className="small">Preserved for future research validation; these gates do not block MVP per-task eligibility.</p></div><Status tone="warn">{gate.status}</Status></div>
        <article className="card"><dl className="data-list"><Row label="Minimum human-reviewed tasks" value={gate.minimumHumanReviewedTasks} /><Row label="Minimum occupations" value={gate.minimumOccupations} /><Row label="Minimum capability-set agreement" value={formatRatio(gate.minimumCapabilitySetAgreement)} /><Row label="Maximum mean weight deviation" value={gate.maximumMeanWeightDeviation} /><Row label="Maximum requirement-level deviation" value={gate.maximumMeanRequirementLevelDeviation} /><Row label="Maximum constraint deviation" value={gate.maximumMeanConstraintDeviation} /><Row label="Minimum confidence agreement" value={formatRatio(gate.minimumConfidenceAgreement)} /><Row label="Maximum false-inference rate" value={formatRatio(gate.maximumFalseInferenceRate)} /></dl></article>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Anchored scales</span><h2>Capability and environment anchors</h2><p className="small">Every dimension has explicit 0, 25, 50, 75 and 100 definitions.</p></div><Status tone="ok">{rubricValidation.capabilityAnchors + rubricValidation.constraintAnchors} anchors</Status></div>
        <div className="admin-grid constraint-grid rubric-scale-grid">
          <article className="card"><h3>15 capability dimensions</h3>{data.capabilityAnchors.map((dimension) => <details key={dimension.slug}><summary>{dimension.name}</summary><dl className="data-list rubric-anchor-list">{dimension.anchors.map((anchor) => <div key={anchor.value}><dt>{anchor.label}<small>{anchor.description}</small></dt><dd>{anchor.value}</dd></div>)}</dl></details>)}</article>
          <article className="card"><h3>10 environment constraints</h3>{data.constraintAnchors.map((dimension) => <details key={dimension.slug}><summary>{dimension.name}</summary><dl className="data-list rubric-anchor-list">{dimension.anchors.map((anchor) => <div key={anchor.value}><dt>{anchor.label}<small>{anchor.description}</small></dt><dd>{anchor.value}</dd></div>)}</dl></details>)}</article>
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Gold standard</span><h2>{gold.name}</h2><p className="small">{gold.datasetVersion} · {gold.reviewedBy}</p></div><Status tone="warn">Test fixture</Status></div>
        <div className="notice"><strong>{gold.mappableItems} mappable controls · {gold.ambiguousItems} ambiguous control</strong><p>This manually adjudicated set validates the rubric and comparison pipeline only. Fixture reviewer identities and task-statement hashes are retained as provenance.</p></div>
        {data.goldItems.map((item) => <article className="card mapping-set-card" key={item.id}>
          <div className="card-heading"><div><h3>{item.occupationCode} · Task {item.onetTaskId}</h3><p>{item.taskStatement}</p></div><Status tone={item.disposition === "mappable" ? "ok" : "warn"}>{label(item.disposition)}</Status></div>
          <p className="small">{item.dispositionRationale}</p>
          <dl className="data-list"><Row label="Capability requirements" value={item.capabilityRequirements} /><Row label="Environment constraints" value={item.environmentConstraints} /><Row label="Reviewer records" value={item.reviewerProvenance.length} /></dl>
        </article>)}
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Candidate comparison</span><h2>Fixture deviation reports</h2><p className="small">Weight, level, constraint and confidence deviations against the gold set.</p></div><Status tone="ok">{data.goldComparisons.length} reconciled</Status></div>
        <div className="admin-grid capability-definition-grid">{data.goldComparisons.map((comparison) => { const summary = comparison.report.summary; return <article className="card" key={comparison.candidateMappingSetId}><h3>Task {comparison.onetTaskId}</h3><dl className="data-list"><Row label="Mean weight deviation" value={Number(summary.meanAbsoluteWeightDeviation).toFixed(3)} /><Row label="Mean level deviation" value={Number(summary.meanAbsoluteLevelDeviation).toFixed(1)} /><Row label="Mean constraint deviation" value={Number(summary.meanAbsoluteConstraintDeviation).toFixed(1)} /><Row label="Mean capability confidence deviation" value={Number(summary.meanAbsoluteCapabilityConfidenceDeviation).toFixed(1)} /><Row label="Missing / extra" value={`${summary.missingCapabilities} / ${summary.extraCapabilities}`} /></dl></article>; })}</div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Capability definitions</span><h2>{taxonomy.name}</h2><p className="small">{taxonomy.version} · {taxonomy.methodologyVersion}</p></div><Status tone="warn">{taxonomy.status}</Status></div>
        <div className="admin-grid capability-definition-grid">
          {data.capabilities.map((capability) => <article className="card compact-definition" key={capability.id}>
            <span className="section-kicker">{label(capability.capabilityCategory)}</span>
            <h3>{capability.name}</h3>
            <p>{capability.description}</p>
            <small>{capability.slug} · definition v{capability.definitionVersion}</small>
          </article>)}
        </div>
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Task requirements</span><h2>Test capability mappings</h2></div><Status tone="warn">Test fixtures</Status></div>
        {data.mappingSets.map((set) => <article className="card mapping-set-card" key={set.id}>
          <div className="card-heading"><div><h3>{set.occupationCode} · Task {set.onetTaskId}</h3><p>{set.taskStatement}</p></div><Status tone={Number(set.weightTotal) === 1 ? "ok" : "error"}>{Number(set.weightTotal).toFixed(3)} total weight</Status></div>
          <p className="small">{set.taxonomyVersion} · {label(set.mappingMethod)} {set.mappingMethodVersion} · {label(set.reviewState)}</p>
          <dl className="data-list">
            {set.mappings.map((mapping) => <div key={mapping.capabilitySlug}><dt>{mapping.capabilityName}<small>Required level {mapping.requiredCapabilityLevel} · confidence {mapping.confidence}</small></dt><dd>{formatWeight(mapping.weight)}</dd></div>)}
          </dl>
        </article>)}
      </section>

      <section className="admin-inspector">
        <div className="card-heading"><div><span className="section-kicker">Environment constraints</span><h2>{environment.name}</h2><p className="small">{environment.version} · independent of capability fit</p></div><Status tone="warn">{environment.status}</Status></div>
        <div className="admin-grid constraint-grid">
          <article className="card"><h3>Definitions</h3><dl className="data-list">{data.constraints.map((constraint) => <div key={constraint.id}><dt>{constraint.name}<small>{label(constraint.constraintCategory)} · {constraint.testMappings} test mappings</small></dt><dd>v{constraint.definitionVersion}</dd></div>)}</dl></article>
          <article className="card"><h3>Test mappings</h3><dl className="data-list">{data.constraintMappings.map((mapping) => <div key={mapping.id}><dt>{mapping.constraintName}<small>Task {mapping.onetTaskId} · {mapping.occupationCode} · confidence {mapping.confidence}</small></dt><dd>{mapping.constraintLevel}</dd></div>)}</dl></article>
        </div>
      </section>

      <section className="admin-grid admin-inspector">
        <article className="card">
          <div className="card-heading"><div><h3>AI benchmark snapshots</h3><p className="small">Provider/model/evidence snapshots reconcile against an explicit expected capability count.</p></div><Status tone={data.snapshots.length ? "warn" : "ok"}>{data.snapshots.length}</Status></div>
          {data.snapshots.length ? <p>{data.snapshots.length} draft snapshots.</p> : <div className="empty-state compact"><p>No AI benchmark snapshots or scores have been generated.</p></div>}
        </article>
        <article className="card">
          <div className="card-heading"><div><h3>Task enrichment assessments</h3><p className="small">Future versioned fields: AI Capability Fit, Automation Feasibility, and Augmentation Potential.</p></div><Status tone={data.assessments.length ? "warn" : "ok"}>{data.assessments.length}</Status></div>
          {data.assessments.length ? <p>{data.assessments.length} draft assessments.</p> : <div className="empty-state compact"><p>No task-level enrichment assessments have been generated.</p></div>}
        </article>
      </section>

      <article className="card admin-inspector">
        <h3>Isolation and reconciliation</h3>
        <dl className="data-list">
          <Row label="Invalid mapping sets" value={data.validation.invalidMappingSets} />
          <Row label="Invalid benchmark snapshots" value={data.validation.invalidSnapshots} />
          <Row label="Invalid constraint mappings" value={data.validation.invalidConstraintMappings} />
          <Row label="Invalid task assessments" value={data.validation.invalidAssessments} />
          <Row label="Invalid gold datasets" value={rubricValidation.invalidGoldDatasets} />
          <Row label="Capability scale anchors" value={rubricValidation.capabilityAnchors} />
          <Row label="Constraint scale anchors" value={rubricValidation.constraintAnchors} />
          <Row label="New task assessments" value={data.validation.taskAssessments} />
          <Row label="New benchmark scores" value={data.validation.benchmarkScores} />
          <Row label="Untouched production score rows" value={data.validation.productionScoreRows} />
          <Row label="Untouched legacy task AI rows" value={data.validation.legacyTaskAiScoreRows} />
        </dl>
      </article>
    </AdminShell>
  );
}

function Kpi({ label: name, value }: { label: string; value: number }) { return <article className="kpi"><span>{name}</span><strong>{value}</strong><small>Live enrichment state</small></article>; }
function Row({ label: name, value }: { label: string; value: number | string }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function label(value: string) { return value.replaceAll("_", " ").replaceAll("-", " "); }
function formatWeight(value: number) { return `${(Number(value) * 100).toFixed(0)}%`; }
function formatRatio(value: number | undefined) { return `${(Number(value ?? 0) * 100).toFixed(1)}%`; }
function formatDecimal(value: number | undefined, digits: number) { return Number(value ?? 0).toFixed(digits); }
