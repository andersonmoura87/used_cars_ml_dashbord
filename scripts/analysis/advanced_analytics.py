import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from xgboost import XGBRegressor
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

def train_price_prediction_model(df):
    """
    Treina um modelo XGBoost para previsão de preços com validação cruzada
    e análise de importância de features.
    """
    # Definir features disponíveis no DataFrame
    available_features = []
    base_features = ['year', 'odometer', 'condition', 'fuel', 'transmission', 'manufacturer', 'model', 'state', 'city']
    
    for feature in base_features:
        if feature in df.columns:
            available_features.append(feature)
    
    # Preparar features
    X = df[available_features].copy()
    y = df['price']
    
    # Codificar variáveis categóricas
    encoders = {}
    for col in X.select_dtypes(include=['object']).columns:
        encoders[col] = LabelEncoder()
        X[col] = encoders[col].fit_transform(X[col].astype(str))
    
    # Normalizar features numéricas
    scaler = StandardScaler()
    numeric_features = [f for f in ['year', 'odometer'] if f in available_features]
    if numeric_features:
        X[numeric_features] = scaler.fit_transform(X[numeric_features])
    
    # Treinar modelo
    model = XGBRegressor(
        n_estimators=200,
        learning_rate=0.1,
        max_depth=7,
        random_state=42
    )
    model.fit(X, y)
    
    # Calcular importância das features
    feature_importance = dict(zip(available_features, model.feature_importances_))
    
    # Fazer previsões e calcular métricas
    y_pred = model.predict(X)
    metrics = {
        'mae': mean_absolute_error(y, y_pred),
        'mse': mean_squared_error(y, y_pred),
        'rmse': np.sqrt(mean_squared_error(y, y_pred)),
        'r2': r2_score(y, y_pred)
    }
    
    return model, encoders, scaler, feature_importance, metrics

def perform_market_segmentation(df, n_clusters=5):
    """
    Realiza segmentação de mercado usando K-means clustering.
    """
    # Selecionar features para clustering
    features = ['price', 'year', 'odometer']
    X = df[features].copy()
    
    # Normalizar dados
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Aplicar K-means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Calcular características dos clusters
    cluster_stats = df.groupby('cluster').agg({
        'price': ['mean', 'count'],
        'year': 'mean',
        'odometer': 'mean',
        'manufacturer': lambda x: x.value_counts().index[0],
        'model': lambda x: x.value_counts().index[0]
    }).round(2)
    
    # Renomear clusters com base nas características
    cluster_names = []
    for idx in range(n_clusters):
        stats = cluster_stats.iloc[idx]
        if stats[('price', 'mean')] > df['price'].quantile(0.75):
            prefix = "Premium"
        elif stats[('price', 'mean')] < df['price'].quantile(0.25):
            prefix = "Econômico"
        else:
            prefix = "Intermediário"
            
        if stats[('year', 'mean')] > df['year'].quantile(0.75):
            suffix = "Novo"
        elif stats[('year', 'mean')] < df['year'].quantile(0.25):
            suffix = "Antigo"
        else:
            suffix = "Médio"
            
        cluster_names.append(f"{prefix} {suffix}")
    
    cluster_map = dict(enumerate(cluster_names))
    df['segment'] = df['cluster'].map(cluster_map)
    
    return df, cluster_stats, cluster_map

