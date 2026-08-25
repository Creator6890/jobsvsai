/** Global AdSense script loader.
 *
 * Loaded once, globally in root layout for site connection and verification.
 * Renders the official AdSense script tag when a client ID is configured.
 *
 * When configuration is absent this renders nothing and does not throw.
 * It uses Next.js `afterInteractive` strategy so it never blocks first paint.
 */

import Script from "next/script";
import { adsenseClientId } from "@/lib/ads";

export function AdsenseScript() {
  if (!adsenseClientId) return null;

  return (
    <Script
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsenseClientId}`}
      strategy="afterInteractive"
      crossOrigin="anonymous"
    />
  );
}
