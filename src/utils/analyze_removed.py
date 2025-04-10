import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

def analyze_removed_cars():
    """Analisa os carros removidos com preços abaixo de $500."""
    load_dotenv()
    
    # Configurar conexão com o banco
    engine = create_engine(f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}')
    
    # Consulta para carros removidos com preços abaixo de $500
    query = """
    SELECT 
        manufacturer,
        model,
        year,
        state,
        price,
        description,
        COUNT(*) as count
    FROM cars_removed 
    WHERE price < 500 
    GROUP BY manufacturer, model, year, state, price, description
    ORDER BY price DESC
    """
    
    df = pd.read_sql(query, engine)
    
    # Imprimir estatísticas
    print("\nEstatísticas dos carros removidos com preços abaixo de $500:")
    print("=" * 80)
    print(f"Total de registros únicos: {len(df)}")
    
    print("\nTop 10 fabricantes mais frequentes:")
    print(df['manufacturer'].value_counts().head(10))
    
    print("\nTop 10 modelos mais frequentes:")
    print(df['model'].value_counts().head(10))
    
    print("\nDistribuição por ano:")
    print(df['year'].value_counts().sort_index())
    
    print("\nDistribuição por estado:")
    print(df['state'].value_counts().head(10))
    
    print("\nExemplos de registros:")
    print(df.head(10).to_string())

if __name__ == "__main__":
    analyze_removed_cars() 