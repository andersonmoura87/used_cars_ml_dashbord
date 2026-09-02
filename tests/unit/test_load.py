"""Testes do ETL de carga, incluindo idempotência contra banco real em memória."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Car, PriceHistory
from src.etl.load import (
    create_database_schema,
    create_price_history,
    load_cars_data,
    load_data,
    load_market_stats,
)


def _clean_cars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "original_id": [str(7300000000 + i) for i in range(n)],
        "url": [f"https://example.test/car/{i}" for i in range(n)],
        "region": ["bay area"] * n,
        "manufacturer": ["toyota"] * n,
        "model": [f"corolla-{i}" for i in range(n)],
        "year": [2018] * n,
        "price": [15000.0 + i for i in range(n)],
        "price_original": [15000.0 + i for i in range(n)],
        "odometer": [40000 + i for i in range(n)],
        "fuel": ["gas"] * n,
        "transmission": ["automatic"] * n,
        "drive": ["fwd"] * n,
        "type": ["sedan"] * n,
        "paint_color": ["white"] * n,
        "condition": ["good"] * n,
        "cylinders": ["4 cylinders"] * n,
        "title_status": ["clean"] * n,
        "vin": [f"VIN{i:014d}" for i in range(n)],
        "size": ["mid-size"] * n,
        "state": ["ca"] * n,
        "latitude": [37.0] * n,
        "longitude": [-122.0] * n,
        "posting_date": pd.to_datetime(["2024-01-01"] * n),
        "vehicle_age": [6] * n,
        "has_installments": [False] * n,
        "monthly_payment": [None] * n,
        "down_payment": [None] * n,
        "installments": [None] * n,
    })


def _market_stats(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "manufacturer": ["toyota"] * n,
        "model": [f"corolla-{i}" for i in range(n)],
        "year": [2018] * n,
        "avg_price": [15000.0 + i for i in range(n)],
        "median_price": [15000.0 + i for i in range(n)],
        "min_price": [10000.0] * n,
        "max_price": [20000.0] * n,
        "total_listings": [10] * n,
        "days_listed": [5] * n,
        "calculated_at": [datetime(2026, 1, 1)] * n,
    })


@pytest.fixture
def sqlite_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestCreateDatabaseSchema:
    def test_calls_create_all(self):
        mock_engine = MagicMock()
        with patch("src.etl.load.create_db_engine", return_value=mock_engine), \
             patch("src.etl.load.Base") as mock_base:
            create_database_schema()
        mock_base.metadata.create_all.assert_called_once_with(mock_engine)

    def test_propagates_sqlalchemy_error(self):
        with patch("src.etl.load.create_db_engine", side_effect=SQLAlchemyError("boom")):
            with pytest.raises(SQLAlchemyError):
                create_database_schema()


class TestIdentityValidation:
    def test_rejects_missing_identity_before_database_query(self):
        session = MagicMock()
        with pytest.raises(ValueError, match="sem identidade"):
            load_cars_data(_clean_cars(1).drop(columns=["original_id"]), session)
        session.query.assert_not_called()

    def test_rejects_duplicate_identity(self):
        session = MagicMock()
        df = _clean_cars(2)
        df.loc[1, "original_id"] = df.loc[0, "original_id"]
        with pytest.raises(ValueError, match="duplicado"):
            load_cars_data(df, session)
        session.query.assert_not_called()

    def test_accepts_raw_id_alias(self, sqlite_sessions):
        session = sqlite_sessions()
        df = _clean_cars(1).rename(columns={"original_id": "id"})
        assert load_cars_data(df, session) is True
        assert session.query(Car).one().original_id == "7300000000"


class TestLoadHelpers:
    def test_market_stats_upsert_preserves_id(self, sqlite_sessions):
        session = sqlite_sessions()
        stats = _market_stats(1)
        assert load_market_stats(stats, session) is True
        first_id = session.execute(Base.metadata.tables["market_stats"].select()).one().id
        assert load_market_stats(stats, session) is True
        second_id = session.execute(Base.metadata.tables["market_stats"].select()).one().id
        assert first_id == second_id

    def test_history_only_uses_recorded_price_changes(self, sqlite_sessions):
        session = sqlite_sessions()
        df = _clean_cars(1)
        load_cars_data(df, session)
        create_price_history(df, session)
        assert session.query(PriceHistory).count() == 0

        df.loc[0, "price"] = 17000.0
        load_cars_data(df, session)
        create_price_history(df, session)
        history = session.query(PriceHistory).one()
        assert history.price == 17000.0


class TestConsecutiveLoads:
    def _run(self, sessions, cars):
        with patch("src.etl.load.create_database_schema"), \
             patch("src.etl.load.get_db_session", side_effect=sessions):
            return load_data(cars, _market_stats(len(cars)))

    def test_same_input_preserves_ids_columns_and_history(self, sqlite_sessions):
        cars = _clean_cars(2)
        self._run(iter([sqlite_sessions()]), cars)

        inspect_session = sqlite_sessions()
        first = {car.original_id: car for car in inspect_session.query(Car).all()}
        first_ids = {identity: car.id for identity, car in first.items()}
        assert inspect_session.query(PriceHistory).count() == 0
        inspect_session.close()

        self._run(iter([sqlite_sessions()]), cars.copy(deep=True))

        inspect_session = sqlite_sessions()
        second = {car.original_id: car for car in inspect_session.query(Car).all()}
        assert {identity: car.id for identity, car in second.items()} == first_ids
        assert inspect_session.query(PriceHistory).count() == 0

        source_fields = (
            "url", "region", "manufacturer", "model", "year", "price",
            "price_original", "odometer", "fuel", "transmission", "drive",
            "type", "paint_color", "condition", "cylinders", "title_status",
            "vin", "size", "state", "latitude", "longitude", "posting_date",
            "vehicle_age",
            "has_installments", "monthly_payment", "down_payment", "installments",
        )
        expected = cars.set_index("original_id")
        for identity, car in second.items():
            for field in source_fields:
                expected_value = expected.loc[identity, field]
                if pd.isna(expected_value):
                    expected_value = None
                elif field == "posting_date":
                    expected_value = expected_value.date()
                assert getattr(car, field) == expected_value

    def test_price_change_adds_one_history_row_without_changing_car_id(self, sqlite_sessions):
        cars = _clean_cars(1)
        self._run(iter([sqlite_sessions()]), cars)
        session = sqlite_sessions()
        original_id = session.query(Car).one().id
        session.close()

        changed = cars.copy()
        changed.loc[0, "price"] = 18000.0
        self._run(iter([sqlite_sessions()]), changed)

        session = sqlite_sessions()
        assert session.query(Car).one().id == original_id
        history = session.query(PriceHistory).all()
        assert len(history) == 1
        assert history[0].price == 18000.0

        self._run(iter([sqlite_sessions()]), changed.copy())
        session = sqlite_sessions()
        assert session.query(PriceHistory).count() == 1

    def test_rolls_back_everything_when_step_fails(self, sqlite_sessions):
        cars = _clean_cars(1)
        session = sqlite_sessions()
        with patch("src.etl.load.create_database_schema"), \
             patch("src.etl.load.get_db_session", return_value=session), \
             patch("src.etl.load.load_market_stats", side_effect=SQLAlchemyError("fail")):
            with pytest.raises(SQLAlchemyError):
                load_data(cars, _market_stats(1))

        verify = sqlite_sessions()
        assert verify.query(Car).count() == 0
        assert verify.query(PriceHistory).count() == 0
