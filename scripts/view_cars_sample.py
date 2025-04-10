#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_value(x):
    """Formata valores numéricos adequadamente."""
    if pd.isna(x):
        return 'NA'
    if isinstance(x, (int, np.integer)):
        return f"{x:d}"
    if isinstance(x, (float, np.floating)):
        return f"{x:.2f}"
    return str(x)

def main():
    """Exibe uma amostra dos dados do arquivo cars_abt.csv"""
    try:
        # Define o caminho do arquivo
        file_path = Path('data/processed/cars_abt.csv')
        
        # Verifica se o arquivo existe
        if not file_path.exists():
            logger.error(f"Arquivo não encontrado: {file_path}")
            return
        
        # Lê o arquivo CSV
        df = pd.read_csv(file_path)
        
        # Configura opções de exibição do pandas
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.float_format', format_value)
        
        # Exibe as primeiras 5 linhas
        print("\nAmostra de 5 registros do arquivo cars_abt.csv:")
        print("="*180)
        print(df.head().to_string(formatters={'price': '${:,.2f}'.format}))
        
        # Exibe informações sobre o DataFrame
        print("\nInformações do DataFrame:")
        print("="*180)
        print(f"Total de registros: {len(df):,}")
        print(f"\nColunas disponíveis ({len(df.columns)}):")
        
        # Agrupa colunas por categoria
        categorias = {
            'Identificação': ['original_id', 'manufacturer', 'model', 'year', 'price'],
            'Características': ['condition', 'cylinders', 'fuel', 'odometer', 'transmission', 'vin', 'drive', 'size', 'type', 'paint_color'],
            'Localização': ['region', 'county', 'state', 'latitude', 'longitude', 'distance_to_state_center'],
            'Documentação': ['title_status', 'is_clean_title', 'is_salvage_title', 'is_rebuilt_title', 'is_lien_title'],
            'Anúncio': ['posting_year', 'posting_month', 'posting_day', 'posting_week', 'days_on_market'],
            'Preço': ['price_category', 'price_per_year', 'price_per_mile', 'price_mileage_ratio', 'price_age_ratio'],
            'Mercado': ['avg_price_by_manufacturer', 'avg_price_by_model', 'avg_price_by_type', 'avg_price_by_state'],
            'Competição': ['competitors_same_model', 'competitors_same_type', 'market_share_manufacturer', 'market_share_model'],
            'Temporal': ['is_weekend', 'is_holiday', 'is_summer', 'is_winter']
        }
        
        for categoria, cols in categorias.items():
            cols_existentes = [col for col in cols if col in df.columns]
            if cols_existentes:
                print(f"\n{categoria}:")
                for col in cols_existentes:
                    print(f"  - {col}")
        
        # Exibe algumas estatísticas básicas
        print("\nEstatísticas básicas:")
        print("="*180)
        print("\nPreços por categoria de veículo:")
        price_stats = df.groupby('manufacturer')['price'].agg(['count', 'mean', 'min', 'max']).round(2)
        price_stats = price_stats.sort_values('count', ascending=False).head()
        print(price_stats.to_string(formatters={
            'count': '{:,.0f}'.format,
            'mean': '${:,.2f}'.format,
            'min': '${:,.2f}'.format,
            'max': '${:,.2f}'.format
        }))
        
    except Exception as e:
        logger.error(f"Erro ao processar arquivo: {str(e)}")

if __name__ == "__main__":
    main() 