"""Shared fixtures.

Nothing is public by default: the read path is gated on
`occupation_publications.activation_status`, and no occupation carries a production score
until one is promoted. Tests that assert on public behaviour therefore build their own
world — identities, a completed promotion run with snapshots and derivations, and
publications — and tear it back down.

Teardown asymmetry is deliberate. Publications and the approval pointer are restored, but
snapshots are *not* deleted: the store is append-only and the triggers correctly refuse.
Withdrawal is a rollback, exactly as it would be in production, after which the currency
view returns nothing.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from tests.db_guard import assert_marker_table, resolve_target

# Checks 1-3 run at import, before `app.db.session` is imported and therefore before an
# engine is constructed against whatever DATABASE_URL happens to be set. Importing this
# module is enough to refuse an unsafe target; no test needs to remember to opt in.
TEST_DATABASE_TARGET = resolve_target()

from app.db.session import SessionFactory  # noqa: E402  (must follow the guard)
from app.main import app  # noqa: E402
from tests.production_fixtures import build_promotion_run, roll_back_run  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="session")


def pytest_report_header() -> list[str]:
    """Put the resolved target in the pytest header so every run states its database."""
    return [f"test database: {TEST_DATABASE_TARGET.describe()}"]


@pytest.fixture(autouse=True)
def _no_live_llm_calls(monkeypatch):
    """No test may reach a real language-model provider.

    The suite runs with the developer's environment, which legitimately carries
    NEWS_LLM_PROVIDER=gemini and a real NEWS_LLM_API_KEY. A generation test that forgot to
    inject a fake provider would therefore call the live API — spending quota, depending on
    the network, and making results non-deterministic.

    This is the language-model analogue of the test-database guard: blank the credentials for
    every test by default, so reaching a provider requires a deliberate override rather than
    an oversight. Tests that exercise provider construction set what they need explicitly.
    """
    monkeypatch.setenv("NEWS_LLM_PROVIDER", "null")
    monkeypatch.setenv("NEWS_LLM_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _verify_test_database():
    """Check 4, the one the environment cannot fake: the marker table must be present.

    Autouse and session-scoped, so it runs before any fixture that touches the database.
    A test that never opens a connection still pays only one connection for this.
    """
    async with SessionFactory() as session:
        label = await assert_marker_table(session)
    print(f"\ntest database marker verified: {label}")
    yield


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


async def set_activation(slug: str, status: str) -> None:
    """Flip one occupation's publication status. Used to exercise the gate itself."""
    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          UPDATE occupation_publications SET activation_status=:status, updated_at=now()
          WHERE identity_id IN (
            SELECT identity.id FROM canonical_occupation_identities identity
            JOIN occupations occupation ON occupation.id = identity.jobs_vs_ai_occupation_id
            WHERE occupation.slug = :slug
          )
        """), {"status": status, "slug": slug})


# NOT autouse: pure-policy tests (e.g. the launch triage) must not be forced to open a
# database connection just because they live in this package.
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def published_occupations():
    run = await build_promotion_run(key_suffix="base")

    created_publications: list[int] = []
    previous_status: dict[int, str] = {}
    created_import_run: int | None = None

    async with SessionFactory() as session, session.begin():
        source_id = (await session.execute(
            text("SELECT id FROM data_sources ORDER BY id LIMIT 1")
        )).scalar_one()
        created_import_run = (await session.execute(
            text("INSERT INTO import_runs (source_id,status) VALUES (:source_id,'complete') RETURNING id"),
            {"source_id": source_id},
        )).scalar_one()

        for slug, identity_id in run["identities"].items():
            title = (await session.execute(
                text("SELECT title FROM occupations WHERE slug=:slug"), {"slug": slug}
            )).scalar_one()
            existing = (await session.execute(text("""
              SELECT activation_status FROM occupation_publications
              WHERE identity_id=:id AND locale='en' AND source_geography='US'
            """), {"id": identity_id})).scalar_one_or_none()
            if existing is not None:
                previous_status[identity_id] = existing
                await session.execute(text("""
                  UPDATE occupation_publications SET activation_status='public'
                  WHERE identity_id=:id AND locale='en' AND source_geography='US'
                """), {"id": identity_id})
                continue

            seo_slug = slug
            if (await session.execute(text(
                "SELECT 1 FROM occupation_publications WHERE locale='en' AND source_geography='US' AND seo_slug=:slug"
            ), {"slug": seo_slug})).scalar_one_or_none():
                seo_slug = f"{seo_slug}-pytest-fixture"
            await session.execute(text("""
              INSERT INTO occupation_publications
                (identity_id,locale,canonical_public_title,seo_slug,source_geography,
                 activation_status,editorial_review_status,title_source,source_id,import_run_id,source_version)
              VALUES (:identity_id,'en',:title,:seo_slug,'US','public','approved',
                      'jobsvsai_editorial',:source_id,:import_run_id,'test')
            """), {"identity_id": identity_id, "title": title, "seo_slug": seo_slug,
                   "source_id": source_id, "import_run_id": created_import_run})
            created_publications.append(identity_id)

    yield run

    async with SessionFactory() as session, session.begin():
        await session.execute(text("""
          UPDATE occupation_publications SET approved_score_snapshot_id=NULL
          WHERE approved_score_snapshot_id IN (
            SELECT id FROM production_occupation_score_snapshots WHERE promotion_run_id=:run)
        """), {"run": run["run_id"]})
        for identity_id, status in previous_status.items():
            await session.execute(text("""
              UPDATE occupation_publications SET activation_status=:status
              WHERE identity_id=:id AND locale='en' AND source_geography='US'
            """), {"status": status, "id": identity_id})
        if created_publications:
            await session.execute(
                text("DELETE FROM occupation_publications WHERE identity_id = ANY(:ids)"),
                {"ids": created_publications},
            )
        if created_import_run is not None:
            await session.execute(
                text("DELETE FROM import_runs WHERE id=:id"), {"id": created_import_run}
            )

    # Snapshots survive by design; withdrawing them is a rollback, never a delete.
    await roll_back_run(run["run_id"], "pytest session teardown")
