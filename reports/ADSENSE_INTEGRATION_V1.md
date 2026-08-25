# JobsVsAI — Google AdSense Integration V1 Report

**Date**: 2026-08-25  
**Author**: Worker B (Antigravity)  
**Status**: Implemented, Verified, Disabled by Default (Awaiting AdSense Approval & Activation)  
**Branch**: `agent/antigravity`  

---

## 1. Executive Summary

A production-safe, privacy-aware, manual-placement Google AdSense integration has been implemented for JobsVsAI. 

### Core Product Invariants Preserved
- **User Value First → Ads After Value**: Users always see core career intelligence (AI Exposure, Replacement Risk, task-level evidence, search, rankings, comparisons, news headlines/context) **before** encountering any advertising.
- **Zero Runtime Overhead When Disabled**: When `NEXT_PUBLIC_ADS_ENABLED=false` (the default), **zero** external Google ad scripts are loaded, **zero** network ad requests are issued, and unfilled ad slots collapse cleanly with no empty layout space.
- **Isolated from Scoring and Backend Logic**: The integration is 100% frontend-only. No scoring algorithms, O*NET mappings, production snapshots, 507-occupation invariants, or AI News backend services were modified.
- **No Auto Ads**: Google Auto Ads are explicitly disabled to prevent uncontrolled algorithmic ad injection into data visualizations and career scorecards.

---

## 2. Architecture & Components

```
                    ┌────────────────────────┐
                    │      Root Layout       │
                    │  (app/layout.tsx)      │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌────────────────────────┐                    ┌────────────────────────┐
│     AdsenseScript      │                    │         Pages          │
│(components/AdsenseScript)                   │ (/, /jobs, /rankings,  │
│ - Conditional script   │                    │  /compare, /news)      │
│ - afterInteractive     │                    └───────────┬────────────┘
└────────────────────────┘                                │
                                                          ▼
                                              ┌────────────────────────┐
                                              │         AdSlot         │
                                              │  (components/AdSlot)   │
                                              │ - Live ins.adsbygoogle │
                                              │ - Debug placeholder    │
                                              │ - Zero-collapse        │
                                              └───────────┬────────────┘
                                                          │
                                                          ▼
                                              ┌────────────────────────┐
                                              │     lib/ads.ts         │
                                              │ Single Source of Truth │
                                              │ - adsEnabled           │
                                              │ - adsReady             │
                                              │ - adsenseClientId      │
                                              │ - slot registry        │
                                              └────────────────────────┘
```

### Key Modules Created & Modified

1. **`frontend/src/lib/ads.ts`**  
   Centralized configuration module mirroring the pattern established by `frontend/src/lib/analytics.ts`. Exports:
   - `adsEnabled`: Master kill switch (`process.env.NEXT_PUBLIC_ADS_ENABLED === "true"`).
   - `adsDebug`: Development placeholder mode (`process.env.NEXT_PUBLIC_ADS_DEBUG === "true"`).
   - `adsenseClientId`: Publisher identifier string.
   - `slots`: Named mapping of placement keys to AdSense slot IDs (`home`, `jobPrimary`, `jobSecondary`, `rankings`, `compare`, `newsList`, `newsArticle`).
   - `adsReady`: Derived boolean requiring both `adsEnabled === true` AND `adsenseClientId !== ""`.
   - `showDebugPlaceholders`: Derived boolean (`adsDebug && !adsEnabled`).

2. **`frontend/src/components/AdsenseScript.tsx`**  
   Global script loader mounted in `app/layout.tsx`.
   - Injected via Next.js `Script` with `strategy="afterInteractive"` so it never blocks First Contentful Paint (FCP).
   - Renders `null` if `adsReady` is false.
   - Loaded once at layout level; prevents duplicate script tag injection during Next.js client-side navigation.

3. **`frontend/src/components/AdSlot.tsx`**  
   Reusable ad container and lifecycle manager.
   - Renders the standard Google `<ins className="adsbygoogle" ... />` unit.
   - Safely pushes `{}` to `window.adsbygoogle` using a `useRef` guard to avoid duplicate initialization across React Strict Mode re-renders and page transitions.
   - Never wraps ads inside anchor (`<a>`) tags or clickable wrappers (complying with Google AdSense Policies).
   - Automatically renders non-commercial dashed debug placeholders when `showDebugPlaceholders` is active.
   - Emits custom GA4 event `trackEvent("ad_slot_rendered", { placement: slot })` when rendered.