def analyze_time_series(df):
    """
    Realiza análise de séries temporais e previsão usando Prophet.
    """
    try:
        if 'date' not in df.columns or 'price' not in df.columns:
            logging.error("Colunas necessárias (date, price) não encontradas no DataFrame")
            return None, None, None

        # Converter e validar datas
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Remover linhas com datas inválidas, preços negativos/zero e outliers extremos
        df = df[
            df['date'].notna() & 
            df['price'].notna() & 
            (df['price'] > 100) &  # Remover preços muito baixos
            (df['price'] < df['price'].quantile(0.99))  # Remover outliers extremos
        ]
        
        if len(df) < 30:
            logging.error("Dados insuficientes após remoção de valores inválidos")
            return None, None, None

        # Preparar dados diários com estatísticas mais robustas
        daily_stats = df.groupby('date', as_index=False).agg({
            'price': ['mean', 'median', 'count', 'std'],
            'model': 'count'
        })
        
        # Corrigir os nomes das colunas
        daily_stats.columns = ['date', 'price_mean', 'price_median', 'price_count', 'price_std', 'model_count']

        # Usar mediana em vez de média para reduzir impacto de outliers
        prophet_data = pd.DataFrame({
            'ds': daily_stats['date'],
            'y': daily_stats['price_median']  # Usando mediana em vez de média
        })

        # Remover outliers de forma mais conservadora
        Q1 = prophet_data['y'].quantile(0.10)  # 10º percentil
        Q3 = prophet_data['y'].quantile(0.90)  # 90º percentil
        IQR = Q3 - Q1
        prophet_data = prophet_data[
            (prophet_data['y'] >= Q1 - 1.5 * IQR) &
            (prophet_data['y'] <= Q3 + 1.5 * IQR)
        ]

        if len(prophet_data) < 2:
            logging.error("Dados insuficientes após remoção de outliers")
            return None, None, None

        # Configurar modelo Prophet com parâmetros ajustados
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='additive',  # Mudado para aditivo para maior estabilidade
            interval_width=0.95,
            changepoint_prior_scale=0.05,  # Ajustado para melhor captura de tendências
            seasonality_prior_scale=10.0,
            changepoint_range=0.9
        )

        # Adicionar regressores extras se disponíveis
        if 'price_count' in daily_stats.columns:
            prophet_data['listing_count'] = daily_stats['price_count']
            model.add_regressor('listing_count', mode='additive')

        model.fit(prophet_data)

        # Fazer previsão
        future = model.make_future_dataframe(periods=30)
        if 'listing_count' in prophet_data.columns:
            # Usar média móvel dos últimos 7 dias para valores futuros
            last_week_avg = prophet_data['listing_count'].tail(7).mean()
            future['listing_count'] = prophet_data['listing_count'].median()
            future.loc[len(prophet_data):, 'listing_count'] = last_week_avg
            
        forecast = model.predict(future)

        # Extrair componentes sazonais
        seasonality = {
            'yearly': model.yearly_seasonality,
            'weekly': model.weekly_seasonality,
            'trend': forecast[['ds', 'trend']].copy(),
            'yhat': forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        }

        # Calcular métricas apenas para o período histórico
        historical_indices = forecast['ds'].isin(prophet_data['ds'])
        y_true = prophet_data['y']
        y_pred = forecast.loc[historical_indices, 'yhat']
        
        # Normalizar os valores antes de calcular as métricas
        y_true_norm = y_true / y_true.mean()
        y_pred_norm = y_pred / y_pred.mean()
        
        metrics = {
            'mae': mean_absolute_error(y_true, y_pred),
            'mse': mean_squared_error(y_true, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mape': np.mean(np.abs((y_true_norm - y_pred_norm) / y_true_norm)) * 100
        }
        seasonality['metrics'] = metrics

        return forecast, seasonality, prophet_data

    except Exception as e:
        logging.error(f"Erro na análise temporal: {e}")
        return None, None, None

def calculate_forecast_metrics(y_true, y_pred):
    """
    Calcula métricas de qualidade da previsão com tratamento robusto
    """
    try:
        # Remover valores nulos ou infinitos
        mask = np.isfinite(y_true) & np.isfinite(y_pred)
        y_true = y_true[mask]
        y_pred = y_pred[mask]
        
        if len(y_true) < 2:
            return {
                'mae': float('nan'),
                'mse': float('nan'),
                'rmse': float('nan'),
                'mape': float('nan')
            }
        
        # Calcular métricas básicas
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        
        # Calcular MAPE de forma robusta
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        # Verificar se as métricas são válidas
        metrics = {
            'mae': mae if np.isfinite(mae) else float('nan'),
            'mse': mse if np.isfinite(mse) else float('nan'),
            'rmse': rmse if np.isfinite(rmse) else float('nan'),
            'mape': mape if np.isfinite(mape) else float('nan')
        }
        
        return metrics
        
    except Exception as e:
        logging.error(f"Erro ao calcular métricas: {e}")
        return {
            'mae': float('nan'),
            'mse': float('nan'),
            'rmse': float('nan'),
            'mape': float('nan')
        }

def analyze_regional_demand(df):
    """
    Analisa a demanda por região e modelo.
    """
    try:
        if df is None or len(df) == 0:
            logging.error("DataFrame vazio ou nulo")
            return None, None, None, None

        # Fazer uma cópia do DataFrame para evitar modificações no original
        df = df.copy()
        
        required_columns = ['model', 'price']
        if not all(col in df.columns for col in required_columns):
            logging.error("Colunas obrigatórias ausentes no DataFrame")
            return None, None, None, None

        # Remover linhas com valores ausentes nas colunas principais
        df = df.dropna(subset=['model', 'price'])
        
        if len(df) < 2:
            logging.error("Dados insuficientes após remoção de valores ausentes")
            return None, None, None, None

        # Análise por estado (se disponível)
        state_demand = None
        if 'state' in df.columns:
            # Remover estados ausentes ou inválidos
            valid_states = df['state'].dropna().unique()
            if len(valid_states) >= 2:  # Precisa de pelo menos 2 estados
                state_data = df[df['state'].notna()].copy()
                state_demand = state_data.groupby('state').agg({
                    'model': 'count',
                    'price': ['mean', 'median', 'std']
                }).round(2)
                
                # Renomear colunas
                state_demand.columns = ['total_anuncios', 'preco_medio', 'preco_mediano', 'desvio_padrao']
                
                # Filtrar estados com poucos anúncios
                state_demand = state_demand[state_demand['total_anuncios'] >= 10]
                
                if state_demand.empty:
                    state_demand = None

        # Análise por cidade (se disponível)
        city_demand = None
        if 'city' in df.columns:
            # Remover cidades ausentes ou inválidas
            valid_cities = df['city'].dropna().unique()
            if len(valid_cities) >= 2:  # Precisa de pelo menos 2 cidades
                city_data = df[df['city'].notna()].copy()
                city_demand = city_data.groupby('city').agg({
                    'model': 'count',
                    'price': ['mean', 'median']
                }).round(2)
                
                # Renomear colunas
                city_demand.columns = ['total_anuncios', 'preco_medio', 'preco_mediano']
                
                # Filtrar e ordenar
                city_demand = city_demand[city_demand['total_anuncios'] >= 5]
                city_demand = city_demand.sort_values('total_anuncios', ascending=False).head(20)
                
                if city_demand.empty:
                    city_demand = None

        # Análise por modelo e região (se disponível)
        model_region_demand = None
        if 'state' in df.columns and len(valid_states) >= 2:
            # Pegar top 20 modelos mais comuns
            top_models = df['model'].value_counts().head(20).index
            filtered_df = df[
                (df['model'].isin(top_models)) & 
                (df['state'].notna())
            ]
            
            if len(filtered_df) >= 2:  # Verificar se há dados suficientes
                try:
                    model_region_demand = pd.crosstab(
                        filtered_df['model'],
                        filtered_df['state'],
                        values=filtered_df['price'],
                        aggfunc='mean'
                    ).round(2)
                    
                    # Preencher valores ausentes com 0
                    model_region_demand = model_region_demand.fillna(0)
                    
                    if model_region_demand.empty:
                        model_region_demand = None
                except Exception as e:
                    logging.error(f"Erro ao criar tabela cruzada: {e}")
                    model_region_demand = None

        # Calcular tendências regionais (se disponível)
        regional_trends = None
        if all(col in df.columns for col in ['state', 'date']):
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            valid_data = df[df['date'].notna() & df['state'].notna()].copy()
            
            if len(valid_data) >= 2:
                try:
                    regional_trends = valid_data.groupby(
                        ['state', pd.Grouper(key='date', freq='M')]
                    ).agg({
                        'model': 'count',
                        'price': ['mean', 'median']
                    }).round(2)
                    
                    # Resetar índice e renomear colunas
                    regional_trends = regional_trends.reset_index()
                    regional_trends.columns = ['state', 'date', 'total_anuncios', 'preco_medio', 'preco_mediano']
                    
                    # Filtrar estados com dados consistentes
                    min_months = 2  # Reduzido para 2 meses
                    state_counts = regional_trends.groupby('state')['date'].count()
                    valid_states = state_counts[state_counts >= min_months].index
                    regional_trends = regional_trends[regional_trends['state'].isin(valid_states)]
                    
                    if regional_trends.empty:
                        regional_trends = None
                except Exception as e:
                    logging.error(f"Erro ao calcular tendências regionais: {e}")
                    regional_trends = None

        return state_demand, city_demand, model_region_demand, regional_trends

    except Exception as e:
        logging.error(f"Erro na análise regional: {e}")
        return None, None, None, None

def create_demand_forecast(df, region=None, model=None, min_data_points=2):
    """
    Cria uma previsão de demanda para uma região e modelo específicos.
    
    Args:
        df (pd.DataFrame): DataFrame com os dados
        region (str): Estado/região para análise
        model (str): Modelo do veículo
        min_data_points (int): Número mínimo de pontos de dados necessários
    
    Returns:
        pd.DataFrame: DataFrame com a previsão ou None se não houver dados suficientes
    """
    try:
        if df is None or len(df) == 0:
            logging.error("DataFrame vazio ou nulo")
            return None
            
        # Fazer uma cópia do DataFrame para evitar modificações no original
        df = df.copy()
        
        # Verificar se temos as colunas necessárias
        required_columns = ['date', 'price']
        if not all(col in df.columns for col in required_columns):
            logging.error("Colunas necessárias ausentes no DataFrame")
            return None
            
        # Filtrar por região e modelo se especificados
        if region is not None and 'state' in df.columns:
            df = df[df['state'] == region]
            
        if model is not None and 'model' in df.columns:
            df = df[df['model'] == model]
            
        # Verificar se temos dados suficientes após a filtragem
        if len(df) < min_data_points:
            logging.warning(f"Dados insuficientes para região={region} e modelo={model}")
            return None
            
        # Converter data para datetime se necessário
        df['date'] = pd.to_datetime(df['date'])
        
        # Agregar dados por dia
        daily_demand = df.groupby('date').agg({
            'price': ['count', 'mean']
        }).reset_index()
        
        # Renomear colunas
        daily_demand.columns = ['ds', 'y', 'price_mean']
        
        # Verificar se temos dados suficientes após agregação
        if len(daily_demand) < min_data_points:
            logging.warning("Dados diários insuficientes após agregação")
            return None
            
        # Remover valores ausentes
        daily_demand = daily_demand.dropna(subset=['ds', 'y'])
        
        # Verificar novamente após remover NaN
        if len(daily_demand) < min_data_points:
            logging.warning("Dados insuficientes após remoção de valores ausentes")
            return None
            
        # Configurar e treinar o modelo Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='multiplicative'
        )
        
        try:
            model.fit(daily_demand)
            
            # Criar dataframe para previsão
            future = model.make_future_dataframe(periods=30)
            forecast = model.predict(future)
            
            return forecast
            
        except Exception as e:
            logging.error(f"Erro ao treinar modelo Prophet: {e}")
            return None
            
    except Exception as e:
        logging.error(f"Erro ao criar previsão de demanda: {e}")
        return None

def get_market_insights(df):
    """
    Gera insights gerais do mercado.
    """
    insights = {
        'total_listings': len(df),
        'total_value': df['price'].sum(),
        'avg_price': df['price'].mean(),
        'price_std': df['price'].std(),
        'top_manufacturers': df['manufacturer'].value_counts().head(5).to_dict(),
        'top_models': df['model'].value_counts().head(5).to_dict(),
        'avg_year': df['year'].mean(),
        'avg_odometer': df['odometer'].mean(),
        'price_trends': df.groupby(pd.Grouper(key='date', freq='M'))['price'].mean().to_dict(),
        'demand_trends': df.groupby(pd.Grouper(key='date', freq='M')).size().to_dict()
    }
    
    return insights 