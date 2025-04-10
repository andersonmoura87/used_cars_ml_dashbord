import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """Retorna a URL de conexão com o banco de dados."""
    load_dotenv()
    return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

def test_connection():
    """Testa a conexão com o banco de dados."""
    try:
        # Criar engine
        engine = create_engine(get_database_url())
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Conexão com o banco de dados estabelecida com sucesso!")
            return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return False

if __name__ == "__main__":
    test_connection() 