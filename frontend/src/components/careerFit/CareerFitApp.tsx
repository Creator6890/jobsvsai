"use client";

import { useState, useTransition } from "react";
import type { Occupation } from "@/types/occupation";
import {
  ASSESSMENT_QUESTIONS,
  RESPONSE_OPTIONS,
  calculateProfile,
  matchOccupations,
  sortMatches,
  DIMENSIONS,
  type SortOption,
  type UserProfile,
  type CareerMatch,
} from "@/lib/careerFit";
import { ProfileStrengthBars } from "./ProfileStrengthBars";
import { CareerMatchCard } from "./CareerMatchCard";
import { trackEvent } from "@/lib/analytics";

type CareerFitAppProps = {
  occupations: Occupation[];
};

type ViewState = "intro" | "assessment" | "results";

export function CareerFitApp({ occupations }: CareerFitAppProps) {
  const [view, setView] = useState<ViewState>("intro");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [matches, setMatches] = useState<CareerMatch[]>([]);
  const [sortOption, setSortOption] = useState<SortOption>("fit");
  const [, startTransition] = useTransition();

  const totalQuestions = ASSESSMENT_QUESTIONS.length;
  const currentQuestion = ASSESSMENT_QUESTIONS[currentIndex];
  const answeredCount = Object.keys(answers).length;
  const progressPercent = Math.round((answeredCount / totalQuestions) * 100);

  // --- Handlers ---

  const handleStart = () => {
    trackEvent("career_fit_started");
    setView("assessment");
    setCurrentIndex(0);
  };

  const handleSelectOption = (value: number) => {
    const newAnswers = { ...answers, [currentQuestion.id]: value };
    setAnswers(newAnswers);

    // Auto-advance to next question if not at the end
    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      // Completed all questions — calculate results
      handleComplete(newAnswers);
    }
  };

  const handleNext = () => {
    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      handleComplete(answers);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const handleComplete = (finalAnswers: Record<number, number>) => {
    startTransition(() => {
      const calculatedProfile = calculateProfile(finalAnswers);
      const matchedCareers = matchOccupations(calculatedProfile, occupations, 12);
      setProfile(calculatedProfile);
      setMatches(matchedCareers);
      setView("results");
      trackEvent("career_fit_completed", {
        topStrength: calculatedProfile.topStrengths[0],
      });
      // Scroll to top of results
      if (typeof window !== "undefined") {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  };

  const handleRestart = () => {
    setAnswers({});
    setProfile(null);
    setMatches([]);
    setCurrentIndex(0);
    setView("intro");
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const sortedMatches = sortMatches(matches, sortOption);

  // =========================================================================
  // VIEW 0: Intro / Explanation
  // =========================================================================
  if (view === "intro") {
    return (
      <section className="content-section">
        <div className="container narrow">
          <div className="card career-fit-intro-card">
            <span className="section-kicker">3–5 Minute Assessment</span>
            <h2>Discover careers matched to your work strengths.</h2>
            <p className="intro-copy">
              Answer 20 concise questions about your problem-solving, creative,
              interpersonal, and operational work preferences. We evaluate your
              profile across 8 core dimensions and highlight compatible roles from
              JobsVsAI&apos;s 507 published occupations.
            </p>

            <div className="intro-dimensions-preview">
              <h3>What we measure</h3>
              <div className="dimensions-pill-grid">
                {Object.values(DIMENSIONS).map((dim) => (
                  <div className="dimension-pill-card" key={dim.key}>
                    <strong>{dim.label}</strong>
                    <span>{dim.tagline}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="intro-privacy-box">
              <strong>Exploratory & Private</strong>
              <p>
                Career Fit is an exploratory match based on your self-reported responses
                and occupation characteristics. It is not a validated aptitude or
                psychological assessment. No login required — all evaluations run locally in your browser.
              </p>
            </div>

            <div className="intro-actions">
              <button
                className="button primary"
                onClick={handleStart}
                type="button"
              >
                Begin Career Fit Assessment →
              </button>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // =========================================================================
  // VIEW 1: Active Assessment Flow
  // =========================================================================
  if (view === "assessment") {
    const currentAnswer = answers[currentQuestion.id];

    return (
      <section className="content-section">
        <div className="container narrow">
          {/* Progress Header */}
          <div className="assessment-progress-wrap">
            <div className="assessment-progress-meta">
              <span className="assessment-step-count">
                Question {currentIndex + 1} of {totalQuestions}
              </span>
              <span className="assessment-progress-pct">{progressPercent}% complete</span>
            </div>
            <div className="bar-track" aria-label="Assessment progress">
              <span
                className="bar-fill"
                style={{ width: `${((currentIndex + 1) / totalQuestions) * 100}%` }}
              />
            </div>
          </div>

          {/* Question Card */}
          <article className="card assessment-question-card">
            <div className="question-dimension-tag">
              {DIMENSIONS[currentQuestion.primaryDimension].label}
            </div>

            <h2 className="question-prompt-text">{currentQuestion.prompt}</h2>

            <div className="assessment-options-list" role="radiogroup" aria-label={currentQuestion.prompt}>
              {RESPONSE_OPTIONS.map((option) => {
                const isSelected = currentAnswer === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    className={`assessment-option-btn${isSelected ? " selected" : ""}`}
                    onClick={() => handleSelectOption(option.value)}
                  >
                    <span className="option-indicator">{option.value}</span>
                    <span className="option-label">{option.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Navigation Controls */}
            <div className="assessment-nav-row">
              <button
                type="button"
                className="button secondary compact"
                onClick={handlePrev}
                disabled={currentIndex === 0}
              >
                ← Previous
              </button>

              <div className="assessment-nav-right">
                <button
                  type="button"
                  className="button secondary compact"
                  onClick={handleNext}
                >
                  {currentIndex === totalQuestions - 1 ? "Complete →" : "Next →"}
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    );
  }

  // =========================================================================
  // VIEW 2: Results & Work-Strength Profile Dashboard
  // =========================================================================
  if (view === "results" && profile) {
    return (
      <>
        {/* Profile Summary Banner */}
        <section className="section section-tint">
          <div className="container">
            <div className="profile-summary-header">
              <div>
                <span className="section-kicker">Your Work-Strength Profile</span>
                <h2>{profile.summaryHeadline}</h2>
                <p className="profile-narrative-lead">{profile.summaryNarrative}</p>
              </div>
              <button
                type="button"
                className="button secondary"
                onClick={handleRestart}
              >
                Retake Assessment ↺
              </button>
            </div>

            {/* 8 Dimension Strength Breakdown */}
            <div className="profile-breakdown-wrap">
              <ProfileStrengthBars
                dimensionScores={profile.dimensionScores}
                dimensionBands={profile.dimensionBands}
                highlightKeys={profile.topStrengths}
              />
            </div>
          </div>
        </section>

        {/* Recommended Careers Section */}
        <section className="section">
          <div className="container">
            <div className="section-heading-row">
              <div>
                <span className="section-kicker">Compatible Career Matches</span>
                <h2>Careers that align with your profile</h2>
                <p>
                  Occupations from the JobsVsAI database with the highest
                  competency alignment, shown alongside verified AI Exposure
                  and Replacement Risk metrics.
                </p>
              </div>

              {/* Sort Filter Tabs */}
              <div className="filter-pill-group" role="tablist" aria-label="Sort recommendations">
                <button
                  type="button"
                  role="tab"
                  aria-selected={sortOption === "fit"}
                  className={`filter-pill${sortOption === "fit" ? " active" : ""}`}
                  onClick={() => setSortOption("fit")}
                >
                  Best Career Fit
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

            {/* Career Cards Grid */}
            <div className="career-fit-matches-grid">
              {sortedMatches.map((match, index) => (
                <CareerMatchCard
                  match={match}
                  rank={index + 1}
                  key={match.occupation.slug}
                />
              ))}
            </div>

            {/* Strategic Advice / Considerations Footer */}
            <div className="card career-fit-guidance-card">
              <div className="section-kicker">Career Transition Context</div>
              <h3>How to interpret your Career Fit matches</h3>
              <ul className="guidance-list">
                <li>
                  <strong>Career Fit Score</strong> reflects structural overlap
                  between your self-reported problem-solving style and the
                  competency mix demanded by the occupation.
                </li>
                <li>
                  <strong>Exploratory Match</strong>: Career Fit is an exploratory discovery tool based on your self-reported preferences. It is not a validated aptitude or psychological test.
                </li>
                <li>
                  <strong>AI Exposure</strong> measures how much of the
                  occupation&apos;s daily task volume can be augmented or automated
                  by modern language/vision models.
                </li>
                <li>
                  <strong>Replacement Risk</strong> combines AI exposure with
                  labour-market adoption friction and physical/human dependency
                  to estimate net workforce pressure.
                </li>
                <li>
                  A high Career Fit with low Replacement Risk highlights careers that align with your work preferences while maintaining strong AI resilience.
                </li>
              </ul>
            </div>
          </div>
        </section>
      </>
    );
  }

  return null;
}
