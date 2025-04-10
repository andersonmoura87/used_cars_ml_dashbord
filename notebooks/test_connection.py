import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()
logger.info("Variáveis de ambiente carregadas")

# Configurar conexão com o banco
connection_string = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
connection_string += "?client_encoding=utf8"
engine = create_engine(connection_string)

# Testar conexão
try:
    with engine.connect() as conn:
        # Testar conexão
        conn.execute("SELECT 1")
        logger.info("Conexão com o banco de dados estabelecida com sucesso")
        
        # Verificar tabelas existentes
        tables = pd.read_sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", conn)
        logger.info(f"Tabelas encontradas: {tables['table_name'].tolist()}")
        
        # Se houver tabelas, mostrar algumas linhas de cada uma
        for table in tables['table_name']:
            try:
                df = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", conn)
                logger.info(f"\nPrimeiras 5 linhas da tabela {table}:")
                logger.info(df)
            except Exception as e:
                logger.error(f"Erro ao ler tabela {table}: {str(e)}")
                
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
    raise 