from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import inspect, text

from src.database.connection import create_db_engine, get_db_session
from src.database.models import (
    Base,
    Car,
    ManufacturerStats,
    MarketStats,
    PriceHistory,
    StateStats,
    YearStats,
)
from src.etl.transform import calculate_market_statistics

logger = logging.getLogger(__name__)

IDENTITY_COLUMN = "original_id"
IDENTITY_ALIASES = ("original_id", "id")
QUERY_BATCH_SIZE = 5_000

CAR_SOURCE_FIELDS = (
    "url",
    "region",
    "manufacturer",
    "model",
    "year",
    "price",
    "price_original",
    "odometer",
    "fuel",
    "transmission",
    "drive",
    "type",
    "paint_color",
    "condition",
    "cylinders",
    "title_status",
    "vin",
    "size",
    "state",
    "latitude",
    "longitude",
    "posting_date",
    "vehicle_age",
    "has_installments",
    "monthly_payment",
    "down_payment",
    "installments",
)


def create_database_schema():
    """Cria estruturas ausentes; migrations continuam obrigatórias para upgrades."""
    engine = create_db_engine()
    Base.metadata.create_all(engine)
    logger.info("Schema do banco de dados verificado")


def _chunks(values: list[str], size: int = QUERY_BATCH_SIZE) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _scalar(value: Any) -> Any:
    """Converte escalares pandas/numpy em valores aceitos pelo SQLAlchemy."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value.item() if hasattr(value, "item") else value


def _normalise_cars(df_clean: pd.DataFrame) -> list[dict[str, Any]]:
    identity_source = next((name for name in IDENTITY_ALIASES if name in df_clean.columns), None)
    if identity_source is None:
        raise ValueError("Dataset sem identidade: informe a coluna 'original_id' ou 'id'")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates: set[str] = set()

    for raw in df_clean.to_dict("records"):
        identity_value = _scalar(raw.get(identity_source))
        if identity_value is None or str(identity_value).strip() == "":
            raise ValueError("original_id nulo ou vazio; carga cancelada antes de alterar o banco")
        if isinstance(identity_value, float) and identity_value.is_integer():
            identity_value = int(identity_value)
        identity = str(identity_value)
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)

        record = {IDENTITY_COLUMN: identity}
        for field in CAR_SOURCE_FIELDS:
            if field in raw:
                record[field] = _scalar(raw[field])
        if "has_installments" in record:
            record["has_installments"] = bool(record["has_installments"])
        records.append(record)

    if duplicates:
        sample = ", ".join(sorted(duplicates)[:5])
        raise ValueError(f"original_id duplicado no lote: {sample}")
    return records


def load_cars_data(df_clean: pd.DataFrame, session) -> bool:
    """Faz upsert por original_id, preservando cars.id e todas as colunas do anúncio."""
    records = _normalise_cars(df_clean)
    identities = [record[IDENTITY_COLUMN] for record in records]

    existing_by_identity: dict[str, Car] = {}
    for batch in _chunks(identities):
        existing = session.query(Car).filter(Car.original_id.in_(batch)).all()
        existing_by_identity.update({str(car.original_id): car for car in existing})

    price_changes: list[Car] = []
    inserted = 0
    for record in records:
        identity = record[IDENTITY_COLUMN]
        car = existing_by_identity.get(identity)
        if car is None:
            session.add(Car(**record))
            inserted += 1
            continue

        old_price = car.price
        new_price = record.get("price", old_price)
        if old_price != new_price:
            price_changes.append(car)
        for field, value in record.items():
            setattr(car, field, value)

    session.flush()
    session.info["price_changes"] = price_changes
    logger.info(
        "Upsert de carros concluído: %d inseridos, %d atualizados, %d preços alterados",
        inserted,
        len(records) - inserted,
        len(price_changes),
    )
    return True


def _sync_rows(session, model, identity_fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    """Sincroniza uma tabela derivada preservando IDs das chaves que permanecem."""
    existing = session.query(model).all()
    existing_by_key = {
        tuple(getattr(item, field) for field in identity_fields): item for item in existing
    }
    incoming_keys: set[tuple[Any, ...]] = set()

    for row in rows:
        key = tuple(row[field] for field in identity_fields)
        if key in incoming_keys:
            raise ValueError(f"Chave agregada duplicada em {model.__tablename__}: {key}")
        incoming_keys.add(key)
        item = existing_by_key.get(key)
        if item is None:
            session.add(model(**row))
            continue

        changed = any(getattr(item, field) != value for field, value in row.items() if field != "calculated_at")
        for field, value in row.items():
            if field != "calculated_at" or changed:
                setattr(item, field, value)

    for key, item in existing_by_key.items():
        if key not in incoming_keys:
            session.delete(item)
    session.flush()


def load_market_stats(stats_df: pd.DataFrame, session) -> bool:
    valid_columns = {attr.key for attr in inspect(MarketStats).column_attrs if attr.key != "id"}
    rows = [
        {key: _scalar(value) for key, value in raw.items() if key in valid_columns}
        for raw in stats_df.rename(columns={"days_listed": "avg_days_listed"}).to_dict("records")
    ]
    _sync_rows(session, MarketStats, ("manufacturer", "model", "year"), rows)
    return True


def load_aggregate_stats(df_clean: pd.DataFrame, session) -> bool:
    frames = calculate_market_statistics(df_clean)
    specs = {
        "manufacturer": (ManufacturerStats, ("manufacturer",)),
        "state": (StateStats, ("state",)),
        "year": (YearStats, ("year",)),
    }
    for dimension, (model, identity_fields) in specs.items():
        valid_columns = {attr.key for attr in inspect(model).column_attrs if attr.key != "id"}
        rows = [
            {key: _scalar(value) for key, value in raw.items() if key in valid_columns}
            for raw in frames[dimension].to_dict("records")
        ]
        _sync_rows(session, model, identity_fields, rows)
    return True


def create_price_history(_df_clean: pd.DataFrame, session) -> bool:
    """Registra o preço novo somente para anúncios cujo preço persistido mudou."""
    changed_cars = session.info.pop("price_changes", [])
    for car in changed_cars:
        session.add(PriceHistory(car_id=car.id, price=car.price, recorded_at=datetime.now()))
    session.flush()
    return True


def _database_version(session) -> str:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        return str(session.execute(text("SELECT version();")).scalar())
    return bind.dialect.name


def load_data(df_clean: pd.DataFrame, market_stats: pd.DataFrame):
    """Executa todos os upserts e o histórico em uma única transação."""
    # Validação de identidade ocorre antes de abrir/transacionar a sessão.
    _normalise_cars(df_clean)
    create_database_schema()
    session = get_db_session()
    try:
        load_cars_data(df_clean, session)
        load_market_stats(market_stats, session)
        load_aggregate_stats(df_clean, session)
        create_price_history(df_clean, session)

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "total_cars_loaded": len(df_clean),
            "total_stats_loaded": len(market_stats),
            "database_version": _database_version(session),
        }
        logger.info("Carga validada; confirmando transação")
        session.commit()
        return metadata
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
