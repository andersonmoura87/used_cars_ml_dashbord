"""Página Análise Avançada — ML, clustering, previsão temporal e análise regional."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Garante que scripts/analysis/ seja encontrado a partir de qualquer CWD
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from dashboard._loader import load_data  # noqa: E402

st.set_page_config(page_title="Análise Avançada", page_icon="📈", layout="wide")

st.title("Análise Avançada de Mercado")
st.caption("Modelos preditivos, segmentação e previsão temporal")

df = load_data()
if df is None:
    st.stop()

# ── tipo de análise ───────────────────────────────────────────────────────────
analysis_type = st.sidebar.selectbox(
    "Tipo de Análise",
    ["Previsão de Preços", "Segmentação de Mercado", "Análise Temporal", "Análise Regional"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 1. Previsão de Preços
# ══════════════════════════════════════════════════════════════════════════════
if analysis_type == "Previsão de Preços":
    st.header("Previsão de Preços")

    @st.cache_resource(show_spinner="Treinando modelo…")
    def _train(hash_key: int):
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

        FEATURES = ["year", "odometer", "manufacturer", "fuel", "transmission", "condition"]
        CAT = ["manufacturer", "fuel", "transmission", "condition"]

        sub = df[FEATURES + ["price"]].dropna()
        X = sub[FEATURES].copy()
        y = sub["price"]

        encs: dict[str, LabelEncoder] = {}
        for col in CAT:
            enc = LabelEncoder()
            X[col] = enc.fit_transform(X[col].astype(str))
            encs[col] = enc

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        mdl = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05, max_depth=5, random_state=42)
        mdl.fit(X_train, y_train)
        y_pred = mdl.predict(X_test)

        feat_imp = dict(zip(FEATURES, mdl.feature_importances_))
        metrics = {
            "mae": mean_absolute_error(y_test, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
            "r2": r2_score(y_test, y_pred),
            "mse": mean_squared_error(y_test, y_pred),
        }
        return mdl, encs, feat_imp, metrics

    with st.spinner("Treinando modelo de previsão…"):
        _, _, feat_imp, metrics = _train(hash(str(df.shape)))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MAE", f"${metrics['mae']:,.2f}")
    c2.metric("RMSE", f"${metrics['rmse']:,.2f}")
    c3.metric("R²", f"{metrics['r2']:.3f}")
    c4.metric("MSE", f"${metrics['mse']:,.2f}")

    st.subheader("Importância das Features")
    imp_df = pd.DataFrame(
        sorted(feat_imp.items(), key=lambda x: x[1], reverse=True),
        columns=["Feature", "Importância"],
    )
    fig = px.bar(imp_df, x="Importância", y="Feature", orientation="h",
                 title="Importância das Features no Modelo")
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 2. Segmentação de Mercado
# ══════════════════════════════════════════════════════════════════════════════
elif analysis_type == "Segmentação de Mercado":
    st.header("Segmentação de Mercado")

    n_clusters = st.slider("Número de segmentos", 3, 8, 5)

    @st.cache_data(show_spinner="Segmentando mercado…")
    def _segment(n: int, hash_key: int):
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import LabelEncoder, StandardScaler

        FEATS = ["price", "year", "odometer"]
        sub = df[FEATS + ["manufacturer", "model"]].dropna()
        X = sub[FEATS].copy()
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        km = KMeans(n_clusters=n, random_state=42, n_init=10)
        sub = sub.copy()
        sub["cluster"] = km.fit_predict(X_scaled)
        seg_names = {i: f"Segmento {i+1}" for i in range(n)}
        sub["segment"] = sub["cluster"].map(seg_names)
        stats = sub.groupby("segment").agg(
            Preco_Medio=("price", "mean"),
            Quantidade=("price", "count"),
            Ano_Medio=("year", "mean"),
            Km_Media=("odometer", "mean"),
        ).round(2)
        return sub, stats

    with st.spinner("Realizando segmentação…"):
        df_seg, cluster_stats = _segment(n_clusters, hash(str(df.shape)))

    st.subheader("Características dos Segmentos")
    st.dataframe(cluster_stats, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.scatter(df_seg, x="year", y="price", color="segment",
                         title="Segmentos — Ano vs. Preço",
                         labels={"year": "Ano", "price": "Preço ($)"}, opacity=0.5)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.box(df_seg, x="segment", y="price",
                     title="Distribuição de Preços por Segmento",
                     labels={"segment": "Segmento", "price": "Preço ($)"})
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 3. Análise Temporal
# ══════════════════════════════════════════════════════════════════════════════
elif analysis_type == "Análise Temporal":
    st.header("Análise Temporal")

    @st.cache_data(show_spinner="Treinando Prophet…")
    def _forecast(hash_key: int):
        try:
            from prophet import Prophet
        except ImportError:
            return None, None, None

        if "posting_date" not in df.columns:
            return None, None, None

        ts = df[["posting_date", "price"]].dropna()
        ts.columns = ["ds", "y"]
        ts = ts.groupby("ds")["y"].mean().reset_index()
        ts = ts.sort_values("ds")

        if len(ts) < 10:
            return None, None, None

        m = Prophet(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False)
        m.fit(ts)
        future = m.make_future_dataframe(periods=30)
        forecast = m.predict(future)
        return forecast, ts, m

    with st.spinner("Analisando séries temporais com Prophet…"):
        forecast, historical, prophet_model = _forecast(hash(str(df.shape)))

    if forecast is None:
        st.warning(
            "Análise temporal requer a coluna `posting_date` no dataset. "
            "Verifique se os dados contêm datas de postagem."
        )
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=historical["ds"], y=historical["y"],
            name="Histórico", line=dict(color="#2563EB"),
        ))
        future_mask = forecast["ds"] > historical["ds"].max()
        fig.add_trace(go.Scatter(
            x=forecast.loc[future_mask, "ds"], y=forecast.loc[future_mask, "yhat"],
            name="Previsão (30 dias)", line=dict(color="#DC2626", dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([forecast["ds"], forecast["ds"][::-1]]),
            y=pd.concat([forecast["yhat_upper"], forecast["yhat_lower"][::-1]]),
            fill="toself", fillcolor="rgba(220,38,38,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name="Intervalo de confiança",
        ))
        fig.update_layout(
            title="Previsão de Preço Médio — Próximos 30 dias",
            xaxis_title="Data", yaxis_title="Preço Médio ($)", hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            fig2 = px.line(forecast, x="ds", y="trend",
                           title="Tendência", labels={"ds": "Data", "trend": "Tendência ($)"})
            st.plotly_chart(fig2, use_container_width=True)
        with col2:
            if "weekly" in forecast.columns:
                fig3 = px.line(forecast, x="ds", y="weekly",
                               title="Sazonalidade Semanal",
                               labels={"ds": "Data", "weekly": "Efeito"})
                st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 4. Análise Regional
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.header("Análise Regional")

    if "state" not in df.columns:
        st.warning("Coluna `state` não encontrada no dataset.")
        st.stop()

    state_stats = (
        df.groupby("state")
        .agg(
            total_anuncios=("price", "count"),
            preco_medio=("price", "mean"),
            preco_mediano=("price", "median"),
            desvio_padrao=("price", "std"),
        )
        .reset_index()
    )

    fig = px.choropleth(
        state_stats,
        locations="state", locationmode="USA-states",
        color="total_anuncios", scope="usa",
        color_continuous_scale="Blues",
        title="Distribuição de Anúncios por Estado",
        hover_data={"preco_medio": ":$,.2f", "preco_mediano": ":$,.2f"},
        labels={"total_anuncios": "Anúncios", "state": "Estado"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=520)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Estatísticas por Estado")
    display = state_stats.sort_values("total_anuncios", ascending=False).rename(columns={
        "state": "Estado", "total_anuncios": "Anúncios",
        "preco_medio": "Preço Médio ($)", "preco_mediano": "Mediana ($)",
        "desvio_padrao": "Desvio Padrão ($)",
    })
    display["Preço Médio ($)"] = display["Preço Médio ($)"].map("${:,.2f}".format)
    display["Mediana ($)"] = display["Mediana ($)"].map("${:,.2f}".format)
    display["Desvio Padrão ($)"] = display["Desvio Padrão ($)"].map("${:,.2f}".format)
    st.dataframe(display, use_container_width=True, height=400)

    # heatmap modelo × estado (top 10)
    if "model" in df.columns:
        st.subheader("Preço Médio por Modelo × Estado (top 10 modelos)")
        top10 = df["model"].value_counts().head(10).index
        pivot = (
            df[df["model"].isin(top10)]
            .groupby(["model", "state"])["price"]
            .mean()
            .unstack(fill_value=0)
        )
        fig2 = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale="Viridis", colorbar=dict(title="Preço ($)"),
        ))
        fig2.update_layout(
            title="Preço Médio ($) por Modelo × Estado",
            xaxis_title="Estado", yaxis_title="Modelo",
            height=500, xaxis_tickangle=-45,
        )
        st.plotly_chart(fig2, use_container_width=True)
