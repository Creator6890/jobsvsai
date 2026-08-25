/** Google AdSense configuration.
 *
 * Single source of truth for all ad-related settings. Every component reads
 * from here rather than touching process.env directly. Mirrors the GA4
 * pattern in analytics.ts: absent configuration is a safe no-op, not an error.
 *
 * Environment variables are NEXT_PUBLIC_* so Next.js inlines them at build
 * time. They are not secrets — AdSense publisher IDs and slot IDs are visible
 * in page source by design.
 */

// ---------------------------------------------------------------------------
// AdSense identifiers
// ---------------------------------------------------------------------------

/** AdSense publisher/client ID, e.g. "ca-pub-1234567890123456".
 *  Official publisher ID for JobsVsAI account. */
export const adsenseClientId: string =
  process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID ?? "ca-pub-7855774194309157";

// ---------------------------------------------------------------------------
// Global switches
// ---------------------------------------------------------------------------

/** Master ad serving kill-switch for manual ad units. When false, no ad
 *  containers (<ins>) are rendered, no adsbygoogle queue pushes occur,
 *  and no manual ad inventory is requested. */
export const adsEnabled: boolean =
  process.env.NEXT_PUBLIC_ADS_ENABLED === "true";

/** Layout-development mode. When true AND adsEnabled is false, ad slots
 *  render a subtle labelled placeholder so layout can be reviewed before
 *  enabling live ads. When adsEnabled is true, debug mode is ignored. */
export const adsDebug: boolean =
  process.env.NEXT_PUBLIC_ADS_DEBUG === "true";

// ---------------------------------------------------------------------------
// Slot registry
// ---------------------------------------------------------------------------

/** Named ad placements and their AdSense slot IDs. An empty string means
 *  the slot is not yet configured and will render nothing (or a debug
 *  placeholder when adsDebug is true). */
export const slots = {
  home:          process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME ?? "",
  jobPrimary:    process.env.NEXT_PUBLIC_ADSENSE_SLOT_JOB_PRIMARY ?? "",
  jobSecondary:  process.env.NEXT_PUBLIC_ADSENSE_SLOT_JOB_SECONDARY ?? "",
  rankings:      process.env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS ?? "",
  compare:       process.env.NEXT_PUBLIC_ADSENSE_SLOT_COMPARE ?? "",
  newsList:      process.env.NEXT_PUBLIC_ADSENSE_SLOT_NEWS_LIST ?? "",
  newsArticle:   process.env.NEXT_PUBLIC_ADSENSE_SLOT_NEWS_ARTICLE ?? "",
} as const;

export type SlotName = keyof typeof slots;

// ---------------------------------------------------------------------------
// Derived helpers
// ---------------------------------------------------------------------------

/** True when ad units should actually render (enabled + client ID present). */
export const adsReady: boolean = adsEnabled && adsenseClientId !== "";

/** True when debug placeholders should show (debug on, live ads off). */
export const showDebugPlaceholders: boolean = adsDebug && !adsEnabled;
