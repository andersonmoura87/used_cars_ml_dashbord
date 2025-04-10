import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
sys.path.append('scripts')
from analysis.advanced_analytics import (
    train_price_prediction_model,
    perform_market_segmentation,
    analyze_time_series,
    analyze_regional_demand,
    create_demand_forecast,
    get_market_insights
)

st.set_page_config(
    page_title="Análise Avançada",
    page_icon="📈",
    layout="wide"
)

@st.cache_data
def load_data():
    """Carrega os dados do arquivo CSV"""
    try:
        df = pd.read_csv("data/processed/cars_abt.csv")
        # Adicionar coluna de data simulada para análise temporal
        dates = pd.date_range(
            start='2023-01-01',
            end='2024-01-01',
            periods=len(df)
        )
        df['date'] = dates
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None

def main():
    st.title("📈 Análise Avançada de Mercado")
    st.subheader("Insights e Previsões")

    # Carregar dados
    df = load_data()
    if df is None:
        return

    # Sidebar com opções de análise
    analysis_type = st.sidebar.selectbox(
        "Tipo de Análise",
        ["Previsão de Preços", "Segmentação de Mercado", "Análise Temporal", "Análise Regional"]
    )

    if analysis_type == "Previsão de Preços":
        st.header("🎯 Previsão de Preços")
        
        with st.spinner("Treinando modelo de previsão..."):
            model, encoders, scaler, feature_importance, metrics = train_price_prediction_model(df)
        
        # Mostrar métricas do modelo
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("MAE", f"${metrics['mae']:,.2f}")
        with col2:
            st.metric("RMSE", f"${metrics['rmse']:,.2f}")
        with col3:
            st.metric("R²", f"{metrics['r2']:.3f}")
        with col4:
            st.metric("MSE", f"${metrics['mse']:,.2f}")
        
        # Gráfico de importância das features
        st.subheader("Importância das Features")
        fig_importance = px.bar(
            x=list(feature_importance.values()),
            y=list(feature_importance.keys()),
            orientation='h',
            title="Importância das Features no Modelo"
        )
        st.plotly_chart(fig_importance, use_container_width=True)

    elif analysis_type == "Segmentação de Mercado":
        st.header("🎯 Segmentação de Mercado")
        
        # Número de clusters
        n_clusters = st.slider("Número de Segmentos", 3, 8, 5)
        
        with st.spinner("Realizando segmentação..."):
            df_segmented, cluster_stats, cluster_map = perform_market_segmentation(df, n_clusters)
        
        # Mostrar estatísticas dos clusters
        st.subheader("Características dos Segmentos")
        
        # Formatar estatísticas para exibição
        display_stats = cluster_stats.copy()
        display_stats.columns = [
            'Preço Médio', 'Quantidade',
            'Ano Médio', 'Quilometragem Média',
            'Fabricante Principal', 'Modelo Principal'
        ]
        display_stats.index = cluster_map.values()
        st.dataframe(display_stats, use_container_width=True)
        
        # Visualizações
        col1, col2 = st.columns(2)
        
        with col1:
            # Scatter plot dos clusters
            fig_clusters = px.scatter(
                df_segmented,
                x='year',
                y='price',
                color='segment',
                title='Segmentos por Ano e Preço',
                labels={
                    'year': 'Ano',
                    'price': 'Preço ($)',
                    'segment': 'Segmento'
                }
            )
            st.plotly_chart(fig_clusters, use_container_width=True)
        
        with col2:
            # Distribuição de preços por segmento
            fig_dist = px.box(
                df_segmented,
                x='segment',
                y='price',
                title='Distribuição de Preços por Segmento',
                labels={
                    'segment': 'Segmento',
                    'price': 'Preço ($)'
                }
            )
            st.plotly_chart(fig_dist, use_container_width=True)

    elif analysis_type == "Análise Temporal":
        st.header("📅 Análise Temporal")
        
        with st.spinner("Analisando séries temporais..."):
            forecast, seasonality, historical_data = analyze_time_series(df)
            
        if forecast is None or historical_data is None:
            st.error("Não foi possível realizar a análise temporal. Verifique os logs para mais detalhes.")
            return
        
        # Gráfico de previsão
        fig_forecast = go.Figure()
        
        # Dados históricos
        fig_forecast.add_trace(
            go.Scatter(
                x=historical_data['ds'],
                y=historical_data['y'],
                name='Dados Históricos',
                line=dict(color='blue')
            )
        )
        
        # Previsão
        fig_forecast.add_trace(
            go.Scatter(
                x=forecast['ds'][len(historical_data):],
                y=forecast['yhat'][len(historical_data):],
                name='Previsão',
                line=dict(color='red')
            )
        )
        
        # Intervalo de confiança
        fig_forecast.add_trace(
            go.Scatter(
                x=forecast['ds'].tolist() + forecast['ds'].tolist()[::-1],
                y=forecast['yhat_upper'].tolist() + forecast['yhat_lower'].tolist()[::-1],
                fill='toself',
                fillcolor='rgba(255,0,0,0.2)',
                line=dict(color='rgba(255,0,0,0)'),
                name='Intervalo de Confiança'
            )
        )
        
        fig_forecast.update_layout(
            title='Previsão de Preços para os Próximos 30 Dias',
            xaxis_title='Data',
            yaxis_title='Preço Médio ($)',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_forecast, use_container_width=True)
        
        # Métricas de qualidade
        if 'metrics' in seasonality:
            st.subheader("Métricas de Qualidade")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "MAE",
                    f"${seasonality['metrics']['mae']:,.2f}"
                )
            
            with col2:
                st.metric(
                    "MSE",
                    f"${seasonality['metrics']['mse']:,.2f}"
                )
            
            with col3:
                st.metric(
                    "RMSE",
                    f"${seasonality['metrics']['rmse']:,.2f}"
                )
            
            with col4:
                st.metric(
                    "MAPE",
                    f"{seasonality['metrics']['mape']:.2f}%"
                )
        
        # Componentes sazonais
        st.subheader("Análise de Sazonalidade")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Tendência
            fig_trend = go.Figure()
            fig_trend.add_trace(
                go.Scatter(
                    x=forecast['ds'],
                    y=forecast['trend'],
                    name='Tendência'
                )
            )
            fig_trend.update_layout(
                title='Tendência de Preços',
                xaxis_title='Data',
                yaxis_title='Preço ($)',
                hovermode='x unified'
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        
        with col2:
            # Sazonalidade semanal
            fig_weekly = go.Figure()
            fig_weekly.add_trace(
                go.Scatter(
                    x=forecast['ds'],
                    y=forecast['weekly'],
                    name='Padrão Semanal'
                )
            )
            fig_weekly.update_layout(
                title='Sazonalidade Semanal',
                xaxis_title='Data',
                yaxis_title='Efeito',
                hovermode='x unified'
            )
            st.plotly_chart(fig_weekly, use_container_width=True)

    else:  # Análise Regional
        st.header("🗺️ Análise Regional")
        
        with st.spinner("Analisando demanda regional..."):
            state_demand, city_demand, model_region_demand, regional_trends = analyze_regional_demand(df)
            
            if state_demand is None:
                st.error("Não foi possível realizar a análise regional")
                return
            
            # Preparar dados para o mapa
            state_data = state_demand.reset_index()
            
            # Criar mapa de calor por estado
            fig = px.choropleth(
                state_data,
                locations='state',
                locationmode="USA-states",
                color='total_anuncios',
                scope="usa",
                color_continuous_scale=px.colors.sequential.Viridis,
                title='Distribuição de Anúncios por Estado',
                labels={
                    'total_anuncios': 'Total de Anúncios',
                    'state': 'Estado',
                    'preco_medio': 'Preço Médio',
                    'preco_mediano': 'Preço Mediano'
                },
                hover_data={
                    'state': True,
                    'total_anuncios': ':,.0f',
                    'preco_medio': ':$,.2f',
                    'preco_mediano': ':$,.2f',
                    'desvio_padrao': ':$,.2f'
                }
            )
            
            # Ajustar layout do mapa
            fig.update_layout(
                geo=dict(
                    showlakes=True,
                    lakecolor='rgb(255, 255, 255)',
                    showland=True,
                    landcolor='rgb(240, 240, 240)',
                    showcoastlines=True,
                    coastlinecolor='rgb(200, 200, 200)',
                    showsubunits=True,
                    subunitcolor='rgb(200, 200, 200)'
                ),
                coloraxis_colorbar=dict(
                    title='Total de Anúncios',
                    tickformat=',d',
                    len=0.75,
                    thickness=20
                ),
                margin=dict(l=0, r=0, t=30, b=0),
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Mostrar estatísticas detalhadas
            st.subheader("Estatísticas por Estado")
            
            # Formatar colunas para exibição
            formatted_state_data = state_data.copy()
            formatted_state_data['preco_medio'] = formatted_state_data['preco_medio'].apply(lambda x: f"${x:,.2f}")
            formatted_state_data['preco_mediano'] = formatted_state_data['preco_mediano'].apply(lambda x: f"${x:,.2f}")
            formatted_state_data['desvio_padrao'] = formatted_state_data['desvio_padrao'].apply(lambda x: f"${x:,.2f}")
            formatted_state_data['total_anuncios'] = formatted_state_data['total_anuncios'].apply(lambda x: f"{x:,}")
            
            st.dataframe(
                formatted_state_data.rename(columns={
                    'state': 'Estado',
                    'total_anuncios': 'Total de Anúncios',
                    'preco_medio': 'Preço Médio',
                    'preco_mediano': 'Preço Mediano',
                    'desvio_padrao': 'Desvio Padrão'
                }),
                use_container_width=True
            )
            
            if model_region_demand is not None:
                st.subheader("Distribuição de Modelos por Estado")
                
                # Criar mapa de calor para modelos por estado
                fig_models = go.Figure(data=go.Heatmap(
                    z=model_region_demand.values,
                    x=model_region_demand.columns,
                    y=model_region_demand.index,
                    colorscale='Viridis',
                    colorbar=dict(
                        title='Preço Médio ($)',
                        tickformat='$,.0f',
                        thickness=20,
                        len=0.75
                    ),
                    hoverongaps=False
                ))
                
                fig_models.update_layout(
                    title='Preço Médio dos Modelos por Estado',
                    xaxis_title='Estado',
                    yaxis_title='Modelo',
                    xaxis_tickangle=-45,
                    height=800,
                    margin=dict(l=100, r=50, t=50, b=100)
                )
                
                st.plotly_chart(fig_models, use_container_width=True)
            
            if city_demand is not None:
                st.subheader("Top 20 Cidades")
                
                # Criar gráfico de barras para cidades
                fig_cities = px.bar(
                    city_demand.reset_index(),
                    x='city',
                    y='total_anuncios',
                    title='Volume de Anúncios por Cidade',
                    labels={
                        'city': 'Cidade',
                        'total_anuncios': 'Total de Anúncios',
                        'preco_medio': 'Preço Médio',
                        'preco_mediano': 'Preço Mediano'
                    },
                    color='preco_medio',
                    color_continuous_scale='Viridis',
                    hover_data={
                        'preco_medio': ':$,.2f',
                        'preco_mediano': ':$,.2f'
                    }
                )
                
                fig_cities.update_layout(
                    xaxis_tickangle=-45,
                    showlegend=True,
                    coloraxis_colorbar=dict(
                        title='Preço Médio ($)',
                        tickformat='$,.0f',
                        thickness=20,
                        len=0.75
                    ),
                    height=600,
                    margin=dict(l=50, r=50, t=50, b=100)
                )
                
                st.plotly_chart(fig_cities, use_container_width=True)
            
            if regional_trends is not None:
                st.subheader("Tendências Regionais")
                
                # Criar gráfico de linha para tendências de preço
                fig_trends = px.line(
                    regional_trends,
                    x='date',
                    y='preco_medio',
                    color='state',
                    title='Evolução do Preço Médio por Estado',
                    labels={
                        'date': 'Data',
                        'preco_medio': 'Preço Médio ($)',
                        'state': 'Estado'
                    }
                )
                
                fig_trends.update_layout(
                    xaxis_title='Data',
                    yaxis_title='Preço Médio ($)',
                    hovermode='x unified',
                    height=600,
                    margin=dict(l=50, r=50, t=50, b=50),
                    yaxis_tickformat='$,.0f'
                )
                
                st.plotly_chart(fig_trends, use_container_width=True)

if __name__ == "__main__":
    main() 