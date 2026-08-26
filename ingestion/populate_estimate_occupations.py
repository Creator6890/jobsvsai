"""Create editorial `occupations` rows for occupations that carry a published estimate.

A sibling of `populate_editorial_occupations.py`, deliberately kept separate rather than
folded in behind a flag. That script exists to bind a verified page to the exact promoted
snapshot its verdict describes; it asserts a snapshot is present and current, and that
assertion is load-bearing — it is what stops a page publishing a number the store no longer
serves. An estimate has no snapshot, so running it through that path would mean weakening the
one check that protects verified pages, for the benefit of rows that are not verified.

So this script writes pages and nothing else:

  occupations                       the page row (title, slug, summary, aliases, category)
  canonical_occupation_identities   jobs_vs_ai_occupation_id, linking identity to page

What it never touches, and has no SQL for:

  occupation_publications           not activation_status, not approved_score_snapshot_id.
                                    An estimated page is public because an estimate is
                                    published, which is recorded in
                                    occupation_score_estimates.is_published. The verified
                                    count stays exactly what it has always meant.

`verdict` is written empty on purpose. The verdict template renders a claim about a promoted
snapshot; there is no snapshot here, and a plausible sentence in its place would be the exact
fabrication the estimate layer exists to avoid. The page renders its preliminary-estimate
panel instead.

  docker compose run --rm -e PYTHONPATH=/app backend \\
      python -m ingestion.populate_estimate_occupations --content-run 4 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import unicodedata

import asyncpg

POLICY_VERSION = "estimate-editorial-pages-v1"


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


CANDIDATES = """
SELECT candidate.identity_id,
       candidate.onet_soc_code,
       candidate.canonical_title,
       candidate.seo_slug,
       candidate.title_source,
       candidate.slug_source,
       candidate.soc_major_group,
       candidate.source_soc_major_group_title,
       candidate.jobsvsai_job_family,
       candidate.source_summary,
       candidate.source_attribution,
       candidate.search_aliases,
       estimate.estimate_method,
       estimate.estimate_confidence,
       existing.id    AS existing_occupation_id,
       existing.title AS existing_title,
       existing.slug  AS existing_slug
FROM public_occupation_content_candidates candidate
JOIN current_published_occupation_estimates estimate
  ON estimate.identity_id = candidate.identity_id
