"""Preliminary estimate layer — separation, calibration and presentation.

The defect this layer could cause is not a crash. It is an estimate rendered as a verified
score, which fails silently and is only visible to the person who was misled. Most of these
tests therefore assert on *separation* rather than on behaviour.
"""

from __future__ import annotations

import pathlib

import pytest
from sqlalchemy import text

from app.db.session import SessionFactory

from scoring.preliminary_estimates import (  # type: ignore[import-not-found]
    RelativeEvidence,
    estimate_from_relatives,
    estimate_from_task_evidence,
)

MIGRATION = pathlib.Path("/app/migrations/035_preliminary_occupation_estimates.sql")


# --------------------------------------------------------------------------- estimator unit


def test_complete_task_evidence_is_a_point_not_a_range() -> None:
    """E1 is the engine's own answer over full coverage; a range would overstate doubt."""
    estimate = estimate_from_task_evidence(
        identity_id=1, occupation_code="47-2111.00", ai_exposure=47.4,
        replacement_risk=33.2, weighted_task_coverage=100.0, confidence=87.7)
    assert estimate.method == "E1"
    assert estimate.confidence == "higher"
    assert estimate.is_range is False
    assert estimate.ai_exposure == 47


def test_thin_task_evidence_becomes_a_range() -> None:
    estimate = estimate_from_task_evidence(
        identity_id=1, occupation_code="41-2011.00", ai_exposure=60.0,
        replacement_risk=55.0, weighted_task_coverage=50.9, confidence=53.2)
    assert estimate.method == "E2"
    assert estimate.confidence == "low"
    assert estimate.is_range is True
    assert estimate.ai_exposure_low < estimate.ai_exposure < estimate.ai_exposure_high


def test_engine_score_is_never_adjusted_by_the_estimator() -> None:
    """Confidence changes how firmly we say it, never what the number is.

    Nudging a validated engine output because we are less sure of it would produce a third
    quantity that is neither the engine's answer nor an honest estimate.
    """
    for coverage in (100.0, 79.0, 55.0):
        estimate = estimate_from_task_evidence(
            identity_id=1, occupation_code="x", ai_exposure=63.4, replacement_risk=41.6,
            weighted_task_coverage=coverage, confidence=80.0)
        assert estimate.ai_exposure == 63
        assert estimate.replacement_risk == 42


def test_proxy_is_always_a_range() -> None:
    relatives = [
        RelativeEvidence("15-1211.00", "Computer Systems Analysts", "Primary-Short", 70.0, 55.0),
        RelativeEvidence("15-1251.00", "Computer Programmers", "Primary-Long", 76.0, 62.0),
    ]
    estimate = estimate_from_relatives(
        identity_id=1, occupation_code="15-1252.00", relatives=relatives)
    assert estimate is not None
    assert estimate.method == "E3"
    assert estimate.is_range is True, "a borrowed number must never render as a point"


def test_proxy_weights_by_relatedness_tier() -> None:
    """A Primary-Short relative counts for three Supplemental ones. Tier is the only signal
    used; a proxy chosen by title text would reintroduce lexical coincidence."""
    close = RelativeEvidence("a", "A", "Primary-Short", 90.0, 90.0)
    far = RelativeEvidence("b", "B", "Supplemental", 10.0, 10.0)
    estimate = estimate_from_relatives(identity_id=1, occupation_code="x", relatives=[close, far])
    assert estimate is not None
    assert estimate.ai_exposure == 70  # (90*3 + 10*1) / 4


def test_no_relatives_produces_no_estimate() -> None:
    """An estimate with no source is not a weaker estimate; it is a fabrication."""
    assert estimate_from_relatives(identity_id=1, occupation_code="55-3016.00", relatives=[]) is None


def test_estimator_is_reproducible() -> None:
    relatives = [RelativeEvidence("a", "A", "Primary-Short", 61.3, 44.7),
                 RelativeEvidence("b", "B", "Supplemental", 33.1, 70.2)]
    first = estimate_from_relatives(identity_id=1, occupation_code="x", relatives=relatives)
    second = estimate_from_relatives(identity_id=1, occupation_code="x", relatives=relatives)
    assert first is not None and second is not None
    assert (first.ai_exposure, first.replacement_risk, first.ai_exposure_low) == (
        second.ai_exposure, second.replacement_risk, second.ai_exposure_low)


def test_estimates_are_whole_numbers() -> None:
    """False precision on a number whose p90 error is ten points is its own kind of lie."""
    estimate = estimate_from_relatives(
        identity_id=1, occupation_code="x",
        relatives=[RelativeEvidence("a", "A", "Primary-Short", 61.37, 44.71)])
    assert estimate is not None
    assert isinstance(estimate.ai_exposure, int)
    assert isinstance(estimate.replacement_risk, int)


# ------------------------------------------------------------------------------- migration


