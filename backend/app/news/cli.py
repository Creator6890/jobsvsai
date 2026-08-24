"""Operator CLI for AI News ingestion.

    python -m app.news.cli ingest --dry-run       fetch, dedupe, score; write nothing
    python -m app.news.cli ingest                 the same, but store the results
    python -m app.news.cli candidates             what is waiting in the queue
    python -m app.news.cli sources                configured feeds and their health
    python -m app.news.cli runs                   recent ingestion runs

Read-mostly by design. **This CLI cannot call a language model, create an article, or
publish anything** — it imports neither the generation service nor a provider, so those are
not oversights that could be corrected by a flag but capabilities the module does not have.

`--dry-run` exists because a first production ingestion is otherwise unobservable until after
it has happened. It runs the identical pipeline and reports the identical decisions, then
discards them.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.news import relevance
from app.news.ingestion import ItemDecision, run_ingestion
from app.repositories import news_ingest as repo


def _fmt_date(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def _truncate(value: str, width: int) -> str:
    value = value or ""
    return value if len(value) <= width else value[: width - 1] + "…"


def _print_decisions(decisions: list[ItemDecision], show_ignored: bool) -> None:
    """One line per entry: source, score, dedupe, status, date, title."""
    shown = [d for d in decisions if show_ignored or d.status not in ("not_stored",)]
    if not shown:
        print("  (no entries to show)")
        return

    print(f"\n  {'SOURCE':<22}{'SCORE':>6} {'DEDUPE':<16}{'STATUS':<11}{'PUBLISHED':<17}TITLE")
    print(f"  {'-'*22}{'-'*6} {'-'*16}{'-'*11}{'-'*17}{'-'*40}")
    for d in sorted(shown, key=lambda x: (x.status, -(x.relevance_score or -1))):
        score = str(d.relevance_score) if d.relevance_score is not None else "—"
        if d.relevance_confident:
            score += "*"
        dedupe = d.dedupe
        if d.near_duplicate_of:
            # A negative id means the match was against an earlier entry in this same run
            # rather than a stored row — only possible on a dry run.
            target = ("earlier-in-run" if d.near_duplicate_of < 0
                      else f"#{d.near_duplicate_of}")
            dedupe = f"near {target}@{d.near_duplicate_similarity}"
        print(f"  {_truncate(d.source_name, 21):<22}{score:>6} {_truncate(dedupe, 15):<16}"
              f"{d.status:<11}{_fmt_date(d.source_published_at):<17}"
              f"{_truncate(d.original_title, 58)}")
    print("\n  * = above the confident threshold "
          f"({relevance.CONFIDENT_THRESHOLD}); candidate threshold is "
          f"{relevance.CANDIDATE_THRESHOLD}")


def _print_urls(decisions: list[ItemDecision]) -> None:
    stored = [d for d in decisions if d.status in ("candidate", "new")]
    if not stored:
        return
    print("\n  URLs of stored candidates:")
    for d in stored:
        print(f"    [{d.relevance_score}] {d.external_url}")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.news.cli",
        description="AI News ingestion operator commands. Cannot generate or publish.",
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

    candidates = sub.add_parser("candidates", help="show the current candidate queue")
    candidates.add_argument("--status", choices=["new", "candidate", "ignored", "duplicate",
                                                 "processed"])
    candidates.add_argument("--since", type=int, metavar="HOURS")
    candidates.add_argument("--limit", type=int, default=50)
    candidates.add_argument("--urls", action="store_true")
    candidates.set_defaults(handler=cmd_candidates)

    sources = sub.add_parser("sources", help="configured feeds and their health")
    sources.set_defaults(handler=cmd_sources)

    runs = sub.add_parser("runs", help="recent ingestion runs")
    runs.add_argument("--limit", type=int, default=5)
    runs.set_defaults(handler=cmd_runs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
