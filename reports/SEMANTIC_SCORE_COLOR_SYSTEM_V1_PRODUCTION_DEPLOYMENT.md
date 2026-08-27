# Semantic Score Color System V1 — Production Deployment Report

**Date**: 2026-08-27  
**Time**: 14:50 IST  
**Environment**: Production (`https://jobsvsai.com`, VPS `200.234.41.59`)  
**Operator**: Worker B / Antigravity (Authorized)  
**Deployed Commit**: `2f6c206` (cherry-picked from `9e3536d`)  
**Previous Production Commit**: `6a53f6c`  
**Deployment Status**: DEPLOYED, VERIFIED & HEALTHY  

---

## 1. Executive Summary

The Semantic Score Color System V1 has been integrated onto `main` and successfully deployed to production. This system introduces a direction-aware, accessible visual language across all numeric intelligence score surfaces on JobsVsAI to prevent usability misconceptions regarding metric directions (e.g. ensuring high exposure or replacement risk is clearly understood as adverse, while high human dependency or resilience is recognized as protective).

All product calculations, scoring thresholds, database records, preliminary estimate algorithms, and search rankings remain strictly untouched and identical.

---

## 2. Release & Artifact Details

- **Integrated Commit SHA**: `2f6c206263595561a337190ce2bb65a397985474`
- **Feature Commit SHA**: `9e3536d76bb359670d8fffae1c3132e4d0d0bb56`
- **Release Tarball**: `jobsvsai-2f6c206.tar.gz`
- **Tarball Size**: 2.2 MB (2,258,409 bytes)
- **Tarball SHA-256**: `cc23560f404cfe2fe30dfaa6fad450940957bf0bce92c6261d5b8f9217c78b35`
- **Database Backup**: `jobsvsai-20260827T091050Z.dump` (875 MB, verified readable)
- **Database Migrations**: 0 applied (Schema remains at 36 applied, 0 pending)

---

## 3. Files Changed

```
frontend/src/app/globals.css                       |  32 ++-
frontend/src/app/page.tsx                          |  40 ++-
frontend/src/components/CareerComparison.tsx       |  96 ++++++-
frontend/src/components/EstimatedOccupationDetail.tsx |  30 +-
frontend/src/components/OccupationDetail.tsx       |  12 +-
frontend/src/components/OccupationSearch.tsx       |  17 +-
frontend/src/components/RankingsExplorer.tsx       | 117 +++++---
frontend/src/components/ScoreCard.tsx              |  79 +++++-
frontend/src/components/careerFit/CareerMatchCard.tsx |  23 +-
frontend/src/components/transitions/TransitionCard.tsx |   7 +-
frontend/src/lib/scoreSemantics.ts                 | 313 +++++++++++++++++++++
frontend/tests/preliminaryOccupation.test.mjs      |   6 +-
frontend/tests/scoreSemantics.test.mjs             | 202 +++++++++++++
13 files changed, 852 insertions(+), 122 deletions(-)
```

---

## 4. Semantic Policy & Metric Classification

### Shared Utility
- File: `frontend/src/lib/scoreSemantics.ts` (`getScoreSemantics`)

### Adverse Metrics (Higher = Worse)
- **Metrics**: AI Exposure, Replacement Risk, Adoption Pressure, Task Exposure, Automation Feasibility
- **Thresholds**:
  - `0–33`: **Low** (Safe / Green: `#16834a`, soft: `#e9f8ef`)
  - `34–66`: **Moderate** (Moderate / Dark Amber: `#a35a00`, soft: `#fef7ed`)
  - `67–100`: **High** (Risk / Red: `#d9354c`, soft: `#fff0f2`)

### Protective Metrics (Higher = Better)
- **Metrics**: Human Dependency, Physical Dependency, Labour-Market Resilience
- **Thresholds**:
  - `0–33`: **Weak** (Risk / Red: `#d9354c`, soft: `#fff0f2`)
  - `34–66`: **Moderate** (Moderate / Dark Amber: `#a35a00`, soft: `#fef7ed`)
  - `67–100`: **Strong** (Safe / Green: `#16834a`, soft: `#e9f8ef`)

### Confidence & Evidence Metrics (Neutral / Informational)
- **Metrics**: Confidence, Task Coverage, Evidence Coverage
- **Treatment**: Branded neutral / violet (`#6d28d9`), never adverse/safe career-risk colors.
- **Labels**: "Higher confidence" (67+), "Moderate confidence" (34–66), "Lower confidence" (0–33), "{val}% coverage".

