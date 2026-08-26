"""consumer-search-v2 — term-level occupation search.

Replaces the V1 ranking, which ordered by `similarity(title || ' ' || search_aliases, query)`
over a blob averaging 1,269 characters. Trigram similarity divides shared trigrams by the
union, so that clause ranked an occupation *lower* the more alternate titles it carried. This
module matches individual terms out of `occupation_search_terms` instead.

## Two rules that shape everything here

**Non-public occupations participate in understanding, never in results.** A staged
occupation is indexed so "data scientist" can be recognised, and the reader answers
`occupation_not_available` rather than substituting something unrelated. It never exposes a
score, a slug or a block reason.

**Lexical similarity can never be an answer on its own.** Fuzzy matching is admitted only
above `FUZZY_ADMISSIBLE`, and even then scores below the exact tiers. Below that the honest
answer is `no_reliable_match`. This is what stops "ml engineer" reaching Search Marketing
Strategists and "pen tester" reaching Non-Destructive Testing Specialists — both of which are
the best of a bad field, and both of which are wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.search.normalize import query_forms

POLICY_VERSION = "consumer-search-v2"

QueryStatus = Literal[
    "public_matches", "ambiguous", "occupation_not_available", "no_reliable_match"
]

# Ranking floors. `priority` on the term row supplies the exact tiers (curated alias 1000,
# canonical 950, ambiguous parent 920, alternate/abbreviation 900); the rest are computed.
PREFIX_TIER = 800
# Every query token is a prefix of a term token, in order: "soft eng" -> "software
# engineer". This field is a search-as-you-type box, so partial words are the normal case
# mid-typing, not an edge case.
TOKEN_PREFIX_TIER = 700
TOKEN_TIER = 650
FUZZY_CEILING = 640

# A term must reach this to be an answer at all. Deliberately above FUZZY_CEILING: fuzzy
# alone is never sufficient, only corroborating.
MIN_RELIABLE = 645

# Trigram floor for the fuzzy tier. Calibrated against the 187-query consumer benchmark: the
# wrong answers V1 produced sit below it ("ml engineer" against "petroleum engineers" scores
# well under this), while ordinary typos clear it.
FUZZY_ADMISSIBLE = 0.62

# An exact hit on a curated alias, canonical title or O*NET alternate title. Strong enough to
# assert "this is the occupation you meant", including when the answer is that we do not
# publish it.
STRONG_MATCH = 900

MAX_CANDIDATES = 40


@dataclass
class TermMatch:
    identity_id: int
    occupation_id: int | None
    soc_code: str
    canonical_title: str
    matched_term: str
    term_type: str
    score: float
    activation_status: str
    slug: str | None = None

    @property
    def is_public(self) -> bool:
        return self.activation_status == "public"


@dataclass
class SearchResolution:
    """What the query resolved to, before the API decides how much of it to expose."""

    query: str
    status: QueryStatus
    public: list[TermMatch] = field(default_factory=list)
    non_public: list[TermMatch] = field(default_factory=list)
    matched_term: str | None = None
    canonical_title: str | None = None
    publication_status: str | None = None
    is_disambiguation: bool = False
    # Every candidate the resolver considered, with its tier and score. Not returned publicly;
    # it exists so a relevance defect can be diagnosed from a test rather than guessed at.
    provenance: list[dict[str, Any]] = field(default_factory=list)


# `activation_status` is joined live rather than materialised: promotion changes it, and a
# stale view would route a user to a page that does not exist.
_SELECT = """
  SELECT term.identity_id,
         occ.id            AS occupation_id,
         occ.slug          AS slug,
         identity.current_source_code AS soc_code,
         COALESCE(occ.title, onet.title) AS canonical_title,
         term.term         AS matched_term,
         term.term_type    AS term_type,
         term.priority     AS priority,
         COALESCE(pub.activation_status, 'unpublished') AS activation_status
  FROM occupation_search_terms term
  JOIN canonical_occupation_identities identity ON identity.id = term.identity_id
  LEFT JOIN occupations occ ON occ.id = identity.jobs_vs_ai_occupation_id
  LEFT JOIN onet_occupations onet ON onet.onet_soc_code = identity.current_source_code
  LEFT JOIN occupation_publications pub ON pub.identity_id = identity.id
