"""Regressões do ETL executadas contra um PostgreSQL real.

Execute com ``INTEGRATION_DB=1`` e as variáveis ``TEST_DB_*`` (preferidas) ou
``DB_*`` configuradas. Cada sessão de testes usa um schema temporário próprio.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import patch
from urllib.parse import quote_plus
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Car, PriceHistory
from src.etl.load import load_data


pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.getenv("INTEGRATION_DB", "").strip().lower() in {"1", "true", "yes", "on"}


def _require_integration() -> None:
    if not _enabled():
        pytest.skip("Defina INTEGRATION_DB=1 para rodar contra PostgreSQL real")


def _database_url() -> str:
    user = os.getenv("TEST_DB_USER") or os.getenv("DB_USER", "postgres")
    password = os.getenv("TEST_DB_PASSWORD") or os.getenv("DB_PASSWORD")
    host = os.getenv("TEST_DB_HOST") or os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT") or os.getenv("DB_PORT", "5432")
    name = os.getenv("TEST_DB_NAME") or os.getenv("DB_NAME", "used_cars")
    if not password:
        pytest.fail(
            "PostgreSQL integration requested but database credentials are incomplete",
            pytrace=False,
        )
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"


def _setup_postgres_sessions():
    """Cria um schema isolado; falhas são fatais após o opt-in da integração."""
    url = _database_url()
    schema = f"etl_integration_{uuid4().hex}"
    admin_engine = None
    engine = None
    try:
        admin_engine = create_engine(url, pool_pre_ping=True)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-c search_path={schema}"},
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return factory, engine, admin_engine, schema
    except Exception as exc:
        if engine is not None:
            engine.dispose()
        if admin_engine is not None:
            admin_engine.dispose()
        pytest.fail(
            "PostgreSQL integration requested but database is unavailable: "
            f"{type(exc).__name__}",
            pytrace=False,
        )


@pytest.fixture(scope="module")
def postgres_sessions():
    _require_integration()
    factory, engine, admin_engine, schema = _setup_postgres_sessions()
    try:
        yield factory
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def empty_postgres_schema(postgres_sessions):
    session = postgres_sessions()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


def _cars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "original_id": ["pg-etl-001"],
            "url": ["https://example.test/pg-etl-001"],
            "region": ["sao-paulo"],
            "manufacturer": ["toyota"],
            "model": ["corolla"],
            "year": [2020],
            "price": [100_000.0],
            "price_original": [105_000.0],
            "odometer": [40_000.0],
            "fuel": ["gas"],
            "transmission": ["automatic"],
            "drive": ["fwd"],
            "type": ["sedan"],
            "paint_color": ["white"],
            "condition": ["good"],
            "cylinders": ["4 cylinders"],
            "title_status": ["clean"],
            "vin": ["PGTEST00000000001"],
            "size": ["mid-size"],
            "state": ["sp"],
            "latitude": [-23.55],
            "longitude": [-46.63],
            "posting_date": [datetime(2026, 1, 1)],
            "vehicle_age": [6],
            "has_installments": [False],
            "monthly_payment": [None],
            "down_payment": [None],
            "installments": [None],
        }
    )


def _market_stats() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "manufacturer": ["toyota"],
            "model": ["corolla"],
            "year": [2020],
            "avg_price": [100_000.0],
            "median_price": [100_000.0],
            "min_price": [90_000.0],
            "max_price": [110_000.0],
            "total_listings": [1],
            "days_listed": [10.0],
            "calculated_at": [datetime(2026, 1, 1)],
        }
    )


def _load(factory, cars: pd.DataFrame) -> None:
    with patch("src.etl.load.create_database_schema"), patch(
        "src.etl.load.get_db_session", side_effect=factory
    ):
        load_data(cars, _market_stats())


def _car_state(factory) -> tuple[int, float, int]:
    session = factory()
    try:
        car = session.execute(select(Car)).scalar_one()
        history_count = session.scalar(select(func.count()).select_from(PriceHistory))
        return car.id, car.price, history_count
    finally:
        session.close()


def test_consecutive_loads_preserve_id_and_do_not_duplicate_history(postgres_sessions):
    cars = _cars()
    _load(postgres_sessions, cars)
    first_state = _car_state(postgres_sessions)
    _load(postgres_sessions, cars.copy(deep=True))
    second_state = _car_state(postgres_sessions)
    assert second_state == first_state
    assert second_state[2] == 0


def test_price_change_creates_exactly_one_history(postgres_sessions):
    cars = _cars()
    _load(postgres_sessions, cars)
    original_id, _, _ = _car_state(postgres_sessions)
    changed = cars.copy(deep=True)
    changed.loc[0, "price"] = 95_000.0
    _load(postgres_sessions, changed)
    _load(postgres_sessions, changed.copy(deep=True))
    car_id, price, history_count = _car_state(postgres_sessions)
    assert car_id == original_id
    assert price == 95_000.0
    assert history_count == 1


def test_duplicate_input_fails_before_database_mutation(postgres_sessions):
    _load(postgres_sessions, _cars())
    before = _car_state(postgres_sessions)
    duplicate = pd.concat([_cars(), _cars()], ignore_index=True)
    duplicate.loc[:, "price"] = 1.0
    with pytest.raises(ValueError, match="duplicado"):
        _load(postgres_sessions, duplicate)
    assert _car_state(postgres_sessions) == before


def test_failure_before_commit_rolls_back_everything(postgres_sessions):
    _load(postgres_sessions, _cars())
    before = _car_state(postgres_sessions)
    changed = _cars()
    changed.loc[0, "price"] = 80_000.0
    with patch("src.etl.load.create_database_schema"), patch(
        "src.etl.load.get_db_session", side_effect=postgres_sessions
    ), patch("src.etl.load.load_market_stats", side_effect=RuntimeError("injected")):
        with pytest.raises(RuntimeError, match="injected"):
            load_data(changed, _market_stats())
    assert _car_state(postgres_sessions) == before


def test_postgresql_unique_constraint_rejects_duplicate_original_id(postgres_sessions):
    _load(postgres_sessions, _cars())
    session = postgres_sessions()
    try:
        session.add(Car(original_id="pg-etl-001", price=1.0))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(Car)) == 1
    finally:
        session.close()