4. **`frontend/src/app/ads.txt/route.ts`**  
   Dynamic Next.js Route Handler serving `/ads.txt` with `Content-Type: text/plain; charset=utf-8`.
   - When `NEXT_PUBLIC_ADSENSE_CLIENT_ID` is configured with a valid publisher ID (`ca-pub-XXXXXXXXXXXXXXXX` or `pub-XXXXXXXXXXXXXXXX`), dynamically extracts the publisher ID and formats the standard Google record:  
     `google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0`
   - When unconfigured or invalid, returns a clean 200 response with an empty body (correctly indicating no authorized sellers declared prior to AdSense account approval).

---

## 3. Placement Strategy

Every ad placement adheres to **User Value First → Ads After Value**:

| Page Surface | Ad Slot Key | Format | Placement Location | Preceding User Value |
| :--- | :--- | :--- | :--- | :--- |
| **Homepage (`/`)** | `home` | `horizontal` | Between Rankings Preview section and Site Footer | Hero banner, AI transformation premise, occupation search bar, and top 5 most exposed / AI-resistant ranking previews |
| **Job Detail (`/jobs/[slug]`) — Primary** | `jobPrimary` | `horizontal` | Between top Score Grid and Task Evidence Table | Occupation Title, Category, Model Version, AI Exposure score, Replacement Risk score + provisional footnote, and Evidence Quality bars |
| **Job Detail (`/jobs/[slug]`) — Secondary** | `jobSecondary` | `horizontal` | Between 2-Column Deep Dive ("Most exposed" / "Hardest to automate") and "Related occupations" | Full Task Evidence Table and deep-dive automation feasibility analysis |
| **Rankings (`/rankings`)** | `rankings` | `horizontal` | Directly after the interactive `RankingsExplorer` table | Full ranking view tabs, search filter, and the complete list of 507 ranked occupations |
| **Dynamic Compare (`/compare/[a]-vs-[b]`)** | `compare` | `horizontal` | Directly after the `CareerComparison` side-by-side card | Complete head-to-head metric table (7 comparison dimensions) and comparative AI resilience verdict |
| **Newsroom Listing (`/news`)** | `newsList` | `horizontal` | Inserted into the `.news-grid` after the 4th article card | Filter tabs and the top 4 news stories with jobs-impact badges |
| **News Article (`/news/[slug]`)** | `newsArticle` | `auto` | Between "What happened" section and "Why it matters for jobs" section | Headline, impact badge, source attribution, and primary event summary |

---

## 4. Mobile Responsiveness & CLS Prevention

### CSS Strategy (`globals.css`)
- **Container Constrained**: `.ad-slot` and `.ad-slot-debug` are capped at `max-width: var(--container)` (1180px) with `width: 100%` and `margin: var(--gap-lg) auto`.
- **Horizontal Overflow Guard**: `overflow: hidden` on container ensures wide ads never trigger horizontal body scroll on 360px–430px viewports.
- **Collapsible Empty Space**: `.ad-slot:empty { display: none; }` prevents phantom whitespace when slots are unfilled or disabled.
- **News Grid Separation**: `.ad-slot-news-list` uses `grid-column: 1 / -1` with subtle top/bottom borders to ensure ads span the full grid width and cannot be visually confused with news cards.
- **Tested Breakpoints**: Layout rules verified against mobile and desktop widths: `360px`, `390px`, `620px`, `768px`, `1024px`, and `1440px`.

---

## 5. Configuration Reference

All variables use the `NEXT_PUBLIC_*` convention and are inlined at build time.

