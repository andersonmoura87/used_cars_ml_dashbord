import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import logging
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from prophet import Prophet
from pathlib import Path

# Configurar página (deve ser a primeira chamada do Streamlit)
st.set_page_config(
    page_title="CarMarket Analytics",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()
logger.info("Variáveis de ambiente carregadas")

# Verificar variáveis de ambiente
required_env_vars = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    st.error(f"Variáveis de ambiente ausentes: {', '.join(missing_vars)}")
    st.stop()

# Configurar conexão com o banco
@st.cache_resource
def get_db_connection():
    """Cria conexão com o banco de dados."""
    return create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}',
        connect_args={
            'client_encoding': 'utf8',
            'options': '-c client_encoding=utf8'
        }
    )

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

# Carregar dados
@st.cache_data
def load_data():
    """Carrega dados do banco de dados."""
    engine = get_db_connection()
    
    query = """
    SELECT 
        manufacturer, model, year, price, odometer, fuel,
        condition, state, latitude, longitude, posting_date,
        vehicle_age, transmission, drive, type, paint_color
    FROM cars_cleaned
    WHERE price > 0 
    AND year >= 1990
    AND posting_date IS NOT NULL
    """
    
    # Carregar dados com encoding específico
    df = pd.read_sql(
        query, 
        engine,
        parse_dates=['posting_date'],
        encoding='utf-8'
    )
    
    # Limpar encoding de colunas de texto
    text_columns = ['manufacturer', 'model', 'fuel', 'condition', 'state', 
                   'transmission', 'drive', 'type', 'paint_color']
    
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_text_encoding)
    
    return df

@st.cache_data
def load_predictions():
    try:
        # Criar dados de previsão de exemplo
        logger.info("Criando dados de previsão de exemplo...")
        
        # Criar datas futuras
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        
        # Criar volume previsto com tendência e sazonalidade
        base_volume = 100
        trend = np.linspace(0, 20, len(dates))
        seasonality = 10 * np.sin(np.linspace(0, 4*np.pi, len(dates)))
        noise = np.random.normal(0, 5, len(dates))
        
        predicted_volume = base_volume + trend + seasonality + noise
        
        # Criar DataFrame
        predictions_df = pd.DataFrame({
            'date': dates,
            'predicted_volume': predicted_volume
        })
        
        logger.info(f"Dados de previsão de exemplo criados com sucesso: {len(predictions_df)} registros")
        return predictions_df
    except Exception as e:
        logger.error(f"Erro ao criar dados de previsão de exemplo: {str(e)}")
        st.error(f"Erro ao criar dados de previsão de exemplo: {str(e)}")
        return None

# Carregar modelos
@st.cache_resource
def load_models():
    try:
        logger.info("Criando modelos de exemplo...")
        
        # Criar dados de exemplo para treinar os modelos
        df = load_data()
        
        # Criar encoders separados para cada característica categórica
        manufacturer_le = LabelEncoder()
        model_le = LabelEncoder()
        condition_le = LabelEncoder()
        fuel_le = LabelEncoder()
        
        # Treinar os encoders
        manufacturer_encoded = manufacturer_le.fit_transform(df['manufacturer'])
        model_encoded = model_le.fit_transform(df['model'])
        condition_encoded = condition_le.fit_transform(df['condition'])
        fuel_encoded = fuel_le.fit_transform(df['fuel'])
        
        # Criar modelo de preço
        X = pd.DataFrame({
            'year': df['year'],
            'odometer': df['odometer'],
            'manufacturer_encoded': manufacturer_encoded,
            'model_encoded': model_encoded,
            'condition_encoded': condition_encoded,
            'fuel_encoded': fuel_encoded
        })
        
        price_model = LinearRegression()
        price_model.fit(X, df['price'])
        
        models = {
            'price': price_model,
            'manufacturer_le': manufacturer_le,
            'model_le': model_le,
            'condition_le': condition_le,
            'fuel_le': fuel_le
        }
        
        logger.info("Modelos de exemplo criados com sucesso")
        return models
    except Exception as e:
        logger.error(f"Erro ao criar modelos: {str(e)}")
        st.error(f"Erro ao criar modelos: {str(e)}")
        return None

