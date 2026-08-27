import type { Metadata } from "next";
import { PageHero, PageShell } from "@/components/PageShell";

export const metadata: Metadata = {
  title: {
    absolute: "How JobsVsAI Calculates AI Exposure & Replacement Risk",
  },
  description:
    "How JobsVsAI separates AI exposure from occupational replacement risk, and what the scores can and cannot tell you.",
  openGraph: {
    title: "How JobsVsAI Calculates AI Exposure & Replacement Risk",
    description:
      "A transparent, task-level methodology separating software capability from structural job replacement.",
  },
};

const factors = [
  {
    weight: 35,
    title: "Task automation exposure",
    provisional: false,
    copy: "The importance-and-frequency-weighted average of how feasible it is to automate each task in the occupation — not how capable AI is in the abstract.",
  },
  {
    weight: 10,
    title: "AI capability proximity",
    provisional: false,
    copy: "How close current commercially deployable AI is to the capabilities the work actually requires, before real-world constraints are applied.",
  },
  {
    weight: 15,
    title: "Human dependency resistance",
    provisional: false,
    copy: "Trust, judgement, accountability and relationship work, derived from O*NET evidence about the occupation rather than assumed by category.",
  },
  {
    weight: 15,
    title: "Physical dependency resistance",
    provisional: false,
    copy: "Physical presence, manipulation and mobility requirements, reconstructed directly from O*NET work-context evidence.",
  },
  {
    weight: 15,
    title: "Adoption pressure",
    provisional: true,
    copy: "How readily employers reorganise this work around AI. A provisional structural model, disclosed transparently as such.",
  },
  {
    weight: 10,
    title: "Labour-market resilience resistance",
    provisional: true,
    copy: "Demand and sector conditions. Also provisional, and disclosed rather than quietly folded into the headline number.",
  },
];