@pytest.mark.skipif(not MIGRATION.exists(), reason="migrations are not mounted here")
def test_migration_pins_score_status_and_is_additive() -> None:
    body = MIGRATION.read_text()
    assert "CHECK (score_status = 'estimated')" in body, (
        "the estimate table must be structurally incapable of holding a verified score")
    assert "occupation_estimates_never_shadow_verified" in body
    assert "current_published_occupation_estimates" in body
    for forbidden in ("DROP TABLE", "TRUNCATE", "ALTER TABLE production_",
                      "UPDATE occupation_publications", "DELETE FROM occupation_publications"):
        assert forbidden not in body.upper().replace("IF EXISTS", ""), forbidden


# ------------------------------------------------------------------------- database wiring


async def _scalar(sql: str) -> int:
    async with SessionFactory() as session:
        return (await session.execute(text(sql))).scalar_one()


@pytest.mark.asyncio(loop_scope="session")
async def test_estimate_table_rejects_a_verified_status() -> None:
    with pytest.raises(Exception):
        async with SessionFactory() as session, session.begin():
            await session.execute(text("""
                INSERT INTO occupation_score_estimates
                    (estimate_run_id, identity_id, occupation_code, score_status,
                     estimate_method, estimate_method_detail, estimate_confidence,
                     ai_exposure_estimate, replacement_risk_estimate)
                VALUES (1, 1, 'x', 'verified', 'E1', 'd', 'higher', 50, 50)
            """))


@pytest.mark.asyncio(loop_scope="session")
async def test_no_identity_holds_both_a_verified_score_and_a_published_estimate() -> None:
    """The invariant the whole design exists to protect."""
    assert await _scalar("""
        SELECT count(*) FROM current_published_occupation_estimates estimate
        WHERE EXISTS (SELECT 1 FROM current_production_occupation_scores score
                      WHERE score.identity_id = estimate.identity_id)
    """) == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_verified_publication_and_live_score_stay_one_to_one() -> None:
    """Publication semantics keep meaning exactly what they meant before.

    Counts are not pinned to 507: the session-scoped `published_occupations` fixture moves the
    ambient number while it is alive. The *relationship* is the invariant.
    """
    orphaned = await _scalar("""
        SELECT count(*) FROM occupation_publications p
        WHERE p.activation_status='public'
          AND NOT EXISTS (SELECT 1 FROM current_production_occupation_scores c
                          WHERE c.identity_id = p.identity_id)
    """)
    assert orphaned == 0, "a public occupation exists with no verified score"


@pytest.mark.asyncio(loop_scope="session")
async def test_rankings_and_listings_cannot_reach_an_estimate() -> None:
    """Estimates are excluded by the publication predicate itself, not by a filter.

    A filter is something a future query can forget. `public_occupation_predicate` gates on
    activation_status, which no estimate ever receives.
    """
    from app.repositories.publication import public_occupation_predicate

    assert await _scalar(f"""
        SELECT count(*) FROM occupations o
        WHERE {public_occupation_predicate('o')}
          AND EXISTS (SELECT 1 FROM canonical_occupation_identities ci
                      JOIN current_published_occupation_estimates e ON e.identity_id = ci.id
                      WHERE ci.jobs_vs_ai_occupation_id = o.id)
    """) == 0


# ------------------------------------------------------------------------------- API shape


@pytest.mark.asyncio(loop_scope="session")
async def test_search_returns_estimates_in_their_own_field(client) -> None:
    """A client that has not been updated for estimates must not receive one in `results`."""
    payload = (await client.get("/api/v1/occupations/search/resolve",
                                params={"q": "electrician"})).json()
    assert payload["queryStatus"] == "public_matches"
    assert payload["results"] == [], "an estimate must never arrive in the verified field"
    assert payload["estimatedResults"], "the estimate should be found and returned"
    assert payload["estimatedResults"][0]["scoreStatus"] == "estimated"


@pytest.mark.asyncio(loop_scope="session")
async def test_estimate_payload_carries_its_disclaimer_and_no_internal_status(client) -> None:
    payload = (await client.get("/api/v1/occupations/search/resolve",
                                params={"q": "electrician"})).json()
    estimate = payload["estimatedResults"][0]
    assert estimate["disclaimer"]
    assert estimate["confidenceLabel"].endswith("estimate")
    # "High confidence" would read as a stronger verified score rather than a different claim.
    assert "High confidence" not in estimate["confidenceLabel"]
    body = str(payload)
    for internal in ("staged", "review_required", "provisional_input_sensitivity"):
        assert internal not in body, f"internal status {internal!r} leaked to the public payload"


@pytest.mark.asyncio(loop_scope="session")
async def test_verified_occupation_has_no_estimate_route(client) -> None:
    response = await client.get("/api/v1/occupations/accountant/estimate")
    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_search_ranks_identity_relevance_over_score_class(client) -> None:
    """`data scientist` must return Data Scientists, not a verified but unrelated occupation.

    This is the whole product argument for the layer: what we have finished validating is not
    evidence about what the user meant.
    """
    payload = (await client.get("/api/v1/occupations/search/resolve",
                                params={"q": "data scientist"})).json()
    named = [o["title"] for o in payload.get("results", [])] + \
            [o["title"] for o in payload.get("estimatedResults", [])]
    assert any("Data Scientist" in title for title in named), named
