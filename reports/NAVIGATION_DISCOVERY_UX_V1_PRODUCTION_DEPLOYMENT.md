# JobsVsAI — Navigation & Discovery UX V1 Production Deployment Report

**Deployment Date:** 2026-08-25T21:37:00+05:30 (16:07:00 UTC)  
**Operator:** Worker B / Antigravity (Temporary Production Authorization)  
**Environment:** Production VPS (`200.234.41.59`)  
**Status:** **DEPLOYED, VERIFIED & HEALTHY (100% PASS)**

---

## 1. Release & Artifact Metadata

- **Deployed Commit:** `b60c392e71ddd40da828d71e0db8bce21c797007` (`b60c392`)
- **Release Directory:** `/opt/jobsvsai/releases/b60c392`
- **Release Tarball:** `jobsvsai-b60c392.tar.gz`
- **Artifact SHA-256:** `402120eeda20221196a52051c11b94cce1c134286ebc8e7a89343ebd6fc632c5`
- **Pre-Deploy Database Backup:** `/var/backups/jobsvsai/jobsvsai-20260825T160200Z.dump` (874 MB, verified readable)
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

## 3. Navigation & Discovery UX V1 Verification

| Surface / Flow | Live Production Verification | Status |
| :--- | :--- | :--- |
| **Desktop Primary Nav** | Renders `[Logo (/)]` \| `Rankings (/rankings)` \| `Career Tools ▾` \| `News (/news)` \| `About (/about)`. Redundant `Home`, `Methodology`, and duplicate `Explore the rankings →` CTA button are completely removed. | **PASS** |
| **Career Tools Dropdown** | Contains exactly `Career Fit` (`/career-fit`) and `Compare Careers` (`/compare`). Keyboard accessible (`Escape`, `ArrowDown`, `ArrowUp`), focus return, and aria attributes functional. | **PASS** |
| **Mobile Drawer Navigation** | Renders `Rankings`, `Career Tools` (`Career Fit` + `Compare Careers`), `News`, `About`. `Methodology` is excluded from primary drawer items, mirroring desktop IA. | **PASS** |
| **Methodology Discoverability** | Relocated to trust destinations: Site Footer across all routes (`/methodology`), About page, and contextual "How we calculate this" links. Route returns HTTP `200`. | **PASS** |
| **Homepage Search Handoff** | Searched occupation returns requested metrics and "See the full analysis →" first; continuation card renders below: *"Thinking about other options? Find careers that align with your strengths and work preferences. [ Find My Career Fit → ] Takes about 3 minutes"* linking to `/career-fit?from=homepage_search`. | **PASS** |
| **Analytics Attribution** | `CareerFitApp` reads `from=homepage_search` and passes `entry_source: "homepage_search"` to `career_fit_started` only when the user clicks "Begin Career Fit Assessment". Zero raw query text or occupation titles transmitted. | **PASS** |
| **Rankings Simplification** | `/rankings` renders two editorial Top-10 sections: **Highest Replacement Risk** and **Lowest Replacement Risk**. 0 sensationalized words (*"AI-proof"*, *"safe jobs"*, *"doomed jobs"*). Full 507 public dataset intact in API/backend. | **PASS** |
| **Rankings Data Accuracy** | Top-10 sorting matches live Postgres score data with 100% precision. | **PASS** |
| **No Career Directory** | Verified `/occupations`, `/careers`, `/explore-careers` all return HTTP `404`. No browseable 507 directory exposed. | **PASS** |

---

## 4. Live Surface Smoke Tests

| Route | URL | HTTP Status | Visual & Component Verification |
| :--- | :--- | :--- | :--- |
| **Homepage** | `https://jobsvsai.com/` | `200 OK` | Logo links home, search active, search continuation CTA rendered |
| **Rankings** | `https://jobsvsai.com/rankings` | `200 OK` | Top 10 Highest Risk + Top 10 Lowest Risk editorial tables |
| **Career Fit** | `https://jobsvsai.com/career-fit` | `200 OK` | Assessment intro, 20-question flow, attribution support |
| **Career Compare** | `https://jobsvsai.com/compare` | `200 OK` | Side-by-side comparison selector and breakdown |
| **News** | `https://jobsvsai.com/news` | `200 OK` | Editorial news listing |
| **About** | `https://jobsvsai.com/about` | `200 OK` | Purpose, trust, and methodology links |
| **Methodology** | `https://jobsvsai.com/methodology` | `200 OK` | Full scoring methodology and framework |
| **Job Detail** | `https://jobsvsai.com/jobs/accountant` | `200 OK` | Score cards, Action Plan section with viewport observer |
| **Transitions Explorer** | `https://jobsvsai.com/jobs/accountant/transitions` | `200 OK` | Career transition recommendations & Transferable match badges |

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

---

## 6. Rollback & State Recording

- **Rollback State File:** `/opt/jobsvsai/releases/b60c392/.deploy-state`
- **Recorded Previous Images:**
  - Backend: `4ffeb2916e3c9557852d0b5cd2b999a5f1a186c29eb7fb6a06fab02780b18c48`
  - Worker: `036257380c1307332db779a32a3370c2c9020c9f782cdeb80c501d537c21ffc2`
  - Frontend: `8e4bc2ef6e2f989615e02240f3b5d226a9cf107fc12bf5c92b7f1f3c4a567db6`

---

## 7. Conclusion

Navigation & Discovery UX V1 is **live in production**, verified healthy with 24/24 passing health checks, 0 regressions, and strict privacy/subsystem invariants intact.

**FINAL STATUS:** **PRODUCTION DEPLOYMENT COMPLETED & VERIFIED**
