import streamlit as st
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from xgboost import XGBRegressor
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Área do Vendedor",
    page_icon="💰",
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

@st.cache_resource
def train_price_model(df):
    """Treina modelo de previsão de preços"""
    try:
        # Preparar features
        features = ['year', 'odometer', 'condition', 'fuel', 'transmission', 'manufacturer']
        X = df[features].copy()
        y = df['price']

        # Criar e treinar encoders
        encoders = {}
        for col in ['condition', 'fuel', 'transmission', 'manufacturer']:
            encoders[col] = LabelEncoder().fit(df[col].astype(str))
            X[col] = encoders[col].transform(X[col].astype(str))

        # Normalizar features numéricas
        scaler = StandardScaler()
        X[['year', 'odometer']] = scaler.fit_transform(X[['year', 'odometer']])

        # Treinar modelo
        model = XGBRegressor(random_state=42)
        model.fit(X, y)

        return model, scaler, encoders, features
    except Exception as e:
        st.error(f"Erro ao treinar modelo: {e}")
        return None, None, None, None

def get_market_insights(df, manufacturer, model, year, condition):
    """Obtém insights de mercado para um veículo específico"""
    insights = {}
    
    # Filtrar dados similares
    similar_cars = df[
        (df['manufacturer'] == manufacturer) &
        (df['model'] == model) &
        (df['year'].between(year - 2, year + 2))
    ]
    
    if len(similar_cars) > 0:
        insights['total_similar'] = len(similar_cars)
        insights['avg_price'] = similar_cars['price'].mean()
        insights['min_price'] = similar_cars['price'].min()
        insights['max_price'] = similar_cars['price'].max()
        insights['median_price'] = similar_cars['price'].median()
        insights['std_price'] = similar_cars['price'].std()
        insights['avg_days_listed'] = similar_cars['days_listed'].mean() if 'days_listed' in similar_cars.columns else None
    else:
        # Se não houver carros similares, buscar por fabricante
        similar_cars = df[df['manufacturer'] == manufacturer]
        insights['total_similar'] = len(similar_cars)
        insights['avg_price'] = similar_cars['price'].mean()
        insights['min_price'] = similar_cars['price'].min()
        insights['max_price'] = similar_cars['price'].max()
        insights['median_price'] = similar_cars['price'].median()
        insights['std_price'] = similar_cars['price'].std()
        insights['avg_days_listed'] = similar_cars['days_listed'].mean() if 'days_listed' in similar_cars.columns else None
    
    return insights

def main():
    st.title("💰 Área do Vendedor")
    st.subheader("Avalie o Preço do Seu Carro")

    # Carregar dados
    df = load_data()
    if df is None:
        return

    # Treinar modelo
    model, scaler, encoders, features = train_price_model(df)
    if model is None:
        return

    # Interface para entrada de dados
    col1, col2 = st.columns(2)

    with col1:
        # Dados básicos do veículo
        manufacturer = st.selectbox(
            "Fabricante",
            sorted(df['manufacturer'].unique())
        )
        
        models = sorted(df[df['manufacturer'] == manufacturer]['model'].unique())
        model_name = st.selectbox("Modelo", models)
        
        year = st.number_input(
            "Ano",
            min_value=int(df['year'].min()),
            max_value=int(df['year'].max()),
            value=2020
        )

    with col2:
        # Características do veículo
        condition = st.selectbox(
            "Condição",
            sorted(df['condition'].unique())
        )
        
        odometer = st.number_input(
            "Quilometragem",
            min_value=0,
            value=50000,
            step=1000
        )
        
        transmission = st.selectbox(
            "Transmissão",
            sorted(df['transmission'].unique())
        )
        
        fuel = st.selectbox(
            "Combustível",
            sorted(df['fuel'].unique())
        )

    # Botão para análise
    if st.button("Analisar Mercado"):
        try:
            # Preparar dados para previsão
            X_pred = pd.DataFrame({
                'year': [year],
                'odometer': [odometer],
                'condition': [str(condition)],
                'fuel': [str(fuel)],
                'transmission': [str(transmission)],
                'manufacturer': [str(manufacturer)]
            })

            # Transformar dados categóricos
            for col in ['condition', 'fuel', 'transmission', 'manufacturer']:
                try:
                    X_pred[col] = encoders[col].transform(X_pred[col])
                except ValueError as e:
                    st.error(f"Erro: valor não reconhecido para {col}. Por favor, selecione um valor válido.")
                    return

            # Normalizar dados numéricos
            X_pred[['year', 'odometer']] = scaler.transform(X_pred[['year', 'odometer']])

            # Fazer previsão
            predicted_price = model.predict(X_pred)[0]

            # Obter insights de mercado
            insights = get_market_insights(df, manufacturer, model_name, year, condition)

            # Mostrar resultados
            st.header("Resultados da Análise")

            # Métricas principais
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Preço Sugerido",
                    f"${predicted_price:,.2f}",
                    delta=f"${predicted_price - insights['median_price']:,.2f} vs. Mediana"
                )
            
            with col2:
                st.metric(
                    "Preço Médio do Mercado",
                    f"${insights['avg_price']:,.2f}",
                    delta=f"±${insights['std_price']:,.2f}"
                )
            
            with col3:
                st.metric(
                    "Carros Similares",
                    f"{insights['total_similar']:,}"
                )

            # Gráficos
            col1, col2 = st.columns(2)

            with col1:
                # Distribuição de preços para carros similares
                similar_cars = df[
                    (df['manufacturer'] == manufacturer) &
                    (df['model'] == model_name) &
                    (df['year'].between(year - 2, year + 2))
                ]

                fig_dist = px.histogram(
                    similar_cars,
                    x='price',
                    title='Distribuição de Preços - Carros Similares',
                    labels={'price': 'Preço ($)', 'count': 'Quantidade'}
                )
                
                # Adicionar linha vertical para o preço previsto
                fig_dist.add_vline(
                    x=predicted_price,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Preço Sugerido"
                )
                
                st.plotly_chart(fig_dist, use_container_width=True)

            with col2:
                # Preço vs. Quilometragem para modelo específico
                fig_scatter = px.scatter(
                    df[df['model'] == model_name],
                    x='odometer',
                    y='price',
                    color='year',
                    title=f'Preço vs. Quilometragem - {model_name}',
                    labels={
                        'odometer': 'Quilometragem',
                        'price': 'Preço ($)',
                        'year': 'Ano'
                    }
                )
                
                # Adicionar ponto para o carro atual
                fig_scatter.add_trace(
                    go.Scatter(
                        x=[odometer],
                        y=[predicted_price],
                        mode='markers',
                        marker=dict(
                            color='red',
                            size=15,
                            symbol='star'
                        ),
                        name='Seu Carro'
                    )
                )
                
                st.plotly_chart(fig_scatter, use_container_width=True)

            # Tabela de comparação
            st.subheader("Comparação com o Mercado")
            
            comparison_df = pd.DataFrame({
                'Métrica': [
                    'Preço Sugerido',
                    'Preço Médio',
                    'Preço Mediano',
                    'Preço Mínimo',
                    'Preço Máximo',
                    'Desvio Padrão'
                ],
                'Valor': [
                    f"${predicted_price:,.2f}",
                    f"${insights['avg_price']:,.2f}",
                    f"${insights['median_price']:,.2f}",
                    f"${insights['min_price']:,.2f}",
                    f"${insights['max_price']:,.2f}",
                    f"${insights['std_price']:,.2f}"
                ]
            })
            
            st.dataframe(comparison_df, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao analisar mercado: {str(e)}")

if __name__ == "__main__":
    main() 