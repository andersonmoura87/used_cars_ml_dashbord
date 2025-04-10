import logging
from datetime import datetime
import json
import os
from pathlib import Path

from src.etl.extract import extract_data
from src.etl.transform import transform_data
from src.etl.load import load_data
from src.database.connection import test_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def save_metadata(metadata, step):
    """Salva os metadados de cada etapa do pipeline."""
    try:
        # Criar diretório de metadados se não existir
        metadata_dir = Path('logs/metadata')
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{step}_{timestamp}.json"
        
        # Salvar metadados
        with open(metadata_dir / filename, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Metadados de {step} salvos em {filename}")
    except Exception as e:
        logger.error(f"Erro ao salvar metadados de {step}: {str(e)}")

def run_pipeline():
    """Executa o pipeline ETL completo."""
    try:
        pipeline_start = datetime.now()
        logger.info("Iniciando pipeline ETL")
        
        # Testar conexão com o banco
        if not test_connection():
            raise Exception("Não foi possível conectar ao banco de dados")
        
        # Extração
        logger.info("Iniciando etapa de extração")
        df, extract_metadata = extract_data()
        save_metadata(extract_metadata, 'extract')
        
        # Transformação
        logger.info("Iniciando etapa de transformação")
        df_clean, df_removed, market_stats, transform_metadata = transform_data(df)
        save_metadata(transform_metadata, 'transform')
        
        # Carregamento
        logger.info("Iniciando etapa de carregamento")
        load_metadata = load_data(df_clean, market_stats)
        save_metadata(load_metadata, 'load')
        
        # Metadados do pipeline
        pipeline_end = datetime.now()
        pipeline_metadata = {
            'pipeline_start': pipeline_start.isoformat(),
            'pipeline_end': pipeline_end.isoformat(),
            'duration_seconds': (pipeline_end - pipeline_start).total_seconds(),
            'total_input_records': len(df),
            'total_clean_records': len(df_clean),
            'total_removed_records': len(df_removed),
            'total_market_stats': len(market_stats)
        }
        save_metadata(pipeline_metadata, 'pipeline')
        
        logger.info("Pipeline ETL concluído com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro no pipeline ETL: {str(e)}")
        return False

if __name__ == "__main__":
    run_pipeline() 