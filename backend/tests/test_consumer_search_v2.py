"""consumer-search-v2 — ranking, honesty and the publication boundary.

The failures this replaces were all the same shape: the best of a bad field, returned as if it
were an answer. "ml engineer" reached Search Marketing Strategists, "pen tester" reached
Non-Destructive Testing Specialists, "data entry operator" reached First-Line Supervisors of
Office and Administrative Support Workers. Each was the top row of a ranking ordered purely by
trigram similarity against a concatenated alias blob.

The tests that matter here are therefore mostly about what search must *not* do.
"""

from __future__ import annotations

import json
import pathlib

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.db.session import SessionFactory
from app.repositories import occupation_search as search
from app.search import normalize

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "consumer_search_benchmark.json").read_text()
)


def _has_search_terms(rows) -> bool:
    return bool(rows)


@pytest_asyncio.fixture(loop_scope="session")
async def search_ready() -> bool:
    """Migration 034 must be applied for these to mean anything."""
    async with SessionFactory() as s:
        present = (await s.execute(text(
            "SELECT to_regclass('public.occupation_search_terms') IS NOT NULL"
        ))).scalar()
    if not present:
        pytest.skip("migration 034 not applied to this database")
    return True


# --- normalisation ---------------------------------------------------------------------


def test_normalise_matches_the_migration_expression() -> None:
    """Query-time and index-time normalisation must not drift.

    Migration 034 stores `lower(regexp_replace(term, '[^a-zA-Z0-9]+', ' ', 'g'))`. If this
    function stops agreeing with that, exact matching silently degrades into fuzzy matching
    and nothing fails loudly.
    """
    for raw, expected in [
        ("Data Entry Keyers", "data entry keyers"),
        ("First-Line Supervisors", "first line supervisors"),
        ("Nurse Practitioners, All Other", "nurse practitioners all other"),
        ("  Web   Developers ", "web developers"),
    ]:
        assert normalize.normalise(raw) == expected


def test_abbreviations_expand_without_replacing_the_literal_query() -> None:
    """"it support" must still be able to match the literal O*NET term "IT Support"."""
    forms = normalize.query_forms("it support")
    assert forms[0] == "it support"
    assert "information technology support" in forms


@pytest.mark.parametrize("query,expected", [
    ("pen tester", "penetration tester"),
    ("ml engineer", "machine learning engineer"),
    ("swe", "software engineer"),
    ("soc analyst", "security operations center analyst"),
])
def test_career_initialisms_expand(query: str, expected: str) -> None:
    assert expected in normalize.query_forms(query)


@pytest.mark.parametrize("query,variant", [
    ("medical assistant", "medical assistants"),
    ("carpenter", "carpenters"),
    ("economist", "economists"),
    ("teachers", "teacher"),
])
def test_singular_plural_variants(query: str, variant: str) -> None:
    """O*NET titles are plural; people type the singular.

    Without this "medical assistant" matched no term exactly and fell through to token
    matching, which reached Health Specialties Teachers.
    """
    assert variant in normalize.query_forms(query)


def test_literal_query_is_always_tried_first() -> None:
    for q in ("it support", "ml engineer", "pen tester", "teacher"):
        assert normalize.query_forms(q)[0] == normalize.normalise(q)


# --- the publication boundary ------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_unpublished_occupation_is_named_but_never_returned(search_ready) -> None:
    """The core contract: understand the query, refuse to publish an unapproved score."""
    async with SessionFactory() as s:
        result = await search.resolve(s, "data scientist", 10)

    if result.status == "public_matches":
        pytest.skip("Data Scientists is published in this database")
    assert result.status == "occupation_not_available"
    assert result.public == []
    assert result.canonical_title
    assert result.publication_status in ("staged", "review_required", "unpublished")


@pytest.mark.asyncio(loop_scope="session")
async def test_resolution_never_carries_a_score_or_a_block_reason(search_ready) -> None:
    """A TermMatch is identity and provenance only — there is nowhere to put a score."""
    fields = set(search.TermMatch.__dataclass_fields__)
    for forbidden in ("score_value", "replacement_risk", "ai_exposure", "confidence",
                      "weighted_task_coverage", "blocking_codes", "provisional_sensitivity"):
        assert forbidden not in fields


