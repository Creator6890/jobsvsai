import Link from "next/link";
import { DIMENSIONS } from "@/lib/careerFit";
import type { CareerMatch } from "@/lib/careerFit";
import { trackEvent } from "@/lib/analytics";

type CareerMatchCardProps = {
  match: CareerMatch;
  rank: number;
};

export function CareerMatchCard({ match, rank }: CareerMatchCardProps) {
  const { occupation, careerFit, keyStrengths, whyFit, considerations } = match;

  const handleClick = () => {
    trackEvent("career_fit_job_opened", {
      slug: occupation.slug,
      fitScore: careerFit,
    });
  };

  return (
    <article className="card career-fit-card">
      <div className="career-fit-card-head">
        <div>
          <div className="career-fit-rank-row">
            <span className="career-fit-rank">#{rank}</span>
            <span className="chip">{occupation.category}</span>
          </div>
          <h3 className="career-fit-card-title">{occupation.title}</h3>
        </div>

        <div className="career-fit-score-badge">
          <span className="career-fit-score-label">CAREER FIT</span>
          <strong className="career-fit-score-value">{careerFit}%</strong>
        </div>
      </div>

      <p className="career-fit-why">{whyFit}</p>

      {keyStrengths.length > 0 && (
        <div className="career-fit-strengths-wrap">
          <span className="career-fit-strengths-label">Key competencies:</span>
          <div className="career-fit-tag-cloud">
            {keyStrengths.map((key) => (
              <span className="chip safe" key={key}>
                {DIMENSIONS[key].shortLabel}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* AI Risk Snapshot */}
      <div className="career-fit-risk-grid">
        <div className="career-fit-risk-item">
          <span className="metric-label">AI EXPOSURE</span>
          <span
            className={`score-badge ${
              occupation.aiExposure >= 70 ? "risk" : "neutral"
            }`}
          >
            {occupation.aiExposure}/100
          </span>
        </div>
        <div className="career-fit-risk-item">
          <span className="metric-label">REPLACEMENT RISK</span>
          <span
            className={`score-badge ${
              occupation.replacementRisk >= 60
                ? "risk"
                : occupation.replacementRisk <= 40
                ? "safe"
                : "neutral"
            }`}
          >
            {occupation.replacementRisk}/100
          </span>
        </div>
      </div>

      {considerations.length > 0 && (
        <ul className="career-fit-considerations">
          {considerations.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      )}

      <footer className="career-fit-card-footer">
        <Link
          className="button secondary"
          href={`/jobs/${occupation.slug}`}
          onClick={handleClick}
        >
          Explore occupation details →
        </Link>
      </footer>
    </article>
  );
}
