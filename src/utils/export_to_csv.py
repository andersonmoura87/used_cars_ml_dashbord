import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()

# Configurar conexão
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

# Configurar codificação
conn.set_client_encoding('LATIN1')

# Query para selecionar dados
query = """
SELECT manufacturer, model, year, price, odometer, fuel, condition, 
       region, posting_date, state, latitude, longitude
FROM cars_cleaned
WHERE price > 0 
AND year >= 1990 
AND posting_date IS NOT NULL
"""

# Criar diretório data se não existir
os.makedirs('data/temp', exist_ok=True)

# Carregar dados e salvar em CSV
df = pd.read_sql(query, conn)
df.to_csv('data/temp/cars_cleaned.csv', index=False, encoding='utf-8')

print(f"Dados exportados com sucesso: {len(df)} registros")

# Fechar conexão
conn.close() 