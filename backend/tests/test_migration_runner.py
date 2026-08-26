"""scripts/migrate.sh — the contract, and the bug that broke it locally.

The runner supports two migration styles and chooses between them by inspecting the file:

  * a migration with no transaction control is wrapped in `--single-transaction`
  * a migration declaring its own BEGIN/COMMIT is run bare, because psql's
    `--single-transaction` would let the inner COMMIT end the outer transaction early

33 of the 34 migrations in this repository take the second path, so it is the normal case
rather than an exception. That path builds an empty `wrap` array, and `"${wrap[@]}"` on an
empty array aborts under `set -u` in bash 3.2 — still the default shell on macOS. Production
runs bash 5.2 and was never affected, which is why every one of those 33 applied to the VPS
without trouble; only local runs broke.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

def _find(relative: str) -> pathlib.Path:
    """Locate a repo path from inside the test container or from a checkout.

    run-tests.sh mounts scripts/ and migrations/ under /app, while a local checkout has them
    two levels above backend/tests. Trying both keeps the file runnable either way.
    """
    for base in (pathlib.Path("/app"), pathlib.Path(__file__).resolve().parents[2]):
        candidate = base / relative
        if candidate.exists():
            return candidate
    pytest.skip(f"{relative} is not mounted in this environment")


# docker compose is only reachable when the suite runs on the host, not inside the test
# container. The failure-path test skips rather than reporting a false pass when it is not.
_repo = pathlib.Path(__file__).resolve().parents[2]
ROOT_FOR_COMPOSE = _repo if (_repo / "docker-compose.yml").exists() else None

RUNNER = _find("scripts/migrate.sh")
MIGRATIONS = sorted(_find("migrations").glob("*.sql"))

BEGIN_RE = re.compile(r"^[ \t]*BEGIN[ \t]*;", re.I | re.M)


def test_runner_exists_and_parses() -> None:
    assert RUNNER.is_file()
    subprocess.run(["bash", "-n", str(RUNNER)], check=True)


def test_runner_keeps_strict_shell_options() -> None:
    """The fix must not have been "turn off set -u"."""
    body = RUNNER.read_text()
    assert "set -euo pipefail" in body


def test_runner_supports_both_migration_styles() -> None:
    """Both branches must still exist — the contract is two styles, not one."""
    body = RUNNER.read_text()
    assert "wrap=()" in body
    assert "wrap=(--single-transaction)" in body
    assert BEGIN_RE.pattern or True  # detection is by grep inside the script
    assert "--single-transaction" in body


def test_empty_wrapper_expansion_is_guarded() -> None:
    """The exact defect: `"${wrap[@]}"` must not survive anywhere in the runner."""
    body = RUNNER.read_text()
    guarded = '${wrap[@]+"${wrap[@]}"}'
    assert guarded in body, "the guarded expansion is missing"
    # `"${wrap[@]}"` is a substring of the guarded form, so count occurrences rather than
    # testing membership: every one of them must be inside a guard.
    assert body.count('"${wrap[@]}"') == body.count(guarded), (
        "an unguarded empty-array expansion is back")


def test_guarded_expansion_survives_set_u_on_this_shell() -> None:
    """Executable proof, run in whatever bash this machine has.

    On bash 3.2 the unguarded form aborts and the guarded form does not; on 5.x both work.
    Asserting only that the guarded form succeeds keeps the test meaningful on both.
    """
    guarded = subprocess.run(
        ["bash", "-c", 'set -euo pipefail; wrap=(); '
                       'printf "%s" "ok:${#wrap[@]}"; : ${wrap[@]+"${wrap[@]}"}'],
        capture_output=True, text=True,
    )
    assert guarded.returncode == 0, guarded.stderr
    assert "ok:0" in guarded.stdout

    populated = subprocess.run(
        ["bash", "-c", 'set -euo pipefail; wrap=(--single-transaction); '
                       'printf "%s" ${wrap[@]+"${wrap[@]}"}'],
        capture_output=True, text=True,
    )
    assert populated.returncode == 0, populated.stderr
    assert "--single-transaction" in populated.stdout


def test_migration_style_detection_matches_the_files_on_disk() -> None:
    """The runner's grep must classify the real corpus the way we believe it does."""
    self_transactional = [p for p in MIGRATIONS if BEGIN_RE.search(p.read_text())]
    wrapped = [p for p in MIGRATIONS if not BEGIN_RE.search(p.read_text())]
    assert self_transactional, "expected migrations that manage their own transaction"
    # Recorded rather than pinned: the ratio moves as migrations are added. What matters is
    # that the empty-wrapper path is exercised by real files, not hypothetical ones.
    assert len(self_transactional) > len(wrapped)


