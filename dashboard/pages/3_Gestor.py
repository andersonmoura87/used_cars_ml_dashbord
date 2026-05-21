"""Página Gestor — visão executiva de mercado."""
import sys
from pathlib import Path

import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from _loader import load_data, sidebar_filters

st.set_page_config(page_title="Gestor", page_icon="📊", layout="wide")

st.title("Gestor")
st.caption("Visão executiva do mercado de veículos usados")

df = load_data()
if df is None:
    st.stop()

fdf = sidebar_filters(df, show_region=True)

if fdf.empty:
    st.warning("Nenhum dado disponível com os filtros selecionados.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
current_year = datetime.date.today().year
c1, c2, c3, c4 = st.columns(4)
c1.metric("Volume total", f"{len(fdf):,}",
          f"{len(fdf)/len(df)*100:.1f}% do mercado")
c2.metric("Valor total do mercado", f"${fdf['price'].sum():,.0f}")
c3.metric("Preço médio", f"${fdf['price'].mean():,.2f}")
c4.metric("Idade média da frota", f"{(current_year - fdf['year'].mean()):.1f} anos")

st.divider()

# ── Volume ────────────────────────────────────────────────────────────────────
st.subheader("Análise de Volume")
col1, col2 = st.columns(2)

top_mfr = fdf["manufacturer"].value_counts().head(10).reset_index()
top_mfr.columns = ["Fabricante", "Quantidade"]

with col1:
    fig = go.Figure(go.Bar(
        x=top_mfr["Quantidade"], y=top_mfr["Fabricante"],
        orientation="h",
    ))
    fig.update_layout(title="Top 10 Fabricantes por Volume",
                      xaxis_title="Quantidade", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    top_models = fdf["model"].value_counts().head(10).reset_index()
    top_models.columns = ["Modelo", "Quantidade"]
    fig = go.Figure(go.Bar(
        x=top_models["Quantidade"], y=top_models["Modelo"],
        orientation="h",
    ))
    fig.update_layout(title="Top 10 Modelos por Volume",
                      xaxis_title="Quantidade", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

# ── Tendências ────────────────────────────────────────────────────────────────
st.subheader("Tendências de Preço")
price_trend = fdf.groupby("year")["price"].agg(["mean", "count"]).reset_index()

col1, col2 = st.columns(2)
with col1:
    fig = px.line(price_trend, x="year", y="mean",
                  title="Evolução do Preço Médio por Ano",
                  labels={"year": "Ano", "mean": "Preço Médio ($)"})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.bar(price_trend, x="year", y="count",
                 title="Volume de Anúncios por Ano",
                 labels={"year": "Ano", "count": "Quantidade"})
    st.plotly_chart(fig, use_container_width=True)

# ── Segmentação ───────────────────────────────────────────────────────────────
st.subheader("Segmentação")
col1, col2 = st.columns(2)

with col1:
    fuel_dist = fdf["fuel"].value_counts().reset_index()
    fuel_dist.columns = ["Combustível", "Quantidade"]
    fig = px.pie(fuel_dist, values="Quantidade", names="Combustível",
                 title="Distribuição por Combustível")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    trans_dist = fdf["transmission"].value_counts().reset_index()
    trans_dist.columns = ["Câmbio", "Quantidade"]
    fig = px.pie(trans_dist, values="Quantidade", names="Câmbio",
                 title="Distribuição por Transmissão")
    st.plotly_chart(fig, use_container_width=True)

# ── Inventário por segmento de preço ─────────────────────────────────────────
st.subheader("Segmentos de Preço")
try:
    fdf_seg = fdf.copy()
    fdf_seg["segmento"] = pd.cut(
        fdf_seg["price"], bins=5,
        labels=["Muito Baixo", "Baixo", "Médio", "Alto", "Muito Alto"],
    )
    seg_table = (
        fdf_seg.groupby("segmento", observed=True)
        .agg(Quantidade=("price", "count"), Preco_Medio=("price", "mean"), Km_Media=("odometer", "mean"))
        .round(2)
    )
    seg_table.columns = ["Quantidade", "Preço Médio ($)", "Km Média"]
    st.dataframe(seg_table, use_container_width=True)
except Exception:
    pass

# ── Mapa geográfico (se latitude/longitude disponíveis) ───────────────────────
if "latitude" in fdf.columns and "longitude" in fdf.columns:
    map_data = fdf.dropna(subset=["latitude", "longitude"])
    if not map_data.empty:
        st.subheader("Distribuição Geográfica")
        fig = px.scatter_mapbox(
            map_data.sample(min(5000, len(map_data))),
            lat="latitude", lon="longitude",
            color="price", size_max=8,
            hover_data=["manufacturer", "model", "year", "price"],
            mapbox_style="carto-positron",
            title="Distribuição de Preços por Localização",
            zoom=3, center={"lat": 37.5, "lon": -96},
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig, use_container_width=True)

