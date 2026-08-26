# Preliminary Occupation Page UI Repair V1 — Production Deployment Report

**Deployment Date**: 2026-08-27  
**Environment**: Production (VPS `200.234.41.59`, Caddy, Docker Compose)  
**Deployed Commit**: `621c977` (`7ee56eb` on `main`)  
**Previous Production Commit**: `078f871` / `77d4e4a`  
**Release Directory**: `/opt/jobsvsai/releases/621c977`  
**Deployment Operator**: Worker B / Antigravity (Authorized production UI hotfix)

---

## 1. Executive Summary

This release resolves the visual defects on preliminary-estimate occupation pages (`/jobs/[slug]`), aligning their layout, containers, hero structure, score-card hierarchy, and evidence presentation directly with healthy verified occupation pages (`/jobs/accountant`).

### Key Fixes
1. **Unified Container Width & Gutters**: Wrapped all preliminary page sections in `.container`, eliminating accidental full-viewport stretching and restoring standard 1180px maximum content width.
2. **Anchored Hero Status**: Positioned the preliminary estimate status badge (`[ Preliminary estimate ]  {Confidence}`) directly below the occupation title and above the lead description, preventing awkward floating on the far right.
3. **Harmonized 3-Column Score Grid**: Replaced oversized 2-column blocks with the verified 3-column `.score-grid` structure, including non-wrapping range score typography (`.score-range`), band chips, and evidence quality metrics.
4. **Consumer-Facing Evidence Section**: Redesigned raw diagnostic dumps into a structured `.estimate-evidence-card` featuring multi-column related-occupation comparison grids (E3) and task evidence coverage stats (E1/E2).
5. **Preserved Invariants**: Zero changes to backend scoring, preliminary estimate calculations, Search V2 ranking, database migrations, or AdSense verification infrastructure.

---

## 2. Release Artifact Verification

- **Artifact Name**: `jobsvsai-621c977.tar.gz`
- **Source Ref**: `621c977` (Cherry-picked `7ee56eb` onto `main`)
- **File Size**: 2.2 MB (2,254,166 bytes)
- **SHA-256 (Local)**: `6ee931cfb84304557f3e15acd28f4b170eeea3e29ea2d58ab3711c6990449ecb`
- **SHA-256 (VPS)**: `6ee931cfb84304557f3e15acd28f4b170eeea3e29ea2d58ab3711c6990449ecb` (MATCH)
- **Exclusion Verification**: Confirmed 0 `.env`, `.git`, `node_modules`, `.next`, or untracked credentials packaged.

---

## 3. Database & Migrations

- **Database Backup**: `/var/backups/jobsvsai/jobsvsai-20260826T214330Z.dump` (875 MB, verified readable)
- **Applied Migrations**: 36
- **Pending Migrations**: 0
- **New Migrations in Release**: 0

---

## 4. Production Healthcheck

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
== Score classes ==
  PASS  verified occupations: 507
  PASS  verified scores match verified occupations (507)
  PASS  preliminary estimates: 390
  PASS  E1: 59
  PASS  E2: 293
  PASS  E3: 38
  PASS  no occupation is both verified and estimated
  ---- verified 507  +  preliminary 390  =  897 searchable ----
== Product policy (V1: verified-only surfaces) ==
  PASS  rankings / career fit / compare expose 0 estimated occupations
  PASS  staged without any analysis: 15
== Read-path indexes ==
  PASS  related-career lookup is indexed by identity
== Worker ==
  PASS  worker process alive
== Search semantics ==
  PASS  "soft eng" -> software-developer
  PASS  "pen tester" -> cybersecurity-analyst
  PASS  "data analyst" -> data-scientists
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
== AdSense ==
  PASS  ADSENSE CONNECTION: LIVE (verification meta + loader, ca-pub-7855774194309157)
  PASS  MANUAL AD SERVING: OFF (0 ad units rendered)
== Hydration budget ==
  PASS  /api/v1/occupations?limit=500 in 1.826743s (budget 6s)
  PASS  /compare -> 200 (loads every occupation)
== Ingress hygiene ==
  PASS  http -> https redirect (308)
  PASS  data console not exposed on API host (404)

== 41 passed, 0 failed ==
```

---

## 5. Production Responsive UI Verification Matrix

| Viewport | Accountant (Verified) | Software Developer (E1) | Cashiers (E2) | Data Scientists (E3) | Status |
|---|---|---|---|---|---|
| **360px** | Title visible, no header overlap, 0 horizontal overflow | Title visible, point estimate `~75/100`, 0 overflow | Title visible, range `52–68/100` non-wrapping, 0 overflow | Title visible, range `67–85/100` non-wrapping, 0 overflow | **PASS** |
| **390px** | Title visible, no header overlap, 0 horizontal overflow | Title visible, point estimate `~75/100`, 0 overflow | Title visible, range `52–68/100` non-wrapping, 0 overflow | Title visible, range `67–85/100` non-wrapping, 0 overflow | **PASS** |
| **768px** | 2-col responsive grid, clean gutters | 2-col responsive grid, clean gutters | 2-col responsive grid, clean gutters | 2-col responsive grid, clean gutters | **PASS** |
| **1024px** | 3-column score grid, full alignment | 3-column score grid, 86% task coverage metric | 3-column score grid, 51% task coverage metric | 3-column score grid, related-work comparison card | **PASS** |
| **1280px** | 1180px standard container, full layout | 1180px standard container, centered layout | 1180px standard container, centered layout | 1180px standard container, centered layout | **PASS** |
| **1440px** | 1180px standard container, full layout | 1180px standard container, no viewport stretch | 1180px standard container, no viewport stretch | 1180px standard container, no viewport stretch | **PASS** |

---

## 6. AdSense Post-Deploy Verification Gate

- **Account Verification Meta**: `<meta name="google-adsense-account" content="ca-pub-7855774194309157" />` present in production document `<head>` (Count: 1).
- **Global Loader Script**: `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7855774194309157` mounted in root layout (`afterInteractive`, `crossorigin="anonymous"`, Count: 1).
- **ads.txt Record**: `https://jobsvsai.com/ads.txt` returns HTTP 200 text/plain with `google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0`.
- **Manual Ad Serving**: Strictly OFF (`NEXT_PUBLIC_ADS_ENABLED=false`, 0 active ad containers rendered).
- **Auto Ads**: OFF (0 automated ad scripts, tags, or placements).

---

## 7. Search V2 & Product Policy Regressions

- **Search V2 Resolution**:
  - `software developer` $\to$ `software-developer` (PASS)
  - `data scientist` $\to$ `data-scientists` (PASS)
  - `soft eng` $\to$ `software-developer` (PASS)
  - `data analyst` $\to$ `data-scientists` (PASS)
  - `pen tester` $\to$ `cybersecurity-analyst` (PASS)
- **Product Surfaces**: Rankings, Career Fit, and Compare remain verified-only (0 estimated occupations leaked).
- **Sitemap Policy**: 507 verified occupation pages submitted; 390 preliminary pages remain outside sitemap.
- **AI News Automation**: Inert (`NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false`, model `gemini-3.6-flash`, timeout 90s, 0 requests).
- **Rollback Readiness**: Previous release images cached on disk; `scripts/rollback.sh` ready if required.
