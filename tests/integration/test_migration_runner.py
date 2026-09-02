"""Histórico, atomicidade e locking do migration runner em PostgreSQL real."""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from scripts.run_migration import MigrationChecksumMismatch, run_migration
from tests.integration.test_etl_postgresql import _database_url, _require_integration


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def runner_engine():
    _require_integration()
    url = _database_url()
    schema = f"migration_runner_{uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        url,
        pool_size=4,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"options": f"-c search_path={schema}"},
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def empty_runner_schema(runner_engine):
    with runner_engine.begin() as connection:
        tables = inspect(connection).get_table_names()
        for table in tables:
            connection.execute(text(f'DROP TABLE "{table}" CASCADE'))


def _write(tmp_path: Path, filename: str, sql: str) -> Path:
    migration = tmp_path / filename
    migration.write_text(sql, encoding="utf-8")
    return migration


def _history(engine):
    if not inspect(engine).has_table("schema_migrations"):
        return []
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT filename, checksum_sha256, duration_ms, runner_version "
                "FROM schema_migrations ORDER BY filename"
            )
        ).mappings().all()


def test_first_run_executes_and_records_history(runner_engine, tmp_path):
    migration = _write(tmp_path, "001_first.sql", "CREATE TABLE first_run (id INTEGER);")

    assert run_migration(runner_engine, migration) is True

    assert inspect(runner_engine).has_table("first_run")
    history = _history(runner_engine)
    assert len(history) == 1
    assert history[0]["filename"] == f"external/{migration.name}"
    assert len(history[0]["checksum_sha256"].strip()) == 64
    assert history[0]["duration_ms"] >= 0
    assert history[0]["runner_version"] == "1"


def test_second_run_with_same_checksum_is_skipped(runner_engine, tmp_path):
    migration = _write(tmp_path, "001_once.sql", "CREATE TABLE run_once (id INTEGER);")
    assert run_migration(runner_engine, migration) is True

    assert run_migration(runner_engine, migration) is False

    assert len(_history(runner_engine)) == 1


def test_modified_applied_migration_fails(runner_engine, tmp_path):
    migration = _write(tmp_path, "001_checksum.sql", "CREATE TABLE checksum_a (id INTEGER);")
    run_migration(runner_engine, migration)
    migration.write_text("CREATE TABLE checksum_b (id INTEGER);", encoding="utf-8")

    with pytest.raises(MigrationChecksumMismatch, match="was modified"):
        run_migration(runner_engine, migration)

    assert inspect(runner_engine).has_table("checksum_a")
    assert not inspect(runner_engine).has_table("checksum_b")
    assert len(_history(runner_engine)) == 1


def test_failed_migration_rolls_back_and_is_not_recorded(runner_engine, tmp_path):
    migration = _write(
        tmp_path,
        "001_failure.sql",
        "CREATE TABLE rolled_back (id INTEGER); SELECT * FROM missing_table;",
    )

    with pytest.raises(SQLAlchemyError):
        run_migration(runner_engine, migration)

    assert not inspect(runner_engine).has_table("rolled_back")
    assert _history(runner_engine) == []


def test_first_migration_remains_when_second_fails(runner_engine, tmp_path):
    first = _write(tmp_path, "001_good.sql", "CREATE TABLE good_one (id INTEGER);")
    second = _write(
        tmp_path,
        "002_bad.sql",
        "CREATE TABLE bad_two (id INTEGER); SELECT * FROM missing_table;",
    )
    run_migration(runner_engine, first)

    with pytest.raises(SQLAlchemyError):
        run_migration(runner_engine, second)

    assert inspect(runner_engine).has_table("good_one")
    assert not inspect(runner_engine).has_table("bad_two")
    assert [row["filename"] for row in _history(runner_engine)] == [
        f"external/{first.name}"
    ]


def test_advisory_lock_prevents_double_application(runner_engine, tmp_path):
    migration = _write(
        tmp_path,
        "001_concurrent.sql",
        "SELECT pg_sleep(0.5); CREATE TABLE concurrent_once (id INTEGER);",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_migration(runner_engine, migration), range(2)))

    assert sorted(results) == [False, True]
    assert len(_history(runner_engine)) == 1
    assert inspect(runner_engine).has_table("concurrent_once")


def test_sql_error_stops_before_later_statement(runner_engine, tmp_path):
    migration = _write(
        tmp_path,
        "001_stop.sql",
        "SELECT * FROM missing_table; SELECT pg_sleep(3);",
    )
    started_at = time.perf_counter()

    with pytest.raises(SQLAlchemyError):
        run_migration(runner_engine, migration)

    assert time.perf_counter() - started_at < 2
    assert _history(runner_engine) == []


def test_full_file_supports_procedural_blocks_and_internal_semicolons(
    runner_engine,
    tmp_path,
):
    migration = _write(
        tmp_path,
        "001_procedural.sql",
        """
        DO $$
        BEGIN
            CREATE TABLE procedural_sql (value TEXT);
            INSERT INTO procedural_sql (value) VALUES ('inside;value');
        END
        $$;
        """,
    )

    assert run_migration(runner_engine, migration) is True

    with runner_engine.connect() as connection:
        value = connection.execute(text("SELECT value FROM procedural_sql")).scalar_one()
    assert value == "inside;value"


def test_existing_database_without_history_executes_then_skips_safe_migration(
    runner_engine,
    tmp_path,
):
    with runner_engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy_existing (id INTEGER)"))
    migration = _write(
        tmp_path,
        "001_bootstrap.sql",
        "CREATE TABLE IF NOT EXISTS legacy_existing (id INTEGER);",
    )

    assert not inspect(runner_engine).has_table("schema_migrations")
    assert run_migration(runner_engine, migration) is True
    assert run_migration(runner_engine, migration) is False

    history = _history(runner_engine)
    assert [row["filename"] for row in history] == ["external/001_bootstrap.sql"]
