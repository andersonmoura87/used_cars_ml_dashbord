"""Contratos da API e aliases para os modelos SQLAlchemy canônicos."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.database.models import (
    Base,
    Car as CarORM,
    ManufacturerStats,
    StateStats,
    YearStats,
)

__all__ = (
    "Base",
    "CarBase",
    "CarCreate",
    "CarORM",
    "CarResponse",
    "ManufacturerStats",
    "StateStats",
    "YearStats",
)


class CarBase(BaseModel):
    original_id: str
    url: Optional[str]
    region: Optional[str]
    price: float
    year: int
    manufacturer: str
    model: str
    condition: Optional[str]
    cylinders: Optional[str]
    fuel: Optional[str]
    odometer: Optional[float]
    title_status: Optional[str]
    transmission: Optional[str]
    vin: Optional[str]
    drive: Optional[str]
    size: Optional[str]
    type: Optional[str]
    paint_color: Optional[str]
    state: str
    latitude: Optional[float]
    longitude: Optional[float]
    posting_date: Optional[date]
    price_original: Optional[float]
    has_installments: Optional[bool]
    monthly_payment: Optional[float]
    down_payment: Optional[float]
    installments: Optional[int]


class CarCreate(CarBase):
    pass


class CarResponse(BaseModel):
    id: int
    original_id: Optional[str]
    url: Optional[str]
    region: Optional[str]
    price: Optional[float]
    year: Optional[int]
    manufacturer: Optional[str]
    model: Optional[str]
    condition: Optional[str]
    cylinders: Optional[str]
    fuel: Optional[str]
    odometer: Optional[float]
    title_status: Optional[str]
    transmission: Optional[str]
    vin: Optional[str]
    drive: Optional[str]
    size: Optional[str]
    type: Optional[str]
    paint_color: Optional[str]
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    posting_date: Optional[date]
    price_original: Optional[float]
    has_installments: Optional[bool]
    monthly_payment: Optional[float]
    down_payment: Optional[float]
    installments: Optional[int]
    model_config = ConfigDict(from_attributes=True)
