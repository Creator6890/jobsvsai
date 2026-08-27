import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AdSlot } from "@/components/AdSlot";
import { CareerComparison } from "@/components/CareerComparison";
import { CompareSelector } from "@/components/CompareSelector";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupation, getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/compare/[comparison]">): Promise<Metadata> {
  const { comparison } = await params;
  const [aSlug, bSlug] = splitComparison(comparison);
  const [a, b] = await Promise.all([getOccupation(aSlug), getOccupation(bSlug)]);
  if (!a || !b) {
    return { title: "Career Comparison" };
  }
  return {
    title: `${a.title} vs ${b.title}: Which Career Is Safer From AI?`,
    description: `Compare ${a.title} (AI Exposure ${a.aiExposure}/100, Replacement Risk ${a.replacementRisk}/100) and ${b.title} (AI Exposure ${b.aiExposure}/100, Replacement Risk ${b.replacementRisk}/100). See task automation and human advantages side by side.`,
    openGraph: {
      title: `${a.title} vs ${b.title} AI Career Comparison | JobsVsAI`,
      description: `Side-by-side AI career risk analysis: ${a.title} vs ${b.title}. Compare task exposure, human dependency, and structural resilience.`,
    },
  };
}

export default async function DynamicComparePage({ params }: PageProps<"/compare/[comparison]">) {
  const { comparison } = await params;
  const [aSlug, bSlug] = splitComparison(comparison);
  const [a, b, occupations] = await Promise.all([
    getOccupation(aSlug),
    getOccupation(bSlug),
    getOccupations(),
  ]);

  if (!a || !b) notFound();

  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Side-by-Side Comparison"
        title={`${a.title} vs ${b.title}`}
        copy="A transparent, evidence-led comparison of AI task capability, replacement friction, and structural career resilience."
      />
      <main className="page-main" id="main-content">
        <div className="container">
          <CompareSelector occupations={occupations} initialA={a.slug} initialB={b.slug} />
          <CareerComparison a={a} b={b} />
          <AdSlot slot="compare" format="horizontal" />
        </div>
      </main>
    </PageShell>
  );
}

function splitComparison(value: string) {
  const marker = "-vs-";
  const at = value.indexOf(marker);
  return at < 0 ? ["", ""] : [value.slice(0, at), value.slice(at + marker.length)];
}
