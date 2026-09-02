"""Regressões para o roteamento e o schema compartilhado da API."""

import asyncio
import importlib
from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import BigInteger, Date, Integer, Text
from starlette.routing import Match

from src.api import database
from src.api.models import Base as ApiBase, CarCreate, CarResponse
from src.api.routers import cars
from src.database.models import Base as DatabaseBase, Car, MarketStats, PriceHistory


def test_api_and_etl_share_the_same_metadata():
    assert ApiBase is DatabaseBase
    assert Car.__table__ is DatabaseBase.metadata.tables["cars"]
    assert "has_installments" in Car.__table__.columns


def test_api_database_reuses_canonical_session_factory():
    session = Mock()
    with patch.object(database, "get_db_session", return_value=session) as factory:
        dependency = database.get_db()
        assert next(dependency) is session
        with pytest.raises(StopIteration):
            next(dependency)
    factory.assert_called_once_with()
    session.close.assert_called_once_with()
    assert not hasattr(database, "engine")
    assert not hasattr(database, "SessionLocal")


def test_api_database_import_does_not_create_engine_or_connect():
    with patch("sqlalchemy.create_engine") as create_engine:
        importlib.reload(database)
    create_engine.assert_not_called()


def test_critical_orm_types_constraints_and_indexes_match_sql_contract():
    assert isinstance(Car.id.type, BigInteger)
    assert isinstance(Car.original_id.type, Text)
    assert isinstance(Car.posting_date.type, Date)
    assert Car.has_installments.nullable is False
    assert str(Car.has_installments.server_default.arg) == "false"

    indexes = {index.name: index for index in Car.__table__.indexes}
    original_id_index = indexes["uq_cars_original_id"]
    assert original_id_index.unique is True
    assert str(original_id_index.dialect_options["postgresql"]["where"]) == (
        "original_id IS NOT NULL"
    )
    assert {
        "idx_cars_manufacturer",
        "idx_cars_state",
        "idx_cars_year",
        "idx_cars_price",
    }.issubset(indexes)

    assert isinstance(MarketStats.avg_days_listed.type, Integer)
    assert MarketStats.calculated_at.type.timezone is True
    assert MarketStats.manufacturer.nullable is True
    assert MarketStats.model.nullable is True
    assert MarketStats.year.nullable is True

    assert isinstance(PriceHistory.car_id.type, BigInteger)
    assert PriceHistory.car_id.nullable is False
    foreign_key = next(iter(PriceHistory.car_id.foreign_keys))
    assert foreign_key.target_fullname == "cars.id"
    assert foreign_key.ondelete == "CASCADE"
    assert PriceHistory.recorded_at.type.timezone is True


def _valid_create_payload():
    payload = {name: None for name in CarCreate.model_fields}
    payload.update({
        "original_id": "source-123",
        "price": 25000.0,
        "year": 2020,
        "manufacturer": "A",
        "model": "B",
        "state": "SP",
    })
    return payload


@pytest.mark.parametrize("missing", ["original_id", "state"])
def test_create_contract_keeps_business_identity_fields_required(missing):
    payload = _valid_create_payload()
    payload.pop(missing)
    with pytest.raises(ValidationError):
        CarCreate.model_validate(payload)


def test_create_contract_requires_installment_field_without_inventing_false():
    payload = _valid_create_payload()
    payload.pop("has_installments")
    with pytest.raises(ValidationError):
        CarCreate.model_validate(payload)

    payload["has_installments"] = None
    car = CarCreate.model_validate(payload)
    assert car.has_installments is None


def test_invalid_create_payload_returns_422():
    app = FastAPI()

    @app.post("/cars")
    async def create_car(payload: CarCreate):
        return payload

    response = TestClient(app).post("/cars", json={"price": "invalid"})
    assert response.status_code == 422


def test_response_contract_accepts_legacy_nulls_without_omitting_fields():
    values = {name: None for name in CarResponse.model_fields if name != "id"}
    response = CarResponse.model_validate({"id": 7, **values})
    assert response.original_id is None
    assert response.state is None
    assert response.has_installments is None
    assert set(response.model_dump()) == set(CarResponse.model_fields)


def test_stats_path_is_not_captured_by_car_id_route():
    dynamic_route = next(route for route in cars.router.routes if route.path == "/{car_id:int}")
    match, _ = dynamic_route.matches(
        {"type": "http", "method": "GET", "path": "/stats/price_ranges", "root_path": ""}
    )
    assert match is Match.NONE


def test_non_integer_path_is_not_accepted_as_car_id():
    dynamic_route = next(route for route in cars.router.routes if route.path == "/{car_id:int}")
    match, _ = dynamic_route.matches(
        {"type": "http", "method": "GET", "path": "/not-an-id", "root_path": ""}
    )
    assert match is Match.NONE


def test_missing_car_preserves_404():
    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return None

    class Session:
        def query(self, *_args):
            return Query()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cars.get_car(123, Session()))
    assert exc_info.value.status_code == 404


def test_unexpected_database_error_returns_sanitized_500():
    class Session:
        def query(self, *_args):
            raise RuntimeError("internal database detail")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cars.get_car(123, Session()))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Error retrieving car"
    assert "internal database detail" not in exc_info.value.detail


def test_existing_car_is_returned():
    expected = object()

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return expected

    class Session:
        def query(self, *_args):
            return Query()

    assert asyncio.run(cars.get_car(123, Session())) is expected


def test_list_applies_filters_and_pagination():
    expected = [object()]

    class Query:
        def __init__(self):
            self.filters = []
            self.offset_value = None
            self.limit_value = None

        def filter(self, expression):
            self.filters.append(expression)
            return self

        def offset(self, value):
            self.offset_value = value
            return self

        def limit(self, value):
            self.limit_value = value
            return self

        def all(self):
            return expected

    query = Query()

    class Session:
        def query(self, *_args):
            return query

    result = asyncio.run(
        cars.get_cars(
            skip=5,
            limit=20,
            manufacturer="Ford",
            min_price=10000,
            max_price=30000,
            min_year=2018,
            max_year=2022,
            state="SP",
            has_installments=False,
            db=Session(),
        )
    )
    assert result is expected
    assert len(query.filters) == 7
    assert query.offset_value == 5
    assert query.limit_value == 20


def test_response_schema_serializes_orm_instance():
    car = Car(
        id=1,
        original_id="source-1",
        price=20000,
        year=2021,
        manufacturer="A",
        model="B",
        state="SP",
        posting_date=date(2024, 1, 2),
        has_installments=None,
    )
    response = CarResponse.model_validate(car)
    assert response.id == 1
    assert response.posting_date == date(2024, 1, 2)
    assert response.has_installments is None
