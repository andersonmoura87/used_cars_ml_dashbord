import pandas as pd
import logging
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from src.database.connection import create_db_engine, get_db_session
from src.database.models import Base, Car, PriceHistory, MarketStats

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_schema():
    """Cria o schema do banco de dados."""
    try:
        engine = create_db_engine()
        Base.metadata.create_all(engine)
        logger.info("Schema do banco de dados criado com sucesso")
    except SQLAlchemyError as e:
        logger.error(f"Erro ao criar schema do banco de dados: {str(e)}")
        raise

def load_cars_data(df_clean, session):
    """Carrega os dados dos carros no banco de dados."""
    try:
        # Converter DataFrame para dicionário
        cars_data = df_clean.to_dict('records')
        
        # Criar objetos Car
        cars = []
        for data in cars_data:
            car = Car(
                manufacturer=data['manufacturer'],
                model=data['model'],
                year=data['year'],
                price=data['price'],
                price_original=data.get('price_original'),
                odometer=data['odometer'],
                fuel=data['fuel'],
                transmission=data['transmission'],
                drive=data.get('drive'),
                type=data.get('type'),
                paint_color=data.get('paint_color'),
                condition=data.get('condition'),
                state=data['state'],
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                posting_date=data['posting_date'],
                vehicle_age=data.get('vehicle_age')
            )
            cars.append(car)
        
        # Inserir em lotes
        batch_size = 1000
        for i in range(0, len(cars), batch_size):
            batch = cars[i:i + batch_size]
            session.bulk_save_objects(batch)
            session.commit()
            logger.info(f"Lote de {len(batch)} carros inserido com sucesso")
        
        logger.info(f"Total de {len(cars)} carros inseridos no banco de dados")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Erro ao carregar dados dos carros: {str(e)}")
        raise

def load_market_stats(stats_df, session):
    """Carrega as estatísticas de mercado no banco de dados."""
    try:
        # Converter DataFrame para dicionário
        stats_data = stats_df.to_dict('records')
        
        # Criar objetos MarketStats
        stats = []
        for data in stats_data:
            stat = MarketStats(
                manufacturer=data['manufacturer'],
                model=data['model'],
                year=data['year'],
                avg_price=data['avg_price'],
                median_price=data['median_price'],
                min_price=data['min_price'],
                max_price=data['max_price'],
                total_listings=data['total_listings'],
                avg_days_listed=data['days_listed'],
                calculated_at=data['calculated_at']
            )
            stats.append(stat)
        
        # Inserir em lotes
        batch_size = 1000
        for i in range(0, len(stats), batch_size):
            batch = stats[i:i + batch_size]
            session.bulk_save_objects(batch)
            session.commit()
            logger.info(f"Lote de {len(batch)} estatísticas inserido com sucesso")
        
        logger.info(f"Total de {len(stats)} estatísticas inseridas no banco de dados")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Erro ao carregar estatísticas de mercado: {str(e)}")
        raise

def create_price_history(df_clean, session):
    """Cria histórico de preços para os carros."""
    try:
        # Obter IDs dos carros inseridos
        car_ids = session.query(Car.id, Car.manufacturer, Car.model, Car.year).all()
        
        # Criar registros de histórico
        history_records = []
        for car_id, manufacturer, model, year in car_ids:
            # Encontrar preço correspondente no DataFrame
            car_data = df_clean[
                (df_clean['manufacturer'] == manufacturer) &
                (df_clean['model'] == model) &
                (df_clean['year'] == year)
            ]
            
            if not car_data.empty:
                history = PriceHistory(
                    car_id=car_id,
                    price=car_data.iloc[0]['price'],
                    recorded_at=datetime.now()
                )
                history_records.append(history)
        
        # Inserir em lotes
        batch_size = 1000
        for i in range(0, len(history_records), batch_size):
            batch = history_records[i:i + batch_size]
            session.bulk_save_objects(batch)
            session.commit()
            logger.info(f"Lote de {len(batch)} registros de histórico inserido com sucesso")
        
        logger.info(f"Total de {len(history_records)} registros de histórico inseridos")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Erro ao criar histórico de preços: {str(e)}")
        raise

def load_data(df_clean, market_stats):
    """Função principal de carregamento dos dados."""
    try:
        # Criar schema
        create_database_schema()
        
        # Iniciar sessão
        session = get_db_session()
        
        try:
            # Carregar dados dos carros
            load_cars_data(df_clean, session)
            
            # Carregar estatísticas de mercado
            load_market_stats(market_stats, session)
            
            # Criar histórico de preços
            create_price_history(df_clean, session)
            
            # Criar metadados do carregamento
            metadata = {
                'timestamp': datetime.now().isoformat(),
                'total_cars_loaded': len(df_clean),
                'total_stats_loaded': len(market_stats),
                'database_version': session.execute(text("SELECT version();")).scalar()
            }
            
            logger.info("Carregamento de dados concluído com sucesso")
            return metadata
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Erro no processo de carregamento: {str(e)}")
        raise 