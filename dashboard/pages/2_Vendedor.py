"""Página Vendedor — avaliação de preço com modelo XGBoost persistido em disco."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_DASHBOARD_DIR = Path(__file__).parent.parent
_ROOT = _DASHBOARD_DIR.parent
sys.path.insert(0, str(_DASHBOARD_DIR))
sys.path.insert(0, str(_ROOT))

from _loader import load_data  # noqa: E402
from src.models.price_model import AdvancedPriceModel  # noqa: E402

st.set_page_config(page_title="Vendedor", page_icon="💰", layout="wide")

st.title("Vendedor")
st.caption("Avalie o preço do seu carro com base no mercado atual")

df = load_data()
if df is None:
    st.stop()

CAT_COLS = ["manufacturer", "condition", "fuel", "transmission"]
NUM_COLS = ["year", "odometer"]
FEATURES = CAT_COLS + NUM_COLS


@st.cache_resource(show_spinner="Carregando modelo de preços…")
def _get_model(data_hash: int) -> AdvancedPriceModel:
    """
    Carrega o modelo do disco se existir; caso contrário treina e salva.
    data_hash força novo treino somente quando o dataset mudar.
    """
    available_cat = [c for c in CAT_COLS if c in df.columns]
    available_num = [c for c in NUM_COLS if c in df.columns]

    model, metrics, from_cache = AdvancedPriceModel.load_or_train(
        df=df,
        categorical_features=available_cat,
        numerical_features=available_num,
        target="price",
        models_dir=_ROOT / "models",
        validation_method="full",   # mais rápido no dashboard; CI usa time_series
    )

    if not from_cache and metrics:
        st.sidebar.success(
            f"Modelo treinado e salvo  \nR² {metrics.get('r2', 0):.3f} | "
            f"RMSE ${metrics.get('rmse', 0):,.0f}"
        )
    elif from_cache:
        st.sidebar.info("Modelo carregado do disco (models/price_model_latest.joblib)")

    return model


data_hash = hash(str(df.shape) + str(round(df["price"].sum())))
price_model = _get_model(data_hash)

# extrai encoders/scaler do modelo para uso direto no formulário
encoders = price_model.label_encoders
scaler = price_model.scaler

# ── formulário de entrada ─────────────────────────────────────────────────────
with st.form("avaliacao"):
    col1, col2 = st.columns(2)

    with col1:
        manufacturer = st.selectbox("Fabricante", sorted(df["manufacturer"].dropna().unique()))
        models_available = sorted(df[df["manufacturer"] == manufacturer]["model"].dropna().unique())
        model_name = st.selectbox("Modelo", models_available)
        year = st.number_input("Ano", int(df["year"].min()), int(df["year"].max()), 2020)

    with col2:
        condition = st.selectbox("Condição", sorted(df["condition"].dropna().unique()))
        odometer = st.number_input("Quilometragem", 0, 500_000, 50_000, step=1_000)
        transmission = st.selectbox("Câmbio", sorted(df["transmission"].dropna().unique()))
        fuel = st.selectbox("Combustível", sorted(df["fuel"].dropna().unique()))

    submitted = st.form_submit_button("Avaliar preço", use_container_width=True)

# ── resultado ─────────────────────────────────────────────────────────────────
if submitted:
    try:
        input_df = pd.DataFrame({
            "manufacturer": [str(manufacturer)],
            "condition": [str(condition)],
            "fuel": [str(fuel)],
            "transmission": [str(transmission)],
            "year": [float(year)],
            "odometer": [float(odometer)],
        })
        preds, _ = price_model.predict(input_df, return_std=False)
        predicted = float(preds.iloc[0])

        # comparáveis de mercado
        similar = df[
            (df["manufacturer"] == manufacturer)
            & (df["model"] == model_name)
            & (df["year"].between(year - 2, year + 2))
        ]
        if similar.empty:
            similar = df[df["manufacturer"] == manufacturer]

        avg_p = similar["price"].mean()
        med_p = similar["price"].median()

        # métricas
        st.subheader("Resultado da avaliação")
        c1, c2, c3 = st.columns(3)
        c1.metric("Preço sugerido", f"${predicted:,.2f}",
                  f"${predicted - med_p:+,.2f} vs. mediana")
        c2.metric("Preço médio de mercado", f"${avg_p:,.2f}",
                  f"±${similar['price'].std():,.2f}")
        c3.metric("Carros similares", f"{len(similar):,}")

        col1, col2 = st.columns(2)

        with col1:
            fig = px.histogram(
                similar, x="price",
                title="Distribuição de Preços — Similares",
                labels={"price": "Preço ($)", "count": "Qtd"},
                nbins=30,
            )
            fig.add_vline(x=predicted, line_dash="dash", line_color="red",
                          annotation_text="Sugerido")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.scatter(
                df[df["model"] == model_name],
                x="odometer", y="price", color="year",
                title=f"Preço vs. Km — {model_name}",
                labels={"odometer": "Quilometragem", "price": "Preço ($)", "year": "Ano"},
                opacity=0.6,
            )
            fig.add_trace(go.Scatter(
                x=[odometer], y=[predicted], mode="markers",
                marker=dict(color="red", size=14, symbol="star"),
                name="Seu carro",
            ))
            st.plotly_chart(fig, use_container_width=True)

        # tabela de comparação
        st.subheader("Comparação com o mercado")
        st.dataframe(pd.DataFrame({
            "Métrica": ["Preço sugerido", "Preço médio", "Mediana", "Mínimo", "Máximo", "Desvio padrão"],
            "Valor": [
                f"${predicted:,.2f}", f"${avg_p:,.2f}", f"${med_p:,.2f}",
                f"${similar['price'].min():,.2f}", f"${similar['price'].max():,.2f}",
                f"${similar['price'].std():,.2f}",
            ],
        }), use_container_width=True)

    except Exception as exc:
        st.error(f"Erro na avaliação: {exc}")
