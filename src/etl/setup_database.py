import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def get_database_url():
    """Retorna a URL de conexão com o banco de dados."""
    return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

def create_database_connection():
    """Cria uma conexão com o banco de dados."""
    try:
        engine = create_engine(get_database_url())
        logger.info("Conexão com o banco de dados estabelecida com sucesso")
        return engine
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        raise

def execute_sql_file(engine, file_path):
    """Executa um arquivo SQL."""
    try:
        with open(file_path, 'r') as file:
            sql = file.read()
            with engine.connect() as conn:
                conn.execute(sql)
                conn.commit()
        logger.info(f"Arquivo SQL {file_path} executado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao executar arquivo SQL {file_path}: {str(e)}")
        raise

def load_data(engine, data_path):
    """Carrega os dados do CSV para o banco de dados."""
    try:
        # Ler o CSV em chunks para lidar com o grande volume de dados
        chunksize = 10000
        for chunk in pd.read_csv(data_path, chunksize=chunksize):
            # Processar dados se necessário
            chunk.to_sql('used_cars', engine, if_exists='append', index=False)
            logger.info(f"Chunk de {len(chunk)} registros carregado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        raise

def main():
    """Função principal para configurar o banco de dados."""
    try:
        # Criar conexão
        engine = create_database_connection()
        
        # Executar schema
        schema_path = 'sql/schemas/create_tables.sql'
        execute_sql_file(engine, schema_path)
        
        # Carregar dados
        data_path = os.getenv('RAW_DATA_PATH')
        if os.path.exists(data_path):
            load_data(engine, data_path)
        else:
            logger.error(f"Arquivo de dados não encontrado: {data_path}")
            
        logger.info("Configuração do banco de dados concluída com sucesso")
        
    except Exception as e:
        logger.error(f"Erro durante a configuração do banco de dados: {str(e)}")
        raise

if __name__ == "__main__":
    main() 