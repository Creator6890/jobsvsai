# Rankings Table Column Alignment Fix V1 — Production Deployment Report

**Date**: 2026-08-27  
**Time**: 16:48 IST  
**Environment**: Production (`https://jobsvsai.com`, VPS `200.234.41.59`)  
**Operator**: Worker B / Antigravity (Authorized)  
**Deployed Commit**: `7816e2f` (cherry-picked from `e92cb3f`)  
**Previous Production Commit**: `46ccf11`  
**Deployment Status**: DEPLOYED, VERIFIED & HEALTHY  

---

## 1. Executive Summary

The Rankings Table Column Alignment Fix V1 has been integrated onto `main` and deployed to production. This fix eliminates the column sizing mismatch between table headers and body rows on `/rankings` by introducing a unified CSS grid structure with fixed/fluid column proportions and dedicated structural classes for both the **Highest Replacement Risk** (Top 10 Exposure) and **Lowest Replacement Risk** (Top 10 Resilience) tables.

Score columns (`Replacement Risk` and `AI Exposure`) are centered directly above their respective score badges across all viewports.

---

## 2. Release & Artifact Details

- **Integrated Commit SHA**: `7816e2fcb0235aeeb3b7a5ae18fbe90df930c72c`
- **Feature Commit SHA**: `e92cb3f1beae52d6a504b2b2b1bdf6a17b07db3d`
- **Release Tarball**: `jobsvsai-7816e2f.tar.gz`
- **Tarball Size**: 2.2 MB (2,259,573 bytes)
- **Tarball SHA-256**: `fe4d3ae4183ac2aa775e812c5b677e3b6a9ce248c90067be1f51006f7244838e`
- **Database Backup**: `jobsvsai-20260827T093632Z.dump` (875 MB, verified readable)
- **Database Migrations**: 0 applied (Schema remains at 36 applied, 0 pending)

---

## 3. Files Changed

```
frontend/src/app/globals.css                 |  26 ++++---
frontend/src/components/RankingsExplorer.tsx | 104 ++++++++++++++-------------
frontend/tests/rankingsAlignment.test.mjs    |  50 +++++++++++++
3 files changed, 120 insertions(+), 60 deletions(-)
```

---

## 4. Root Cause & Solution

1. **Root Cause**:
   - The desktop grid template used `grid-template-columns: 40px 2fr 1fr .8fr 1fr auto;`.
   - In `.ranking-header`, the 6th child (action column) was an empty `<span></span>`, which evaluated `auto` to 0px.
   - In `.ranking-row`, the 6th child was `<Link className="button secondary">View →</Link>`, which evaluated `auto` to ~92.45px.
   - This caused the remaining available width across columns 2–5 to be distributed asymmetrically between the header and body rows (e.g. Header Replacement Risk width: 171.00px vs Row Replacement Risk width: 155.59px; Header AI Exposure width: 213.75px vs Row AI Exposure width: 194.48px).
   - In addition, mobile `@media (max-width: 680px)` pseudo-elements inverted the labels ("EXP." was applied to child 4 which was Replacement Risk, and "Risk" was applied to child 5 which was AI Exposure).

2. **Resolution**:
   - Defined a unified desktop grid template: `44px minmax(180px, 2fr) minmax(140px, 1fr) 140px 120px 96px`.
   - Added dedicated structural classes (`.ranking-col-rank`, `.ranking-col-title`, `.ranking-col-cat`, `.ranking-col-risk`, `.ranking-col-exp`, `.ranking-col-action`) shared identically by both header and body rows.
   - Enforced center alignment (`display: flex; justify-content: center; align-items: center;`) on `.ranking-col-risk` and `.ranking-col-exp` in both header and body.
   - Corrected mobile responsive labels: Replacement Risk -> `RISK`, AI Exposure -> `EXP.`.

---

## 5. Real Browser Production Verification

### Viewport Matrix (48/48 PASS)

| Route / Viewport | 360px | 390px | 768px | 1024px | 1280px | 1440px |
|---|---|---|---|---|---|---|
| **Rankings (`/rankings`) - Top 10 Exposure** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Rankings (`/rankings`) - Top 10 Resilience** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Homepage (`/`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Accountant (`/jobs/accountant`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Compare (`/compare/...`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Career Fit (`/career-fit`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Methodology (`/methodology`)** | PASS | PASS | PASS | PASS | PASS | PASS |

- **Header / Body Alignment**: `leftDiff: 0px`, `widthDiff: 0px` across all columns and breakpoints.
- **Score Badge Centering**: Centered precisely at column cell midpoints.
- **Horizontal Overflow**: 0 horizontal scroll across all tested viewports.

---

## 6. AdSense & AI News Invariants

- **`google-adsense-account` meta**: Exactly 1 (`ca-pub-7855774194309157`)
- **AdSense loader script**: Exactly 1 (`ca-pub-7855774194309157`)
- **ads.txt**: HTTP 200 (`google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0`)
- **Manual ad units**: 0 rendered (`NEXT_PUBLIC_ADS_ENABLED=false`)
- **Auto Ads**: OFF
- **AI News Automation**: Inert (`NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false`)

---

## 7. Test Suite & Production Health Summary

- **Frontend Tests**: 82 passed, 0 failed (`node --test tests/*.test.mjs`)
- **Frontend Lint**: PASS (0 errors, 0 warnings)
- **Frontend Build**: PASS (Next.js production Turbopack build)
- **Backend & Integration Tests**: 601 passed, 3 skipped (`./scripts/run-tests.sh`)
- **Production Healthcheck**: 41 passed, 0 failed (`./scripts/healthcheck.sh`)
- **Corpus Integrity**: 507 verified + 390 preliminary = 897 searchable occupations (unchanged)

---

## 8. Rollback Runbook

In the event of an unexpected regression:
```bash
ssh root@200.234.41.59
cd /opt/jobsvsai/releases/7816e2f
./scripts/rollback.sh
```
Previous release directory: `/opt/jobsvsai/releases/2f6c206` (retained on disk with images).
