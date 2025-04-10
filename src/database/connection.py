from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging
from dotenv import load_dotenv
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def get_database_url():
    """Retorna a URL de conexão com o banco de dados."""
    return (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

def create_db_engine():
    """Cria e retorna uma engine do SQLAlchemy."""
    try:
        engine = create_engine(
            get_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={
                'client_encoding': 'utf8',
                'options': '-c client_encoding=utf8'
            }
        )
        # Testar conexão
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        
        logger.info("Engine do banco de dados criada com sucesso")
        return engine
    except SQLAlchemyError as e:
        logger.error(f"Erro ao criar engine do banco de dados: {str(e)}")
        raise

def get_db_session():
    """Cria e retorna uma sessão do banco de dados."""
    try:
        engine = create_db_engine()
        Session = sessionmaker(bind=engine)
        return Session()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao criar sessão do banco de dados: {str(e)}")
        raise

def test_connection():
    """Testa a conexão com o banco de dados."""
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();")).scalar()
            logger.info(f"Conectado ao PostgreSQL. Versão: {result}")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Erro ao testar conexão: {str(e)}")
        return False

def get_db_connection():
    """Cria conexão com o banco de dados PostgreSQL."""
    try:
        # Obter credenciais do ambiente
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'mobato')
        db_user = os.getenv('DB_USER', 'postgres')
        db_pass = os.getenv('DB_PASSWORD', 'postgres')
        
        # Criar string de conexão
        connection_string = (
            f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'
        )
        
        # Criar engine com configurações de codificação
        engine = create_engine(
            connection_string,
            client_encoding='utf8',
            connect_args={'options': '-c client_encoding=utf8'}
        )
        
        # Testar conexão
        with engine.connect() as conn:
            logger.info('Conexão com o banco de dados estabelecida com sucesso!')
        
        return engine
    
    except Exception as e:
        logger.error(f'Erro ao conectar ao banco de dados: {str(e)}')
        raise 