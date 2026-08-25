"use client";

import { useState } from "react";
import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import type {
  TransitionAnalysis,
  TransitionSortOption,
} from "@/lib/transitions/types";
import { sortTransitions } from "@/lib/transitions/scoring";
import { TransitionSourceBanner } from "./TransitionSourceBanner";
import { TransitionCard } from "./TransitionCard";

export function TransitionExplorerApp({
  analysis,
}: {
  analysis: TransitionAnalysis;
  allOccupations: Occupation[];
}) {
  const [sortOption, setSortOption] = useState<TransitionSortOption>("fit");

  const sortedTransitions = sortTransitions(analysis.transitions, sortOption);
  const source = analysis.sourceOccupation;

  return (
    <div className="transition-explorer-root">
      {/* 1. Persistent Source Occupation Banner */}
      <section className="section section-tint">
        <div className="container">
          <TransitionSourceBanner
            source={source}
            isLowRisk={analysis.isLowRiskSource}
          />
        </div>
      </section>

      {/* 2. Destination Alternatives Section */}
      <section className="section">
        <div className="container">
          <div className="section-heading-row">
            <div>
              <span className="section-kicker">
                {analysis.isLowRiskSource
                  ? "Adjacent Career Moves"
                  : "Safer Career Alternatives"}
              </span>
              <h2>{analysis.summaryHeadline}</h2>
              <p>{analysis.summaryNarrative}</p>
            </div>

            {/* Sort Filter Tabs */}
            <div
              className="filter-pill-group"
              role="tablist"
              aria-label="Sort transition alternatives"
            >
              <button
                type="button"
                role="tab"
                aria-selected={sortOption === "fit"}
                className={`filter-pill${sortOption === "fit" ? " active" : ""}`}
                onClick={() => setSortOption("fit")}
              >
                Best Transition Fit
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={sortOption === "risk"}
                className={`filter-pill${sortOption === "risk" ? " active" : ""}`}
                onClick={() => setSortOption("risk")}
              >
                Lowest Replacement Risk
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={sortOption === "exposure"}
                className={`filter-pill${sortOption === "exposure" ? " active" : ""}`}
                onClick={() => setSortOption("exposure")}
              >
                Lowest AI Exposure
              </button>
            </div>
          </div>

          {/* Cards Grid */}
          {sortedTransitions.length > 0 ? (
            <div className="transition-cards-grid">
              {sortedTransitions.map((t, index) => (
                <TransitionCard
                  transition={t}
                  source={source}
                  rank={index + 1}
                  key={t.occupation.slug}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              No close transition alternatives found for this occupation in the published catalog.
            </div>
          )}

          {/* 3. Methodology / Guidance Context */}
          <div className="card transition-guidance-card">
            <div className="section-kicker">Transition Context & Guidance</div>
            <h3>How to interpret your transition matches</h3>
            <ul className="guidance-list">
              <li>
                <strong>Transition Fit</strong> reflects structural overlap in
                competencies and work characteristics, balanced against relative
                AI-replacement risk reduction.
              </li>
              <li>
                <strong>Exploratory Estimate</strong>: Transition difficulty is an
                exploratory estimate based on occupational similarity, not
                measured retraining duration or guaranteed hiring outcomes.
              </li>
              <li>
                <strong>AI Resilience</strong>: Destinations with meaningful
                replacement-risk reductions offer greater structural insulation
                against future task automation.
              </li>
            </ul>
          </div>

          {/* 4. Optional Career Fit Assessment CTA */}
          <div className="card transition-career-fit-cta">
            <div>
              <div className="section-kicker">Unsure about your next move?</div>
              <h3>Discover careers matched to your work strengths</h3>
              <p>
                Take our 3-minute, private assessment to evaluate your problem-solving,
                creative, and operational preferences and find compatible careers from scratch.
              </p>
            </div>
            <Link className="button primary" href="/career-fit">
              Take Career Fit Assessment →
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
