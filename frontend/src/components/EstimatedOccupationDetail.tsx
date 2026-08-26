import Link from "next/link";
import type { EstimatedOccupation } from "@/lib/api";

/** The status is rendered *above* the scores, not beneath them.
 *
 *  A disclaimer below a number is read after the number has already been believed. Everything
 *  a reader needs in order to interpret the figures — that they are preliminary, what they
 *  rest on, how confident we are — appears before the first digit. */
export function EstimatedOccupationDetail({ job }: { job: EstimatedOccupation }) {
  return (
    <div className="estimate-detail">
      <section className="estimate-banner" aria-labelledby="estimate-status">
        <div className="estimate-banner-head">
          <span className="estimate-flag" id="estimate-status">
            Preliminary estimate
          </span>
          <span className="estimate-confidence">{job.confidenceLabel}</span>
        </div>
        <p className="estimate-disclaimer">{job.disclaimer}</p>
        <Link className="text-button estimate-learn" href="/methodology#preliminary-estimates">
          Learn how estimates work <span aria-hidden="true">→</span>
        </Link>
      </section>

      <section className="estimate-scores">
        <EstimateScore
          label="Estimated AI Exposure"
          value={job.aiExposure}
          low={job.aiExposureLow}
          high={job.aiExposureHigh}
        />
        <EstimateScore
          label="Estimated Replacement Risk"
          value={job.replacementRisk}
          low={job.replacementRiskLow}
          high={job.replacementRiskHigh}
        />
      </section>

      <section className="estimate-evidence">
        <h2>What this estimate is based on</h2>
        <p>{job.estimateMethodDetail}</p>
        {job.evidenceCoverage !== null && (
          <p className="estimate-evidence-line">
            Task evidence covers <strong>{Math.round(job.evidenceCoverage)}%</strong> of this
            occupation&rsquo;s weighted work.
          </p>
        )}
        {job.basedOn.length > 0 && (
          <>
            <p className="estimate-evidence-line">
              Estimated from these fully analysed occupations:
            </p>
            <ul className="estimate-sources">
              {job.basedOn.map((title) => (
                <li key={title}>{title}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="estimate-pending">
        <h2>Not yet available for this occupation</h2>
        <p>
          A detailed task breakdown, career transitions and an action plan need validated
          task-level evidence. They will appear here once this occupation completes full
          analysis &mdash; we would rather leave them out than generate guidance we cannot
          stand behind.
        </p>
      </section>
    </div>
  );
}

function EstimateScore({
  label,
  value,
  low,
  high,
}: {
  label: string;
  value: number;
  low: number | null;
  high: number | null;
}) {
  // A range is shown whenever the evidence does not support a single number. The "~" on a
  // point estimate is doing real work: it marks the figure as approximate even where the
  // range is narrow enough to omit.
  const isRange = low !== null && high !== null;
  return (
    <div className="estimate-score">
      <span className="metric-label">{label}</span>
      <strong>
        {isRange ? (
          <>
            {low}&ndash;{high}
          </>
        ) : (
          <>~{value}</>
        )}
        <small>/100</small>
      </strong>
      <span className="chip estimate-chip">Estimated</span>
    </div>
  );
}
