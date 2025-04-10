import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import os
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from prophet import Prophet
import joblib
from pathlib import Path
from datetime import datetime, timedelta
import logging
import re
from sqlalchemy import text

from src.database.connection import create_db_engine
from src.database.models import Car, MarketStats

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar página
st.set_page_config(
    page_title="Análise de Carros Usados",
    page_icon="🚗",
    layout="wide"
)

# Carregar variáveis de ambiente
load_dotenv()

def clean_text_encoding(text):
    """Limpa e corrige problemas de encoding em textos."""
    if not isinstance(text, str):
        return text
    
    # Tenta decodificar se estiver em bytes
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = text.decode('latin-1')
            except UnicodeDecodeError:
                return text
    
    # Remove caracteres inválidos
    text = ''.join(char for char in text if ord(char) < 0x10000)
    
    return text

def extract_price_info(price_str, description):
    """Extrai informações de preço do texto, tratando casos de parcelas."""
    try:
        # Se o preço já é um número, retorna ele mesmo
        if isinstance(price_str, (int, float)):
            return float(price_str)
        
        # Procura por padrões de parcelas no texto
        monthly_pattern = r'(\$?\d+[.,]\d+|\d+)(?:\s*(?:x|×)\s*|\s+parcelas?\s+de\s+)(\d+[.,]\d+|\d+)'
        down_payment_pattern = r'entrada\s+(?:de\s+)?(\$?\d+[.,]\d+|\d+)'
        
        price = 0.0
        
        # Verifica se há informação de parcelas
        if description and isinstance(description, str):
            # Procura por parcelas
            monthly_match = re.search(monthly_pattern, description.lower())
            if monthly_match:
                num_payments = float(monthly_match.group(1).replace('$', '').replace(',', '.'))
                payment_value = float(monthly_match.group(2).replace(',', '.'))
                price = num_payments * payment_value
            
            # Procura por entrada
            down_payment_match = re.search(down_payment_pattern, description.lower())
            if down_payment_match:
                down_payment = float(down_payment_match.group(1).replace('$', '').replace(',', '.'))
                price += down_payment
        
        # Se não encontrou parcelas, tenta converter o preço direto
        if price == 0.0 and price_str:
            price = float(str(price_str).replace('$', '').replace(',', '').strip())
        
        return price
    except:
        return None

def clean_price_data(df):
    """Limpa e valida os preços dos carros."""
    try:
        # Criar cópia do DataFrame
        df_clean = df.copy()
        
        # Extrair preços considerando parcelas
        df_clean['price_cleaned'] = df_clean.apply(
            lambda row: extract_price_info(row['price'], row.get('description', '')), 
            axis=1
        )
        
        # Definir limites de preço por fabricante
        price_limits = {
            'toyota': (5000, 150000),
            'honda': (4000, 130000),
            'ford': (3000, 120000),
            'chevrolet': (3000, 110000),
            'bmw': (10000, 200000),
            'mercedes-benz': (12000, 250000),
            'audi': (10000, 180000),
            'volkswagen': (3000, 100000),
            'hyundai': (3000, 90000),
            'kia': (3000, 85000)
        }
        
        # Aplicar limites de preço por fabricante
        df_clean['price_valid'] = df_clean.apply(
            lambda row: (
                price_limits.get(row['manufacturer'].lower(), (2000, 300000))[0] <= row['price_cleaned'] <= 
                price_limits.get(row['manufacturer'].lower(), (2000, 300000))[1]
                if pd.notnull(row['price_cleaned']) else False
            ),
            axis=1
        )
        
        # Remover preços inválidos
        df_removed = df_clean[~df_clean['price_valid']].copy()
        df_clean = df_clean[df_clean['price_valid']].copy()
        
        # Usar o preço limpo
        df_clean['price_original'] = df_clean['price']
        df_clean['price'] = df_clean['price_cleaned']
        
        # Remover colunas temporárias
        df_clean = df_clean.drop(['price_cleaned', 'price_valid'], axis=1)
        
        # Log das remoções
        total_removed = len(df_removed)
        total_kept = len(df_clean)
        logger.info(f"Total de registros removidos por preço inválido: {total_removed}")
        logger.info(f"Total de registros mantidos: {total_kept}")
        
        return df_clean, df_removed
    except Exception as e:
        logger.error(f"Erro ao limpar preços: {str(e)}")
        return None, None

