import Link from "next/link";
import { AdSlot } from "@/components/AdSlot";
import { OccupationSearch } from "@/components/OccupationSearch";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { getOccupations } from "@/lib/api";
import type { Occupation } from "@/types/occupation";
import { getScoreSemantics } from "@/lib/scoreSemantics";

export const dynamic = "force-dynamic";

export default async function Home() {
  const occupations = await getOccupations();
  const exposed = [...occupations].sort((a, b) => b.aiExposure - a.aiExposure).slice(0, 5);
  const resilient = [...occupations].sort((a, b) => a.replacementRisk - b.replacementRisk).slice(0, 5);

  return (
    <>
      <SiteHeader />
      <main>
        <section className="home-hero">
          <div className="container hero-inner">
            <div className="eyebrow">AI is transforming every career</div>
            <h1>Will AI<br />take your job<span className="accent">?</span></h1>
            <p className="hero-copy">Get your AI Exposure and Replacement Risk scores, understand what is changing, and discover your safest career moves.</p>
            <OccupationSearch popularOccupations={occupations.slice(0, 3)} />
            <p className="trust-line">Two separate scores. Task-level evidence. No fear-based predictions.</p>
          </div>
        </section>

        <section className="section section-tint" aria-labelledby="ranking-preview-title">
          <div className="container">
            <div className="section-kicker">See how jobs compare</div>
            <div className="section-heading-row">
              <div>
                <h2 id="ranking-preview-title">Rankings at a glance</h2>
                <p>Explore the most affected jobs—and the careers built to last.</p>
              </div>
              <Link className="text-link desktop-only" href="/rankings">Explore all rankings →</Link>
            </div>
            <div className="ranking-grid">
              <RankingPreview title="Most exposed jobs" jobs={exposed} score="aiExposure" />
              <RankingPreview title="Most AI-resistant jobs" jobs={resilient} score="replacementRisk" />
            </div>
            <Link className="button secondary mobile-ranking-link" href="/rankings">Explore all rankings →</Link>
          </div>
        </section>

        <section className="section" aria-labelledby="career-fit-cta-title">
          <div className="container">
            <div className="card career-fit-cta-card">
              <div>
                <div className="section-kicker">Not sure which career to search for?</div>
                <h2 id="career-fit-cta-title">Find careers that match how you work.</h2>
                <p>Take a 3-minute assessment across 8 core work dimensions to discover occupations aligned with your work preferences and strengths, paired with verified AI risk metrics.</p>
              </div>
              <Link className="button" href="/career-fit">Take Career Fit Assessment →</Link>
            </div>
          </div>
        </section>

        {/* Ad: after hero + search + ranking previews + career fit — user value first. */}
        <div className="container ad-break">
          <AdSlot slot="home" format="horizontal" />
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

function RankingPreview({
  title,
  jobs,
  score,
}: {
  title: string;
  jobs: Occupation[];
  score: "aiExposure" | "replacementRisk";
  tone?: "risk" | "safe";
}) {
  return (
    <article className="card ranking-preview">
      <div className="card-heading">
        <h3>{title}</h3>
        <span className="muted small">Score /100</span>
      </div>
      {jobs.length === 0 && <p className="empty-state compact">No occupations are published yet.</p>}
      <ol className="ranking-list">
        {jobs.map((job, index) => {
          const sem = getScoreSemantics(score, job[score]);
          return (
            <li key={job.slug}>
              <span className="rank-number">{index + 1}</span>
              <Link href={`/jobs/${job.slug}`}>{job.title}</Link>
              <span className={sem.badgeClass} title={sem.label}>
                {job[score]}
              </span>
            </li>
          );
        })}
      </ol>
    </article>
  );
}
