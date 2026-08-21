from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.occupations import get_occupation, list_occupations, search_occupations
from app.schemas.occupation import Occupation

router = APIRouter(prefix="/occupations", tags=["occupations"])


@router.get("", response_model=list[Occupation], response_model_by_alias=True)
async def occupations(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), session: AsyncSession = Depends(get_session)) -> list[Occupation]:
    return await list_occupations(session, limit, offset)


@router.get("/search", response_model=list[Occupation], response_model_by_alias=True)
async def occupation_search(q: str = Query(min_length=2, max_length=120), limit: int = Query(10, ge=1, le=25), session: AsyncSession = Depends(get_session)) -> list[Occupation]:
    return await search_occupations(session, q, limit)


@router.get("/{slug}", response_model=Occupation, response_model_by_alias=True)
async def occupation_detail(slug: str, session: AsyncSession = Depends(get_session)) -> Occupation:
    result = await get_occupation(session, slug)
    if not result:
        raise HTTPException(status_code=404, detail="Occupation not found")
    return result
