import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import type { CareerTransition } from "@/lib/transitions/types";
import { trackEvent, getAnalyticsRiskBand } from "@/lib/analytics";
import { getScoreSemantics } from "@/lib/scoreSemantics";

function difficultyTone(difficulty: string): string {
  switch (difficulty) {
    case "Easier transition":
      return "tone-easier";
    case "Moderate transition":
      return "tone-moderate";
    case "Larger transition":
      return "tone-larger";
    default:
      return "";
  }
}

export function TransitionCard({
  transition,
  source,
  rank,
}: {
  transition: CareerTransition;
  source: Occupation;
  rank: number;
}) {
  const dest = transition.occupation;
  const exposureDelta = transition.exposureDelta;
  const riskPres = transition.riskPresentation;
  const destRiskSem = getScoreSemantics("replacement_risk", dest.replacementRisk);
  const destExpSem = getScoreSemantics("ai_exposure", dest.aiExposure);

  const handleOpenDestination = () => {
    trackEvent("transition_destination_opened", {
      source_slug: source.slug,
      destination_slug: dest.slug,
      source_risk_band: getAnalyticsRiskBand(source.replacementRisk),
      destination_risk_band: getAnalyticsRiskBand(dest.replacementRisk),
    });
  };

  return (
    <article className="card transition-card" key={dest.slug}>
      {/* Card Header */}
      <div className="transition-card-head">
        <div className="transition-rank-meta">
          <span className="transition-rank-pill">#{rank}</span>
          <div>
            <h3 className="transition-card-title">
              <Link href={`/jobs/${dest.slug}`} onClick={handleOpenDestination}>
                {dest.title}
              </Link>
            </h3>
            <span className="transition-category-tag">{dest.category}</span>
          </div>
        </div>

        <div className="transition-fit-badge-wrap">
          <div className="transition-fit-badge">
            <span className="fit-val">{transition.transitionFit}%</span>
            <span className="fit-lbl">Transition Fit</span>
          </div>
        </div>
      </div>

      {/* Difficulty & Tier Indicator */}
      <div className="transition-difficulty-row">
        <span
          className={`difficulty-pill ${difficultyTone(transition.difficulty)}`}
        >
          {transition.difficulty}
        </span>
        <span className="difficulty-note">{transition.difficultySummary}</span>
      </div>

      {/* Risk & Exposure Comparison Grid */}
      <div className="transition-metrics-grid">
        <div className="transition-metric-cell">
          <span className="metric-cell-label">Replacement Risk</span>
          <div className="metric-compare-val">
            <span className="metric-from">{source.replacementRisk}</span>
            <span className="metric-arrow">→</span>
            <span className={`metric-to ${destRiskSem.textClass}`}>{dest.replacementRisk}</span>
            <span className={`delta-chip ${riskPres.chipTone}`}>
              {riskPres.deltaLabel}
            </span>
          </div>
        </div>

        <div className="transition-metric-cell">
          <span className="metric-cell-label">AI Exposure</span>
          <div className="metric-compare-val">
            <span className="metric-from">{source.aiExposure}</span>
            <span className="metric-arrow">→</span>
            <span className={`metric-to ${destExpSem.textClass}`}>{dest.aiExposure}</span>
            {exposureDelta > 0 && (
              <span className="delta-sub lower">
                ({exposureDelta} pts lower)
              </span>
            )}
            {exposureDelta < 0 && (
              <span className="delta-sub higher">
                ({Math.abs(exposureDelta)} pts higher)
              </span>
            )}
            {exposureDelta === 0 && (
              <span className="delta-sub neutral">(similar exposure)</span>
            )}
          </div>
        </div>
      </div>

      {/* Why Fit & Considerations Rationale */}
      <div className="transition-rationale-box">
        <div className="rationale-section">
          <strong>Why this may fit</strong>
          <p>{transition.whyFit}</p>
        </div>
        <div className="rationale-section">
          <strong>Considerations</strong>
          <p>{transition.considerations}</p>
        </div>
      </div>

      {/* Action Links */}
      <div className="transition-card-actions">
        <Link
          className="button secondary"
          href={`/jobs/${dest.slug}`}
          onClick={handleOpenDestination}
        >
          View Career →
        </Link>
        <Link
          className="button tertiary"
          href={`/compare/${source.slug}-vs-${dest.slug}`}
          onClick={() =>
            trackEvent("transition_compare_clicked", {
              source_slug: source.slug,
              destination_slug: dest.slug,
            })
          }
        >
          Compare with {source.title} ⇄
        </Link>
      </div>
    </article>
  );
}
