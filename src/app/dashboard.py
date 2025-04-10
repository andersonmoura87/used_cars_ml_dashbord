import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
from datetime import datetime
import plotly.figure_factory as ff

# Configurar página
st.set_page_config(
    page_title="Análise de Mercado de Carros Usados",
    page_icon="🚗",
    layout="wide"
)

def load_latest_results(analysis_name: str) -> dict:
    """Carrega os resultados mais recentes de uma análise."""
    reports_dir = Path('reports')
    if not reports_dir.exists():
        st.error("Diretório de relatórios não encontrado!")
        return None
    
    # Encontrar arquivo mais recente
    files = list(reports_dir.glob(f'{analysis_name}_*.json'))
    if not files:
        st.error(f"Nenhum resultado encontrado para {analysis_name}!")
        return None
    
    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def plot_distribution(data: pd.Series, title: str) -> go.Figure:
    """Cria um gráfico de distribuição com histograma e boxplot."""
    fig = go.Figure()
    
    # Adicionar histograma
    fig.add_trace(go.Histogram(
        x=data,
        name='Distribuição',
        nbinsx=50,
        opacity=0.7
    ))
    
    # Adicionar boxplot
    fig.add_trace(go.Box(
        x=data,
        name='Boxplot',
        boxpoints='outliers'
    ))
    
    fig.update_layout(
        title=title,
        showlegend=True,
        height=400
    )
    
    return fig

def plot_feature_importance(importance_dict: dict, title: str) -> go.Figure:
    """Cria um gráfico de barras para importância das features."""
    df = pd.DataFrame({
        'feature': list(importance_dict.keys()),
        'importance': list(importance_dict.values())
    }).sort_values('importance', ascending=True)
    
    fig = go.Figure(go.Bar(
        x=df['importance'],
        y=df['feature'],
        orientation='h'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title='Importância',
        yaxis_title='Feature',
        height=400
    )
    
    return fig

def plot_market_segments(segments: dict) -> go.Figure:
    """Cria um gráfico de dispersão para segmentos de mercado."""
    data = []
    for segment_id, info in segments.items():
        data.append({
            'segment': f"Segmento {segment_id}",
            'tamanho': info['size'],
            'preço_médio': info['avg_price'],
            'ano_médio': info['avg_year']
        })
    
    df = pd.DataFrame(data)
    
    fig = px.scatter(
        df,
        x='ano_médio',
        y='preço_médio',
        size='tamanho',
        color='segment',
        title='Segmentos de Mercado'
    )
    
    return fig

def main():
    st.title("🚗 Dashboard - Análise de Mercado de Carros Usados")
    
    # Carregar resultados
    data_quality = load_latest_results('data_quality')
    price_analysis = load_latest_results('price_analysis')
    market_analysis = load_latest_results('market_analysis')
    model_analysis = load_latest_results('model_analysis')
    
    if not all([data_quality, price_analysis, market_analysis, model_analysis]):
        st.error("Alguns resultados não foram encontrados. Execute as análises primeiro!")
        return
    
    # Sidebar
    st.sidebar.title("Navegação")
    section = st.sidebar.radio(
        "Escolha uma seção:",
        ["Qualidade dos Dados", "Análise de Preços", "Análise de Mercado", "Modelo Preditivo"]
    )
    
    if section == "Qualidade dos Dados":
        st.header("📊 Qualidade dos Dados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Total de Outliers",
                f"{data_quality['outliers_count']:,}",
                f"{data_quality['outliers_percentage']:.1f}%"
            )
        
        with col2:
            st.metric(
                "Campos com Valores Faltantes",
                len(data_quality['imputation_statistics'])
            )
        
        st.subheader("Distribuições das Variáveis")
        for var, stats in data_quality['distributions'].items():
            st.write(f"**{var}**")
            metrics = {
                "Mediana": stats['median'],
                "MAD": stats['mad'],
                "IQR": stats['iqr'],
                "Assimetria": stats['skewness'],
                "Curtose": stats['kurtosis']
            }
            st.write(metrics)
    
    elif section == "Análise de Preços":
        st.header("💰 Análise de Preços")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Anomalias de Preço",
                f"{price_analysis['anomalies_count']:,}",
                f"{price_analysis['anomalies_percentage']:.1f}%"
            )
        
        with col2:
            st.metric(
                "R² do Modelo de Preços",
                f"{price_analysis['price_metrics']['r2']:.3f}"
            )
        
        st.subheader("Distribuição de Preços por Fabricante")
        manufacturers = list(price_analysis['price_distribution'].keys())
        selected_manufacturer = st.selectbox(
            "Escolha um fabricante:",
            manufacturers
        )
        
        if selected_manufacturer:
            stats = price_analysis['price_distribution'][selected_manufacturer]
            st.write(f"**Estatísticas para {selected_manufacturer}**")
            st.write({
                "Contagem": stats['count'],
                "Mediana": stats['median'],
                "IQR": stats['iqr'],
                "Intervalo de Confiança": f"({stats['ci_low']:.2f}, {stats['ci_high']:.2f})"
            })
    
    elif section == "Análise de Mercado":
        st.header("📈 Análise de Mercado")
        
        # Segmentos de mercado
        st.subheader("Segmentação de Mercado")
        fig = plot_market_segments(market_analysis['market_segments'])
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise de competição
        st.subheader("Análise de Competição")
        manufacturer = st.selectbox(
            "Escolha um fabricante:",
            list(market_analysis['competition_analysis'].keys())
        )
        
        if manufacturer:
            comp_data = market_analysis['competition_analysis'][manufacturer]
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Market Share",
                    f"{comp_data['target_metrics']['market_share']:.1%}"
                )
            
            with col2:
                st.metric(
                    "Competidores Diretos",
                    comp_data['competition_metrics']['direct_competitors']
                )
            
            st.write("**Top Competidores:**")
            st.write(comp_data['competition_metrics']['top_competitors'])
        
        # Tendências de mercado
        st.subheader("Tendências de Mercado")
        trends = market_analysis['market_trends']
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Preço Atual",
                f"${trends['current_price']:,.2f}",
                f"{trends['price_change_percent']:.1f}%"
            )
        
        with col2:
            st.metric(
                "Preço Previsto",
                f"${trends['forecasted_price']:,.2f}"
            )
    
    else:  # Modelo Preditivo
        st.header("🤖 Modelo Preditivo")
        
        # Métricas do modelo
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "RMSE",
                f"${model_analysis['model_metrics']['rmse']:,.2f}"
            )
        
        with col2:
            st.metric(
                "MAE",
                f"${model_analysis['model_metrics']['mae']:,.2f}"
            )
        
        with col3:
            st.metric(
                "R²",
                f"{model_analysis['model_metrics']['r2']:.3f}"
            )
        
        # Importância das features
        st.subheader("Importância das Features")
        fig = plot_feature_importance(
            model_analysis['feature_importance'],
            "Importância das Features (Gain)"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise de resíduos
        st.subheader("Análise de Resíduos")
        residuals = model_analysis['residuals_analysis']
        
        st.write("**Estatísticas dos Resíduos:**")
        st.write({
            "Média": residuals['residuals_mean'],
            "Desvio Padrão": residuals['residuals_std'],
            "Assimetria": residuals['residuals_skew'],
            "Curtose": residuals['residuals_kurtosis']
        })
        
        st.write("**Teste de Heterocedasticidade:**")
        hetero = residuals['heteroscedasticity_test']
        st.write({
            "Estatística de Teste": hetero[0],
            "P-valor": hetero[1]
        })

if __name__ == "__main__":
    main() 