"""


def _row_to_match(row: Any, score: float) -> TermMatch:
    return TermMatch(
        identity_id=row["identity_id"],
        occupation_id=row["occupation_id"],
        soc_code=row["soc_code"],
        canonical_title=row["canonical_title"] or "",
        matched_term=row["matched_term"],
        term_type=row["term_type"],
        score=score,
        activation_status=row["activation_status"],
        slug=row["slug"],
    )


async def _exact(session: AsyncSession, form: str) -> list[TermMatch]:
    rows = (await session.execute(text(
        _SELECT + " WHERE term.normalized_term = :form ORDER BY term.priority DESC LIMIT :cap"
    ), {"form": form, "cap": MAX_CANDIDATES})).mappings().all()
    return [_row_to_match(r, float(r["priority"])) for r in rows]


async def _prefix(session: AsyncSession, form: str) -> list[TermMatch]:
    """Shorter completions rank higher: "electric" should prefer Electricians to Electrical
    and Electronics Repairers, Commercial and Industrial Equipment."""
    rows = (await session.execute(text(
        _SELECT + """ WHERE term.normalized_term LIKE :prefix
                      ORDER BY length(term.normalized_term), term.priority DESC LIMIT :cap"""
    ), {"prefix": form + "%", "cap": MAX_CANDIDATES})).mappings().all()
    return [
        _row_to_match(r, PREFIX_TIER - min(len(r["matched_term"]) - len(form), 40))
        for r in rows
    ]


async def _token_prefix(session: AsyncSession, form: str) -> list[TermMatch]:
    """Each query token a prefix of the corresponding term token, in order.

    Built as a single LIKE pattern ("soft% eng%"), so the leading literal still lets the
    btree `text_pattern_ops` index narrow the scan rather than reading the whole corpus.
    """
    tokens = [t for t in form.split() if t]
    if not tokens:
        return []
    pattern = "% ".join(tokens) + "%"
    rows = (await session.execute(text(
        _SELECT + """ WHERE term.normalized_term LIKE :pattern
                      ORDER BY length(term.normalized_term), term.priority DESC LIMIT :cap"""
    ), {"pattern": pattern, "cap": MAX_CANDIDATES})).mappings().all()
    return [_row_to_match(r, float(TOKEN_PREFIX_TIER)) for r in rows]


async def _tokens(session: AsyncSession, form: str) -> list[TermMatch]:
    """Every query token present in one single term — not scattered across a blob."""
    tokens = [t for t in form.split() if t]
    if not tokens:
        return []
    clauses = " AND ".join(
        f"term.normalized_term LIKE :tok_{i}" for i in range(len(tokens))
    )
    params: dict[str, Any] = {f"tok_{i}": f"%{t}%" for i, t in enumerate(tokens)}
    params["cap"] = MAX_CANDIDATES
    rows = (await session.execute(text(
        _SELECT + f" WHERE {clauses} ORDER BY length(term.normalized_term), term.priority DESC"
        " LIMIT :cap"
    ), params)).mappings().all()
    return [_row_to_match(r, float(TOKEN_TIER)) for r in rows]


async def _fuzzy(session: AsyncSession, form: str) -> list[TermMatch]:
    """The only tier that scans, and the only one that can never answer alone.

    The `%` operator is what lets the GIN trigram index serve this; the explicit
    `similarity() >= :floor` then applies our own floor rather than the session's default
    `pg_trgm.similarity_threshold`, so the tier's behaviour does not depend on a GUC.
    """
    rows = (await session.execute(text(
        _SELECT + """ WHERE term.normalized_term % :form
                        AND similarity(term.normalized_term, :form) >= :floor
                      ORDER BY similarity(term.normalized_term, :form) DESC LIMIT :cap"""
    ), {"form": form, "floor": FUZZY_ADMISSIBLE, "cap": MAX_CANDIDATES})).mappings().all()
    return [_row_to_match(r, float(FUZZY_CEILING)) for r in rows]


def _canonical_evidence(match: TermMatch, tokens: list[str]) -> int:
    """How much of the query the occupation's own canonical title accounts for.

    This is the "additional defensible evidence" that may break a tie. "Cashier" is an exact
    O*NET alternate title for both Cashiers and Tellers; only one of them is *called* Cashiers,
    and that is a real reason to prefer it. Title length and row order are not.
    """
    canonical = match.canonical_title.lower()
    return sum(1 for t in tokens if t in canonical)


def _dedupe(matches: list[TermMatch], form: str) -> list[TermMatch]:
    """One row per occupation, keeping its best-scoring term.

    Ties break on how much of the query appears in the *canonical* title, before falling back
    to length. "Cashier" is an exact O*NET alternate title for both Cashiers and Tellers; the
    one actually called Cashiers is the answer, and title length alone picked Tellers.
    """
    best: dict[int, TermMatch] = {}
    for m in matches:
        if m.identity_id not in best or m.score > best[m.identity_id].score:
            best[m.identity_id] = m

    tokens = [t for t in form.split() if t]

    def rank(m: TermMatch) -> tuple:
        canonical = m.canonical_title.lower()
        in_canonical = sum(1 for t in tokens if t in canonical)
        return (-m.score, -in_canonical, len(m.canonical_title), m.canonical_title)

    return sorted(best.values(), key=rank)


async def resolve(session: AsyncSession, query: str, limit: int = 10) -> SearchResolution:
    """Resolve a consumer query into public results, or an honest unavailable answer.

    Tiers are tried in order and the first that yields anything wins, so an exact match is a
    single index lookup and never competes with a fuzzy one. Measured on the consumer
    benchmark, 80% of queries stop before the fuzzy tier is reached.
    """
    forms = query_forms(query)
    if not forms:
        return SearchResolution(query=query, status="no_reliable_match")

    # Exact and prefix stop early — an exact hit needs no corroboration. The weak tiers are
    # gathered together instead: each caps its candidate list, so stopping at the first
    # non-empty weak tier can discard the row a later tier would have found. "soft eng"
    # exposed this — token-prefix returned a capped list with no published occupation in it,
    # and the token tier that would have found one never ran.
    matches: list[TermMatch] = []
    for tier_group in ((_exact,), (_prefix,), (_token_prefix, _tokens, _fuzzy)):
        for tier in tier_group:
            for form in forms:
                matches.extend(await tier(session, form))
        if matches:
            break

    ranked = _dedupe(matches, forms[0])
    provenance = [
        {"soc": m.soc_code, "title": m.canonical_title, "matched_term": m.matched_term,
         "term_type": m.term_type, "score": m.score, "status": m.activation_status}
        for m in ranked[:12]
    ]
    if not ranked or ranked[0].score < MIN_RELIABLE:
        return SearchResolution(query=query, status="no_reliable_match",
                                provenance=provenance)

    # ---------------------------------------------------------------------------------
    # Semantic intent is resolved FIRST, over every candidate regardless of publication.
    #
    # Publication eligibility is not evidence. Choosing the published occupation when an
    # equally-supported unpublished one shares the same exact consumer term would be
    # answering a semantic question with an availability fact — "Financial Analyst" is a
    # genuine O*NET alternate title for both Financial and Investment Analysts and Financial
    # Quantitative Analysts, and which one a person meant is not settled by which we happen
    # to have scored.
    #
    # Publication is applied only after intent is settled, below.
    # ---------------------------------------------------------------------------------
    tokens = [t for t in forms[0].split() if t]
    top_score = ranked[0].score
    tied = [m for m in ranked if m.score == top_score]

    if len(tied) > 1 and tied[0].term_type != "consumer_parent":
        evidence = {id(m): _canonical_evidence(m, tokens) for m in tied}
        best_evidence = max(evidence.values())
        contenders = [m for m in tied if evidence[id(m)] == best_evidence]
        # Ambiguity needs genuinely strong evidence on both sides. A token-prefix scrape tying
        # two occupations is weak matching, not a decision worth putting to someone.
        if len(contenders) > 1 and top_score >= STRONG_MATCH:
            tied_public = [m for m in contenders if m.is_public]
            tied_non_public = [m for m in contenders if not m.is_public]
            # A chooser with nothing choosable is not a choice. When every equally-supported
            # interpretation is unpublished — "surgeon" ties several surgical specialties, none
            # of them published — the honest answer is that we cannot analyse it yet.
            if not tied_public:
                best_unavailable = tied_non_public[0]
                return SearchResolution(
                    query=query, status="occupation_not_available",
                    public=[], non_public=tied_non_public[:1],
                    matched_term=best_unavailable.matched_term,
                    canonical_title=best_unavailable.canonical_title,
                    publication_status=best_unavailable.activation_status,
                    provenance=provenance,
                )
            return SearchResolution(
                query=query, status="ambiguous",
                public=tied_public[:limit],
                non_public=tied_non_public[:limit],
                matched_term=contenders[0].matched_term,
                is_disambiguation=True,
                provenance=provenance,
            )

    # Intent is settled. Now, and only now, does publication decide what can be shown.
    public = [m for m in ranked if m.is_public][:limit]
    non_public = [m for m in ranked if not m.is_public]
    best = ranked[0]
    best_public = public[0] if public else None

    # A curated mapping is an editorial statement that an interpretation is acceptable, so a
    # curated *published* mapping may stand in for an unpublished top interpretation. This is
    # a statement about the mapping's authorship, not about publication: the check is on term
    # type, and an accidental lexical hit never qualifies.
    curated_public = (
        best_public is not None
        and best_public.term_type in ("consumer_alias", "consumer_parent")
        and best_public.score >= STRONG_MATCH
    )

    if best.is_public or curated_public:
        return SearchResolution(
            query=query, status="public_matches", public=public, non_public=non_public,
            matched_term=best_public.matched_term if best_public else None,
            canonical_title=best_public.canonical_title if best_public else None,
            publication_status="public",
            is_disambiguation=bool(
                best_public and best_public.term_type == "consumer_parent" and len(public) > 1
            ),
            provenance=provenance,
        )

    if non_public and best.score >= STRONG_MATCH:
        return SearchResolution(
            query=query, status="occupation_not_available",
            public=[], non_public=non_public[:1],
            matched_term=best.matched_term, canonical_title=best.canonical_title,
            publication_status=best.activation_status,
            provenance=provenance,
        )

    # Weak-tier fallback. A published candidate may answer only if it is tied for best on
    # evidence. If an unpublished candidate scored strictly higher, the published ones lost the
    # semantic contest, and presenting one anyway is substitution by another route — "soft eng"
    # identifies Software Developer at the token-prefix tier, and returning Etchers and
    # Engravers because Software Developers is staged is precisely the failure this policy
    # exists to stop. Not confident enough to answer is an acceptable answer.
    # A weak-tier tie is still a tie, and publication may not break it. Where an unpublished
    # candidate matches the query's own words at least as well as the best published one, we
    # cannot tell them apart and cannot show the unpublished one — so we say we are not sure
    # rather than presenting the published one as the answer. "soft eng" ties Software
    # Developer with Etchers and Engravers (via "Soft Metal Hand Engraver") at the token-prefix
    # tier; answering with the engraver would be the same substitution wearing a different hat.
    if public and public[0].score >= best.score:
        public_evidence = _canonical_evidence(public[0], tokens)
        blocked_by_tie = any(
            _canonical_evidence(m, tokens) >= public_evidence
            for m in ranked
            if not m.is_public and m.score >= public[0].score
        )
        if blocked_by_tie:
            return SearchResolution(query=query, status="no_reliable_match",
                                    provenance=provenance)
        return SearchResolution(
            query=query, status="public_matches", public=public,
            matched_term=public[0].matched_term,
            canonical_title=public[0].canonical_title, publication_status="public",
            provenance=provenance,
        )

    return SearchResolution(query=query, status="no_reliable_match",
                            provenance=provenance)


async def related_public(
    session: AsyncSession, identity_id: int, limit: int = 4
) -> list[dict[str, Any]]:
    """Public occupations related to an unpublished one, for the secondary slot.

    Uses O*NET's own related-occupations data — the same source the public occupation page
    uses — so nothing is inferred and no model is consulted. Each target must independently
    clear the publication gate, because these are links out to real pages.
    """
    rows = (await session.execute(text("""
      SELECT target.slug, target.title
      FROM onet_related_occupations related
      JOIN canonical_occupation_identities source_identity
        ON source_identity.current_source_code = related.occupation_code
      JOIN canonical_occupation_identities target_identity
        ON target_identity.current_source_code = related.related_occupation_code
      JOIN occupations target ON target.id = target_identity.jobs_vs_ai_occupation_id
      JOIN occupation_publications pub
        ON pub.identity_id = target_identity.id AND pub.activation_status = 'public'
      WHERE source_identity.id = :identity_id
        AND related.is_current
      ORDER BY related.relatedness_rank NULLS LAST, target.title
      LIMIT :limit
    """), {"identity_id": identity_id, "limit": limit})).mappings().all()
    return [{"slug": r["slug"], "title": r["title"]} for r in rows]
