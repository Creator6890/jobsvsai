import type { NewsImpactLevel } from "@/lib/api";

// V1 shows the band and nothing else. The numeric score exists, is stored and is audited,
// but publishing it would invite readers to compare two stories on a scale that has not
// been calibrated against outcomes yet.
const LABELS: Record<NewsImpactLevel, string> = {
  low: "LOW JOBS IMPACT",
  medium: "MEDIUM JOBS IMPACT",
  high: "HIGH JOBS IMPACT",
};

export function NewsImpactBadge({ level }: { level: NewsImpactLevel }) {
  return <span className={`impact-badge impact-${level}`}>{LABELS[level]}</span>;
}
