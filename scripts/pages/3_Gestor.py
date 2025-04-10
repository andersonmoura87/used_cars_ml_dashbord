import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Área do Gestor",
    page_icon="📊",
    layout="wide"
)

@st.cache_data
def load_data():
    """Carrega os dados do arquivo CSV"""
    try:
        df = pd.read_csv("data/processed/cars_abt.csv")
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None

def calculate_market_metrics(df):
    """Calcula métricas de mercado"""
    metrics = {}
    
    # Volume total
    metrics['total_cars'] = len(df)
    
    # Valor total do mercado
    metrics['total_market_value'] = df['price'].sum()
    
    # Preço médio
    metrics['avg_price'] = df['price'].mean()
    
    # Idade média da frota
    metrics['avg_age'] = 2024 - df['year'].mean()
    
    # Top 5 fabricantes por volume
    top_manufacturers = df['manufacturer'].value_counts().head()
    metrics['top_manufacturers'] = {
        'names': top_manufacturers.index.tolist(),
        'values': top_manufacturers.values.tolist()
    }
    
    # Top 5 modelos por volume
    top_models = df['model'].value_counts().head()
    metrics['top_models'] = {
        'names': top_models.index.tolist(),
        'values': top_models.values.tolist()
    }
    
    return metrics

def analyze_market_trends(df):
    """Analisa tendências de mercado"""
    trends = {}
    
    # Preço médio por ano
    price_by_year = df.groupby('year')['price'].agg(['mean', 'count']).reset_index()
    trends['price_by_year'] = price_by_year
    
    # Distribuição de combustível
    fuel_dist = df['fuel'].value_counts()
    trends['fuel_distribution'] = {
        'types': fuel_dist.index.tolist(),
        'values': fuel_dist.values.tolist()
    }
    
    # Distribuição de transmissão
    transmission_dist = df['transmission'].value_counts()
    trends['transmission_distribution'] = {
        'types': transmission_dist.index.tolist(),
        'values': transmission_dist.values.tolist()
    }
    
    return trends

def analyze_inventory_metrics(df):
    """Analisa métricas de inventário"""
    inventory = {}
    
    # Distribuição de preços por segmento
    df['price_segment'] = pd.qcut(df['price'], q=5, labels=['Muito Baixo', 'Baixo', 'Médio', 'Alto', 'Muito Alto'])
    inventory['price_segments'] = df.groupby('price_segment').agg({
        'price': ['count', 'mean'],
        'odometer': 'mean'
    }).round(2)
    
    # Idade do inventário (se disponível)
    if 'days_listed' in df.columns:
        inventory['age_metrics'] = {
            'mean_days': df['days_listed'].mean(),
            'median_days': df['days_listed'].median(),
            'old_inventory': (df['days_listed'] > 60).sum()
        }
    
    return inventory

