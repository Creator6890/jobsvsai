import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { EstimatedOccupationDetail } from "@/components/EstimatedOccupationDetail";
import { OccupationDetail } from "@/components/OccupationDetail";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupation, getOccupationEstimate, getOccupations } from "@/lib/api";
import { calculatePercentile } from "@/lib/scorePercentiles";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/jobs/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const job = await getOccupation(slug);
  if (job) {
    return {
      title: `Will AI Replace ${job.title}? AI Risk & Task Analysis`,
      description: `${job.title} has an AI Exposure score of ${job.aiExposure}/100 and Replacement Risk of ${job.replacementRisk}/100. See vulnerable tasks, human advantages, evidence and safer career alternatives.`,
      alternates: {
        canonical: `https://jobsvsai.com/jobs/${job.slug}`,
      },
      openGraph: {
        title: `Will AI Replace ${job.title}? AI Risk & Task Analysis | JobsVsAI`,
        description: `${job.title} AI career analysis: ${job.aiExposure}/100 Exposure, ${job.replacementRisk}/100 Replacement Risk. Task-level evidence and human advantages.`,
        url: `https://jobsvsai.com/jobs/${job.slug}`,
      },
    };
  }
  const estimate = await getOccupationEstimate(slug);
  if (!estimate) return { title: "Occupation Not Found" };

  const riskRange =
    estimate.replacementRiskLow !== null && estimate.replacementRiskHigh !== null
      ? `${estimate.replacementRiskLow}–${estimate.replacementRiskHigh}`
      : `${estimate.replacementRisk}`;

  return {
    title: `Will AI Replace ${estimate.title}? Preliminary AI Risk Estimate`,
    description: `JobsVsAI estimates ${estimate.title} at approximately ${riskRange}/100 Replacement Risk (${estimate.confidenceLabel} confidence). See preliminary evidence and comparable careers.`,
    alternates: {
      canonical: `https://jobsvsai.com/jobs/${estimate.slug}`,
    },
    openGraph: {
      title: `Will AI Replace ${estimate.title}? Preliminary AI Risk Estimate | JobsVsAI`,
      description: `Preliminary estimate for ${estimate.title}: approximately ${riskRange}/100 Replacement Risk. ${estimate.disclaimer}`,
      url: `https://jobsvsai.com/jobs/${estimate.slug}`,
    },
  };
}

export default async function JobPage({ params }: PageProps<"/jobs/[slug]">) {
  const { slug } = await params;
  const [job, allOccupations] = await Promise.all([
    getOccupation(slug),
    getOccupations(),
  ]);
  if (job) {
    const verifiedExposures = allOccupations.map((o) => o.aiExposure);
    const verifiedRisks = allOccupations.map((o) => o.replacementRisk);
    const exposurePercentile = calculatePercentile(job.aiExposure, verifiedExposures);
    const replacementRiskPercentile = calculatePercentile(job.replacementRisk, verifiedRisks);

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
          <OccupationDetail
            job={job}
            exposurePercentile={exposurePercentile}
            replacementRiskPercentile={replacementRiskPercentile}
          />
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