```bash
# Master enable switch (must be explicitly "true" to activate)
NEXT_PUBLIC_ADS_ENABLED=false

# Publisher identifier (e.g. ca-pub-1234567890123456)
NEXT_PUBLIC_ADSENSE_CLIENT_ID=

# Debug placeholder mode (active only when ADS_ENABLED is false)
NEXT_PUBLIC_ADS_DEBUG=false

# Ad unit slot IDs generated from Google AdSense console
NEXT_PUBLIC_ADSENSE_SLOT_HOME=
NEXT_PUBLIC_ADSENSE_SLOT_JOB_PRIMARY=
NEXT_PUBLIC_ADSENSE_SLOT_JOB_SECONDARY=
NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS=
NEXT_PUBLIC_ADSENSE_SLOT_COMPARE=
NEXT_PUBLIC_ADSENSE_SLOT_NEWS_LIST=
NEXT_PUBLIC_ADSENSE_SLOT_NEWS_ARTICLE=
```

Templates updated:
- `.env.example`
- `.env.production.example`
- `docker-compose.yml` (frontend `build.args` and `environment`)
- `frontend/Dockerfile` (`ARG` and `ENV` declarations)

---

## 6. Privacy & Consent Management (CMP) Readiness

- **CMP Readiness vs. Automatic Compliance**: The codebase is architected to be **CMP-ready**, but loading via `afterInteractive` does not automatically confer legal GDPR compliance on its own.
- **External CMP Configuration Required**: Before live ads are served in jurisdictions requiring explicit consent (EU/EEA/UK/CPRA), the site owner must configure Google AdSense's **Privacy & Messaging** console (or a Google-certified TCF v2.2 Consent Management Platform).
- **No Custom/Homegrown Cookie Modals**: We intentionally avoid custom non-certified cookie banners that fail ePrivacy/TCF audit requirements. Google's certified consent layer manages consent dialogs and signals directly.

---

## 7. Auto Ads Policy

**Auto Ads are deliberately kept disabled.**
- Google Auto Ads automatically injects ad units into arbitrary DOM nodes (e.g., between score rows, inside tables, above heroes).
- Because JobsVsAI's value proposition depends on trust, analytical rigor, and pristine visual hierarchy, uncontrolled ad insertion would degrade the user experience and potentially disrupt interactive components like `RankingsExplorer` and `OccupationSearch`.

---

## 8. Verification & Testing

### Frontend Test Suite (`frontend/tests/ads.test.mjs`)
13 automated unit and invariant tests executed via Node.js native test runner (`npm test`):
- `ads.txt` unconfigured client ID returns empty body (Status 200).
- `ads.txt` valid client ID extracts `pub-XXXX` and generates the standard Google record.
- `adsReady` truth table verification (`adsEnabled` AND `adsenseClientId`).
- `showDebugPlaceholders` truth table verification (`adsDebug` AND NOT `adsEnabled`).
- All 7 named slot constants verified in `lib/ads.ts`.
- `AdsenseScript` null return when unconfigured.
- `AdSlot` component safety invariants (no anchor wrapping, clean null return when inactive).
- Placement invariant tests for Homepage, Job Detail, Rankings, Compare, News List, and News Article.

**Result**: 13/13 passing (41ms).

### Build & Type Verification
- `npm run lint` — 0 errors, 0 warnings.
- `npm run build` — Successful standalone Next.js 16 build; `/ads.txt` generated as dynamic route.

---

## 9. Visual Integration & Merge Gate Review

All placements were audited visually using layout-representative debug placeholders (`NEXT_PUBLIC_ADS_DEBUG=true`) across responsive viewports: `360px`, `390px`, `768px`, `1024px`, and `1440px`.

### Visual Quality Standards Applied
- **Native Typography & Colors**: Advertisement label uses `.ad-label` with `var(--muted)` (`#676776`), uppercase tracking (`.62rem`, `letter-spacing: .12em`), clearly identifying ads without masquerading as editorial badges or recommendation chips.
- **Understated Chrome**: Neutral background (`var(--soft)`), subtle borders (`1px dashed #dcd8e8` in debug, `1px solid var(--line)` for dividers), zero gradients, zero heavy shadows.
- **Container Alignment**: All placements adhere to the site's responsive container scale (`1180px` max, with `min(calc(100% - 40px), var(--container))` and `min(calc(100% - 24px), ...)` gutters on mobile).
- **Responsive Overflow Guard**: Container-constrained with `overflow: hidden` to eliminate horizontal body scrolling on mobile devices.