@pytest.mark.asyncio(loop_scope="session")
async def test_shown_results_all_carry_a_published_analysis(search_ready) -> None:
    """Every result offered to a user is backed by a published analysis of a known class.

    After the preliminary-estimate layer "shown" no longer means "activation_status=public":
    an estimated occupation is showable too. What must never happen is a result with no
    analysis behind it at all, or one whose class we cannot name.
    """
    async with SessionFactory() as s:
        for query in ("nurse", "teacher", "accountant", "manager", "analyst"):
            result = await search.resolve(s, query, 10)
            for match in result.public:
                assert match.score_status in ("verified", "estimated"), query
                if match.score_status == "verified":
                    assert match.activation_status == "public", query
                    assert match.occupation_id is not None, query


# --- the stop rule ------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_nonsense_returns_no_reliable_match(search_ready) -> None:
    async with SessionFactory() as s:
        for query in ("zzzqqq nonsense", "qwertyuiop asdf", "xyzzy plugh"):
            assert (await search.resolve(s, query, 10)).status == "no_reliable_match"


def test_fuzzy_can_never_answer_alone() -> None:
    """The single rule that prevents best-of-a-bad-field substitution.

    Fuzzy scores at FUZZY_CEILING; an answer needs MIN_RELIABLE. The gap is deliberate: a
    lexical near-miss may corroborate a match, never constitute one.
    """
    assert search.FUZZY_CEILING < search.MIN_RELIABLE


def test_tier_floors_are_strictly_ordered() -> None:
    """Known semantics must outrank accidental lexical similarity, by construction."""
    assert search.STRONG_MATCH > search.PREFIX_TIER > search.TOKEN_TIER
    assert search.TOKEN_TIER > search.FUZZY_CEILING


@pytest.mark.asyncio(loop_scope="session")
async def test_the_production_substitutions_do_not_recur(search_ready) -> None:
    """Each of these returned an unrelated occupation in production."""
    forbidden = {
        "ml engineer": ["search marketing", "petroleum"],
        "pen tester": ["non-destructive", "cabinetmaker", "financial examiner"],
        "data entry operator": ["first-line supervisors of office"],
        "data scientist": ["bioinformatics technician", "survey researcher"],
    }
    async with SessionFactory() as s:
        for query, banned in forbidden.items():
            result = await search.resolve(s, query, 10)
            titles = " | ".join(m.canonical_title.lower() for m in result.public)
            for bad in banned:
                assert bad not in titles, f"{query!r} returned {bad!r}"


# --- broad families -----------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_broad_query_disambiguates_rather_than_picking_one(search_ready) -> None:
    """"teacher" must not silently resolve to one teaching occupation."""
    async with SessionFactory() as s:
        result = await search.resolve(s, "teacher", 10)
    if result.status != "public_matches":
        pytest.skip("no published teaching occupations in this database")
    assert len(result.public) > 1
    assert result.is_disambiguation
    assert any("teacher" in m.canonical_title.lower() for m in result.public)


# --- the regression corpus ----------------------------------------------------------------


def test_fixture_is_versioned_and_explains_its_banding() -> None:
    assert FIXTURE["fixture_version"] == "consumer-search-benchmark-v1"
    assert len(FIXTURE["queries"]) >= 150
    for row in FIXTURE["queries"]:
        assert row["band"] in ("public_answerable", "non_public_detection", "taxonomy_gap")
        assert row["expected_status"] in (
            "public_matches", "occupation_not_available", "no_reliable_match")
        # Every judgement is inspectable: no opaque annotations.
        assert row["expected_titles"]


def test_critical_queries_are_marked() -> None:
    critical = {row["query"] for row in FIXTURE["queries"] if row.get("critical")}
    for query in ("teacher", "ml engineer", "data scientist", "data analyst",
                  "data entry operator", "pen tester", "martial arts instructor",
                  "software engineer", "lawyer", "electrician", "cashier"):
        assert query in critical, query


