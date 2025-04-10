import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
import os
from pathlib import Path

st.set_page_config(
    page_title="Área do Comprador",
    page_icon="🚗",
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

def main():
    st.title("🚗 Área do Comprador")
    st.subheader("Encontre o carro ideal para você")

    # Carregar dados
    df = load_data()
    if df is None:
        return

    # Sidebar com filtros
    st.sidebar.header("Suas Preferências")

    # Filtros principais
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        # Filtro de fabricante
        manufacturers = sorted(df['manufacturer'].unique())
        selected_manufacturer = st.selectbox(
            "Fabricante",
            ["Todos"] + manufacturers
        )

        # Filtro de combustível
        fuel_types = sorted(df['fuel'].unique())
        selected_fuel = st.selectbox(
            "Combustível",
            ["Todos"] + fuel_types
        )

    with col2:
        # Filtro de transmissão
        transmission_types = sorted(df['transmission'].unique())
        selected_transmission = st.selectbox(
            "Transmissão",
            ["Todos"] + transmission_types
        )

        # Filtro de condição
        conditions = sorted(df['condition'].unique())
        selected_condition = st.selectbox(
            "Condição",
            ["Todos"] + conditions
        )

    # Filtros de faixa
    st.sidebar.subheader("Faixas de Valores")

    # Faixa de preço
    price_range = st.sidebar.slider(
        "Faixa de Preço ($)",
        min_value=int(df['price'].min()),
        max_value=int(df['price'].max()),
        value=(int(df['price'].min()), int(df['price'].quantile(0.75)))
    )

    # Faixa de ano
    year_range = st.sidebar.slider(
        "Faixa de Ano",
        min_value=int(df['year'].min()),
        max_value=int(df['year'].max()),
        value=(int(df['year'].quantile(0.25)), int(df['year'].max()))
    )

    # Faixa de quilometragem
    odometer_range = st.sidebar.slider(
        "Faixa de Quilometragem",
        min_value=int(df['odometer'].min()),
        max_value=int(df['odometer'].max()),
        value=(int(df['odometer'].min()), int(df['odometer'].quantile(0.75)))
    )

    # Aplicar filtros
    filtered_df = df.copy()

    if selected_manufacturer != "Todos":
        filtered_df = filtered_df[filtered_df['manufacturer'] == selected_manufacturer]
    if selected_fuel != "Todos":
        filtered_df = filtered_df[filtered_df['fuel'] == selected_fuel]
    if selected_transmission != "Todos":
        filtered_df = filtered_df[filtered_df['transmission'] == selected_transmission]
    if selected_condition != "Todos":
        filtered_df = filtered_df[filtered_df['condition'] == selected_condition]

    filtered_df = filtered_df[
        (filtered_df['price'].between(price_range[0], price_range[1])) &
        (filtered_df['year'].between(year_range[0], year_range[1])) &
        (filtered_df['odometer'].between(odometer_range[0], odometer_range[1]))
    ]

    # Mostrar resultados
    st.header("Carros Encontrados")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Carros", len(filtered_df))
    with col2:
        st.metric("Preço Médio", f"${filtered_df['price'].mean():,.2f}")
    with col3:
        st.metric("Ano Médio", f"{filtered_df['year'].mean():.0f}")
    with col4:
        st.metric("Quilometragem Média", f"{filtered_df['odometer'].mean():,.0f}")

    # Visualizações
    col1, col2 = st.columns(2)

    with col1:
        # Distribuição de preços
        fig_price = px.histogram(
            filtered_df,
            x='price',
            title='Distribuição de Preços',
            labels={'price': 'Preço ($)', 'count': 'Quantidade'}
        )
        st.plotly_chart(fig_price, use_container_width=True)

    with col2:
        # Preço vs. Ano
        fig_year = px.scatter(
            filtered_df,
            x='year',
            y='price',
            color='manufacturer',
            title='Preço vs. Ano',
            labels={'year': 'Ano', 'price': 'Preço ($)'}
        )
        st.plotly_chart(fig_year, use_container_width=True)

    # Tabela de resultados
    st.subheader("Lista de Carros")
    
    # Selecionar e formatar colunas para exibição
    display_cols = [
        'manufacturer', 'model', 'year', 'price',
        'odometer', 'condition', 'fuel', 'transmission'
    ]
    
    display_df = filtered_df[display_cols].copy()
    display_df.columns = [
        'Fabricante', 'Modelo', 'Ano', 'Preço',
        'Quilometragem', 'Condição', 'Combustível', 'Transmissão'
    ]
    
    # Formatar valores
    display_df['Preço'] = display_df['Preço'].map('${:,.2f}'.format)
    display_df['Quilometragem'] = display_df['Quilometragem'].map('{:,.0f}'.format)
    
    st.dataframe(
        display_df.sort_values('Preço'),
        use_container_width=True,
        height=400
    )

if __name__ == "__main__":
    main() 