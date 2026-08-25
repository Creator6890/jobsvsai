import {
  DIMENSIONS,
  DIMENSION_KEYS,
  getStrengthTone,
  type DimensionKey,
  type StrengthBand,
} from "@/lib/careerFit";

type ProfileStrengthBarsProps = {
  dimensionScores: Record<DimensionKey, number>;
  dimensionBands: Record<DimensionKey, StrengthBand>;
  highlightKeys?: DimensionKey[];
};

export function ProfileStrengthBars({
  dimensionScores,
  dimensionBands,
  highlightKeys = [],
}: ProfileStrengthBarsProps) {
  return (
    <div className="career-fit-strength-grid">
      {DIMENSION_KEYS.map((key) => {
        const dim = DIMENSIONS[key];
        const score = dimensionScores[key] ?? 50;
        const band = dimensionBands[key] ?? "Moderate";
        const tone = getStrengthTone(band);
        const isHighlighted = highlightKeys.includes(key);

        return (
          <article
            className={`card career-fit-strength-card${
              isHighlighted ? " highlighted" : ""
            }`}
            key={key}
          >
            <div className="strength-card-header">
              <div>
                <span className="strength-dim-name">{dim.label}</span>
                <p className="strength-dim-tagline">{dim.tagline}</p>
              </div>
              <div className="strength-badge-wrap">
                <span className={`chip ${tone}`}>{band}</span>
                <span className="strength-score-num">{score}/100</span>
              </div>
            </div>

            <div
              className="bar-track"
              role="progressbar"
              aria-valuenow={score}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${dim.label}: ${score} out of 100`}
            >
              <span
                className={`bar-fill ${tone}`}
                style={{ width: `${score}%` }}
              />
            </div>

            <p className="strength-dim-desc">{dim.description}</p>
          </article>
        );
      })}
    </div>
  );
}
