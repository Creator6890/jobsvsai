# Methodology Page Spacing Repair V1 — Production Deployment Report

**Deployment Date**: 2026-08-27  
**Environment**: Production (VPS `200.234.41.59`, Caddy, Docker Compose)  
**Integrated Commit**: `9e5a66c` (`c199221` cherry-picked onto `main`)  
**Deployed Commit**: `9e5a66c`  
**Previous Production Commit**: `bc411c2`  
**Release Directory**: `/opt/jobsvsai/releases/9e5a66c`  
**Deployment Operator**: Worker B / Antigravity (Authorized production UI hotfix)

---

## 1. Executive Summary

This release resolves the vertical spacing inconsistencies across `/methodology`, specifically addressing the visual collision of closing cards at the bottom of the page, oversized parent section padding between white sections, missing score block cohesion, and in-page anchor navigation to `#preliminary-estimates`.

### Key Fixes
1. **Closing Cards Separation**: Placed "What these scores are not." (`.notice`) and "Source attribution" (`.methodology-attribution-card`) into a flex column stack (`.methodology-closing-stack`) with an intentional 20px gap (`var(--gap)`), eliminating the 0px visual collision.
2. **Normalized Vertical Rhythm**: Scoped methodology section vertical padding (`.methodology-section`) to `clamp(38px, 4.5vw, 60px) 0`, removing the ~180px gap between consecutive white sections.
3. **Score Block Grouping**: Grouped the 0–100 definition cards (AI Exposure & Replacement Risk) and the explanatory notice within a single container, establishing an intentional 20px gap between metrics and explanation.
4. **Natural Footer Transition**: Scoped the closing section padding (`.methodology-closing-section`) to `clamp(36px, 4vw, 52px) 0 clamp(40px, 4.5vw, 56px)`, smoothly transitioning into the site footer with ~50px total separation.
5. **Anchor Scroll Offset**: Set `scroll-margin-top: 96px` on `#preliminary-estimates`, ensuring in-page jumps position the section kicker and heading comfortably 24px below the 72px sticky header.
6. **Zero Content/Backend Changes**: 100% frontend layout repair with zero copy modifications, scoring adjustments, estimate alterations, or database migrations.

---

## 2. Release Artifact Verification

- **Artifact Name**: `jobsvsai-9e5a66c.tar.gz`
- **Source Ref**: `9e5a66c`
- **File Size**: 2.2 MB (2,254,460 bytes)
- **SHA-256 (Local)**: `58e9dbd0073e79f8489ebf1a534f2b028d96bf087d7d049a4ca7675156470d7f`
- **SHA-256 (VPS)**: `58e9dbd0073e79f8489ebf1a534f2b028d96bf087d7d049a4ca7675156470d7f` (MATCH)
- **Exclusion Verification**: Confirmed 0 `.env`, `.git`, `node_modules`, `.next`, or untracked credentials packaged.

---

## 3. Database & Migrations

- **Database Backup**: `/var/backups/jobsvsai/jobsvsai-20260827T054802Z.dump` (875 MB, verified readable)
- **Applied Migrations**: 36
- **Pending Migrations**: 0
- **New Migrations in Release**: 0

---

## 4. Production Healthcheck

```
== Containers ==
  PASS  redis running
  PASS  postgres running
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
  PASS  /api/v1/occupations?limit=500 in 2.384367s (budget 6s)
  PASS  /compare -> 200 (loads every occupation)
== Ingress hygiene ==
  PASS  http -> https redirect (308)
  PASS  data console not exposed on API host (404)

== 41 passed, 0 failed ==
```

---

## 5. Production Responsive UI Verification Matrix

| Viewport | Score Block (0-100 & Notice) | Preliminary Estimates Anchor | Closing Cards Stack | Footer Transition | Status |
|---|---|---|---|---|---|
| **360px** | Single-col stack, 20px gap to notice, 0 overflow | Kicker & H2 comfortably below sticky header | 20px gap between notice & attribution, 0 collision | 40px clean transition to site footer | **PASS** |
| **390px** | Single-col stack, 20px gap to notice, 0 overflow | Kicker & H2 comfortably below sticky header | 20px gap between notice & attribution, 0 collision | 40px clean transition to site footer | **PASS** |
| **768px** | 2-column definition grid, 20px gap to notice | Target top aligns 24px below sticky nav | 20px gap between notice & attribution, 0 collision | 40px clean transition to site footer | **PASS** |
| **1024px** | 2-column definition grid, 20px gap to notice | Clean scroll margin, no overlap | 20px gap between notice & attribution, 0 collision | 46px clean transition to site footer | **PASS** |
| **1280px** | 1180px standard container, balanced padding | Clean scroll margin, no overlap | 20px gap between notice & attribution, 0 collision | 56px clean transition to site footer | **PASS** |
| **1440px** | 1180px standard container, balanced padding | Clean scroll margin, no overlap | 20px gap between notice & attribution, 0 collision | 56px clean transition to site footer | **PASS** |

---

## 6. AdSense Post-Deploy Verification Gate

- **Account Verification Meta**: `<meta name="google-adsense-account" content="ca-pub-7855774194309157" />` present in production document `<head>` (Count: 1).
- **Global Loader Script**: `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7855774194309157` mounted in root layout (`afterInteractive`, `crossorigin="anonymous"`, Count: 1).
- **ads.txt Record**: `https://jobsvsai.com/ads.txt` returns HTTP 200 text/plain with `google.com, pub-7855774194309157, DIRECT, f08c47fec0942fa0`.
- **Manual Ad Serving**: Strictly OFF (`NEXT_PUBLIC_ADS_ENABLED=false`, 0 active ad containers rendered).
- **Auto Ads**: OFF (0 automated ad scripts, tags, or placements).

---

## 7. Product Regressions & AI News

- **Product Routes**:
  - `/`: 200 PASS
  - `/jobs/accountant` (Verified): 200 PASS
  - `/jobs/data-scientists` (Preliminary E3): 200 PASS
  - `/rankings`: 200 PASS
  - `/career-fit`: 200 PASS
  - `/compare`: 200 PASS
- **AI News Automation**: Inert (`NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false`, model `gemini-3.6-flash`, timeout 90s, 0 requests).
- **Rollback Readiness**: Previous release images (`621c977`) cached on disk; `scripts/rollback.sh` available if required.
