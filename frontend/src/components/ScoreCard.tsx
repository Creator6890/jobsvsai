import { getScoreSemantics, type SemanticTone } from "@/lib/scoreSemantics";

export function ScoreCard({
  label,
  value,
  description,
  metric,
  tone,
  isEstimated = false,
}: {
  label: string;
  value: number;
  description?: string;
  metric?: string;
  tone?: "violet" | "green" | "red" | "safe" | "moderate" | "risk" | "neutral";
  isEstimated?: boolean;
}) {
  const metricKey = metric ?? label;
  const semantics = getScoreSemantics(metricKey, value, { isEstimated });
  const toneClass = tone ?? semantics.tone;

  return (
    <article className={`card score-card ${toneClass}`}>
      <span className="metric-label">{label}</span>
      <div className="score-number">
        {value}
        <small>/100</small>
      </div>
      <span className={semantics.chipClass}>{semantics.label}</span>
      {description && (
        <>
          <hr />
          <p>{description}</p>
        </>
      )}
    </article>
  );
}

export function MetricBar({
  label,
  value,
  suffix = "",
  metric,
  tone,
}: {
  label: string;
  value: number;
  suffix?: string;
  metric?: string;
  tone?: SemanticTone;
}) {
  const semantics = metric ? getScoreSemantics(metric, value) : null;
  const resolvedTone = tone ?? semantics?.tone;
  const fillClass = resolvedTone ? ` ${resolvedTone}` : "";

  return (
    <div className="metric-bar">
      <div>
        <span>{label}</span>
        <strong>
          {value}
          {suffix}
          {semantics && semantics.direction !== "confidence" && (
            <span className={`metric-bar-qualifier ${semantics.tone}`}> · {semantics.shortLabel}</span>
          )}
        </strong>
      </div>
      <div className="bar-track" aria-label={`${label}: ${value}${suffix}`}>
        <span
          className={`bar-fill${fillClass}`}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}
