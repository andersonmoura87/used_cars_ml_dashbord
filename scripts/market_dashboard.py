#!/usr/bin/env python
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import logging
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, LabelEncoder
from xgboost import XGBRegressor
import sys
import os

# Adicionar o diretório raiz ao PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from analysis.advanced_analytics import (
    analyze_time_series,
    analyze_regional_demand,
    calculate_forecast_metrics
)

# Configuração do logging
logging.basicConfig(
    filename='logs/dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Análise de Veículos",
    page_icon="🚗",
    layout="wide"
)

@st.cache_data
def load_data():
    """Carrega os dados do arquivo CSV"""
    try:
        df = pd.read_csv("data/processed/cars_abt.csv")
        logging.info("Dados carregados com sucesso")
        return df
    except Exception as e:
        logging.error(f"Erro ao carregar dados: {e}")
        st.error("Erro ao carregar dados. Verifique o arquivo de log para mais detalhes.")
        return None

@st.cache_resource
def train_price_model(df):
    """Treina o modelo de previsão de preços"""
    try:
        # Preparar features
        features = ['year', 'odometer', 'condition', 'fuel', 'transmission']
        X = df[features].copy()
        y = df['price']

        # Codificar variáveis categóricas
        le = LabelEncoder()
        for col in ['condition', 'fuel', 'transmission']:
            X[col] = le.fit_transform(X[col])

        # Normalizar features numéricas
        scaler = StandardScaler()
        X[['year', 'odometer']] = scaler.fit_transform(X[['year', 'odometer']])

        # Treinar modelo
        model = XGBRegressor(random_state=42)
        model.fit(X, y)

        logging.info("Modelo de preços treinado com sucesso")
        return model, scaler, le, features
    except Exception as e:
        logging.error(f"Erro ao treinar modelo: {e}")
        st.error("Erro ao treinar modelo. Verifique o arquivo de log para mais detalhes.")
        return None, None, None, None

def find_buying_opportunities(df, price_model, scaler, le, features, max_price, min_year, max_mileage):
    """Encontra oportunidades de compra baseadas em critérios"""
    try:
        if df is None or price_model is None or scaler is None or le is None:
            logging.error("Dados ou modelo não disponíveis")
            return pd.DataFrame()

        # Filtrar candidatos
        candidates = df[
            (df['price'] <= max_price) &
            (df['year'] >= min_year) &
            (df['odometer'] <= max_mileage)
        ].copy()

        if len(candidates) == 0:
            logging.info("Nenhum veículo encontrado com os critérios especificados")
            return pd.DataFrame()

        # Preparar features para previsão
        X = candidates[features].copy()
        
        # Verificar se todas as features necessárias estão presentes
        missing_features = [f for f in features if f not in X.columns]
        if missing_features:
            logging.error(f"Features ausentes: {missing_features}")
            return pd.DataFrame()

        # Transformar features categóricas
        cat_features = ['condition', 'fuel', 'transmission']
        for col in cat_features:
            if col in X.columns:
                X[col] = X[col].fillna('unknown')  # Tratar valores ausentes
                try:
                    X[col] = le.transform(X[col])
                except ValueError as e:
                    logging.error(f"Erro ao transformar {col}: {e}")
                    return pd.DataFrame()

        # Transformar features numéricas
        num_features = ['year', 'odometer']
        num_data = X[num_features].copy()
        try:
            X[num_features] = scaler.transform(num_data)
        except ValueError as e:
            logging.error(f"Erro ao normalizar features numéricas: {e}")
            return pd.DataFrame()

        # Fazer previsões
        try:
            candidates['predicted_price'] = price_model.predict(X)
            candidates['price_difference'] = candidates['predicted_price'] - candidates['price']
            candidates['price_difference_pct'] = (candidates['price_difference'] / candidates['price']) * 100

            # Filtrar apenas oportunidades reais (diferença positiva)
            opportunities = candidates[candidates['price_difference_pct'] > 0].copy()
            opportunities = opportunities.sort_values('price_difference_pct', ascending=False)

            # Adicionar formatação para valores monetários
            opportunities['price'] = opportunities['price'].apply(lambda x: f"${x:,.2f}")
            opportunities['predicted_price'] = opportunities['predicted_price'].apply(lambda x: f"${x:,.2f}")
            opportunities['price_difference'] = opportunities['price_difference'].apply(lambda x: f"${x:,.2f}")
            opportunities['price_difference_pct'] = opportunities['price_difference_pct'].apply(lambda x: f"{x:.1f}%")

            logging.info(f"Encontradas {len(opportunities)} oportunidades de compra")
            return opportunities[['manufacturer', 'model', 'year', 'odometer', 'condition', 'price', 'predicted_price', 'price_difference', 'price_difference_pct']]
        except Exception as e:
            logging.error(f"Erro ao calcular previsões: {e}")
            return pd.DataFrame()

    except Exception as e:
        logging.error(f"Erro ao encontrar oportunidades: {e}")
        return pd.DataFrame()

