"use client";

import { useEffect, useRef } from "react";
import { trackEvent, getAnalyticsRiskBand } from "@/lib/analytics";

/**
 * Tracks occupation_viewed on the occupation detail page once per slug.
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
 * Tracks action_plan_viewed on ActionPlanSection once per slug.
 */
export function ActionPlanViewTracker({
  slug,
  replacementRisk,
}: {
  slug: string;
  replacementRisk: number;
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    if (trackedRef.current === slug) return;
    trackedRef.current = slug;

    trackEvent("action_plan_viewed", {
      occupation_slug: slug,
      replacement_risk_band: getAnalyticsRiskBand(replacementRisk),
    });
  }, [slug, replacementRisk]);

  return null;
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
 * Tracks rankings_viewed once on mount or when sort/filter changes.
 */
export function RankingsViewTracker({
  sortBy,
  filterCategory,
}: {
  sortBy?: string;
  filterCategory?: string;
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${sortBy || "default"}-${filterCategory || "all"}`;
    if (trackedRef.current === key) return;
    trackedRef.current = key;

    trackEvent("rankings_viewed", {
      sort_by: sortBy,
      filter_category: filterCategory,
    });
  }, [sortBy, filterCategory]);

  return null;
}
