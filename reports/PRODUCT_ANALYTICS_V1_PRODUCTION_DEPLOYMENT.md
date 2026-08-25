# JobsVsAI — Product Funnel Analytics V1 Production Deployment Report

**Deployment Date:** 2026-08-25T20:50:00+05:30 (15:20:00 UTC)  
**Operator:** Worker B / Antigravity (Temporary Production Authorization)  
**Environment:** Production VPS (`200.234.41.59`)  
**Status:** **DEPLOYED, VERIFIED & HEALTHY (100% PASS)**

---

## 1. Release & Artifact Metadata

- **Deployed Commit:** `1812b947c617b707c29377461405e3f426210f0f` (`1812b94`)
- **Release Directory:** `/opt/jobsvsai/releases/1812b94`
- **Release Tarball:** `jobsvsai-1812b94.tar.gz`
- **Artifact SHA-256:** `b466ec41ce5e361cc59edc3a77b43daa9376c286537eb11200558b26311e512d`
- **Pre-Deploy Database Backup:** `/var/backups/jobsvsai/jobsvsai-20260825T151225Z.dump` (874 MB, verified readable)
- **Database Migrations:** **0 applied, 0 pending** (Total applied remains exactly `33`)

---

## 2. Production Health & Core Integrity

### Automated Healthcheck (`./scripts/healthcheck.sh`)
- **Result:** **24 passed, 0 failed**
  - Datastores: Postgres connected, Redis PING ok
  - Containers: `postgres`, `redis`, `backend`, `worker`, `frontend`, `caddy` all running and healthy
  - Core API endpoints: `/health` (200), `/api/v1/occupations` (200)
  - Public routes: `/` (200), `/rankings` (200), `/compare` (200), `/methodology` (200), `/about` (200), `/sitemap.xml` (200), `/jobs/accountant` (200)
  - Ingress hygiene: HTTP $\to$ HTTPS redirect (308), Admin console not exposed on API host (404)

### Core Invariants Check
- **Public Occupations:** `507`
- **Live Production Scores:** `507`
- **Active Scoring Model:** `JVS 1.0.3`
- **Promotion Run 30 Snapshots:** `507`
- **Schema Migrations Applied:** `33`

---

## 3. Product Funnel Analytics V1 Verification & Semantics

| Area / Event | Verification Method & Semantics | Production Status |
| :--- | :--- | :--- |
| **GA4 Script & Preload** | `next/script` preloads `https://www.googletagmanager.com/gtag/js?id=G-Q73BL7PRKX` with `afterInteractive` execution. Single tag loader present, no duplicate scripts. | **PASS** |
| **`occupation_viewed`** | Rendered via `<OccupationViewTracker />` with ref deduplication. Transmits only `occupation_slug`, `ai_exposure_band`, `replacement_risk_band`. | **PASS** |
| **`action_plan_viewed`** | Viewport-observed via `IntersectionObserver` (`threshold: 0.15`) observing sentinel inside `<ActionPlanSection />`. Does NOT fire on mount below the fold; fires exactly once when scrolled into view. | **PASS** |
| **Action Plan CTAs** | `action_plan_transition_clicked` and `action_plan_career_fit_clicked` emit on user click with only coarse risk bands and slug (0 task text). | **PASS** |
| **`career_transitions_viewed`** | Emitted once on `/jobs/[slug]/transitions`. Destination clicks fire `transition_destination_opened` with destination slug and risk band. | **PASS** |
| **`comparison_created`** | Authoritative single emission from `<ComparisonViewTracker />` within `<CareerComparison />`. Redundant selector form submission emission removed. | **PASS** |
| **`career_fit_started`** | Fires only upon explicit user click on "Begin Career Fit Assessment", not upon page mount. | **PASS** |
| **`career_fit_completed`** | Fires once on assessment calculation, carrying only bounded `duration_seconds`. | **PASS** |
| **`career_fit_job_opened`** | Fires upon click on career match card with destination slug and fit rank. | **PASS** |
| **`occupation_search_used`** | Emits only `query_result_count` and `selected_occupation_slug`. User typed queries, raw search text, and IPs are never logged. | **PASS** |
| **`rankings_viewed` & Filters** | `rankings_viewed` fires once on mount. Tab switches emit `rankings_filter_changed` with sort enum. | **PASS** |

