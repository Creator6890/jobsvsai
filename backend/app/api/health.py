from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    return {"status": "ok", "database": "ok", "redis": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
