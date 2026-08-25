"use client";

import { useEffect, useRef } from "react";
import { trackEvent, getAnalyticsRiskBand } from "@/lib/analytics";

/**
 * Tracks occupation_viewed on the occupation detail page once per slug.
 * Navigating to a different occupation slug fires a new event.
 */
export function OccupationViewTracker({
  slug,
  aiExposure,
  replacementRisk,
}: {
  slug: string;
  aiExposure: number;
  replacementRisk: number;
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    if (trackedRef.current === slug) return;
    trackedRef.current = slug;

    trackEvent("occupation_viewed", {
      occupation_slug: slug,
      ai_exposure_band: getAnalyticsRiskBand(aiExposure),
      replacement_risk_band: getAnalyticsRiskBand(replacementRisk),
    });
  }, [slug, aiExposure, replacementRisk]);

  return null;
}

/**
 * Tracks action_plan_viewed when the Action Plan section actually enters the user's viewport.
 * Uses IntersectionObserver. Fires once per occupation slug.
 */
export function ActionPlanViewTracker({
  slug,
  replacementRisk,
}: {
  slug: string;
  replacementRisk: number;
}) {
  const trackedRef = useRef<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Reset trackedRef if slug changes
    if (trackedRef.current === slug) return;

    const el = sentinelRef.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      // Fallback in environments lacking IntersectionObserver (e.g. older SSR/test runners)
      trackedRef.current = slug;
      trackEvent("action_plan_viewed", {
        occupation_slug: slug,
        replacement_risk_band: getAnalyticsRiskBand(replacementRisk),
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && trackedRef.current !== slug) {
            trackedRef.current = slug;
            trackEvent("action_plan_viewed", {
              occupation_slug: slug,
              replacement_risk_band: getAnalyticsRiskBand(replacementRisk),
            });
            observer.disconnect();
          }
        }
      },
      { threshold: 0.15 }
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [slug, replacementRisk]);

  return (
    <div
      ref={sentinelRef}
      aria-hidden="true"
      style={{
        position: "relative",
        width: "100%",
        height: "1px",
        pointerEvents: "none",
      }}
    />
  );
}

/**
 * Tracks career_transitions_viewed on the transition explorer page once per source slug.
 */
export function CareerTransitionsViewTracker({
  sourceSlug,
  sourceRisk,
  candidateCount,
}: {
  sourceSlug: string;
  sourceRisk: number;
  candidateCount: number;
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    if (trackedRef.current === sourceSlug) return;
    trackedRef.current = sourceSlug;

    trackEvent("career_transitions_viewed", {
      source_slug: sourceSlug,
      source_risk_band: getAnalyticsRiskBand(sourceRisk),
      candidate_count: candidateCount,
    });
  }, [sourceSlug, sourceRisk, candidateCount]);

  return null;
}

/**
 * Tracks comparison_created on the compare page once per pair.
 */
export function ComparisonViewTracker({
  slugA,
  slugB,
}: {
  slugA: string;
  slugB: string;
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${slugA}-vs-${slugB}`;
    if (trackedRef.current === key) return;
    trackedRef.current = key;

    trackEvent("comparison_created", {
      occupation_a_slug: slugA,
      occupation_b_slug: slugB,
    });
  }, [slugA, slugB]);

  return null;
}

/**
 * Tracks rankings_viewed once on mount of the rankings experience.
 */
export function RankingsViewTracker() {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    trackEvent("rankings_viewed", { page: "rankings" });
  }, []);

  return null;
}
