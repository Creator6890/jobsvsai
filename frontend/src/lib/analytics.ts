/** GA4 custom events.
 *
 * One helper, one call site pattern. GA4 itself is initialised once in the root layout;
 * nothing here loads a tag or configures a property, so there is no second initialisation
 * to keep in sync.
 *
 * Every call is a no-op unless gtag is actually on the page: analytics is absent in
 * development, absent when NEXT_PUBLIC_GA_MEASUREMENT_ID is unset, and absent for the
 * moment between first paint and the afterInteractive script landing. Callers should not
 * have to care, so this never throws and never blocks navigation.
 */

/** Values GA4 accepts as an event parameter. No objects, no arrays, no PII. */
type EventParams = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    gtag?: (command: "event", eventName: string, params?: EventParams) => void;
  }
}

export function trackEvent(eventName: string, params: EventParams = {}): void {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;

  // Drop undefined rather than sending empty parameters: "occupation_title": undefined
  // becomes a real, useless dimension in GA4 otherwise.
  const defined = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== ""),
  );

  try {
    window.gtag("event", eventName, defined);
  } catch {
    // Analytics must never break a user action. A blocked tag, a consent tool that
    // replaced gtag, an ad blocker mid-navigation — all of it is non-fatal here.
  }
}
