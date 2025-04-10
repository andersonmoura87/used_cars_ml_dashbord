import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_dataset():
    """Processa o dataset completo."""
    load_dotenv()
    
    input_file = os.getenv('RAW_DATA_PATH')
    output_file = os.path.join(
        os.getenv('PROCESSED_DATA_PATH'),
        'used_cars_processed.csv'
    )
    
    try:
        # Ler o arquivo CSV
        logger.info("Lendo o arquivo CSV...")
        df = pd.read_csv(input_file)
        
        # Tratamento de dados
        logger.info("Processando dados...")
        
        # 1. Tratamento de valores nulos
        # Para colunas categóricas, substituir por 'unknown'
        categorical_cols = ['manufacturer', 'model', 'condition', 'cylinders', 
                          'fuel', 'title_status', 'transmission', 'drive', 
                          'size', 'type', 'paint_color']
        for col in categorical_cols:
            df[col] = df[col].fillna('unknown')
        
        # Para colunas numéricas, substituir pela mediana
        numeric_cols = ['year', 'odometer', 'lat', 'long']
        for col in numeric_cols:
            df[col] = df[col].fillna(df[col].median())
        
        # 2. Limpeza de dados
        # Remover registros com preço zero ou negativo
        df = df[df['price'] > 0]
        
        # Remover registros com ano inválido (antes de 1900)
        df = df[df['year'] >= 1900]
        
        # 3. Criação de novas features
        # Idade do veículo
        df['vehicle_age'] = 2024 - df['year']
        
        # Categorização de preço
        df['price_category'] = pd.cut(df['price'], 
                                    bins=[0, 10000, 20000, 30000, 50000, float('inf')],
                                    labels=['<10k', '10k-20k', '20k-30k', '30k-50k', '>50k'])
        
        # 4. Salvar dataset processado
        logger.info(f"Salvando dataset processado com {len(df):,} registros...")
        df.to_csv(output_file, index=False)
        
        # 5. Gerar estatísticas do dataset processado
        logger.info("\nEstatísticas do dataset processado:")
        logger.info(f"Total de registros: {len(df):,}")
        
        logger.info("\nDistribuição por fabricante (top 10):")
        logger.info(df['manufacturer'].value_counts().head(10))
        
        logger.info("\nDistribuição por ano:")
        logger.info(df['year'].value_counts().sort_index().head())
        
        logger.info("\nDistribuição por combustível:")
        logger.info(df['fuel'].value_counts())
        
        logger.info("\nDistribuição por estado (top 10):")
        logger.info(df['state'].value_counts().head(10))
        
        logger.info("\nDistribuição por categoria de preço:")
        logger.info(df['price_category'].value_counts())
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao processar dataset: {str(e)}")
        return False

if __name__ == "__main__":
    process_dataset() 