### Placement-by-Placement Merge Gate

| Placement Surface | Status | Visual Fit & Invariant Assessment |
| :--- | :--- | :--- |
| **HOMEPAGE** | **PASS** | Appears after hero, search, and the complete top-5 ranking previews in `.container.ad-break`. First viewport remains 100% ad-free. Landing page aesthetic preserved. |
| **JOB PRIMARY** | **PASS** | Sits in `.container.ad-break` between the 3-column Score Grid and the Task Evidence Table. The user receives their full core answer (AI Exposure, Replacement Risk, Evidence Quality) before encountering any ad. |
| **JOB SECONDARY** | **PASS** | Placed in `.container.ad-break` at a natural content boundary between the 2-Column Deep Dive ("Most exposed" / "Hardest to automate") and "Related occupations". No score cards or task lists are fragmented. |
| **RANKINGS** | **PASS** | Sits below `RankingsExplorer` within `.container`. Never injected inside row structures; does not interfere with ranking tabs, search input, or sorting. |
| **COMPARE** | **PASS** | Placed below `CareerComparison` within `.container`. Full 7-metric comparison table and AI resilience verdict precede the unit. |
| **NEWS LIST** | **PASS** | Spans full grid width (`grid-column: 1 / -1`) with top and bottom dividers between the 4th and 5th article cards. Visually distinct from article cards; cannot be mistaken for editorial news. |
| **NEWS ARTICLE** | **PASS** | Sits inside `.container.news-article` (capped at reading measure `68ch`) between "What happened" and "Why it matters for jobs". Creates a natural editorial pause. Headline and source attribution remain uninterrupted. |

---

## 10. AdSense Owner Pre-Monetization Checklist

Before turning monetization on in production, the site owner must complete the following steps:

1. [ ] **AdSense Account Setup**: Sign in to [Google AdSense](https://www.google.com/adsense/) and add site `jobsvsai.com`.
2. [ ] **Domain Verification**: Deploy this release with `NEXT_PUBLIC_ADS_ENABLED=false` and `NEXT_PUBLIC_ADSENSE_CLIENT_ID=ca-pub-XXXXXXXXXXXXXXXX`. This enables `/ads.txt` on `https://jobsvsai.com/ads.txt` for Google's crawler.
3. [ ] **Privacy & Messaging Configuration**: In Google AdSense Console → *Privacy & messaging*, enable European regulations (GDPR) and US state regulations (CPRA) consent messages.
4. [ ] **Create Manual Ad Units**: In AdSense Console → *Ads* → *By ad unit* → *Display ads*:
   - Create Responsive Ad Unit: `home_bottom` → Note Slot ID.
   - Create Responsive Ad Unit: `job_detail_primary` → Note Slot ID.
   - Create Responsive Ad Unit: `job_detail_secondary` → Note Slot ID.
   - Create Responsive Ad Unit: `rankings_bottom` → Note Slot ID.
   - Create Responsive Ad Unit: `compare_bottom` → Note Slot ID.
   - Create Responsive Ad Unit: `news_list_mid` → Note Slot ID.
   - Create Responsive Ad Unit: `news_article_mid` → Note Slot ID.
5. [ ] **Configure Production `.env`**: Set the slot IDs and publisher ID on the host.
6. [ ] **Turn On Ads**: Set `NEXT_PUBLIC_ADS_ENABLED=true` in production `.env` and rebuild the frontend container.

---

## 11. Rollback & Emergency Procedures

If ads cause layout degradation, performance issues, or policy flags:

1. **Instant Ad Kill-Switch (Host Level)**:
   Set `NEXT_PUBLIC_ADS_ENABLED=false` in `.env` on production and rebuild/restart the frontend service:
   ```bash
   docker compose build frontend && docker compose up -d frontend
   ```
   *Result*: Immediately removes the AdSense script tag and collapses all ad containers on the site.
2. **Individual Slot Kill-Switch**:
   Emptying any individual `NEXT_PUBLIC_ADSENSE_SLOT_*` environment variable disables only that specific placement while leaving others functional.
