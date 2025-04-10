import pandas as pd
import numpy as np
from datetime import datetime
import logging
from pathlib import Path
import json

from src.utils.data_quality import RobustDataQuality
from src.utils.price_analysis import RobustPriceAnalysis
from src.models.price_model import AdvancedPriceModel
from src.utils.market_analysis import MarketAnalysis
from src.database.connection import get_db_connection

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_analysis_results(results: dict, analysis_name: str):
    """Salva resultados da análise em JSON."""
    output_dir = Path('reports')
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'{analysis_name}_{timestamp}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, default=str)
    
    logger.info(f'Resultados salvos em: {output_file}')

def run_data_quality_analysis(df: pd.DataFrame) -> dict:
    """Executa análise de qualidade dos dados."""
    logger.info('Iniciando análise de qualidade dos dados...')
    
    dq = RobustDataQuality()
    
    # Analisar distribuições
    distributions = dq.analyze_distributions(df)
    
    # Detectar outliers multivariados
    outliers = dq.detect_multivariate_outliers(df)
    
    # Imputar valores faltantes
    df_clean, imputation_stats = dq.impute_missing_values(df)
    
    results = {
        'distributions': distributions,
        'outliers_count': outliers.sum(),
        'outliers_percentage': (outliers.sum() / len(df)) * 100,
        'imputation_statistics': imputation_stats
    }
    
    save_analysis_results(results, 'data_quality')
    return df_clean

def run_price_analysis(df: pd.DataFrame) -> dict:
    """Executa análise robusta de preços."""
    logger.info('Iniciando análise de preços...')
    
    pa = RobustPriceAnalysis()
    
    # Analisar distribuição de preços por fabricante e modelo
    price_dist = pa.analyze_price_distribution(df, ['manufacturer', 'model'])
    
    # Estimar preços justos
    features = ['year', 'odometer', 'manufacturer', 'model', 'fuel', 'transmission']
    fair_prices, price_metrics = pa.estimate_fair_price(df, features)
    
    # Detectar anomalias nos preços
    price_anomalies = pa.detect_price_anomalies(df, features)
    
    results = {
        'price_distribution': price_dist,
        'price_metrics': price_metrics,
        'anomalies_count': price_anomalies.sum(),
        'anomalies_percentage': (price_anomalies.sum() / len(df)) * 100
    }
    
    save_analysis_results(results, 'price_analysis')
    return fair_prices

def run_market_analysis(df: pd.DataFrame) -> dict:
    """Executa análise de mercado."""
    logger.info('Iniciando análise de mercado...')
    
    ma = MarketAnalysis()
    
    # Segmentar mercado
    df_segmented, segments = ma.segment_market(df)
    
    # Analisar competição para principais fabricantes
    top_manufacturers = df['manufacturer'].value_counts().head(5).index
    competition_analysis = {}
    for manufacturer in top_manufacturers:
        competition_analysis[manufacturer] = ma.analyze_competition(df, manufacturer)
    
    # Prever tendências de mercado
    forecast, trends = ma.forecast_market_trends(df)
    
    # Analisar padrões geográficos
    geo_stats, geo_patterns = ma.analyze_geographical_patterns(df)
    
    results = {
        'market_segments': segments,
        'competition_analysis': competition_analysis,
        'market_trends': trends,
        'geographical_patterns': geo_patterns
    }
    
    save_analysis_results(results, 'market_analysis')
    return results

def train_price_model(df: pd.DataFrame) -> dict:
    """Treina e avalia modelo de preços."""
    logger.info('Iniciando treinamento do modelo...')
    
    categorical_features = ['manufacturer', 'model', 'fuel', 'transmission', 'state']
    numerical_features = ['year', 'odometer']
    
    model = AdvancedPriceModel(
        categorical_features=categorical_features,
        numerical_features=numerical_features
    )
    
    # Treinar modelo
    metrics = model.train(df)
    
    # Analisar importância das features
    feature_importance = model.get_feature_importance()
    shap_importance = model.get_feature_importance(method='shap')
    
    # Fazer previsões com intervalos de confiança
    predictions, uncertainty = model.predict(df)
    
    # Analisar resíduos
    residuals_analysis = model.analyze_residuals(df['price'], predictions)
    
    results = {
        'model_metrics': metrics,
        'feature_importance': feature_importance.to_dict(),
        'shap_importance': shap_importance.to_dict(),
        'residuals_analysis': residuals_analysis
    }
    
    save_analysis_results(results, 'model_analysis')
    return results

def main():
    """Função principal que executa todas as análises."""
    logger.info('Iniciando análise completa dos dados...')
    
    # Conectar ao banco de dados
    engine = get_db_connection()
    
    # Carregar dados
    query = """
    SELECT *
    FROM cars
    WHERE price > 0 AND year >= 1990
    """
    df = pd.read_sql(query, engine)
    
    # 1. Análise de qualidade dos dados
    df_clean = run_data_quality_analysis(df)
    
    # 2. Análise de preços
    fair_prices = run_price_analysis(df_clean)
    
    # 3. Análise de mercado
    market_results = run_market_analysis(df_clean)
    
    # 4. Modelagem de preços
    model_results = train_price_model(df_clean)
    
    logger.info('Análise completa finalizada!')

if __name__ == '__main__':
    main() 