#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data():
    """Carrega os dados do arquivo CSV."""
    file_path = Path('data/processed/cars_abt.csv')
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    return pd.read_csv(file_path)

def sql_analysis(df):
    """Realiza análises usando consultas SQL-like com pandas."""
    print("\nParte 1: Consultas SQL")
    print("="*100)
    
    # 1. Preço médio por fabricante
    print("\n1. Preço médio dos veículos por fabricante (top 10):")
    print("-"*80)
    price_by_manufacturer = df.groupby('manufacturer')['price'].agg(['mean', 'count'])\
        .round(2)\
        .sort_values('mean', ascending=False)\
        .head(10)
    print(price_by_manufacturer.to_string(formatters={
        'mean': '${:,.2f}'.format,
        'count': '{:,}'.format
    }))
    
    # 2. Top 5 modelos mais anunciados
    print("\n2. Top 5 modelos mais anunciados e sua quilometragem média:")
    print("-"*80)
    top_models = df.groupby('model').agg({
        'original_id': 'count',
        'odometer': 'mean'
    }).round(2)\
    .sort_values('original_id', ascending=False)\
    .head(5)
    print(top_models.to_string(formatters={
        'original_id': '{:,}'.format,
        'odometer': '{:,.1f}'.format
    }))
    
    # 3. Top 3 tipos de combustível
    print("\n3. Top 3 tipos de combustível e quilometragem média:")
    print("-"*80)
    fuel_stats = df.groupby('fuel').agg({
        'original_id': 'count',
        'odometer': 'mean'
    }).round(2)\
    .sort_values('original_id', ascending=False)\
    .head(3)
    print(fuel_stats.to_string(formatters={
        'original_id': '{:,}'.format,
        'odometer': '{:,.1f}'.format
    }))
    
    # 4. Top 5 regiões por preço médio
    print("\n4. Top 5 regiões com maiores preços médios:")
    print("-"*80)
    region_prices = df.groupby('region').agg({
        'price': 'mean',
        'original_id': 'count'
    }).round(2)\
    .sort_values('price', ascending=False)\
    .head(5)
    print(region_prices.to_string(formatters={
        'price': '${:,.2f}'.format,
        'original_id': '{:,}'.format
    }))
    
    # 5. Proporção de transmissão manual vs automática
    print("\n5. Proporção de transmissão manual vs automática:")
    print("-"*80)
    transmission_counts = df['transmission'].value_counts()
    transmission_pct = df['transmission'].value_counts(normalize=True) * 100
    trans_stats = pd.DataFrame({
        'count': transmission_counts,
        'percentage': transmission_pct
    }).round(2)
    print(trans_stats.to_string(formatters={
        'count': '{:,}'.format,
        'percentage': '{:.1f}%'.format
    }))

def descriptive_statistics(df):
    """Realiza análises estatísticas descritivas."""
    print("\nParte 2: Estatística Descritiva")
    print("="*100)
    
    # 1. Distribuição dos preços
    print("\n1. Distribuição dos preços dos veículos:")
    print("-"*80)
    price_stats = df['price'].describe().round(2)
    stats_df = pd.DataFrame(price_stats).T
    print(stats_df.to_string(formatters={
        'count': '{:,.0f}'.format,
        'mean': '${:,.2f}'.format,
        'std': '${:,.2f}'.format,
        'min': '${:,.2f}'.format,
        '25%': '${:,.2f}'.format,
        '50%': '${:,.2f}'.format,
        '75%': '${:,.2f}'.format,
        'max': '${:,.2f}'.format
    }))
    
    # 2. Relação ano vs preço médio
    print("\n2. Relação entre ano de fabricação e preço médio:")
    print("-"*80)
    year_price = df.groupby('year')['price'].agg(['mean', 'count'])\
        .round(2)\
        .sort_index(ascending=False)\
        .head(10)
    print(year_price.to_string(formatters={
        'mean': '${:,.2f}'.format,
        'count': '{:,}'.format
    }))
    
    # 3. Quilometragem média por combustível e fabricante
    print("\n3. Quilometragem média por tipo de combustível e fabricante (top 5 fabricantes):")
    print("-"*80)
    mileage_stats = df.pivot_table(
        values='odometer',
        index='manufacturer',
        columns='fuel',
        aggfunc='mean'
    ).round(2)\
    .sort_values('gas', ascending=False)\
    .head()
    print(mileage_stats.to_string(formatters={col: '{:,.1f}'.format for col in mileage_stats.columns}))
    
    # 4. Correlação entre quilometragem e preço
    print("\n4. Correlação entre quilometragem e preço:")
    print("-"*80)
    correlation = df['price'].corr(df['odometer'])
    print(f"Coeficiente de correlação: {correlation:.3f}")
    
    # 5. Outliers nos preços
    print("\n5. Análise de outliers nos preços:")
    print("-"*80)
    Q1 = df['price'].quantile(0.25)
    Q3 = df['price'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    outliers = df[
        (df['price'] < lower_bound) | 
        (df['price'] > upper_bound)
    ]
    print(f"Limite inferior: ${lower_bound:,.2f}")
    print(f"Limite superior: ${upper_bound:,.2f}")
    print(f"Número de outliers: {len(outliers):,} ({(len(outliers)/len(df)*100):.1f}% dos dados)")
    print("\nExemplos de outliers (top 5 mais altos):")
    print(outliers.nlargest(5, 'price')[['manufacturer', 'model', 'year', 'price']]\
        .to_string(formatters={'price': '${:,.2f}'.format}))

def main():
    """Função principal."""
    try:
        # Carrega os dados
        logger.info("Carregando dados...")
        df = load_data()
        
        # Realiza análises
        sql_analysis(df)
        descriptive_statistics(df)
        
    except Exception as e:
        logger.error(f"Erro durante a análise: {str(e)}")
        raise

if __name__ == "__main__":
    main() 