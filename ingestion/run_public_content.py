"""Generate staged public occupation content for an approved cohort.

Reads O*NET source facts and promoted score snapshots; writes only to the
public_occupation_content_* tables from migration 028. It does not touch the editorial
`occupations` table, does not publish, and does not activate anything.

  docker compose run --rm worker python -m ingestion.run_public_content \
      --run-version phase6-content-2026q3-v1 --triage-run 1

Without --triage-run every identity that has a current production snapshot is processed.
With it, only the launch-eligible cohort from that triage run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from decimal import Decimal
from typing import Any

import asyncpg

try:
    from .public_content_policy import CONTENT_POLICY_VERSION, VERDICT_TEMPLATE_VERSION, build_content
except ImportError:  # Direct script execution.
    from public_content_policy import CONTENT_POLICY_VERSION, VERDICT_TEMPLATE_VERSION, build_content

CONSTRAINT_KEYS = (
    "physical-presence", "environment-variability", "accountability",
    "consequence-severity", "human-dependency", "regulation",
)


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai"
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def plain(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


async def load_targets(
    connection: asyncpg.Connection, triage_run_id: int | None
) -> list[asyncpg.Record]:
    """Identities to generate content for, with their O*NET facts and current snapshot."""
    cohort_filter = ""
    params: list[Any] = []
    if triage_run_id is not None:
        cohort_filter = """
          AND identity.current_source_code IN (
            SELECT result.occupation_code FROM phase6_launch_triage_results result
            WHERE result.triage_run_id = $1 AND result.launch_eligible
          )
        """
        params.append(triage_run_id)

    return await connection.fetch(f"""
      SELECT identity.id AS identity_id,
             identity.current_source_code AS onet_soc_code,
             onet.title AS onet_title,
             onet.description AS onet_description,
             score.id AS snapshot_id,
             score.ai_exposure,
             score.replacement_risk,
             score.exact_inputs,
             occupation.title AS editorial_title,
             occupation.slug AS editorial_slug,
             publication.canonical_public_title,
             (SELECT coalesce(array_agg(alternate.job_title ORDER BY alternate.job_title), '{{}}')
                FROM onet_alternate_titles alternate
               WHERE alternate.occupation_code = identity.current_source_code
                 AND alternate.is_current) AS alternate_titles
      FROM canonical_occupation_identities identity
      JOIN onet_occupations onet
        ON onet.onet_soc_code = identity.current_source_code AND onet.is_current
      LEFT JOIN current_production_occupation_scores score ON score.identity_id = identity.id
      LEFT JOIN occupations occupation ON occupation.id = identity.jobs_vs_ai_occupation_id
      LEFT JOIN occupation_publications publication
             ON publication.identity_id = identity.id
            AND publication.locale = 'en' AND publication.source_geography = 'US'
      WHERE identity.current_source_code IS NOT NULL
      {cohort_filter}
      ORDER BY identity.current_source_code
    """, *params)


async def structural_constraints(
    connection: asyncpg.Connection, snapshot_id: int | None
) -> dict[str, float]:
    """Constraint levels for the verdict, read from the promoted snapshot's exact inputs."""
    if snapshot_id is None:
        return {}
    row = await connection.fetchrow(
        "SELECT exact_inputs FROM production_occupation_score_snapshots WHERE id = $1", snapshot_id)
    if row is None:
        return {}
    payload = row["exact_inputs"]
    payload = json.loads(payload) if isinstance(payload, str) else payload
    values = (payload or {}).get("structuralProxyValues") or (payload or {}).get("values") or {}
    return {key: float(values[key]) for key in CONSTRAINT_KEYS if key in values}


async def provisional_factors(
    connection: asyncpg.Connection, snapshot_id: int | None
) -> list[dict[str, Any]]:
    """The provisional factor rows behind one snapshot's Replacement Risk.

    Read from the promoted snapshot rather than from a constant, so the disclosure a page
    carries is the disclosure that snapshot's own arithmetic warrants.
    """
    if snapshot_id is None:
        return []
    rows = await connection.fetch("""
      SELECT factor_key, weight, proxy_model_version
      FROM production_score_factor_contributions
      WHERE snapshot_id = $1 AND is_provisional_proxy
      ORDER BY weight DESC, factor_key
    """, snapshot_id)
    return [{
        "factorKey": row["factor_key"],
        "weight": plain(row["weight"]),
        "proxyModelVersion": row["proxy_model_version"],
    } for row in rows]