### Career Fit & Transition Fit
- **Policy**: Higher fit is better; strictly retains positive violet accent treatment (`.career-fit-score-badge`). Never applies adverse red coloring to high fit scores (e.g. 90%).
- **AI Risk Snapshot**: Sub-badges on cards accurately display adverse risk semantics for AI Exposure and Replacement Risk while preserving positive fit hierarchy.

### Unknown Metrics Fallback
- Defaults safely to neutral styling without inferring direction.

---

## 5. Accessibility & Comprehension Hard Gates

- **Do Not Use Color Alone**: Every prominent score card, badge, and metric row pairs its color tone with explicit qualifying text (e.g., "High exposure", "Moderate replacement risk", "Strong human dependency", "Weak physical dependency").
- **Contrast**: Amber text uses high-contrast `#a35a00` (> 4.5:1 against white and `#fef7ed` backgrounds).
- **Numeric Dominance**: The numeric score (e.g. `67/100` or range `52–68`) remains the primary visual focal point with semantic qualifier chips positioned as supporting metadata.
- **Methodology Page 0–100 Scale**: Generic methodology examples remain neutral illustrative scales.

---

## 6. Real Browser Production Verification

### Viewport Matrix (48/48 PASS)

| Route | 360px | 390px | 768px | 1024px | 1280px | 1440px |
|---|---|---|---|---|---|---|
| **Homepage (`/`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Verified: Accountant (`/jobs/accountant`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **E1: Software Developer (`/jobs/software-developer`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **E2: Cashiers (`/jobs/cashiers`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **E3: Data Scientists (`/jobs/data-scientists`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Rankings (`/rankings`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Compare (`/compare/accountant-vs-advertising-sales-agents`)** | PASS | PASS | PASS | PASS | PASS | PASS |
| **Career Fit (`/career-fit`)** | PASS | PASS | PASS | PASS | PASS | PASS |

### Compare Page Usability Gate (Accountant vs Advertising Sales Agents)
- **AI Exposure**: Accountant 67 (`risk`, "High exposure") vs Advertising Sales 69 (`risk`, "High exposure") → Advantage: Accountant (lower exposure is better).
- **Replacement Risk**: Accountant 61 (`moderate`, "Moderate replacement risk") vs Advertising Sales 58 (`moderate`, "Moderate replacement risk") → Advantage: Advertising Sales Agents (lower risk is better).
- **Human Dependency**: Accountant 72 (`safe`, "Strong human dependency") vs Advertising Sales 62 (`moderate`, "Moderate human dependency") → Advantage: Accountant (higher dependency is better).
- **Physical Dependency**: Accountant 18 (`risk`, "Weak physical dependency") vs Advertising Sales 36 (`moderate`, "Moderate physical dependency") → Advantage: Advertising Sales Agents.
- **Resilience**: Accountant 53 (`moderate`, "Moderate resilience") vs Advertising Sales 61 (`moderate`, "Moderate resilience") → Advantage: Advertising Sales Agents.
- **Confidence / Coverage**: Both neutral violet, Higher confidence.

---

## 7. AdSense & AI News Invariants

- **`google-adsense-account` meta**: Exactly 1 (`ca-pub-7855774194309157`)
- **AdSense loader script**: Exactly 1 (`ca-pub-7855774194309157`)
- **ads.txt**: HTTP 200 (`google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0`)
- **Manual ad units**: 0 rendered (`NEXT_PUBLIC_ADS_ENABLED=false`)
- **Auto Ads**: OFF
- **AI News Automation**: Inert (`NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false`)

---

## 8. Test Suite & Production Health Summary

- **Frontend Tests**: 80 passed, 0 failed (`node --test tests/*.test.mjs`)
- **Frontend Lint**: PASS (0 errors, 0 warnings)
- **Frontend Build**: PASS (Next.js production Turbopack build)
- **Backend & Integration Tests**: 601 passed, 3 skipped (`./scripts/run-tests.sh`)
- **Production Healthcheck**: 41 passed, 0 failed (`./scripts/healthcheck.sh`)
- **Corpus Integrity**: 507 verified + 390 preliminary = 897 searchable occupations (unchanged)

---

## 9. Rollback Runbook

In the event of an unexpected regression:
```bash
ssh root@200.234.41.59
cd /opt/jobsvsai/releases/2f6c206
./scripts/rollback.sh
```
Previous release directory: `/opt/jobsvsai/releases/9e5a66c` (retained with active containers and images on disk).
