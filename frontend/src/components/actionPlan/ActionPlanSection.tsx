"use client";

import Link from "next/link";
import type { Occupation } from "@/types/occupation";
import { generateActionPlan } from "@/lib/actionPlan";
import { trackEvent, getAnalyticsRiskBand } from "@/lib/analytics";
import { ActionPlanViewTracker } from "../analytics/AnalyticsTrackers";

export function ActionPlanSection({ job }: { job: Occupation }) {
  const plan = generateActionPlan(job);
  const riskBand = getAnalyticsRiskBand(job.replacementRisk);

  return (
    <section className="content-section action-plan-section" id="action-plan">
      <ActionPlanViewTracker slug={job.slug} replacementRisk={job.replacementRisk} />
      <div className="container">
        {/* Section Header */}
        <div className="section-head">
          <div>
            <div className="section-kicker">Strategic Career Guidance</div>
            <h2>What should you do next?</h2>
            <p>
              Practical steps to stay resilient, adopt AI tools effectively, and
              build on your defensible strengths as {job.title}.
            </p>
          </div>
          <span className={`chip action-band-chip ${plan.riskBand}`}>
            {plan.bandTitle}
          </span>
        </div>

        {/* Profile Context Banner */}
        <div className="card action-profile-card">
          <div className="action-profile-body">
            <strong>{plan.bandTitle}</strong>
            <p>{plan.bandDescription}</p>
          </div>
        </div>

        {/* Priority Pillars */}
        <div className="action-priorities-grid">
          {plan.priorities.map((p) => (
            <div className="card priority-card" key={p.order}>
              <span className="priority-badge">Priority 0{p.order}</span>
              <h4>{p.title}</h4>
              <p>{p.guidance}</p>
            </div>
          ))}
        </div>

        {/* 4 Core Pillars Grid */}
        <div className="action-pillars-grid">
          {/* Pillar 1: Lean Into */}
          <article className="card action-pillar-card lean-card">
            <div className="pillar-header">
              <span className="section-kicker">01 · Defensible Strengths</span>
              <h3>{plan.leanInto.title}</h3>
              <p>{plan.leanInto.description}</p>
            </div>

            {/* Resilient Characteristics */}
            <div className="resilient-characteristics-list">
              {plan.leanInto.characteristics.map((c, i) => (
                <div className="characteristic-item" key={i}>
                  <span className="bullet-icon">✦</span>
                  <span>{c}</span>
                </div>
              ))}
            </div>

            {/* Key Tasks */}
            {plan.leanInto.tasks.length > 0 && (
              <div className="pillar-tasks-wrap">
                <span className="pillar-subhead">Resilient Tasks to Emphasize</span>
                <ul className="pillar-tasks-list">
                  {plan.leanInto.tasks.map((t, idx) => (
                    <li className="pillar-task-item" key={idx}>
                      <div className="task-item-head">
                        <strong>{t.name}</strong>
                        {t.tag && <span className="task-meta-tag tag-resilient">{t.tag}</span>}
                      </div>
                      <p className="task-guidance">{t.guidance}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Pillar 2: Use AI For */}
          <article className="card action-pillar-card augment-card">
            <div className="pillar-header">
              <span className="section-kicker">02 · Augmentation</span>
              <h3>{plan.useAiFor.title}</h3>
              <p>{plan.useAiFor.description}</p>
            </div>

            {plan.useAiFor.tasks.length > 0 && (
              <div className="pillar-tasks-wrap">
                <span className="pillar-subhead">High-Value AI Adoption Areas</span>
                <ul className="pillar-tasks-list">
                  {plan.useAiFor.tasks.map((t, idx) => (
                    <li className="pillar-task-item" key={idx}>
                      <div className="task-item-head">
                        <strong>{t.name}</strong>
                        {t.tag && <span className="task-meta-tag tag-augment">{t.tag}</span>}
                      </div>
                      <p className="task-guidance">{t.guidance}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Pillar 3: Watch Closely */}
          <article className="card action-pillar-card watch-card">
            <div className="pillar-header">
              <span className="section-kicker">03 · Automation Pressure</span>
              <h3>{plan.watchClosely.title}</h3>
              <p>{plan.watchClosely.description}</p>
            </div>

            {plan.watchClosely.tasks.length > 0 && (
              <div className="pillar-tasks-wrap">
                <span className="pillar-subhead">Most Exposed Work Areas</span>
                <ul className="pillar-tasks-list">
                  {plan.watchClosely.tasks.map((t, idx) => (
                    <li className="pillar-task-item" key={idx}>
                      <div className="task-item-head">
                        <strong>{t.name}</strong>
                        {t.tag && <span className="task-meta-tag tag-exposed">{t.tag}</span>}
                      </div>
                      <p className="task-guidance">{t.guidance}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>

          {/* Pillar 4: Consider Alternatives */}
          <article className="card action-pillar-card alternatives-card">
            <div className="pillar-header">
              <span className="section-kicker">04 · Adjacent Horizons</span>
              <h3>{plan.alternatives.title}</h3>
              <p>{plan.alternatives.description}</p>
            </div>

            <div className="alternatives-cta-wrap">
              <Link
                className={`button ${plan.alternatives.transitionProminence === "prominent" ? "primary" : "secondary"}`}
                href={`/jobs/${job.slug}/transitions`}
                onClick={() =>
                  trackEvent("action_plan_transition_clicked", {
                    occupation_slug: job.slug,
                    replacement_risk_band: riskBand,
                  })
                }
              >
                Explore Career Transitions for {job.title} →
              </Link>
              <div className="career-fit-secondary-callout">
                <span>Considering a broader change?</span>
                <Link
                  className="text-link"
                  href="/career-fit"
                  onClick={() =>
                    trackEvent("action_plan_career_fit_clicked", {
                      occupation_slug: job.slug,
                      replacement_risk_band: riskBand,
                    })
                  }
                >
                  Take the private Career Fit assessment →
                </Link>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
