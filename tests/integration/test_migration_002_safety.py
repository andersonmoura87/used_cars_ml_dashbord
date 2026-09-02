"""Segurança não destrutiva da migration 002 em PostgreSQL real."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from scripts.run_migration import run_migration
from tests.integration.test_etl_postgresql import _database_url, _require_integration


pytestmark = pytest.mark.integration
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "sql"
    / "migrations"
    / "002_unify_api_etl_schema.sql"
)


@pytest.fixture(scope="module")
def migration_engine():
    _require_integration()
    url = _database_url()
    schema = f"migration_002_safety_{uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        url,
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
def legacy_schema(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS market_stats, cars CASCADE"))
        connection.execute(
            text("CREATE TABLE cars (id SERIAL PRIMARY KEY, original_id TEXT)")
        )
        connection.execute(
            text(
                "CREATE TABLE market_stats ("
                "id SERIAL PRIMARY KEY, manufacturer TEXT, model TEXT, year INTEGER, "
                "avg_price DOUBLE PRECISION)"
            )
        )


def _rows(engine, table: str):
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings().all()


def test_duplicate_original_id_aborts_without_changing_cars(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO cars (original_id) VALUES ('same-id'), ('same-id'), ('other-id')")
        )
    before = _rows(migration_engine, "cars")

    with pytest.raises(SQLAlchemyError, match="CARS_DUPLICATE_ORIGINAL_ID"):
        run_migration(migration_engine, MIGRATION)

    assert _rows(migration_engine, "cars") == before
    assert {column["name"] for column in inspect(migration_engine).get_columns("cars")} == {
        "id",
        "original_id",
    }


def test_duplicate_market_stats_aborts_without_deleting_data(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO market_stats (manufacturer, model, year, avg_price) VALUES "
                "('toyota', 'corolla', 2020, 100.0), "
                "('toyota', 'corolla', 2020, 200.0)"
            )
        )
    before = _rows(migration_engine, "market_stats")

    with pytest.raises(SQLAlchemyError, match="MARKET_STATS_DUPLICATE_KEY"):
        run_migration(migration_engine, MIGRATION)

    assert _rows(migration_engine, "market_stats") == before


def test_valid_data_applies_both_unique_indexes(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO cars (original_id) VALUES ('car-1'), (NULL)"))
        connection.execute(
            text(
                "INSERT INTO market_stats (manufacturer, model, year) "
                "VALUES ('toyota', 'corolla', 2020)"
            )
        )

    run_migration(migration_engine, MIGRATION)

    car_indexes = {item["name"] for item in inspect(migration_engine).get_indexes("cars")}
    stats_indexes = {
        item["name"] for item in inspect(migration_engine).get_indexes("market_stats")
    }
    assert "uq_cars_original_id" in car_indexes
    assert "uq_market_stats_main" in stats_indexes


def test_duplicate_original_id_is_rejected_after_migration(migration_engine):
    run_migration(migration_engine, MIGRATION)
    sessions = sessionmaker(bind=migration_engine)
    session = sessions()
    try:
        session.execute(text("INSERT INTO cars (original_id) VALUES ('car-1')"))
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(text("INSERT INTO cars (original_id) VALUES ('car-1')"))
            session.flush()
        session.rollback()
    finally:
        session.close()


def test_duplicate_market_stats_is_rejected_after_migration(migration_engine):
    run_migration(migration_engine, MIGRATION)
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO market_stats (manufacturer, model, year) "
                "VALUES ('toyota', 'corolla', 2020)"
            )
        )
    with pytest.raises(IntegrityError):
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO market_stats (manufacturer, model, year) "
                    "VALUES ('toyota', 'corolla', 2020)"
                )
            )


def test_null_market_stats_key_aborts_without_modification(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO market_stats (manufacturer, model, year, avg_price) "
                "VALUES ('toyota', NULL, 2020, 123.0)"
            )
        )
    before = _rows(migration_engine, "market_stats")

    with pytest.raises(SQLAlchemyError, match="MARKET_STATS_NULL_KEY"):
        run_migration(migration_engine, MIGRATION)

    assert _rows(migration_engine, "market_stats") == before
