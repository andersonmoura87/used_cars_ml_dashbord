import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_database():
    """Cria o banco de dados se ele não existir."""
    load_dotenv()
    
    # Conectar ao PostgreSQL
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    try:
        # Criar cursor
        cur = conn.cursor()
        
        # Verificar se o banco de dados existe
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (os.getenv('DB_NAME'),))
        exists = cur.fetchone()
        
        if not exists:
            # Criar banco de dados
            cur.execute(f"CREATE DATABASE {os.getenv('DB_NAME')}")
            logger.info(f"Banco de dados {os.getenv('DB_NAME')} criado com sucesso!")
        else:
            logger.info(f"Banco de dados {os.getenv('DB_NAME')} já existe.")
            
    except Exception as e:
        logger.error(f"Erro ao criar banco de dados: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_database() 