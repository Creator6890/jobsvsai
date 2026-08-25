# Career Fit V1 — Production Deployment Report

**Date:** 2026-08-25 · **Host:** `srv1920920` (Ubuntu 24.04.4 LTS) · **Outcome:** HEALTHY / LIVE

Career Fit V1 has been successfully deployed to production on https://jobsvsai.com/career-fit.

---

## 1. Deployed Commit

| Field | Value |
| :--- | :--- |
| **Commit** | `a313a6adb958cbb25360c57dfcbe2d0bf2e4c2bc` (`a313a6a`) |
| **Branch** | `main` (in sync with `origin/main`) |
| **Integrated Commits** | `9c59b0b` (feat: implement Career Fit V1), `7b618bc` (feat: calibration gate), `a313a6a` (copy: clarify exploratory assessment) |
| **Pre-deploy Tests** | 26 frontend unit/invariant tests passing, 495 backend guarded tests passing |

---

## 2. Release Directory

```
/opt/jobsvsai/releases/a313a6adb958
```

All prior releases (`d669f082a56e`, `26e91c0a8650`, `a6cc69481da9`, `59a6578b8305`) remain intact on disk. Deployment executed via versioned artifact extraction; no git commands were run on the VPS.

---

## 3. Release Artifact

| Field | Value |
| :--- | :--- |
| **Filename** | `jobsvsai-a313a6adb958.tar.gz` |
| **Built with** | `git archive --format=tar.gz --prefix=a313a6adb958/ HEAD` |
| **Size** | 2,058,760 bytes (2.0 MB) |
| **SHA-256** | `e65615113c729991c9fae7a01815324e4b5a3509f56569cfe55216d8a43e3ce3` |
| **Integrity** | Hash verified identical on VPS before extraction |
| **Security** | Verified absent: `.env`, `.git/`, `node_modules`, `.next`, `__pycache__`, API/SSH keys |

---

## 4. Database Backup

| Field | Value |
| :--- | :--- |
| **Path** | `/var/backups/jobsvsai/jobsvsai-20260825T121145Z.dump` |
| **Size** | 874 MB |
| **Integrity** | Verified readable with `pg_restore --list` |
| **Retained Dumps** | 6 dumps retained on VPS |

---

## 5. Database Migrations

```
==> Applying database migrations
==> Ensuring schema_migrations exists
NOTICE:  relation "schema_migrations" already exists, skipping
==> Database is up to date; nothing to apply.
```

- **Applied Migrations:** 33
- **Pending Migrations:** 0
- **New Migrations in Release:** 0 (Career Fit is 100% frontend and requires no schema changes)

---

## 6. Healthcheck Results

```
== Containers ==
  PASS  postgres running
  PASS  redis running
  PASS  backend running
  PASS  frontend running
  PASS  caddy running
  PASS  worker running
== Datastores ==
  PASS  postgres accepting connections
  PASS  redis responding to PING
== Data integrity ==
  PASS  public occupations: 507
  PASS  live production scores: 507
  PASS  active scoring model is JVS 1.0.3
== Worker ==
  PASS  worker process alive
== API (internal) ==
  PASS  backend /health
== Public routes (https://jobsvsai.com) ==
  PASS  / -> 200
  PASS  /rankings -> 200
  PASS  /compare -> 200
  PASS  /methodology -> 200
  PASS  /about -> 200
  PASS  /sitemap.xml -> 200
  PASS  /jobs/accountant -> 200
== API (https://api.jobsvsai.com) ==
  PASS  /health -> 200
  PASS  /api/v1/occupations -> 200
== Ingress hygiene ==
  PASS  http -> https redirect (308)
  PASS  data console not exposed on API host (404)

== 24 passed, 0 failed ==
```

---

## 7. Core Product Invariants

| Invariant | Pre-Deploy | Post-Deploy | Status |
| :--- | :---: | :---: | :---: |
| **Public Occupations** | 507 | **507** | PASS |
| **Live Production Scores** | 507 | **507** | PASS |
| **Active Scoring Model** | JVS 1.0.3 | **JVS 1.0.3** | PASS |
| **Promotion Run 30 Snapshots** | 507 | **507** | PASS |
| **Schema Migrations** | 33 | **33** | PASS |

---

## 8. Career Fit Public Route Verification

- **URL:** `https://jobsvsai.com/career-fit`
- **HTTP Status:** `200 OK`
- **Title:** `Career Fit Assessment — Discover Careers Matched to Your Work Strengths — JobsVsAI`
- **Canonical:** `https://jobsvsai.com/career-fit`
- **OpenGraph:** Title and description configured cleanly for social preview.
- **Server Rendering:** Server pre-renders page shell with complete 507-occupation payload for zero-latency client evaluation.

