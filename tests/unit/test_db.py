import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_database():
    """Testa a conexão com o banco e verifica os dados carregados."""
    load_dotenv()
    
    try:
        # Configurar conexão com o banco
        db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        engine = create_engine(db_url)
        
        # Testar conexão
        logger.info("Testando conexão com o banco de dados...")
        with engine.connect() as conn:
            logger.info("Conexão estabelecida com sucesso!")
        
        # Verificar quantidade de registros
        logger.info("\nVerificando quantidade de registros nas tabelas:")
        
        # Tabela cars
        cars_count = pd.read_sql("SELECT COUNT(*) FROM cars", engine).iloc[0,0]
        logger.info(f"Tabela cars: {cars_count:,} registros")
        
        # Tabela manufacturer_stats
        mf_stats_count = pd.read_sql("SELECT COUNT(*) FROM manufacturer_stats", engine).iloc[0,0]
        logger.info(f"Tabela manufacturer_stats: {mf_stats_count:,} registros")
        
        # Tabela state_stats
        state_stats_count = pd.read_sql("SELECT COUNT(*) FROM state_stats", engine).iloc[0,0]
        logger.info(f"Tabela state_stats: {state_stats_count:,} registros")
        
        # Tabela year_stats
        year_stats_count = pd.read_sql("SELECT COUNT(*) FROM year_stats", engine).iloc[0,0]
        logger.info(f"Tabela year_stats: {year_stats_count:,} registros")
        
        # Verificar alguns dados de exemplo
        logger.info("\nVerificando alguns dados de exemplo:")
        
        # Top 5 fabricantes
        logger.info("\nTop 5 fabricantes por quantidade:")
        top_manufacturers = pd.read_sql("""
            SELECT manufacturer, total_cars, avg_price 
            FROM manufacturer_stats 
            ORDER BY total_cars DESC 
            LIMIT 5
        """, engine)
        logger.info(top_manufacturers.to_string())
        
        # Top 5 estados
        logger.info("\nTop 5 estados por quantidade:")
        top_states = pd.read_sql("""
            SELECT state, total_cars, avg_price 
            FROM state_stats 
            ORDER BY total_cars DESC 
            LIMIT 5
        """, engine)
        logger.info(top_states.to_string())
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao testar banco de dados: {str(e)}")
        return False

if __name__ == "__main__":
    test_database() 