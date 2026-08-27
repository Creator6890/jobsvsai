import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHero, PageShell } from "@/components/PageShell";
import { TransitionExplorerApp } from "@/components/transitions/TransitionExplorerApp";
import { getOccupation, getOccupations } from "@/lib/api";
import { calculateCareerTransitions } from "@/lib/transitions";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const job = await getOccupation(slug);
  if (!job) return { title: "Occupation Not Found" };

  return {
    title: `Career Alternatives & Transitions for ${job.title}`,
    description: `Explore transferable career alternatives for ${job.title} with lower AI replacement risk and compatible work characteristics.`,
    alternates: {
      canonical: `https://jobsvsai.com/jobs/${job.slug}/transitions`,
    },
    // Keep dynamic transition routes noindex for V1 per architectural review
    robots: {
      index: false,
      follow: true,
    },
  };
}

export default async function JobTransitionsPage({ params }: Props) {
  const { slug } = await params;
  const [job, allOccupations] = await Promise.all([
    getOccupation(slug),
    getOccupations(),
  ]);

  if (!job) notFound();

  const analysis = calculateCareerTransitions(job, allOccupations, 10);

  return (
    <PageShell>
      <PageHero
        dark
        eyebrow={`${job.category} · Career Transitions`}
        title={`Career Alternatives for ${job.title}`}
        copy={`Discover realistic, transferable career moves from ${job.title} evaluated across competency overlap and relative AI replacement risk.`}
      >
        <span className="chip hero-chip">
          Replacement Risk {job.replacementRisk}/100
        </span>
      </PageHero>
      <main className="page-main">
        <TransitionExplorerApp
          analysis={analysis}
          allOccupations={allOccupations}
        />
      </main>
    </PageShell>
  );
}