@pytest.mark.asyncio(loop_scope="session")
async def test_critical_queries_meet_their_expected_status(search_ready) -> None:
    """The hard gate. A regression on any of these should fail the build."""
    critical = [r for r in FIXTURE["queries"] if r.get("critical")]
    failures = []
    async with SessionFactory() as s:
        for row in critical:
            result = await search.resolve(s, row["query"], 10)
            if result.status == row["expected_status"]:
                continue
            # The fixture predates the preliminary-estimate layer, so its
            # `occupation_not_available` expectations describe a cohort that has since
            # changed. What the gate actually protects is that the *intended occupation* is
            # the one named — not that we still decline to analyse it. Naming it with an
            # estimate satisfies that; substituting a different occupation never does.
            intended = (row.get("intended") or {}).get("soc")
            named = {m.soc_code for m in result.public} | {m.soc_code for m in result.non_public}
            if (row["expected_status"] == "occupation_not_available"
                    and result.status in ("public_matches", "ambiguous")
                    and intended in named):
                continue
            failures.append(f"{row['query']!r}: {result.status} "
                            f"(expected {row['expected_status']})")
    assert not failures, "critical query regressions: " + "; ".join(failures)


@pytest.mark.asyncio(loop_scope="session")
async def test_benchmark_quality_gates_hold(search_ready) -> None:
    """Aggregate gates, asserted against the current public cohort.

    Thresholds sit a little below the measured values so ordinary noise does not fail a build,
    while a real regression does. Publication-coverage changes move which band a query is in,
    not whether search is working, which is why the two are measured separately.
    """
    public_rows = [r for r in FIXTURE["queries"] if r["band"] == "public_answerable"]
    non_public_rows = [r for r in FIXTURE["queries"] if r["band"] == "non_public_detection"]

    top3 = useful = misleading = 0
    detected = substituted = 0
    async with SessionFactory() as s:
        for row in public_rows:
            result = await search.resolve(s, row["query"], 10)
            titles = [m.canonical_title.lower() for m in result.public]
            # Estimated results count for this band too: the question is whether the user
            # was given the occupation they asked for, not which store answered.
            titles = titles + [m.canonical_title.lower() for m in result.non_public
                               if m.score_status == "estimated"]
            hit = next((i for i, t in enumerate(titles)
                        if any(e.lower() in t for e in row["expected_titles"])), None)
            if hit is not None:
                useful += 1
                if hit < 3:
                    top3 += 1
            elif result.status == "public_matches":
                misleading += 1
        for row in non_public_rows:
            result = await search.resolve(s, row["query"], 10)
            intended = (row.get("intended") or {}).get("soc")
            # This band was written when an occupation was either verified-public or nothing,
            # so "detection" meant returning `occupation_not_available`. The estimate layer
            # gives the same occupations a third fate, and declining to analyse one that now
            # has a published estimate would be a regression rather than a success.
            #
            # What the band has always really measured is *substitution*: did we answer with
            # the occupation the user meant, or with a different one? So detection is now
            # "the intended occupation is the one we named", whether that naming is an
            # estimate, an unavailable notice, or a choice in a chooser.
            named = {m.soc_code for m in result.public} | {m.soc_code for m in result.non_public}
            if result.status == "occupation_not_available" or (intended and intended in named):
                detected += 1
            elif result.status in ("public_matches", "ambiguous"):
                substituted += 1

    n, m = len(public_rows), len(non_public_rows)
    assert 100 * top3 / n >= 88, f"public top-3 fell to {100 * top3 / n:.1f}%"
    assert 100 * misleading / n <= 4, f"misleading rose to {100 * misleading / n:.1f}%"
    assert 100 * detected / m >= 90, (
        f"intended-occupation detection fell to {100 * detected / m:.1f}%")
    assert 100 * substituted / m <= 6, f"false substitution rose to {100 * substituted / m:.1f}%"


