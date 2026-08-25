/** Global AdSense script loader.
 *
 * Mirrors the GA4 Script injection in layout.tsx: loaded once, globally,
 * only when ads are enabled and a valid client ID is configured.
 *
 * When configuration is absent this renders nothing and does not throw.
 * It uses Next.js `afterInteractive` strategy so it never blocks first paint.
 */

import Script from "next/script";
import { adsReady, adsenseClientId } from "@/lib/ads";

export function AdsenseScript() {
  if (!adsReady) return null;

  return (
    <Script
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsenseClientId}`}
      strategy="afterInteractive"
      crossOrigin="anonymous"
    />
  );
}
