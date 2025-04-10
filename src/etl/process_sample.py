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

def process_sample(input_file, output_file, sample_size=100_000):
    """
    Processa a amostra do dataset mantendo a representatividade.
    
    Args:
        input_file: Caminho do arquivo CSV original
        output_file: Caminho para salvar a amostra
        sample_size: Tamanho da amostra desejada (default: 100,000)
    """
    try:
        # Ler o arquivo CSV
        logger.info("Lendo o arquivo CSV...")
        df = pd.read_csv(input_file)
        
        # Criar estratificação
        logger.info("Criando estratificação...")
        df['strata'] = df['manufacturer'].fillna('unknown') + '_' + \
                      df['year'].fillna(-1).astype(str) + '_' + \
                      df['fuel'].fillna('unknown') + '_' + \
                      df['state'].fillna('unknown')
        
        # Calcular proporções originais
        proportions = df['strata'].value_counts(normalize=True)
        
        # Calcular tamanho da amostra por estrato
        sample_sizes = (proportions * sample_size).round().astype(int)
        
        # Garantir que a soma não exceda o tamanho desejado
        while sample_sizes.sum() > sample_size:
            # Reduzir uma amostra do maior estrato
            max_stratum = sample_sizes.idxmax()
            sample_sizes[max_stratum] -= 1
        
        # Coletar amostra estratificada
        logger.info("Coletando amostra estratificada...")
        sampled_df = pd.DataFrame()
        for stratum, size in sample_sizes.items():
            if size > 0:
                stratum_sample = df[df['strata'] == stratum].sample(
                    n=min(size, len(df[df['strata'] == stratum])),
                    random_state=42
                )
                sampled_df = pd.concat([sampled_df, stratum_sample])
        
        # Remover coluna de estratificação
        sampled_df = sampled_df.drop('strata', axis=1)
        
        # Salvar amostra
        logger.info(f"Salvando amostra de {len(sampled_df):,} registros...")
        sampled_df.to_csv(output_file, index=False)
        
        # Mostrar estatísticas da amostra
        logger.info("\nEstatísticas da amostra:")
        logger.info(f"Total de registros: {len(sampled_df):,}")
        logger.info("\nDistribuição por fabricante:")
        logger.info(sampled_df['manufacturer'].value_counts().head())
        logger.info("\nDistribuição por ano:")
        logger.info(sampled_df['year'].value_counts().head())
        logger.info("\nDistribuição por combustível:")
        logger.info(sampled_df['fuel'].value_counts().head())
        logger.info("\nDistribuição por estado:")
        logger.info(sampled_df['state'].value_counts().head())
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao processar amostra: {str(e)}")
        return False

if __name__ == "__main__":
    load_dotenv()
    
    input_file = os.getenv('RAW_DATA_PATH')
    output_file = os.path.join(
        os.getenv('PROCESSED_DATA_PATH'),
        'used_cars_sample.csv'
    )
    
    process_sample(input_file, output_file) 