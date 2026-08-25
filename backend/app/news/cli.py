"""Operator CLI for AI News ingestion.

    python -m app.news.cli ingest --dry-run       fetch, dedupe, score; write nothing
    python -m app.news.cli ingest                 the same, but store the results
    python -m app.news.cli generate               turn candidates into review-ready drafts
    python -m app.news.cli candidates             what is waiting in the queue
    python -m app.news.cli sources                configured feeds and their health
    python -m app.news.cli runs                   recent ingestion runs
    python -m app.news.cli metrics                cost, reliability and quality readings

`generate` is the one command that spends money. It is gated by `NEWS_GENERATION_ENABLED`,
bounded by the daily cap, and **cannot publish**: every article it produces is `draft` or
`review_required`, because the service it calls has no path to `published`.

Every other command is read-only or ingestion-only.

`--dry-run` exists because a first production ingestion is otherwise unobservable until after
it has happened. It runs the identical pipeline and reports the identical decisions, then
discards them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news import priority, relevance
from app.news.ingestion import ItemDecision, run_ingestion
from app.repositories import news_ingest as repo


def _fmt_date(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def _truncate(value: str, width: int) -> str:
    value = value or ""
    return value if len(value) <= width else value[: width - 1] + "…"


def _print_decisions(decisions: list[ItemDecision], show_ignored: bool) -> None:
    """One line per entry, carrying both scores.

    AI relevance and JobsVsAI priority answer different questions and regularly disagree, so
    showing only one of them hides the disagreement an operator most needs to see. Ordering
    here is by priority, because that is the order generation will actually consume.
    """
    shown = [d for d in decisions if show_ignored or d.status not in ("not_stored",)]
    if not shown:
        print("  (no entries to show)")
        return

    print(f"\n  {'SOURCE':<22}{'AI':>4}{'PRIO':>6} {'BAND':<8}{'STATUS':<11}"
          f"{'PUBLISHED':<17}TITLE")
    print(f"  {'-'*22}{'-'*4}{'-'*6} {'-'*8}{'-'*11}{'-'*17}{'-'*40}")
    for d in sorted(shown, key=lambda x: (x.status, -(x.priority_score or -1),
                                          -(x.relevance_score or -1))):
        score = str(d.relevance_score) if d.relevance_score is not None else "—"
        if d.relevance_confident:
            score += "*"
        prio = str(d.priority_score) if d.priority_score is not None else "—"
        band = d.priority_band or ""
        if d.title_only:
            band += "!"
        if d.near_duplicate_of:
            # A negative id means the match was against an earlier entry in this same run
            # rather than a stored row — only possible on a dry run.
            target = ("earlier-in-run" if d.near_duplicate_of < 0
                      else f"#{d.near_duplicate_of}")
            band = f"near {target}"
        print(f"  {_truncate(d.source_name, 21):<22}{score:>4}{prio:>6} {band:<8}"
              f"{d.status:<11}{_fmt_date(d.source_published_at):<17}"
              f"{_truncate(d.original_title, 52)}")
    print("\n  AI   = relevance "
          f"({relevance.POLICY_VERSION}); * above confident threshold "
          f"{relevance.CONFIDENT_THRESHOLD}, candidate threshold {relevance.CANDIDATE_THRESHOLD}")
    print(f"  PRIO = JobsVsAI generation priority ({priority.POLICY_VERSION}); "
          f"HIGH >= {priority.HIGH_THRESHOLD}, MEDIUM >= {priority.MEDIUM_THRESHOLD}")
    print("  !    = feed supplied no excerpt; judged on the headline alone")

    ranked = [d for d in shown if d.status == "candidate" and d.priority_score is not None]
    if ranked:
        ranked.sort(key=lambda x: (-(x.priority_score or 0), -(x.relevance_score or 0)))
        print("\n  Top candidates by generation priority:")
        for d in ranked[:15]:
            signals = ", ".join(d.priority_signals[:6]) or "(no substantive signal)"
            print(f"    AI {str(d.relevance_score or '—'):>3} · "
                  f"Priority {d.priority_score:>3} {d.priority_band:<6} "
                  f"{_truncate(d.original_title, 56)}")
            print(f"        {_truncate(signals, 96)}")


def _print_urls(decisions: list[ItemDecision]) -> None:
    stored = [d for d in decisions if d.status in ("candidate", "new")]
    if not stored:
        return
    print("\n  URLs of stored candidates (priority order):")
    for d in sorted(stored, key=lambda x: -(x.priority_score or 0)):
        print(f"    [AI {d.relevance_score} / prio {d.priority_score}] {d.external_url}")


async def cmd_ingest(args: argparse.Namespace) -> int:
    settings = get_settings()
    mode = "DRY RUN — nothing will be written" if args.dry_run else "LIVE — results will be stored"
    print(f"AI News ingestion · {mode}")
    print(f"  ingestion_enabled = {settings.ingestion_enabled}"
          f"   generation_enabled = {settings.generation_enabled}"
          f"   auto_publish = {settings.news_auto_publish}")
    print(f"  lookback = {args.lookback or settings.news_lookback_hours}h"
          f"   per-feed cap = {args.max_entries or settings.news_max_entries_per_feed}"
          f"   relevance policy = {relevance.POLICY_VERSION}")

    if not settings.ingestion_enabled:
        # Reported rather than raised: an operator running this on a gated environment should
        # be told why nothing happened, not handed a traceback.
        print("\n  SKIPPED: NEWS_INGESTION_ENABLED is false.")
        print("  Set NEWS_INGESTION_ENABLED=true to allow feed ingestion.")
        return 0

    async with SessionFactory() as session:
        result = await run_ingestion(
            session, triggered_by=args.triggered_by, lookback_hours=args.lookback,
            max_entries_per_feed=args.max_entries, dry_run=args.dry_run,
        )

    c = result.counters
    print(f"\n  status={result.status}  {c.duration_ms}ms"
          + (f"  run_id={result.run_id}" if result.run_id else ""))
    print(f"  sources : attempted={c.sources_attempted} ok={c.sources_succeeded} "
          f"failed={c.sources_failed}")
    print(f"  entries : fetched={c.items_fetched} outside_window={c.items_outside_window}")
    print(f"  stored  : new={c.items_new} candidate={c.items_candidate} ignored={c.items_ignored}")
    print(f"  dedupe  : exact={c.items_exact_duplicate} near={c.items_near_duplicate}")

    for error in result.errors:
        print(f"  ERROR   : {error['source']}: {_truncate(error['error'], 100)}")

    _print_decisions(result.decisions, show_ignored=args.all)
    if args.urls:
        _print_urls(result.decisions)

    if args.dry_run:
        print("\n  Nothing was written. Re-run without --dry-run to store these results.")
    return 0


async def cmd_generate(args: argparse.Namespace) -> int:
    """Turn candidates into review-ready drafts. The command that costs money."""
    from app.news.generation_service import run_generation_batch

    settings = get_settings()
    print("AI News generation")
    print(f"  generation_enabled = {settings.generation_enabled}"
          f"   auto_publish = {settings.news_auto_publish}"
          f"   provider = {settings.news_llm_provider}")
    print(f"  batch = {args.batch_size or settings.generations_per_run}"
          f"   daily cap = {settings.generations_per_day}"
          f"   model = {settings.news_llm_model or 'provider default'}")

    if not settings.generation_enabled:
        print("\n  SKIPPED: NEWS_GENERATION_ENABLED is false. No provider call was made.")
        return 0
    if settings.news_auto_publish:
        # Reported, not enforced here: the generation service has no path to `published`
        # regardless. Surfaced so a misconfiguration is visible rather than silent.
        print("\n  WARNING: NEWS_AUTO_PUBLISH is true. Generation still cannot publish —"
              " every article is draft or review_required — but the flag should be false.")

    async with SessionFactory() as session:
        result = await run_generation_batch(
            session, triggered_by=args.triggered_by, batch_size=args.batch_size,
            ingest_item_ids=args.item or None,
        )

    if result.status == "skipped":
        print(f"\n  SKIPPED: {result.skipped_reason}")
        return 0

    c = result.counters
    print(f"\n  status={result.status}  {c.duration_ms}ms  run_id={result.run_id}")
    print(f"  selected={c.candidates_selected} calls={c.calls_made} "
          f"skipped_existing={c.skipped_existing}")
    print(f"  outcomes: accepted={c.accepted} rejected={c.rejected} failed={c.failed}")
    print(f"  articles: draft={c.articles_draft} review_required={c.articles_review_required}")
    print(f"  tokens  : input={c.input_tokens} output={c.output_tokens} "
          f"total={c.input_tokens + c.output_tokens}")

    # The numbers Step 5 needs to answer whether this is worth doing. Printed per run rather
    # than aggregated, because a single run is the unit an operator is deciding about.
    if c.calls_made:
        # Same helpers the metrics layer uses, so a run summary and the aggregate report
        # cannot express the same quantity two different ways.
        from app.news.metrics import _rate

        print(f"\n  acceptance {_pct(_rate(c.accepted, c.calls_made))}"
              f"   rejection {_pct(_rate(c.rejected, c.calls_made))}"
              f"   failure {_pct(_rate(c.failed, c.calls_made))}")
        tokens = c.input_tokens + c.output_tokens
        print(f"  tokens per accepted article: "
              f"{round(tokens / c.accepted) if c.accepted else '—'}")

    for o in result.outcomes:
        print(f"\n  --- #{o.ingest_item_id} [{o.source_name}] det={o.relevance_score} "
              f"-> {o.outcome.upper()}")
        print(f"      {_truncate(o.original_title, 84)}")
        if o.latency_ms is not None:
            tokens = (f" · {o.input_tokens}/{o.output_tokens} tokens"
                      if o.input_tokens is not None else "")
            print(f"      {o.latency_ms}ms{tokens}")
        if o.is_ai_news is not None:
            print(f"      is_ai_news={o.is_ai_news} confidence={o.ai_relevance_confidence}")
            print(f"      {_truncate(o.relevance_reason or '', 96)}")
        if o.outcome == "accepted":
            f = o.factors
            print(f"      factors cap={f['capability_advancement']} "
                  f"deploy={f['commercial_deployability']} "
                  f"breadth={f['breadth_of_affected_work']} "
                  f"speed={f['adoption_speed']} "
                  f"reduction={f['human_work_reduction_potential']}")
            print(f"      impact {o.impact_score} {(o.impact_level or '').upper()} "
                  f"(confidence {o.impact_confidence}) -> {o.article_status}")
        if o.error:
            print(f"      {o.error_kind or 'error'}: {_truncate(o.error, 96)}")

    print("\n  Nothing was published. Review at /admin/news before anything goes public.")
    return 0


async def cmd_candidates(args: argparse.Namespace) -> int:
    async with SessionFactory() as session:
        counts = await repo.ingest_status_counts(session)
        items = await repo.list_ingest_items(
            session, status=args.status, since_hours=args.since, limit=args.limit
        )

    print("AI News candidate queue")
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    if not items:
        print("\n  (nothing matching)")
        return 0

    print(f"\n  {'ID':>7}{'SCORE':>6} {'SOURCE':<22}{'STATUS':<11}{'PUBLISHED':<17}TITLE")
    print(f"  {'-'*7}{'-'*6} {'-'*22}{'-'*11}{'-'*17}{'-'*40}")
    for item in items:
        score = item["relevance_score"]
        verdict = ""
        if item.get("is_ai_news") is not None:
            verdict = " [AI:yes]" if item["is_ai_news"] else " [AI:no]"
        print(f"  {item['id']:>7}{(str(score) if score is not None else '—'):>6} "
              f"{_truncate(item['source_name'], 21):<22}{item['status']:<11}"
              f"{_fmt_date(item['source_published_at']):<17}"
              f"{_truncate(item['original_title'], 52)}{verdict}")
    if args.urls:
        for item in items:
            print(f"    [{item['relevance_score']}] {item['external_url']}")
    return 0


async def cmd_sources(args: argparse.Namespace) -> int:
    async with SessionFactory() as session:
        rows = (await session.execute(text("""
          SELECT name, enabled, trust_tier, source_type, feed_format, feed_url,
                 last_success_at, consecutive_failures, last_error,
                 (SELECT count(*) FROM news_ingest_items i WHERE i.source_id = s.id) items
          FROM news_sources s ORDER BY trust_tier, name
        """))).mappings().all()

    print(f"AI News sources ({len(rows)} configured)")
    print(f"\n  {'NAME':<24}{'ON':<4}{'TIER':<6}{'FMT':<6}{'ITEMS':>6}{'FAILS':>7}  LAST SUCCESS")
    print(f"  {'-'*24}{'-'*4}{'-'*6}{'-'*6}{'-'*6}{'-'*7}  {'-'*18}")
    for r in rows:
        print(f"  {_truncate(r['name'], 23):<24}{('yes' if r['enabled'] else 'no'):<4}"
              f"{r['trust_tier']:<6}{(r['feed_format'] or '—'):<6}{r['items']:>6}"
              f"{r['consecutive_failures']:>7}  {_fmt_date(r['last_success_at'])}")
        if r["last_error"]:
            print(f"      last error: {_truncate(r['last_error'], 88)}")
    return 0


async def cmd_runs(args: argparse.Namespace) -> int:
    async with SessionFactory() as session:
        rows = await repo.latest_runs(session, limit=args.limit)
    if not rows:
        print("No ingestion runs recorded.")
        return 0
    print(f"Recent ingestion runs ({len(rows)})")
    for r in rows:
        print(f"\n  {r['run_key']}  [{r['status']}]  {_fmt_date(r['started_at'])}"
              f"  by {r['triggered_by']}")
        print(f"    sources {r['sources_succeeded']}/{r['sources_attempted']} ok, "
              f"{r['sources_failed']} failed · lookback {r['lookback_hours']}h")
        print(f"    fetched={r['items_fetched']} new={r['items_new']} "
              f"candidate={r['items_candidate']} ignored={r['items_ignored']} "
              f"exact_dup={r['items_exact_duplicate']} near_dup={r['items_near_duplicate']} "
              f"outside_window={r['items_outside_window']}")
        for error in (r["errors"] or []):
            print(f"    ERROR {error.get('source')}: {_truncate(error.get('error', ''), 88)}")
    return 0


def _pct(value: float | None) -> str:
    """A rate as a percentage, or an em dash. None means "nothing to divide by"."""
    return f"{value * 100:.0f}%" if value is not None else "—"


def _ms(value: object) -> str:
    return f"{int(value)}ms" if value is not None else "—"


def _money(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "—"


async def cmd_metrics(args: argparse.Namespace) -> int:
    """Report cost, reliability and editorial usefulness.

    Formatting only. Every derived value comes from app.news.metrics, so the numbers here
    and in `--json` cannot drift apart.
    """
    from app.news import metrics as metrics_service

    async with SessionFactory() as session:
        data = await metrics_service.collect(session, days=args.days)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0

    src, cand, ing = data["sources"], data["candidates"], data["ingestion"]
    gen, cost, rel, qual = data["generation"], data["cost"], data["reliability"], data["quality"]

    print(f"AI NEWS METRICS · last {data['windowDays']} days")
    if data["status"] == metrics_service.INSUFFICIENT:
        print("\n  No ingestion runs and no generation attempts in this window.")
        print("  Every figure below is zero because nothing has run, not because it failed.")

    print("\nINGESTION\n-----------")
    print(f"  Sources configured   : {src['configured']} ({src['enabled']} enabled, "
          f"{src['failing']} currently failing)")
    print(f"  Fetch attempts       : {rel['ingestionFetchAttempts']}")
    print(f"  Successful fetches   : {rel['ingestionFetchSuccesses']}")
    print(f"  Failed fetches       : {ing['source_failures']}")
    print(f"  Success rate         : {_pct(rel['ingestionSuccessRate'])}")
    print(f"  Runs                 : {ing['runs']}   last {_fmt_date(ing['last_run'])}")

    print("\nCANDIDATES\n-----------")
    print(f"  Entries fetched      : {ing['fetched']}   outside window {ing['outside_window']}")
    print(f"  Candidates created   : {qual['candidatesCreated']}")
    print(f"  Ignored (relevance)  : {qual['candidatesIgnored']}")
    print(f"  Duplicates           : exact {ing['exact_duplicates']}   "
          f"near {ing['near_duplicates']}")

    print("\nGENERATION\n-----------")
    print(f"  Attempts             : {rel['generationAttempts']}")
    print(f"  Accepted / rejected  : {gen['accepted']} / {gen['rejected']}")
    print(f"  Failed               : {gen['failed']}")
    print(f"  Success rate         : {_pct(rel['generationSuccessRate'])}   "
          f"(a rejection is a successful call)")
    print(f"  Provider failure rate: {_pct(rel['providerFailureRate'])}   "
          f"timeouts {_pct(rel['timeoutRate'])}   retries {_pct(rel['retryRate'])}")
    print(f"  Latency mean         : {_ms(rel['latencyMeanMs'])}")
    print(f"  Latency median (p50) : {_ms(rel['latencyP50Ms'])}")
    print(f"  Latency p95 / max    : {_ms(rel['latencyP95Ms'])} / {_ms(rel['latencyMaxMs'])}")
    if rel["failuresByKind"]:
        for kind, total in sorted(rel["failuresByKind"].items(), key=lambda kv: -kv[1]):
            print(f"    {kind:<18}{total}")

    print("\nTOKENS\n-----------")
    print(f"  Input tokens         : {cost['inputTokens']}")
    print(f"  Output tokens        : {cost['outputTokens']}")
    print(f"  Total tokens         : {cost['totalTokens']}")
    print(f"  Tokens / attempt     : {cost['tokensPerAttempt'] if cost['tokensPerAttempt'] is not None else '—'}")
    print(f"  Tokens / article     : {cost['tokensPerArticle'] if cost['tokensPerArticle'] is not None else '—'}")

    print("\nCOST\n-----------")
    if not cost["priced"]:
        print("  No currency estimate: set NEWS_LLM_COST_PER_1M_INPUT and "
              "NEWS_LLM_COST_PER_1M_OUTPUT.")
        print("  A rate is not guessed here — an invented price produces a number that")
        print("  looks authoritative and is not.")
    else:
        print(f"  Estimated spend      : {_money(cost['estimatedSpend'])}")
        print(f"  Cost / attempt       : {_money(cost['costPerAttempt'])}")
        print(f"  Cost / article       : {_money(cost['costPerArticle'])}")
        print(f"  Cost / 100 articles  : {_money(cost['costPer100Articles'])}")
    if cost["status"] == metrics_service.INSUFFICIENT:
        print(f"  INSUFFICIENT SAMPLE SIZE: {cost['sampleSize']} successful generation(s); "
              f"{cost['minimumSampleForProjection']} needed.")
        print("  Per-article figures and projections are withheld rather than estimated.")
    elif cost["monthlyProjections"]:
        print("  Monthly projection at:")
        for volume, amount in cost["monthlyProjections"].items():
            print(f"    {volume.replace('_', ' '):<14} {_money(amount)}")

    print("\nEDITORIAL\n-----------")
    print(f"  Articles created     : {qual['articlesCreated']}")
    print(f"  Draft / review req.  : {qual['draft']} / {qual['reviewRequired']}")
    print(f"  Published            : {qual['published']}")
    print(f"  Rejected             : {qual['rejected']}")
    print(f"  Archived             : {qual['archived']}")
    print(f"  Regenerated          : {qual['regeneratedArticles']} article(s), "
          f"{qual['regenerations']} time(s)")
    print(f"  Impact overrides     : {qual['impactOverrides']}")

    print("\nQUALITY\n-----------")
    print(f"  Semantic acceptance  : {_pct(qual['semanticAcceptanceRate'])}   "
          f"(of candidates the model assessed)")
    print(f"  Editorial acceptance : {_pct(qual['editorialAcceptanceRate'])}   "
          f"(of {qual['editoriallyResolved']} resolved; draft/review excluded as undecided)")
    print(f"  Regeneration rate    : {_pct(qual['regenerationRate'])}")
    print(f"  Impact distribution  : low {qual['impactDistribution']['low']}  "
          f"medium {qual['impactDistribution']['medium']}  "
          f"high {qual['impactDistribution']['high']}")
    print(f"  Avg impact score     : {qual['avgImpactScore'] if qual['avgImpactScore'] is not None else '—'}")
    print(f"  Avg confidence       : impact {qual['avgImpactConfidence'] or '—'}   "
          f"semantic {qual['avgSemanticConfidence'] or '—'}")
    print("\n  Quality figures are proxies: self-reported confidences, policy scores and")
    print("  what editors did. Nothing here has been validated against whether a story")
    print("  mattered to a reader.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.news.cli",
        description="AI News operator commands. Nothing here can publish.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="fetch feeds, deduplicate and score")
    ingest.add_argument("--dry-run", action="store_true",
                        help="run the full pipeline and write nothing")
    ingest.add_argument("--lookback", type=int, metavar="HOURS",
                        help="override the lookback window; a first run needs a wide one")
    ingest.add_argument("--max-entries", type=int, metavar="N",
                        help="override the per-feed entry cap")
    ingest.add_argument("--all", action="store_true",
                        help="also list entries rejected by the window or exact dedupe")
    ingest.add_argument("--urls", action="store_true", help="print stored candidate URLs")
    ingest.add_argument("--triggered-by", default="cli", help="recorded on the run row")
    ingest.set_defaults(handler=cmd_ingest)

    generate = sub.add_parser(
        "generate", help="generate drafts from candidates (calls the provider)")
    generate.add_argument("--batch-size", type=int, metavar="N",
                          help="override the configured batch size")
    generate.add_argument("--item", type=int, action="append", metavar="ID",
                          help="generate for specific candidates; repeatable")
    generate.add_argument("--triggered-by", default="cli", help="recorded on the run row")
    generate.set_defaults(handler=cmd_generate)

    candidates = sub.add_parser("candidates", help="show the current candidate queue")
    candidates.add_argument("--status", choices=["new", "candidate", "ignored", "duplicate",
                                                 "processed"])
    candidates.add_argument("--since", type=int, metavar="HOURS")
    candidates.add_argument("--limit", type=int, default=50)
    candidates.add_argument("--urls", action="store_true")
    candidates.set_defaults(handler=cmd_candidates)

    sources = sub.add_parser("sources", help="configured feeds and their health")
    sources.set_defaults(handler=cmd_sources)

    metrics = sub.add_parser("metrics", help="cost, reliability and quality readings")
    metrics.add_argument("--days", type=int, default=30, metavar="N",
                         help="reporting window; default 30")
    metrics.add_argument("--json", action="store_true",
                         help="machine-readable output for dashboards")
    metrics.set_defaults(handler=cmd_metrics)

    runs = sub.add_parser("runs", help="recent ingestion runs")
    runs.add_argument("--limit", type=int, default=5)
    runs.set_defaults(handler=cmd_runs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
