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
      title: `${job.title}: AI exposure & replacement risk`,
      description: `${job.title} has ${job.aiExposure}/100 AI exposure and ${job.replacementRisk}/100 replacement risk. See tasks, drivers, and safer career moves.`,
      openGraph: { title: `${job.title} AI career risk analysis`, description: job.verdict },
    };
  }
  const estimate = await getOccupationEstimate(slug);
  if (!estimate) return { title: "Occupation not found" };
  // The description says "preliminary estimate" in the search snippet too. A page that is
  // honest on screen and silent in the SERP is only half honest.
  return {
    title: `${estimate.title}: preliminary AI exposure estimate`,
    description: `Preliminary estimate for ${estimate.title}. ${estimate.disclaimer}`,
    openGraph: { title: `${estimate.title} — preliminary AI risk estimate`, description: estimate.disclaimer },
  };
}

export default async function JobPage({ params }: PageProps<"/jobs/[slug]">) {
  const { slug } = await params;
  const job = await getOccupation(slug);
  if (job) {
    return (
      <PageShell>
        <PageHero
          eyebrow={`${job.category} · Updated ${new Date(job.updatedAt).toLocaleDateString("en", { month: "short", year: "numeric" })}`}
          title={job.title}
          copy={job.summary}
        >
          <span className="chip hero-chip">{job.modelVersion}</span>
        </PageHero>
        <main><OccupationDetail job={job} /></main>
      </PageShell>
    );
  }

  // No verified score. An occupation may still carry a published preliminary estimate; the
  // estimate route is asked separately rather than folded into the verified one, so nothing
  // can return an estimate to a caller that asked for a verified score.
  const estimate = await getOccupationEstimate(slug);
  if (!estimate) notFound();
  return (
    <PageShell>
      <PageHero
        eyebrow={estimate.category}
        title={estimate.title}
        status={
          <div className="estimate-status-row">
            <span className="chip hero-chip estimate-hero-chip">Preliminary estimate</span>
            <span className="estimate-confidence-pill">{estimate.confidenceLabel}</span>
          </div>
        }
        copy={estimate.summary}
      />
      <main><EstimatedOccupationDetail job={estimate} /></main>
    </PageShell>
  );
}
