import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";
import { CareerFitApp } from "@/components/careerFit/CareerFitApp";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Career Fit Assessment — Find Careers Matched to Your Work Strengths",
  description:
    "Take a 3-minute, private assessment to evaluate your analytical, creative, communication, and practical strengths and discover compatible careers alongside their AI risk profiles.",
  alternates: {
    canonical: "https://jobsvsai.com/career-fit",
  },
  openGraph: {
    title: "Career Fit Assessment — JobsVsAI",
    description:
      "Discover which careers match your natural work strengths, paired with authoritative AI Exposure and Replacement Risk scores.",
    url: "https://jobsvsai.com/career-fit",
  },
};

export default async function CareerFitPage() {
  const occupations = await getOccupations();

  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Career Intelligence Assessment"
        title="Find careers that fit how you work."
        copy="Evaluate your strengths across 8 core dimensions. Discover roles tailored to your natural problem-solving style, paired with rigorous AI Exposure and Replacement Risk metrics."
      />
      <main className="page-main">
        <CareerFitApp occupations={occupations} />
      </main>
    </PageShell>
  );
}
