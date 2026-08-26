from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
# Aliased: the legacy endpoint function below is also called `occupation_search`, and a
# bare import would be shadowed by it at module scope.
from app.repositories import occupation_search as search_repo
from app.repositories.occupations import (
    get_occupation,
    hydrate_by_ids,
    list_occupations,
    search_occupations,
)
from app.schemas.occupation import Occupation
from app.schemas.search import (
    AmbiguousChoice,
    RelatedPublicOccupation,
    SearchResponse,
)

router = APIRouter(prefix="/occupations", tags=["occupations"])


@router.get("", response_model=list[Occupation], response_model_by_alias=True)
async def occupations(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), session: AsyncSession = Depends(get_session)) -> list[Occupation]:
    return await list_occupations(session, limit, offset)


@router.get("/search", response_model=list[Occupation], response_model_by_alias=True)
async def occupation_search(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(10, ge=1, le=25),
    session: AsyncSession = Depends(get_session),
) -> list[Occupation]:
    """Published occupations matching the query.

    Kept returning a bare list so existing clients are unaffected. It now ranks through
    Search V2, so the results improve while the shape does not; a client that needs to tell
    "no such occupation" from "we do not publish it yet" calls `/search/resolve` instead.
    """
    return await search_occupations(session, q, limit)


@router.get("/search/resolve", response_model=SearchResponse,
            response_model_by_alias=True)
async def occupation_search_resolve(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(10, ge=1, le=25),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Search with the outcome made explicit.

    Three outcomes, because collapsing them loses the distinction that matters: a query we
    could not understand and a query naming an occupation we have not published are different
    answers, and substituting an unrelated occupation for either is the failure this endpoint
    exists to stop.
    """
    resolution = await search_repo.resolve(session, q, limit)

    # `ambiguous` carries published occupations too — several occupations share the matched
    # term with equally strong evidence, so the UI offers a choice instead of a ranking.
    if resolution.status in ("public_matches", "ambiguous"):
        occupations = await hydrate_by_ids(
            session, [m.occupation_id for m in resolution.public if m.occupation_id]
        )
        # An ambiguous query may legitimately include an interpretation we cannot show. It is
        # listed as unavailable rather than dropped, because dropping it would silently
        # resolve the ambiguity in favour of whatever happens to be published.
        choices = [
            AmbiguousChoice(title=m.canonical_title, available=True, slug=m.slug)
            for m in resolution.public
        ] + [
            AmbiguousChoice(title=m.canonical_title, available=False)
            for m in resolution.non_public
        ] if resolution.status == "ambiguous" else []

        return SearchResponse(
            query_status=resolution.status,
            results=occupations,
            matched_title=resolution.matched_term,
            canonical_title=resolution.canonical_title,
            publication_status="public",
            is_disambiguation=resolution.is_disambiguation,
            choices=choices,
        )

    if resolution.status == "occupation_not_available":
        unavailable = resolution.non_public[0]
        related = await search_repo.related_public(session, unavailable.identity_id)
        return SearchResponse(
            query_status="occupation_not_available",
            matched_title=resolution.matched_term,
            canonical_title=resolution.canonical_title,
            # The coarse lifecycle state only. Never a coverage figure or blocking code.
            publication_status=resolution.publication_status,
            related_public_results=[RelatedPublicOccupation(**r) for r in related],
        )

    return SearchResponse(query_status="no_reliable_match")


@router.get("/{slug}", response_model=Occupation, response_model_by_alias=True)
async def occupation_detail(slug: str, session: AsyncSession = Depends(get_session)) -> Occupation:
    result = await get_occupation(session, slug)
    if not result:
        raise HTTPException(status_code=404, detail="Occupation not found")
    return result
