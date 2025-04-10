import os
import pandas as pd
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_dataset():
    """Valida o dataset baixado."""
    load_dotenv()
    
    file_path = os.getenv('RAW_DATA_PATH')
    
    try:
        # Verificar se o arquivo existe
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return False
            
        # Ler o arquivo
        logger.info("Lendo o arquivo CSV...")
        df = pd.read_csv(file_path)
        
        # Validar estrutura
        expected_columns = [
            'id', 'price', 'url', 'region', 'region_url', 'year',
            'manufacturer', 'model', 'condition', 'cylinders', 'fuel',
            'odometer', 'title_status', 'transmission', 'VIN', 'drive',
            'size', 'type', 'paint_color', 'image_url', 'description',
            'county', 'state', 'lat', 'long', 'posting_date'
        ]
        
        missing_columns = set(expected_columns) - set(df.columns)
        if missing_columns:
            logger.error(f"Colunas ausentes: {missing_columns}")
            return False
            
        # Informações básicas
        logger.info(f"Número de linhas: {len(df):,}")
        logger.info(f"Número de colunas: {len(df.columns)}")
        logger.info("\nInformações do dataset:")
        logger.info("\nTipos de dados:")
        for col, dtype in df.dtypes.items():
            logger.info(f"{col}: {dtype}")
            
        logger.info("\nValores nulos por coluna:")
        for col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                logger.info(f"{col}: {null_count:,} ({(null_count/len(df))*100:.2f}%)")
        
        # Análise de distribuição para colunas importantes
        logger.info("\nDistribuição por fabricante (top 10):")
        logger.info(df['manufacturer'].value_counts().head(10))
        
        logger.info("\nDistribuição por ano:")
        logger.info(df['year'].value_counts().sort_index().head())
        
        logger.info("\nDistribuição por combustível:")
        logger.info(df['fuel'].value_counts())
        
        logger.info("\nDistribuição por estado (top 10):")
        logger.info(df['state'].value_counts().head(10))
        
        logger.info("\nValidação concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao validar dataset: {str(e)}")
        return False

if __name__ == "__main__":
    validate_dataset() 