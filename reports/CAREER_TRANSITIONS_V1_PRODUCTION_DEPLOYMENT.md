# Career Transition Explorer V1 — Production Deployment Report

**Deployment Date:** 2026-08-25 13:31:12 UTC  
**Deployed Commit:** `cadfc0c55144b2265f81b1cbecd9227ee1be1499` (`cadfc0c`)  
**Release Directory:** `/opt/jobsvsai/releases/cadfc0c`  
**Deployment Operator:** Worker B / Antigravity (under explicit temporary architect authorization)  
**Status:** **DEPLOYED TO PRODUCTION & VERIFIED HEALTHY**

---

## 1. Release & Artifact Verification

- **Commit Integrated:**
  - `3402d0e` — *feat: implement Career Transition Explorer V1 with calibration gate*
  - `cadfc0c` — *copy: clarify career transition risk improvement*
- **Source Tree:** Exact `cadfc0c` via `git archive`
- **Artifact File:** `jobsvsai-cadfc0c.tar.gz` (2.0 MB)
- **Local & Remote SHA-256:** `622fbf4e5e8a5a555bb22612b62a3535b34ed8d402e7c4bee14e438caa60e98d` (verified matching)
- **Archive Audit:** Zero `.env`, `.git`, `node_modules`, `.next`, `__pycache__`, or private keys included.
- **Production Mode:** `.env` copied with permissions `0600` from `/opt/jobsvsai/releases/a313a6adb958/.env`.

---

## 2. Pre- & Post-Deployment Core Safety Invariants

| Invariant | Pre-Deploy Value | Post-Deploy Value | Target Baseline | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Public Occupations** | 507 | 507 | 507 | **PASS** |
| **Live Production Scores** | 507 | 507 | 507 | **PASS** |
| **Active Scoring Model** | `JVS 1.0.3` | `JVS 1.0.3` | `JVS 1.0.3` | **PASS** |
| **Run 30 Score Snapshots** | 507 | 507 | 507 | **PASS** |
| **Database Migrations** | 33 applied / 0 pending | 33 applied / 0 pending | 33 applied | **PASS** |
| **Automated Healthcheck** | 24 passed / 0 failed | 24 passed / 0 failed | 24 passed / 0 failed | **PASS** |

---

## 3. Database Backup & Update Lifecycle

- **Pre-deployment Database Backup:**
  - File: `/var/backups/jobsvsai/jobsvsai-20260825T132547Z.dump`
  - Size: 874 MB
  - Checksum: `/var/backups/jobsvsai/jobsvsai-20260825T132547Z.dump.sha256` generated and verified.
- **Migration Execution:** `NOTICE: relation "schema_migrations" already exists, skipping. Database is up to date; nothing to apply.`
- **Service Recreation:** `jobsvsai-frontend-1` and `jobsvsai-caddy-1` rebuilt and recreated smoothly.
- **Rollback Preparedness:** `/opt/jobsvsai/releases/a313a6adb958` and previous Docker images preserved on disk.

---

## 4. Live Feature Verification

### A. Transition Routes (`/jobs/[slug]/transitions`)
Tested representative cohort across sectors:
- `/jobs/fashion-designers/transitions` — **HTTP 200**
- `/jobs/computer-programmers/transitions` — **HTTP 200**
- `/jobs/accountant/transitions` — **HTTP 200**
- `/jobs/registered-nurses/transitions` — **HTTP 200**
- `/jobs/electrical-engineers/transitions` — **HTTP 200**
- `/jobs/aircraft-mechanic/transitions` — **HTTP 200**

### B. Risk Framing & Presentation Verification
- **Meaningful Drop ($\Delta \ge 5$):** Fashion Designers $\to$ Fabric & Patternmakers (8 pts lower) renders `8 points lower` with green delta chip.
- **Slight Drop ($\Delta \in [1, 4]$):** Computer Programmers $\to$ Computer Systems Analysts (1 pt lower) renders `1 point lower`.
- **Similar Risk ($\Delta = 0$):** Accountant $\to$ Treasurers and Controllers renders `similar replacement risk` with neutral tone.
- **Higher Risk ($\Delta < 0$):** Accountant $\to$ Credit Analysts renders `13 points higher` with distinct higher-risk tone; never labelled or framed as safer.

### C. Low-Risk Occupation Adaptive Narrative
- Verified `aircraft-mechanic` (Replacement Risk 37/100 $\le 40$) renders header narrative *"Related career paths for Aircraft Mechanic"* without implying the source role requires replacement.

### D. Comparison & Navigation Integration
- Transition cards render 1-click comparison links to `/compare/[source]-vs-[destination]`.
- Verified `/compare/accountant-vs-treasurers-and-controllers` returns **HTTP 200**.
- Job detail page (`/jobs/accountant`) renders entry CTA banner and header button.

### E. SEO & Robots Hygiene
- Verified live HTML: `<meta name="robots" content="noindex, follow"/>`.
- Canonical tag properly set to `https://jobsvsai.com/jobs/[slug]/transitions`.
- `sitemap.xml` verified intact with 0 transitional route leaks.

---

## 5. Secondary Systems Invariant Audit

### A. AdSense Dark State (Post-Frontend Build)
- `NEXT_PUBLIC_ADS_ENABLED=false`
- `NEXT_PUBLIC_ADS_DEBUG=false`
- All client and slot IDs are empty strings.
- Verified 0 `adsbygoogle` script tags, 0 ad containers, and 0 network requests to Google ad endpoints.

### B. AI News Inert State
- `NEWS_LLM_MODEL=gemini-3.6-flash`
- `NEWS_LLM_TIMEOUT_SECONDS=90`
- `NEWS_INGESTION_ENABLED=False`
- `NEWS_GENERATION_ENABLED=False`
- `NEWS_AUTO_PUBLISH=False`
- Provider remains `null`, zero cron tasks active, zero news records mutated.

### C. Career Fit Regression
- `/career-fit` returns **HTTP 200**; 20-question exploratory assessment and score computation fully functional.

---

## 6. Site-Wide Smoke Test Matrix

| URL Path | Expected | Actual Status |
| :--- | :---: | :---: |
| `https://jobsvsai.com/` | 200 | **200 OK** |
| `https://jobsvsai.com/career-fit` | 200 | **200 OK** |
| `https://jobsvsai.com/rankings` | 200 | **200 OK** |
| `https://jobsvsai.com/compare` | 200 | **200 OK** |
| `https://jobsvsai.com/news` | 200 | **200 OK** |
| `https://jobsvsai.com/jobs/accountant` | 200 | **200 OK** |
| `https://jobsvsai.com/jobs/accountant/transitions` | 200 | **200 OK** |
| `https://jobsvsai.com/compare/accountant-vs-treasurers-and-controllers` | 200 | **200 OK** |

---

## 7. Operational Conclusion & Handoff

Career Transition Explorer V1 has been safely deployed and verified on production (`200.234.41.59`).
All core metrics, safety baselines, responsive viewports, and non-active subsystems remain in their exact specified state.

Temporary deployment authorization for Worker B ends with this report. Future production operations return to Worker A / Claude upon availability.
