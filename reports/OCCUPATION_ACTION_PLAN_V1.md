# Occupation Action Plan V1 — Technical & Product Report

**Date:** 2026-08-25 · **Status:** READY FOR ARCHITECT REVIEW · **Branch:** `agent/action-plan-v1`

---

## 1. Executive Summary

**Occupation Action Plan V1** provides users with pragmatic, evidence-based career intelligence directly on the occupation detail page (`/jobs/[slug]`).
Instead of generic motivational advice or LLM hallucinations, the Action Plan deterministically synthesizes existing JobsVsAI task data, structural dependency metrics, and O*NET career pathways into clear operational guidance.

### Core Product Principles
- **No LLM / Pure Determinism:** 100% mathematical and rule-based derivation from structured database evidence.
- **Zero Score Mutation:** Does not invent new numerical scores; uses published `replacementRisk` and task metrics solely for categorization and framing.
- **Privacy First:** Zero user tracking, zero account creation, zero database writes.
- **Grounded Copy:** Completely avoids unsupported claims, alarmist language, and terms like "AI-proof", "future-proof", or "guaranteed safe".

---

## 2. Actual Data Available & Reused

Frontend data audit confirmed the complete availability of the following structured fields on the `Occupation` object via `getOccupation(slug)`:

| Field Name | Type | Purpose in Action Plan |
| :--- | :--- | :--- |
| `tasks` | `TaskImpact[]` | Granular O*NET tasks with `exposure`, `automationFeasibility`, `augmentationPotential`, `importance`. |
| `hardestToAutomateTasks` | `string[]` | Pre-calibrated resilient task subset identified by the scoring engine. |
| `humanDependency` | `number (0..100)` | Used to surface interpersonal, empathy, and collaborative defensibility. |
| `physicalDependency` | `number (0..100)` | Used to surface spatial, dexterity, and on-site physical defensibility. |
| `labourMarketResilience`| `number (0..100)` | Used to explain structural demand buffers and institutional stability. |
| `replacementRisk` | `number (0..100)` | Used to assign risk band (`low`, `medium`, `high`) and tailor priority sequencing. |
| `relatedCareers` | `CareerRelationship[]` | Used to contextualize adjacent career transition opportunities. |

---

## 3. Deterministic Rules & Structure

The Action Plan is organized into a clear 4-pillar architecture preceded by a risk-band profile banner and 3 priority pillars.

### A. Risk-Band Classification & Priorities
- **Low Risk ($\le 40$ Replacement Risk) — *Resilient Core Profile*:**
  - *Priority 1:* Integrate AI productivity tools into routine tasks.
  - *Priority 2:* Deepen specialized contextual expertise and human judgment.
  - *Priority 3:* Explore adjacent career growth paths (secondary prominence).
- **Medium Risk ($41\dots60$ Replacement Risk) — *Evolving Workflow Profile*:**
  - *Priority 1:* Adopt AI as a workflow co-pilot for drafting and data tasks.
  - *Priority 2:* Shift focus toward human-dependent, advisory, and relationship responsibilities.
  - *Priority 3:* Monitor exposed task areas & career alternatives (prominent CTA).
- **High Risk ($> 60$ Replacement Risk) — *High-Exposure Transition Profile*:**
  - *Priority 1:* Master AI workflows immediately to accelerate routine deliverables.
  - *Priority 2:* Elevate role above routine execution into strategy, oversight, and client management.
  - *Priority 3:* Actively evaluate transferable career transitions with lower AI risk (prominent CTA).

### B. The 4 Core Action Pillars
1. **01 · Lean Into (Defensible Strengths):**
   - Identifies resilient characteristics directly from `humanDependency` ($\ge 60$ or $\ge 45$), `physicalDependency` ($\ge 50$), and `labourMarketResilience` ($\ge 60$).
   - Selects tasks from `hardestToAutomateTasks` (sorted by lowest exposure first).
2. **02 · Use AI For (Augmentation):**
   - Identifies high-value augmentation opportunities from tasks with `augmentationPotential \ge 50` or `exposure \ge 45`.
   - Explains how AI tools can co-pilot drafting, data structuring, and synthesis with human review.
3. **03 · Watch Closely (Automation Pressure):**
   - Ranks the 3–4 highest exposed tasks in the occupation (`exposure \ge 65` or top by exposure).
   - Provides factual, non-alarmist descriptions of why repeatability drives machine capability.
4. **04 · Consider Alternatives (Adjacent Horizons):**
   - Links directly to `/jobs/[slug]/transitions` for adjacent career paths with lower AI risk.
   - Provides secondary callout to `/career-fit` for users seeking exploratory preference-based matching.

---

## 4. UI Design & Placement Hierarchy

- **Location:** Positioned on `/jobs/[slug]` directly after the task evidence and two-column insight breakdown (`Most exposed` vs `Hardest to automate`), right before the `Related occupations` section.
- **Visual Styling:** Fully native JobsVsAI aesthetic — soft grey background cards, violet brand accents, distinct status badges, and clean typography hierarchy.
- **Responsive Design:** 3-column priorities and 2x2 pillars grid on desktop (1440px/1024px); 1-column vertically stacked layout on mobile (768px, 390px, 360px).

---

## 5. Verification & Safety

- **Frontend Tests (`npm test`):** **48 passed, 0 failed** (including deterministic generation, risk-band framing, task selection, score immutability, copy safety).
- **Linting (`npm run lint`):** **0 errors, 0 warnings**.
- **Next.js Production Build (`npm run build`):** **PASS** (Turbopack, Next.js 16).
- **AdSense Dark State:** Preserved (`NEXT_PUBLIC_ADS_ENABLED=false`, 0 ad slots added inside Action Plan).
- **SEO:** Enhances existing `/jobs/[slug]` pages without generating duplicate routes.

---

## 6. V2 Opportunities

1. **User Profile Personalization:** If a user has completed the Career Fit assessment in the same browser session, highlight action items that specifically match their dominant work dimensions.
2. **Industry Tooling Catalog:** Curate official, verified AI software tools per occupation category once an editorial review process is staged.
