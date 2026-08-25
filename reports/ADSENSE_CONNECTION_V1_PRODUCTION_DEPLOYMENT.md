# AdSense Connection V1 — Production Deployment Report

**Deployment Date**: 2026-08-26  
**Environment**: Production (VPS `200.234.41.59`, Caddy, Docker Compose)  
**Deployed Release Commit**: `606662e` (`f60f51e` on `main`)  
**Previous Production Commit**: `25169ec` / `d8c003f`  
**Release Directory**: `/opt/jobsvsai/releases/606662e`  
**Deployment Operator**: Worker B / Antigravity (Authorized AdSense connection deployment)

---

## 1. Executive Summary

JobsVsAI is now cleanly connected to the official Google AdSense publisher account (`ca-pub-7855774194309157`) for domain verification, account linkage, and Google site review. 

### Operational State Matrix
- **AdSense Account Connection**: **LIVE** (Global loader script + Verification meta tag + `/ads.txt`)
- **Manual Ad Serving**: **OFF** (`NEXT_PUBLIC_ADS_ENABLED=false`, 0 active ad containers rendered)
- **Auto Ads**: **OFF** (0 auto ads scripts, flags, or automated placements)
- **Individual Slot IDs**: **UNPOPULATED / WAITING** (All 7 named slots remain blank)

---

## 2. Release Artifact Verification

- **Artifact Name**: `jobsvsai-606662e.tar.gz`
- **Source Ref**: `606662e` (Integrated `f60f51e` onto `main`)
- **File Size**: 2.0 MB (2,059,271 bytes)
- **SHA-256 (Local)**: `de7ff7681d5c1f24432f5c90fdc22f53d817ff2d84f3b1597544edc3ce40a7a5`
- **SHA-256 (VPS)**: `de7ff7681d5c1f24432f5c90fdc22f53d817ff2d84f3b1597544edc3ce40a7a5` (MATCH)
- **Exclusion Verification**: Confirmed 0 `.env`, `.git`, `node_modules`, `.next`, or untracked credentials packaged.

---

## 3. Database & Migrations

- **Database Backup**: `/var/backups/jobsvsai/jobsvsai-20260825T191627Z.dump` (874 MB, mode 600)
- **Applied Migrations**: 33
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

## 5. Production AdSense QA Verification (https://jobsvsai.com)

| Target Property | Expected Value | Production Result | Status |
|---|---|---|---|
| **Publisher ID** | `ca-pub-7855774194309157` | Configured in `lib/ads.ts` and production `.env` | **PASS** |
| **Site Verification Meta Tag** | `<meta name="google-adsense-account" content="ca-pub-7855774194309157" />` | Exactly 1 tag in `<head>` | **PASS** |
| **AdSense Loader Script** | `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7855774194309157` | Exactly 1 global script mounted in root layout (`strategy="afterInteractive"`, `crossorigin="anonymous"`) | **PASS** |
| **Duplicate Scripts** | 0 duplicate loaders across pages | 0 duplicate loaders found across all tested routes | **PASS** |
| **ads.txt Route** | `https://jobsvsai.com/ads.txt` | HTTP 200 `text/plain` returning `google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0` | **PASS** |
| **Manual Ad Units** | 0 rendered | 0 `.ad-slot`, 0 `.ad-slot-debug`, 0 `ins[data-ad-slot]` rendered | **PASS** |
| **Auto Ads** | OFF | No `enable_page_level_ads` or auto-ad configuration present | **PASS** |
| **Master Ads Flag** | `NEXT_PUBLIC_ADS_ENABLED=false` | Disabled on host, ad units collapse cleanly | **PASS** |
| **Slot IDs** | All 7 named slot IDs empty | All 7 `NEXT_PUBLIC_ADSENSE_SLOT_*` variables are empty strings | **PASS** |
| **Career Tools Dropdown** | Fully interactive | Hover/click opens dropdown, navigates to `/career-fit` and `/compare` | **PASS** |

---

## 6. Privacy & Consent Management (CMP) Readiness

- The global AdSense loader loads via Next.js `strategy="afterInteractive"` for initial domain discovery and site verification.
- `afterInteractive` is a performance optimization for script lifecycle and does not represent user consent gating.
- Manual advertising is disabled in production. When monetized ad units are enabled in the future, user consent in the EEA, UK, and applicable jurisdictions will be handled via Google Privacy & Messaging (or a Google-certified TCF v2.2 Consent Management Platform) configured in the AdSense console.

---

## 7. Safety, Scoring & Operational Invariants

- **Core Data Invariants**: 507 public occupations, 507 live production scores, active scoring model JVS 1.0.3, promotion run 30, 507 snapshots, 33 applied migrations (0 pending).
- **AI News Automation**: Inert (`NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false`, model `gemini-3.6-flash`, timeout 90s, 0 requests triggered).
- **Rollback Readiness**: Previous container images remain cached on disk; `scripts/rollback.sh` is available for immediate reversion if necessary.
