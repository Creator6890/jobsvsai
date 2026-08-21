from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.production_scores import (
    FACTOR_LATERAL,
    PRODUCTION_SCORE_COLUMNS,
    PRODUCTION_SCORE_JOIN,
    production_replacement_risk_scalar,
)
from app.repositories.publication import public_occupation_predicate
from app.schemas.occupation import CareerRelationship, Occupation, TaskImpact

# Public occupation reads compose from two shared fragments and nothing else:
#   * production_scores.py decides which score is current
#   * publication.py decides whether the occupation may be seen at all
# BASE_SELECT already carries the publication gate in its WHERE clause, so callers extend
# it with AND, never with a fresh WHERE.
BASE_SELECT = (
    """
SELECT o.id, o.slug, o.title, c.name AS category, o.summary, o.verdict,
"""
    + PRODUCTION_SCORE_COLUMNS
    + PRODUCTION_SCORE_JOIN
    + FACTOR_LATERAL
    + "WHERE "
    + public_occupation_predicate("o")
    + "\n"
)


async def list_occupations(session: AsyncSession, limit: int = 100, offset: int = 0) -> list[Occupation]:
    rows = (await session.execute(text(BASE_SELECT + " ORDER BY o.title, o.id LIMIT :limit OFFSET :offset"), {"limit": limit, "offset": offset})).mappings().all()
    return [await _hydrate(session, row) for row in rows]


async def get_occupation(session: AsyncSession, slug: str) -> Occupation | None:
    row = (await session.execute(text(BASE_SELECT + " AND o.slug = :slug"), {"slug": slug})).mappings().first()
    return await _hydrate(session, row) if row else None


async def search_occupations(session: AsyncSession, query: str, limit: int = 10) -> list[Occupation]:
    tokens = [token for token in query.lower().split() if token]
    search_text = "lower(o.title || ' ' || o.search_aliases)"
    where = " AND ".join(f"{search_text} LIKE :token_{index}" for index in range(len(tokens))) or "true"
    params = {f"token_{index}": f"%{token}%" for index, token in enumerate(tokens)} | {"query": query, "limit": limit}
    sql = BASE_SELECT + f" AND (({where}) OR similarity({search_text}, lower(:query)) > 0.18) ORDER BY similarity({search_text}, lower(:query)) DESC, o.title LIMIT :limit"
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [await _hydrate(session, row) for row in rows]


async def _hydrate(session: AsyncSession, row: object) -> Occupation:
    data = dict(row)
    occupation_id = data.pop("id")
    snapshot_id = data.pop("snapshot_id")

    # Task evidence comes from the promoted derivation, keyed on O*NET task identity.
    # The legacy `occupation_tasks` / `task_ai_scores` pair is no longer consulted here.
    task_rows = (await session.execute(text("""
        SELECT contribution.onet_task_id,
               contribution.task_statement,
               CASE
                 WHEN contribution.source_importance >= 75 THEN 'High'
                 WHEN contribution.source_importance >= 45 THEN 'Medium'
                 ELSE 'Low'
               END AS importance,
               round(contribution.task_ai_exposure)::int AS exposure,
               round(contribution.automation_feasibility)::int AS automation_feasibility,
               round(contribution.augmentation_potential)::int AS augmentation_potential
        FROM production_score_task_contributions contribution
        WHERE contribution.snapshot_id = :snapshot_id
        ORDER BY contribution.exposure_contribution DESC, contribution.onet_task_id
    """), {"snapshot_id": snapshot_id})).mappings().all()

    # Related occupations come from O*NET's own related-occupations data, staged by the
    # public content pipeline for the latest content run. They are *related*, not "safer" —
    # O*NET publishes a relatedness tier and rank and nothing about transition difficulty,
    # skill overlap or retraining time, so this reader exposes only what the source supports.
    #
    # Links out of a public page, so each target must independently clear the publication
    # gate and carry a current production score. A related occupation that is not itself
    # launchable is omitted rather than linked to a page that does not exist.
    relation_rows = (await session.execute(text("""
        SELECT target.slug, target.title,
               """ + production_replacement_risk_scalar("target") + """ AS replacement_risk,
               related.relatedness_tier, related.relatedness_rank
        FROM public_occupation_related_occupations related
        -- The newest staged relations *for this occupation*, not the newest content run
        -- overall: regenerating content for a subset must not blank out the relations of
        -- occupations that subset did not include.
        JOIN LATERAL (
          SELECT max(newer.content_run_id) AS content_run_id
          FROM public_occupation_related_occupations newer
          WHERE newer.identity_id = related.identity_id
        ) latest_run ON latest_run.content_run_id = related.content_run_id
        JOIN canonical_occupation_identities source_identity
          ON source_identity.id = related.identity_id
        JOIN canonical_occupation_identities target_identity
          ON target_identity.id = related.related_identity_id
        JOIN occupations target ON target.id = target_identity.jobs_vs_ai_occupation_id
        WHERE source_identity.jobs_vs_ai_occupation_id = :occupation_id
          AND """ + public_occupation_predicate("target") + """
          AND """ + production_replacement_risk_scalar("target") + """ IS NOT NULL
        ORDER BY related.relatedness_rank, target.title LIMIT 6
    """), {"occupation_id": occupation_id})).mappings().all()

    data["tasks"] = [
        TaskImpact(
            onet_task_id=item["onet_task_id"],
            name=item["task_statement"],
            importance=item["importance"],
            exposure=item["exposure"],
            automation_feasibility=item["automation_feasibility"],
            augmentation_potential=item["augmentation_potential"],
        )
        for item in task_rows
    ]
    # "Hardest to automate" replaces the legacy hand-curated `is_resilient` flag. It uses
    # Automation Feasibility for exactly what that metric means, rather than inventing a
    # new resilience claim the methodology has not validated.
    data["hardest_to_automate_tasks"] = [
        item["task_statement"]
        for item in sorted(task_rows, key=lambda entry: entry["automation_feasibility"])[:5]
    ]
    data["related_careers"] = [CareerRelationship(**item) for item in relation_rows]
    return Occupation(**data)
