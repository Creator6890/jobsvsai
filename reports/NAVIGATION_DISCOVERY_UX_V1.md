# JobsVsAI — Navigation & Discovery UX V1

**Architecture & Implementation Report**  
**Author:** Worker B / Antigravity  
**Branch:** `agent/navigation-discovery-ux-v1`  
**Status:** **READY FOR ARCHITECT REVIEW**

---

## 1. Root Cause Analysis: Previous Navigation Problem

Prior to Navigation V1, the primary desktop navigation rendered seven distinct text links:
`Home` | `Rankings` | `Career Fit` | `News` | `Compare` | `Methodology` | `About`  
alongside a fixed-width logo (`160px`) and an "Explore the rankings →" CTA button (`185px`).

### Issues Identified
1. **Breakpoint Width Crunch:** The required horizontal inline width for 7 links + CTA + logo + container padding exceeded `980px`. Between `860px` and `1080px` (standard tablet and smaller laptop viewports), the desktop nav experienced severe horizontal cramping and visual clipping before hitting the `860px` mobile breakpoint.
2. **Redundant Actions:** `Home` duplicated the primary branding logo which already links to `/`.
3. **Imbalanced Hierarchy:** `Methodology` occupied primary navigation real estate despite being supporting trust/documentation content rather than a primary discovery action.
4. **Scattered Tool Discovery:** `Career Fit` and `Compare` were split into separate top-level links without contextual framing.

---

## 2. New Information Architecture (IA)

```
[JobsVsAI Logo (/)]
   │
   ├── Rankings (/rankings)
   ├── Career Tools ▾
   │     ├── Career Fit (/career-fit)
   │     └── Compare Careers (/compare)
   ├── News (/news)
   ├── About (/about)
   │
   └── [CTA: Explore the rankings → (/rankings)]
```

- **Home Link:** Removed from desktop primary nav; the JobsVsAI logo remains the authoritative home link.
- **Methodology:** Relocated from primary header to trust destinations (Footer, About page, and contextual "How we calculate this" sections).
- **Public Directory:** No 507-occupation public directory is exposed. All 507 occupation pages remain public and indexed, accessible via search, Career Fit, Transitions, Rankings, and SEO.

---

## 3. Career Tools Dropdown Design

The `CareerToolsDropdown` component is implemented as a compact, accessible client dropdown using the JobsVsAI design language:

### Destinations
1. **Career Fit** (`/career-fit`)
   - *Title:* Career Fit
   - *Description:* Find careers aligned with your work preferences and strengths.
2. **Compare Careers** (`/compare`)
   - *Title:* Compare Careers
   - *Description:* Compare AI Exposure and Replacement Risk side by side.

### Accessibility (A11y) & Interaction
- Semantic `<button aria-expanded={isOpen} aria-haspopup="true">` trigger.
- Full keyboard support: `Enter`/`Space` to open, `Escape` to close with focus return, `ArrowDown` to enter menu.
- Closes on click-outside, route navigation, and tab-out.
- High-contrast visible focus rings and active route cues (`aria-current`).

---

## 4. Mobile Navigation

The mobile navigation menu (`<details className="mobile-menu">`) reflects the exact same IA:
- `Rankings`
- **Career Tools Group:**
  - `Career Fit` (with subtext *"Find careers matching your strengths"*)
  - `Compare Careers` (with subtext *"Side-by-side AI risk comparison"*)
- `News`
- `Methodology`
- `About`

---

## 5. Methodology Relocation

`Methodology` is now prominently anchored as a primary trust destination:
- **Site Footer:** Listed across all pages.
- **Contextual Explanations:** Linked in scoring methodology sections.
- **Direct Route:** `/methodology` remains intact with no SEO deindexing.

---

## 6. Rankings Simplification (Editorial Discovery)

The public rankings page (`/rankings`) has been transformed from an exhaustive, searchable 507-table into two curated, editorial discovery sections:

### Section 1: Highest Replacement Risk (Top 10)
- **Heading:** Highest Replacement Risk
- **Subtitle:** *"Careers currently showing the highest estimated replacement risk"*
- **Data:** Top 10 occupations sorted by `replacementRisk` descending.

### Section 2: Lowest Replacement Risk (Top 10)
- **Heading:** Lowest Replacement Risk
- **Subtitle:** *"Careers currently showing comparatively lower estimated replacement risk"*
- **Data:** Top 10 occupations sorted by `replacementRisk` ascending.

