import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from typing import Dict, Tuple
import json

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CarStatsAnalyzer:
    """Classe para análise estatística do mercado de carros usados."""
    
    def __init__(self, data_path: str):
        self.df = pd.read_parquet(data_path)
        self.results_path = Path("reports/statistical_analysis")
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # Configurar estilo dos gráficos
        plt.style.use('seaborn')
        
    def price_distribution(self) -> Dict:
        """1. Distribuição dos preços dos veículos."""
        price_stats = self.df['price'].describe()
        
        # Calcular estatísticas adicionais
        stats = {
            'mean': float(price_stats['mean']),
            'median': float(price_stats['50%']),
            'std': float(price_stats['std']),
            'skewness': float(self.df['price'].skew()),
            'kurtosis': float(self.df['price'].kurtosis())
        }
        
        # Gerar visualização
        plt.figure(figsize=(12, 6))
        
        # Histograma com KDE
        sns.histplot(self.df['price'].dropna(), kde=True)
        plt.title('Distribuição dos Preços')
        plt.xlabel('Preço')
        plt.ylabel('Frequência')
        
        # Salvar gráfico
        plt.savefig(self.results_path / 'price_distribution.png')
        plt.close()
        
        return stats
    
    def price_by_year(self) -> pd.DataFrame:
        """2. Relação entre ano de fabricação e preço médio."""
        yearly_stats = self.df.groupby('year').agg({
            'price': ['count', 'mean', 'std', 'median']
        }).round(2)
        
        yearly_stats.columns = ['count', 'mean_price', 'std_price', 'median_price']
        yearly_stats = yearly_stats.reset_index()
        
        # Gerar visualização
        plt.figure(figsize=(15, 6))
        
        # Linha para preço médio
        sns.lineplot(data=self.df, x='year', y='price', ci='sd')
        plt.title('Preço Médio por Ano de Fabricação')
        plt.xlabel('Ano')
        plt.ylabel('Preço')
        
        # Salvar gráfico
        plt.savefig(self.results_path / 'price_by_year.png')
        plt.close()
        
        return yearly_stats
    
    def mileage_analysis(self) -> pd.DataFrame:
        """3. Quilometragem média por tipo de combustível e fabricante."""
        mileage_stats = self.df.groupby(['fuel', 'manufacturer']).agg({
            'odometer': ['count', 'mean', 'std', 'median']
        }).round(2)
        
        mileage_stats.columns = ['count', 'mean_mileage', 'std_mileage', 'median_mileage']
        mileage_stats = mileage_stats.reset_index()
        
        # Gerar visualização
        plt.figure(figsize=(15, 6))
        
        # Boxplot
        sns.boxplot(data=self.df, x='fuel', y='odometer')
        plt.title('Distribuição de Quilometragem por Tipo de Combustível')
        plt.xticks(rotation=45)
        
        # Salvar gráfico
        plt.savefig(self.results_path / 'mileage_by_fuel.png')
        plt.close()
        
        return mileage_stats
    
    def price_mileage_correlation(self) -> Dict:
        """4. Correlação entre quilometragem e preço."""
        # Calcular correlação
        correlation = self.df['price'].corr(self.df['odometer'])
        
        # Teste de significância
        r, p_value = stats.pearsonr(
            self.df['price'].dropna(),
            self.df['odometer'].dropna()
        )
        
        results = {
            'correlation': float(correlation),
            'p_value': float(p_value),
            'significant': bool(p_value < 0.05)
        }
        
        # Gerar visualização
        plt.figure(figsize=(10, 6))
        
        # Scatter plot com linha de regressão
        sns.regplot(data=self.df, x='odometer', y='price')
        plt.title('Correlação entre Preço e Quilometragem')
        plt.xlabel('Quilometragem')
        plt.ylabel('Preço')
        
        # Salvar gráfico
        plt.savefig(self.results_path / 'price_mileage_correlation.png')
        plt.close()
        
        return results
    
    def detect_price_outliers(self) -> Dict:
        """5. Identificar outliers nos preços usando IQR."""
        Q1 = self.df['price'].quantile(0.25)
        Q3 = self.df['price'].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = self.df[
            (self.df['price'] < lower_bound) |
            (self.df['price'] > upper_bound)
        ]
        
        results = {
            'Q1': float(Q1),
            'Q3': float(Q3),
            'IQR': float(IQR),
            'lower_bound': float(lower_bound),
            'upper_bound': float(upper_bound),
            'n_outliers': len(outliers),
            'outliers_percentage': float(len(outliers) / len(self.df) * 100)
        }
        
        # Gerar visualização
        plt.figure(figsize=(10, 6))
        
        # Boxplot
        sns.boxplot(y=self.df['price'])
        plt.title('Distribuição de Preços com Outliers')
        plt.ylabel('Preço')
        
        # Salvar gráfico
        plt.savefig(self.results_path / 'price_outliers.png')
        plt.close()
        
        return results
    
    def run_all_analyses(self) -> Dict:
        """Executa todas as análises estatísticas."""
        analyses = {
            'price_distribution': self.price_distribution(),
            'price_by_year': self.price_by_year().to_dict(orient='records'),
            'mileage_analysis': self.mileage_analysis().to_dict(orient='records'),
            'price_mileage_correlation': self.price_mileage_correlation(),
            'price_outliers': self.detect_price_outliers()
        }
        
        # Salvar resultados
        results_file = self.results_path / 'statistical_analysis.json'
        with open(results_file, 'w') as f:
            json.dump(analyses, f, indent=2)
        
        logger.info(f"Análises estatísticas salvas em {results_file}")
        
        return analyses

if __name__ == "__main__":
    # Executar análises
    analyzer = CarStatsAnalyzer("data/cleansed/used_cars.parquet")
    results = analyzer.run_all_analyses()
    
    # Log dos resultados
    for name, result in results.items():
        print(f"\n=== {name} ===")
        print(json.dumps(result, indent=2)) 