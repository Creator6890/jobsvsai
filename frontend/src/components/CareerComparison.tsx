import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import { ComparisonViewTracker } from "./analytics/AnalyticsTrackers";
import { getScoreSemantics } from "@/lib/scoreSemantics";

// Salary and future demand are absent by design: the Phase 5 engine produces neither and
// they are not fabricated. Evidence-quality metrics take their place.

const metrics: { label: string; key: keyof Occupation; metric: string; lower?: boolean }[] = [
  { label: "AI Exposure", key: "aiExposure", metric: "ai_exposure", lower: true },
  { label: "Replacement Risk", key: "replacementRisk", metric: "replacement_risk", lower: true },
  { label: "Human Dependency", key: "humanDependency", metric: "human_dependency" },
  { label: "Physical Dependency", key: "physicalDependency", metric: "physical_dependency" },
  { label: "Labour-market Resilience", key: "labourMarketResilience", metric: "labour_market_resilience" },
  { label: "Confidence", key: "confidence", metric: "confidence" },
  { label: "Task Coverage", key: "weightedTaskCoverage", metric: "task_coverage" },
];

export function CareerComparison({ a, b }: { a: Occupation; b: Occupation }) {
  return (
    <article className="card comparison-card">
      <ComparisonViewTracker slugA={a.slug} slugB={b.slug} />
      <div className="comparison-head">
        <CareerHead job={a} />
        <div className="vs-badge">VS</div>
        <CareerHead job={b} />
      </div>
      <div className="comparison-table">
        <div className="comparison-row comparison-labels">
          <b>Metric</b>
          <b>{a.title}</b>
          <b>{b.title}</b>
          <b>Advantage</b>
        </div>
        {metrics.map((metric) => {
          const av = Number(a[metric.key]);
          const bv = Number(b[metric.key]);
          const semA = getScoreSemantics(metric.metric, av);
          const semB = getScoreSemantics(metric.metric, bv);
          const winner =
            av === bv
              ? "Even"
              : metric.lower
              ? av < bv
                ? a.title
                : b.title
              : av > bv
              ? a.title
              : b.title;

          return (
            <div className="comparison-row" key={metric.label}>
              <strong>{metric.label}</strong>
              <span>
                <span className={semA.badgeClass} title={semA.label}>
                  {av}
                  {metric.metric === "task_coverage" ? "%" : ""}
                </span>
              </span>
              <span>
                <span className={semB.badgeClass} title={semB.label}>
                  {bv}
                  {metric.metric === "task_coverage" ? "%" : ""}
                </span>
              </span>
              <b>{winner}</b>
            </div>
          );
        })}
      </div>
      <div className="notice">
        <strong>Verdict</strong>
        <p>
          {a.replacementRisk < b.replacementRisk ? a.title : b.title} currently appears more AI-resilient. That advantage
          reflects lower replacement pressure after human dependency, physical dependency, labour-market resilience and
          adoption factors are included.
        </p>
      </div>
    </article>
  );
}

function CareerHead({ job }: { job: Occupation }) {
  const riskSem = getScoreSemantics("replacement_risk", job.replacementRisk);
  return (
    <div>
      <span className="chip">{job.category}</span>
      <h2>{job.title}</h2>
      <div className={`score-number score-${riskSem.tone}`}>
        {job.replacementRisk}
        <small>/100 risk</small>
      </div>
      <span className={riskSem.chipClass}>{riskSem.label}</span>
      <div style={{ marginTop: "12px" }}>
        <Link className="text-link" href={`/jobs/${job.slug}`}>
          Full analysis →
        </Link>
      </div>
    </div>
  );
}
