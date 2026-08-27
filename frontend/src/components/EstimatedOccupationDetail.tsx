import Link from "next/link";
import type { EstimatedOccupation } from "@/lib/api";
import { AdSlot } from "./AdSlot";
import { Breadcrumbs } from "./Breadcrumbs";
import { EvidenceReceipt } from "./EvidenceReceipt";
import { MetricBar } from "./ScoreCard";
import { getScoreSemantics } from "@/lib/scoreSemantics";

/** Estimated occupation detail page.
 *
 *  Reuses the exact container, grid, typography, and card hierarchy of verified
 *  occupation pages while adapting the display for preliminary estimates.
 */
export function EstimatedOccupationDetail({ job }: { job: EstimatedOccupation }) {
  const isExposureRange =
    job.aiExposureLow !== null &&
    job.aiExposureHigh !== null &&
    job.aiExposureLow !== job.aiExposureHigh;
  const isRiskRange =
    job.replacementRiskLow !== null &&
    job.replacementRiskHigh !== null &&
    job.replacementRiskLow !== job.replacementRiskHigh;

  const exposureSemantics = getScoreSemantics("ai_exposure", job.aiExposure, { isEstimated: true });
  const riskSemantics = getScoreSemantics("replacement_risk", job.replacementRisk, { isEstimated: true });

  const breadcrumbItems = [
    { name: "Home", item: "/" },
    { name: "Occupations", item: "/rankings" },
    { name: job.title, item: `/jobs/${job.slug}` },
  ];

  return (
    <>
      {/* Breadcrumbs */}
      <div className="container" style={{ paddingTop: "16px" }}>
        <Breadcrumbs items={breadcrumbItems} />
      </div>

      <section className="score-section">
        <div className="container">
          <div className="card estimate-banner" role="region" aria-label="Preliminary estimate explanation">
            <div className="estimate-banner-header">
              <span className="section-kicker">Preliminary estimate · {job.confidenceLabel}</span>
            </div>
            <p className="estimate-disclaimer">{job.disclaimer}</p>
            <div>
              <Link className="text-link estimate-learn" href="/methodology#preliminary-estimates">
                Learn how estimates work <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>

          <div className="score-grid">
            <article className={`card score-card ${exposureSemantics.tone}`}>
              <span className="metric-label">Estimated AI Exposure</span>
              <div className={`score-number${isExposureRange ? " score-range" : ""}`}>
                {isExposureRange ? (
                  <>
                    {job.aiExposureLow}–{job.aiExposureHigh}
                    <small>/100</small>
                  </>
                ) : (
                  <>
                    ~{job.aiExposure}
                    <small>/100</small>
                  </>
                )}
              </div>
              <span className={exposureSemantics.chipClass}>{exposureSemantics.label}</span>
              <hr />
              <p>How much of this occupation&rsquo;s work can be materially affected by current AI systems.</p>
            </article>

            <div className="score-card-stack">
              <article className={`card score-card ${riskSemantics.tone}`}>
                <span className="metric-label">Estimated Replacement Risk</span>
                <div className={`score-number${isRiskRange ? " score-range" : ""}`}>
                  {isRiskRange ? (
                    <>
                      {job.replacementRiskLow}–{job.replacementRiskHigh}
                      <small>/100</small>
                    </>
                  ) : (
                    <>
                      ~{job.replacementRisk}
                      <small>/100</small>
                    </>
                  )}
                </div>
                <span className={riskSemantics.chipClass}>{riskSemantics.label}</span>
                <hr />
                <p>How likely exposure is to translate into reduced human demand.</p>
              </article>
              <p className="score-footnote">
                Preliminary estimate based on available occupational evidence.{" "}
                <Link className="text-link" href="/methodology#preliminary-estimates">
                  How this is measured
                </Link>
              </p>
            </div>

            <article className="card score-card">
              <span className="metric-label">Evidence quality</span>
              {job.evidenceCoverage !== null ? (
                <>
                  <MetricBar label="Task coverage" value={Math.round(job.evidenceCoverage)} suffix="%" metric="task_coverage" />
                  <div className="estimate-evidence-meta">
                    <span className="metric-label">Confidence</span>
                    <strong>{job.confidenceLabel}</strong>
                  </div>
                  <hr />
                  <p>
                    Task-level evidence directly covers {Math.round(job.evidenceCoverage)}% of this occupation&rsquo;s weighted work activities.
                  </p>
                </>
              ) : (
                <>
                  <div className="estimate-evidence-meta">
                    <span className="metric-label">Estimation method</span>
                    <strong>Related-work comparison</strong>
                  </div>
                  <div className="estimate-evidence-meta" style={{ marginTop: "10px" }}>
                    <span className="metric-label">Confidence</span>
                    <strong>{job.confidenceLabel}</strong>
                  </div>
                  <hr />
                  <p>
                    Estimated from {job.supportingRelativeCount ?? job.basedOn.length} closely related occupations with validated task-level analysis.
                  </p>
                </>
              )}
            </article>
          </div>
        </div>
      </section>

      {/* Ad 1: after scores, before evidence section */}
      <div className="container ad-break">
        <AdSlot slot="jobPrimary" format="horizontal" />
      </div>

      <section className="content-section">
        <div className="container">
          <div className="section-head">
            <div>
              <div className="section-kicker">Evidence base</div>
              <h2>What this estimate is based on</h2>
              <p>{job.estimateMethodDetail}</p>
            </div>
          </div>

          <div className="card estimate-evidence-card">
            {job.evidenceCoverage !== null && (
              <div className="estimate-coverage-stat">
                <span className="metric-label">Task Evidence Coverage</span>
                <div className="estimate-coverage-value">{Math.round(job.evidenceCoverage)}%</div>
                <p>
                  Task-level capability evidence covers {Math.round(job.evidenceCoverage)}% of the core work for this occupation.
                </p>
              </div>
            )}

            {job.basedOn.length > 0 && (
              <div>
                <h3 className="estimate-subheading">Closest analysed occupations</h3>
                <p className="estimate-subheading-desc">
                  These verified occupations share substantial work activities and provide the comparison basis for this estimate:
                </p>
                <div className="estimate-related-grid">
                  {job.basedOn.map((title) => (
                    <div className="estimate-related-item" key={title}>
                      <span className="estimate-related-bullet" aria-hidden="true">•</span>
                      <span>{title}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Ad 2: before pending guidance section */}
      <div className="container ad-break">
        <AdSlot slot="jobSecondary" format="horizontal" />
      </div>

      <section className="content-section section-tint">
        <div className="container">
          <div className="card estimate-pending-card">
            <div className="section-kicker">Detailed guidance pending</div>
            <h2>Task analysis &amp; action plan in progress</h2>
            <p>
              Detailed task-level breakdowns, automation resistance analysis, and personalized career transition guidance will become available once this occupation completes full validated analysis.
            </p>
          </div>
        </div>
      </section>

      <div className="container" style={{ paddingBottom: "48px" }}>
        <EvidenceReceipt
          status="preliminary"
          onetVersion="O*NET 30.3"
          capabilityModel="15 Structural Capability Dimensions"
          confidenceLabel={job.confidenceLabel}
        />
      </div>
    </>
  );
}
