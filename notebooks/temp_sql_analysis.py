import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import sys
import psycopg2
import logging
import pathlib

# Configurar logging
current_dir = pathlib.Path(__file__).parent.parent.absolute()
log_file = current_dir / 'logs' / 'sql_analysis.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=str(log_file),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Sobrescrever o arquivo a cada execução
)

# Adicionar logging também para o console
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def test_connection():
    """Testa a conexão com o banco de dados usando psycopg2 diretamente."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        print("Variáveis de ambiente carregadas:")
        print(f"DB_HOST: {os.getenv('DB_HOST')}")
        print(f"DB_PORT: {os.getenv('DB_PORT')}")
        print(f"DB_NAME: {os.getenv('DB_NAME')}")
        print(f"DB_USER: {os.getenv('DB_USER')}")
        print(f"DB_PASSWORD: {'*' * len(os.getenv('DB_PASSWORD', ''))}")

        # Tentar conectar
        print("\nTentando conectar ao PostgreSQL...")
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        
        # Verificar versão do PostgreSQL
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"\nConexão bem sucedida!")
        print(f"Versão do PostgreSQL: {version[0]}")
        
        # Verificar se a tabela cars_cleaned existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'cars_cleaned'
            );
        """)
        table_exists = cur.fetchone()[0]
        print(f"\nTabela cars_cleaned existe? {'Sim' if table_exists else 'Não'}")
        
        if table_exists:
            # Verificar estrutura da tabela
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'cars_cleaned';
            """)
            columns = cur.fetchall()
            print("\nColunas da tabela cars_cleaned:")
            for col in columns:
                print(f"- {col[0]}: {col[1]}")
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\nERRO DE CONEXÃO: {str(e)}")
        print("\nPossíveis causas:")
        print("1. PostgreSQL não está rodando")
        print("2. Credenciais incorretas")
        print("3. Banco de dados não existe")
        print("4. Porta incorreta")
        return False
    except Exception as e:
        print(f"\nERRO INESPERADO: {str(e)}")
        print(f"Tipo do erro: {type(e)}")
        return False

def main():
    logging.info("1. Iniciando o script...")

    # Configurar visualização
    plt.style.use('seaborn-v0_8')
    sns.set_palette('husl')

    # Configurar conexão com o banco
    load_dotenv()
    logging.info("2. Arquivo .env carregado")
    logging.info(f"DB_HOST: {os.getenv('DB_HOST')}")
    logging.info(f"DB_PORT: {os.getenv('DB_PORT')}")
    logging.info(f"DB_NAME: {os.getenv('DB_NAME')}")
    logging.info(f"DB_USER: {os.getenv('DB_USER')}")

    # Testar conexão primeiro
    if not test_connection():
        logging.error("Falha ao testar conexão com o banco. Verifique se o PostgreSQL está rodando.")
        return

    # Criar a string de conexão com codificação explícita
    connection_string = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    logging.info("3. String de conexão criada")

    # Criar engine com configurações de codificação
    try:
        engine = create_engine(
            connection_string,
            connect_args={
                'client_encoding': 'utf8',
                'options': '-c client_encoding=utf8'
            }
        )
        logging.info("4. Engine criada com sucesso")

        # Configurar a codificação da conexão
        with engine.connect() as conn:
            conn.execute(text("SET client_encoding TO 'UTF8'"))
            conn.execute(text("SET standard_conforming_strings TO on"))
            logging.info("5. Codificação configurada")

            # Teste da conexão
            query = '''
            SELECT 
                manufacturer,
                COUNT(*) as total_vehicles,
                ROUND(AVG(price)::numeric, 2) as avg_price,
                ROUND(MIN(price)::numeric, 2) as min_price,
                ROUND(MAX(price)::numeric, 2) as max_price
            FROM cars_cleaned
            GROUP BY manufacturer
            HAVING COUNT(*) > 10
            ORDER BY avg_price DESC;
            '''
            logging.info("6. Executando query...")

            df_prices = pd.read_sql(query, conn)
            logging.info("7. Query executada com sucesso!")
            
            logging.info("\nPreço médio por fabricante:")
            logging.info("\n" + str(df_prices))

    except Exception as e:
        logging.error(f"\nERRO: {str(e)}")
        logging.error(f"Tipo do erro: {type(e)}")
        raise e
    
    logging.info("8. Script finalizado")

if __name__ == "__main__":
    test_connection() 