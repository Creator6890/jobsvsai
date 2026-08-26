"""Public search response contract.

Deliberately narrow. A staged occupation may be *named* here, because telling someone "we do
not analyse that yet" is more useful than substituting something unrelated — but naming is all
it gets. No score, no slug, no snapshot, no triage finding and no block reason crosses this
boundary, so the payload cannot leak an unapproved number or an internal review diagnostic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.occupation import Occupation


def _camel(value: str) -> str:
    head, *rest = value.split("_")
    return head + "".join(part.capitalize() for part in rest)


class _Base(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class RelatedPublicOccupation(_Base):
    """A published occupation offered alongside an unavailable one, explicitly secondary.

    Carries a title and a slug and nothing else: it is a navigation option, not a claim that
    it resembles what the user asked for.
    """

    slug: str
    title: str


class AmbiguousChoice(_Base):
    """One interpretation of an ambiguous query.

    `available` is the only publication signal that crosses this boundary: whether we can show
    an analysis. The internal lifecycle words — staged, review_required — never do, and an
    unavailable choice carries no slug because there is no page to link to.
    """

    title: str
    available: bool
    slug: str | None = None


class SearchResponse(_Base):
    """One of three outcomes.

    `public_matches`            results carry full published occupations
    `occupation_not_available`  we understood the query; the occupation is not published
    `no_reliable_match`         nothing cleared the relevance floor, and we say so
    """

    query_status: str
    results: list[Occupation] = Field(default_factory=list)

    # What the user typed, as matched. Lets the UI say "Penetration Tester" while the
    # occupation underneath remains Information Security Analysts.
    matched_title: str | None = None
    canonical_title: str | None = None

    # Present only for `occupation_not_available`, and only ever the coarse lifecycle state.
    # Never a triage finding, coverage figure or blocking code.
    publication_status: str | None = None

    # True when a broad term legitimately spans several occupations, so the UI offers a
    # chooser instead of implying a single answer.
    is_disambiguation: bool = False

    related_public_results: list[RelatedPublicOccupation] = Field(default_factory=list)

    # Populated for `ambiguous`. May mix available and unavailable occupations: an
    # equally-supported unpublished interpretation is still one of the things the query could
    # have meant, and dropping it would silently pick the published one.
    choices: list[AmbiguousChoice] = Field(default_factory=list)
