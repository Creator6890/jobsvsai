# AI News Phase 4 — Step 1: feature flag separation

Date: 2026-08-24
Scope: **Step 1 only.** No scheduler, no UI features, no related occupations, no auto-publish.

## 1. Why

`NEWS_ENABLED` gated ingestion and generation together, so the state Phase 4A requires —
**feeds polling in production while no language-model call is ever made** — was inexpressible.
Under one flag, enabling ingestion also armed the admin *Generate* button against a live,
billed API key.

Ingestion and generation now have independent gates.

## 2. Configuration

```
NEWS_INGESTION_ENABLED=false     # fetch, normalise, dedupe, store candidates
NEWS_GENERATION_ENABLED=false    # language-model calls, article creation
NEWS_AUTO_PUBLISH=false          # unchanged, still enforced
```

Both new flags default to **disabled**. A fresh environment inherits nothing.

### Precedence, and why it is shaped this way

Resolved by `Settings.ingestion_enabled` / `Settings.generation_enabled`:

1. An **explicitly set** new flag wins.
2. Otherwise **`NEWS_ENABLED`** applies to both, preserving old behaviour exactly.
3. Otherwise disabled.

The fields are `bool | None`, not `bool`. That is what makes "explicitly set" distinguishable
from "left at default" — a plain `bool = False` could not tell the two apart, and the legacy
fallback would be unreachable.

**Nothing in the application reads `news_enabled` directly any more.** Every consumer goes
through the two properties, so the deprecation can be completed later by deleting one field
and two fallback lines.

### Backwards compatibility

`NEWS_ENABLED=true` continues to enable both pipelines, exactly as before. Failing closed
would have been the silent behaviour change the brief forbids: anyone already running with
that flag would have had their system quietly stop.

`Settings.uses_legacy_news_flag` reports when behaviour is still coming from the deprecated
variable, and the admin pipeline panel shows a warning when it is — so an operator sees it
rather than discovering it when the fallback is eventually removed.

Verified in containers:

| Environment | ingestion | generation | legacy in use |
|---|---|---|---|
| nothing set | false | false | no |
| `NEWS_ENABLED=true` | **true** | **true** | yes |
| `NEWS_ENABLED=true`, `NEWS_GENERATION_ENABLED=false` | true | **false** | yes |
| `NEWS_INGESTION_ENABLED=true`, `NEWS_GENERATION_ENABLED=false` | true | false | no |

## 3. Two defects found while implementing

Both would have caused real production problems.

### 3.1 Compose would have silently disabled a legacy environment

The first version passed the new flags as `${NEWS_INGESTION_ENABLED:-false}`. Compose
substitutes that as an **explicit** `false`, which outranks `NEWS_ENABLED` — so an
environment running on the legacy flag would have been switched off by a deploy, with no
configuration change and no warning. Exactly the silent behaviour change the brief prohibits.

Fixed: the new flags are passed as `${NEWS_INGESTION_ENABLED:-}`. Unset stays unset, and the
code default (disabled) applies.

### 3.2 An empty environment variable crashed startup

`${NEWS_ENABLED:-}` yields `NEWS_ENABLED=""`, not an absent key, and pydantic cannot parse an
empty string as `bool | None`. The API refused to start whenever the deprecated variable was
merely passed through unset — the normal case after this change. A `field_validator` now
treats a blank string as "not set".

## 4. Where the generation gate lives

The check is inside **`generate_for_candidate`**, before the ingest item is even loaded — not
only in the batch runner. Every generation path (batch run, admin single-item action, worker
job) funnels through that function, so one check there is what makes "generation disabled
means no provider call" *true* rather than merely intended.

## 5. Files changed

| File | Change |
|---|---|
| `backend/app/core/config.py` | split flags, resolution properties, blank-string validator |
| `backend/app/news/ingestion.py` | gated on `ingestion_enabled` |
| `backend/app/news/generation_service.py` | gated on `generation_enabled`, at the chokepoint |
| `backend/app/api/admin_news.py` | reports both flags + legacy state; single-generate gated |
| `worker/news_jobs.py` | enqueue helpers gated independently |
| `docker-compose.yml` | new vars on backend and worker; legacy passed through unset |
| `.env.example` | documents both flags and the deprecation |
| `frontend/src/lib/api.ts` | `GenerationStatus` carries both flags |
| `frontend/src/app/admin/news/incoming/page.tsx` | shows both states; buttons gated by the right one; legacy warning |
| `backend/tests/test_news_feature_flags.py` | **new** — 11 tests |
| `backend/tests/test_news_ingestion_run.py` | helpers use the split flags |
| `backend/tests/test_news_generation_service.py` | helpers use the split flags |

## 6. Migration required

**No database migration.** This is configuration only; no schema, no data, no backfill. The
change is reversible by reverting the commit — there is no migrated state to undo.

## 7. Tests

**323 passed** (was 313; +10 net). New file covers the four required cases:

| Case | Test | Asserts |
|---|---|---|
| 1 | `test_case1_ingestion_disabled_runs_nothing` | no feed opened, no candidate, **no run row written** |
| 2 | `test_case2_candidates_are_created_but_nothing_is_generated` | feed fetched, candidates stored, **provider call count is 0**, no article, both entry points refuse |
| 3 | `test_case3_generation_runs_when_enabled` | provider called once, article created as draft |
| 4 | `test_case4_nothing_publishes_automatically` | with both pipelines on and `NEWS_AUTO_PUBLISH=true` forced, status is not `published` and zero published rows exist |

Plus: defaults closed, the two gates independent in both directions, legacy fallback drives
both, explicit flags override legacy, and `None` is not confused with `False`.

The Case 2 test counts **actual provider invocations**, not configuration values — the
question is not "is the flag false" but "did anything reach the model".

Frontend build: clean. API verified live: `ingestionEnabled=false`, `generationEnabled=false`,
`usesLegacyNewsFlag=false`, `autoPublish=false`.

## 8. Risks

| Risk | Assessment |
|---|---|
| Production behaviour changes on deploy | **No.** Production has neither new flag set and `NEWS_ENABLED=false`; all paths resolve to disabled, as now. |
| Legacy environments break | **No.** `NEWS_ENABLED=true` still enables both, verified in a container. |
| Operator sets only one flag and is surprised | Mitigated: admin reports both states plus a legacy warning. |
| Two flags is more configuration surface | Accepted. It is the minimum needed to express "ingest but do not generate". |
| Deprecated variable lingers indefinitely | Real. Nothing forces removal. `uses_legacy_news_flag` makes it visible; removal should be a later, deliberate step. |

## 9. Next recommended step

**Step 2 — CLI / manual ingestion validation.** Step 1 makes it safe: ingestion can be
enabled in production with generation provably off.

Note for Step 2: a first production run with the default 48h lookback will find **nothing**,
because first-party AI labs publish every few days. It needs a wider one-off window, which
`run_ingestion(lookback_hours=…)` already accepts.
