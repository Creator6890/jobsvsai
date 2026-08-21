import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How JobsVsAI separates AI exposure from occupational replacement risk, and what the scores can and cannot tell you.",
};

// Describes the validated Phase 4B/4D/5 engine (JVS 2.0.0-phase4b). The previous version of
// this page documented the legacy JVS 1.0.3 weights, which no longer produce any score the
// product publishes.
const factors = [
  { weight: 35, title: "Task automation exposure", provisional: false,
    copy: "The importance-and-frequency-weighted average of how feasible it is to automate each task in the occupation — not how capable AI is in the abstract." },
  { weight: 10, title: "AI capability proximity", provisional: false,
    copy: "How close current commercially deployable AI is to the capabilities the work actually requires, before real-world constraints are applied." },
  { weight: 15, title: "Human dependency resistance", provisional: false,
    copy: "Trust, judgement, accountability and relationship work, derived from O*NET evidence about the occupation rather than assumed by category." },
  { weight: 15, title: "Physical dependency resistance", provisional: false,
    copy: "Physical presence, manipulation and mobility requirements, reconstructed in Phase 4D directly from O*NET work-context evidence." },
  { weight: 15, title: "Adoption pressure", provisional: true,
    copy: "How readily employers reorganise this work around AI. Still a provisional model — the weakest input in the system, and disclosed as such." },
  { weight: 10, title: "Labour-market resilience resistance", provisional: true,
    copy: "Demand and sector conditions. Also provisional, and also disclosed rather than quietly folded into the headline number." },
];

const taskMetrics = [
  { title: "AI Capability Fit", copy: "Does current commercially deployable AI have the capabilities this task requires? Computed as a weighted geometric mean across the fifteen capability dimensions, so a critical weakness cannot be averaged away by strength elsewhere." },
  { title: "Automation Feasibility", copy: "Even where AI is capable, can this task actually be automated in its real working environment? Physical presence, variability, regulation, accountability and consequence severity all reduce it." },
  { title: "Augmentation Potential", copy: "Could AI substantially help a human do this task, even where full automation is unrealistic? Reported per task. There is deliberately no occupation-level augmentation headline: that number has not been validated." },
];

