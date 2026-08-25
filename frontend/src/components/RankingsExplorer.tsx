"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { RankingOccupation } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { RankingsViewTracker } from "./analytics/AnalyticsTrackers";

export function RankingsExplorer({
  occupations,
}: {
  occupations: RankingOccupation[];
}) {
  const highestRisk = useMemo(() => {
    return [...occupations]
      .sort((a, b) => b.replacementRisk - a.replacementRisk)
      .slice(0, 10);
  }, [occupations]);

  const lowestRisk = useMemo(() => {
    return [...occupations]
      .sort((a, b) => a.replacementRisk - b.replacementRisk)
      .slice(0, 10);
  }, [occupations]);

  return (
    <>
      <RankingsViewTracker />

      {/* Section 1: Highest Replacement Risk */}
      <section className="rankings-section" aria-labelledby="highest-risk-heading">
        <div className="section-heading-row">
          <div>
            <div className="section-kicker">Top 10 Exposure</div>
            <h2 id="highest-risk-heading">Highest Replacement Risk</h2>
            <p>Careers currently showing the highest estimated replacement risk</p>
          </div>
        </div>

        <div className="card ranking-table">
          <div className="ranking-row ranking-header">
            <b>#</b>
            <b>Occupation</b>
            <b>Category</b>
            <b>Replacement Risk</b>
            <b>AI Exposure</b>
            <span></span>
          </div>
          {highestRisk.map((job, index) => (
            <div className="ranking-row" key={`high-${job.slug}`}>
              <strong className="rank-number">{index + 1}</strong>
              <div>
                <b>{job.title}</b>
                <span className="mobile-category">{job.category}</span>
              </div>
              <span>{job.category}</span>
              <b>{job.replacementRisk}</b>
              <b>{job.aiExposure}</b>
              <Link
                className="button secondary"
                href={`/jobs/${job.slug}`}
                onClick={() =>
                  trackEvent("rankings_job_opened", {
                    occupation_slug: job.slug,
                    sort_by: "Highest replacement risk",
                  })
                }
              >
                View <span aria-hidden="true">→</span>
              </Link>
            </div>
          ))}
          {highestRisk.length === 0 && (
            <div className="empty-state">No occupations are published yet.</div>
          )}
        </div>
      </section>

      {/* Section 2: Lowest Replacement Risk */}
      <section
        className="rankings-section"
        aria-labelledby="lowest-risk-heading"
        style={{ marginTop: "48px" }}
      >
        <div className="section-heading-row">
          <div>
            <div className="section-kicker">Top 10 Resilience</div>
            <h2 id="lowest-risk-heading">Lowest Replacement Risk</h2>
            <p>
              Careers currently showing comparatively lower estimated replacement risk
            </p>
          </div>
        </div>

        <div className="card ranking-table">
          <div className="ranking-row ranking-header">
            <b>#</b>
            <b>Occupation</b>
            <b>Category</b>
            <b>Replacement Risk</b>
            <b>AI Exposure</b>
            <span></span>
          </div>
          {lowestRisk.map((job, index) => (
            <div className="ranking-row" key={`low-${job.slug}`}>
              <strong className="rank-number">{index + 1}</strong>
              <div>
                <b>{job.title}</b>
                <span className="mobile-category">{job.category}</span>
              </div>
              <span>{job.category}</span>
              <b>{job.replacementRisk}</b>
              <b>{job.aiExposure}</b>
              <Link
                className="button secondary"
                href={`/jobs/${job.slug}`}
                onClick={() =>
                  trackEvent("rankings_job_opened", {
                    occupation_slug: job.slug,
                    sort_by: "Lowest replacement risk",
                  })
                }
              >
                View <span aria-hidden="true">→</span>
              </Link>
            </div>
          ))}
          {lowestRisk.length === 0 && (
            <div className="empty-state">No occupations are published yet.</div>
          )}
        </div>
      </section>
    </>
  );
}
