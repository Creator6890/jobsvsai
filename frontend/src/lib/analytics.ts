/**
 * JobsVsAI Centralized Product Funnel Analytics Module (V1)
 *
 * Provides a strictly typed, privacy-preserving, and non-blocking event tracking
 * interface across all core product funnels.
 *
 * Core Privacy & Measurement Invariants:
 * - Zero PII (no personal info, names, emails, IPs)
 * - Zero Career Fit raw answers, dimension scores, or full profiles
 * - Zero task text, task descriptions, or guidance strings
 * - Strict property name allowlisting AND value constraint validation
 * - View events fire on meaningful user view / viewport entry
 */

export type RiskBand = "low" | "medium" | "high";

/**
 * Derives standardized analytics risk band from a numeric score [0..100].
 * Thresholds:
 * - Low: <= 40
 * - Medium: 41..60
 * - High: > 60
 */
export function getAnalyticsRiskBand(score: number): RiskBand {
  if (score <= 40) return "low";
  if (score <= 60) return "medium";
  return "high";
}

export type KnownSortOption =
  | "Most exposed"
  | "Most AI-resistant"
  | "Highest replacement risk"
  | "Lowest replacement risk"
  | "fit"
  | "risk"
  | "exposure";

export type KnownEntrySource = "career_fit_page" | "action_plan" | "transitions";

/**
 * Strictly defined event property schemas.
 */
export interface AnalyticsEventMap {
  // ACQUISITION / SEARCH
  occupation_search_used: {
    query_result_count?: number;
    selected_occupation_slug?: string;
  };

  // OCCUPATION DETAIL
  occupation_viewed: {
    occupation_slug: string;
    ai_exposure_band: RiskBand;
    replacement_risk_band: RiskBand;
  };

  // ACTION PLAN (Fires only when section enters user's viewport)
  action_plan_viewed: {
    occupation_slug: string;
    replacement_risk_band: RiskBand;
  };
  action_plan_transition_clicked: {
    occupation_slug: string;
    replacement_risk_band: RiskBand;
  };
  action_plan_career_fit_clicked: {
    occupation_slug: string;
    replacement_risk_band: RiskBand;
  };

  // CAREER TRANSITIONS
  career_transitions_viewed: {
    source_slug: string;
    source_risk_band: RiskBand;
    candidate_count?: number;
  };
  transition_destination_opened: {
    source_slug: string;
    destination_slug: string;
    source_risk_band: RiskBand;
    destination_risk_band?: RiskBand;
  };
  transition_compare_clicked: {
    source_slug: string;
    destination_slug: string;
  };
  transition_career_fit_clicked: {
    source_slug: string;
  };

  // CAREER FIT (STRICT PRIVACY: zero answers or raw profile)
  career_fit_started: {
    entry_source?: KnownEntrySource;
  };
  career_fit_completed: {
    duration_seconds?: number;
  };
  career_fit_job_opened: {
    destination_slug: string;
    fit_rank?: number;
  };

  // COMPARE (Fires authoritative view event when comparison renders)
  comparison_created: {
    occupation_a_slug: string;
    occupation_b_slug: string;
  };

  // RANKINGS
  rankings_viewed: {
    page?: string;
  };
  rankings_filter_changed: {
    sort_by?: KnownSortOption;
    filter_category?: string;
  };
  rankings_job_opened: {
    occupation_slug: string;
    sort_by?: string;
  };

  // SYSTEM / ADS / RELATED
  related_occupation_click?: {
    source_occupation_slug: string;
    related_occupation_slug: string;
    related_occupation_title: string;
    source: string;
  };
  ad_slot_rendered?: {
    placement: string;
  };
}

export type AnalyticsEventName = keyof AnalyticsEventMap;

