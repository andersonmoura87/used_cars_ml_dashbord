from sqlalchemy import Column, Integer, String, Float, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship  # noqa: F401 (available for future use)
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict

Base = declarative_base()

# SQLAlchemy ORM Models
class CarORM(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(String, unique=True, index=True)
    url = Column(String)
    region = Column(String)
    price = Column(Float)
    year = Column(Integer)
    manufacturer = Column(String, index=True)
    model = Column(String)
    condition = Column(String)
    cylinders = Column(String)
    fuel = Column(String)
    odometer = Column(Float)
    title_status = Column(String)
    transmission = Column(String)
    vin = Column(String)
    drive = Column(String)
    size = Column(String)
    type = Column(String)
    paint_color = Column(String)
    state = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    posting_date = Column(Date)
    
    # Financing fields
    price_original = Column(Float)
    has_installments = Column(Boolean, default=False)
    monthly_payment = Column(Float)
    down_payment = Column(Float)
    installments = Column(Integer)

# Pydantic Models for API
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


class CarResponse(CarBase):
    """Pydantic response model — use this in router response_model annotations."""
    id: int
    model_config = ConfigDict(from_attributes=True)

# Statistics Models
class ManufacturerStats(Base):
    __tablename__ = "manufacturer_stats"

    id = Column(Integer, primary_key=True, index=True)
    manufacturer = Column(String, unique=True, index=True)
    total_listings = Column(Integer)
    avg_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    avg_year = Column(Float)
    total_financed = Column(Integer)
    avg_monthly_payment = Column(Float)
    avg_down_payment = Column(Float)
    avg_installments = Column(Float)

class StateStats(Base):
    __tablename__ = "state_stats"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, unique=True, index=True)
    total_listings = Column(Integer)
    avg_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    total_financed = Column(Integer)
    avg_monthly_payment = Column(Float)
    avg_down_payment = Column(Float)
    avg_installments = Column(Float)

class YearStats(Base):
    __tablename__ = "year_stats"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, unique=True, index=True)
    total_listings = Column(Integer)
    avg_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    total_financed = Column(Integer)
    avg_monthly_payment = Column(Float)
    avg_down_payment = Column(Float)
    avg_installments = Column(Float) 