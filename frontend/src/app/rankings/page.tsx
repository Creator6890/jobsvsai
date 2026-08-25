import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";
import { AdSlot } from "@/components/AdSlot";
import { RankingsExplorer } from "@/components/RankingsExplorer";
import { getRankings } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "AI job rankings",
  description: "Explore occupations ranked by AI exposure and replacement risk.",
};

export default async function RankingsPage() {
  const occupations = await getRankings();
  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="JobsVsAI Index"
        title="How jobs rank against AI."
        copy="Explore occupations showing the highest and lowest estimated replacement risk across the JobsVsAI index."
      />
      <main className="page-main">
        <div className="container">
          <RankingsExplorer occupations={occupations} />
          <AdSlot slot="rankings" format="horizontal" />
        </div>
      </main>
    </PageShell>
  );
}
