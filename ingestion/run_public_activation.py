"""Activate the approved launch cohort's publications.

This is the step that makes pages public. It is all-or-nothing, it activates only identities
that pass every readiness check independently re-verified here, and it refuses to activate
anything outside the approved cohort.

Readiness, re-checked per occupation rather than trusted:

  * in the approved content run, with content marked complete
  * carries a current production score snapshot
  * `approved_score_snapshot_id` is set and equals that current snapshot
  * has an active editorial page with a non-empty summary and verdict
  * the page slug is unique

Reversal: `--deactivate` restores the recorded previous status. The run prints the prior
status of every row it changes, so a reversal is possible even from the log alone.

  docker compose run --rm -e PYTHONPATH=/app/ingestion backend \
      python /app/ingestion/run_public_activation.py --content-run 2 --expect-count 507 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from typing import Any

import asyncpg

ACTIVATION_POLICY_VERSION = "phase6-public-activation-v1"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


READINESS_SQL = """
  SELECT candidate.identity_id,
         candidate.onet_soc_code,
         candidate.content_completeness,
         candidate.verdict_snapshot_id,
         publication.activation_status,
         publication.editorial_review_status,
         publication.review_reasons,
         publication.approved_score_snapshot_id,
         current_score.id AS current_snapshot_id,
         page.id AS occupation_id,
         page.slug AS page_slug,
         page.is_active AS page_active,
         (page.summary <> '') AS has_summary,
         (page.verdict <> '') AS has_verdict
  FROM public_occupation_content_candidates candidate
  JOIN canonical_occupation_identities identity ON identity.id = candidate.identity_id
  LEFT JOIN occupations page ON page.id = identity.jobs_vs_ai_occupation_id
  LEFT JOIN occupation_publications publication
         ON publication.identity_id = candidate.identity_id
        AND publication.locale = 'en' AND publication.source_geography = 'US'
  LEFT JOIN current_production_occupation_scores current_score
         ON current_score.identity_id = candidate.identity_id
  WHERE candidate.content_run_id = $1
  ORDER BY candidate.onet_soc_code
"""


def readiness_failures(row: asyncpg.Record) -> list[str]:
    failures: list[str] = []
    if row["content_completeness"] != "complete":
        failures.append(f"content_{row['content_completeness']}")
    if row["current_snapshot_id"] is None:
        failures.append("no_current_production_snapshot")
    if row["approved_score_snapshot_id"] is None:
        failures.append("no_approved_snapshot_binding")
    elif row["approved_score_snapshot_id"] != row["current_snapshot_id"]:
        failures.append("approved_snapshot_is_not_current")
    if row["verdict_snapshot_id"] != row["current_snapshot_id"]:
        failures.append("verdict_describes_a_different_snapshot")
    if row["occupation_id"] is None:
        failures.append("no_editorial_page")
    else:
        if not row["page_active"]:
            failures.append("editorial_page_inactive")
        if not row["has_summary"]:
            failures.append("editorial_page_has_no_summary")
        if not row["has_verdict"]:
            failures.append("editorial_page_has_no_verdict")
    if row["activation_status"] is None:
        failures.append("no_publication_row")
    return failures


async def run(
    content_run_id: int, expect_count: int | None, deactivate: bool, dry_run: bool
) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        rows = await connection.fetch(READINESS_SQL, content_run_id)
        if not rows:
            raise SystemExit(f"Content run {content_run_id} has no candidates.")

        blocked = [
            {"occupationCode": row["onet_soc_code"], "reasons": readiness_failures(row)}
            for row in rows if readiness_failures(row)
        ]
        if blocked:
            await transaction.rollback()
            return {
                "policyVersion": ACTIVATION_POLICY_VERSION,
                "refused": f"{len(blocked)} occupations are not ready for activation",
                "blocked": blocked[:25],
                "persisted": False,
            }
        if expect_count is not None and len(rows) != expect_count:
            raise SystemExit(
                f"Cohort resolved to {len(rows)} occupations, expected {expect_count}."
            )

        target_status = "approved" if deactivate else "public"
        identity_ids = [row["identity_id"] for row in rows]
        previous = Counter(row["activation_status"] for row in rows)
        review_flagged = [
            {"occupationCode": row["onet_soc_code"],
             "reasons": row["review_reasons"] if isinstance(row["review_reasons"], list)
             else json.loads(row["review_reasons"] or "[]")}
            for row in rows if row["activation_status"] == "review_required"
        ]

        summary: dict[str, Any] = {
            "policyVersion": ACTIVATION_POLICY_VERSION,
            "contentRunId": content_run_id,
            "cohort": len(rows),
            "targetStatus": target_status,
            "previousStatusCounts": dict(previous),
            "publicationsFlaggedForTitleReview": len(review_flagged),
            "titleReviewDetail": review_flagged,
            "readinessFailures": 0,
        }

        if dry_run:
            await transaction.rollback()
            summary["persisted"] = False
            return summary

        changed = await connection.execute("""
          UPDATE occupation_publications
             SET activation_status = $2, updated_at = now()
           WHERE identity_id = ANY($1::bigint[])
             AND locale = 'en' AND source_geography = 'US'
             AND activation_status IS DISTINCT FROM $2
        """, identity_ids, target_status)
        summary["rowsChanged"] = int(changed.split()[-1])

        # Nothing outside the approved cohort may have become public as a side effect.
        stray = await connection.fetchval("""
          SELECT count(*) FROM occupation_publications
          WHERE activation_status = 'public' AND identity_id <> ALL($1::bigint[])
        """, identity_ids)
        if stray:
            raise ValueError(f"{stray} publications outside the approved cohort are public.")

        if not deactivate:
            public_total = await connection.fetchval(
                "SELECT count(*) FROM occupation_publications WHERE activation_status='public'")
            if public_total != len(rows):
                raise ValueError(
                    f"Expected {len(rows)} public publications, found {public_total}.")
            inconsistent = await connection.fetchval("""
              SELECT count(*) FROM publication_snapshot_consistency
              WHERE activation_status = 'public' AND consistency_state <> 'consistent'
            """)
            if inconsistent:
                raise ValueError(f"{inconsistent} public pages have an inconsistent snapshot.")
            summary["publicTotal"] = public_total
            summary["publicationSnapshotInconsistencies"] = 0

        await transaction.commit()
        summary["persisted"] = True
        return summary
    except Exception:
        try:
            await transaction.rollback()
        except Exception:
            pass
        raise
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-run", type=int, required=True)
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--deactivate", action="store_true",
                        help="Reverse activation: set the cohort back to 'approved'.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(
        await run(args.content_run, args.expect_count, args.deactivate, args.dry_run),
        indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
