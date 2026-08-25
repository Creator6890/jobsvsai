"use client";

/** Reusable ad-slot component.
 *
 * Renders one AdSense `<ins>` element and pushes to the adsbygoogle queue.
 * When ads are disabled, renders nothing (or a debug placeholder).
 *
 * Safety:
 * - Initialises each slot exactly once via a ref guard, even across React
 *   Strict Mode double-renders and client-side navigation.
 * - Never wraps the ad in a clickable container (Google policy violation).
 * - Collapses to zero height when no ad fills, so disabled ads leave no gap.
 */

import { useEffect, useRef } from "react";
import {
  adsReady,
  adsenseClientId,
  showDebugPlaceholders,
  slots,
  type SlotName,
} from "@/lib/ads";
import { trackEvent } from "@/lib/analytics";

declare global {
  interface Window {
    adsbygoogle?: Record<string, unknown>[];
  }
}

type AdSlotProps = {
  /** Which named slot to render. */
  slot: SlotName;
  /** Responsive ad format. Defaults to "auto" for Google's responsive sizing. */
  format?: "auto" | "horizontal" | "vertical" | "rectangle";
  /** Additional CSS class for the wrapper. */
  className?: string;
};

export function AdSlot({ slot, format = "auto", className }: AdSlotProps) {
  const slotId = slots[slot];
  const initialised = useRef(false);

  useEffect(() => {
    if (!adsReady || !slotId || initialised.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
      initialised.current = true;
      trackEvent("ad_slot_rendered", { placement: slot });
    } catch {
      // AdSense errors (blocked, uninitialised, etc.) are non-fatal.
    }
  }, [slot, slotId]);

  // --- Debug placeholder ---
  if (showDebugPlaceholders) {
    return (
      <div
        className={`ad-slot-debug${className ? ` ${className}` : ""}`}
        role="presentation"
        aria-hidden="true"
      >
        <span className="ad-slot-debug-label">ADVERTISEMENT</span>
        <span className="ad-slot-debug-name">{slot}</span>
        <span className="ad-slot-debug-spec">{format === "auto" ? "responsive · auto" : `${format} banner`}</span>
      </div>
    );
  }

  // --- No-op when disabled or unconfigured ---
  if (!adsReady || !slotId) return null;

  // --- Live ad unit ---
  return (
    <div
      className={`ad-slot${className ? ` ${className}` : ""}`}
      aria-hidden="true"
    >
      <span className="ad-label">Advertisement</span>
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={adsenseClientId}
        data-ad-slot={slotId}
        data-ad-format={format}
        data-full-width-responsive="true"
      />
    </div>
  );
}
