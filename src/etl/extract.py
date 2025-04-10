import pandas as pd
import logging
from dotenv import load_dotenv
import os
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def read_csv_data():
    """Lê os dados do arquivo CSV."""
    try:
        csv_path = os.getenv('RAW_DATA_PATH')
        logger.info(f"Lendo dados do arquivo: {csv_path}")
        
        df = pd.read_csv(
            csv_path,
            parse_dates=['posting_date'],
            date_parser=lambda x: pd.to_datetime(x, utc=True)
        )
        
        logger.info(f"Dados lidos com sucesso. Total de registros: {len(df)}")
        return df
    except Exception as e:
        logger.error(f"Erro ao ler arquivo CSV: {str(e)}")
        raise

def validate_raw_data(df):
    """Valida os dados brutos."""
    try:
        # Verificar colunas obrigatórias
        required_columns = [
            'manufacturer', 'model', 'year', 'price', 'odometer',
            'fuel', 'transmission', 'state', 'posting_date'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Colunas obrigatórias faltando: {missing_columns}")
        
        # Verificar tipos de dados
        type_checks = {
            'manufacturer': 'object',
            'model': 'object',
            'year': 'int64',
            'price': ['int64', 'float64'],
            'odometer': ['int64', 'float64'],
            'fuel': 'object',
            'transmission': 'object',
            'state': 'object'
        }
        
        for col, expected_type in type_checks.items():
            if isinstance(expected_type, list):
                if df[col].dtype not in expected_type:
                    logger.warning(f"Coluna {col} com tipo incorreto: {df[col].dtype}")
            elif df[col].dtype != expected_type:
                logger.warning(f"Coluna {col} com tipo incorreto: {df[col].dtype}")
        
        # Verificar valores nulos
        null_counts = df[required_columns].isnull().sum()
        if null_counts.any():
            logger.warning("Valores nulos encontrados:")
            for col, count in null_counts[null_counts > 0].items():
                logger.warning(f"- {col}: {count} valores nulos")
        
        # Verificar intervalos de valores
        if df['year'].min() < 1900 or df['year'].max() > datetime.now().year:
            logger.warning(f"Anos fora do intervalo esperado: {df['year'].min()} - {df['year'].max()}")
        
        if df['price'].min() < 0:
            logger.warning("Preços negativos encontrados")
        
        if df['odometer'].min() < 0:
            logger.warning("Quilometragens negativas encontradas")
        
        logger.info("Validação dos dados brutos concluída")
        return True
    except Exception as e:
        logger.error(f"Erro na validação dos dados brutos: {str(e)}")
        raise

def extract_data():
    """Função principal de extração dos dados."""
    try:
        # Ler dados
        df = read_csv_data()
        
        # Validar dados
        validate_raw_data(df)
        
        # Salvar metadados da extração
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'source': os.getenv('RAW_DATA_PATH'),
            'total_records': len(df),
            'columns': list(df.columns),
            'dtypes': df.dtypes.to_dict()
        }
        
        logger.info("Extração de dados concluída com sucesso")
        return df, metadata
    except Exception as e:
        logger.error(f"Erro no processo de extração: {str(e)}")
        raise 