import pandas as pd
import numpy as np
import os
import sys
import logging
from pathlib import Path

# Adicionar o diretório src ao path para importar o módulo app
sys.path.append(str(Path(__file__).parent.parent))

from app import load_data, load_predictions

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_data_for_powerbi():
    try:
        # Criar diretório para dados do Power BI se não existir
        output_dir = Path('data/powerbi')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Carregar dados
        logger.info("Carregando dados para exportação...")
        df = load_data()
        predictions = load_predictions()
        
        if df is not None:
            # Exportar dados principais
            main_data_path = output_dir / 'cars_data.csv'
            logger.info(f"Exportando dados principais para {main_data_path}")
            df.to_csv(main_data_path, index=False, encoding='utf-8')
            
            # Criar e exportar agregações úteis para o Power BI
            
            # Agregação por fabricante
            manufacturer_agg = df.groupby('manufacturer').agg({
                'price': ['count', 'mean', 'min', 'max'],
                'odometer': 'mean',
                'year': 'mean'
            }).round(2)
            manufacturer_agg.columns = ['total_listings', 'avg_price', 'min_price', 'max_price', 'avg_odometer', 'avg_year']
            manufacturer_agg.to_csv(output_dir / 'manufacturer_metrics.csv', encoding='utf-8')
            
            # Agregação por região
            region_agg = df.groupby(['region', 'state']).agg({
                'price': ['count', 'mean'],
                'odometer': 'mean'
            }).round(2)
            region_agg.columns = ['total_listings', 'avg_price', 'avg_odometer']
            region_agg.to_csv(output_dir / 'region_metrics.csv', encoding='utf-8')
            
            # Agregação temporal
            df['posting_month'] = df['posting_date'].dt.to_period('M')
            time_agg = df.groupby('posting_month').agg({
                'price': ['count', 'mean'],
                'odometer': 'mean'
            }).round(2)
            time_agg.columns = ['total_listings', 'avg_price', 'avg_odometer']
            time_agg.to_csv(output_dir / 'time_metrics.csv', encoding='utf-8')
        
        if predictions is not None:
            # Exportar previsões
            predictions_path = output_dir / 'predictions.csv'
            logger.info(f"Exportando previsões para {predictions_path}")
            predictions.to_csv(predictions_path, index=False, encoding='utf-8')
        
        logger.info("Exportação concluída com sucesso!")
        
        # Retornar instruções para o Power BI
        return """
        Arquivos exportados com sucesso! Para configurar o Power BI:

        1. Abra o Power BI Desktop
        2. Clique em 'Obter Dados' > 'Texto/CSV'
        3. Navegue até a pasta 'data/powerbi' e importe os seguintes arquivos:
           - cars_data.csv (dados principais)
           - manufacturer_metrics.csv (métricas por fabricante)
           - region_metrics.csv (métricas por região)
           - time_metrics.csv (métricas temporais)
           - predictions.csv (previsões)
        4. Para cada arquivo:
           - Selecione a codificação UTF-8
           - Verifique se os tipos de dados estão corretos
           - Aplique as transformações necessárias
        5. Crie as relações entre as tabelas conforme necessário
        """
        
    except Exception as e:
        logger.error(f"Erro durante a exportação: {str(e)}")
        return f"Erro durante a exportação: {str(e)}"

if __name__ == "__main__":
    instructions = export_data_for_powerbi()
    print(instructions) 