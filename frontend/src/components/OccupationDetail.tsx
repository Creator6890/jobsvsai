import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import { AdSlot } from "./AdSlot";
import { MetricBar, ScoreCard } from "./ScoreCard";
import { RelatedOccupationLink } from "./RelatedOccupationLink";

// O*NET's relatedness tiers, rendered for readers. The tier is a source fact; the wording
// is a presentation of it and deliberately claims nothing about transition difficulty.
const RELATEDNESS_LABELS: Record<string, string> = {
  "Primary-Short": "Closely related work",
  "Primary-Long": "Related work",
  Supplemental: "Shares some work",
};

function relatednessLabel(tier: string): string {
  return RELATEDNESS_LABELS[tier] ?? "Related work";
}

// Reads the production score store only. `trend`, `salaryPotential` and `futureDemand` are
// gone because the Phase 5 engine produces none of them; `/career-finder` links are gone
// because that surface is excluded from the initial launch.
export function OccupationDetail({ job }: { job: Occupation }) {
  const vulnerable = [...job.tasks].sort((a, b) => b.exposure - a.exposure).slice(0, 4);
  return <>
    <section className="score-section"><div className="container score-grid"><ScoreCard label="AI Exposure" value={job.aiExposure} description="How much of this occupation's work can be materially affected by current AI systems." /><div className="score-card-stack"><ScoreCard label="Replacement Risk" value={job.replacementRisk} description="How likely exposure is to translate into reduced human demand." tone="red" /><p className="score-footnote">Includes provisional estimates for AI adoption pressure and labour-market resilience. <Link className="text-link" href="/methodology#provisional-factors">How this is measured</Link></p></div><article className="card score-card"><span className="metric-label">Evidence quality</span><MetricBar label="Confidence" value={Math.round(job.confidence)} suffix="/100" /><MetricBar label="Task coverage" value={Math.round(job.weightedTaskCoverage)} suffix="%" /><p>Confidence reflects task coverage, mapping and capability-evidence quality, and how much of the score rests on provisional inputs.</p></article></div></section>

    {/* Ad 1: after scores + evidence quality, before task-level detail. */}
    <div className="container ad-break">
      <AdSlot slot="jobPrimary" format="horizontal" />
    </div>

    <section className="content-section"><div className="container"><div className="section-head"><div><div className="section-kicker">Task-level evidence</div><h2>What is driving the score?</h2><p>Occupation scores are built from the task mix—not a single prediction about a job title.</p></div><span className="chip">{job.modelVersion}</span></div><div className="card task-table"><div className="task-row task-header"><b>Task</b><b>Importance</b><b>AI impact</b><b>Exposure</b></div>{job.tasks.map((task) => <div className="task-row" key={task.onetTaskId}><strong>{task.name}</strong><span>{task.importance}</span><div className="bar-track"><span style={{ width: `${task.exposure}%` }} /></div><b>{task.exposure}</b></div>)}</div></div></section>

    <section className="content-section section-tint"><div className="container two-column"><article className="card"><span className="section-kicker">Most exposed</span><h2>Where AI can do more</h2><p>Routine, digitized, and highly repeatable tasks face the greatest pressure.</p><ol className="insight-list">{vulnerable.map((task) => <li key={task.onetTaskId}><span>{task.name}</span><b>{task.exposure}</b></li>)}</ol></article><article className="card human-card"><span className="section-kicker">Hardest to automate</span><h2>Where people still matter</h2><p>These tasks score lowest on automation feasibility—physical presence, judgement, accountability and real-world variability all resist end-to-end automation.</p><ol className="insight-list">{job.hardestToAutomateTasks.map((task, index) => <li key={task}><span>{task}</span><b>0{index + 1}</b></li>)}</ol></article></div></section>

    {/* Ad 2: natural content boundary before related occupations. */}
    <div className="container ad-break">
      <AdSlot slot="jobSecondary" format="horizontal" />
    </div>

    <section className="content-section"><div className="container"><div className="section-head"><div><div className="section-kicker">Where else this work leads</div><h2>Related occupations</h2><p>Occupations O*NET links to this one. Relatedness reflects shared work, not a claim that these roles are safer.</p></div><Link className="button secondary" href="/rankings">See all rankings →</Link></div>{job.relatedCareers.length ? <div className="career-grid">{job.relatedCareers.map((career) => <article className="card career-card" key={career.slug}><span className="chip safe">AI risk {career.replacementRisk}</span><h3>{career.title}</h3><p>{relatednessLabel(career.relatednessTier)}</p><RelatedOccupationLink sourceSlug={job.slug} relatedSlug={career.slug} relatedTitle={career.title} href={`/compare/${job.slug}-vs-${career.slug}`}>Compare these careers →</RelatedOccupationLink></article>)}</div> : <div className="empty-state">No related occupation is published yet.</div>}</div></section>

    <section className="content-section section-tint"><div className="container outlook-grid"><div><div className="section-kicker">Beyond AI capability</div><h2>Adoption and labour-market outlook</h2><p>Structural factors are kept separate from raw capability so you can see what actually resists automation. Adoption pressure and labour-market resilience are still provisional models—{Math.round(job.provisionalWeightShare)}% of this occupation’s replacement-risk weight rests on them.</p></div><article className="card metric-stack"><MetricBar label="Human dependency" value={job.humanDependency} /><MetricBar label="Physical dependency" value={job.physicalDependency} /><MetricBar label="Adoption pressure" value={job.adoptionPressure} /><MetricBar label="Labour-market resilience" value={job.labourMarketResilience} /></article></div></section>

    <section className="source-strip"><div className="container"><div><strong>Methodology & sources</strong><p>O*NET 30.3 occupational data interpreted through the JobsVsAI capability, automation and structural-constraint models.</p></div><div><span className="metric-label">Confidence</span><strong>{Math.round(job.confidence)}/100</strong></div><div><span className="metric-label">Calculated</span><strong>{new Date(job.updatedAt).toLocaleDateString("en", { dateStyle: "medium" })}</strong></div><Link className="text-link" href="/methodology">Read methodology →</Link></div></section>
  </>;
}
