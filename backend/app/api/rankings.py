from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.production_scores import PRODUCTION_SCORE_JOIN
from app.repositories.publication import public_occupation_predicate

router = APIRouter(prefix="/rankings", tags=["rankings"])

METRIC_COLUMNS = {"ai_exposure": "score.ai_exposure", "replacement_risk": "score.replacement_risk"}


@router.get("")
async def rankings(metric: str = Query("ai_exposure", pattern="^(ai_exposure|replacement_risk)$"), direction: str = Query("desc", pattern="^(asc|desc)$"), limit: int = Query(100, ge=1, le=1000), session: AsyncSession = Depends(get_session)) -> list[dict[str, object]]:
    order = "ASC" if direction == "asc" else "DESC"
    # Currency comes from current_production_occupation_scores via the shared join, so a
    # ranking can never disagree with the occupation page about which snapshot is live.
    query = text(f"""
      SELECT o.slug, o.title, c.name AS category,
             score.ai_exposure, score.replacement_risk,
             score.confidence, score.weighted_task_coverage
      {PRODUCTION_SCORE_JOIN}
      WHERE {public_occupation_predicate("o")}
      ORDER BY {METRIC_COLUMNS[metric]} {order}, o.title LIMIT :limit
    """)
    return [dict(row) for row in (await session.execute(query, {"limit": limit})).mappings().all()]