@st.cache_resource
def get_db_connection():
    """Cria conexão com o banco de dados."""
    try:
        engine = create_db_engine()
        logger.info("Conexão com o banco de dados estabelecida com sucesso")
        return engine
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        st.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return None

@st.cache_data
def load_data():
    """Carrega dados do banco de dados."""
    try:
        engine = get_db_connection()
        if engine is None:
            return None
        
        # Query principal
        query = """
        SELECT 
            c.manufacturer, c.model, c.year, c.price, c.odometer,
            c.fuel, c.condition, c.state, c.latitude, c.longitude,
            c.posting_date, c.vehicle_age, c.transmission, c.drive,
            c.type, c.paint_color,
            ms.avg_price as market_avg_price,
            ms.median_price as market_median_price,
            ms.total_listings as market_total_listings
        FROM cars c
        LEFT JOIN market_stats ms ON 
            c.manufacturer = ms.manufacturer AND
            c.model = ms.model AND
            c.year = ms.year
        WHERE c.price > 0 
        AND c.year >= 1990
        """
        
        # Carregar dados
        df = pd.read_sql(query, engine)
        
        logger.info(f"Dados carregados com sucesso: {len(df)} registros")
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        st.error(f"Erro ao carregar dados: {str(e)}")
        return None

@st.cache_data
def load_market_trends():
    """Carrega tendências de mercado."""
    try:
        engine = get_db_connection()
        if engine is None:
            return None
        
        query = """
        SELECT 
            manufacturer,
            model,
            year,
            avg_price,
            median_price,
            total_listings,
            avg_days_listed,
            calculated_at
        FROM market_stats
        WHERE calculated_at >= NOW() - INTERVAL '30 days'
        ORDER BY total_listings DESC
        """
        
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar tendências: {str(e)}")
        return None

@st.cache_data
def load_price_history(manufacturer=None, model=None, year=None):
    """Carrega histórico de preços."""
    try:
        engine = get_db_connection()
        if engine is None:
            return None
        
        query = """
        SELECT 
            c.manufacturer,
            c.model,
            c.year,
            ph.price,
            ph.recorded_at
        FROM price_history ph
        JOIN cars c ON ph.car_id = c.id
        WHERE 1=1
        """
        
        params = {}
        if manufacturer:
            query += " AND c.manufacturer = :manufacturer"
            params['manufacturer'] = manufacturer
        if model:
            query += " AND c.model = :model"
            params['model'] = model
        if year:
            query += " AND c.year = :year"
            params['year'] = year
            
        query += " ORDER BY ph.recorded_at"
        
        df = pd.read_sql(query, engine, params=params)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar histórico: {str(e)}")
        return None

@st.cache_resource
def train_xgboost_model(df):
    """Treina um modelo XGBoost para previsão de preços."""
    try:
        # Preparar features
        features = ['year', 'odometer', 'vehicle_age']
        categorical_features = ['manufacturer', 'model', 'fuel', 'transmission', 'state', 'condition']
        
        # Codificar variáveis categóricas
        encoders = {}
        X = df[features].copy()
        
        for col in categorical_features:
            if col in df.columns:
                le = LabelEncoder()
                X[col] = le.fit_transform(df[col].fillna('missing'))
                encoders[col] = le
        
        # Separar target
        y = df['price']
        
        # Dividir dados
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Treinar modelo
        model = xgb.XGBRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        
        # Calcular métricas
        y_pred = model.predict(X_test)
        metrics = {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred)
        }
        
        logger.info("Modelo XGBoost treinado com sucesso")
        return model, encoders, metrics
    except Exception as e:
        logger.error(f"Erro ao treinar modelo XGBoost: {str(e)}")
        st.error(f"Erro ao treinar modelo XGBoost: {str(e)}")
        return None, None, None

