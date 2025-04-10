import os
import subprocess
import sys

# Executar o script Python e capturar a saída
result = subprocess.run(
    [sys.executable, "-c", """
import os
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

# Carregar variáveis de ambiente
logging.info("1. Carregando variáveis de ambiente...")
load_dotenv()

# Criar a string de conexão
logging.info("2. Criando string de conexão...")
connection_string = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
logging.info(f"String de conexão: {connection_string}")

# Criar engine com configurações de codificação
logging.info("3. Criando engine...")
engine = create_engine(
    connection_string,
    connect_args={
        'client_encoding': 'utf8',
        'options': '-c client_encoding=utf8'
    }
)

# Configurar a codificação da conexão
logging.info("4. Conectando ao banco...")
try:
    with engine.connect() as conn:
        logging.info("5. Configurando codificação...")
        # Configurar a codificação
        conn.execute(text("SET client_encoding TO 'UTF8'"))
        conn.execute(text("SET standard_conforming_strings TO on"))
        
        # Testar a conexão com uma query simples
        logging.info("6. Testando conexão...")
        query = "SELECT version();"
        result = conn.execute(text(query))
        logging.info(f"Versão do PostgreSQL: {result.scalar()}")
        
        # Verificar se a tabela cars_cleaned existe
        logging.info("7. Verificando tabela cars_cleaned...")
        query = '''
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name = 'cars_cleaned'
        );
        '''
        result = conn.execute(text(query))
        table_exists = result.scalar()
        logging.info(f"Tabela cars_cleaned existe? {'Sim' if table_exists else 'Não'}")
        
        if table_exists:
            # Verificar estrutura da tabela
            logging.info("8. Verificando estrutura da tabela...")
            query = '''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'cars_cleaned';
            '''
            result = conn.execute(text(query))
            logging.info("Colunas da tabela cars_cleaned:")
            for row in result:
                logging.info(f"- {row[0]}: {row[1]}")
            
            # Testar uma query com dados
            logging.info("9. Testando query com dados...")
            query = '''
            SELECT manufacturer, COUNT(*) as total
            FROM cars_cleaned
            GROUP BY manufacturer
            LIMIT 5;
            '''
            df = pd.read_sql(query, conn)
            logging.info("\\nPrimeiros 5 fabricantes:")
            logging.info(df.to_string())
            
    logging.info("10. Conexão fechada com sucesso!")
except Exception as e:
    logging.error(f"ERRO: {str(e)}")
    logging.error(f"Tipo do erro: {type(e)}")
    raise e
"""],
    capture_output=True,
    text=True
)

# Imprimir a saída
print(result.stdout)
print(result.stderr) 