def display_regional_analysis():
    """
    Exibe a análise regional no dashboard.
    """
    st.header("🗺️ Análise Regional")
    
    # Carregar dados
    df = load_data()
    if df is None:
        st.error("Não foi possível carregar os dados para análise regional")
        return
        
    try:
        # Realizar análise regional
        state_demand, city_demand, model_region_demand, regional_trends = analyze_regional_demand(df)
        
        # Exibir análise por estado
        if state_demand is not None and not state_demand.empty:
            st.subheader("Demanda por Estado")
            
            # Preparar dados para o mapa
            state_map_data = state_demand.reset_index()
            
            # Criar mapa de calor por estado
            fig = px.choropleth(
                state_map_data,
                locations='state',
                color='total_anuncios',
                scope="usa",
                color_continuous_scale="Viridis",
                title="Distribuição de Anúncios por Estado"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Exibir tabela com estatísticas
            st.dataframe(
                state_demand.style.format({
                    'preco_medio': '${:,.2f}',
                    'preco_mediano': '${:,.2f}',
                    'desvio_padrao': '${:,.2f}',
                    'total_anuncios': '{:,}'
                }),
                use_container_width=True
            )
        else:
            st.warning("Dados por estado não disponíveis")
        
        # Exibir análise por cidade
        if city_demand is not None and not city_demand.empty:
            st.subheader("Top 20 Cidades por Volume de Anúncios")
            
            # Criar gráfico de barras para cidades
            fig = px.bar(
                city_demand.reset_index(),
                x='city',
                y='total_anuncios',
                title="Volume de Anúncios por Cidade",
                labels={
                    'city': 'Cidade',
                    'total_anuncios': 'Total de Anúncios'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Exibir tabela com estatísticas
            st.dataframe(
                city_demand.style.format({
                    'preco_medio': '${:,.2f}',
                    'preco_mediano': '${:,.2f}',
                    'total_anuncios': '{:,}'
                }),
                use_container_width=True
            )
        else:
            st.warning("Dados por cidade não disponíveis")
        
        # Exibir análise por modelo e região
        if model_region_demand is not None and not model_region_demand.empty:
            st.subheader("Distribuição de Modelos por Estado")
            
            # Criar mapa de calor
            fig = px.imshow(
                model_region_demand,
                title="Mapa de Calor: Preço Médio dos Modelos por Estado",
                labels={
                    'x': 'Estado',
                    'y': 'Modelo',
                    'color': 'Preço Médio ($)'
                },
                aspect='auto'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Exibir tabela com os dados
            st.dataframe(
                model_region_demand.style.format('${:,.2f}'),
                use_container_width=True
            )
        else:
            st.warning("Dados de distribuição de modelos por estado não disponíveis")
        
        # Exibir tendências regionais
        if regional_trends is not None and not regional_trends.empty:
            st.subheader("Tendências Regionais ao Longo do Tempo")
            
            # Criar gráfico de linha para tendências
            fig = px.line(
                regional_trends,
                x='date',
                y='total_anuncios',
                color='state',
                title="Evolução do Volume de Anúncios por Estado",
                labels={
                    'date': 'Data',
                    'total_anuncios': 'Total de Anúncios',
                    'state': 'Estado'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Criar gráfico de linha para preços médios
            fig = px.line(
                regional_trends,
                x='date',
                y='preco_medio',
                color='state',
                title="Evolução do Preço Médio por Estado",
                labels={
                    'date': 'Data',
                    'preco_medio': 'Preço Médio ($)',
                    'state': 'Estado'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Dados de tendências regionais não disponíveis")
            
    except Exception as e:
        logging.error(f"Erro ao exibir análise regional: {e}")
        st.error("Ocorreu um erro ao exibir a análise regional. Verifique os logs para mais detalhes.")

def display_time_series_analysis():
    """
    Exibe a análise de séries temporais no dashboard.
    """
    st.header("📈 Análise Temporal")
    
    # Carregar dados
    df = load_data()
    if df is None:
        st.error("Não foi possível carregar os dados para análise temporal")
        return
        
    try:
        # Realizar análise temporal
        forecast, seasonality = analyze_time_series(df)
        
        if forecast is None or seasonality is None:
            st.warning("Não foi possível realizar a análise temporal. Verifique os logs para mais detalhes.")
            return
            
        # Exibir previsões
        st.subheader("Previsão de Preços")
        
        # Criar gráfico de previsão
        fig = go.Figure()
        
        # Dados históricos
        fig.add_trace(go.Scatter(
            x=forecast['ds'],
            y=forecast['yhat'],
            mode='lines',
            name='Previsão',
            line=dict(color='blue')
        ))
        
        # Intervalo de confiança
        fig.add_trace(go.Scatter(
            x=forecast['ds'],
            y=forecast['yhat_upper'],
            mode='lines',
            name='Limite Superior',
            line=dict(width=0),
            showlegend=False
        ))
        
        fig.add_trace(go.Scatter(
            x=forecast['ds'],
            y=forecast['yhat_lower'],
            mode='lines',
            name='Limite Inferior',
            fill='tonexty',
            line=dict(width=0),
            showlegend=False
        ))
        
        fig.update_layout(
            title='Previsão de Preços para os Próximos 30 Dias',
            xaxis_title='Data',
            yaxis_title='Preço Médio ($)',
            hovermode='x'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Exibir componentes da série temporal
        st.subheader("Componentes da Série Temporal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Tendência
            fig_trend = px.line(
                seasonality['trend'],
                x='ds',
                y='trend',
                title='Tendência de Preços'
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with col2:
            # Métricas de qualidade
            st.subheader("Métricas de Qualidade")
            metrics = seasonality['metrics']
            
            metrics_df = pd.DataFrame({
                'Métrica': [
                    'Erro Médio Absoluto (MAE)',
                    'Erro Quadrático Médio (MSE)',
                    'Raiz do Erro Quadrático Médio (RMSE)',
                    'Erro Percentual Médio Absoluto (MAPE)'
                ],
                'Valor': [
                    f"${metrics['mae']:,.2f}",
                    f"${metrics['mse']:,.2f}",
                    f"${metrics['rmse']:,.2f}",
                    f"{metrics['mape']:.2f}%"
                ]
            })
            
            st.dataframe(metrics_df, use_container_width=True)
            
    except Exception as e:
        logging.error(f"Erro ao exibir análise temporal: {e}")
        st.error("Ocorreu um erro ao exibir a análise temporal. Verifique os logs para mais detalhes.")

def display_market_analysis(filtered_df):
    """
    Exibe a análise de mercado no dashboard.
    """
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Preço Médio", f"${filtered_df['price'].mean():,.2f}")
    with col2:
        st.metric("Ano Médio", f"{filtered_df['year'].mean():.0f}")
    with col3:
        st.metric("Quilometragem Média", f"{filtered_df['odometer'].mean():,.0f}")
    with col4:
        st.metric("Total de Veículos", f"{len(filtered_df):,}")

    # Gráficos
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

        # Preço médio por fabricante
        manufacturer_avg = filtered_df.groupby('manufacturer')['price'].mean().sort_values(ascending=True)
        fig_manufacturer = px.bar(
            manufacturer_avg,
            title='Preço Médio por Fabricante',
            labels={'value': 'Preço Médio ($)', 'manufacturer': 'Fabricante'}
        )
        st.plotly_chart(fig_manufacturer, use_container_width=True)

    with col2:
        # Preço vs. Ano
        fig_year = px.scatter(
            filtered_df,
            x='year',
            y='price',
            title='Preço vs. Ano',
            labels={'year': 'Ano', 'price': 'Preço ($)'}
        )
        st.plotly_chart(fig_year, use_container_width=True)

        # Preço vs. Quilometragem
        fig_mileage = px.scatter(
            filtered_df,
            x='odometer',
            y='price',
            title='Preço vs. Quilometragem',
            labels={'odometer': 'Quilometragem', 'price': 'Preço ($)'}
        )
        st.plotly_chart(fig_mileage, use_container_width=True)

def display_buying_recommendations(df, price_model, scaler, le, features):
    """
    Exibe as recomendações de compra no dashboard.
    """
    # Filtros para oportunidades
    col1, col2, col3 = st.columns(3)
    
    with col1:
        max_price = st.number_input(
            "Preço Máximo ($)",
            min_value=0,
            max_value=1000000,
            value=50000,
            step=1000
        )
    
    with col2:
        min_year = st.number_input(
            "Ano Mínimo",
            min_value=1900,
            max_value=2024,
            value=2010,
            step=1
        )
    
    with col3:
        max_mileage = st.number_input(
            "Quilometragem Máxima",
            min_value=0,
            max_value=500000,
            value=100000,
            step=1000
        )

    # Encontrar oportunidades
    opportunities = find_buying_opportunities(
        df, price_model, scaler, le, features,
        max_price, min_year, max_mileage
    )

    if len(opportunities) > 0:
        st.subheader("Top 10 Oportunidades de Compra")
        
        # Selecionar e formatar colunas
        display_cols = [
            'manufacturer', 'model', 'year', 'odometer', 'condition', 'price', 'predicted_price', 'price_difference', 'price_difference_pct'
        ]
        
        opportunities_display = opportunities[display_cols].head(10)
        opportunities_display.columns = [
            'Fabricante', 'Modelo', 'Ano', 'Quilometragem', 'Condição', 'Preço Atual', 'Preço Previsto', 'Diferença', 'Diferença %'
        ]
        
        st.dataframe(opportunities_display, use_container_width=True)
        
        # Adicionar visualização das oportunidades
        st.subheader("Visualização das Oportunidades")
        
        fig = px.scatter(
            opportunities.head(10),
            x='year',
            y='price',
            size='price_difference_pct',
            color='manufacturer',
            hover_data=['model', 'odometer', 'condition'],
            title='Top 10 Oportunidades de Compra'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma oportunidade encontrada com os critérios selecionados.")

def main():
    """Função principal do dashboard"""
    st.title("🚗 Dashboard de Análise de Veículos")

    # Carregar dados
    df = load_data()
    if df is None:
        return

    # Treinar modelo de preços
    price_model, scaler, le, features = train_price_model(df)
    if price_model is None:
        return

    # Sidebar com filtros
    st.sidebar.header("Filtros")
    
    # Filtro de fabricantes
    manufacturers = sorted(df['manufacturer'].unique())
    selected_manufacturers = st.sidebar.multiselect(
        "Fabricantes",
        manufacturers,
        default=manufacturers[:5]
    )

    # Filtro de combustível
    fuel_types = sorted(df['fuel'].unique())
    selected_fuel = st.sidebar.multiselect(
        "Tipo de Combustível",
        fuel_types,
        default=fuel_types
    )

    # Filtro de transmissão
    transmission_types = sorted(df['transmission'].unique())
    selected_transmission = st.sidebar.multiselect(
        "Transmissão",
        transmission_types,
        default=transmission_types
    )

    # Aplicar filtros
    filtered_df = df[
        (df['manufacturer'].isin(selected_manufacturers)) &
        (df['fuel'].isin(selected_fuel)) &
        (df['transmission'].isin(selected_transmission))
    ]

    # Tabs para diferentes análises
    tab1, tab2, tab3, tab4 = st.tabs([
        "Análise de Mercado",
        "Recomendações de Compra",
        "Análise Regional",
        "Análise Temporal"
    ])

    with tab1:
        st.header("📊 Análise de Mercado")
        display_market_analysis(filtered_df)

    with tab2:
        st.header("💰 Recomendações de Compra")
        display_buying_recommendations(df, price_model, scaler, le, features)

    with tab3:
        display_regional_analysis()

    with tab4:
        display_time_series_analysis()

if __name__ == "__main__":
    main() 