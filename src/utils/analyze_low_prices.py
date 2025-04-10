import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import re

def extract_financing_info(description):
    """Extrai informações de financiamento da descrição."""
    info = {
        'down_payment': None,
        'monthly_payment': None,
        'term_months': None,
        'apr': None,
        'real_price': None
    }
    
    # Padrões para extrair informações
    patterns = {
        'down_payment': r'\$(\d+)\s*(?:down|entrada)',
        'monthly_payment': r'\$(\d+)\s*(?:monthly|mensal)',
        'term_months': r'(\d+)\s*(?:months|meses)',
        'apr': r'(\d+\.?\d*)%\s*APR',
        'real_price': r'price\s*of\s*\$(\d+,?\d*)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, description.lower())
        if match:
            value = match.group(1).replace(',', '')
            if key in ['down_payment', 'monthly_payment', 'real_price']:
                info[key] = float(value)
            elif key in ['term_months', 'apr']:
                info[key] = float(value)
    
    return info

def analyze_low_prices():
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
        description
    FROM cars_removed 
    WHERE price < 500 
    ORDER BY price DESC
    """
    
    df = pd.read_sql(query, engine)
    
    # Extrair informações de financiamento
    financing_info = df['description'].apply(extract_financing_info)
    df['financing_info'] = financing_info
    
    # Imprimir estatísticas
    print("\nAnálise dos carros removidos com preços abaixo de $500:")
    print("=" * 80)
    print(f"Total de registros: {len(df)}")
    
    print("\nTop 10 fabricantes mais frequentes:")
    print(df['manufacturer'].value_counts().head(10))
    
    print("\nTop 10 modelos mais frequentes:")
    print(df['model'].value_counts().head(10))
    
    print("\nDistribuição por ano:")
    print(df['year'].value_counts().sort_index())
    
    print("\nDistribuição por estado:")
    print(df['state'].value_counts().head(10))
    
    print("\nDetalhes de financiamento dos primeiros 10 registros:")
    for idx, row in df.head(10).iterrows():
        print(f"\n{row['manufacturer']} {row['model']} {row['year']} - ${row['price']}")
        print(f"Estado: {row['state']}")
        info = row['financing_info']
        if info['real_price']:
            print(f"Preço real: ${info['real_price']:,.2f}")
        if info['down_payment']:
            print(f"Entrada: ${info['down_payment']:,.2f}")
        if info['monthly_payment']:
            print(f"Pagamento mensal: ${info['monthly_payment']:,.2f}")
        if info['term_months']:
            print(f"Prazo: {info['term_months']} meses")
        if info['apr']:
            print(f"Taxa de juros: {info['apr']}%")
        print("-" * 80)

if __name__ == "__main__":
    analyze_low_prices() 