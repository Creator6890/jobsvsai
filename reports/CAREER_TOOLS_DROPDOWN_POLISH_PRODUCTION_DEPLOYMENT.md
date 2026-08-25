# Career Tools Dropdown UI Polish & Interaction Hotfix — Production Deployment Report

**Deployment Date**: 2026-08-25  
**Environment**: Production (VPS `200.234.41.59`, Caddy, Docker Compose)  
**Deployed Release**: `25169ec31165b40cfb6ba6da074bb7c4e5187740` (`25169ec`)  
**Previous Production Commit**: `b60c392` (with documentation record `6784a0c`)  
**Release Directory**: `/opt/jobsvsai/releases/25169ec`  
**Deployment Operator**: Worker B / Antigravity (Authorized production hotfix deployment)

---

## 1. Integrated Commits

| Commit | Subject | Scope |
|---|---|---|
| `19abad9` (`dcee4eb`) | `refine: polish Career Tools dropdown UI` | Visual redesign: ~320px width, ~14px radius, vertical hierarchy (title over description), rotating SVG chevron, compact padding |
| `25169ec` (`441b1a0`) | `fix: restore Career Tools dropdown interaction` | Interaction & accessibility fix: persistent DOM mounting with CSS opacity/visibility transitions, removed synchronous click unmounting, added universal pointerdown outside click, onBlur focusout closing, and full ArrowDown/ArrowUp/Escape keyboard navigation |

---

## 2. Release Artifact Verification

- **Artifact Name**: `jobsvsai-25169ec.tar.gz`
- **Source Ref**: `25169ec31165b40cfb6ba6da074bb7c4e5187740`
- **File Size**: 2.0 MB (2,058,806 bytes)
- **SHA-256 (Local)**: `a6bd79986bd4a611b8ca691c163bb039ec99f9232bd37b7e55540bad32d6dad7`
- **SHA-256 (VPS)**: `a6bd79986bd4a611b8ca691c163bb039ec99f9232bd37b7e55540bad32d6dad7` (MATCH)
- **Excluded Files Invariant**: Confirmed 0 `.env`, `.git`, `node_modules`, `.next`, credentials, or untracked artifacts in the tarball.

---

## 3. Database & Migrations

- **Database Backup**: `/var/backups/jobsvsai/jobsvsai-20260825T165400Z.dump` (874 MB, verified readable)
- **Applied Migrations Before Deploy**: 33
- **Applied Migrations After Deploy**: 33
- **Pending Migrations**: 0
- **New Migrations in Hotfix**: 0

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

## 5. Live Production Browser QA Matrix (https://jobsvsai.com)

| Test Category | Target Check | Result |
|---|---|---|
| **Mouse Open** | Click "Career Tools" expands menu, rotates chevron, sets `aria-expanded="true"` | **PASS** |
| **Mouse Close** | Second click collapses menu and sets `aria-expanded="false"` | **PASS** |
| **Career Fit Navigation** | Click "Career Fit" navigates cleanly to `/career-fit` | **PASS** |
| **Compare Careers Navigation** | Click "Compare Careers" navigates cleanly to `/compare` | **PASS** |
| **Outside Click** | Click outside dropdown container closes menu via pointerdown | **PASS** |
| **Escape Key** | Escape key closes menu and restores active focus to Career Tools button | **PASS** |
| **Keyboard Arrow Navigation** | Tab focuses button, ArrowDown opens & focuses Career Fit, ArrowDown focuses Compare Careers, ArrowUp returns | **PASS** |
| **Visual Dimensions** | Width ~320px, radius ~14px, single-line titles, descriptions below titles, compact spacing | **PASS** |
| **Desktop 1024px** | Dropdown opens and anchors cleanly under header | **PASS** |
| **Desktop 1280px** | Dropdown opens and anchors cleanly under header | **PASS** |
| **Desktop 1440px** | Dropdown opens and anchors cleanly under header | **PASS** |
| **Mobile 360px** | Mobile drawer contains Career Fit and Compare links | **PASS** |
| **Mobile 390px** | Mobile drawer contains Career Fit and Compare links | **PASS** |
| **Mobile 768px** | Mobile drawer contains Career Fit and Compare links | **PASS** |
| **Header Invariants** | `[Logo]` \| `Rankings` \| `Career Tools ▾` \| `News` \| `About` (No Home link, No Methodology in header, No duplicate CTA) | **PASS** |
| **AdSense Dark** | 0 active AdSense scripts, 0 active ad slots | **PASS** |

---

## 6. Safety & Operational Configuration

- **AdSense**: `NEXT_PUBLIC_ADS_ENABLED=false`, `NEXT_PUBLIC_ADS_DEBUG=false` (Dark)
- **AI News**: `NEWS_INGESTION_ENABLED=false`, `NEWS_GENERATION_ENABLED=false`, `NEWS_AUTO_PUBLISH=false` (Inert)
- **Model Invariant**: `NEWS_LLM_MODEL=gemini-3.6-flash`, timeout 90s, 0 Gemini requests triggered
- **Scoring Invariant**: JVS 1.0.3, promotion run 30, 507 public occupations, 507 live production scores
- **Rollback Readiness**: Previous container images remain cached on disk; `scripts/rollback.sh` is available for immediate rollback if needed.
