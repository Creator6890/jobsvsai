"""Regression guards for the three faults that reached production in the Search V2 release.

Each of them passed every liveness check at the time. The site was up, the API answered, the
database was consistent — and search returned a confidently wrong occupation, a page took
eight seconds, and the AdSense verification tag was silently absent. These tests pin the
structural facts that make those states detectable rather than relying on someone noticing.

The runtime half lives in `scripts/healthcheck.sh`; what is asserted here is the part that
can be checked without a running production stack.
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def _find(relative: str) -> pathlib.Path:
    for base in (pathlib.Path("/app"), REPO):
        candidate = base / relative
        if candidate.exists():
            return candidate
    pytest.skip(f"{relative} is not mounted in this environment")


# ------------------------------------------------------- the /compare 500 (missing index)


def test_migration_036_creates_the_identity_keyed_related_index() -> None:
    """The index whose absence made /compare time out.

    Every other index on `public_occupation_related_occupations` leads with `content_run_id`;
    the read path filters on `identity_id` and takes `max(content_run_id)`, so none of them
    could serve it. Fine at 6,470 rows, an outage at 31,401.
    """
    body = _find("migrations/036_related_occupations_identity_index.sql").read_text()
    assert "public_content_related_identity_run_idx" in body
    assert re.search(
        r"ON\s+public_occupation_related_occupations\s*\(\s*identity_id\s*,\s*content_run_id\s*\)",
        body,
    ), "the index must lead with identity_id, or it cannot serve the LATERAL"


def test_healthcheck_guards_the_related_index() -> None:
    """A migration creating an index does not stop someone dropping it later."""
    body = _find("scripts/healthcheck.sh").read_text()
    assert "public_content_related_identity_run_idx" in body


# ------------------------------------------------------------- the AdSense tag disappearing


def test_adsense_client_id_falls_back_on_an_empty_string() -> None:
    """`??` is not enough, and the difference took the verification tag off the live site.

    `NEXT_PUBLIC_*` values are baked at build time from compose build args, and compose
    interpolates a key that is present-but-empty in `.env` as `""` rather than leaving it
    undefined. `??` only falls back on null/undefined, so an empty line produced an empty
    client ID, which removed both the meta tag and the loader while every other check passed.
    """
    body = _find("frontend/src/lib/ads.ts").read_text()
    match = re.search(
        r"adsenseClientId:\s*string\s*=\s*\n?\s*process\.env\.NEXT_PUBLIC_ADSENSE_CLIENT_ID\s*(\?\?|\|\|)",
        body,
    )
    assert match, "could not locate the adsenseClientId fallback"
    assert match.group(1) == "||", (
        "must be `||`: an empty string is not a configured value, and `??` lets it through"
    )


def test_healthcheck_separates_connection_from_ad_serving() -> None:
    """Two different facts that must not be reported as one.

    The account connection being live is what Google's review needs; manual ad serving being
    off is the product decision. Collapsing them would let "ads are off, as intended" mask
    "the publisher tag is gone".
    """
    body = _find("scripts/healthcheck.sh").read_text()
    assert "ADSENSE CONNECTION" in body
    assert "MANUAL AD SERVING" in body
    assert "ca-pub-7855774194309157" in body


# ------------------------------------------------------------------ the `soft eng` failure


@pytest.mark.parametrize(
    ("query", "expected_slug"),
    [
        ("soft eng", "software-developer"),
        ("pen tester", "cybersecurity-analyst"),
        ("data analyst", "data-scientists"),
    ],
)
def test_healthcheck_pins_the_semantic_smoke_queries(query: str, expected_slug: str) -> None:
    """Asserted on canonical slugs, not display text: titles are editorial and move."""
    body = _find("scripts/healthcheck.sh").read_text()
    assert f'semantic "{query}"' in body, f"{query!r} is not smoke-checked"
    assert expected_slug in body


def test_healthcheck_names_the_documented_wrong_answers() -> None:
    """The negative half. Knowing what it must NOT return is what makes the check specific."""
    body = _find("scripts/healthcheck.sh").read_text()
    assert "etchers-and-engravers" in body, "the soft eng failure is not pinned"
    assert "non-destructive-testing-specialists" in body, "the pen tester failure is not pinned"


def test_healthcheck_does_not_run_the_full_benchmark() -> None:
    """Cron-safe. The 187-query benchmark belongs in the suite, not in a liveness check."""
    body = _find("scripts/healthcheck.sh").read_text()
    assert "consumer_search_benchmark" not in body


# --------------------------------------------------------------- the two-class invariant


def test_healthcheck_tracks_verified_and_estimated_separately() -> None:
    """897 searchable pages is not 897 verified analyses.

    A health model that reported one total would erase the distinction the whole preliminary
    layer exists to preserve.
    """
    body = _find("scripts/healthcheck.sh").read_text()
    assert "EXPECT_VERIFIED" in body and "EXPECT_ESTIMATES" in body
    assert "no occupation is both verified and estimated" in body
    # The verified expectation must not have been quietly replaced by the combined total.
    assert "EXPECT_VERIFIED:-507}" in body
    assert "EXPECT_VERIFIED:-897}" not in body
