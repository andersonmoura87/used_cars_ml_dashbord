"""Modelos SQLAlchemy canônicos compartilhados por ETL e API."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


def _bigint_identity_type():
    """Mantém BIGINT no PostgreSQL e autoincremento compatível no SQLite."""
    return BigInteger().with_variant(Integer, "sqlite")


class Car(Base):
    __tablename__ = "cars"

    id = Column(_bigint_identity_type(), primary_key=True)
    original_id = Column(Text)
    url = Column(Text)
    region = Column(Text)
    manufacturer = Column(Text)
    model = Column(Text)
    year = Column(Integer)
    price = Column(Float)
    price_original = Column(Float)
    odometer = Column(Float)
    fuel = Column(Text)
    transmission = Column(Text)
    drive = Column(Text)
    type = Column(Text)
    paint_color = Column(Text)
    condition = Column(Text)
    cylinders = Column(Text)
    title_status = Column(Text)
    vin = Column(Text)
    size = Column(Text)
    state = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    posting_date = Column(Date)
    vehicle_age = Column(Integer)
    has_installments = Column(Boolean, server_default=text("false"))
    monthly_payment = Column(Float)
    down_payment = Column(Float)
    installments = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index(
            "uq_cars_original_id",
            "original_id",
            unique=True,
            postgresql_where=text("original_id IS NOT NULL"),
        ),
        Index("idx_cars_manufacturer", "manufacturer"),
        Index("idx_cars_state", "state"),
        Index("idx_cars_year", "year"),
        Index("idx_cars_price", "price"),
    )


class MarketStats(Base):
    __tablename__ = "market_stats"

    id = Column(Integer, primary_key=True)
    manufacturer = Column(Text)
    model = Column(Text)
    year = Column(Integer)
    avg_price = Column(Float)
    median_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    total_listings = Column(Integer)
    avg_days_listed = Column("days_listed", Integer)
    state = Column(Text)
    calculated_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_market_stats_main", "manufacturer", "model", "year", unique=True),
        Index("idx_market_stats_date", "calculated_at"),
    )


class _AggregateColumns:
    id = Column(Integer, primary_key=True)
    total_listings = Column(Integer)
    avg_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    total_financed = Column(Integer)
    avg_monthly_payment = Column(Float)
    avg_down_payment = Column(Float)
    avg_installments = Column(Float)


class ManufacturerStats(_AggregateColumns, Base):
    __tablename__ = "manufacturer_stats"
    manufacturer = Column(Text, unique=True)
    avg_year = Column(Float)


class StateStats(_AggregateColumns, Base):
    __tablename__ = "state_stats"
    state = Column(Text, unique=True)


class YearStats(_AggregateColumns, Base):
    __tablename__ = "year_stats"
    year = Column(Integer, unique=True)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(_bigint_identity_type(), primary_key=True)
    car_id = Column(
        _bigint_identity_type(),
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
    )
    price = Column(Float)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_car_price_date", "car_id", "price", "recorded_at"),)


def create_tables(engine):
    """Cria estruturas ausentes sem apagar dados existentes."""
    Base.metadata.create_all(engine)
