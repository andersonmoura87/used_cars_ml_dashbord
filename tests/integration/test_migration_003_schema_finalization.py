"""Convergência não destrutiva da migration 003 em PostgreSQL real."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from scripts.run_migration import run_migration
from tests.integration.test_etl_postgresql import _database_url, _require_integration


pytestmark = pytest.mark.integration
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "sql"
    / "migrations"
    / "003_finalize_car_financing_and_price_history.sql"
)


@pytest.fixture
def migration_engine():
    _require_integration()
    url = _database_url()
    schema = f"migration_003_{uuid4().hex}"
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


def _create_cars(engine, *, nullable=True):
    nullability = "" if nullable else " NOT NULL"
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE cars ("
                "id BIGSERIAL PRIMARY KEY, "
                f"has_installments BOOLEAN{nullability} DEFAULT FALSE)"
            )
        )


def _create_existing_history(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE price_history ("
                "id BIGSERIAL PRIMARY KEY, "
                "car_id BIGINT NOT NULL, "
                "price DOUBLE PRECISION, "
                "recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)"
            )
        )


def _history_rows(engine):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id, car_id, price, recorded_at FROM price_history ORDER BY id")
        ).mappings().all()


def test_normalizes_only_null_installment_values_and_enforces_contract(
    migration_engine,
):
    _create_cars(migration_engine)
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cars (has_installments) VALUES "
                "(TRUE), (FALSE), (NULL)"
            )
        )

    assert run_migration(migration_engine, MIGRATION) is True

    with migration_engine.connect() as connection:
        values = connection.execute(
            text("SELECT has_installments FROM cars ORDER BY id")
        ).scalars().all()
    column = {
        item["name"]: item for item in inspect(migration_engine).get_columns("cars")
    }["has_installments"]
    assert values == [True, False, False]
    assert column["nullable"] is False
    assert "false" in str(column["default"]).lower()


def test_creates_versioned_price_history_schema(migration_engine):
    _create_cars(migration_engine)
    run_migration(migration_engine, MIGRATION)

    schema = inspect(migration_engine)
    columns = {item["name"]: item for item in schema.get_columns("price_history")}
    assert str(columns["id"]["type"]) == "BIGINT"
    assert str(columns["car_id"]["type"]) == "BIGINT"
    assert columns["car_id"]["nullable"] is False
    assert str(columns["price"]["type"]) == "DOUBLE PRECISION"
    assert columns["recorded_at"]["type"].timezone is True
    assert columns["recorded_at"]["default"] is not None

    foreign_key = schema.get_foreign_keys("price_history")[0]
    assert foreign_key["referred_table"] == "cars"
    assert foreign_key["referred_columns"] == ["id"]
    assert foreign_key["options"]["ondelete"] == "CASCADE"
    indexes = {item["name"]: item for item in schema.get_indexes("price_history")}
    assert indexes["idx_car_price_date"]["column_names"] == [
        "car_id",
        "price",
        "recorded_at",
    ]


def test_existing_valid_history_is_preserved_and_completed(migration_engine):
    _create_cars(migration_engine)
    _create_existing_history(migration_engine)
    with migration_engine.begin() as connection:
        car_id = connection.execute(
            text("INSERT INTO cars (has_installments) VALUES (TRUE) RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO price_history (car_id, price) "
                "VALUES (:car_id, 12345.0)"
            ),
            {"car_id": car_id},
        )
    before = _history_rows(migration_engine)

    run_migration(migration_engine, MIGRATION)

    assert _history_rows(migration_engine) == before
    assert len(inspect(migration_engine).get_foreign_keys("price_history")) == 1
    assert "idx_car_price_date" in {
        item["name"] for item in inspect(migration_engine).get_indexes("price_history")
    }


def test_orphan_aborts_and_transaction_preserves_all_legacy_state(migration_engine):
    _create_cars(migration_engine)
    _create_existing_history(migration_engine)
    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO cars (has_installments) VALUES (NULL)"))
        connection.execute(
            text("INSERT INTO price_history (car_id, price) VALUES (999999, 10.0)")
        )
    before = _history_rows(migration_engine)

    with pytest.raises(SQLAlchemyError, match="PRICE_HISTORY_ORPHAN_CAR_ID"):
        run_migration(migration_engine, MIGRATION)

    assert _history_rows(migration_engine) == before
    with migration_engine.connect() as connection:
        assert connection.execute(
            text("SELECT has_installments FROM cars")
        ).scalar_one() is None
    cars_column = {
        item["name"]: item for item in inspect(migration_engine).get_columns("cars")
    }["has_installments"]
    assert cars_column["nullable"] is True
    assert not inspect(migration_engine).has_table("schema_migrations")


def test_second_runner_execution_skips_without_duplicate_objects(migration_engine):
    _create_cars(migration_engine)
    assert run_migration(migration_engine, MIGRATION) is True
    first_foreign_keys = inspect(migration_engine).get_foreign_keys("price_history")
    first_indexes = inspect(migration_engine).get_indexes("price_history")

    assert run_migration(migration_engine, MIGRATION) is False

    assert inspect(migration_engine).get_foreign_keys("price_history") == first_foreign_keys
    assert inspect(migration_engine).get_indexes("price_history") == first_indexes
    with migration_engine.connect() as connection:
        history = connection.execute(
            text(
                "SELECT filename, checksum_sha256 FROM schema_migrations "
                "WHERE filename = 'migrations/003_finalize_car_financing_and_price_history.sql'"
            )
        ).mappings().all()
    assert len(history) == 1
    assert len(history[0]["checksum_sha256"].strip()) == 64


def test_existing_integer_identity_is_widened_without_losing_rows(migration_engine):
    _create_cars(migration_engine)
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE price_history ("
                "id SERIAL PRIMARY KEY, car_id INTEGER NOT NULL, price REAL, "
                "recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, "
                "CONSTRAINT legacy_history_car_fk FOREIGN KEY (car_id) "
                "REFERENCES cars(id) ON DELETE CASCADE)"
            )
        )
        car_id = connection.execute(
            text("INSERT INTO cars (has_installments) VALUES (FALSE) RETURNING id")
        ).scalar_one()
        connection.execute(
            text("INSERT INTO price_history (car_id, price) VALUES (:car_id, 42.5)"),
            {"car_id": car_id},
        )

    before = _history_rows(migration_engine)
    run_migration(migration_engine, MIGRATION)

    columns = {
        item["name"]: item
        for item in inspect(migration_engine).get_columns("price_history")
    }
    assert _history_rows(migration_engine) == before
    assert str(columns["id"]["type"]) == "BIGINT"
    assert str(columns["car_id"]["type"]) == "BIGINT"
    assert str(columns["price"]["type"]) == "DOUBLE PRECISION"


def test_ambiguous_timestamp_type_aborts_without_partial_changes(migration_engine):
    _create_cars(migration_engine)
    with migration_engine.begin() as connection:
        car_id = connection.execute(
            text("INSERT INTO cars (has_installments) VALUES (NULL) RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "CREATE TABLE price_history ("
                "id BIGSERIAL PRIMARY KEY, car_id BIGINT NOT NULL, "
                "price DOUBLE PRECISION, recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text("INSERT INTO price_history (car_id, price) VALUES (:car_id, 9.0)"),
            {"car_id": car_id},
        )
    before = _history_rows(migration_engine)

    with pytest.raises(SQLAlchemyError, match="PRICE_HISTORY_COLUMNS_OR_TYPES"):
        run_migration(migration_engine, MIGRATION)

    assert _history_rows(migration_engine) == before
    with migration_engine.connect() as connection:
        assert connection.execute(
            text("SELECT has_installments FROM cars")
        ).scalar_one() is None
    recorded_at = {
        item["name"]: item
        for item in inspect(migration_engine).get_columns("price_history")
    }["recorded_at"]
    assert recorded_at["type"].timezone is False