def main():
    st.title("📊 Área do Gestor")
    st.subheader("Análise de Mercado e Desempenho")

    # Carregar dados
    df = load_data()
    if df is None:
        return

    # Sidebar com filtros
    st.sidebar.header("Filtros")
    
    # Filtro de período (simulado com ano do carro)
    year_range = st.sidebar.slider(
        "Período (Ano do Carro)",
        min_value=int(df['year'].min()),
        max_value=int(df['year'].max()),
        value=(int(df['year'].quantile(0.25)), int(df['year'].max()))
    )
    
    # Filtro de fabricantes
    manufacturers = sorted(df['manufacturer'].unique())
    selected_manufacturers = st.sidebar.multiselect(
        "Fabricantes",
        manufacturers,
        default=manufacturers[:5]
    )

    # Aplicar filtros
    filtered_df = df[
        (df['year'].between(year_range[0], year_range[1])) &
        (df['manufacturer'].isin(selected_manufacturers))
    ]

    # Calcular métricas
    metrics = calculate_market_metrics(filtered_df)
    trends = analyze_market_trends(filtered_df)
    inventory = analyze_inventory_metrics(filtered_df)

    # Layout principal
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Volume Total",
            f"{metrics['total_cars']:,}",
            f"{metrics['total_cars']/len(df)*100:.1f}% do mercado"
        )
    
    with col2:
        st.metric(
            "Valor Total do Mercado",
            f"${metrics['total_market_value']:,.2f}"
        )
    
    with col3:
        st.metric(
            "Preço Médio",
            f"${metrics['avg_price']:,.2f}"
        )
    
    with col4:
        st.metric(
            "Idade Média da Frota",
            f"{metrics['avg_age']:.1f} anos"
        )

    # Análise de Volume
    st.header("Análise de Volume")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top fabricantes
        fig_manufacturers = go.Figure(data=[
            go.Bar(
                x=metrics['top_manufacturers']['values'],
                y=metrics['top_manufacturers']['names'],
                orientation='h'
            )
        ])
        fig_manufacturers.update_layout(
            title="Top 5 Fabricantes por Volume",
            xaxis_title="Quantidade",
            yaxis_title="Fabricante"
        )
        st.plotly_chart(fig_manufacturers, use_container_width=True)

    with col2:
        # Top modelos
        fig_models = go.Figure(data=[
            go.Bar(
                x=metrics['top_models']['values'],
                y=metrics['top_models']['names'],
                orientation='h'
            )
        ])
        fig_models.update_layout(
            title="Top 5 Modelos por Volume",
            xaxis_title="Quantidade",
            yaxis_title="Modelo"
        )
        st.plotly_chart(fig_models, use_container_width=True)

    # Análise de Tendências
    st.header("Análise de Tendências")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Preço médio por ano
        fig_price_trend = px.line(
            trends['price_by_year'],
            x='year',
            y='mean',
            title='Evolução do Preço Médio por Ano',
            labels={
                'year': 'Ano',
                'mean': 'Preço Médio ($)'
            }
        )
        st.plotly_chart(fig_price_trend, use_container_width=True)

    with col2:
        # Volume por ano
        fig_volume_trend = px.bar(
            trends['price_by_year'],
            x='year',
            y='count',
            title='Volume de Carros por Ano',
            labels={
                'year': 'Ano',
                'count': 'Quantidade'
            }
        )
        st.plotly_chart(fig_volume_trend, use_container_width=True)

    # Análise de Segmentação
    st.header("Análise de Segmentação")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribuição de combustível
        fig_fuel = px.pie(
            values=trends['fuel_distribution']['values'],
            names=trends['fuel_distribution']['types'],
            title='Distribuição por Tipo de Combustível'
        )
        st.plotly_chart(fig_fuel, use_container_width=True)

    with col2:
        # Distribuição de transmissão
        fig_transmission = px.pie(
            values=trends['transmission_distribution']['values'],
            names=trends['transmission_distribution']['types'],
            title='Distribuição por Tipo de Transmissão'
        )
        st.plotly_chart(fig_transmission, use_container_width=True)

    # Análise de Inventário
    st.header("Análise de Inventário")
    
    # Mostrar segmentos de preço
    st.subheader("Segmentos de Preço")
    segments_df = inventory['price_segments'].round(2)
    segments_df.columns = ['Quantidade', 'Preço Médio', 'Quilometragem Média']
    st.dataframe(segments_df, use_container_width=True)

    # Se houver métricas de idade do inventário
    if 'age_metrics' in inventory:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Média de Dias em Estoque",
                f"{inventory['age_metrics']['mean_days']:.1f}"
            )
        
        with col2:
            st.metric(
                "Mediana de Dias em Estoque",
                f"{inventory['age_metrics']['median_days']:.1f}"
            )
        
        with col3:
            st.metric(
                "Inventário > 60 dias",
                inventory['age_metrics']['old_inventory']
            )

if __name__ == "__main__":
    main() 