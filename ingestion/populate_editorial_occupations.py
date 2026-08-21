"""Create the editorial `occupations` rows for the launch cohort from completed content.

Runs only after a post-promotion content run has produced complete candidates. Every field
written here comes from that run — no shells, no placeholder verdicts, no invented facts.

What it writes, per cohort occupation:

  occupations                          the editorial page row (title, slug, summary,
                                       verdict, aliases, category, external code)
  canonical_occupation_identities      jobs_vs_ai_occupation_id, linking identity to page
  occupation_publications              approved_score_snapshot_id, binding the page to the
                                       exact promoted snapshot its verdict describes

What it deliberately does not touch:

  occupation_publications.activation_status   activation is a separate, approved step
  existing editorial titles and slugs         a decision already taken is not revisited

Categories: the content policy derives a JobsVsAI job family from the SOC major group. The
legacy `occupation_categories` rows predate that taxonomy and cover only seven families, so
this script reuses a category whose name matches the family exactly and creates the rest.
Cohort rows are assigned their SOC-derived family so the launch is internally consistent;
rows outside the cohort keep whatever category they already had.

  docker compose run --rm -e PYTHONPATH=/app/ingestion backend \
      python /app/ingestion/populate_editorial_occupations.py --content-run 2 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import unicodedata
from typing import Any

import asyncpg

EDITORIAL_POLICY_VERSION = "phase6-editorial-population-v1"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


async def run(content_run_id: int, dry_run: bool) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        content_run = await connection.fetchrow(
            "SELECT * FROM public_occupation_content_runs WHERE id=$1", content_run_id)
        if content_run is None:
            raise SystemExit(f"No content run {content_run_id}.")

        candidates = await connection.fetch("""
          SELECT candidate.*, identity.jobs_vs_ai_occupation_id AS existing_occupation_id,
                 existing.slug AS existing_slug, existing.title AS existing_title,
                 existing.category_id AS existing_category_id
          FROM public_occupation_content_candidates candidate
          JOIN canonical_occupation_identities identity ON identity.id = candidate.identity_id
          LEFT JOIN occupations existing ON existing.id = identity.jobs_vs_ai_occupation_id
          WHERE candidate.content_run_id = $1
          ORDER BY candidate.onet_soc_code
        """, content_run_id)
        if not candidates:
            raise SystemExit("Content run has no candidates.")

        incomplete = [row for row in candidates if row["content_completeness"] != "complete"]
        if incomplete:
            raise SystemExit(
                f"{len(incomplete)} candidates are incomplete. Editorial rows are created from "
                "completed content only; re-run the content pipeline first."
            )
        # Every verdict must describe a snapshot that is currently live, or the page would
        # publish a number the store no longer serves.
        stale = await connection.fetchval("""
          SELECT count(*) FROM public_occupation_content_candidates candidate
          WHERE candidate.content_run_id = $1
            AND NOT EXISTS (SELECT 1 FROM current_production_occupation_scores score
                            WHERE score.id = candidate.verdict_snapshot_id)
        """, content_run_id)
        if stale:
            raise SystemExit(f"{stale} candidates reference a snapshot that is not current.")

        source_id = await connection.fetchval(
            "SELECT id FROM data_sources WHERE name='JobsVsAI Phase 5 bounded corpus scoring'")

        # --- categories -------------------------------------------------------
        existing_categories = {
            row["name"]: row["id"]
            for row in await connection.fetch("SELECT id,name FROM occupation_categories")
        }
        families = sorted({row["jobsvsai_job_family"] for row in candidates})
        created_categories: list[str] = []
        category_ids: dict[str, int] = {}
        for family in families:
            if family in existing_categories:
                category_ids[family] = existing_categories[family]
                continue
            created_categories.append(family)
            if dry_run:
                category_ids[family] = -1
                continue
            category_ids[family] = await connection.fetchval(
                "INSERT INTO occupation_categories (name,slug) VALUES ($1,$2) RETURNING id",
                family, slugify(family))

        # --- slug safety ------------------------------------------------------
        # occupations.slug is globally unique. A cohort slug may already belong to a page
        # outside the cohort; that is a genuine collision and must stop the run.
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

        created = updated = publications_bound = identities_linked = 0
        for row in candidates:
            title = row["existing_title"] or row["canonical_title"]
            slug = row["existing_slug"] or row["seo_slug"]
            category_id = category_ids[row["jobsvsai_job_family"]]
            metadata = {
                "policyVersion": EDITORIAL_POLICY_VERSION,
                "contentRunId": content_run_id,
                "contentRunKey": content_run["run_key"],
                "contentPolicyVersion": content_run["content_policy_version"],
                "verdictTemplateVersion": content_run["verdict_template_version"],
                "onetSocCode": row["onet_soc_code"],
                "socMajorGroup": row["soc_major_group"],
                "sourceSocMajorGroupTitle": row["source_soc_major_group_title"],
                "jobsvsaiJobFamily": row["jobsvsai_job_family"],
                "sourceAttribution": row["source_attribution"],
                "verdictSnapshotId": row["verdict_snapshot_id"],
                "titleSource": "existing_editorial" if row["existing_title"] else row["title_source"],
                "slugSource": "existing_editorial" if row["existing_slug"] else row["slug_source"],
            }
            if dry_run:
                if row["existing_occupation_id"]:
                    updated += 1
                else:
                    created += 1
                continue

            if row["existing_occupation_id"]:
                await connection.execute("""
                  UPDATE occupations
                     SET title=$2, summary=$3, verdict=$4, search_aliases=$5, category_id=$6,
                         external_code=$7, source_id=$8, source_metadata=$9, is_active=true,
                         updated_at=now()
                   WHERE id=$1
                """, row["existing_occupation_id"], title, row["source_summary"],
                     row["jobsvsai_verdict"], row["search_aliases"], category_id,
                     row["onet_soc_code"], source_id, json.dumps(metadata))
                occupation_id = row["existing_occupation_id"]
                updated += 1
            else:
                occupation_id = await connection.fetchval("""
                  INSERT INTO occupations (
                    external_code, slug, title, category_id, summary, verdict,
                    search_aliases, is_active, source_id, source_metadata)
                  VALUES ($1,$2,$3,$4,$5,$6,$7,true,$8,$9) RETURNING id
                """, row["onet_soc_code"], slug, title, category_id, row["source_summary"],
                     row["jobsvsai_verdict"], row["search_aliases"], source_id,
                     json.dumps(metadata))
                created += 1

            linked = await connection.execute("""
              UPDATE canonical_occupation_identities SET jobs_vs_ai_occupation_id=$2
               WHERE id=$1 AND jobs_vs_ai_occupation_id IS DISTINCT FROM $2
            """, row["identity_id"], occupation_id)
            if linked.endswith("1"):
                identities_linked += 1

            # Bind the page to the exact snapshot its verdict describes. Activation status
            # is untouched.
            bound = await connection.execute("""
              UPDATE occupation_publications SET approved_score_snapshot_id=$2, updated_at=now()
               WHERE identity_id=$1 AND locale='en' AND source_geography='US'
                 AND approved_score_snapshot_id IS DISTINCT FROM $2
            """, row["identity_id"], row["verdict_snapshot_id"])
            if bound.endswith("1"):
                publications_bound += 1

        summary = {
            "policyVersion": EDITORIAL_POLICY_VERSION,
            "contentRunId": content_run_id,
            "candidates": len(candidates),
            "categoriesReused": sorted(set(families) & set(existing_categories)),
            "categoriesCreated": created_categories,
            "occupationsCreated": created,
            "occupationsUpdated": updated,
            "identitiesLinked": identities_linked,
            "publicationsBoundToSnapshot": publications_bound,
            "slugCollisions": 0,
            "activationsChanged": 0,
            "persisted": not dry_run,
        }
        if dry_run:
            await transaction.rollback()
            return summary

        public_rows = await connection.fetchval(
            "SELECT count(*) FROM occupation_publications WHERE activation_status='public'")
        if public_rows:
            raise ValueError(
                f"{public_rows} publications are public; editorial population must not activate.")
        await transaction.commit()
        return summary
    except Exception:
        if not transaction._managed:  # pragma: no cover - defensive
            pass
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(await run(args.content_run, args.dry_run), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