---

## 9. Functional Assessment QA

- **Intro View:** Clear exploratory disclosure rendered (*"Career Fit is an exploratory match based on your self-reported responses and occupation characteristics. It is not a validated aptitude or psychological assessment."*).
- **Questionnaire:** 20 original Likert questions render cleanly across 8 dimensions.
- **Navigation Controls:** Progress bar tracks 1–20 steps; Previous/Next buttons and keyboard shortcuts operate smoothly.
- **Results View:**
  - 8-dimension work-strength profile rendered with horizontal percentage bars and strength band badges.
  - Generates 12 top occupation recommendations with exact Career Fit %, AI Exposure, and Replacement Risk.
  - "Why this fits" narrative reflects highest overlapping competencies.
  - Sort tabs (*Best Career Fit*, *Lowest Replacement Risk*, *Lowest AI Exposure*) sort dynamically without re-running network calls.

---

## 10. Job Link Integration

- Verified recommendation card links directly to live canonical occupation pages:
  - `/jobs/accountant` -> `200 OK`
  - `/jobs/nurse-practitioner` -> `200 OK`
  - `/jobs/aircraft-mechanic` -> `200 OK`
  - `/jobs/brand-strategist` -> `200 OK`
  - `/jobs/chief-executives` -> `200 OK`
  - `/jobs/general-and-operations-managers` -> `200 OK`
- Underlying AI Exposure and Replacement Risk scores remain identical to published database records.

---

## 11. Navigation Integration

- **Site Header:** "Career Fit" link present in primary navigation on desktop and mobile.
- **Site Footer:** "Career Fit" link present in footer navigation.
- **Homepage:** High-visibility CTA card *"Find careers that match how you work"* positioned after ranking previews and before footer.

---

## 12. Responsive QA

Verified across standard responsive viewports (360px, 390px, 768px, 1024px, 1440px):
- Likert 5-point options wrap cleanly on small screens (360px–390px).
- Dimension strength bars render with fluid width and no horizontal clipping.
- Recommendation grid stacks vertically on mobile (<768px) and expands to multi-column on desktop (>=1024px).
- No horizontal scroll or viewport overflow.

---

## 13. Privacy & Network Invariants

- **No User Accounts:** No registration or email required.
- **Zero Answer Persistence:** Answers are stored only in React component state during the session and discarded on reset or page unload.
- **No Analytics on Raw Responses:** Telemetry only fires generic `career_fit_completed` with primary dimension category.
- **Zero LLM / External API Calls:** 100% deterministic mathematical evaluation in-browser.
- **Zero Database Writes:** Server handles static route requests only.

---

## 14. AdSense State (Dark Verification)

- **Build Configuration:** `NEXT_PUBLIC_ADS_ENABLED=false`, `NEXT_PUBLIC_ADS_DEBUG=false`, and blank AdSense client and slot IDs.
- **Runtime Verification:**
  - Zero Google AdSense scripts (`adsbygoogle.js`) loaded.
  - Zero `.ad-slot` active DOM containers rendered.
  - Zero ad gap spacing or layout shifts.
  - `/career-fit` is completely ad-free.

---

## 15. AI News State (Inert Verification)

- **Backend Configuration:**
  - `NEWS_LLM_MODEL=gemini-3.6-flash`
  - `NEWS_LLM_TIMEOUT_SECONDS=90`
  - `NEWS_INGESTION_ENABLED=false`
  - `NEWS_GENERATION_ENABLED=false`
  - `NEWS_AUTO_PUBLISH=false`
- **Integrity:** Zero Gemini API calls made, candidate records untouched, no cron jobs installed.

---

## 16. Sitemap & SEO

- `/sitemap.xml` returns `200 OK` with 507 occupation URLs and homepage.
- Note: Static routes in `sitemap.ts` are explicitly enumerated; `/career-fit` will be included in the next scheduled SEO route sync without altering production deployment files.

---

## 17. Rollback State & Previous Images

Previous release `/opt/jobsvsai/releases/d669f082a56e` and `.deploy-state` image records are preserved on the VPS. If rollback is ever requested:
```bash
cd /opt/jobsvsai/releases/a313a6adb958 && ./scripts/rollback.sh
```

---

## Final Status

**DEPLOYMENT COMPLETE & PRODUCTION HEALTHY**
