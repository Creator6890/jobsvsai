import type { Metadata } from "next";
import Script from "next/script";
import { AdsenseScript } from "@/components/AdsenseScript";
import { adsenseClientId } from "@/lib/ads";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "Will AI Take Your Job? AI Job Risk & Career Analysis | JobsVsAI",
    template: "%s | JobsVsAI",
  },
  description: "Understand your job's AI exposure, replacement risk, and the most resilient career moves available to you.",
  openGraph: {
    title: "JobsVsAI — Will AI take your job?",
    description: "Clear, explainable career intelligence for the AI era.",
    type: "website",
    images: [{ url: "/og.png", width: 1536, height: 1024, alt: "Will AI take your job? JobsVsAI career intelligence" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "JobsVsAI — Will AI take your job?",
    description: "AI Exposure. Replacement Risk. Your next move.",
    images: ["/og.png"],
  },
  other: {
    ...(adsenseClientId ? { "google-adsense-account": adsenseClientId } : {}),
  },
};

// Supplied at build time as a NEXT_PUBLIC_* variable, so it is inlined into the client
// bundle. A GA4 measurement ID is not a secret — it ships in the page source of every site
// that uses one — but it is environment-specific, so it stays out of the code.
const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "JobsVsAI",
    url: "https://jobsvsai.com",
    logo: "https://jobsvsai.com/logo.png",
    description: "Evidence-based career intelligence and AI occupational risk research.",
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "JobsVsAI",
    url: "https://jobsvsai.com",
    description: "The intelligence layer for navigating your career through AI.",
  };

  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
        />
      </head>
      <body>
        {children}
        {/* Absent in development and in any environment that does not set the ID, so local
            work and previews never write into the production property. */}
        {gaMeasurementId && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`}
              strategy="afterInteractive"
            />
            <Script id="google-analytics" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${gaMeasurementId}');
              `}
            </Script>
          </>
        )}
        {/* AdSense script — renders nothing when NEXT_PUBLIC_ADS_ENABLED is not "true"
            or when NEXT_PUBLIC_ADSENSE_CLIENT_ID is absent. */}
        <AdsenseScript />
      </body>
    </html>
  );
}
