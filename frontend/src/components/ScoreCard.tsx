export function ScoreCard({ label, value, description, tone = "violet" }: { label: string; value: number; description?: string; tone?: "violet" | "green" | "red" }) {
  const band = value >= 75 ? "Very high" : value >= 60 ? "High" : value >= 40 ? "Moderate" : "Low";
  return <article className={`card score-card ${tone}`}><span className="metric-label">{label}</span><div className="score-number">{value}<small>/100</small></div><span className="chip">{band}</span>{description && <><hr /><p>{description}</p></>}</article>;
}

export function MetricBar({ label, value, suffix = "" }: { label: string; value: number; suffix?: string }) {
  return <div className="metric-bar"><div><span>{label}</span><strong>{value}{suffix}</strong></div><div className="bar-track" aria-label={`${label}: ${value}${suffix}`}><span style={{ width: `${Math.min(100, value)}%` }} /></div></div>;
}