/** Allowed property keys per event to strictly guarantee zero unwanted data leakage. */
const ALLOWED_PROPERTIES: Record<string, readonly string[]> = {
  occupation_search_used: ["query_result_count", "selected_occupation_slug"],
  occupation_viewed: ["occupation_slug", "ai_exposure_band", "replacement_risk_band"],
  action_plan_viewed: ["occupation_slug", "replacement_risk_band"],
  action_plan_transition_clicked: ["occupation_slug", "replacement_risk_band"],
  action_plan_career_fit_clicked: ["occupation_slug", "replacement_risk_band"],
  career_transitions_viewed: ["source_slug", "source_risk_band", "candidate_count"],
  transition_destination_opened: ["source_slug", "destination_slug", "source_risk_band", "destination_risk_band"],
  transition_compare_clicked: ["source_slug", "destination_slug"],
  transition_career_fit_clicked: ["source_slug"],
  career_fit_started: ["entry_source"],
  career_fit_completed: ["duration_seconds"],
  career_fit_job_opened: ["destination_slug", "fit_rank"],
  comparison_created: ["occupation_a_slug", "occupation_b_slug"],
  rankings_viewed: ["page"],
  rankings_filter_changed: ["sort_by", "filter_category"],
  rankings_job_opened: ["occupation_slug", "sort_by"],
  related_occupation_click: ["source_occupation_slug", "related_occupation_slug", "related_occupation_title", "source"],
  ad_slot_rendered: ["placement"],
};

// ---------------------------------------------------------------------------
// Strict Value Validators
// ---------------------------------------------------------------------------

const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const KNOWN_RISK_BANDS = new Set<string>(["low", "medium", "high"]);
const KNOWN_SORT_OPTIONS = new Set<string>([
  "Most exposed",
  "Most AI-resistant",
  "Highest replacement risk",
  "Lowest replacement risk",
  "fit",
  "risk",
  "exposure",
]);
const KNOWN_ENTRY_SOURCES = new Set<string>(["career_fit_page", "action_plan", "transitions"]);

function isValidSlug(val: unknown): val is string {
  return typeof val === "string" && val.length >= 1 && val.length <= 100 && SLUG_REGEX.test(val);
}

function isValidRiskBand(val: unknown): val is RiskBand {
  return typeof val === "string" && KNOWN_RISK_BANDS.has(val);
}

function isValidBoundedInt(val: unknown, min: number, max: number): val is number {
  return typeof val === "number" && Number.isInteger(val) && val >= min && val <= max;
}

function isValidValue(key: string, val: unknown): boolean {
  if (val === undefined || val === null || val === "") return false;

  switch (key) {
    case "occupation_slug":
    case "source_slug":
    case "destination_slug":
    case "selected_occupation_slug":
    case "occupation_a_slug":
    case "occupation_b_slug":
    case "source_occupation_slug":
    case "related_occupation_slug":
      return isValidSlug(val);

    case "ai_exposure_band":
    case "replacement_risk_band":
    case "source_risk_band":
    case "destination_risk_band":
      return isValidRiskBand(val);

    case "query_result_count":
    case "candidate_count":
      return isValidBoundedInt(val, 0, 1000);

    case "fit_rank":
      return isValidBoundedInt(val, 1, 100);

    case "duration_seconds":
      return isValidBoundedInt(val, 0, 86400);

    case "sort_by":
      return typeof val === "string" && KNOWN_SORT_OPTIONS.has(val);

    case "entry_source":
      return typeof val === "string" && KNOWN_ENTRY_SOURCES.has(val);

    case "filter_category":
    case "related_occupation_title":
    case "source":
    case "placement":
    case "page":
      return typeof val === "string" && val.length >= 1 && val.length <= 80;

    default:
      return false;
  }
}

/** Global window gtag declaration. */
type EventParams = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    gtag?: (command: "event", eventName: string, params?: EventParams) => void;
    dataLayer?: unknown[];
  }
}

/**
 * Emits a structured GA4 analytics event.
 * Safe no-op in SSR, when gtag is unconfigured, or in test environments.
 */
export function trackEvent<E extends AnalyticsEventName>(
  eventName: E,
  properties?: AnalyticsEventMap[E]
): void {
  if (typeof window === "undefined") {
    return;
  }

  // Filter properties against strict allowlist & value constraints
  const allowedKeys = ALLOWED_PROPERTIES[eventName] ?? [];
  const rawObj = (properties || {}) as Record<string, unknown>;
  const cleanParams: EventParams = {};

  for (const key of allowedKeys) {
    const val = rawObj[key];
    if (isValidValue(key, val)) {
      cleanParams[key] = val as string | number | boolean;
    }
  }

  // Debug logger if NEXT_PUBLIC_ANALYTICS_DEBUG is enabled
  if (process.env.NEXT_PUBLIC_ANALYTICS_DEBUG === "true") {
    console.debug(`[Analytics] ${eventName}:`, cleanParams);
  }

  if (typeof window.gtag === "function") {
    try {
      window.gtag("event", eventName, cleanParams);
    } catch {
      // Analytics must never throw or block UI operations
    }
  }
}