async def run(run_version: str, triage_run_id: int | None, dry_run: bool) -> dict[str, Any]:
    connection = await asyncpg.connect(database_url())
    try:
        targets = await load_targets(connection, triage_run_id)
        if not targets:
            raise SystemExit(
                "No identities to process. Check that the O*NET import has run and, if a "
                "triage run was named, that it has launch-eligible results."
            )

        generated: list[dict[str, Any]] = []
        seen_slugs: dict[str, str] = {}
        slug_collisions: list[dict[str, str]] = []
        for target in targets:
            snapshot = None
            if target["snapshot_id"] is not None:
                snapshot = {
                    "snapshotId": target["snapshot_id"],
                    "aiExposure": plain(target["ai_exposure"]),
                    "replacementRisk": plain(target["replacement_risk"]),
                    "structuralConstraints": await structural_constraints(
                        connection, target["snapshot_id"]),
                    "provisionalFactors": await provisional_factors(
                        connection, target["snapshot_id"]),
                }
            override = {
                "title": target["editorial_title"] or target["canonical_public_title"],
                "slug": target["editorial_slug"],
            }
            content = build_content(
                identity={"identityId": target["identity_id"]},
                onet={
                    "onetSocCode": target["onet_soc_code"],
                    "title": target["onet_title"],
                    "description": target["onet_description"],
                },
                snapshot=snapshot,
                alternate_titles=list(target["alternate_titles"] or []),
                editorial_override={key: value for key, value in override.items() if value},
            )
            # Slugs are the public URL. A collision is a content defect, not something to
            # paper over with a numeric suffix that would silently outlive this run.
            if content["seoSlug"] in seen_slugs:
                slug_collisions.append({
                    "slug": content["seoSlug"],
                    "first": seen_slugs[content["seoSlug"]],
                    "second": content["onetSocCode"],
                })
            seen_slugs[content["seoSlug"]] = content["onetSocCode"]
            generated.append(content)

        if slug_collisions:
            raise SystemExit(
                "Slug collisions detected; resolve them editorially before generating content:\n"
                + json.dumps(slug_collisions, indent=2)
            )

        complete = [item for item in generated if item["contentCompleteness"] == "complete"]
        incomplete = [item for item in generated if item["contentCompleteness"] == "incomplete"]
        missing_counts: dict[str, int] = {}
        for item in incomplete:
            for field in item["missingFields"]:
                missing_counts[field] = missing_counts.get(field, 0) + 1

        summary = {
            "contentPolicyVersion": CONTENT_POLICY_VERSION,
            "verdictTemplateVersion": VERDICT_TEMPLATE_VERSION,
            "triageRunId": triage_run_id,
            "occupationsProcessed": len(generated),
            "complete": len(complete),
            "incomplete": len(incomplete),
            "missingFieldCounts": missing_counts,
            "jobFamilies": sorted({item["jobsvsaiJobFamily"] for item in generated}),
        }

        if dry_run:
            summary["persisted"] = False
            summary["sample"] = generated[:3]
            return summary

        transaction = connection.transaction()
        await transaction.start()
        try:
            source_id = await connection.fetchval("SELECT id FROM data_sources ORDER BY id LIMIT 1")
            onet_version = await connection.fetchval(
                "SELECT source_version FROM onet_occupations WHERE is_current LIMIT 1")
            content_run_id = await connection.fetchval("""
              INSERT INTO public_occupation_content_runs (
                run_key, content_policy_version, verdict_template_version, triage_run_id,
                onet_source_version, occupation_count, complete_count, incomplete_count,
                input_hash, source_id, provenance, created_by)
              VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
              RETURNING id
            """, run_version, CONTENT_POLICY_VERSION, VERDICT_TEMPLATE_VERSION, triage_run_id,
                 onet_version or "unknown", len(generated), len(complete), len(incomplete),
                 canonical_hash(summary), source_id,
                 json.dumps({"aiCalls": 0, "factsCopiedVerbatim": True}), "system:phase6-content")

            for item in generated:
                await connection.execute("""
                  INSERT INTO public_occupation_content_candidates (
                    content_run_id, identity_id, onet_soc_code, canonical_title, title_source,
                    seo_slug, slug_source, soc_major_group, source_soc_major_group_title,
                    jobsvsai_job_family, source_summary, source_summary_origin, source_attribution,
                    jobsvsai_verdict, verdict_snapshot_id, verdict_inputs, search_aliases,
                    alternate_title_count, content_completeness, missing_fields, input_hash, provenance)
                  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,
                          $20::jsonb,$21,$22::jsonb)
                """, content_run_id, item["identityId"], item["onetSocCode"],
                     item["canonicalTitle"], item["titleSource"], item["seoSlug"], item["slugSource"],
                     item["socMajorGroup"], item["sourceSocMajorGroupTitle"], item["jobsvsaiJobFamily"],
                     item["sourceSummary"], item["sourceSummaryOrigin"], item["sourceAttribution"],
                     item["jobsvsaiVerdict"], item["verdictSnapshotId"], json.dumps(item["verdictInputs"]),
                     item["searchAliases"], item["alternateTitleCount"], item["contentCompleteness"],
                     json.dumps(item["missingFields"]), canonical_hash(item),
                     json.dumps({"policy": CONTENT_POLICY_VERSION}))

            # Adjacency from O*NET, not from the hand-seeded career_relationships graph.
            related = await connection.execute("""
              INSERT INTO public_occupation_related_occupations (
                content_run_id, identity_id, related_identity_id, related_onet_soc_code,
                relatedness_tier, relatedness_rank)
              SELECT $1, source_identity.id, target_identity.id,
                     related.related_occupation_code, related.relatedness_tier, related.relatedness_rank
              FROM onet_related_occupations related
              JOIN canonical_occupation_identities source_identity
                ON source_identity.current_source_code = related.occupation_code
              JOIN canonical_occupation_identities target_identity
                ON target_identity.current_source_code = related.related_occupation_code
              WHERE related.is_current
                AND source_identity.id <> target_identity.id
                AND source_identity.id IN (
                  SELECT identity_id FROM public_occupation_content_candidates
                  WHERE content_run_id = $1)
                AND target_identity.id IN (
                  SELECT identity_id FROM public_occupation_content_candidates
                  WHERE content_run_id = $1)
              ON CONFLICT DO NOTHING
            """, content_run_id)
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise

        summary["persisted"] = True
        summary["contentRunId"] = content_run_id
        summary["relatedOccupationRows"] = related
        return summary
    finally:
        await connection.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", required=True)
    parser.add_argument("--triage-run", type=int, default=None,
                        help="Restrict to the launch-eligible cohort of this triage run.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(await run(args.run_version, args.triage_run, args.dry_run), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
