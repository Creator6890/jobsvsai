# Career Transition Explorer V1 — Technical & Product Report

**Date:** 2026-08-25 · **Status:** READY FOR ARCHITECT REVIEW · **Branch:** `agent/career-transitions-v1`

---

## 1. Executive Summary

Career Transition Explorer V1 builds an independent, deterministic recommendation layer enabling users on JobsVsAI to discover realistic career alternatives with lower AI-replacement risk from any published occupation.

### Core Product Invariants
- **Principle**: *Realistic Transition First, AI Resilience Second*.
- **Zero LLM Recommender**: 100% deterministic mathematical evaluation based on O*NET relationship graph data and calibrated competency vectors.
- **Unmodified Scoring Invariants**: Does not alter AI Exposure, Replacement Risk, JVS 1.0.3, promotion snapshots, or database schemas.
- **Privacy First**: Zero user accounts, zero answer tracking, zero client state persisted across sessions.

---

## 2. Data Reused & API Architecture

### Data Sources
1. **O*NET Relationship Graph**: Consumes `relatedCareers` (`slug`, `title`, `replacementRisk`, `relatednessTier`, `relatednessRank`) already populated for every public occupation in `_hydrate` from `public_occupation_related_occupations`.
2. **Structural & Competency Vectors**: Reuses the calibrated 8-dimension work archetype vector model from `src/lib/careerFit` (`analytical`, `creativity`, `communication`, `people`, `practical`, `organization`, `technology`, `leadership`), enriched by `humanDependency` and `physicalDependency`.
3. **Public Catalog**: Consumes `getOccupation(slug)` and `getOccupations()` without modifying backend APIs or introducing duplicate data stores.

---

## 3. Transition Matching & Scoring Algorithm

The matching engine uses a strict **Tiered Candidate Expansion** strategy:

### Candidate Expansion Tiers
- **Tier 1 (Direct O*NET Relations)**: Occupations directly mapped by O*NET (`Primary-Short`, `Primary-Long`, `Supplemental`). Receives highest structural transferability priority ($85 \dots 98\%$).
- **Tier 2 (2-Hop O*NET Relations)**: Adjacent occupations mapped to direct relations. Subject to a strict similarity gate:
  - Vector distance $L_2 \le 14$ (or same category with $L_2 \le 18$),
  - Physical dependency difference $\le 15$,
  - Destination Replacement Risk $\le \text{Source Risk} + 6$.
- **Tier 3 (Category & Structural Fallback)**: Employed only when Tiers 1 and 2 supply fewer than the target recommendation count ($< 12$).

### Mathematical Formula
```
Transition Fit = 0.55 * Transferability + 0.35 * Risk Contribution + 0.10 * AI Exposure Contribution
```
- **Transferability Score ($10 \dots 99\%$)**:
  - Direct: $90 + \text{rankBonus} - (\text{vecDist} \times 0.4)$
  - 2-Hop: $78 - (\text{vecDist} \times 1.1)$
  - Fallback: $65 - (\text{vecDist} \times 1.4)$
- **Risk Contribution ($0 \dots 100$)**:
  - Base: $50 + (\Delta\text{Risk} \times 2.2)$ where $\Delta\text{Risk} = \text{Source Risk} - \text{Dest Risk}$.
  - Severe risk regression penalty: $-18$ points if destination is $> 8$ points riskier.
  - Low-risk source protection: Sources with risk $\le 40$ are not penalized for lateral moves.
- **Exposure Contribution ($0 \dots 100$)**:
  - $50 + (\Delta\text{Exposure} \times 1.2)$.
- **Bounds**: `Transition Fit` is strictly clamped to $[15 \dots 98\%]$.

---

## 4. Observable Transition Difficulty & Explainability

### Difficulty Classification
- **Easier transition**: Direct O*NET `Primary-Short` relations or tight structural overlap ($L_2 \le 12$, close physical and interpersonal demands).
- **Moderate transition**: Adjacent domain roles requiring adaptation to new workflow demands.
- **Larger transition**: Noticeable divergence in physical presence, technical complexity, or human dependency.
- **Disclosure**: *"Transition difficulty is an exploratory estimate based on occupational similarity, not required training time."*

### Why It Fits & Considerations
- Derived purely from observable structural characteristics without inventing credentials, degrees, or certifications.
- Examples:
  - *"Strong alignment in Analytical and Technology competencies."*
  - *"Significantly more people-facing and interpersonal than your current role."*
  - *"Requires substantially more hands-on, physical or on-site work."*

---

## 5. UI & Navigation Integration

1. **Job Detail Page Entry (`/jobs/[slug]`)**:
   - Secondary button *"Explore Career Transitions →"* in the Related Occupations section head.
   - Distinct transition CTA banner at the bottom of the related careers grid.
2. **Transition Explorer Page (`/jobs/[slug]/transitions`)**:
   - **Source Occupation Context**: Persistent header banner displaying the source title, category, model version, and baseline AI metrics.
   - **Interactive Filtering**: Real-time client-side sorting by *Best Transition Fit*, *Lowest Replacement Risk*, and *Lowest AI Exposure*.
   - **Recommendation Cards**: Displays rank, title, category, Transition Fit %, Risk comparison (`Current → Destination`), Exposure comparison, Difficulty badge, "Why this may fit", "Considerations", and 1-click Compare link.
   - **Low-Risk Adaptation**: Automatically shifts narrative from *"Safer alternatives"* to *"Adjacent career paths"* when source risk is $\le 40$.
   - **Career Fit CTA**: Optional link encouraging users unsure of their strengths to take the private 3-minute Career Fit assessment.

---

## 6. Comparison Integration

Every transition recommendation card includes a direct link to the existing comparison experience:
```
/compare/[source-slug]-vs-[destination-slug]
```
This enables users to seamlessly view side-by-side task breakdowns, exposure drivers, and labor-market resilience without creating a separate comparison tool.

---

## 7. SEO Strategy

- **Technical Route**: Public Next.js Server Component at `/jobs/[slug]/transitions`.
- **Metadata & Canonical**: Fully populated title, description, and canonical URL.
- **Robots Directive**: Configured with `robots: { index: false, follow: true }` for V1.
- **Sitemap Exclusion**: 507 transition pages are withheld from `sitemap.xml` until content quality is reviewed by the project architect.

---

## 8. Verification & Test Summary

- **Frontend Tests (`npm test`)**: 33 passed, 0 failed.
- **Frontend Lint (`npm run lint`)**: 0 errors, 0 warnings.
- **Next.js Production Build (`npm run build`)**: PASS (Turbopack, `/jobs/[slug]/transitions` dynamic route registered).
- **Backend Guarded Suite (`./scripts/run-tests.sh`)**: 495 passed, 0 failed.

---

## 9. V2 Opportunities

1. **Career Fit Profile Enrichment**: Optionally weight transition rankings by a user's completed 8-dimension assessment vector if stored in browser session.
2. **Salary & Outlook Integration**: Incorporate BLS median wage bands and projected job growth when official government data layers are staged.
3. **Curated Indexable SEO Cohort**: Promote top 50 high-exposure occupations with high-quality transition mappings to indexable status with custom editorial intros.
