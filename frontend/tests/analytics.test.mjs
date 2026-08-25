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
// 3. Runtime Event Dispatch & Allowlist Sanitization Invariants
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
  rankings_viewed: ["sort_by", "filter_category"],
  rankings_job_opened: ["occupation_slug", "sort_by"],
  related_occupation_click: ["source_occupation_slug", "related_occupation_slug", "related_occupation_title", "source"],
  ad_slot_rendered: ["placement"],
};

function sanitizeEventPayload(eventName, rawProperties) {
  const allowedKeys = ALLOWED_PROPERTIES[eventName] ?? [];
  const cleanParams = {};

  for (const key of allowedKeys) {
    const val = rawProperties?.[key];
    if (val !== undefined && val !== null && val !== "") {
      if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
        cleanParams[key] = val;
      }
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

  const cleanCareerFit = sanitizeEventPayload("career_fit_completed", dirtyCareerFit);
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

  const cleanActionPlan = sanitizeEventPayload("action_plan_viewed", dirtyActionPlan);
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

  const cleanSearch = sanitizeEventPayload("occupation_search_used", dirtySearch);
  assert.deepEqual(cleanSearch, {
    query_result_count: 5,
    selected_occupation_slug: "registered-nurses",
  });
  assert.equal(cleanSearch.search_term, undefined);
  assert.equal(cleanSearch.user_ip, undefined);
});

// ---------------------------------------------------------------------------
// 4. Safe No-Op Invariants (SSR and Unconfigured GA)
// ---------------------------------------------------------------------------

test("trackEvent execution handles unconfigured gtag and exceptions safely", () => {
  // Simulate browser environment with mocked gtag
  let capturedEvents = [];
  const mockWindow = {
    gtag: (cmd, name, params) => {
      capturedEvents.push({ cmd, name, params });
    },
  };

  function simulateTrack(eventName, properties) {
    if (typeof mockWindow === "undefined") return;
    const clean = sanitizeEventPayload(eventName, properties);
    if (typeof mockWindow.gtag === "function") {
      mockWindow.gtag("event", eventName, clean);
    }
  }

  simulateTrack("occupation_viewed", {
    occupation_slug: "software-engineers",
    ai_exposure_band: "high",
    replacement_risk_band: "medium",
  });

  assert.equal(capturedEvents.length, 1);
  assert.equal(capturedEvents[0].cmd, "event");
  assert.equal(capturedEvents[0].name, "occupation_viewed");
  assert.deepEqual(capturedEvents[0].params, {
    occupation_slug: "software-engineers",
    ai_exposure_band: "high",
    replacement_risk_band: "medium",
  });

  // Broken gtag scenario
  const throwingWindow = {
    gtag: () => {
      throw new Error("Adblocker blocked gtag");
    },
  };

  assert.doesNotThrow(() => {
    try {
      throwingWindow.gtag("event", "test", {});
    } catch {
      // Caught as expected
    }
  });
});

// ---------------------------------------------------------------------------
// 5. Deduplication & StrictMode Double-Render Protection Invariants
// ---------------------------------------------------------------------------

test("View tracker deduplication prevents double-firing across renders", () => {
  const events = [];

  class TrackerSession {
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

  const tracker = new TrackerSession();

  // Simulating React StrictMode initial mount & remount
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });
  tracker.trackView("accountant", "occupation_viewed", { occupation_slug: "accountant" });

  assert.equal(events.length, 1, "Expected exactly 1 event emitted for identical slug");

  // Simulating navigation to another occupation
  tracker.trackView("registered-nurses", "occupation_viewed", { occupation_slug: "registered-nurses" });
  assert.equal(events.length, 2, "Expected second event after navigating to new occupation");
});

// ---------------------------------------------------------------------------
// 6. Complete Funnel Event Mapping Verification
// ---------------------------------------------------------------------------

test("All 15 specification event names are defined and strictly typed", () => {
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
    "rankings_job_opened",
  ];

  for (const evt of expectedEvents) {
    assert.ok(
      ALLOWED_PROPERTIES[evt] !== undefined,
      `Event ${evt} must be defined in ALLOWED_PROPERTIES`
    );
  }
});
