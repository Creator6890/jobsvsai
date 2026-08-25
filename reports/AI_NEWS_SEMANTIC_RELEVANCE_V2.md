# news-semantic-relevance-v2 — aligning the semantic gate with work impact

**Recommendation: READY FOR SUPERVISED REVALIDATION** — with one honest limitation stated
plainly in §10: no provider was called, so the *contract* is validated and the *verdict* is
not.

Nothing was deployed. No Gemini call, no generation, no publication, no cron, no change to
`news-generation-priority-v1`, `news-relevance-v1` or occupation scoring.

---

## 1. Why v1 was too narrow

`news-semantic-relevance-v1` asked one question: *"Is this genuinely AI news?"*, and answered
it with a single definition — **"a material development in what AI can do or where it is
deployed."** Every accept criterion was a capability or deployment change: model release, agent
capability, robotics, inference breakthrough, coding automation, deployable system.

Applied to the first production corpus it rejected candidate 25 — the Stanford study finding
AI-exposed occupations lost entry-level hiring — at **0.95 confidence**, with the reason:

> "This is an academic study analyzing labor market trends and youth employment impacts rather
> than a material development in AI capabilities, model releases, or system deployments."

**The model was right about the policy and the policy was wrong about the product.** That
verdict is a correct application of v1's rules. It is also a rejection of the single most
on-topic item the pipeline had found, for a service whose stated purpose is *"how is AI likely
to affect my job, and what should I do about it?"*

The conflict was structural, not incidental. `news-generation-priority-v1` ranks credible
labour-market evidence **highest** — that is what it was built to do. So the pipeline was
routing its best-ranked candidates into a gate designed to refuse them, and the deterministic
and semantic layers were encoding two different definitions of the product. That could not be
fixed by tuning a threshold, and it stayed invisible until a real generation call was made.

## 2. Exact product definition for v2

The gate now asks:

> **"Is this a substantive AI development, OR credible evidence that AI is changing work?"**

An item qualifies on **either** limb. The prompt states them as categories A/B (development)
and B (evidence), with the boundary against opinion made explicit and load-bearing.

## 3. The new positive category — empirical AI-and-work evidence

Substantive evidence about AI's measurable effect on jobs, workers, or how work is done —
explicitly **not requiring** any model release or deployment announcement:

- employment, hiring, layoffs, displacement or headcount effects
- wages, earnings or entry-level opportunity
- task substitution, task augmentation or work compression
- productivity, throughput or time saved on real work
- workforce structure, staffing patterns or occupational change
- how adoption is landing on the people doing the work

Acceptable forms are enumerated: academic research, labour-market datasets, credible surveys,
company studies reporting measured outcomes, and independent reporting on any of these.

The prompt names the case that broke v1 as a worked example, because writing the failure down
is cheaper than hoping a general rule covers it:

> "A study finding that AI-exposed occupations lost entry-level hiring is squarely in scope. It
> announces no model and ships no product, and that is fine: measuring the effect is the
> contribution."

## 4. Preserved rejection boundaries

Every v1 rejection survives unchanged: funding rounds, valuations, IPOs, earnings; executive
appointments and board changes; conferences, keynotes, sponsorships, awards; advertising and
marketing rollouts, pricing-only changes, regional availability; contentless corporate
partnerships; legal and regulatory stories with no capability change.

**The widening's own failure mode is blocked explicitly.** The obvious risk in adding a
work-evidence category is that "anything mentioning jobs" becomes relevant. The prompt forbids
exactly that:

> "An item does not become relevant merely because it uses the words jobs, workers,
> employment, automation or future of work. Ask what the item actually establishes."

A dedicated section, *"Evidence versus opinion — the distinction that matters most"*, rejects
opinion columns and think pieces, predictions and speculation without supporting data, broad
"AI will change jobs" commentary with nothing measured, and ethics or policy debate with no
development and no findings. The operative test is a positive obligation rather than a
blacklist:

> "Accept only when the item reports something observed, measured or shipped. If you cannot
> name what was measured or what was built, it is not in scope."

