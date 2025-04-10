import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import logging
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def create_tables(engine):
    """Cria as tabelas no banco de dados."""
    logger.info("Criando tabelas...")
    
    create_cars_table = """
    CREATE TABLE IF NOT EXISTS cars (
        id SERIAL PRIMARY KEY,
        original_id INTEGER,
        url TEXT,
        region TEXT,
        region_url TEXT,
        price FLOAT,
        year INTEGER,
        manufacturer TEXT,
        model TEXT,
        condition TEXT,
        cylinders TEXT,
        fuel TEXT,
        odometer FLOAT,
        title_status TEXT,
        transmission TEXT,
        vin TEXT,
        drive TEXT,
        size TEXT,
        type TEXT,
        paint_color TEXT,
        image_url TEXT,
        description TEXT,
        county TEXT,
        state TEXT,
        latitude FLOAT,
        longitude FLOAT,
        posting_date TIMESTAMP,
        vehicle_age INTEGER,
        price_category TEXT
    );
    """
    
    create_manufacturer_stats_table = """
    CREATE TABLE IF NOT EXISTS manufacturer_stats (
        manufacturer TEXT PRIMARY KEY,
        total_cars INTEGER,
        avg_price FLOAT,
        min_price FLOAT,
        max_price FLOAT,
        avg_year FLOAT,
        avg_odometer FLOAT
    );
    """
    
    create_state_stats_table = """
    CREATE TABLE IF NOT EXISTS state_stats (
        state TEXT PRIMARY KEY,
        total_cars INTEGER,
        avg_price FLOAT,
        min_price FLOAT,
        max_price FLOAT,
        avg_year FLOAT,
        avg_odometer FLOAT
    );
    """
    
    create_year_stats_table = """
    CREATE TABLE IF NOT EXISTS year_stats (
        year INTEGER PRIMARY KEY,
        total_cars INTEGER,
        avg_price FLOAT,
        min_price FLOAT,
        max_price FLOAT,
        avg_odometer FLOAT
    );
    """
    
    try:
        with engine.connect() as conn:
            # Configurar codificação da conexão para UTF-8
            conn.execute(text("SET client_encoding TO 'UTF8';"))
            conn.execute(text(create_cars_table))
            conn.execute(text(create_manufacturer_stats_table))
            conn.execute(text(create_state_stats_table))
            conn.execute(text(create_year_stats_table))
            conn.commit()
        logger.info("Tabelas criadas com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {str(e)}")
        return False

def load_data_to_db():
    """Carrega os dados processados no banco de dados."""
    logger.info("Iniciando carregamento de dados...")
    load_dotenv()
    
    # Configurar conexão com o banco
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    logger.info(f"Conectando ao banco: {db_url}")
    
    # Criar engine com configurações específicas para UTF-8
    engine = create_engine(
        db_url,
        connect_args={
            'client_encoding': 'utf8',
            'options': '-c client_encoding=utf8'
        }
    )
    
    # Criar tabelas
    if not create_tables(engine):
        logger.error("Falha ao criar tabelas. Abortando...")
        return False
    
    try:
        # Ler dados processados
        file_path = os.getenv('PROCESSED_DATA_PATH') + '/used_cars_processed.csv'
        logger.info(f"Lendo arquivo: {file_path}")
        logger.info(f"Verificando se arquivo existe: {os.path.exists(file_path)}")
        logger.info(f"Tamanho do arquivo: {os.path.getsize(file_path)} bytes")
        
        # Ler o arquivo CSV com codificação UTF-8
        df = pd.read_csv(file_path, encoding='utf-8')
        logger.info(f"Dados lidos com sucesso. Shape: {df.shape}")
        logger.info(f"Colunas: {df.columns.tolist()}")
        
        # Renomear colunas para corresponder ao schema do banco
        df = df.rename(columns={
            'VIN': 'vin',
            'lat': 'latitude',
            'long': 'longitude',
            'id': 'original_id'
        })
        
        # Converter posting_date para timestamp
        df['posting_date'] = pd.to_datetime(df['posting_date'])
        
        # Garantir que todas as colunas de texto estejam em UTF-8
        text_columns = df.select_dtypes(include=['object']).columns
        for col in text_columns:
            df[col] = df[col].astype(str).apply(lambda x: x.encode('utf-8', errors='ignore').decode('utf-8'))
        
        # Carregar dados na tabela principal em chunks
        logger.info("Carregando dados na tabela cars...")
        chunk_size = 1000
        total_rows = len(df)
        for i in range(0, total_rows, chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            chunk.to_sql('cars', engine, if_exists='append', index=False, method=None)
            logger.info(f"Carregados {min(i + chunk_size, total_rows)} de {total_rows} registros...")
        
        logger.info("Dados carregados na tabela cars com sucesso!")
        
        # Atualizar estatísticas por fabricante
        logger.info("Atualizando estatísticas por fabricante...")
        manufacturer_stats = df.groupby('manufacturer').agg({
            'price': ['count', 'mean', 'min', 'max'],
            'year': 'mean',
            'odometer': 'mean'
        }).reset_index()
        
        manufacturer_stats.columns = ['manufacturer', 'total_cars', 'avg_price', 'min_price', 
                                    'max_price', 'avg_year', 'avg_odometer']
        
        manufacturer_stats.to_sql('manufacturer_stats', engine, if_exists='replace', index=False)
        logger.info("Estatísticas por fabricante atualizadas com sucesso!")
        
        # Atualizar estatísticas por estado
        logger.info("Atualizando estatísticas por estado...")
        state_stats = df.groupby('state').agg({
            'price': ['count', 'mean', 'min', 'max'],
            'year': 'mean',
            'odometer': 'mean'
        }).reset_index()
        
        state_stats.columns = ['state', 'total_cars', 'avg_price', 'min_price', 
                             'max_price', 'avg_year', 'avg_odometer']
        
        state_stats.to_sql('state_stats', engine, if_exists='replace', index=False)
        logger.info("Estatísticas por estado atualizadas com sucesso!")
        
        # Atualizar estatísticas por ano
        logger.info("Atualizando estatísticas por ano...")
        year_stats = df.groupby('year').agg({
            'price': ['count', 'mean', 'min', 'max'],
            'odometer': 'mean'
        }).reset_index()
        
        year_stats.columns = ['year', 'total_cars', 'avg_price', 'min_price', 
                            'max_price', 'avg_odometer']
        
        year_stats.to_sql('year_stats', engine, if_exists='replace', index=False)
        logger.info("Estatísticas por ano atualizadas com sucesso!")
        
        logger.info("Dados carregados com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        logger.error(f"Tipo do erro: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    load_data_to_db() 