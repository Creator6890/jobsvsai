import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "JobsVsAI — Career intelligence for the AI era", template: "%s — JobsVsAI" },
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
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
