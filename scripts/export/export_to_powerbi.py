import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

def export_data_for_powerbi():
    """
    Exporta os dados processados em formato adequado para o Power BI
    """
    # Criar diretório de exportação se não existir
    export_dir = Path("data/export")
    export_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Carregar dados da ABT
        print("Carregando dados...")
        df = pd.read_csv("data/processed/cars_abt.csv")
        
        # Criar coluna de data
        print("Criando coluna de data...")
        df['posting_date'] = pd.to_datetime(datetime.now().replace(day=1, month=1).strftime('%Y-%m-%d')) # Data base
        df['posting_date'] = df.apply(lambda x: x['posting_date'].replace(year=int(x['year'])), axis=1)
        
        # Remover outliers
        def remove_outliers(df, column):
            Q1 = df[column].quantile(0.01)
            Q3 = df[column].quantile(0.99)
            IQR = Q3 - Q1
            return df[(df[column] >= Q1 - 1.5 * IQR) & (df[column] <= Q3 + 1.5 * IQR)]
        
        print("Removendo outliers...")
        # Aplicar remoção de outliers
        df = remove_outliers(df, 'price')
        df = remove_outliers(df, 'odometer')
        
        # Filtrar anos recentes
        df = df[df['year'] >= 2000]
        
        print("Calculando métricas agregadas...")
        # Calcular métricas agregadas
        df['total_listings'] = df.groupby('manufacturer')['manufacturer'].transform('count')
        df['avg_price_manufacturer'] = df.groupby('manufacturer')['price'].transform('mean')
        df['avg_price_state'] = df.groupby('state')['price'].transform('mean')
        df['avg_odometer_fuel'] = df.groupby('fuel')['odometer'].transform('mean')
        
        # Criar tabela de métricas por fabricante
        manufacturer_metrics = df.groupby('manufacturer').agg({
            'price': ['count', 'mean', 'median', 'std'],
            'year': 'mean',
            'odometer': 'mean'
        }).round(2)
        
        manufacturer_metrics.columns = [
            'total_listings', 'avg_price', 'median_price', 'price_std',
            'avg_year', 'avg_odometer'
        ]
        manufacturer_metrics = manufacturer_metrics.reset_index()
        
        # Criar tabela de métricas por estado
        state_metrics = df.groupby('state').agg({
            'price': ['count', 'mean', 'median'],
            'odometer': 'mean',
            'latitude': 'first',
            'longitude': 'first'
        }).round(2)
        
        state_metrics.columns = [
            'total_listings', 'avg_price', 'median_price', 'avg_odometer',
            'latitude', 'longitude'
        ]
        state_metrics = state_metrics.reset_index()
        
        print("Exportando dados...")
        # Exportar dados
        df.to_csv(export_dir / "cars_powerbi.csv", index=False)
        manufacturer_metrics.to_csv(export_dir / "manufacturer_metrics.csv", index=False)
        state_metrics.to_csv(export_dir / "state_metrics.csv", index=False)
        
        print(f"""
        Dados exportados com sucesso para o diretório data/export/
        
        Arquivos gerados:
        - cars_powerbi.csv: {len(df)} registros
        - manufacturer_metrics.csv: {len(manufacturer_metrics)} fabricantes
        - state_metrics.csv: {len(state_metrics)} estados
        
        Colunas disponíveis para análise no Power BI:
        
        Tabela principal (cars_powerbi.csv):
        - year: Ano do veículo
        - posting_date: Data de referência (primeiro dia do ano do veículo)
        - price: Preço
        - state: Estado
        - manufacturer: Fabricante
        - fuel: Tipo de combustível
        - odometer: Quilometragem
        - latitude/longitude: Coordenadas geográficas
        - total_listings: Total de anúncios por fabricante
        - avg_price_manufacturer: Preço médio por fabricante
        - avg_price_state: Preço médio por estado
        - avg_odometer_fuel: Quilometragem média por tipo de combustível
        
        Métricas por fabricante (manufacturer_metrics.csv):
        - total_listings: Total de anúncios
        - avg_price: Preço médio
        - median_price: Preço mediano
        - price_std: Desvio padrão do preço
        - avg_year: Ano médio
        - avg_odometer: Quilometragem média
        
        Métricas por estado (state_metrics.csv):
        - total_listings: Total de anúncios
        - avg_price: Preço médio
        - median_price: Preço mediano
        - avg_odometer: Quilometragem média
        - latitude/longitude: Coordenadas geográficas
        """)
        
    except Exception as e:
        print(f"Erro ao exportar dados: {e}")

if __name__ == "__main__":
    export_data_for_powerbi() 