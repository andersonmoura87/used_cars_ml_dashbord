import pandas as pd
import numpy as np
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple, Any
import logging
from datetime import datetime, timedelta
from prophet import Prophet

logger = logging.getLogger(__name__)

class MarketAnalysis:
    """Classe para análise avançada de mercado."""
    
    def __init__(self, n_segments: int = 5):
        self.n_segments = n_segments
        self.scaler = StandardScaler()
        self.kmeans = KMeans(
            n_clusters=n_segments,
            random_state=42
        )
        
    def segment_market(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Dict[str, float]]]:
        """Segmenta o mercado usando clustering."""
        # Preparar features para segmentação
        features = ['price', 'year', 'odometer']
        X = df[features].copy()
        
        # Escalar features
        X_scaled = self.scaler.fit_transform(X)
        
        # Aplicar clustering
        df_segmented = df.copy()
        df_segmented['segment'] = self.kmeans.fit_predict(X_scaled)
        
        # Calcular estatísticas por segmento
        segments = {}
        for segment in range(self.n_segments):
            segment_data = df_segmented[df_segmented['segment'] == segment]
            segments[str(segment)] = {
                'size': len(segment_data),
                'avg_price': float(segment_data['price'].mean()),
                'avg_year': float(segment_data['year'].mean()),
                'avg_odometer': float(segment_data['odometer'].mean())
            }
        
        return df_segmented, segments
    
    def analyze_competition(self, df: pd.DataFrame, target_manufacturer: str) -> Dict[str, Any]:
        """Analisa competição para um fabricante específico."""
        # Filtrar dados do fabricante alvo
        target_data = df[df['manufacturer'] == target_manufacturer]
        
        if len(target_data) == 0:
            return {}
        
        # Calcular métricas do alvo
        target_metrics = {
            'market_share': len(target_data) / len(df),
            'avg_price': float(target_data['price'].mean()),
            'price_range': (
                float(target_data['price'].quantile(0.25)),
                float(target_data['price'].quantile(0.75))
            )
        }
        
        # Identificar competidores diretos
        price_range = target_metrics['price_range']
        competitors = df[
            (df['manufacturer'] != target_manufacturer) &
            (df['price'].between(price_range[0], price_range[1]))
        ]
        
        # Analisar competidores
        top_competitors = (
            competitors['manufacturer']
            .value_counts()
            .head(5)
            .to_dict()
        )
        
        competition_metrics = {
            'direct_competitors': len(competitors['manufacturer'].unique()),
            'top_competitors': top_competitors,
            'avg_competitor_price': float(competitors['price'].mean())
        }
        
        return {
            'target_metrics': target_metrics,
            'competition_metrics': competition_metrics
        }
    
    def forecast_market_trends(
        self,
        df: pd.DataFrame,
        forecast_days: int = 30
    ) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """Prevê tendências de mercado usando Prophet."""
        # Preparar dados para Prophet
        df_prophet = pd.DataFrame({
            'ds': pd.to_datetime(df['date']),
            'y': df['price']
        })
        
        # Treinar modelo
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False
        )
        model.fit(df_prophet)
        
        # Fazer previsões
        future = model.make_future_dataframe(periods=forecast_days)
        forecast = model.predict(future)
        
        # Calcular métricas
        current_price = float(forecast['yhat'].iloc[-forecast_days-1])
        forecasted_price = float(forecast['yhat'].iloc[-1])
        price_change = forecasted_price - current_price
        price_change_percent = (price_change / current_price) * 100
        
        trends = {
            'current_price': current_price,
            'forecasted_price': forecasted_price,
            'price_change': price_change,
            'price_change_percent': price_change_percent,
            'trend_direction': 'up' if price_change > 0 else 'down'
        }
        
        return forecast, trends
    
    def analyze_geographical_patterns(
        self,
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Analisa padrões geográficos nos preços."""
        # Calcular estatísticas por estado
        geo_stats = df.groupby('state').agg({
            'price': ['mean', 'std', 'count'],
            'year': 'mean',
            'odometer': 'mean'
        }).round(2)
        
        # Identificar clusters de estados por preço
        state_features = pd.DataFrame({
            'avg_price': geo_stats['price']['mean'],
            'price_std': geo_stats['price']['std'],
            'avg_year': geo_stats['year']['mean']
        })
        
        # Escalar features
        X_scaled = self.scaler.fit_transform(state_features)
        
        # Aplicar clustering
        n_clusters = min(3, len(state_features))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        state_features['cluster'] = kmeans.fit_predict(X_scaled)
        
        # Analisar padrões
        patterns = {
            'price_clusters': {},
            'high_price_states': [],
            'low_price_states': []
        }
        
        for cluster in range(n_clusters):
            cluster_states = state_features[state_features['cluster'] == cluster]
            patterns['price_clusters'][str(cluster)] = {
                'avg_price': float(cluster_states['avg_price'].mean()),
                'states': cluster_states.index.tolist()
            }
        
        # Identificar estados com preços extremos
        threshold = state_features['avg_price'].mean() + state_features['avg_price'].std()
        patterns['high_price_states'] = state_features[
            state_features['avg_price'] > threshold
        ].index.tolist()
        
        threshold = state_features['avg_price'].mean() - state_features['avg_price'].std()
        patterns['low_price_states'] = state_features[
            state_features['avg_price'] < threshold
        ].index.tolist()
        
        return geo_stats, patterns
    
    def _analyze_price_positioning(
        self, target_prices: pd.Series, competitor_prices: pd.Series
    ) -> Dict:
        """Analisa posicionamento de preço em relação à competição."""
        # Teste t para diferença de médias
        t_stat, p_value = stats.ttest_ind(target_prices, competitor_prices)
        
        # Calcular percentis
        target_median = target_prices.median()
        market_percentile = stats.percentileofscore(competitor_prices, target_median)
        
        return {
            'price_difference': target_prices.mean() - competitor_prices.mean(),
            'price_difference_pct': (
                (target_prices.mean() - competitor_prices.mean()) /
                competitor_prices.mean() * 100
            ),
            'statistical_difference': {
                't_statistic': t_stat,
                'p_value': p_value,
                'is_significant': p_value < self.significance_level
            },
            'market_percentile': market_percentile,
            'positioning': (
                'premium' if market_percentile > 75 else
                'competitive' if market_percentile > 25 else
                'economic'
            )
        }
    
    def _analyze_seasonality(
        self, model: Prophet, forecast: pd.DataFrame
    ) -> Dict:
        """Analisa padrões sazonais nas previsões."""
        # Extrair componentes sazonais
        seasonal_components = model.seasonalities
        
        # Analisar cada componente
        seasonality = {}
        for component in seasonal_components:
            if component == 'yearly':
                # Identificar meses de pico e vale
                yearly = forecast['yearly'].values
                peak_month = forecast.loc[yearly.argmax(), 'ds'].month
                trough_month = forecast.loc[yearly.argmin(), 'ds'].month
                seasonality['yearly'] = {
                    'peak_month': peak_month,
                    'trough_month': trough_month,
                    'amplitude': yearly.max() - yearly.min()
                }
            elif component == 'weekly':
                # Identificar dias da semana de pico e vale
                weekly = forecast['weekly'].values
                peak_day = forecast.loc[weekly.argmax(), 'ds'].dayofweek
                trough_day = forecast.loc[weekly.argmin(), 'ds'].dayofweek
                seasonality['weekly'] = {
                    'peak_day': peak_day,
                    'trough_day': trough_day,
                    'amplitude': weekly.max() - weekly.min()
                }
        
        return seasonality 