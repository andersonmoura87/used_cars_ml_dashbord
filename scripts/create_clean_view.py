import os
import sys
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    try:
        engine = create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
            connect_args={'client_encoding': 'utf8'}
        )
        return engine
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        sys.exit(1)

def create_clean_view(engine):
    """Cria uma view com dados limpos e confiáveis."""
    logger.info("Criando view com dados limpos...")
    
    # Query para criar a view com dados limpos
    query = """
    CREATE OR REPLACE VIEW clean_cars AS
    WITH manufacturer_stats AS (
        SELECT 
            manufacturer,
            AVG(price) as mean_price,
            STDDEV(price) as std_price
        FROM cars
        WHERE price > 0
        GROUP BY manufacturer
    )
    SELECT 
        c.*
    FROM cars c
    JOIN manufacturer_stats ms ON c.manufacturer = ms.manufacturer
    WHERE 
        -- Remover registros com valores nulos em campos importantes
        c.manufacturer IS NOT NULL
        AND c.model IS NOT NULL
        AND c.year IS NOT NULL
        AND c.price IS NOT NULL
        
        -- Remover anos inválidos
        AND c.year BETWEEN 1900 AND 2024
        
        -- Remover preços negativos ou zero
        AND c.price > 0
        
        -- Remover preços muito baixos (menos de 10% da média do fabricante)
        AND c.price >= ms.mean_price * 0.1
        
        -- Remover preços muito altos (mais de 3 desvios padrão da média)
        AND c.price <= ms.mean_price + (3 * ms.std_price)
        
        -- Garantir consistência nos dados de parcelamento
        AND (
            (c.has_installments = TRUE AND 
             c.monthly_payment > 0 AND 
             c.installments > 0 AND
             c.installments <= 120 AND  -- Máximo de 120 parcelas
             ABS(c.price - (c.monthly_payment * c.installments + COALESCE(c.down_payment, 0))) <= 0.01)
            OR 
            (c.has_installments = FALSE)
        )
        
        -- Remover valores extremos de quilometragem
        AND (c.odometer IS NULL OR (c.odometer > 0 AND c.odometer < 1000000))  -- Máximo 1 milhão de milhas
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(query))
            conn.commit()
            
            # Contar registros na view
            result = conn.execute(text("SELECT COUNT(*) FROM clean_cars"))
            count = result.scalar()
            logger.info(f"View clean_cars criada com sucesso. Total de registros limpos: {count}")
            
            # Mostrar estatísticas por fabricante
            stats_query = """
            SELECT 
                manufacturer,
                COUNT(*) as total_cars,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price
            FROM clean_cars
            GROUP BY manufacturer
            ORDER BY total_cars DESC
            """
            
            stats_df = pd.read_sql(stats_query, conn)
            logger.info("\nEstatísticas por fabricante:")
            logger.info(f"\n{stats_df.to_string(index=False)}")
            
    except Exception as e:
        logger.error(f"Erro ao criar view: {str(e)}")
        sys.exit(1)

def main():
    """Função principal."""
    try:
        engine = get_db_connection()
        create_clean_view(engine)
        logger.info("Processo concluído com sucesso")
    except Exception as e:
        logger.error(f"Erro durante o processo: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 