export default function MethodologyPage() {
  return (
    <PageShell>
      <PageHero
        dark
        eyebrow="Transparent by design"
        title="How JobsVsAI scores work."
        copy="Every score is reproducible from stored inputs, versioned, and explainable down to the individual task. Where the evidence is weak, we say so on the page rather than in a footnote."
      />
      <main>
        <section className="content-section">
          <div className="container two-column">
            <article className="card definition-card">
              <span className="metric-label">AI Exposure</span>
              <div className="score-number">0–100</div>
              <p>How much of this occupation&rsquo;s actual task mix current AI can meaningfully act on. It is a statement about the work, not about your job.</p>
            </article>
            <article className="card definition-card">
              <span className="metric-label">Replacement Risk</span>
              <div className="score-number">0–100</div>
              <p>How likely that exposure is to become reduced human demand, once physical reality, human dependency, accountability, regulation and adoption are accounted for.</p>
            </article>
          </div>
          <div className="container">
            <div className="notice">
              <strong>These two are not the same number, and the gap is the point.</strong>
              <p>A surgeon has tasks current AI can assist with, and a replacement risk that stays low because the work requires physical presence, carries severe consequences, and someone has to be accountable for the outcome. A collapsing of exposure into replacement would get that backwards. Both scores are indices, not probabilities.</p>
            </div>
          </div>
        </section>

        <section className="content-section section-tint">
          <div className="container">
            <div className="section-kicker">Task level</div>
            <div className="section-head">
              <div>
                <h2>Three questions, kept separate</h2>
                <p>Occupations are decomposed into their O*NET tasks, and each task is assessed three ways. Collapsing these into one number is the most common way AI-risk estimates go wrong.</p>
              </div>
            </div>
            <div className="factor-grid">
              {taskMetrics.map((metric) => (
                <article className="card factor-card" key={metric.title}>
                  <h3>{metric.title}</h3>
                  <p>{metric.copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="content-section">
          <div className="container">
            <div className="section-kicker">Occupation level · JVS 2.0.0-phase4b</div>
            <div className="section-head">
              <div>
                <h2 id="provisional-factors">Six factors, and two of them are provisional</h2>
                <p>Weights are fixed in versioned scoring configuration. Two factors — adoption pressure (weight 0.15) and labour-market resilience resistance (weight 0.10), together 25% of Replacement Risk weighting — rest on models we consider provisional, and every occupation page reports how sensitive its score is to them. Provisional means estimated from structural proxies rather than measured directly, and not yet through the validation the other four factors have had.</p>
              </div>
            </div>
            <div className="factor-grid">
              {factors.map((factor) => (
                <article className="card factor-card" key={factor.title}>
                  <strong>{factor.weight}%</strong>
                  <h3>{factor.title} {factor.provisional && <span className="chip">Provisional</span>}</h3>
                  <p>{factor.copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="content-section section-tint">
          <div className="container outlook-grid">
            <div>
              <div className="section-kicker">The bottleneck principle</div>
              <h2>Strength in one capability does not cancel weakness in another</h2>
              <p>If a task is 60% fine physical manipulation and 40% language, excellent language ability does not make the task automatable. Capability Fit uses a weighted geometric mean and applies an explicit cap when a critical requirement is unmet, so a genuine bottleneck survives into the final score instead of being averaged out of it.</p>
            </div>
            <article className="card">
              <h3>The Frontier AI Capability Index</h3>
              <p>JobsVsAI maintains its own index of what commercially deployable AI can currently do across fifteen capability dimensions — from language comprehension to mobility in the physical world. It is a synthesis over independent evaluations, vendor evaluations, academic research and documented deployments, not an average of benchmark scores.</p>
              <p><small>A separate technical-frontier track exists and is deliberately empty: we have not seen evidence sufficient to populate it responsibly.</small></p>
            </article>
          </div>
        </section>

        <section className="content-section">
          <div className="container outlook-grid">
            <div>
              <div className="section-kicker">Coverage and confidence</div>
              <h2>We would rather publish nothing than publish a guess</h2>
              <p>An occupation is only scored when at least 70% of its weighted task evidence is usable. Below that it stays unpublished — no default values, no borrowed category averages, no filling gaps with what similar occupations look like.</p>
              <p>Confidence is reported as a number out of 100, not a High/Medium/Low badge, and combines weighted coverage, mapping quality, capability-evidence quality, source completeness and proxy confidence.</p>
            </div>
            <ol className="method-steps">
              <li><b>01</b><div><strong>Map tasks to capability requirements</strong><p>What the work requires — assessed independently of what AI can currently do, so capability updates do not require remapping.</p></div></li>
              <li><b>02</b><div><strong>Apply the current capability index</strong><p>Producing Capability Fit, Automation Feasibility and Augmentation Potential per task.</p></div></li>
              <li><b>03</b><div><strong>Aggregate with structural constraints</strong><p>Weighted by task importance and frequency, then adjusted for real-world constraints.</p></div></li>
              <li><b>04</b><div><strong>Gate, version and persist</strong><p>Coverage and confidence gates decide publishability. Every score keeps its inputs, weights and formula versions.</p></div></li>
            </ol>
          </div>
        </section>

        <section className="content-section section-tint">
          <div className="container two-column">
            <div>
              <div className="section-kicker">Versioning</div>
              <h2>Every score can be rebuilt</h2>
              <p>Scores are immutable snapshots. Each records the frontier index version, structural proxy model, occupation and task formula versions, capability taxonomy, mapping rubric and evidence policy that produced it. The same inputs and versions always reproduce the same number.</p>
              <p>When frontier AI capability changes, we update the capability index and recalculate — without rebuilding the occupational knowledge base underneath it.</p>
            </div>
            <article className="card">
              <dl className="data-list">
                <div><dt>Occupation data</dt><dd>O*NET 30.3, on source release</dd></div>
                <div><dt>Capability index</dt><dd>On material capability shifts</dd></div>
                <div><dt>Structural proxies</dt><dd>Phase 4D direct O*NET evidence</dd></div>
                <div><dt>Score snapshots</dt><dd>Immutable, versioned, promoted in runs</dd></div>
              </dl>
            </article>
          </div>
        </section>

        <section className="content-section">
          <div className="container">
            <div className="notice">
              <strong>What these scores are not.</strong>
              <p>They are decision-support indices, not probabilities that any individual will lose their job. Job content varies by employer, seniority and country. Adoption pressure and labour-market resilience remain provisional models, and occupations whose scores depend heavily on them are held back from publication rather than shipped with a caveat. Where our evidence is thin, the occupation does not appear at all.</p>
            </div>
            <div className="source-strip">
              <div>
                <strong>Source attribution</strong>
                <p>Occupational data from O*NET 30.3 by the U.S. Department of Labor, Employment and Training Administration. Used under CC BY 4.0. O*NET® is a trademark of USDOL/ETA. JobsVsAI scores, capability taxonomy and structural models are our own interpretation and are not endorsed by USDOL/ETA.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </PageShell>
  );
}
