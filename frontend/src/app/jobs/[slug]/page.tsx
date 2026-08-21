import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OccupationDetail } from "@/components/OccupationDetail";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupation } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/jobs/[slug]">): Promise<Metadata> {
  const { slug } = await params; const job = await getOccupation(slug);
  if (!job) return { title: "Occupation not found" };
  return { title: `${job.title}: AI exposure & replacement risk`, description: `${job.title} has ${job.aiExposure}/100 AI exposure and ${job.replacementRisk}/100 replacement risk. See tasks, drivers, and safer career moves.`, openGraph: { title: `${job.title} AI career risk analysis`, description: job.verdict } };
}

export default async function JobPage({ params }: PageProps<"/jobs/[slug]">) {
  const { slug } = await params; const job = await getOccupation(slug); if (!job) notFound();
  return <PageShell><PageHero eyebrow={`${job.category} · Updated ${new Date(job.updatedAt).toLocaleDateString("en", { month: "short", year: "numeric" })}`} title={job.title} copy={job.summary}><span className="chip hero-chip">{job.modelVersion}</span></PageHero><main><OccupationDetail job={job} /></main></PageShell>;
}
