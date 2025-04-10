import pandas as pd
import numpy as np
from scipy import stats
from sklearn.preprocessing import RobustScaler
from sklearn.linear_model import HuberRegressor
from sklearn.model_selection import cross_val_score
from typing import Dict, Tuple, List, Any
import logging

logger = logging.getLogger(__name__)

class RobustPriceAnalysis:
    """Classe para análise robusta de preços."""
    
    def __init__(self):
        self.scaler = RobustScaler()
        self.model = HuberRegressor(epsilon=1.35)
        
    def analyze_price_distribution(self, df: pd.DataFrame, group_cols: List[str]) -> Dict[str, Dict[str, float]]:
        """Analisa distribuição de preços por grupos."""
        results = {}
        
        # Análise geral
        results['overall'] = self._calculate_price_stats(df['price'])
        
        # Análise por grupos
        for col in group_cols:
            group_stats = {}
            for group in df[col].unique():
                group_data = df[df[col] == group]['price']
                if len(group_data) > 0:
                    group_stats[group] = self._calculate_price_stats(group_data)
            results[col] = group_stats
        
        return results
    
    def _calculate_price_stats(self, prices: pd.Series) -> Dict[str, float]:
        """Calcula estatísticas robustas para preços."""
        if len(prices) == 0:
            return {}
            
        # Estatísticas básicas
        median = prices.median()
        mad = stats.median_abs_deviation(prices)
        q1, q3 = prices.quantile([0.25, 0.75])
        iqr = q3 - q1
        
        # Intervalo de confiança bootstrap
        ci_low, ci_high = self._bootstrap_confidence_interval(prices)
        
        return {
            'count': len(prices),
            'median': float(median),
            'mad': float(mad),
            'iqr': float(iqr),
            'ci_low': float(ci_low),
            'ci_high': float(ci_high)
        }
    
    def _bootstrap_confidence_interval(self, data: pd.Series, n_bootstrap: int = 1000, confidence: float = 0.95) -> Tuple[float, float]:
        """Calcula intervalo de confiança usando bootstrap."""
        bootstrap_medians = []
        for _ in range(n_bootstrap):
            sample = np.random.choice(data, size=len(data), replace=True)
            bootstrap_medians.append(np.median(sample))
        
        alpha = (1 - confidence) / 2
        return np.percentile(bootstrap_medians, [alpha * 100, (1 - alpha) * 100])
    
    def estimate_fair_price(self, df: pd.DataFrame, features: List[str]) -> Tuple[pd.Series, Dict[str, float]]:
        """Estima preços justos usando regressão robusta."""
        # Preparar features
        X = pd.get_dummies(df[features], drop_first=True)
        y = df['price']
        
        # Escalar features numéricas
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            X[numeric_cols] = self.scaler.fit_transform(X[numeric_cols])
        
        # Treinar modelo
        self.model.fit(X, y)
        
        # Fazer previsões
        fair_prices = pd.Series(self.model.predict(X), index=df.index)
        
        # Calcular métricas
        r2 = self.model.score(X, y)
        residuals = y - fair_prices
        rmse = np.sqrt(np.mean(residuals ** 2))
        mae = np.mean(np.abs(residuals))
        
        metrics = {
            'r2': float(r2),
            'rmse': float(rmse),
            'mae': float(mae),
            'residuals_std': float(np.std(residuals))
        }
        
        return fair_prices, metrics
    
    def detect_price_anomalies(self, df: pd.DataFrame, features: List[str]) -> pd.Series:
        """Detecta anomalias nos preços usando múltiplos critérios."""
        # Estimar preços justos
        fair_prices, _ = self.estimate_fair_price(df, features)
        
        # Calcular resíduos
        residuals = df['price'] - fair_prices
        
        # Identificar anomalias usando múltiplos critérios
        mad = stats.median_abs_deviation(residuals)
        median = np.median(residuals)
        
        # Critério 1: Resíduos extremos (3 MADs do centro)
        residual_outliers = np.abs(residuals - median) > 3 * mad
        
        # Critério 2: Preços extremos
        price_mad = stats.median_abs_deviation(df['price'])
        price_median = df['price'].median()
        price_outliers = np.abs(df['price'] - price_median) > 3 * price_mad
        
        # Combinar critérios
        anomalies = residual_outliers | price_outliers
        
        return pd.Series(anomalies, index=df.index) 