def create_forecast(df, manufacturer, forecast_period):
    """Cria forecast de vendas para um fabricante."""
    try:
        # Preparar dados para forecast
        forecast_data = df[df['manufacturer'] == manufacturer].copy()
        forecast_data['posting_date'] = pd.to_datetime(forecast_data['posting_date'])
        
        # Agregar vendas por dia
        daily_sales = forecast_data.groupby('posting_date').size().reset_index()
        daily_sales.columns = ['ds', 'y']
        
        if len(daily_sales) > 30:  # Mínimo de dados para forecast
            # Treinar modelo Prophet
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=True
            )
            model.fit(daily_sales)
            
            # Criar dataframe futuro
            future_dates = model.make_future_dataframe(periods=forecast_period)
            forecast = model.predict(future_dates)
            
            return daily_sales, forecast
        else:
            return None, None
    except Exception as e:
        logger.error(f"Erro ao criar forecast: {str(e)}")
        st.error(f"Erro ao criar forecast: {str(e)}")
        return None, None

def analyze_opportunities(df, target_margin, max_investment, min_year, max_mileage):
    """Analisa oportunidades de compra para revenda."""
    try:
        # Análise de oportunidades
        opportunities = df[
            (df['year'] >= min_year) &
            (df['odometer'] <= max_mileage) &
            (df['price'] <= max_investment)
        ].copy()
        
        # Calcular potencial de revenda
        opportunities['preco_revenda'] = opportunities['price'] * (1 + target_margin/100)
        opportunities['potencial_lucro'] = opportunities['preco_revenda'] - opportunities['price']
        opportunities['roi'] = (opportunities['potencial_lucro'] / opportunities['price']) * 100
        
        # Ordenar por ROI
        opportunities = opportunities.sort_values('roi', ascending=False)
        
        return opportunities
    except Exception as e:
        logger.error(f"Erro ao analisar oportunidades: {str(e)}")
        st.error(f"Erro ao analisar oportunidades: {str(e)}")
        return None

