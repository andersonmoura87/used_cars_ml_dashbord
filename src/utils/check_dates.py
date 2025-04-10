import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

def check_dates():
    # Configurar conexão com o banco
    load_dotenv()
    engine = create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    )

    # Carregar alguns exemplos de datas
    df = pd.read_sql('SELECT posting_date FROM cars_cleaned LIMIT 5', engine)
    
    print("Tipo da coluna:", df['posting_date'].dtype)
    print("\nExemplos de valores:")
    print(df['posting_date'])

if __name__ == "__main__":
    check_dates() 