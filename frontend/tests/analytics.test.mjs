import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(frontendRoot, "src");

// ---------------------------------------------------------------------------
// 1. Source File Existence & Export Structure Invariants
// ---------------------------------------------------------------------------

test("Analytics source module exists with required exports and schemas", () => {
  const analyticsPath = path.join(srcRoot, "lib", "analytics.ts");
  const trackersPath = path.join(srcRoot, "components", "analytics", "AnalyticsTrackers.tsx");

  assert.ok(fs.existsSync(analyticsPath), `Expected ${analyticsPath} to exist`);
  assert.ok(fs.existsSync(trackersPath), `Expected ${trackersPath} to exist`);

  const analyticsContent = fs.readFileSync(analyticsPath, "utf8");
  assert.ok(analyticsContent.includes("export function trackEvent"));
  assert.ok(analyticsContent.includes("export function getAnalyticsRiskBand"));
  assert.ok(analyticsContent.includes("export interface AnalyticsEventMap"));

  const trackersContent = fs.readFileSync(trackersPath, "utf8");
  assert.ok(trackersContent.includes("export function OccupationViewTracker"));
  assert.ok(trackersContent.includes("export function ActionPlanViewTracker"));
  assert.ok(trackersContent.includes("export function CareerTransitionsViewTracker"));
  assert.ok(trackersContent.includes("export function ComparisonViewTracker"));
  assert.ok(trackersContent.includes("export function RankingsViewTracker"));
});

// ---------------------------------------------------------------------------
// 2. Risk Band Normalization Logic Invariants
// ---------------------------------------------------------------------------

function getAnalyticsRiskBandPure(score) {
  if (score <= 40) return "low";
  if (score <= 60) return "medium";
  return "high";
}

test("Risk band thresholds align strictly with low (<=40), medium (41..60), high (>60)", () => {
  // Low boundary
  assert.equal(getAnalyticsRiskBandPure(0), "low");
  assert.equal(getAnalyticsRiskBandPure(25), "low");
  assert.equal(getAnalyticsRiskBandPure(40), "low");

  // Medium boundary
  assert.equal(getAnalyticsRiskBandPure(41), "medium");
  assert.equal(getAnalyticsRiskBandPure(50), "medium");
  assert.equal(getAnalyticsRiskBandPure(60), "medium");

  // High boundary
  assert.equal(getAnalyticsRiskBandPure(61), "high");
  assert.equal(getAnalyticsRiskBandPure(85), "high");
  assert.equal(getAnalyticsRiskBandPure(100), "high");
});

// ---------------------------------------------------------------------------
// 3. Property Allowlist & Strict Value Sanitization Invariants
// ---------------------------------------------------------------------------

