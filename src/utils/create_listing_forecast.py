import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pytz
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
import xgboost as xgb
from prophet import Prophet
import joblib

def create_listing_forecast():
    """
    Cria previsões de características dos anúncios futuros de carros.
    Prevê: preço, região, fabricante, modelo e tipo do veículo.
    """
    
    # Configurar conexão com o banco
    load_dotenv()
    engine = create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    )

    # Carregar dados base
    print("Carregando dados do banco...")
    df = pd.read_sql("""
        SELECT *
        FROM cars_cleaned
        WHERE price > 0 
        AND year >= 1990
        AND posting_date IS NOT NULL
        AND type IS NOT NULL
        ORDER BY posting_date DESC
    """, engine)

    # Converter posting_date para datetime com UTC
    print("Convertendo datas...")
    df['posting_date'] = pd.to_datetime(df['posting_date'], format='%Y-%m-%dT%H:%M:%S%z', utc=True)
    
    # Converter para timezone local (America/New_York para -0500)
    eastern = pytz.timezone('America/New_York')
    df['posting_date'] = df['posting_date'].dt.tz_convert(eastern)

    # Criar features temporais
    print("Criando features temporais...")
    df['year'] = df['posting_date'].dt.year
    df['month'] = df['posting_date'].dt.month
    df['day'] = df['posting_date'].dt.day
    df['dayofweek'] = df['posting_date'].dt.dayofweek
    df['quarter'] = df['posting_date'].dt.quarter
    df['is_weekend'] = df['dayofweek'].isin([5, 6]).astype(int)
    df['vehicle_age'] = df['year'].max() - df['year']

    # Preparar dados para previsão
    print("Preparando dados para previsão...")
    
    # 1. Previsão de Volume de Anúncios (usando Prophet)
    print("\n1. Prevendo volume de anúncios...")
    daily_counts = df.groupby(df['posting_date'].dt.date).size().reset_index()
    daily_counts.columns = ['ds', 'y']
    daily_counts['y'] = np.log1p(daily_counts['y'])  # Transformação log para evitar valores negativos
    daily_counts['ds'] = pd.to_datetime(daily_counts['ds'])
    
    # Treinar modelo Prophet para volume
    model_volume = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=True,
        growth='flat'  # Usar crescimento flat para evitar tendências extremas
    )
    model_volume.fit(daily_counts)
    
    # Criar dataframe para previsões futuras
    future_dates = pd.DataFrame({
        'ds': pd.date_range(
            start=datetime.now().date(),
            periods=61,  # 60 dias + hoje
            freq='D'
        )
    })
    forecast_volume = model_volume.predict(future_dates)
    forecast_volume['yhat'] = np.expm1(forecast_volume['yhat'])  # Reverter transformação log
    
    # 2. Previsão de Características dos Anúncios
    print("\n2. Preparando modelos para características...")
    
    # Preparar features para treino
    features = ['year', 'month', 'day', 'dayofweek', 'quarter', 'is_weekend', 'vehicle_age']
    
    # Codificar variáveis categóricas
    le_manufacturer = LabelEncoder()
    le_model = LabelEncoder()
    le_type = LabelEncoder()
    le_region = LabelEncoder()
    
    # Filtrar apenas os valores mais comuns para melhorar as previsões
    min_count = 100  # Mínimo de ocorrências para incluir na previsão
    
    common_manufacturers = df['manufacturer'].value_counts()[df['manufacturer'].value_counts() >= min_count].index
    common_models = df['model'].value_counts()[df['model'].value_counts() >= min_count].index
    common_types = df['type'].value_counts()[df['type'].value_counts() >= min_count].index
    common_regions = df['region'].value_counts()[df['region'].value_counts() >= min_count].index
    
    df_filtered = df[
        df['manufacturer'].isin(common_manufacturers) &
        df['model'].isin(common_models) &
        df['type'].isin(common_types) &
        df['region'].isin(common_regions)
    ].copy()
    
    df_filtered['manufacturer_encoded'] = le_manufacturer.fit_transform(df_filtered['manufacturer'])
    df_filtered['model_encoded'] = le_model.fit_transform(df_filtered['model'])
    df_filtered['type_encoded'] = le_type.fit_transform(df_filtered['type'])
    df_filtered['region_encoded'] = le_region.fit_transform(df_filtered['region'])
    
    # Treinar modelos para cada característica
    print("\n3. Treinando modelos...")
    
    # Modelo para preço
    model_price = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=6
    )
    model_price.fit(df_filtered[features], df_filtered['price'])
    
    # Modelos para características categóricas
    model_manufacturer = RandomForestClassifier(n_estimators=100, class_weight='balanced')
    model_model = RandomForestClassifier(n_estimators=100, class_weight='balanced')
    model_type = RandomForestClassifier(n_estimators=100, class_weight='balanced')
    model_region = RandomForestClassifier(n_estimators=100, class_weight='balanced')
    
    model_manufacturer.fit(df_filtered[features], df_filtered['manufacturer_encoded'])
    model_model.fit(df_filtered[features], df_filtered['model_encoded'])
    model_type.fit(df_filtered[features], df_filtered['type_encoded'])
    model_region.fit(df_filtered[features], df_filtered['region_encoded'])
    
    # Gerar previsões para diferentes horizontes de tempo
    horizons = [1, 7, 15, 30, 60]
    
    print("\n4. Gerando previsões...")
    all_predictions = []
    
    for days in horizons:
        print(f"\nPrevisões para {days} dias:")
        future_date = datetime.now().date() + timedelta(days=days)
        
        # Criar features para a data futura
        future_features = pd.DataFrame({
            'year': [future_date.year],
            'month': [future_date.month],
            'day': [future_date.day],
            'dayofweek': [future_date.weekday()],
            'quarter': [(future_date.month-1)//3 + 1],
            'is_weekend': [1 if future_date.weekday() in [5, 6] else 0],
            'vehicle_age': [0]  # Será ajustado com base na média dos dados
        })
        
        # Ajustar vehicle_age com a média dos dados
        future_features['vehicle_age'] = df_filtered['vehicle_age'].mean()
        
        # Fazer previsões
        pred_price = model_price.predict(future_features)
        pred_manufacturer = le_manufacturer.inverse_transform(model_manufacturer.predict(future_features))
        pred_model = le_model.inverse_transform(model_model.predict(future_features))
        pred_type = le_type.inverse_transform(model_type.predict(future_features))
        pred_region = le_region.inverse_transform(model_region.predict(future_features))
        
        # Volume previsto para o dia
        day_volume = max(1, int(forecast_volume[forecast_volume['ds'].dt.date == future_date]['yhat'].values[0]))
        
        predictions = {
            'horizon_days': days,
            'date': future_date,
            'expected_volume': day_volume,
            'predicted_price': int(pred_price[0]),
            'predicted_manufacturer': pred_manufacturer[0],
            'predicted_model': pred_model[0],
            'predicted_type': pred_type[0],
            'predicted_region': pred_region[0]
        }
        
        all_predictions.append(predictions)
    
    # Criar DataFrame com todas as previsões
    predictions_df = pd.DataFrame(all_predictions)
    
    # Salvar previsões
    print("\n5. Salvando previsões...")
    os.makedirs('data/predictions', exist_ok=True)
    predictions_df.to_csv('data/predictions/listing_forecast.csv', index=False)
    
    # Salvar modelos treinados
    print("\n6. Salvando modelos...")
    os.makedirs('models', exist_ok=True)
    joblib.dump(model_price, 'models/price_predictor.joblib')
    joblib.dump(model_manufacturer, 'models/manufacturer_predictor.joblib')
    joblib.dump(model_model, 'models/model_predictor.joblib')
    joblib.dump(model_type, 'models/type_predictor.joblib')
    joblib.dump(model_region, 'models/region_predictor.joblib')
    
    print("\nPrevisões finalizadas! Resultados:")
    print(predictions_df.to_string(index=False))

if __name__ == "__main__":
    create_listing_forecast() 