const taskMetrics = [
  {
    title: "AI Capability Fit",
    copy: "Does current commercially deployable AI have the capabilities this task requires? Computed as a weighted geometric mean across fifteen capability dimensions, so a critical weakness cannot be averaged away by strength elsewhere.",
  },
  {
    title: "Automation Feasibility",
    copy: "Even where AI is capable, can this task actually be automated in its real working environment? Physical presence, variability, regulation, accountability and consequence severity all reduce it.",
  },
  {
    title: "Augmentation Potential",
    copy: "Could AI substantially help a human do this task, even where full automation is unrealistic? Reported per task. There is deliberately no occupation-level augmentation headline: that number has not been validated.",
  },
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
        {/* Core definitions */}
        <section className="content-section methodology-section">
          <div className="container">
            <div className="two-column">
              <article className="card definition-card">
                <span className="metric-label">AI Exposure</span>
                <div className="score-number">0–100</div>
                <p>
                  How much of this occupation&rsquo;s actual task mix current AI can meaningfully act on. It is a statement about the work, not about your job.
                </p>
              </article>
              <article className="card definition-card">
                <span className="metric-label">Replacement Risk</span>
                <div className="score-number">0–100</div>
                <p>
                  How likely that exposure is to become reduced human demand, once physical reality, human dependency, accountability, regulation and adoption are accounted for.
                </p>
              </article>
            </div>
            <div className="notice methodology-notice">
              <strong>These two are not the same number, and the gap is the point.</strong>
              <p>
                A surgeon has tasks current AI can assist with, and a replacement risk that stays low because the work requires physical presence, carries severe consequences, and someone has to be accountable for the outcome. A collapsing of exposure into replacement would get that backwards. Both scores are indices, not probabilities.
              </p>
            </div>
          </div>
        </section>

        {/* 7-Step Workflow */}
        <section className="content-section section-tint methodology-section">
          <div className="container">
            <div className="section-kicker">7-Step Measurement Process</div>
            <div className="section-head">
              <div>
                <h2>From raw tasks to calibrated career intelligence</h2>
                <p>How occupational data flows through our capability and constraint models.</p>
              </div>
            </div>
            <ol className="method-steps" style={{ marginTop: "24px" }}>
              <li>
                <b>01</b>
                <div>
                  <strong>Decompose occupations into individual tasks</strong>
                  <p>We break each role down into official O*NET 30.3 task statements, weighted by importance and frequency ratings.</p>
                </div>
              </li>
              <li>
                <b>02</b>
                <div>
                  <strong>Map tasks to capability requirements</strong>
                  <p>Each task is evaluated across 15 AI capability dimensions (e.g. natural language synthesis, pattern recognition, spatial navigation).</p>
                </div>
              </li>
              <li>
                <b>03</b>
                <div>
                  <strong>Measure current commercial AI capability</strong>
                  <p>We evaluate verified frontier and commercial AI systems against required task levels using our Capability Index.</p>
                </div>
              </li>
              <li>
                <b>04</b>
                <div>
                  <strong>Estimate task automation feasibility</strong>
                  <p>Capability is modified by real-world friction: environmental variability, consequence severity, and regulatory burden.</p>
                </div>
              </li>
              <li>
                <b>05</b>
                <div>
                  <strong>Apply human and environmental barriers</strong>
                  <p>We evaluate physical dependency (manual dexterity, mobility) and human dependency (interpersonal trust, ethics, accountability).</p>
                </div>
              </li>
              <li>
                <b>06</b>
                <div>
                  <strong>Calculate AI Exposure and Replacement Risk separately</strong>
                  <p>Task exposure reflects capability overlap; Replacement Risk incorporates structural adoption pressure and labour resilience.</p>
                </div>
              </li>
              <li>
                <b>07</b>
                <div>
                  <strong>Publish only after rigorous evidence gating</strong>
                  <p>Occupations publish as verified only when weighted task coverage exceeds 80% and confidence passes validation thresholds.</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        {/* Task-level metrics */}
        <section className="content-section methodology-section">
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

        {/* Occupation-level factors */}
        <section className="content-section section-tint methodology-section">
          <div className="container">
            <div className="section-kicker">Occupation level</div>
            <div className="section-head">
              <div>
                <h2 id="provisional-factors">Six factors, and two of them are provisional</h2>
                <p>
                  Weights are fixed in versioned scoring configuration. Two factors — adoption pressure (weight 0.15) and labour-market resilience resistance (weight 0.10), together 25% of Replacement Risk weighting — rest on models we consider provisional, and every occupation page reports how sensitive its score is to them. Provisional means estimated from structural proxies rather than measured directly, and not yet through the validation the other four factors have had.
                </p>
              </div>
            </div>
            <div className="factor-grid">
              {factors.map((factor) => (
                <article className="card factor-card" key={factor.title}>
                  <strong>{factor.weight}%</strong>
                  <h3>
                    {factor.title} {factor.provisional && <span className="chip">Provisional</span>}
                  </h3>
                  <p>{factor.copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* The Bottleneck Principle */}
        <section className="content-section methodology-section">
          <div className="container outlook-grid">
            <div>
              <div className="section-kicker">The bottleneck principle</div>
              <h2>Strength in one capability does not cancel weakness in another</h2>
              <p>
                If a task is 60% fine physical manipulation and 40% language, excellent language ability does not make the task automatable. Capability Fit uses a weighted geometric mean and applies an explicit cap when a critical requirement is unmet, so a genuine bottleneck survives into the final score instead of being averaged out of it.
              </p>
            </div>
            <article className="card">
              <h3>The Frontier AI Capability Index</h3>
              <p>
                JobsVsAI maintains its own index of what commercially deployable AI can currently do across fifteen capability dimensions — from language comprehension to mobility in the physical world. It is a synthesis over independent evaluations, vendor evaluations, academic research and documented deployments, not an average of benchmark scores.
              </p>
              <p>
                <small>A separate technical-frontier track exists and is deliberately empty: we have not seen evidence sufficient to populate it responsibly.</small>
              </p>
            </article>
          </div>
        </section>

        {/* Coverage and confidence */}
        <section className="content-section section-tint methodology-section">
          <div className="container outlook-grid">
            <div>
              <div className="section-kicker">Coverage and confidence</div>
              <h2>We would rather publish nothing than publish a guess</h2>
              <p>
                An occupation is only scored when at least 70% of its weighted task evidence is usable. Below that it stays unpublished — no default values, no borrowed category averages, no filling gaps with what similar occupations look like.
              </p>
              <p>
                Confidence is reported as a number out of 100, not a High/Medium/Low badge, and combines weighted coverage, mapping quality, capability-evidence quality, source completeness and proxy confidence.
              </p>
            </div>
            <ol className="method-steps">
              <li>
                <b>01</b>
                <div>
                  <strong>Map tasks to capability requirements</strong>
                  <p>What the work requires — assessed independently of what AI can currently do, so capability updates do not require remapping.</p>
                </div>
              </li>
              <li>
                <b>02</b>
                <div>
                  <strong>Apply the current capability index</strong>
                  <p>Producing Capability Fit, Automation Feasibility and Augmentation Potential per task.</p>
                </div>
              </li>
              <li>
                <b>03</b>
                <div>
                  <strong>Aggregate with structural constraints</strong>
                  <p>Weighted by task importance and frequency, then adjusted for real-world constraints.</p>
                </div>
              </li>
              <li>
                <b>04</b>
                <div>
                  <strong>Gate, version and persist</strong>
                  <p>Coverage and confidence gates decide publishability. Every score keeps its inputs, weights and formula versions.</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        {/* Preliminary Estimates Section */}
        <section className="content-section methodology-section" id="preliminary-estimates">
          <div className="container two-column">
            <div>
              <div className="section-kicker">Two score classes</div>
              <h2>Verified analyses and preliminary estimates</h2>
              <p>
                A <strong>verified</strong> JobsVsAI analysis has cleared every gate above: at least 80% weighted task coverage, a confidence threshold, mapping completeness, and a review of the factors carrying provisional models. 507 occupations currently qualify.
              </p>
              <p>
                A <strong>preliminary estimate</strong> has not. It exists because returning nothing for an occupation we know something real about serves nobody &mdash; but it is never presented as a verified score, never enters our rankings, and is labelled before any number appears.
              </p>
              <p>
                <strong>How estimates are made.</strong> Every estimate is deterministic and uses only data already imported. Nothing is inferred from an occupation&rsquo;s title.
              </p>
              <ul className="method-list">
                <li>
                  <strong>Complete task evidence.</strong> The same calculation used for verified occupations, over full task coverage. Withheld from the verified cohort by a review gate rather than by missing evidence.
                </li>
                <li>
                  <strong>Partial task evidence.</strong> The same calculation over the task evidence available so far, which covers only part of the work.
                </li>
                <li>
                  <strong>Related-occupation estimate.</strong> No task evidence exists, so the figure is drawn from fully analysed occupations that O*NET itself identifies as closely related, weighted by how close that relationship is. These are always shown as a range.
                </li>
              </ul>
              <p>
                <strong>How accurate are they?</strong> We test the related-occupation method by taking each of the 507 verified occupations, hiding its own evidence, and estimating it from its relatives alone. Half the estimates land within 3.6 points of the verified AI Exposure score and 2.8 points of Replacement Risk; nine in ten land within 10.2 and 7.7 points respectively. Roughly 78% land in the same risk band. That is useful, and it is not the same as measured.
              </p>
              <p>
                <strong>Limits.</strong> An estimate carries no task-level breakdown, no career transitions and no action plan, because those need validated task evidence and we will not generate guidance we cannot support. An estimate becomes a verified analysis when the underlying evidence clears the gates &mdash; usually when its tasks are mapped, or when a provisional factor model is validated. Nothing about the estimate is carried over; the verified score is calculated from scratch.
              </p>
            </div>
            <ol className="method-steps">
              <li>
                <b>01</b>
                <div>
                  <strong>Never from a title</strong>
                  <p>An occupation&rsquo;s name is not evidence. Every estimate traces to imported task data or to named, fully analysed related occupations.</p>
                </div>
              </li>
              <li>
                <b>02</b>
                <div>
                  <strong>Labelled before the number</strong>
                  <p>The preliminary status and its confidence appear above the scores, not in a footnote beneath them.</p>
                </div>
              </li>
              <li>
                <b>03</b>
                <div>
                  <strong>Ranges where precision is not earned</strong>
                  <p>Where the evidence supports a span rather than a point, we show the span.</p>
                </div>
              </li>
              <li>
                <b>04</b>
                <div>
                  <strong>Excluded from rankings</strong>
                  <p>Our highest and lowest replacement-risk lists contain verified occupations only, so an estimate can never distort them.</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        {/* Versioning */}
        <section className="content-section section-tint methodology-section">
          <div className="container two-column">
            <div>
              <div className="section-kicker">Versioning</div>
              <h2>Every score can be rebuilt</h2>
              <p>
                Scores are immutable snapshots. Each records the frontier index version, structural proxy model, occupation and task formula versions, capability taxonomy, mapping rubric and evidence policy that produced it. The same inputs and versions always reproduce the same number.
              </p>
              <p>
                When frontier AI capability changes, we update the capability index and recalculate — without rebuilding the occupational knowledge base underneath it.
              </p>
            </div>
            <article className="card">
              <dl className="data-list">
                <div>
                  <dt>Occupation data</dt>
                  <dd>O*NET 30.3, on source release</dd>
                </div>
                <div>
                  <dt>Capability index</dt>
                  <dd>On material capability shifts</dd>
                </div>
                <div>
                  <dt>Structural proxies</dt>
                  <dd>Direct O*NET evidence</dd>
                </div>
                <div>
                  <dt>Score snapshots</dt>
                  <dd>Immutable, versioned, promoted in runs</dd>
                </div>
              </dl>
            </article>
          </div>
        </section>

        {/* Closing notices */}
        <section className="content-section methodology-section methodology-closing-section">
          <div className="container methodology-closing-stack">
            <div className="notice">
              <strong>What these scores are not.</strong>
              <p>
                They are decision-support indices, not probabilities that any individual will lose their job. Job content varies by employer, seniority and country. Adoption pressure and labour-market resilience remain provisional models, and occupations whose scores depend heavily on them are held back from publication rather than shipped with a caveat. Where our evidence is thin, the occupation does not appear at all.
              </p>
            </div>
            <div className="card methodology-attribution-card">
              <strong>Source attribution</strong>
              <p>
                Occupational data from O*NET 30.3 by the U.S. Department of Labor, Employment and Training Administration. Used under CC BY 4.0. O*NET® is a trademark of USDOL/ETA. JobsVsAI scores, capability taxonomy and structural models are our own interpretation and are not endorsed by USDOL/ETA.
              </p>
            </div>
          </div>
        </section>
      </main>
    </PageShell>
  );
}
