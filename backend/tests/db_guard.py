"""Refuse to open a test connection against anything but a dedicated test database.

Background: the suite builds a production score store from fixtures — promotion runs,
snapshots, factor and task contributions — and flips `occupation_publications` rows to
exercise the publication gate. Those writes are correct against a disposable database and
unacceptable against the development database that holds the promoted Phase 6 state. The
suite historically had no opinion about which database it was given: `conftest` imported
`app.db.session.SessionFactory`, which resolves `DATABASE_URL` from the environment, and
`docker compose run backend pytest` supplies the development URL. Fixture rows accumulated
in the real database as a result.

The guard runs at import time, before SQLAlchemy is asked for a connection, and applies
four independent checks. They are deliberately not variations on one string comparison:

1. `TEST_DATABASE=true` must be set. An explicit opt-in that no normal service sets.
2. `ENVIRONMENT` must not name production.
3. The database name in the URL must look like a test database and must not be one of the
   known non-test names.
4. The database itself must contain the marker table `test_database_marker`. This is the
   only check that survives a lie in the environment: a URL can claim any name, but the
   marker exists only in a database that `scripts/create-test-db.sh` created.

Check 4 needs a connection, so it runs from an async session fixture rather than at import.
Checks 1-3 have already refused anything obviously wrong by then.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

MARKER_ENV = "TEST_DATABASE"
MARKER_TABLE = "test_database_marker"

# Names that must never be used for tests, whatever else the environment claims.
FORBIDDEN_DATABASE_NAMES = frozenset({"jobsvsai", "postgres", "template0", "template1"})

# A test database identifies itself in its own name.
TEST_NAME_PATTERN = re.compile(r"(?:^test_|_test$|_test_)")

PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "live", "staging"})


class UnsafeTestDatabase(RuntimeError):
    """Raised when the configured database is not provably a disposable test database."""


@dataclass(frozen=True)
class DatabaseTarget:
    """What the tests resolved to, with no credentials retained."""

    host: str
    port: int | None
    database: str
    environment: str
    driver: str

    def describe(self) -> str:
        port = f":{self.port}" if self.port else ""
        return (
            f"host={self.host}{port} database={self.database} "
            f"environment={self.environment} driver={self.driver}"
        )


def _parse(url: str) -> tuple[str, int | None, str, str]:
    """Split a SQLAlchemy URL into host/port/database/driver, discarding credentials."""
    split = urlsplit(url)
    database = split.path.lstrip("/")
    if not database:
        raise UnsafeTestDatabase(
            "DATABASE_URL names no database. Refusing to run tests against a server default."
        )
    return split.hostname or "", split.port, database, split.scheme


def resolve_target(url: str | None = None, environment: str | None = None) -> DatabaseTarget:
    """Apply checks 1-3 and return the target. Never returns for an unsafe configuration."""
    url = url if url is not None else os.getenv("DATABASE_URL", "")
    environment = environment if environment is not None else os.getenv("ENVIRONMENT", "")

    if not url:
        raise UnsafeTestDatabase(
            "DATABASE_URL is unset. The test suite requires an explicit test database; it "
            "will not fall back to an application default."
        )

    # 1. Explicit opt-in.
    marker = os.getenv(MARKER_ENV, "")
    if marker.strip().lower() != "true":
        raise UnsafeTestDatabase(
            f"{MARKER_ENV} is not 'true' (got {marker!r}). The test suite writes fixture "
            f"promotion runs and mutates publication rows, so it refuses to start without "
            f"this explicit acknowledgement that the target database is disposable. Use "
            f"the documented test command rather than setting this by hand against a "
            f"development database."
        )

    # 2. Never production.
    if environment.strip().lower() in PRODUCTION_ENVIRONMENTS:
        raise UnsafeTestDatabase(
            f"ENVIRONMENT={environment!r} names a protected environment. Tests are refused."
        )

    host, port, database, driver = _parse(url)

    # 3. The name must identify itself as a test database, and must not be a known real one.
    if database.lower() in FORBIDDEN_DATABASE_NAMES:
        raise UnsafeTestDatabase(
            f"Refusing to run tests against database {database!r}: it is a known "
            f"non-test database. Expected a dedicated test database such as 'jobsvsai_test'."
        )
    if not TEST_NAME_PATTERN.search(database.lower()):
        raise UnsafeTestDatabase(
            f"Database name {database!r} does not identify itself as a test database. "
            f"Expected a name matching {TEST_NAME_PATTERN.pattern} — e.g. 'jobsvsai_test'."
        )

    return DatabaseTarget(
        host=host, port=port, database=database, environment=environment or "(unset)", driver=driver
    )


async def assert_marker_table(session) -> str:
    """Check 4: the database itself must carry the marker written at creation time.

    This is the check that cannot be satisfied by lying in the environment. Returns the
    marker's recorded label for reporting.
    """
    from sqlalchemy import text

    exists = (await session.execute(text(
        "SELECT to_regclass(:name) IS NOT NULL"
    ), {"name": f"public.{MARKER_TABLE}"})).scalar_one()
    if not exists:
        raise UnsafeTestDatabase(
            f"The connected database has no {MARKER_TABLE!r} table. Only a database created "
            f"by scripts/create-test-db.sh carries this marker, so this connection is not "
            f"the isolated test database — regardless of what its name or the environment "
            f"claims. Refusing to run tests."
        )
    label = (await session.execute(text(
        f"SELECT label FROM {MARKER_TABLE} ORDER BY created_at DESC LIMIT 1"
    ))).scalar_one_or_none()
    if not label:
        raise UnsafeTestDatabase(
            f"{MARKER_TABLE!r} exists but is empty. Refusing to run tests against a database "
            f"whose test provenance cannot be confirmed."
        )
    return label