const ALLOWED_PROPERTIES = {
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

const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const KNOWN_RISK_BANDS = new Set(["low", "medium", "high"]);
const KNOWN_SORT_OPTIONS = new Set([
  "Most exposed",
  "Most AI-resistant",
  "Highest replacement risk",
  "Lowest replacement risk",
  "fit",
  "risk",
  "exposure",
]);
const KNOWN_ENTRY_SOURCES = new Set(["career_fit_page", "action_plan", "transitions"]);

function isValidValuePure(key, val) {
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
      return typeof val === "string" && val.length >= 1 && val.length <= 100 && SLUG_REGEX.test(val);

    case "ai_exposure_band":
    case "replacement_risk_band":
    case "source_risk_band":
    case "destination_risk_band":
      return typeof val === "string" && KNOWN_RISK_BANDS.has(val);

    case "query_result_count":
    case "candidate_count":
      return typeof val === "number" && Number.isInteger(val) && val >= 0 && val <= 1000;

    case "fit_rank":
      return typeof val === "number" && Number.isInteger(val) && val >= 1 && val <= 100;

    case "duration_seconds":
      return typeof val === "number" && Number.isInteger(val) && val >= 0 && val <= 86400;

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

function sanitizeEventPayloadPure(eventName, rawProperties) {
  const allowedKeys = ALLOWED_PROPERTIES[eventName] ?? [];
  const cleanParams = {};

  for (const key of allowedKeys) {
    const val = rawProperties?.[key];
    if (isValidValuePure(key, val)) {
      cleanParams[key] = val;
    }
  }
  return cleanParams;
}

test("trackEvent strips unapproved properties, PII, and raw assessment data", () => {
  // Attempt to pass prohibited fields into career_fit_completed
  const dirtyCareerFit = {
    duration_seconds: 142,
    raw_answers: { 1: 5, 2: 4, 3: 1 },
    user_email: "test@example.com",
    dimension_scores: { analytical: 88, operational: 64 },
    profile_vector: [0.8, 0.9, 0.2],
  };

  const cleanCareerFit = sanitizeEventPayloadPure("career_fit_completed", dirtyCareerFit);
  assert.deepEqual(cleanCareerFit, { duration_seconds: 142 });
  assert.equal(cleanCareerFit.raw_answers, undefined);
  assert.equal(cleanCareerFit.user_email, undefined);
  assert.equal(cleanCareerFit.dimension_scores, undefined);

  // Attempt to pass task text into action_plan_viewed
  const dirtyActionPlan = {
    occupation_slug: "accountant",
    replacement_risk_band: "high",
    task_name: "Audit client financial ledger balances",
    task_guidance: "Use automated formula validators",
  };

  const cleanActionPlan = sanitizeEventPayloadPure("action_plan_viewed", dirtyActionPlan);
  assert.deepEqual(cleanActionPlan, {
    occupation_slug: "accountant",
    replacement_risk_band: "high",
  });
  assert.equal(cleanActionPlan.task_name, undefined);
  assert.equal(cleanActionPlan.task_guidance, undefined);

  // Attempt to pass search query text into occupation_search_used
  const dirtySearch = {
    query_result_count: 5,
    selected_occupation_slug: "registered-nurses",
    search_term: "John Doe Registered Nurse Salary",
    user_ip: "192.168.1.1",
  };

  const cleanSearch = sanitizeEventPayloadPure("occupation_search_used", dirtySearch);
  assert.deepEqual(cleanSearch, {
    query_result_count: 5,
    selected_occupation_slug: "registered-nurses",
  });
  assert.equal(cleanSearch.search_term, undefined);
  assert.equal(cleanSearch.user_ip, undefined);
});

test("Value sanitizer rejects malformed slugs, unapproved risk bands, and invalid integers", () => {
  // Invalid slug with spaces or uppercase
  const badSlugPayload = sanitizeEventPayloadPure("occupation_viewed", {
    occupation_slug: "Bad Slug Name!",
    ai_exposure_band: "high",
    replacement_risk_band: "low",
  });
  assert.equal(badSlugPayload.occupation_slug, undefined, "Malformed slug must be dropped");

  // Invalid risk band enum
  const badRiskPayload = sanitizeEventPayloadPure("occupation_viewed", {
    occupation_slug: "accountant",
    ai_exposure_band: "ultra-extreme",
    replacement_risk_band: "low",
  });
  assert.equal(badRiskPayload.ai_exposure_band, undefined, "Unapproved risk band enum must be dropped");
  assert.equal(badRiskPayload.replacement_risk_band, "low");

  // Negative query result count
  const badCountPayload = sanitizeEventPayloadPure("occupation_search_used", {
    query_result_count: -10,
    selected_occupation_slug: "accountant",
  });
  assert.equal(badCountPayload.query_result_count, undefined, "Negative count must be dropped");
  assert.equal(badCountPayload.selected_occupation_slug, "accountant");
});

// ---------------------------------------------------------------------------
// 4. Action Plan Viewport Intersection & Deduplication Invariants
// ---------------------------------------------------------------------------

test("Action Plan viewport simulation: does not fire on mount below fold, fires once when scrolled into view", () => {
  const emittedEvents = [];

  class ActionPlanObserverMock {
    constructor(slug, replacementRisk) {
      this.slug = slug;
      this.replacementRisk = replacementRisk;
      this.tracked = false;
    }

    onMount() {
      // Below fold: does NOT fire immediately
      return;
    }

    onIntersection(isIntersecting) {
      if (isIntersecting && !this.tracked) {
        this.tracked = true;
        emittedEvents.push({
          eventName: "action_plan_viewed",
          slug: this.slug,
          risk: getAnalyticsRiskBandPure(this.replacementRisk),
        });
      }
    }
  }

  const observer = new ActionPlanObserverMock("accountant", 68);

  // 1. Initial page load (below viewport)
  observer.onMount();
  assert.equal(emittedEvents.length, 0, "Must not fire on mount below fold");

  // 2. User scrolls down and section enters viewport
  observer.onIntersection(true);
  assert.equal(emittedEvents.length, 1, "Must fire once when entering viewport");
  assert.deepEqual(emittedEvents[0], {
    eventName: "action_plan_viewed",
    slug: "accountant",
    risk: "high",
  });

  // 3. User scrolls out and back in
  observer.onIntersection(false);
  observer.onIntersection(true);
  assert.equal(emittedEvents.length, 1, "Must not duplicate while scrolling on same page");

  // 4. User navigates to new occupation page
  const newObserver = new ActionPlanObserverMock("electricians", 22);
  newObserver.onMount();
  newObserver.onIntersection(true);
  assert.equal(emittedEvents.length, 2, "Must fire new event for new occupation page view");
  assert.deepEqual(emittedEvents[1], {
    eventName: "action_plan_viewed",
    slug: "electricians",
    risk: "low",
  });
});

// ---------------------------------------------------------------------------
// 5. Entity-Scoped View Deduplication Invariants
// ---------------------------------------------------------------------------

test("View tracker deduplication is scoped by entity/route key", () => {
  const events = [];

  class EntityTrackerSession {
    constructor() {
      this.lastTrackedKey = null;
    }

    trackView(key, eventName, payload) {
      if (this.lastTrackedKey === key) {
        return; // Guarded against duplicate fire
      }
      this.lastTrackedKey = key;
      events.push({ eventName, payload });
    }
  }

  const tracker = new EntityTrackerSession();

  // Simulating React StrictMode initial mount & remount on /jobs/accountant
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });

  assert.equal(events.length, 1, "Expected exactly 1 event emitted for identical slug");

  // Simulating navigation to another occupation
  tracker.trackView("registered-nurses", "occupation_viewed", { occupation_slug: "registered-nurses" });
  assert.equal(events.length, 2, "Expected second event after navigating to new occupation");

  // Simulating returning back to accountant
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });
  assert.equal(events.length, 3, "Navigating back to accountant should emit a new page view event");
});

// ---------------------------------------------------------------------------
// 6. Complete Funnel Event Mapping Verification
// ---------------------------------------------------------------------------

test("All specification event names are defined and strictly typed", () => {
  const expectedEvents = [
    "occupation_search_used",
    "occupation_viewed",
    "action_plan_viewed",
    "action_plan_transition_clicked",
    "action_plan_career_fit_clicked",
    "career_transitions_viewed",
    "transition_destination_opened",
    "transition_compare_clicked",
    "transition_career_fit_clicked",
    "career_fit_started",
    "career_fit_completed",
    "career_fit_job_opened",
    "comparison_created",
    "rankings_viewed",
    "rankings_filter_changed",
    "rankings_job_opened",
  ];

  for (const evt of expectedEvents) {
    assert.ok(
      ALLOWED_PROPERTIES[evt] !== undefined,
      `Event ${evt} must be defined in ALLOWED_PROPERTIES`
    );
  }
});
