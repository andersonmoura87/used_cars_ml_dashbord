import os
import sys
import logging
from dotenv import load_dotenv
import psycopg2

# Configurar logging para escrever no stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# Forçar flush do stdout
sys.stdout.reconfigure(line_buffering=True)

logger.info("1. Carregando variáveis de ambiente...")
load_dotenv()

logger.info("2. Verificando variáveis de ambiente...")
db_params = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'client_encoding': 'LATIN1'
}

for key, value in db_params.items():
    if value is None:
        logger.error(f"Variável {key} não encontrada!")
    else:
        logger.info(f"Variável {key} encontrada")

logger.info("3. Tentando conectar ao banco de dados...")
try:
    conn = psycopg2.connect(**db_params)
    logger.info("4. Conexão estabelecida com sucesso!")
    
    with conn.cursor() as cur:
        logger.info("5. Configurando codificação...")
        cur.execute("SET client_encoding TO 'LATIN1';")
        cur.execute("SET standard_conforming_strings TO on;")
        
        logger.info("6. Executando query de teste...")
        cur.execute("SELECT version();")
        version = cur.fetchone()
        logger.info(f"Versão do PostgreSQL: {version[0]}")
        
        logger.info("7. Verificando tabelas disponíveis...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        tables = cur.fetchall()
        logger.info("Tabelas encontradas:")
        for table in tables:
            logger.info(f"- {table[0]}")
        
        logger.info("8. Testando leitura de dados...")
        cur.execute("""
            SELECT manufacturer, COUNT(*) as total
            FROM cars_cleaned
            GROUP BY manufacturer
            LIMIT 5;
        """)
        rows = cur.fetchall()
        logger.info("\nPrimeiros 5 fabricantes:")
        for row in rows:
            logger.info(f"- {row[0]}: {row[1]}")
    
    conn.close()
    logger.info("9. Conexão fechada com sucesso!")
except Exception as e:
    logger.error("Erro durante a execução:")
    logger.error(str(e))
    logger.error(f"Tipo do erro: {type(e)}")
    raise e

# Forçar flush final
sys.stdout.flush() 