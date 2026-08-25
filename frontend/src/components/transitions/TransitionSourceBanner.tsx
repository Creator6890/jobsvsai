import type { Occupation } from "@/types/occupation";
import Link from "next/link";

export function TransitionSourceBanner({
  source,
  isLowRisk,
}: {
  source: Occupation;
  isLowRisk: boolean;
}) {
  return (
    <div className="card transition-source-banner">
      <div className="source-banner-meta">
        <span className="section-kicker">
          {isLowRisk
            ? "Exploring Adjacent Paths From"
            : "Exploring Career Alternatives From"}
        </span>
        <h2 className="source-banner-title">
          <Link href={`/jobs/${source.slug}`}>{source.title}</Link>
        </h2>
        <div className="source-banner-chips">
          <span className="chip">{source.category}</span>
          <span className="chip muted">{source.modelVersion}</span>
        </div>
      </div>

      <div className="source-banner-metrics">
        <div className="source-metric-box">
          <span className="metric-label">Current AI Exposure</span>
          <strong className="source-metric-value">{source.aiExposure}</strong>
          <span className="metric-scale">/100</span>
        </div>
        <div className="source-metric-box">
          <span className="metric-label">Current Replacement Risk</span>
          <strong className="source-metric-value risk-val">
            {source.replacementRisk}
          </strong>
          <span className="metric-scale">/100</span>
        </div>
      </div>
    </div>
  );
}
