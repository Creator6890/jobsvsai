import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import { AdSlot } from "./AdSlot";
import { Breadcrumbs } from "./Breadcrumbs";
import { EvidenceReceipt } from "./EvidenceReceipt";
import { MetricBar, ScoreCard } from "./ScoreCard";
import { RelatedOccupationLink } from "./RelatedOccupationLink";
import { ActionPlanSection } from "./actionPlan/ActionPlanSection";
import { OccupationViewTracker } from "./analytics/AnalyticsTrackers";
import { getScoreSemantics } from "@/lib/scoreSemantics";
import { getOccupationContent } from "@/lib/occupationContent";
import { formatExposurePercentile, formatReplacementRiskPercentile } from "@/lib/scorePercentiles";
import { getCanonicalField, getCanonicalFieldSlug } from "@/lib/careerFields";

const RELATEDNESS_LABELS: Record<string, string> = {
  "Primary-Short": "Closely related work",
  "Primary-Long": "Related work",
  Supplemental: "Shares some work",
};

function relatednessLabel(tier: string): string {
  return RELATEDNESS_LABELS[tier] ?? "Related work";
}

export function OccupationDetail({
  job,
  exposurePercentile,
  replacementRiskPercentile,
}: {
  job: Occupation;
  exposurePercentile?: number;
  replacementRiskPercentile?: number;
}) {
  const content = getOccupationContent(job);

  const fieldSlug = getCanonicalFieldSlug(job.slug, job.category);
  const fieldDef = getCanonicalField(fieldSlug);

  const breadcrumbItems = [
    { name: "Home", item: "/" },
    ...(fieldDef ? [{ name: fieldDef.name, item: `/careers/${fieldDef.slug}` }] : [{ name: "Occupations", item: "/rankings" }]),
    { name: job.title, item: `/jobs/${job.slug}` },
  ];

  return (
    <>
      <OccupationViewTracker
        slug={job.slug}
        aiExposure={job.aiExposure}
        replacementRisk={job.replacementRisk}
      />

      {/* Breadcrumbs */}
      <div className="container" style={{ paddingTop: "16px" }}>
        <Breadcrumbs items={breadcrumbItems} />
      </div>

      {/* Direct Answer Hero Callout */}
      <section className="content-section" style={{ paddingBottom: "12px", paddingTop: "20px" }}>
        <div className="container">
          <article className="card direct-answer-card" style={{ background: "linear-gradient(135deg, #fbfaff, #fff)", borderColor: "var(--violet-soft)", padding: "24px 28px" }}>
            <span className="section-kicker">Direct Answer</span>
            <h2 style={{ fontSize: "1.4rem", marginTop: "4px", marginBottom: "12px" }}>
              Will AI replace {job.title.toLowerCase()}s?
            </h2>
            <p style={{ fontSize: "1.05rem", lineHeight: 1.65, color: "var(--ink)", maxWidth: "var(--measure)" }}>
              {content.directAnswer}
            </p>
          </article>
        </div>
      </section>

      {/* Headline Scores */}
      <section className="score-section">
        <div className="container score-grid">
          <ScoreCard
            label="AI Exposure"
            value={job.aiExposure}
            metric="ai_exposure"
            percentileLabel={exposurePercentile !== undefined ? formatExposurePercentile(exposurePercentile) : undefined}
            description="How much of this occupation's daily workload can be materially assisted or executed by current AI systems."
          />
          <div className="score-card-stack">
            <ScoreCard
              label="Replacement Risk"
              value={job.replacementRisk}
              metric="replacement_risk"
              percentileLabel={replacementRiskPercentile !== undefined ? formatReplacementRiskPercentile(replacementRiskPercentile) : undefined}
              description="Relative structural vulnerability of the human role after accounting for real-world friction and constraints."
            />
            <p className="score-footnote">
              Includes provisional estimates for AI adoption pressure and labour-market resilience.{" "}
              <Link className="text-link" href="/methodology#provisional-factors">
                How this is measured
              </Link>
            </p>
          </div>
          <article className="card score-card">
            <span className="metric-label">Evidence quality</span>
            <MetricBar
              label="Confidence"
              value={Math.round(job.confidence)}
              suffix="/100"
              metric="confidence"
            />
            <MetricBar
              label="Task coverage"
              value={Math.round(job.weightedTaskCoverage)}
              suffix="%"
              metric="task_coverage"
            />
            <p>
              Confidence reflects O*NET task coverage ({Math.round(job.weightedTaskCoverage)}%), AI mapping quality, and reliance on validated structural proxies.
            </p>
          </article>
        </div>
      </section>

      {/* Ad 1: after scores, before deep dive */}
      <div className="container ad-break">
        <AdSlot slot="jobPrimary" format="horizontal" />
      </div>

      {/* The Verdict: What this means */}
      <section className="content-section">
        <div className="container">
          <div className="section-head">
            <div>
              <div className="section-kicker">Comprehensive Verdict</div>
              <h2>What this analysis means for {job.title}s</h2>
              <p>An evidence-led breakdown of structural exposure and real-world replacement constraints.</p>
            </div>
          </div>
          <article className="card" style={{ padding: "28px 32px" }}>
            {content.verdictParagraphs.map((p, idx) => (
              <p key={idx} style={{ fontSize: "1.02rem", lineHeight: 1.7, marginBottom: idx === content.verdictParagraphs.length - 1 ? 0 : "16px", color: "var(--ink)" }}>
                {p}
              </p>
            ))}
            <div className="metric-callout" style={{ marginTop: "20px", background: "var(--soft)", padding: "14px 18px", borderRadius: "var(--radius-xs)" }}>
              <strong>Exposure vs. Replacement Difference: </strong>
              <span>{content.exposureVsReplacementContrast}</span>
            </div>
          </article>
        </div>
      </section>

      {/* Why This Job Scores This Way: Structural Drivers */}
      <section className="content-section section-tint">
        <div className="container">
          <div className="section-head">
            <div>
              <div className="section-kicker">Multi-Factor Analysis</div>
              <h2>Why {job.title} scores this way</h2>
              <p>How five foundational dimensions shape this occupation&apos;s vulnerability and resilience.</p>
            </div>
          </div>
          <div className="factor-grid">
            {content.keyDrivers.map((driver, idx) => (
              <article className="card factor-card" key={idx} style={{ padding: "22px" }}>
                <span className="section-kicker" style={{ fontSize: "0.75rem" }}>Factor 0{idx + 1}</span>
                <h3 style={{ fontSize: "1.1rem", margin: "8px 0 6px" }}>{driver.title}</h3>
                <p style={{ fontSize: "0.92rem", lineHeight: 1.55 }}>{driver.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Task Automation Breakdown */}
      <section className="content-section">
        <div className="container">
          <div className="section-head">
            <div>
              <div className="section-kicker">Task-level evidence ({job.tasks.length} tasks assessed)</div>
              <h2>Which parts of {job.title} can AI automate?</h2>
              <p>Jobs are bundles of tasks. Task exposure does not equal occupation elimination.</p>
            </div>
            <span className="chip hero-chip">{job.modelVersion}</span>
          </div>
          <div className="card task-table">
            <div className="task-row task-header">
              <b>Task Statement</b>
              <b>Importance</b>
              <b>AI Impact Track</b>
              <b>Exposure</b>
            </div>
            {job.tasks.map((task) => {
              const taskSem = getScoreSemantics("task_exposure", task.exposure);
              return (
                <div className="task-row" key={task.onetTaskId}>
                  <strong>{task.name}</strong>
                  <span>{task.importance}</span>
                  <div className="bar-track">
                    <span className={taskSem.tone} style={{ width: `${task.exposure}%` }} />
                  </div>
                  <b className={taskSem.textClass}>{task.exposure}</b>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Human Advantage & Anchors */}
      <section className="content-section section-tint">
        <div className="container two-column">
          <article className="card human-card">
            <span className="section-kicker">Human Strongholds</span>
            <h2>Where humans remain essential</h2>
            <p>
              These tasks score lowest on automation feasibility—physical agility, accountability, and empathy resist automation.
            </p>
            <ol className="insight-list" style={{ marginTop: "16px" }}>
              {job.hardestToAutomateTasks.map((task, index) => (
                <li key={task}>
                  <span>{task}</span>
                  <b>0{index + 1}</b>
                </li>
              ))}
            </ol>
          </article>

          <article className="card">
            <span className="section-kicker">Human Advantage Factors</span>
            <h2>Core protective barriers</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginTop: "16px" }}>
              {content.humanAdvantages.map((adv, idx) => (
                <div key={idx} style={{ borderBottom: idx === content.humanAdvantages.length - 1 ? 0 : "1px solid var(--line)", paddingBottom: "12px" }}>
                  <strong style={{ display: "block", fontSize: "0.95rem", color: "var(--ink)", marginBottom: "4px" }}>
                    {adv.title}
                  </strong>
                  <p style={{ fontSize: "0.88rem", color: "var(--muted)", margin: 0, lineHeight: 1.5 }}>
                    {adv.description}
                  </p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      {/* Ad 2 */}
      <div className="container ad-break">
        <AdSlot slot="jobSecondary" format="horizontal" />
      </div>

      {/* Action Plan V1 */}
      <ActionPlanSection job={job} />

      {/* Career Fit Assessment CTA Banner */}
      <section className="content-section" style={{ paddingTop: "12px", paddingBottom: "24px" }}>
        <div className="container">
          <div className="card" style={{ background: "var(--soft)", padding: "24px 28px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "20px", flexWrap: "wrap" }}>
            <div>
              <strong style={{ fontSize: "1.1rem", display: "block", marginBottom: "4px" }}>
                Looking for careers matching your personal strengths?
              </strong>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.92rem", maxWidth: "600px" }}>
                National occupational analyses reflect typical job roles. Take the Career Fit Assessment to discover careers aligned with your individual work style and verified AI resilience.
              </p>
            </div>
            <Link className="button primary" href="/career-fit">
              Take Career Fit Assessment →
            </Link>
          </div>
        </div>
      </section>

      {/* Related Occupations & Transitions */}
      <section className="content-section">
        <div className="container">
          <div className="section-head">
            <div>
              <div className="section-kicker">Career Path Mobility</div>
              <h2>Related occupations and career transitions</h2>
              <p>Occupations linked by shared O*NET tasks and skills.</p>
            </div>
            <div className="section-actions">
              <Link className="button secondary" href={`/jobs/${job.slug}/transitions`}>
                Explore Career Transitions →
              </Link>
            </div>
          </div>
          {job.relatedCareers.length ? (
            <div className="career-grid">
              {job.relatedCareers.map((career) => {
                const relSem = getScoreSemantics("replacement_risk", career.replacementRisk);
                return (
                  <article className="card career-card" key={career.slug}>
                    <span className={relSem.chipClass}>
                      AI risk {career.replacementRisk} · {relSem.band}
                    </span>
                    <h3>{career.title}</h3>
                    <p>{relatednessLabel(career.relatednessTier)}</p>
                    <RelatedOccupationLink
                      sourceSlug={job.slug}
                      relatedSlug={career.slug}
                      relatedTitle={career.title}
                      href={`/compare/${job.slug}-vs-${career.slug}`}
                    >
                      Compare these careers →
                    </RelatedOccupationLink>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">No related occupation is published yet.</div>
          )}
        </div>
      </section>

      {/* Evidence Receipt */}
      <div className="container">
        <EvidenceReceipt
          status="verified"
          onetVersion="O*NET 30.3"
          capabilityModel="15 Structural Capability Dimensions"
          scoringModel={job.modelVersion}
          taskCount={job.tasks.length}
          coveragePercent={job.weightedTaskCoverage}
          confidenceScore={job.confidence}
          updatedAt={job.updatedAt}
        />
      </div>

      {/* Occupation FAQ Section */}
      <section className="section" aria-labelledby="occupation-faq-heading">
        <div className="container">
          <div className="section-kicker">Frequently Asked Questions</div>
          <h2 id="occupation-faq-heading">Questions about {job.title} and AI</h2>
          <div className="faq-stack" style={{ marginTop: "24px" }}>
            {content.faqs.map((faq, idx) => (
              <details className="card faq-item" key={idx} style={{ padding: "18px 24px", marginBottom: "10px" }}>
                <summary style={{ fontWeight: 750, fontSize: "1.02rem", cursor: "pointer" }}>
                  {faq.question}
                </summary>
                <p style={{ marginTop: "12px", color: "var(--ink)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                  {faq.answer}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