# --- Gate 1: exact-term collisions --------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_high_priority_term_collisions_are_measured(search_ready) -> None:
    """The corpus carries thousands of terms shared by several occupations.

    Recorded rather than asserted at a fixed number, because the count moves with every O*NET
    import. What matters is that the resolver knows collisions exist and does not settle them
    by row order.
    """
    async with SessionFactory() as s:
        collisions = (await s.execute(text("""
          WITH high AS (
            SELECT normalized_term, identity_id, max(priority) AS p
            FROM occupation_search_terms WHERE priority >= 900
            GROUP BY normalized_term, identity_id)
          SELECT count(*) FROM (
            SELECT normalized_term FROM high GROUP BY normalized_term
            HAVING count(*) > 1 AND max(p) = min(p)) tied
        """))).scalar()
    assert collisions > 0, "expected shared alternate titles in the O*NET corpus"


@pytest.mark.asyncio(loop_scope="session")
async def test_unbreakable_tie_returns_ambiguous_not_a_guess(search_ready) -> None:
    """A tie canonical-title evidence cannot break must not be resolved by length or id."""
    async with SessionFactory() as s:
        result = await search.resolve(s, "psychologist", 10)
    if result.status != "ambiguous":
        pytest.skip("psychologist does not collide in this database")
    assert len(result.public) > 1
    assert result.is_disambiguation
    assert all(m.activation_status == "public" for m in result.public)


@pytest.mark.asyncio(loop_scope="session")
async def test_tie_is_broken_when_the_canonical_title_carries_the_query(search_ready) -> None:
    """"Cashier" is an exact alternate title for both Cashiers and Tellers.

    Only one of them is *called* Cashiers, which is defensible evidence — unlike title length.
    """
    async with SessionFactory() as s:
        result = await search.resolve(s, "cashier", 10)
    assert result.status != "ambiguous"
    titles = [p["title"].lower() for p in result.provenance[:1]]
    assert any("cashier" in t for t in titles), result.provenance[:2]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_tie_won_by_an_unpublished_occupation_is_never_a_chooser(search_ready) -> None:
    """Ambiguity is only ever offered among published occupations.

    Converting an unavailable answer into a list of loosely related public jobs is the
    substitution this design exists to prevent, so the collision check runs only after the
    publication decision.
    """
    async with SessionFactory() as s:
        for query in ("data scientist", "electrician", "lawyer"):
            result = await search.resolve(s, query, 10)
            if result.status == "ambiguous":
                assert all(m.activation_status == "public" for m in result.public), query


# --- Gate 4: provenance -------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_every_candidate_is_explainable(search_ready) -> None:
    """A relevance defect must be diagnosable from a test rather than guessed at."""
    async with SessionFactory() as s:
        result = await search.resolve(s, "pen tester", 10)
    assert result.provenance
    for row in result.provenance:
        assert {"soc", "title", "matched_term", "term_type", "score", "status"} <= set(row)


@pytest.mark.asyncio(loop_scope="session")
async def test_provenance_is_not_exposed_by_the_public_schema(search_ready) -> None:
    """Internal ranking detail stays server-side."""
    from app.schemas.search import SearchResponse

    assert "provenance" not in SearchResponse.model_fields


# --- Gate 9: one implementation, two shapes ------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_legacy_endpoint_shares_the_v2_resolver(search_ready) -> None:
    """`/search` and `/search/resolve` must not drift into two search implementations."""
    import inspect

    from app.repositories import occupations

    source = inspect.getsource(occupations.search_occupations)
    assert "occupation_search.resolve" in source

    async with SessionFactory() as s:
        resolution = await search.resolve(s, "nurse", 10)
        legacy = await occupations.search_occupations(s, "nurse", 10)
    if resolution.status in ("public_matches", "ambiguous"):
        # Verified only: the bare-list shape cannot express an estimate, so the legacy
        # endpoint returns the verified subset of what the resolver found.
        assert [o.slug for o in legacy] == [
            m.slug for m in resolution.public if m.is_verified and m.slug]
    else:
        assert legacy == []


@pytest.mark.asyncio(loop_scope="session")
async def test_legacy_endpoint_returns_nothing_for_unpublished_intent(search_ready) -> None:
    """The old shape cannot express "exists but unpublished", so it must return empty rather
    than substitute."""
    from app.repositories import occupations

    async with SessionFactory() as s:
        resolution = await search.resolve(s, "data scientist", 10)
        if resolution.status != "occupation_not_available":
            pytest.skip("Data Scientists is published in this database")
        assert await occupations.search_occupations(s, "data scientist", 10) == []