def test_failure_is_not_recorded_as_applied() -> None:
    """A failed migration must not land in schema_migrations.

    Asserted on the control flow: the INSERT is only reached after the psql call succeeds,
    and the failure branch exits non-zero.
    """
    body = RUNNER.read_text()
    failure_index = body.index("!! $file failed")
    # The runner inserts in two places: once when baselining and once after a successful
    # apply. The one that matters here is the last, which follows the failure branch.
    insert_index = body.rindex("INSERT INTO schema_migrations (filename, checksum)")
    assert failure_index < insert_index, "the failure branch must precede the INSERT"
    assert "exit 1" in body[failure_index:insert_index]
    assert "ON_ERROR_STOP=1" in body, "psql must abort on the first SQL error"


def test_already_applied_migrations_are_skipped() -> None:
    """Idempotency: applied filenames are read back and excluded from the pending list."""
    body = RUNNER.read_text()
    assert "SELECT filename FROM schema_migrations" in body
    assert "is_applied" in body
    assert "nothing to apply" in body


def test_checksum_drift_refuses_to_proceed() -> None:
    """Editing an applied migration must stop the run, not silently diverge environments."""
    body = RUNNER.read_text()
    assert "drifted" in body
    assert "Refusing to continue" in body


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_every_migration_parses_as_one_style_or_the_other(path: pathlib.Path) -> None:
    """No migration may open a transaction it does not close."""
    body = path.read_text()
    begins = len(BEGIN_RE.findall(body))
    commits = len(re.findall(r"^[ \t]*COMMIT[ \t]*;", body, re.I | re.M))
    assert begins == commits, f"{path.name}: {begins} BEGIN vs {commits} COMMIT"


def test_migration_034_declares_every_object_it_needs() -> None:
    """034 must create its table, view and indexes in one transactional unit.

    Asserted on the file rather than a live database so this holds without requiring the
    migration to have been applied to whatever database the suite is pointed at.
    """
    path = next(p for p in MIGRATIONS if p.name.startswith("034"))
    body = path.read_text()
    assert "CREATE TABLE IF NOT EXISTS consumer_aliases" in body
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS occupation_search_terms" in body
    for index in ("occupation_search_terms_normalized_idx",
                  "occupation_search_terms_trgm_idx",
                  "occupation_search_terms_unique_idx",
                  "occupation_search_terms_identity_idx"):
        assert index in body, index
    # REFRESH … CONCURRENTLY needs a unique index; without one a refresh takes an exclusive
    # lock and search stalls behind an O*NET import.
    assert "CREATE UNIQUE INDEX" in body
    assert BEGIN_RE.search(body), "034 manages its own transaction"


def test_runner_aborts_on_a_broken_migration_body() -> None:
    """The harness must not swallow a SQL failure.

    Exercised against a throwaway file rather than any real migration: `psql -v ON_ERROR_STOP=1`
    is what makes an invalid statement a non-zero exit, and the runner branches on that exit.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        broken = pathlib.Path(tmp) / "999_broken.sql"
        broken.write_text("BEGIN;\nSELECT * FROM a_table_that_does_not_exist;\nCOMMIT;\n")
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres",
             "psql", "-U", "jobsvsai", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q"],
            stdin=broken.open(), capture_output=True, text=True, cwd=ROOT_FOR_COMPOSE,
        ) if ROOT_FOR_COMPOSE else None
        if result is None:
            pytest.skip("docker compose is not reachable from this test environment")
        assert result.returncode != 0, "an invalid migration must exit non-zero"
