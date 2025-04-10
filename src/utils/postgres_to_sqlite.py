import pandas as pd
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

def create_sqlite_db():
    # Carregar variáveis de ambiente
    load_dotenv()
    
    # Conectar ao PostgreSQL
    pg_conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    
    # Criar diretório data se não existir
    os.makedirs('data', exist_ok=True)
    
    # Conectar ao SQLite
    sqlite_conn = sqlite3.connect('data/cars.db')
    
    try:
        # Ler dados do PostgreSQL
        query = """
            SELECT *
            FROM cars_cleaned
            WHERE price > 0 
            AND year >= 1990
            AND posting_date IS NOT NULL
        """
        
        print("Lendo dados do PostgreSQL...")
        df = pd.read_sql(query, pg_conn)
        print(f"Dados lidos com sucesso: {len(df)} registros")
        
        # Salvar no SQLite
        print("Salvando dados no SQLite...")
        df.to_sql('cars_cleaned', sqlite_conn, if_exists='replace', index=False)
        print("Dados salvos com sucesso!")
        
    finally:
        pg_conn.close()
        sqlite_conn.close()

if __name__ == "__main__":
    create_sqlite_db() 