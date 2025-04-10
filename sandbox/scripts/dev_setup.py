import os
import sys
import logging
from pathlib import Path
import subprocess
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

def setup_virtual_env():
    """Configura o ambiente virtual."""
    logger.info("Configurando ambiente virtual...")
    
    # Verificar se o ambiente virtual já existe
    venv_path = Path("venv")
    if not venv_path.exists():
        logger.info("Criando ambiente virtual...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])
    
    # Determinar o script de ativação baseado no sistema operacional
    if sys.platform == "win32":
        activate_script = "venv\\Scripts\\activate"
    else:
        activate_script = "venv/bin/activate"
    
    logger.info(f"Ambiente virtual criado em {venv_path.absolute()}")
    logger.info(f"Para ativar, execute: {activate_script}")

def setup_dev_database():
    """Configura o banco de dados de desenvolvimento."""
    logger.info("Configurando banco de dados de desenvolvimento...")
    
    # Criar conexão com o banco de dados
    engine = create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/postgres"
    )
    
    try:
        with engine.connect() as conn:
            # Criar banco de dados de desenvolvimento
            conn.execute(text("COMMIT"))  # Fechar transação atual
            conn.execute(text("DROP DATABASE IF EXISTS mobato_dev"))
            conn.execute(text("CREATE DATABASE mobato_dev"))
            
            # Conectar ao banco de desenvolvimento
            dev_engine = create_engine(
                f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
                f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/mobato_dev"
            )
            
            # Criar tabelas
            with dev_engine.connect() as dev_conn:
                # Criar tabela cars
                dev_conn.execute(text("""
                CREATE TABLE cars (
                    id SERIAL PRIMARY KEY,
                    original_id BIGINT UNIQUE,
                    manufacturer VARCHAR(100),
                    model VARCHAR(100),
                    year INTEGER,
                    price DECIMAL(10,2),
                    condition VARCHAR(50),
                    odometer INTEGER,
                    title_status VARCHAR(50),
                    transmission VARCHAR(50),
                    region VARCHAR(100),
                    has_installments BOOLEAN DEFAULT FALSE,
                    monthly_payment DECIMAL(10,2),
                    down_payment DECIMAL(10,2),
                    installments INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """))
                
                # Criar índices
                dev_conn.execute(text("CREATE INDEX idx_cars_manufacturer ON cars(manufacturer)"))
                dev_conn.execute(text("CREATE INDEX idx_cars_year ON cars(year)"))
                dev_conn.execute(text("CREATE INDEX idx_cars_price ON cars(price)"))
                
                # Criar view clean_cars
                dev_conn.execute(text("""
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
                    c.manufacturer IS NOT NULL
                    AND c.model IS NOT NULL
                    AND c.year IS NOT NULL
                    AND c.price IS NOT NULL
                    AND c.year BETWEEN 1900 AND 2024
                    AND c.price > 0
                    AND c.price >= ms.mean_price * 0.1
                    AND c.price <= ms.mean_price + (3 * ms.std_price)
                    AND (
                        (c.has_installments = TRUE AND 
                         c.monthly_payment > 0 AND 
                         c.installments > 0 AND
                         c.installments <= 120 AND
                         ABS(c.price - (c.monthly_payment * c.installments + COALESCE(c.down_payment, 0))) <= 0.01)
                        OR 
                        (c.has_installments = FALSE)
                    )
                    AND (c.odometer IS NULL OR (c.odometer > 0 AND c.odometer < 1000000))
                """))
                
                dev_conn.commit()
            
            logger.info("Banco de dados de desenvolvimento configurado com sucesso")
            
    except Exception as e:
        logger.error(f"Erro ao configurar banco de dados: {str(e)}")
        sys.exit(1)

def setup_test_database():
    """Configura o banco de dados de testes."""
    logger.info("Configurando banco de dados de testes...")
    
    # Criar conexão com o banco de dados
    engine = create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/postgres"
    )
    
    try:
        with engine.connect() as conn:
            # Criar banco de dados de testes
            conn.execute(text("COMMIT"))  # Fechar transação atual
            conn.execute(text("DROP DATABASE IF EXISTS mobato_test"))
            conn.execute(text("CREATE DATABASE mobato_test"))
            
            # Conectar ao banco de testes
            test_engine = create_engine(
                f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
                f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/mobato_test"
            )
            
            # Criar tabelas (mesma estrutura do banco de desenvolvimento)
            with test_engine.connect() as test_conn:
                # Criar tabela cars
                test_conn.execute(text("""
                CREATE TABLE cars (
                    id SERIAL PRIMARY KEY,
                    original_id BIGINT UNIQUE,
                    manufacturer VARCHAR(100),
                    model VARCHAR(100),
                    year INTEGER,
                    price DECIMAL(10,2),
                    condition VARCHAR(50),
                    odometer INTEGER,
                    title_status VARCHAR(50),
                    transmission VARCHAR(50),
                    region VARCHAR(100),
                    has_installments BOOLEAN DEFAULT FALSE,
                    monthly_payment DECIMAL(10,2),
                    down_payment DECIMAL(10,2),
                    installments INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """))
                
                # Criar índices
                test_conn.execute(text("CREATE INDEX idx_cars_manufacturer ON cars(manufacturer)"))
                test_conn.execute(text("CREATE INDEX idx_cars_year ON cars(year)"))
                test_conn.execute(text("CREATE INDEX idx_cars_price ON cars(price)"))
                
                # Criar view clean_cars
                test_conn.execute(text("""
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
                    c.manufacturer IS NOT NULL
                    AND c.model IS NOT NULL
                    AND c.year IS NOT NULL
                    AND c.price IS NOT NULL
                    AND c.year BETWEEN 1900 AND 2024
                    AND c.price > 0
                    AND c.price >= ms.mean_price * 0.1
                    AND c.price <= ms.mean_price + (3 * ms.std_price)
                    AND (
                        (c.has_installments = TRUE AND 
                         c.monthly_payment > 0 AND 
                         c.installments > 0 AND
                         c.installments <= 120 AND
                         ABS(c.price - (c.monthly_payment * c.installments + COALESCE(c.down_payment, 0))) <= 0.01)
                        OR 
                        (c.has_installments = FALSE)
                    )
                    AND (c.odometer IS NULL OR (c.odometer > 0 AND c.odometer < 1000000))
                """))
                
                test_conn.commit()
            
            logger.info("Banco de dados de testes configurado com sucesso")
            
    except Exception as e:
        logger.error(f"Erro ao configurar banco de dados de testes: {str(e)}")
        sys.exit(1)

def main():
    """Função principal."""
    try:
        # Configurar ambiente virtual
        setup_virtual_env()
        
        # Configurar bancos de dados
        setup_dev_database()
        setup_test_database()
        
        logger.info("Ambiente de desenvolvimento configurado com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante a configuração: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 