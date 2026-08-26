"""Read layer for published preliminary estimates.

Every read goes through `current_published_occupation_estimates`, mirroring how every
verified read goes through `current_production_occupation_scores`. Divergent bespoke
"latest row" clauses are what previously let readers disagree about which verified score was
live; one store already learned that lesson and the second does not need to learn it again.

There is deliberately no function here that returns a verified and an estimated score in one
shape. A caller that wants both must ask for both and will therefore have both classes in
hand at the point where it decides how to render them — which is exactly where the decision
belongs.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.estimate import EstimatedOccupation

# `verdict` is not selected: an estimated page has none, by design, and selecting a column
# that is always empty invites someone to render it.
_SELECT = """
SELECT o.slug, o.title, c.name AS category, o.summary,
       e.estimate_method, e.estimate_method_detail, e.estimate_confidence,
       e.evidence_coverage, e.supporting_relative_count,
       e.ai_exposure_estimate, e.ai_exposure_low, e.ai_exposure_high,
       e.replacement_risk_estimate, e.replacement_risk_low, e.replacement_risk_high,
       e.evidence_sources
FROM current_published_occupation_estimates e
JOIN canonical_occupation_identities ci ON ci.id = e.identity_id
JOIN occupations o ON o.id = ci.jobs_vs_ai_occupation_id
JOIN occupation_categories c ON c.id = o.category_id
WHERE o.is_active
"""

CONFIDENCE_LABEL = {
    # "Higher-confidence" rather than "High confidence": the latter reads as a stronger
    # version of a verified score, when it is a different kind of claim altogether.
    "higher": "Higher-confidence estimate",
    "moderate": "Moderate-confidence estimate",
    "low": "Low-confidence estimate",
}

# Per-tier, because a single sentence cannot be true of all of them. E1 has *complete* task
# evidence — telling its readers we lack evidence would be simply false, and the estimate
# layer loses its point the moment its own explanations stop being accurate.
DISCLAIMER_BY_METHOD = {
    "E1": (
        "This occupation has complete task-level evidence, but has not yet cleared JobsVsAI's "
        "full validation review. The score below is the same calculation used for verified "
        "occupations and is shown as a preliminary estimate until that review is complete."
    ),
    "E2": (
        "This occupation does not yet have enough validated task-level evidence for a full "
        "JobsVsAI score. The score below is calculated from the task evidence available so "
        "far, which covers only part of the work."
    ),
    "E3": (
        "This occupation does not yet have any validated task-level evidence for a full "
        "JobsVsAI score. The range below is estimated from closely related occupations that "
        "have been fully analysed."
    ),
}


def _to_schema(row) -> EstimatedOccupation:
    sources = row["evidence_sources"] or []
    return EstimatedOccupation(
        slug=row["slug"],
        title=row["title"],
        category=row["category"],
        summary=row["summary"],
        ai_exposure=row["ai_exposure_estimate"],
        ai_exposure_low=row["ai_exposure_low"],
        ai_exposure_high=row["ai_exposure_high"],
        replacement_risk=row["replacement_risk_estimate"],
        replacement_risk_low=row["replacement_risk_low"],
        replacement_risk_high=row["replacement_risk_high"],
        estimate_method=row["estimate_method"],
        estimate_method_detail=row["estimate_method_detail"],
        estimate_confidence=row["estimate_confidence"],
        confidence_label=CONFIDENCE_LABEL[row["estimate_confidence"]],
        evidence_coverage=(
            float(row["evidence_coverage"]) if row["evidence_coverage"] is not None else None
        ),
        supporting_relative_count=row["supporting_relative_count"],
        based_on=[s.get("title", "") for s in sources][:6],
        disclaimer=DISCLAIMER_BY_METHOD[row["estimate_method"]],
    )


async def get_by_slug(session: AsyncSession, slug: str) -> EstimatedOccupation | None:
    row = (await session.execute(
        text(_SELECT + " AND o.slug = :slug"), {"slug": slug})).mappings().first()
    return _to_schema(row) if row else None


async def hydrate_by_slugs(session: AsyncSession, slugs: list[str]) -> list[EstimatedOccupation]:
    """Load published estimates by slug, preserving the order given.

    Order comes from search relevance, not from anything about the estimates themselves.
    """
    if not slugs:
        return []
    rows = (await session.execute(
        text(_SELECT + " AND o.slug = ANY(:slugs)"), {"slugs": slugs})).mappings().all()
    by_slug = {row["slug"]: row for row in rows}
    return [_to_schema(by_slug[s]) for s in slugs if s in by_slug]


async def count_published(session: AsyncSession) -> int:
    return (await session.execute(
        text("SELECT count(*) FROM current_published_occupation_estimates"))).scalar_one()
