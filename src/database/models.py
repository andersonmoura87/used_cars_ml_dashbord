from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Car(Base):
    """Modelo para a tabela de carros."""
    __tablename__ = 'cars'

    id = Column(Integer, primary_key=True)
    manufacturer = Column(String(100), index=True)
    model = Column(String(200), index=True)
    year = Column(Integer, index=True)
    price = Column(Float, index=True)
    price_original = Column(Float)
    odometer = Column(Float)
    fuel = Column(String(50))
    transmission = Column(String(50))
    drive = Column(String(50))
    type = Column(String(50))
    paint_color = Column(String(50))
    condition = Column(String(50))
    state = Column(String(50), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    posting_date = Column(DateTime, index=True)
    vehicle_age = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Índices compostos para consultas comuns
    __table_args__ = (
        Index('idx_manufacturer_model_year', 'manufacturer', 'model', 'year'),
        Index('idx_price_year_odometer', 'price', 'year', 'odometer'),
        Index('idx_location', 'state', 'latitude', 'longitude')
    )

class MarketStats(Base):
    """Modelo para estatísticas de mercado."""
    __tablename__ = 'market_stats'

    id = Column(Integer, primary_key=True)
    manufacturer = Column(String(100))
    model = Column(String(200))
    year = Column(Integer)
    avg_price = Column(Float)
    median_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    total_listings = Column(Integer)
    avg_days_listed = Column(Float)
    state = Column(String(50))
    calculated_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_market_stats_main', 'manufacturer', 'model', 'year'),
        Index('idx_market_stats_date', 'calculated_at')
    )

class PriceHistory(Base):
    """Modelo para histórico de preços."""
    __tablename__ = 'price_history'

    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey('cars.id', ondelete='CASCADE'))
    price = Column(Float)
    recorded_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_car_price_date', 'car_id', 'price', 'recorded_at'),
    )

def create_tables(engine):
    """Cria todas as tabelas no banco de dados."""
    # Primeiro, remove todas as tabelas existentes
    Base.metadata.drop_all(engine)
    # Depois, cria todas as tabelas na ordem correta
    Base.metadata.create_all(engine) 