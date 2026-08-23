"""Public AI News API. Published articles only."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.news import get_public_article, list_public_articles, list_public_slugs
from app.schemas.news import NewsArticleDetail, NewsArticleSummary, NewsSitemapEntry

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsArticleSummary], response_model_by_alias=True)
async def news_list(
    impact: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[NewsArticleSummary]:
    return await list_public_articles(session, impact, limit, offset)


@router.get("/sitemap", response_model=list[NewsSitemapEntry], response_model_by_alias=True)
async def news_sitemap(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Slugs and dates for sitemap generation. Published only, by construction."""
    return await list_public_slugs(session)


@router.get("/{slug}", response_model=NewsArticleDetail, response_model_by_alias=True)
async def news_detail(slug: str, session: AsyncSession = Depends(get_session)) -> NewsArticleDetail:
    # Draft, review_required and rejected articles are indistinguishable from missing ones
    # here: the repository predicate never returns them, so this 404s for all of them.
    article = await get_public_article(session, slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