JOIN canonical_occupation_identities identity ON identity.id = candidate.identity_id
LEFT JOIN occupations existing ON existing.id = identity.jobs_vs_ai_occupation_id
WHERE candidate.content_run_id = $1
ORDER BY candidate.onet_soc_code
"""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-run", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(dsn)
    try:
        async with connection.transaction():
            candidates = await connection.fetch(CANDIDATES, args.content_run)
            if not candidates:
                raise SystemExit(f"No published estimates found for content run {args.content_run}.")

            # A page for an occupation that also holds a verified score would give one
            # occupation two sources of truth. The database refuses to publish such an
            # estimate at all, so this should be unreachable — checked anyway, because an
            # invariant worth enforcing is worth confirming at the point of use.
            conflicted = await connection.fetchval("""
              SELECT count(*) FROM current_published_occupation_estimates estimate
              WHERE EXISTS (SELECT 1 FROM current_production_occupation_scores score
                            WHERE score.identity_id = estimate.identity_id)
            """)
            if conflicted:
                raise SystemExit(f"{conflicted} published estimates shadow a verified score.")

            existing_categories = {
                row["name"]: row["id"]
                for row in await connection.fetch("SELECT id,name FROM occupation_categories")
            }
            families = sorted({row["jobsvsai_job_family"] for row in candidates})
            category_ids: dict[str, int] = {}
            created_categories: list[str] = []
            for family in families:
                if family in existing_categories:
                    category_ids[family] = existing_categories[family]
                    continue
                created_categories.append(family)
                category_ids[family] = -1 if args.dry_run else await connection.fetchval(
                    "INSERT INTO occupation_categories (name,slug) VALUES ($1,$2) RETURNING id",
                    family, slugify(family))

            # occupations.slug is globally unique. A slug already held by a *different* page
            # is a real collision and must stop the run rather than silently rename.
            taken = {
                row["slug"]: row["id"]
                for row in await connection.fetch("SELECT id,slug FROM occupations")
            }
            collisions = [
                {"occupationCode": row["onet_soc_code"], "slug": row["seo_slug"],
                 "heldBy": taken[row["seo_slug"]]}
                for row in candidates
                if row["seo_slug"] in taken
                and taken[row["seo_slug"]] != row["existing_occupation_id"]
            ]
            if collisions:
                raise SystemExit(f"Slug collisions with existing pages: {collisions[:10]}")

            source_id = await connection.fetchval(
                "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 5 bounded corpus scoring'")

            created = updated = linked = 0
            for row in candidates:
                # An editorial decision already taken is not revisited: an existing page keeps
                # its title and slug, and only gains the imported summary and aliases.
                title = row["existing_title"] or row["canonical_title"]
                slug = row["existing_slug"] or row["seo_slug"]
                metadata = {
                    "policyVersion": POLICY_VERSION,
                    "scoreStatus": "estimated",
                    "estimateMethod": row["estimate_method"],
                    "estimateConfidence": row["estimate_confidence"],
                    "contentRunId": args.content_run,
                    "onetSocCode": row["onet_soc_code"],
                    "socMajorGroup": row["soc_major_group"],
                    "sourceSocMajorGroupTitle": row["source_soc_major_group_title"],
                    "jobsvsaiJobFamily": row["jobsvsai_job_family"],
                    "sourceAttribution": row["source_attribution"],
                    "titleSource": "existing_editorial" if row["existing_title"] else row["title_source"],
                    "slugSource": "existing_editorial" if row["existing_slug"] else row["slug_source"],
                    "verdictOmitted": "no promoted snapshot; page renders the estimate panel",
                }

                if args.dry_run:
                    created += 0 if row["existing_occupation_id"] else 1
                    updated += 1 if row["existing_occupation_id"] else 0
                    continue

                if row["existing_occupation_id"]:
                    await connection.execute("""
                      UPDATE occupations
                         SET summary=$2, search_aliases=$3, category_id=$4, external_code=$5,
                             source_id=$6, source_metadata=$7, is_active=true, updated_at=now()
                       WHERE id=$1
                    """, row["existing_occupation_id"], row["source_summary"],
                         row["search_aliases"], category_ids[row["jobsvsai_job_family"]],
                         row["onet_soc_code"], source_id, json.dumps(metadata))
                    occupation_id = row["existing_occupation_id"]
                    updated += 1
                else:
                    occupation_id = await connection.fetchval("""
                      INSERT INTO occupations (
                        external_code, slug, title, category_id, summary, verdict,
                        search_aliases, is_active, source_id, source_metadata)
                      VALUES ($1,$2,$3,$4,$5,'',$6,true,$7,$8) RETURNING id
                    """, row["onet_soc_code"], slug, title,
                         category_ids[row["jobsvsai_job_family"]], row["source_summary"],
                         row["search_aliases"], source_id, json.dumps(metadata))
                    created += 1

                result = await connection.execute("""
                  UPDATE canonical_occupation_identities SET jobs_vs_ai_occupation_id=$2
                   WHERE id=$1 AND jobs_vs_ai_occupation_id IS DISTINCT FROM $2
                """, row["identity_id"], occupation_id)
                if result.endswith("1"):
                    linked += 1

            print(json.dumps({
                "policyVersion": POLICY_VERSION,
                "contentRunId": args.content_run,
                "candidates": len(candidates),
                "pagesCreated": created,
                "pagesUpdated": updated,
                "identitiesLinked": linked,
                "categoriesCreated": created_categories,
                "publicationsTouched": 0,
                "aiCalls": 0,
                "persisted": not args.dry_run,
            }, indent=2))

            if args.dry_run:
                raise SystemExit(0)
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