---

## 4. Privacy & Payload Security Audit

- **Career Fit Answers & Vectors:** `0` raw questionnaire answers, `0` dimension scores, and `0` profile vectors are ever transmitted.
- **Action Plan Content:** `0` task names, descriptions, or guidance strings are transmitted.
- **Search Query Text:** `0` raw typed search terms are persisted or logged.
- **Third-Party Trackers:** `0` session replay tools (Hotjar, Microsoft Clarity, FullStory) or fingerprinting scripts.
- **Value Validation:** Slugs regex `/^[a-z0-9]+(?:-[a-z0-9]+)*$/`, risk bands constrained to `"low" | "medium" | "high"`, bounded integers for counts/ranks/durations.

---

## 5. Subsystem Isolation & Invariants

### AdSense (Dark)
- `NEXT_PUBLIC_ADS_ENABLED=false`
- `NEXT_PUBLIC_ADS_DEBUG=false`
- Publisher ID & Slot IDs blank
- `0` `adsbygoogle` script tags, `0` active ad containers, `0` network requests to Google Ads.

### AI News (Inert)
- `NEWS_LLM_MODEL=gemini-3.6-flash`
- `NEWS_LLM_TIMEOUT_SECONDS=90`
- `NEWS_INGESTION_ENABLED=false`
- `NEWS_GENERATION_ENABLED=false`
- `NEWS_AUTO_PUBLISH=false`
- `provider=null`, no persistent Gemini key, no active cron tasks.

### CMP / Consent Mode Limitation
- The GA4 script uses Next.js `afterInteractive`, which is an async script loading strategy, not an active CMP or ePrivacy consent gate.
- GA4 is initialized using the standard `gtag` API and is structurally prepared for Google Consent Mode / certified CMP integration in future releases.

---

## 6. Live Surface Smoke Tests

| Route | URL | HTTP Status | Visual & Component Verification |
| :--- | :--- | :--- | :--- |
| **Homepage** | `https://jobsvsai.com/` | `200 OK` | GA4 loader initialized, search active, rankings preview rendered |
| **Occupation Detail** | `https://jobsvsai.com/jobs/accountant` | `200 OK` | Score cards, Action Plan section with viewport observer, transitions CTA |
| **Transitions Explorer** | `https://jobsvsai.com/jobs/accountant/transitions` | `200 OK` | Transition cards, Transferable match badges, compare links |
| **Career Fit** | `https://jobsvsai.com/career-fit` | `200 OK` | Assessment intro, 20-question flow, privacy-preserving completion |
| **Career Compare** | `https://jobsvsai.com/compare` | `200 OK` | Selector form, side-by-side comparison tables |
| **Rankings** | `https://jobsvsai.com/rankings` | `200 OK` | Full table, sort/filter tabs, pagination |
| **Methodology** | `https://jobsvsai.com/methodology` | `200 OK` | Methodology documentation, JVS formula descriptions |

---

## 7. Rollback State

If rollback is ever required:
```bash
cd /opt/jobsvsai/releases/4c18b5c
./scripts/update.sh
```
Database dump available at `/var/backups/jobsvsai/jobsvsai-20260825T151225Z.dump`.

---

**DEPLOYMENT CONCLUSION:**  
Product Funnel Analytics V1 is successfully deployed to production. All 24 health checks pass, core integrity (507/507/JVS 1.0.3) is preserved, event semantics and privacy filters are verified live, and temporary production authorization has concluded.
