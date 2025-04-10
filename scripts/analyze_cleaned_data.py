import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_data():
    """
    Load the cleaned data from CSV.
    """
    logger.info("Loading data...")
    try:
        df = pd.read_csv('data/processed/used_cars_cleaned.csv')
        logger.info(f"Loaded {len(df)} records")
        return df
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        raise

def print_dataset_info(df):
    """
    Print basic information about the dataset.
    """
    print("\nInformações do Dataset:")
    print("=" * 50)
    print(f"Total de registros: {len(df):,}")
    print(f"Total de colunas: {len(df.columns)}")
    
    print("\nColunas disponíveis:")
    for col in df.columns:
        print(f"- {col}")
        
    print("\nEstatísticas Básicas:")
    print("=" * 50)
    print(df.describe())
    
    print("\nPrimeiras 5 linhas:")
    print("=" * 50)
    print(df.head())
    
    print("\nValores nulos por coluna:")
    print("=" * 50)
    print(df.isnull().sum())

def analyze_financing(df):
    """
    Analyze financing patterns in the data.
    """
    logger.info("Analyzing financing patterns...")
    
    # Calculate financing statistics
    total_cars = len(df)
    financed_cars = df['has_installments'].sum()
    financing_percentage = (financed_cars / total_cars) * 100
    
    print("\nAnálise de Financiamento:")
    print("=" * 50)
    print(f"Total de carros: {total_cars:,}")
    print(f"Carros financiados: {financed_cars:,}")
    print(f"Percentual financiado: {financing_percentage:.2f}%")
    
    if financed_cars > 0:
        financed_df = df[df['has_installments']]
        
        print("\nEstatísticas de Financiamento:")
        print("-" * 30)
        print("Pagamento Mensal:")
        print(f"  Média: ${financed_df['monthly_payment'].mean():,.2f}")
        print(f"  Mediana: ${financed_df['monthly_payment'].median():,.2f}")
        print(f"  Mínimo: ${financed_df['monthly_payment'].min():,.2f}")
        print(f"  Máximo: ${financed_df['monthly_payment'].max():,.2f}")
        
        print("\nEntrada:")
        print(f"  Média: ${financed_df['down_payment'].mean():,.2f}")
        print(f"  Mediana: ${financed_df['down_payment'].median():,.2f}")
        print(f"  Mínimo: ${financed_df['down_payment'].min():,.2f}")
        print(f"  Máximo: ${financed_df['down_payment'].max():,.2f}")
        
        print("\nNúmero de Parcelas:")
        print(f"  Média: {financed_df['installments'].mean():.1f}")
        print(f"  Mediana: {financed_df['installments'].median():.0f}")
        print(f"  Mínimo: {financed_df['installments'].min():.0f}")
        print(f"  Máximo: {financed_df['installments'].max():.0f}")

def analyze_by_manufacturer(df):
    """
    Analyze financing patterns by manufacturer.
    """
    logger.info("Analyzing patterns by manufacturer...")
    
    manufacturer_stats = df.groupby('manufacturer').agg({
        'id': 'count',
        'has_installments': 'sum',
        'monthly_payment': 'mean',
        'down_payment': 'mean',
        'installments': 'mean',
        'price': 'mean'
    }).reset_index()
    
    manufacturer_stats['financing_percentage'] = (manufacturer_stats['has_installments'] / manufacturer_stats['id']) * 100
    manufacturer_stats = manufacturer_stats.sort_values('id', ascending=False)
    
    print("\nAnálise por Fabricante (Top 10):")
    print("=" * 50)
    print(manufacturer_stats.head(10).to_string(index=False))

def analyze_by_price_range(df):
    """
    Analyze financing patterns by price range.
    """
    logger.info("Analyzing patterns by price range...")
    
    df['price_range'] = pd.cut(
        df['price'],
        bins=[0, 10000, 20000, 30000, 50000, float('inf')],
        labels=['<$10k', '$10k-$20k', '$20k-$30k', '$30k-$50k', '>$50k']
    )
    
    price_range_stats = df.groupby('price_range').agg({
        'id': 'count',
        'has_installments': 'sum',
        'monthly_payment': 'mean',
        'down_payment': 'mean',
        'installments': 'mean'
    }).reset_index()
    
    price_range_stats['financing_percentage'] = (price_range_stats['has_installments'] / price_range_stats['id']) * 100
    
    print("\nAnálise por Faixa de Preço:")
    print("=" * 50)
    print(price_range_stats.to_string(index=False))

def main():
    """
    Main analysis process.
    """
    try:
        # Load data
        df = load_data()
        
        # Print basic information
        print_dataset_info(df)
        
        # Analyze financing patterns
        analyze_financing(df)
        
        # Analyze by manufacturer
        analyze_by_manufacturer(df)
        
        # Analyze by price range
        analyze_by_price_range(df)
        
        logger.info("Analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise

if __name__ == "__main__":
    main() 