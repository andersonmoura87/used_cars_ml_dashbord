import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz

def create_abt():
    """Creates an Analytical Base Table (ABT) from the database."""
    
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
    """, engine)

    # Criar ABT
    print("Criando ABT...")
    abt = df.copy()

    # Converter colunas numéricas
    print("Convertendo colunas numéricas...")
    numeric_columns = ['price', 'year', 'odometer', 'latitude', 'longitude', 'vehicle_age']
    for col in numeric_columns:
        if col in abt.columns:
            abt[col] = pd.to_numeric(abt[col], errors='coerce')

    # 1. Features Temporais
    print("Criando features temporais...")
    # Converter posting_date para datetime com UTC
    abt['posting_date'] = pd.to_datetime(abt['posting_date'], utc=True)
    
    # Converter para timezone local (America/New_York para -0500)
    eastern = pytz.timezone('America/New_York')
    abt['posting_date'] = abt['posting_date'].dt.tz_convert(eastern)
    
    # Criar features temporais
    abt['posting_year'] = abt['posting_date'].dt.year
    abt['posting_month'] = abt['posting_date'].dt.month
    abt['posting_day'] = abt['posting_date'].dt.day
    abt['posting_dayofweek'] = abt['posting_date'].dt.dayofweek
    abt['posting_quarter'] = abt['posting_date'].dt.quarter
    abt['vehicle_age'] = abt['posting_year'].max() - abt['year']
    abt['days_on_market'] = (abt['posting_date'].max() - abt['posting_date']).dt.days

    # 2. Features de Preço
    print("Criando features de preço...")
    abt['price_per_year'] = abt['price'] / abt['vehicle_age'].replace(0, 1)
    abt['price_per_mile'] = abt['price'] / abt['odometer'].replace(0, np.nan)
    
    # Preços médios por segmento
    abt['avg_price_by_manufacturer'] = abt.groupby('manufacturer')['price'].transform('mean')
    abt['avg_price_by_model'] = abt.groupby(['manufacturer', 'model'])['price'].transform('mean')
    abt['avg_price_by_type'] = abt.groupby('type')['price'].transform('mean')
    abt['avg_price_by_state'] = abt.groupby('state')['price'].transform('mean')
    
    # Posicionamento relativo de preço
    abt['price_position_manufacturer'] = (abt['price'] - abt['avg_price_by_manufacturer']) / abt['avg_price_by_manufacturer']
    abt['price_position_model'] = (abt['price'] - abt['avg_price_by_model']) / abt['avg_price_by_model']
    abt['price_position_type'] = (abt['price'] - abt['avg_price_by_type']) / abt['avg_price_by_type']

    # 3. Features de Quilometragem
    print("Criando features de quilometragem...")
    abt['miles_per_year'] = abt['odometer'] / abt['vehicle_age'].replace(0, 1)
    abt['avg_miles_by_manufacturer'] = abt.groupby('manufacturer')['odometer'].transform('mean')
    abt['avg_miles_by_model'] = abt.groupby(['manufacturer', 'model'])['odometer'].transform('mean')
    abt['miles_position'] = (abt['odometer'] - abt['avg_miles_by_model']) / abt['avg_miles_by_model']

    # 4. Features de Texto
    print("Criando features de texto...")
    abt['description_length'] = abt['description'].str.len()
    abt['has_description'] = abt['description'].notna().astype(int)
    abt['has_vin'] = abt['vin'].notna().astype(int)
    abt['description_mentions_new'] = abt['description'].str.contains('new', case=False, na=False).astype(int)
    abt['description_mentions_warranty'] = abt['description'].str.contains('warranty', case=False, na=False).astype(int)
    abt['description_mentions_clean'] = abt['description'].str.contains('clean', case=False, na=False).astype(int)

    # 5. Features de Condição
    print("Criando features de condição...")
    condition_map = {
        'new': 5,
        'like new': 4,
        'excellent': 3,
        'good': 2,
        'fair': 1,
        'salvage': 0
    }
    abt['condition_numeric'] = abt['condition'].map(condition_map)
    abt['condition_relative'] = abt.groupby(['manufacturer', 'model'])['condition_numeric'].transform(lambda x: (x - x.mean()) / x.std())

    # 6. Features de Demanda
    print("Criando features de demanda...")
    abt['listings_by_manufacturer'] = abt.groupby('manufacturer')['original_id'].transform('count')
    abt['listings_by_model'] = abt.groupby(['manufacturer', 'model'])['original_id'].transform('count')
    abt['listings_by_state'] = abt.groupby('state')['original_id'].transform('count')
    abt['listings_by_type'] = abt.groupby('type')['original_id'].transform('count')

    # 7. Features de Competitividade
    print("Criando features de competitividade...")
    abt['competitors_same_model'] = abt.groupby(['manufacturer', 'model'])['original_id'].transform('count')
    abt['competitors_same_type'] = abt.groupby('type')['original_id'].transform('count')
    abt['competitors_same_state'] = abt.groupby('state')['original_id'].transform('count')
    abt['market_share_manufacturer'] = abt['listings_by_manufacturer'] / len(abt)
    abt['market_share_model'] = abt['listings_by_model'] / len(abt)

    # 8. Features de Sazonalidade
    print("Criando features de sazonalidade...")
    abt['is_weekend'] = abt['posting_dayofweek'].isin([5, 6]).astype(int)
    abt['is_holiday'] = abt['posting_month'].isin([12, 1]).astype(int)  # Dezembro e Janeiro
    abt['is_summer'] = abt['posting_month'].isin([6, 7, 8]).astype(int)
    abt['is_winter'] = abt['posting_month'].isin([12, 1, 2]).astype(int)

    # 9. Features de Interação
    print("Criando features de interação...")
    abt['age_mileage_ratio'] = abt['vehicle_age'] / abt['odometer'].replace(0, np.nan)
    abt['price_mileage_ratio'] = abt['price'] / abt['odometer'].replace(0, np.nan)
    abt['price_age_ratio'] = abt['price'] / abt['vehicle_age'].replace(0, 1)
    abt['competition_density'] = abt['competitors_same_model'] / abt['competitors_same_state']

    # 10. Features de Agregação Temporal
    print("Criando features de agregação temporal...")
    # Ordenar por data para cálculos temporais
    abt = abt.sort_values('posting_date')
    
    # Calcular médias e desvios por semana e mês
    abt['posting_week'] = abt['posting_date'].dt.isocalendar().week
    abt['price_avg_by_week'] = abt.groupby(['manufacturer', 'model', 'posting_year', 'posting_week'])['price'].transform('mean')
    abt['price_std_by_week'] = abt.groupby(['manufacturer', 'model', 'posting_year', 'posting_week'])['price'].transform('std')
    
    abt['price_avg_by_month'] = abt.groupby(['manufacturer', 'model', 'posting_year', 'posting_month'])['price'].transform('mean')
    abt['price_std_by_month'] = abt.groupby(['manufacturer', 'model', 'posting_year', 'posting_month'])['price'].transform('std')

    # 11. Features de Segmentação
    print("Criando features de segmentação...")
    abt['is_luxury'] = abt['manufacturer'].isin(['bmw', 'mercedes-benz', 'audi', 'porsche', 'lexus']).astype(int)
    abt['is_economy'] = abt['manufacturer'].isin(['toyota', 'honda', 'hyundai', 'kia', 'nissan']).astype(int)
    abt['is_american'] = abt['manufacturer'].isin(['ford', 'chevrolet', 'dodge', 'jeep', 'chrysler']).astype(int)
    abt['is_electric'] = abt['fuel'].str.contains('electric', case=False, na=False).astype(int)
    abt['is_hybrid'] = abt['fuel'].str.contains('hybrid', case=False, na=False).astype(int)

    # 12. Features Geográficas
    print("Criando features geográficas...")
    # Calcular centróides por estado
    state_centroids = abt.groupby('state').agg({
        'latitude': 'mean',
        'longitude': 'mean'
    }).reset_index()
    
    # Função para calcular distância em km
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371  # raio da Terra em km
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    # Calcular distância até o centróide do estado
    abt = abt.merge(state_centroids, on='state', suffixes=('', '_centroid'))
    abt['distance_to_state_center'] = haversine_distance(
        abt['latitude'], abt['longitude'],
        abt['latitude_centroid'], abt['longitude_centroid']
    )
    
    # Remover colunas temporárias
    abt = abt.drop(['latitude_centroid', 'longitude_centroid'], axis=1)

    # 13. Features de Status do Título
    print("Criando features de status do título...")
    abt['is_clean_title'] = (abt['title_status'] == 'clean').astype(int)
    abt['is_salvage_title'] = (abt['title_status'] == 'salvage').astype(int)
    abt['is_rebuilt_title'] = (abt['title_status'] == 'rebuilt').astype(int)
    abt['is_lien_title'] = (abt['title_status'] == 'lien').astype(int)

    # Remover colunas originais que foram transformadas
    columns_to_drop = [
        'description', 'posting_date', 'url', 'region_url', 'image_url'
    ]
    abt = abt.drop(columns=columns_to_drop)

    # Salvar ABT no banco de dados
    print("Salvando ABT no banco de dados...")
    abt.to_sql('cars_abt', engine, if_exists='replace', index=False)
    
    # Salvar ABT em CSV para backup
    print("Salvando ABT em CSV...")
    os.makedirs('data/processed', exist_ok=True)
    abt.to_csv('data/processed/cars_abt.csv', index=False)

    print("ABT criada com sucesso!")
    print(f"Shape da ABT: {abt.shape}")
    print(f"Colunas da ABT: {len(abt.columns)}")
    print("\nExemplo das primeiras linhas:")
    print(abt.head())

if __name__ == "__main__":
    create_abt() 