def main():
    # Título principal
    st.title("📊 Dashboard de Análise de Carros Usados")
    
    # Carregar dados
    df = load_data()
    if df is None:
        st.error("Não foi possível carregar os dados. Verifique os logs para mais detalhes.")
        return
    
    # Sidebar
    st.sidebar.title("Filtros")
    
    # Filtros
    selected_manufacturers = st.sidebar.multiselect(
        "Fabricantes",
        options=sorted(df['manufacturer'].unique()),
        default=[]
    )
    
    selected_states = st.sidebar.multiselect(
        "Estados",
        options=sorted(df['state'].unique()),
        default=[]
    )
    
    min_year, max_year = st.sidebar.slider(
        "Ano",
        min_value=int(df['year'].min()),
        max_value=int(df['year'].max()),
        value=(int(df['year'].min()), int(df['year'].max()))
    )
    
    # Aplicar filtros
    mask = df['year'].between(min_year, max_year)
    if selected_manufacturers:
        mask &= df['manufacturer'].isin(selected_manufacturers)
    if selected_states:
        mask &= df['state'].isin(selected_states)
    
    filtered_df = df[mask]
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total de Veículos",
            f"{len(filtered_df):,}"
        )
    
    with col2:
        st.metric(
            "Preço Médio",
            f"${filtered_df['price'].mean():,.2f}"
        )
    
    with col3:
        st.metric(
            "Quilometragem Média",
            f"{filtered_df['odometer'].mean():,.0f}"
        )
    
    with col4:
        st.metric(
            "Idade Média",
            f"{filtered_df['vehicle_age'].mean():.1f} anos"
        )
    
    # Tabs para diferentes análises
    tab1, tab2, tab3 = st.tabs(["Análise de Mercado", "Forecast de Vendas", "Recomendações de Compra"])
    
    with tab1:
        st.subheader("Distribuição de Preços")
        fig = px.histogram(
            filtered_df,
            x="price",
            nbins=50,
            title="Distribuição de Preços"
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Top 10 fabricantes
        st.subheader("Top 10 Fabricantes")
        top_manufacturers = filtered_df.groupby('manufacturer').agg({
            'price': ['count', 'mean'],
            'market_avg_price': 'first'
        }).sort_values(('price', 'count'), ascending=False).head(10)
        
        fig = go.Figure(data=[
            go.Bar(
                x=top_manufacturers.index,
                y=top_manufacturers[('price', 'count')],
                name='Quantidade'
            ),
            go.Bar(
                x=top_manufacturers.index,
                y=top_manufacturers[('price', 'mean')],
                name='Preço Médio',
                yaxis='y2'
            ),
            go.Scatter(
                x=top_manufacturers.index,
                y=top_manufacturers[('market_avg_price', 'first')],
                name='Média de Mercado',
                yaxis='y2',
                line=dict(color='red', dash='dot')
            )
        ])
        
        fig.update_layout(
            title='Top 10 Fabricantes - Quantidade e Preço Médio',
            yaxis=dict(title='Quantidade'),
            yaxis2=dict(title='Preço Médio', overlaying='y', side='right')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Mapa de calor de preços
        st.subheader("Mapa de Calor de Preços")
        fig = px.density_mapbox(
            filtered_df,
            lat='latitude',
            lon='longitude',
            z='price',
            radius=10,
            center=dict(lat=39.8283, lon=-98.5795),
            zoom=3,
            mapbox_style="carto-positron",
            title="Distribuição Geográfica de Preços"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Previsão de Vendas")
        
        # Selecionar período de forecast
        forecast_period = st.slider(
            "Período de Previsão (dias)",
            min_value=30,
            max_value=365,
            value=90
        )
        
        # Selecionar fabricante para análise
        forecast_manufacturer = st.selectbox(
            "Fabricante para Análise",
            options=sorted(filtered_df['manufacturer'].unique())
        )
        
        # Criar forecast
        daily_sales, forecast = create_forecast(filtered_df, forecast_manufacturer, forecast_period)
        
        if daily_sales is not None and forecast is not None:
            # Plotar forecast
            fig = go.Figure()
            
            # Dados históricos
            fig.add_trace(go.Scatter(
                x=daily_sales['ds'],
                y=daily_sales['y'],
                name='Vendas Históricas',
                line=dict(color='blue')
            ))
            
            # Forecast
            fig.add_trace(go.Scatter(
                x=forecast['ds'],
                y=forecast['yhat'],
                name='Previsão',
                line=dict(color='red')
            ))
            
            # Intervalo de confiança
            fig.add_trace(go.Scatter(
                x=forecast['ds'].tolist() + forecast['ds'].tolist()[::-1],
                y=forecast['yhat_upper'].tolist() + forecast['yhat_lower'].tolist()[::-1],
                fill='toself',
                fillcolor='rgba(255,0,0,0.2)',
                line=dict(color='rgba(255,0,0,0)'),
                name='Intervalo de Confiança'
            ))
            
            fig.update_layout(
                title=f'Forecast de Vendas - {forecast_manufacturer}',
                xaxis_title='Data',
                yaxis_title='Quantidade de Vendas',
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Métricas de forecast
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_forecast = forecast['yhat'].mean()
                st.metric(
                    "Média Diária Prevista",
                    f"{avg_forecast:.1f} vendas"
                )
            
            with col2:
                total_forecast = forecast['yhat'].sum()
                st.metric(
                    "Total Previsto no Período",
                    f"{total_forecast:.0f} vendas"
                )
            
            with col3:
                growth_rate = ((forecast['yhat'].mean() - daily_sales['y'].mean()) / daily_sales['y'].mean()) * 100
                st.metric(
                    "Taxa de Crescimento",
                    f"{growth_rate:.1f}%"
                )
        else:
            st.warning("Dados insuficientes para realizar forecast. Necessário mínimo de 30 dias de dados.")
    
    with tab3:
        st.subheader("Recomendações de Compra para Revenda")
        
        # Parâmetros de análise
        col1, col2 = st.columns(2)
        
        with col1:
            target_margin = st.slider(
                "Margem de Lucro Alvo (%)",
                min_value=5.0,
                max_value=30.0,
                value=15.0
            )
            
            max_investment = st.number_input(
                "Investimento Máximo por Veículo ($)",
                min_value=10000,
                max_value=100000,
                value=50000
            )
        
        with col2:
            min_year = st.number_input(
                "Ano Mínimo",
                min_value=1990,
                max_value=2024,
                value=2015
            )
            
            max_mileage = st.number_input(
                "Quilometragem Máxima",
                min_value=0,
                max_value=200000,
                value=100000
            )
        
        # Analisar oportunidades
        opportunities = analyze_opportunities(
            filtered_df, target_margin, max_investment, min_year, max_mileage
        )
        
        if opportunities is not None:
            # Mostrar top oportunidades
            st.write("Top 10 Oportunidades de Compra:")
            
            for idx, row in opportunities.head(10).iterrows():
                with st.expander(f"{row['manufacturer']} {row['model']} {row['year']} - ROI: {row['roi']:.1f}%"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Detalhes do Veículo:**")
                        st.write(f"- Preço Atual: ${row['price']:,.2f}")
                        st.write(f"- Quilometragem: {row['odometer']:,} km")
                        st.write(f"- Estado: {row['state']}")
                        st.write(f"- Condição: {row['condition']}")
                    
                    with col2:
                        st.write(f"**Análise de Revenda:**")
                        st.write(f"- Preço Sugerido Revenda: ${row['preco_revenda']:,.2f}")
                        st.write(f"- Lucro Potencial: ${row['potencial_lucro']:,.2f}")
                        st.write(f"- ROI: {row['roi']:.1f}%")
                        
                        # Análise de mercado
                        similar_cars = filtered_df[
                            (filtered_df['manufacturer'] == row['manufacturer']) &
                            (filtered_df['model'] == row['model']) &
                            (filtered_df['year'].between(row['year'] - 1, row['year'] + 1))
                        ]
                        
                        if not similar_cars.empty:
                            market_avg = similar_cars['price'].mean()
                            price_diff = ((row['preco_revenda'] - market_avg) / market_avg) * 100
                            st.write(f"- Diferença para Média de Mercado: {price_diff:+.1f}%")
            
            # Gráfico de distribuição de ROI
            fig = px.histogram(
                opportunities,
                x='roi',
                nbins=50,
                title='Distribuição de ROI nas Oportunidades'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Análise por cor
            st.subheader("Análise por Cor")
            
            color_analysis = opportunities.groupby('paint_color').agg({
                'price': ['count', 'mean'],
                'roi': 'mean'
            }).sort_values(('roi', 'mean'), ascending=False)
            
            fig = go.Figure(data=[
                go.Bar(
                    x=color_analysis.index,
                    y=color_analysis[('roi', 'mean')],
                    name='ROI Médio'
                ),
                go.Bar(
                    x=color_analysis.index,
                    y=color_analysis[('price', 'count')],
                    name='Quantidade',
                    yaxis='y2'
                )
            ])
            
            fig.update_layout(
                title='Análise de Oportunidades por Cor',
                yaxis=dict(title='ROI Médio (%)'),
                yaxis2=dict(title='Quantidade de Veículos', overlaying='y', side='right')
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "Desenvolvido com ❤️ usando Streamlit | "
        "Dados atualizados em: " + filtered_df['posting_date'].max().strftime('%d/%m/%Y')
    )

if __name__ == "__main__":
    main() 