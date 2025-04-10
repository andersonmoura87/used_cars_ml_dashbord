import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar página
st.set_page_config(
    page_title="Análise de Carros Usados",
    page_icon="🚗",
    layout="wide"
)

# Função para conectar ao banco de dados
@st.cache_resource
def get_db_connection():
    """Estabelece conexão com o banco de dados."""
    return create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
        connect_args={'client_encoding': 'utf8'}
    )

# Função para carregar dados
@st.cache_data
def load_data():
    """Carrega dados da view clean_cars."""
    engine = get_db_connection()
    query = """
    SELECT 
        manufacturer, model, year, price, condition,
        odometer, title_status, transmission, region,
        has_installments, monthly_payment, down_payment, installments
    FROM clean_cars
    """
    return pd.read_sql(query, engine)

# Função para treinar modelo
@st.cache_resource
def train_price_model(df):
    """Treina um modelo de Random Forest para previsão de preços."""
    # Preparar features
    le = LabelEncoder()
    X = df[['year', 'odometer']].copy()
    X['manufacturer'] = le.fit_transform(df['manufacturer'])
    X['condition'] = le.fit_transform(df['condition'])
    X['transmission'] = le.fit_transform(df['transmission'])
    
    y = df['price']
    
    # Dividir dados
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Treinar modelo
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    return model, le

def main():
    st.title("🚗 Análise de Carros Usados")
    
    # Carregar dados
    with st.spinner('Carregando dados...'):
        df = load_data()
    
    # Sidebar para filtros
    st.sidebar.header("Filtros")
    
    # Filtro de fabricante
    manufacturers = ['Todos'] + sorted(df['manufacturer'].unique().tolist())
    selected_manufacturer = st.sidebar.selectbox('Fabricante:', manufacturers)
    
    # Filtro de ano
    year_range = st.sidebar.slider(
        'Ano:',
        min_value=int(df['year'].min()),
        max_value=int(df['year'].max()),
        value=(int(df['year'].min()), int(df['year'].max()))
    )
    
    # Filtro de preço
    price_range = st.sidebar.slider(
        'Preço (USD):',
        min_value=float(df['price'].min()),
        max_value=float(df['price'].max()),
        value=(float(df['price'].min()), float(df['price'].max()))
    )
    
    # Aplicar filtros
    mask = (df['year'].between(year_range[0], year_range[1])) & \
           (df['price'].between(price_range[0], price_range[1]))
    
    if selected_manufacturer != 'Todos':
        mask &= (df['manufacturer'] == selected_manufacturer)
    
    filtered_df = df[mask]
    
    # Layout principal com três colunas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Carros", len(filtered_df))
    
    with col2:
        st.metric("Preço Médio", f"${filtered_df['price'].mean():,.2f}")
    
    with col3:
        st.metric("Idade Média", f"{2024 - filtered_df['year'].mean():.1f} anos")
    
    # Gráficos
    st.subheader("Distribuição de Preços por Fabricante")
    fig_box = px.box(
        filtered_df,
        x='manufacturer',
        y='price',
        title='Distribuição de Preços por Fabricante'
    )
    st.plotly_chart(fig_box, use_container_width=True)
    
    # Duas colunas para mais gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Preço vs. Ano")
        fig_scatter = px.scatter(
            filtered_df,
            x='year',
            y='price',
            color='manufacturer',
            title='Preço vs. Ano do Veículo'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col2:
        st.subheader("Preço vs. Quilometragem")
        fig_scatter2 = px.scatter(
            filtered_df,
            x='odometer',
            y='price',
            color='manufacturer',
            title='Preço vs. Quilometragem'
        )
        st.plotly_chart(fig_scatter2, use_container_width=True)
    
    # Seção de ML
    st.header("🤖 Previsão de Preços")
    
    # Treinar modelo
    with st.spinner('Treinando modelo...'):
        model, le = train_price_model(df)
    
    # Interface para previsão
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pred_manufacturer = st.selectbox(
            'Fabricante para previsão:',
            sorted(df['manufacturer'].unique().tolist())
        )
        pred_year = st.number_input('Ano:', min_value=1900, max_value=2024, value=2020)
    
    with col2:
        pred_condition = st.selectbox(
            'Condição:',
            sorted(df['condition'].unique().tolist())
        )
        pred_odometer = st.number_input('Quilometragem:', min_value=0, value=50000)
    
    with col3:
        pred_transmission = st.selectbox(
            'Transmissão:',
            sorted(df['transmission'].unique().tolist())
        )
        if st.button('Prever Preço'):
            # Preparar dados para previsão
            X_pred = pd.DataFrame({
                'year': [pred_year],
                'odometer': [pred_odometer],
                'manufacturer': [le.transform([pred_manufacturer])[0]],
                'condition': [le.transform([pred_condition])[0]],
                'transmission': [le.transform([pred_transmission])[0]]
            })
            
            # Fazer previsão
            predicted_price = model.predict(X_pred)[0]
            st.metric("Preço Previsto", f"${predicted_price:,.2f}")
    
    # Estatísticas detalhadas
    st.header("📊 Estatísticas Detalhadas")
    
    stats_df = filtered_df.groupby('manufacturer').agg({
        'price': ['count', 'mean', 'std', 'min', 'max'],
        'year': 'mean',
        'odometer': 'mean'
    }).round(2)
    
    stats_df.columns = ['Total', 'Preço Médio', 'Desvio Padrão', 'Preço Mínimo', 'Preço Máximo', 'Ano Médio', 'Quilometragem Média']
    st.dataframe(stats_df, use_container_width=True)
    
    # Informações sobre parcelamento
    st.header("💰 Análise de Parcelamento")
    
    # Proporção de carros com parcelamento
    installment_ratio = filtered_df['has_installments'].mean() * 100
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Carros com Parcelamento", f"{installment_ratio:.1f}%")
        
        # Gráfico de pizza para proporção de parcelamento
        fig_pie = px.pie(
            values=[installment_ratio, 100-installment_ratio],
            names=['Com Parcelamento', 'Sem Parcelamento'],
            title='Proporção de Carros com Parcelamento'
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Distribuição do número de parcelas
        installment_df = filtered_df[filtered_df['has_installments']]
        fig_hist = px.histogram(
            installment_df,
            x='installments',
            title='Distribuição do Número de Parcelas'
        )
        st.plotly_chart(fig_hist, use_container_width=True)

if __name__ == "__main__":
    main() 