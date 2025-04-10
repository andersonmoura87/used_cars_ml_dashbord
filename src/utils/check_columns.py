import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

def check_columns():
    # Configurar conexão com o banco
    load_dotenv()
    engine = create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    )

    # Carregar um registro para ver as colunas
    df = pd.read_sql('SELECT * FROM cars_cleaned LIMIT 1', engine)
    
    print("Colunas disponíveis:")
    for col in df.columns:
        print(f"- {col}")

if __name__ == "__main__":
    check_columns() 