import Link from "next/link";

export type EvidenceReceiptProps = {
  status: "verified" | "preliminary";
  onetVersion?: string;
  capabilityModel?: string;
  scoringModel?: string;
  taskCount?: number;
  coveragePercent?: number;
  confidenceScore?: number;
  confidenceLabel?: string;
  updatedAt?: string | null;
};

export function EvidenceReceipt({
  status,
  onetVersion = "O*NET 30.3",
  capabilityModel = "15 Structural Capability Dimensions",
  scoringModel,
  taskCount,
  coveragePercent,
  confidenceScore,
  confidenceLabel,
  updatedAt,
}: EvidenceReceiptProps) {
  const isVerified = status === "verified";
  const resolvedScoringModel =
    scoringModel?.trim() ||
    (isVerified
      ? "Versioned Multi-Factor Scoring Pipeline"
      : "Cross-Occupational Structural Proxy Engine");

  const formattedDate = updatedAt
    ? new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(
        new Date(updatedAt)
      )
    : "2026 Baseline";

  return (
    <section className="evidence-receipt-card" aria-label="Evidence and Model Receipt">
      <div className="receipt-head">
        <div>
          <span className="section-kicker">Data Provenance</span>
          <h3 className="receipt-title">Evidence &amp; Methodology Receipt</h3>
        </div>
        <span className={`chip ${isVerified ? "safe" : "neutral"}`}>
          {isVerified ? "Verified Analysis" : "Preliminary Estimate"}
        </span>
      </div>

      <dl className="receipt-grid">
        <div className="receipt-item">
          <dt>Taxonomy Source</dt>
          <dd>{onetVersion}</dd>
        </div>

        <div className="receipt-item">
          <dt>AI Capability Model</dt>
          <dd>{capabilityModel}</dd>
        </div>

        <div className="receipt-item">
          <dt>Scoring Model</dt>
          <dd>{resolvedScoringModel}</dd>
        </div>

        <div className="receipt-item">
          <dt>Evidence Coverage</dt>
          <dd>
            {isVerified
              ? `${taskCount ?? 0} assessed tasks (${
                  coveragePercent ? Math.round(coveragePercent) : 100
                }% coverage)`
              : "Cross-occupational proxy evidence"}
          </dd>
        </div>

        <div className="receipt-item">
          <dt>Model Confidence</dt>
          <dd>
            {isVerified
              ? `${confidenceScore ? Math.round(confidenceScore) : 85}/100`
              : confidenceLabel || "Provisional estimate"}
          </dd>
        </div>

        <div className="receipt-item">
          <dt>Data Vintage</dt>
          <dd>{formattedDate}</dd>
        </div>
      </dl>

      <div className="receipt-footer">
        <p className="receipt-note">
          JobsVsAI scores are calculated through a versioned deterministic scoring pipeline from
          occupational task evidence.
        </p>
        <Link className="text-link" href="/methodology">
          See how JobsVsAI calculates AI risk →
        </Link>
      </div>
    </section>
  );
}