## 5. Capability and deployment acceptance retained

Category A is carried over intact — model releases and substantive updates, agent/tool-use/
computer-use capability, robotics and physical automation, inference and training
breakthroughs, multimodal changes, coding-automation releases, products gaining materially new
capability, commercially deployable automation systems.

Deployment was made explicit rather than implied: *"a meaningful enterprise deployment or
production rollout, where AI is documented doing real work inside an organisation."* Five
parametrised tests pin the capability phrases so a future edit cannot quietly weaken the path
v1 already got right.

## 6. Source attribution

Relevance and credibility are different questions, and the prompt must not merge them:

> "A vendor case study describing measured outcomes at a named customer is legitimate category
> B material. Relevance is not a judgement that the claim has been independently verified — it
> means the item is worth analysing. Treat a company's report about its own product as the
> company's report, not as established fact, and carry that distinction into the brief you
> write in Step 2."

This makes candidate 24 (OpenAI's Asana/Codex customer story) admissible **as a vendor claim**
while instructing the brief to preserve attribution. Full attribution enforcement was not
attempted here — it belongs to Step 2 and needs its own supervised test, which remains the
open question from the previous session.

## 7. Historical v1 verdict handling

**No verdict was rewritten, and no bulk operation exists.**

The two versions are already persisted per item (`semantic_policy_version`) and per run, so
every historical verdict stays attributable to the policy that produced it. Candidate 25 still
reads `is_ai_news=false`, `confidence=0.95`, `semantic_policy_version='news-semantic-relevance-v1'`.

### Why a new operator path was needed

A semantic rejection sets `status='ignored'` **and** `is_ai_news=false`, and
`select_generation_candidates` filters on both — so a rejected item is doubly excluded. The
existing `set_ingest_status` can restore `candidate` but does not clear the verdict, so it
cannot make a rejected item eligible again. There was no safe path, which is what Step 8
anticipated.

### The minimum path added

`requeue_for_reassessment(session, item_id, current_policy_version)`, exposed as
`python -m app.news.cli requeue --item ID`. Deliberately narrow:

- **One item per call.** There is no bulk variant, and a test asserts the module exposes no
  other `requeue*` name and the signature takes no plural argument. A bulk reset would rewrite
  history and spend the daily budget without anyone choosing to.
- **Refused when the stored verdict came from the policy currently in force**, so the same
  policy can never be asked to re-roll a decision it already made — the guard against burning
  free-tier quota in a loop.
- **Refused once the item is linked to an article**, which is a conversion, not a verdict.
- **Refused when there is no verdict at all** — nothing to requeue.
- **`generation_attempts` is not reset.** The spend already happened and the daily cap counts
  it; erasing it would make the budget lie.
- **The superseded verdict is printed before it is cleared**, because the per-item columns hold
  only the current verdict and it is not archived elsewhere.

### What must happen to candidate 25

After v2 is deployed, exactly two explicit operator steps, in order:

```
python -m app.news.cli requeue  --item 25     # returns it to the queue, spends nothing
python -m app.news.cli generate --item 25     # one supervised call under v2
```

The requeue will be accepted because item 25's stored version (`v1`) differs from the version
then in force (`v2`). Until v2 is deployed the requeue would be **refused**, since v1 would
still be current — the guard working as intended.

## 8. Tests

**465 passed, 0 failed, 0 skipped** via `./scripts/run-tests.sh` against `jobsvsai_test`.
Baseline was 421; 44 tests were added, in `backend/tests/test_news_semantic_relevance_v2.py`.

All seven Step 6 regression categories are covered as contract assertions — capability without
job words, deployment, direct work evidence, think piece, policy/opinion, marketing, generic
partnership — plus:

- versioning: semantic policy is v2, prompt version deliberately still v1
- category A phrases retained (5 parametrised cases)
- category C phrases present (5 parametrised cases) and evidence forms enumerated (5 cases)
- the Stanford worked example is present in the prompt
- v1 rejections all survive (5 parametrised cases)
- opinion/speculation rejected explicitly (4 parametrised cases)
- work vocabulary alone cannot confer relevance
- the observed/measured/shipped obligation is present
- first-party evidence is relevant but not verified, and attribution carries into Step 2
- the prompt references no occupation or scoring data
- **the safety surface is unchanged**: zero `.publish(` call sites, no `news_auto_publish`
  read, `generation_enabled` still checked at three points, `decide_status` still cannot emit
  `published`
- the requeue path: invisible-to-selection before requeue, eligible after, attempt count
  preserved, refused under the policy in force, refused with no verdict, refused for an unknown
  item, and no bulk variant

Two pre-existing tests were updated because the version they pinned legitimately changed.
`test_versions_are_the_documented_ones` now pins `v2` as a literal (pinning is its purpose);
the service test now references `SEMANTIC_POLICY_VERSION` instead of a hardcoded string, since
what it actually cares about is that provenance is recorded, not which version.

One test that previously skipped when the database happened to contain no unassessed item was
rewritten to produce that state itself by requeueing once. A skipped test proves nothing.

## 9. Migration requirement

**None.** `semantic_policy_version` already exists on `news_ingest_items` and
`news_generation_runs`, and both were already being written. Versioning infrastructure was
present from Phase 3; v2 reuses it. Highest migration remains `033`.

The requeue path writes only to existing columns.

## 10. Remaining risks

1. **The verdict is unvalidated. This is the main one.** Everything above tests the *contract* —
   that the prompt says what we intend. No provider was called, so whether Gemini actually
   accepts candidate 25 under v2, and at what confidence, is unknown. A prompt that reads
   correctly to a human can still fail in practice, and this exact class of gap is what the
   first supervised run exposed.
2. **The gate could now fail in the other direction.** v2 widens scope, and the evidence/opinion
   boundary is the only thing holding it. A think piece citing one statistic is the ambiguous
   case, and it is a judgement call the prompt describes but cannot enforce. If v2
   over-accepts, the symptom will be commentary reaching drafts.
3. **The 0.70 semantic-confidence threshold remains unexercised.** Every live verdict so far has
   returned 0.95. Widened criteria may produce genuinely borderline calls, which is the first
   time that threshold would do real work.
4. **Attribution is specified but untested.** §6 tells the model to preserve vendor framing; no
   generated brief has ever been inspected for whether it does.
5. **Provider reliability is unresolved** — one 503 in two calls, on a sample too small to
   characterise.
6. **Requeue discards the prior reason text.** The append-only run row keeps the aggregate and
   the policy version, and the CLI prints the verdict before clearing it, but the per-item
   reason string is not archived. Deliberate, to avoid a migration for a rare operation; worth
   revisiting if requeues become common.

## 11. Recommendation

### READY FOR SUPERVISED REVALIDATION

The policy conflict is resolved in the only place it could be — the semantic contract — and
resolved narrowly. Capability and deployment acceptance are preserved and pinned by tests, the
new evidence category is explicit about what counts as evidence, and the boundary against
opinion is stronger in v2 than it was in v1 rather than weaker. Versioning is honest: v1
verdicts remain attributable to v1, nothing was rewritten, and the only way to revisit one is a
deliberate single-item operator action that refuses to re-run the policy in force.

What cannot be settled here is whether the model agrees. That needs one supervised call, and
the sequence is small and reversible:

1. Deploy v2 (a separate task; nothing was deployed here).
2. `requeue --item 25`, which spends nothing and prints the v1 verdict as it clears it.
3. `generate --item 25` — one call, generation enabled process-scoped only, auto-publish false.
4. Inspect the brief against §6: does it attribute, or assert?
5. If candidate 25 is accepted and the brief is sound, retry candidate 24 — the vendor
   attribution test that the 503 prevented.

If candidate 25 is rejected again under v2, that is a far more informative result than the
first rejection was, and the reason string will say why.

The broader target is unchanged: **at least 5 successful supervised generations** before cost
projections or scheduled generation are trustworthy. Two attempts have produced zero.
