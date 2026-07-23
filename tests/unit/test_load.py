"""
Testes unitários — src.etl.load (cobertura ETL core, com mocks).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.etl.load import (
    create_database_schema,
    create_price_history,
    load_cars_data,
    load_data,
    load_market_stats,
)


def _clean_cars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "manufacturer": ["toyota"] * n,
        "model": ["corolla"] * n,
        "year": [2018] * n,
        "price": [15000.0] * n,
        "price_original": [15000.0] * n,
        "odometer": [40000] * n,
        "fuel": ["gas"] * n,
        "transmission": ["automatic"] * n,
        "drive": ["fwd"] * n,
        "type": ["sedan"] * n,
        "paint_color": ["white"] * n,
        "condition": ["good"] * n,
        "state": ["ca"] * n,
        "latitude": [37.0] * n,
        "longitude": [-122.0] * n,
        "posting_date": pd.to_datetime(["2024-01-01"] * n, utc=True),
        "vehicle_age": [6] * n,
    })


def _market_stats(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "manufacturer": ["toyota"] * n,
        "model": ["corolla"] * n,
        "year": list(range(2018, 2018 + n)),
        "avg_price": [15000.0 + i * 1000 for i in range(n)],
        "median_price": [15000.0 + i * 1000 for i in range(n)],
        "min_price": [10000.0] * n,
        "max_price": [20000.0] * n,
        "total_listings": [10] * n,
        "days_listed": [5] * n,
        "calculated_at": [datetime.now()] * n,
    })


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


class TestLoadCarsData:
    def test_bulk_inserts_and_commits(self):
        session = MagicMock()
        df = _clean_cars(3)
        assert load_cars_data(df, session) is True
        assert session.bulk_save_objects.called
        assert session.commit.called

    def test_rollback_on_error(self):
        session = MagicMock()
        session.bulk_save_objects.side_effect = SQLAlchemyError("fail")
        with pytest.raises(SQLAlchemyError):
            load_cars_data(_clean_cars(1), session)
        session.rollback.assert_called_once()


class TestLoadMarketStats:
    def test_bulk_inserts(self):
        session = MagicMock()
        assert load_market_stats(_market_stats(), session) is True
        assert session.bulk_save_objects.called


class TestCreatePriceHistory:
    def test_creates_history_for_matching_cars(self):
        session = MagicMock()
        session.query.return_value.all.return_value = [
            (1, "toyota", "corolla", 2018),
        ]
        df = _clean_cars(1)
        assert create_price_history(df, session) is True
        assert session.bulk_save_objects.called


class TestLoadData:
    def test_orchestrates_all_steps(self):
        session = MagicMock()
        session.execute.return_value.scalar.return_value = "PostgreSQL 15"

        with patch("src.etl.load.create_database_schema") as mock_schema, \
             patch("src.etl.load.get_db_session", return_value=session), \
             patch("src.etl.load.load_cars_data") as mock_cars, \
             patch("src.etl.load.load_market_stats") as mock_stats, \
             patch("src.etl.load.create_price_history") as mock_hist:

            meta = load_data(_clean_cars(2), _market_stats(1))

        mock_schema.assert_called_once()
        mock_cars.assert_called_once()
        mock_stats.assert_called_once()
        mock_hist.assert_called_once()
        session.close.assert_called_once()
        assert meta["total_cars_loaded"] == 2
        assert meta["total_stats_loaded"] == 1
        assert "timestamp" in meta
