# AI News Phase 4 — Step 3: editorial workflow controls

Date: 2026-08-24
Scope: **Step 3 only.** No scheduler, no related occupations, no auto-publish, no public
changes.

## 1. What was missing

The architecture review found the editorial actions complete except for two:

| Action | Before | Now |
|---|---|---|
| Approve (publish) | present | unchanged |
| Reject | present | unchanged |
| Edit | present | unchanged |
| **Regenerate** | **missing** | added |
| **Archive** | **missing** | added |

Review *surfaces* were already complete after the Phase 3 hardening — source, excerpt, AI
verdict, confidence, reasoning, provider/model, tokens, factors, score, level, tags, job
areas — and are unchanged.

## 2. Archive is not reject

They are different judgements and collapsing them loses the difference:

- **Reject** — a judgement about the *content*. This should not have been an article.
- **Archive** — a judgement about its *currency*. It was fine; it is now retired.

That distinction has a concrete consequence in the data. Rejecting clears `published_at`,
treating the item as something that should never have gone out. **Archiving preserves it**,
because an article that was published genuinely was, and erasing that would falsify the
record of what the site once served.

Neither status is public: `PUBLIC_ARTICLE_PREDICATE` admits only `published`, so an archived
article leaves the site the moment it is archived. **No separate unpublish step is needed**,
and a test asserts the article, the listing and the sitemap all drop it immediately.

**Restore** returns an archived article to `review_required`, never straight to public. Time
has passed; an article worth un-retiring is worth a second look before readers see it again.

## 3. Regenerate rewrites in place

The rule that "one candidate produces one article" is what stops a retried job or an
impatient click from creating duplicates. Regeneration must not become the exception that
breaks it, so it **updates the existing row** and a test asserts the candidate still maps to
exactly one article afterwards.

Four refusals, each returning a reason rather than raising:

| Condition | Why refused |
|---|---|
| Article is `published` | Rewriting in place would silently change what readers are already served, with no review between the model's new output and the public page. Archive or unpublish first — both are one click and both make the change visible. |
| `NEWS_GENERATION_ENABLED=false` | Step 1's gate applies here too. |
| Daily generation cap reached | A regenerated brief costs a call like any other; exempting it would make the ceiling meaningless to anyone clicking the button. |
| No source candidate | A hand-written article has nothing to regenerate *from*. Those are edited. |

**Each refusal costs zero quota** — the provider is never reached. Tested.

Two behaviours worth stating explicitly:

- **A stale editorial override is cleared.** An override was a judgement about prose that no
  longer exists; carrying it onto new text would attribute an editor's decision to writing
  they never read.
- **If the model now says "not AI news", the article is left exactly as it was** and the new
  verdict is reported. Deleting an editor's article because a second call disagreed is not a
  decision to make automatically.

A failed regeneration also leaves the article intact, with `regeneration_count` unchanged.

## 4. Migration 032

The first Phase 4 step needing one. News-only; no reference to any occupation or scoring
table.

- `news_articles.status` CHECK widened to include `archived`.
- Added `archived_at`, `archived_by`, `archive_reason`, `regenerated_at`,
  `regeneration_count`.
- Constraints: an archive must record its actor; status and `archived_at` cannot disagree;
  `regeneration_count` and `regenerated_at` cannot disagree.
- Partial index on archived articles for the queue.

`set_status()` now refuses `archived` outright, the same way it refuses `published`: a helper
that takes only a status string cannot record who archived it, and failing there gives a
legible message instead of a constraint violation surfacing from three layers down.

**Backwards compatible.** Existing rows are untouched — `regeneration_count` defaults to 0
and the archive columns to NULL, which satisfies every new constraint.

## 5. Files changed

| File | Change |
|---|---|
| `migrations/032_ai_news_phase4_editorial.sql` | **new** |
| `backend/app/repositories/news.py` | `archive`, `restore_from_archive`, `replace_generated_content`; `set_status` refuses archive |
| `backend/app/news/generation_service.py` | `regenerate_article` |
| `backend/app/api/admin_news.py` | `/archive`, `/restore`, `/regenerate` |
| `backend/app/schemas/news.py` | `archived` status, `ArchiveInput`, audit fields |
| `frontend/src/lib/api.ts` | types |
| `frontend/src/app/admin/news/actions.ts` | three server actions |
| `frontend/src/app/admin/news/[articleId]/page.tsx` | Lifecycle panel |
| `backend/tests/test_news_editorial.py` | **new** — 14 tests |

## 6. Tests

**346 passed** (was 332; +14). Covering:

- archiving preserves `published_at` where rejecting clears it
- an archived article leaves the public API, listing and sitemap immediately
- restore returns to `review_required`, never to public
- `set_status` refuses to archive without an actor
- all three endpoints require authentication
- regeneration rewrites in place and creates no second article
- regeneration clears a stale editorial override
- published articles cannot be regenerated, and the refusal costs no quota
- regeneration is refused when generation is disabled, and when the daily cap is reached
- a hand-written article cannot be regenerated
- a regeneration that now rejects leaves the article untouched
- a failed regeneration leaves the article intact
- regenerated articles are never published automatically, even with `NEWS_AUTO_PUBLISH=true`

Frontend build clean. Migration applied to dev and test; occupation state unchanged at 507
live / 507 public / JVS 1.0.3.

## 7. Risks

| Risk | Assessment |
|---|---|
| `archived` breaks an existing consumer | No. The public predicate matches on `published` only, and admin filters are explicit. |
| Regeneration loses editorial work | Real but bounded: it overwrites headline and both prose fields, and clears an impact override. The UI states this before the button. Published articles are refused outright. |
| Regeneration spends quota unexpectedly | Counted against the same daily cap; every refusal path returns before reaching the provider. |
| Archive used where reject was meant | They are separate buttons with different copy; the distinction is recorded rather than inferred. |
| Migration 032 not yet on production | Correct — this has not been deployed. It must be applied before the new endpoints are used there. |

## 8. Next recommended step

**Step 4 — generation pipeline validation.** Step 3 was ordered first so anything generated
during that validation can be archived rather than only rejected, and so a poor brief can be
regenerated in place instead of leaving an orphaned article.

Two things still gate Step 4: the free-tier quota ceiling (~3 calls per session observed),
and the two candidates from the Phase 3 supervised run that never completed.
