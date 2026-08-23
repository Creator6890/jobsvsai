"""Apply the same test-database guard the backend suite uses.

`test_onet_database.py` connects with asyncpg directly rather than through
`app.db.session`, so it bypasses the backend conftest entirely. Without this module a
developer running `pytest ingestion/tests` would reach whatever `DATABASE_URL` points at —
the same hole that let fixture rows into the development database.

The guard module ships at /app/tests/db_guard.py in the backend image; when it is not
importable (running this package outside that image) the import failure is deliberate
rather than a silent fallback to an unguarded connection.
"""

from tests.db_guard import resolve_target

TEST_DATABASE_TARGET = resolve_target()


def pytest_report_header() -> list[str]:
    return [f"test database: {TEST_DATABASE_TARGET.describe()}"]