# Sistema de recomendação
@st.cache_data
def get_similar_cars(df, car_features, n_recommendations=5):
    try:
        features = ['year', 'price', 'odometer']
        
        scaler = StandardScaler()
        features_matrix = scaler.fit_transform(df[features])
        
        car_features_scaled = scaler.transform(car_features[features].reshape(1, -1))
        similarities = cosine_similarity(car_features_scaled, features_matrix)
        
        similar_indices = similarities[0].argsort()[-n_recommendations:][::-1]
        
        return df.iloc[similar_indices]
    except Exception as e:
        logger.error(f"Erro ao buscar carros similares: {str(e)}")
        st.error(f"Erro ao buscar carros similares: {str(e)}")
        return None

def create_manager_dashboard(df):
    st.header("📊 Dashboard do Gestor")
    
    # Layout em colunas para KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    # KPIs
    with col1:
        st.metric(
            label="Total de Veículos",
            value=f"{len(df):,}",
            delta=f"{len(df[df['posting_date'] > (pd.Timestamp.now() - pd.Timedelta(days=7))])} novos (7d)"
        )
    
    with col2:
        avg_price = df['price'].mean()
        st.metric(
            label="Preço Médio",
            value=f"${avg_price:,.2f}",
            delta=f"{((df[df['posting_date'] > (pd.Timestamp.now() - pd.Timedelta(days=7))]['price'].mean() / avg_price - 1) * 100):.1f}%"
        )
    
    with col3:
        avg_days = (pd.Timestamp.now() - df['posting_date']).mean().days
        st.metric(
            label="Tempo Médio em Estoque",
            value=f"{avg_days:.1f} dias",
            delta=None
        )
    
    with col4:
        premium_percent = (df['price'] > avg_price).mean() * 100
        st.metric(
            label="% Veículos Premium",
            value=f"{premium_percent:.1f}%",
            delta=None
        )
    
    # Análise de Mercado
    st.subheader("📈 Análise de Mercado")
    col1, col2 = st.columns(2)
    
    with col1:
        # Tendência de preços por mês
        df['month'] = df['posting_date'].dt.to_period('M')
        price_trend = df.groupby('month').agg({
            'price': 'mean'
        }).reset_index()
        price_trend['month'] = price_trend['month'].astype(str)
        
        fig = px.line(price_trend, x='month', y='price',
                     title='Tendência de Preços',
                     labels={'price': 'Preço Médio', 'month': 'Mês'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Top 5 fabricantes
        top_manufacturers = df.groupby('manufacturer').agg({
            'manufacturer': 'count',
            'price': 'mean'
        }).rename(columns={'manufacturer': 'count'}).sort_values('count', ascending=False).head(5)
        
        fig = px.bar(top_manufacturers, 
                    title='Top 5 Fabricantes',
                    labels={'value': 'Quantidade', 'manufacturer': 'Fabricante'},
                    color='price',
                    color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)
    
    # Análise Regional
    st.subheader("🗺️ Análise Regional")
    col1, col2 = st.columns(2)
    
    with col1:
        # Mapa de calor por estado
        state_metrics = df.groupby('state').agg({
            'price': 'mean',
            'manufacturer': 'count'
        }).reset_index()
        
        fig = px.choropleth(state_metrics,
                           locations='state',
                           locationmode="USA-states",
                           color='price',
                           scope="usa",
                           title='Preço Médio por Estado',
                           color_continuous_scale="Viridis")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Métricas por região
        region_metrics = df.groupby('region').agg({
            'manufacturer': 'count',
            'price': ['mean', 'std'],
            'odometer': 'mean'
        }).round(2)
        region_metrics.columns = ['Total', 'Preço Médio', 'Desvio Padrão', 'Km Média']
        st.dataframe(region_metrics, use_container_width=True)
    
    # Análise de Produto
    st.subheader("🚗 Análise de Produto")
    col1, col2 = st.columns(2)
    
    with col1:
        # Mix de produtos (TreeMap)
        product_mix = df.groupby(['manufacturer', 'model']).size().reset_index(name='count')
        fig = px.treemap(product_mix, 
                        path=[px.Constant("Todos"), 'manufacturer', 'model'],
                        values='count',
                        title='Mix de Produtos')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Matriz de desempenho
        fig = px.scatter(df,
                        x='odometer',
                        y='price',
                        color='manufacturer',
                        title='Matriz Preço x Quilometragem',
                        labels={'odometer': 'Quilometragem', 'price': 'Preço'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Filtros laterais
    with st.sidebar:
        st.subheader("Filtros")
        
        # Filtro de período
        date_range = st.date_input(
            "Período",
            value=(df['posting_date'].min(), df['posting_date'].max()),
            min_value=df['posting_date'].min().date(),
            max_value=df['posting_date'].max().date()
        )
        
        # Filtro de fabricante
        selected_manufacturers = st.multiselect(
            "Fabricantes",
            options=sorted(df['manufacturer'].unique()),
            default=[]
        )
        
        # Filtro de faixa de preço
        price_range = st.slider(
            "Faixa de Preço",
            min_value=float(df['price'].min()),
            max_value=float(df['price'].max()),
            value=(float(df['price'].min()), float(df['price'].max()))
        )
        
        # Filtro de região/estado
        selected_regions = st.multiselect(
            "Regiões",
            options=sorted(df['region'].unique()),
            default=[]
        )

def create_market_analysis(df):
    st.header("📈 Análise de Mercado")
    
    # Distribuição de preços por ano
    st.subheader("Distribuição de Preços por Ano")
    fig = px.box(df, x='year', y='price',
                 title='Distribuição de Preços por Ano de Fabricação',
                 labels={'year': 'Ano', 'price': 'Preço ($)'})
    st.plotly_chart(fig, use_container_width=True)
    
    # Mapa de distribuição
    st.subheader("Distribuição Geográfica")
    fig = px.scatter_mapbox(df, 
                           lat='latitude', 
                           lon='longitude',
                           color='price',
                           size='price',
                           hover_name='manufacturer',
                           hover_data=['model', 'year', 'price'],
                           title='Distribuição de Veículos por Estado',
                           color_continuous_scale='Viridis',
                           zoom=3,
                           mapbox_style='carto-positron')
    st.plotly_chart(fig, use_container_width=True)
    
    # Top 5 fabricantes
    st.subheader("Top 5 Fabricantes")
    top_manufacturers = df.groupby('manufacturer').agg({
        'manufacturer': 'count',
        'price': 'mean'
    }).rename(columns={'manufacturer': 'count'}).sort_values('count', ascending=False).head(5)
    
    fig = px.bar(top_manufacturers,
                 title='Top 5 Fabricantes: Volume e Preço Médio',
                 labels={'value': 'Quantidade', 'manufacturer': 'Fabricante'},
                 color='price',
                 color_continuous_scale='Viridis')
    st.plotly_chart(fig, use_container_width=True)
    
    # Quilometragem média por combustível
    st.subheader("Quilometragem por Tipo de Combustível")
    fuel_mileage = df.groupby('fuel')['odometer'].mean().sort_values(ascending=False)
    
    fig = px.bar(fuel_mileage,
                 title='Quilometragem Média por Tipo de Combustível',
                 labels={'fuel': 'Combustível', 'value': 'Quilometragem Média'},
                 color=fuel_mileage.values,
                 color_continuous_scale='Viridis')
    st.plotly_chart(fig, use_container_width=True)
    
    # Análise de dispersão
    st.subheader("Relação Preço vs. Quilometragem")
    fig = px.scatter(df,
                    x='odometer',
                    y='price',
                    color='manufacturer',
                    title='Relação entre Preço e Quilometragem',
                    labels={'odometer': 'Quilometragem', 'price': 'Preço ($)'},
                    trendline="lowess")
    st.plotly_chart(fig, use_container_width=True)

def create_predictions_page(df):
    st.header("🔮 Previsões e Tendências")
    
    # Carregar previsões
    predictions = load_predictions()
    
    if predictions is not None:
        # Tendência de volume
        st.subheader("Tendência de Volume de Anúncios")
        fig = px.line(predictions,
                     x='date',
                     y='predicted_volume',
                     title='Previsão de Volume de Anúncios',
                     labels={'date': 'Data', 'predicted_volume': 'Volume Previsto'})
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise sazonal
        st.subheader("Análise Sazonal")
        predictions['month'] = predictions['date'].dt.month
        monthly_avg = predictions.groupby('month')['predicted_volume'].mean()
        
        fig = px.line(monthly_avg,
                     title='Sazonalidade do Volume de Anúncios',
                     labels={'month': 'Mês', 'value': 'Volume Médio Previsto'})
        st.plotly_chart(fig, use_container_width=True)
        
        # Insights
        st.subheader("Insights")
        
        # Encontrar melhor momento para venda
        best_month = monthly_avg.idxmax()
        worst_month = monthly_avg.idxmin()
        
        # Calcular tendências
        trend = (predictions['predicted_volume'].iloc[-1] - predictions['predicted_volume'].iloc[0]) / predictions['predicted_volume'].iloc[0] * 100
        
        st.markdown(f"""
        **Principais insights:**
        - Melhor mês para vender: **{best_month}º mês**
        - Mês com menor movimento: **{worst_month}º mês**
        - Tendência geral do mercado: **{trend:.1f}%**
        """)
        
        # Previsão de preços
        st.subheader("Simulador de Preços")
        
        col1, col2 = st.columns(2)
        
        with col1:
            manufacturer = st.selectbox('Fabricante', sorted(df['manufacturer'].unique()))
            model = st.selectbox('Modelo', sorted(df[df['manufacturer'] == manufacturer]['model'].unique()))
            year = st.number_input('Ano', min_value=2010, max_value=2024, value=2020)
            
        with col2:
            odometer = st.number_input('Quilometragem', min_value=0, value=50000)
            condition = st.selectbox('Condição', sorted(df['condition'].unique()))
            fuel = st.selectbox('Combustível', sorted(df['fuel'].unique()))
        
        if st.button("Calcular Preço Estimado"):
            # Carregar modelos
            models = load_models()
            
            if models is not None:
                try:
                    # Preparar dados para previsão
                    input_data = pd.DataFrame({
                        'year': [year],
                        'odometer': [odometer],
                        'manufacturer_encoded': [models['manufacturer_le'].transform([manufacturer])[0]],
                        'model_encoded': [models['model_le'].transform([model])[0]],
                        'condition_encoded': [models['condition_le'].transform([condition])[0]],
                        'fuel_encoded': [models['fuel_le'].transform([fuel])[0]]
                    })
                    
                    # Fazer previsão
                    price_prediction = models['price'].predict(input_data)[0]
                    
                    # Mostrar resultado
                    st.success(f"Preço estimado: ${price_prediction:,.2f}")
                    
                    # Mostrar comparação com mercado
                    similar_cars = df[
                        (df['manufacturer'] == manufacturer) &
                        (df['model'] == model) &
                        (abs(df['year'] - year) <= 2)
                    ]
                    
                    if len(similar_cars) > 0:
                        st.markdown(f"""
                        **Comparação com o mercado:**
                        - Preço médio: ${similar_cars['price'].mean():,.2f}
                        - Preço mínimo: ${similar_cars['price'].min():,.2f}
                        - Preço máximo: ${similar_cars['price'].max():,.2f}
                        - Número de veículos similares: {len(similar_cars)}
                        """)
                        
                except Exception as e:
                    st.error(f"Erro ao calcular preço: {str(e)}")
    else:
        st.error("Não foi possível carregar as previsões")

    # Seção de Forecast e Recomendações para Revenda
    st.header("📈 Forecast e Recomendações para Revenda")

    # Tabs para diferentes análises
    tab1, tab2 = st.tabs(["Forecast de Vendas", "Recomendações de Compra"])

    with tab1:
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
            options=sorted(df['manufacturer'].unique())
        )
        
        # Preparar dados para forecast
        forecast_data = df[df['manufacturer'] == forecast_manufacturer].copy()
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

    with tab2:
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
                    similar_cars = df[
                        (df['manufacturer'] == row['manufacturer']) &
                        (df['model'] == row['model']) &
                        (df['year'].between(row['year'] - 1, row['year'] + 1))
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

def show_buyer_interface(df):
    st.title("🔍 Busca de Veículos")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        manufacturers = ['Todos'] + sorted(df['manufacturer'].unique().tolist())
        manufacturer = st.selectbox('Fabricante', manufacturers)
        
        if manufacturer != 'Todos':
            models = ['Todos'] + sorted(df[df['manufacturer'] == manufacturer]['model'].unique().tolist())
        else:
            models = ['Todos'] + sorted(df['model'].unique().tolist())
        model = st.selectbox('Modelo', models)
    
    with col2:
        min_year = int(df['year'].min())
        max_year = int(df['year'].max())
        year_range = st.slider('Ano', min_year, max_year, (min_year, max_year))
        
        conditions = ['Todos'] + sorted(df['condition'].unique().tolist())
        condition = st.selectbox('Condição', conditions)
    
    with col3:
        min_price = float(df['price'].min())
        max_price = float(df['price'].max())
        price_range = st.slider('Preço ($)', min_price, max_price, (min_price, max_price))
        
        fuel_types = ['Todos'] + sorted(df['fuel'].unique().tolist())
        fuel = st.selectbox('Combustível', fuel_types)
    
    # Aplicar filtros
    filtered_df = df.copy()
    
    if manufacturer != 'Todos':
        filtered_df = filtered_df[filtered_df['manufacturer'] == manufacturer]
    if model != 'Todos':
        filtered_df = filtered_df[filtered_df['model'] == model]
    if condition != 'Todos':
        filtered_df = filtered_df[filtered_df['condition'] == condition]
    if fuel != 'Todos':
        filtered_df = filtered_df[filtered_df['fuel'] == fuel]
        
    filtered_df = filtered_df[
        (filtered_df['year'] >= year_range[0]) & 
        (filtered_df['year'] <= year_range[1]) &
        (filtered_df['price'] >= price_range[0]) & 
        (filtered_df['price'] <= price_range[1])
    ]
    
    # Mostrar resultados
    st.subheader(f"Resultados encontrados: {len(filtered_df)}")
    
    if len(filtered_df) > 0:
        # Ordenar por preço
        filtered_df = filtered_df.sort_values('price')
        
        # Mostrar cards dos veículos
        for i in range(0, len(filtered_df), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(filtered_df):
                    car = filtered_df.iloc[i + j]
                    with cols[j]:
                        st.markdown(f"""
                        **{car['year']} {car['manufacturer']} {car['model']}**  
                        💰 ${car['price']:,.2f}  
                        🚗 {car['odometer']:,.0f} milhas  
                        ⛽ {car['fuel']}  
                        📍 {car['region']}  
                        """)
                        
                        if st.button(f"Ver similares #{i+j}"):
                            st.subheader("Veículos similares")
                            similar_cars = get_similar_cars(df, car)
                            if similar_cars is not None:
                                for _, similar in similar_cars.iterrows():
                                    st.markdown(f"""
                                    **{similar['year']} {similar['manufacturer']} {similar['model']}**  
                                    💰 ${similar['price']:,.2f}  
                                    🚗 {similar['odometer']:,.0f} milhas
                                    """)
    else:
        st.info("Nenhum veículo encontrado com os filtros selecionados.")

def show_seller_interface(df):
    st.title("📊 Análise de Mercado para Vendedores")
    
    # Formulário para previsão de preço
    st.subheader("Estimativa de Preço")
    
    col1, col2 = st.columns(2)
    
    with col1:
        manufacturer = st.selectbox('Fabricante', sorted(df['manufacturer'].unique()))
        model = st.selectbox('Modelo', sorted(df[df['manufacturer'] == manufacturer]['model'].unique()))
        year = st.number_input('Ano', min_value=1990, max_value=2024, value=2020)
    
    with col2:
        odometer = st.number_input('Quilometragem (milhas)', min_value=0, value=50000)
        condition = st.selectbox('Condição', sorted(df['condition'].unique()))
        fuel = st.selectbox('Combustível', sorted(df['fuel'].unique()))
    
    if st.button("Calcular Preço Estimado"):
        models = load_models()
        if models is not None:
            try:
                # Preparar dados para previsão
                input_data = pd.DataFrame({
                    'year': [year],
                    'odometer': [odometer],
                    'manufacturer_encoded': [models['manufacturer_le'].transform([manufacturer])[0]],
                    'model_encoded': [models['model_le'].transform([model])[0]],
                    'condition_encoded': [models['condition_le'].transform([condition])[0]],
                    'fuel_encoded': [models['fuel_le'].transform([fuel])[0]]
                })
                
                # Fazer previsão
                price_prediction = models['price'].predict(input_data)[0]
                
                # Mostrar resultado
                st.success(f"Preço estimado: ${price_prediction:,.2f}")
                
                # Análise de mercado
                market_data = df[
                    (df['manufacturer'] == manufacturer) &
                    (df['model'] == model) &
                    (df['year'] >= year - 2) &
                    (df['year'] <= year + 2)
                ]
                
                if len(market_data) > 0:
                    st.subheader("Análise de Mercado")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Distribuição de preços
                        fig = px.histogram(
                            market_data,
                            x='price',
                            title='Distribuição de Preços',
                            labels={'price': 'Preço ($)', 'count': 'Quantidade'}
                        )
                        fig.add_vline(x=price_prediction, line_dash="dash", line_color="red")
                        st.plotly_chart(fig)
                        
                    with col2:
                        # Preço vs. Quilometragem
                        fig = px.scatter(
                            market_data,
                            x='odometer',
                            y='price',
                            title='Preço vs. Quilometragem',
                            labels={'odometer': 'Quilometragem (milhas)', 'price': 'Preço ($)'}
                        )
                        fig.add_hline(y=price_prediction, line_dash="dash", line_color="red")
                        st.plotly_chart(fig)
                        
                    # Estatísticas do mercado
                    st.markdown(f"""
                    **Estatísticas do Mercado:**
                    - Preço médio: ${market_data['price'].mean():,.2f}
                    - Preço mínimo: ${market_data['price'].min():,.2f}
                    - Preço máximo: ${market_data['price'].max():,.2f}
                    - Número de anúncios similares: {len(market_data)}
                    """)
                
            except Exception as e:
                logger.error(f"Erro ao fazer previsão: {str(e)}")
                st.error("Erro ao calcular preço estimado. Tente novamente.")
    
    # Tendências de mercado
    predictions = load_predictions()
    if predictions is not None:
        st.subheader("Tendências de Mercado")
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=predictions['date'],
            y=predictions['predicted_volume'],
            mode='lines',
            name='Volume Previsto'
        ))
        
        fig.update_layout(
            title='Previsão de Volume de Anúncios',
            xaxis_title='Data',
            yaxis_title='Volume de Anúncios'
        )
        
        st.plotly_chart(fig)
        
        # Recomendações
        st.subheader("Recomendações")
        
        # Calcular melhor momento para venda
        predictions['date'] = pd.to_datetime(predictions['date'])
        best_date = predictions.loc[predictions['predicted_volume'].idxmin(), 'date']
        
        st.markdown(f"""
        Com base nas previsões:
        - Melhor momento para anunciar: **{best_date.strftime('%d/%m/%Y')}**
        - Volume médio previsto: **{predictions['predicted_volume'].mean():.0f}** anúncios/dia
        """)

def show_manager_interface(df):
    # Menu de navegação para o gestor
    page = st.sidebar.selectbox(
        "Escolha uma página",
        ["Dashboard Gerencial", "Análise de Mercado", "Previsões"]
    )
    
    if page == "Dashboard Gerencial":
        create_manager_dashboard(df)
    elif page == "Análise de Mercado":
        create_market_analysis(df)
    else:
        create_predictions_page(df)

# Interface principal
def main():
    try:
        # Sidebar
        st.sidebar.title("CarMarket Analytics 🚗")
        user_type = st.sidebar.selectbox(
            "Selecione seu perfil:",
            ["Comprador", "Vendedor", "Gestor"]
        )
        
        # Carregar dados
        logger.info("Iniciando carregamento de dados...")
        df = load_data()
        if df is None:
            st.error("Não foi possível carregar os dados. Verifique os logs para mais detalhes.")
            st.stop()
            
        predictions = load_predictions()
        if predictions is None:
            st.warning("Não foi possível carregar as previsões. Algumas funcionalidades podem estar indisponíveis.")
        
        # Mostrar interface apropriada
        if user_type == "Comprador":
            show_buyer_interface(df)
        elif user_type == "Vendedor":
            show_seller_interface(df)
        else:
            show_manager_interface(df)
            
    except Exception as e:
        logger.error(f"Erro na aplicação: {str(e)}")
        st.error(f"Ocorreu um erro na aplicação: {str(e)}")

if __name__ == "__main__":
    main() 