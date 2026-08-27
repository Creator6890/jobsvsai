import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { EstimatedOccupationDetail } from "@/components/EstimatedOccupationDetail";
import { OccupationDetail } from "@/components/OccupationDetail";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupation, getOccupationEstimate } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/jobs/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const job = await getOccupation(slug);
  if (job) {
    return {
      title: `Will AI Replace ${job.title}? AI Risk & Task Analysis | JobsVsAI`,
      description: `${job.title} has an AI Exposure score of ${job.aiExposure}/100 and Replacement Risk of ${job.replacementRisk}/100. See vulnerable tasks, human advantages, evidence and safer career alternatives.`,
      openGraph: {
        title: `Will AI Replace ${job.title}? AI Risk & Task Analysis | JobsVsAI`,
        description: `${job.title} AI career analysis: ${job.aiExposure}/100 Exposure, ${job.replacementRisk}/100 Replacement Risk. Task-level evidence and human advantages.`,
      },
    };
  }
  const estimate = await getOccupationEstimate(slug);
  if (!estimate) return { title: "Occupation not found | JobsVsAI" };

  const riskRange =
    estimate.replacementRiskLow !== null && estimate.replacementRiskHigh !== null
      ? `${estimate.replacementRiskLow}–${estimate.replacementRiskHigh}`
      : `${estimate.replacementRisk}`;

  return {
    title: `Will AI Replace ${estimate.title}? Preliminary AI Risk Estimate | JobsVsAI`,
    description: `JobsVsAI estimates ${estimate.title} at approximately ${riskRange}/100 Replacement Risk (${estimate.confidenceLabel} confidence). See preliminary evidence and comparable careers.`,
    openGraph: {
      title: `Will AI Replace ${estimate.title}? Preliminary AI Risk Estimate | JobsVsAI`,
      description: `Preliminary estimate for ${estimate.title}: approximately ${riskRange}/100 Replacement Risk. ${estimate.disclaimer}`,
    },
  };
}

export default async function JobPage({ params }: PageProps<"/jobs/[slug]">) {
  const { slug } = await params;
  const job = await getOccupation(slug);
  if (job) {
    return (
      <PageShell>
        <PageHero
          eyebrow={`${job.category} · Verified Analysis`}
          title={job.title}
          copy={job.summary}
        >
          <span className="chip hero-chip">{job.modelVersion}</span>
        </PageHero>
        <main id="main-content">
          <OccupationDetail job={job} />
        </main>
      </PageShell>
    );
  }

  const estimate = await getOccupationEstimate(slug);
  if (!estimate) notFound();
  return (
    <PageShell>
      <PageHero
        eyebrow={`${estimate.category} · Preliminary Estimate`}
        title={estimate.title}
        status={
          <div className="estimate-status-row">
            <span className="chip hero-chip estimate-hero-chip">Preliminary estimate</span>
            <span className="estimate-confidence-pill">{estimate.confidenceLabel}</span>
          </div>
        }
        copy={estimate.summary}
      />
      <main id="main-content">
        <EstimatedOccupationDetail job={estimate} />
      </main>
    </PageShell>
  );
}