### Row Attributes
- `#` (Rank 1..10)
- Occupation title & category
- Replacement Risk score
- AI Exposure score
- `View career →` action link (`/jobs/[slug]`)

### Copy & Tone Invariants
- Zero sensationalized language (*"AI-proof"*, *"safe jobs"*, *"doomed jobs"*, *"worst jobs"* strictly excluded).
- The underlying API (`getRankings()`) and full 507 dataset remain available for backend calculation.

---

## 7. Homepage Search → Career Fit Handoff

When a user searches for an occupation on the homepage (`/`):
1. **Immediate Value First:** The user receives the exact searched occupation result card with AI Exposure, Replacement Risk, Verdict, and `See the full analysis →`.
2. **Contextual Discovery Second:** Directly within the result card below a subtle divider, the user sees:
   ```
   ──────────────────────────────────────────────────
   Thinking about other options?
   Find careers that align with your strengths and work preferences.
   [ Find My Career Fit → ]  (Takes about 3 minutes)
   ──────────────────────────────────────────────────
   ```
- Links to `/career-fit?from=homepage_search`.
- Integrated seamlessly into the card layout (not an ad, modal, or intrusive banner).

---

## 8. Analytics & Privacy Attribution

1. **Entry Source Attribution:**
   - Added `"homepage_search"` to the allowed enum for `career_fit_started.entry_source`:
     `"career_fit_page" | "action_plan" | "transitions" | "homepage_search"`.
   - `CareerFitApp.tsx` reads `?from=homepage_search` or `?source=homepage_search` dynamically on start.
2. **Strict Privacy Invariants Preserved:**
   - Zero search queries, typed strings, or searched occupation titles are attached to attribution.
   - Zero assessment answers or profile vectors are transmitted.
   - `career_fit_started` fires **only** when the user explicitly clicks "Begin Career Fit Assessment".

---

## 9. Responsive QA Validation

| Viewport | Component / Surface | Status | Verification Notes |
| :--- | :--- | :--- | :--- |
| **1440px** | Desktop Header & Nav | `PASS` | Clean alignment; logo, 4 nav items, dropdown, CTA fit with generous margin. |
| **1280px** | Desktop Header & Nav | `PASS` | No crowding or text wrapping. |
| **1024px** | Desktop Header & Nav | `PASS` | Resolved previous crunch; items fit within 550px total nav width. |
| **768px** | Mobile Nav & Dropdown | `PASS` | Mobile drawer button visible; Career Tools section expands cleanly. |
| **390px** | Search Handoff & Rankings | `PASS` | Continuation CTA wraps gracefully; Top 10 tables format cleanly. |
| **360px** | Small Screen Layouts | `PASS` | Zero horizontal overflow; touch targets $\ge 44\text{px}$. |

---

## 10. Automated Test Results

- **Frontend Test Suite:** **64 passed, 0 failed** (`npm test`)
  - `navigation.test.mjs`: Primary nav items, absence of Home/Methodology in top nav, Career Tools dropdown items, mobile menu items, footer links, homepage search handoff, rankings Top 10 sections (`PASS`)
  - `careerFit.test.mjs`: Assessment integrity, scoring bounds, navigation links (`PASS`)
  - `analytics.test.mjs`: Property allowlists, value sanitization, viewport observation (`PASS`)
  - `actionPlan.test.mjs`, `transitions.test.mjs`, `ads.test.mjs`: All passing (`PASS`)
- **Lint:** **0 errors, 0 warnings** (`npm run lint`)
- **Next.js Production Build:** **PASS** (Turbopack, Next.js 16.3.1)
- **Guarded Backend Suite:** **495 passed in 10.76s** (`./scripts/run-tests.sh`)

---

## 11. Subsystem Invariants & Isolation

- **AI News:** Inert (LLM timeout 90s, all ingestion/generation flags `false`, `provider=null`, 0 cron).
- **AdSense:** Dark (`NEXT_PUBLIC_ADS_ENABLED=false`, `NEXT_PUBLIC_ADS_DEBUG=false`, 0 `adsbygoogle` script tags).
- **Scoring & Backend:** 0 backend files modified, 0 migrations, JVS 1.0.3 and 507/507 data integrity intact.

---

## 12. Conclusion & Readiness

Navigation & Discovery UX V1 has been implemented and tested on branch `agent/navigation-discovery-ux-v1`.

**STATUS:** **READY FOR ARCHITECT REVIEW**
